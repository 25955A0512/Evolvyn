"""Support/agent credential separation and real automation dispatch/approval boundaries."""
import json
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import app as module
from backend.model_access import model_scope,key_for
from backend.providers import PROVIDERS

@pytest.fixture
def c():
    with TestClient(module.app,client=(uuid4().hex,40000)) as c:
        c.headers['X-Requested-With']='Evolvyn'
        response=c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'experience-acceptance-password','name':'Experience acceptance'})
        response.raise_for_status();c.org=response.json()['organization_id'];yield c

def configure(monkeypatch):
    primary='help-primary-'+uuid4().hex;backup='help-backup-'+uuid4().hex
    for key,value in {'EVOLVYN_HELP_GEMINI_KEY':primary,'EVOLVYN_HELP_GEMINI_MODEL':'unit-gemini-model','EVOLVYN_HELP_GROQ_KEY':backup,'EVOLVYN_HELP_GROQ_MODEL':'unit-groq-model'}.items():monkeypatch.setenv(key,value)
    return primary,backup

def test_support_is_unavailable_without_credentials_and_has_no_canned_reply(c,monkeypatch):
    for name in ('EVOLVYN_HELP_GEMINI_KEY','EVOLVYN_HELP_GROQ_KEY'):monkeypatch.delenv(name,raising=False)
    response=c.post('/api/help/ask',json={'question':'How do I find the analysis mode?'})
    assert response.status_code==503 and 'No AI answer' in response.text
    assert c.get('/api/help/threads').json()==[]

def test_help_gemini_to_groq_is_real_transport_failover_without_agent_key_reuse(c,monkeypatch):
    primary,backup=configure(monkeypatch);seen=[]
    async def handler(request):
        seen.append(request.url.host);body=request.content.decode()
        assert primary not in body and backup not in body
        if request.url.host=='generativelanguage.googleapis.com':
            assert request.headers['authorization']=='Bearer '+primary
            return httpx.Response(429,json={'error':'Quota limited'})
        assert request.url.host=='api.groq.com' and request.headers['authorization']=='Bearer '+backup
        return httpx.Response(200,json={'choices':[{'message':{'content':'Generated support answer '+marker}}],'usage':{'total_tokens':22,'private_extra':primary}})
    marker=uuid4().hex
    original=httpx.AsyncClient;monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    response=c.post('/api/help/ask',json={'question':'How do I connect a tool?'})
    assert response.status_code==200,response.text
    thread=response.json();message=thread['messages'][-1]
    assert message['text']=='Generated support answer '+marker and message['provider']=='groq' and message['fallback'] is True
    assert seen==['generativelanguage.googleapis.com','api.groq.com']
    assert primary not in response.text and backup not in response.text and 'private_extra' not in response.text
    assert c.get('/api/help/threads').json()[0]['id']==thread['id']
    with model_scope(c.org,'business_analyst'):
        assert key_for('gemini',PROVIDERS['gemini'])!=primary and key_for('groq',PROVIDERS['groq'])!=backup

def test_support_secret_input_and_reflection_never_persist(c,monkeypatch):
    primary,backup=configure(monkeypatch)
    assert c.post('/api/help/ask',json={'question':'My credential is '+primary}).status_code==422
    assert c.get('/api/help/threads').json()==[]
    async def handler(request):return httpx.Response(200,json={'choices':[{'message':{'content':primary+' '+backup}}]})
    original=httpx.AsyncClient;monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    response=c.post('/api/help/ask',json={'question':'What is the registry?'})
    assert response.status_code==503
    history=c.get('/api/help/threads').json()
    assert primary not in json.dumps(history) and backup not in json.dumps(history)
    assert history[0]['state']=='FAILED' and len(history[0]['messages'])==1

def test_help_respects_org_policy_and_tenant_scope(c,monkeypatch):
    configure(monkeypatch)
    policy=c.get('/api/governance/policy').json();c.put('/api/governance/policy',json={**policy,'allow_external_processing':False}).raise_for_status()
    assert c.post('/api/help/ask',json={'question':'Explain the platform'}).status_code==403
    row=module.save('another-owner','help_thread',{'messages':[],'state':'IDLE'})
    c.put('/api/governance/policy',json=policy).raise_for_status()
    assert c.post('/api/help/ask',json={'question':'Read another tenant','thread_id':row['id']}).status_code==404

def conversation(c):return c.post('/api/conversations',json={'title':'Automation source'}).json()
def trigger(c,conv,condition=None):
    response=c.post('/api/automations',json={'name':'Review uploaded sales','conversation_id':conv['id'],'query':'Review actual sales and propose a safe investigation','mode':'evidence','condition':condition})
    assert response.status_code==200,response.text
    return response.json()
def upload(c,conv):
    response=c.post('/api/conversations/'+conv['id']+'/files',files={'file':('sales.csv',Path('sample-data/ecommerce-sales.csv').read_bytes())});response.raise_for_status();return response.json()

def test_upload_condition_dispatches_once_and_never_approves(c):
    conv=conversation(c);rule=trigger(c,conv,{'metric':'net_revenue','op':'lt','value':'50'});doc=upload(c,conv)
    response=c.post('/api/automations/'+rule['id']+'/run');assert response.status_code==200,response.text
    event=response.json()[0];assert event['state']=='QUEUED' and event['condition_result']['observed']=='45.10'
    id=event['execution_id'];c.get('/api/executions/'+id+'/live');execution=c.get('/api/executions/'+id).json()
    assert execution['state']=='WAITING_FOR_APPROVAL' and execution['automation_event_id']==event['id']
    assert execution['report']['commerce']['primary']['dataset_id']==doc['id']
    assert c.get('/api/tasks').json()==[] and 'artifact' not in execution
    repeated=c.post('/api/automations/'+rule['id']+'/run').json()
    assert len(repeated)==1 and repeated[0]['execution_id']==id
    assert len([r for r in module.listing(c.org,'execution') if r.get('automation_event_id')==event['id']])==1

def test_false_or_missing_metric_skips_without_a_model_or_execution(c):
    conv=conversation(c);rule=trigger(c,conv,{'metric':'orders','op':'gt','value':'100'});upload(c,conv)
    events=c.post('/api/automations/'+rule['id']+'/run').json()
    assert events[0]['state']=='SKIPPED' and not events[0].get('execution_id')
    assert module.listing(c.org,'execution')==[]
    c.patch('/api/automations/'+rule['id'],json={'enabled':False}).raise_for_status()
    assert c.post('/api/automations/'+rule['id']+'/run').status_code==409

def test_automation_revoked_creator_and_other_tenant_are_denied(c):
    conv=conversation(c);rule=trigger(c,conv);upload(c,conv)
    with module.conn() as db:db.execute('DELETE FROM memberships WHERE organization_id=%s',(c.org,))
    c.portal.call(module.AUTOMATIONS.tick)
    with module.conn() as db:
        row=db.execute("SELECT body FROM records WHERE owner=%s AND kind='automation_event'",(c.org,)).fetchone()['body']
        assert row['state']=='FAILED'
        assert db.execute("SELECT count(*) AS count FROM records WHERE owner=%s AND kind='execution'",(c.org,)).fetchone()['count']==0

def test_strict_ai_run_does_not_substitute_rules_when_workspace_key_is_missing(c,monkeypatch):
    conv=conversation(c);upload(c,conv)
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    response=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Use an actual configured model','mode':'gemini','allow_fallback':False})
    response.raise_for_status();id=response.json()['id'];c.get('/api/executions/'+id+'/live')
    result=c.get('/api/executions/'+id).json()
    assert result['state']=='FAILED' and not result.get('output') and not (result.get('report') or {}).get('strategy_fallback')
