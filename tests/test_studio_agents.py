import importlib.util
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timedelta,timezone
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend import app as module
from backend.model_access import model_scope,effective_mode,key_for,model_for
from backend.product_studio import QUESTIONS
from backend.product_templates import generate,validate

@pytest.fixture
def private_client(monkeypatch):
    monkeypatch.setenv('EVOLVYN_VAULT_MASTER_KEY',Fernet.generate_key().decode())
    with TestClient(module.app,client=(uuid4().hex,50000)) as c:
        c.headers['X-Requested-With']='Evolvyn'
        response=c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'studio-acceptance-password','name':'Studio acceptance'})
        assert response.status_code==201,response.text
        c.org=response.json()['organization_id']
        yield c

def credential(c,provider='provider'):
    value='private-unit-key-'+uuid4().hex
    response=c.post('/api/vault/credentials',json={'name':'Unit credential','provider':provider,'value':value})
    assert response.status_code==200,response.text
    return response.json(),value

def conversation(c):
    conv=c.post('/api/conversations',json={'title':'Specialist evidence'}).json()
    c.post('/api/conversations/'+conv['id']+'/files',files={'file':('funnel.csv',Path('sample-data/funnel.csv').read_bytes())}).raise_for_status()
    return conv

def build(c,stack='react_fastapi'):
    product=c.post('/api/studio/products',json={'name':'Customer workspace','goal':'Manage customer work with private records'}).json()
    for field,_,answer in QUESTIONS:
        if field=='stack':answer=stack
        response=c.post('/api/studio/products/'+product['id']+'/answers',json={'field':field,'text':answer,'revision':product['revision']})
        assert response.status_code==200,response.text
        product=response.json()
    response=c.post('/api/studio/products/'+product['id']+'/build',json={'revision':product['revision']})
    assert response.status_code==200,response.text
    return product,response.json()

def test_vault_ciphertext_only_rotation_revocation_and_no_readback(private_client):
    c=private_client;row,value=credential(c)
    assert value not in json.dumps(row)
    with module.conn() as db:raw=db.execute("SELECT body FROM records WHERE id=%s",(row['id'],)).fetchone()['body']
    assert value not in json.dumps(raw) and raw['ciphertext']
    assert module.VAULT.reveal_for_service(c.org,row['id'],'provider')==value
    replacement='replacement-unit-key-'+uuid4().hex
    response=c.put('/api/vault/credentials/'+row['id'],json={'name':'Rotated','provider':'provider','value':replacement})
    assert response.status_code==200 and response.json()['version']==2
    assert replacement not in c.get('/api/vault').text
    assert module.VAULT.reveal_for_service(c.org,row['id'],'provider')==replacement
    assert c.delete('/api/vault/credentials/'+row['id']).status_code==200
    with module.conn() as db:raw=db.execute("SELECT body FROM records WHERE id=%s",(row['id'],)).fetchone()['body']
    assert 'ciphertext' not in raw
    with pytest.raises(Exception):module.VAULT.reveal_for_service(c.org,row['id'],'provider')

def test_default_and_per_agent_routes_are_tenant_scoped(private_client):
    c=private_client;row,value=credential(c,'groq')
    c.put('/api/vault/bindings/default',json={'provider':'groq','credential_id':row['id'],'model':'model-for-all'}).raise_for_status()
    c.put('/api/vault/bindings/reviewer',json={'provider':'evidence'}).raise_for_status()
    from backend.providers import PROVIDERS
    with model_scope(c.org,'product_manager'):
        assert effective_mode('default')=='groq'
        assert key_for('groq',PROVIDERS['groq'])==value
        assert model_for('groq',PROVIDERS['groq'])=='model-for-all'
    with model_scope(c.org,'reviewer'):assert effective_mode('default')=='evidence'
    with model_scope('another-organization','product_manager'):assert effective_mode('default')=='local'
    assert c.put('/api/vault/bindings/architect',json={'provider':'provider','credential_id':row['id']}).status_code==409
    assert c.put('/api/vault/bindings/architect',json={'provider':'groq','credential_id':'foreign-id'}).status_code==409

def test_memory_requires_review_and_filters_scope_retention_and_forgetting(private_client):
    c=private_client
    proposal=c.post('/api/memory',json={'text':'Prefer accessible dark themes for customer dashboards','category':'preference','retention_days':30}).json()
    assert c.get('/api/memory/recall?q=dark').json()==[]
    c.post('/api/memory/'+proposal['id']+'/decision',json={'accept':True}).raise_for_status()
    assert c.get('/api/memory/recall?q=dark').json()[0]['id']==proposal['id']
    assert c.post('/api/memory/'+proposal['id']+'/decision',json={'accept':True}).status_code==409
    assert c.get('/api/memory/recall?q=dark&project_id=foreign').status_code==404
    with module.conn() as db:
        row=db.execute('SELECT body FROM records WHERE id=%s',(proposal['id'],)).fetchone()['body'];row['expires_at']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        db.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(row),proposal['id']))
    assert c.get('/api/memory/recall?q=dark').json()==[]
    assert c.delete('/api/memory/'+proposal['id']).status_code==200
    assert c.get('/api/memory').json()==[]

def test_secret_patterns_are_rejected_from_memory_and_requirements(private_client):
    secret='sk-proj-'+'A'*48
    response=private_client.post('/api/memory',json={'text':secret})
    assert response.status_code==422 and secret not in response.text
    response=private_client.post('/api/studio/products',json={'name':'Private','goal':'Use '+secret})
    assert response.status_code==422 and secret not in response.text

def test_actual_langgraph_handoffs_approval_and_memory(private_client):
    c=private_client;conv=conversation(c)
    response=c.post('/api/discussions',json={'conversation_id':conv['id'],'goal':'Review conversion and product priorities','mode':'evidence'})
    assert response.status_code==202,response.text
    id=response.json()['id'];c.get('/api/executions/'+id+'/live')
    run=c.get('/api/executions/'+id).json()
    assert run['state']=='WAITING_FOR_APPROVAL',run
    assert set(run['discussion_result']['outputs'])=={'business_analyst','marketing_analyst','product_manager','reviewer'}
    assert len({o['text'] for o in run['discussion_result']['outputs'].values()})==4
    assert all(o['classification'].startswith('Deterministic') for o in run['discussion_result']['outputs'].values())
    assert c.post('/api/executions/'+id+'/decision',json={'approve':True,'plan':'Bypass discussion gate'}).status_code==409
    decision=c.post('/api/discussions/'+id+'/decision',json={'approve':True,'plan':'Validate the conversion baseline before changing the product'})
    assert decision.status_code==200 and decision.json()['state']=='COMPLETED'
    assert c.get('/api/memory/recall?q=conversion').json()[0]['id']==decision.json()['memory_id']
    assert c.post('/api/discussions/'+id+'/decision',json={'approve':True,'plan':'Duplicate decision'}).status_code==409

def test_review_loop_is_bounded_and_unresolved_issues_require_explicit_ack(private_client,monkeypatch):
    calls=[]
    async def respond(owner,agent,conversation,report,goal,handoffs,mode,allow_fallback):
        calls.append(agent)
        return {'text':'Claim 77% ['+report['facts'][0]['source']+']','fallback':False,'mode':'local','classification':'Mocked model response'}
    monkeypatch.setattr(module.AGENTS,'respond',respond)
    c=private_client;conv=conversation(c)
    response=c.post('/api/discussions',json={'conversation_id':conv['id'],'goal':'Check numerical claims against sources','mode':'evidence','max_rounds':2})
    id=response.json()['id'];c.get('/api/executions/'+id+'/live');run=c.get('/api/executions/'+id).json()
    assert run['state']=='WAITING_FOR_APPROVAL',run
    assert run['discussion_result']['round']==2
    assert calls.count('product_manager')==2 and calls.count('reviewer')==2
    assert run['discussion_result']['issues']
    assert c.post('/api/discussions/'+id+'/decision',json={'approve':True,'plan':'Accept unverified 77%'}).status_code==409
    result=c.post('/api/discussions/'+id+'/decision',json={'approve':True,'plan':'I corrected the plan: verify 8% and 5% from the source rows','acknowledge_issues':True})
    assert result.status_code==200

def test_remote_route_data_policy_is_checked_before_model_call(private_client,monkeypatch):
    c=private_client;row,value=credential(c)
    c.put('/api/vault/bindings/default',json={'provider':'provider','credential_id':row['id']}).raise_for_status()
    policy=c.get('/api/governance/policy').json()
    c.put('/api/governance/policy',json={**policy,'allow_external_processing':False}).raise_for_status()
    conv=conversation(c)
    result=c.post('/api/discussions',json={'conversation_id':conv['id'],'goal':'Do not export private evidence','mode':'default'})
    assert result.status_code==403

@pytest.mark.parametrize('stack',['react_fastapi','react_express'])
def test_requirements_to_source_and_persisted_prototype(private_client,stack):
    c=private_client;product,result=build(c,stack)
    assert result['state']=='READY',result
    assert [e['stage'] for e in result['events']]==['architect','developer','reviewer']
    archive=c.get('/api/studio/builds/'+result['id']+'/download')
    assert archive.status_code==200
    files=zipfile.ZipFile(io.BytesIO(archive.content))
    assert 'frontend/src/main.jsx' in files.namelist()
    assert ('backend/app.py' if stack=='react_fastapi' else 'backend/server.mjs') in files.namelist()
    path='/api/studio/builds/'+result['id']+'/preview/tasks'
    item=c.post(path,json={'title':'Customer interview','status':'todo'})
    assert item.status_code==200,item.text
    assert c.get(path).json()[0]['data']['title']=='Customer interview'
    assert c.get('/api/studio/builds/foreign/preview/tasks').status_code==404
    assert c.post(path,json={'title':'missing status'}).status_code==422
    assert c.delete(path+'/'+item.json()['id']).status_code==200
    assert c.get(path).json()==[]
    assert c.post('/api/studio/products/'+product['id']+'/answers',json={'field':'theme','text':'dark','revision':1}).status_code==409

def sample_spec(stack='react_fastapi'):
    spec={field:__import__('backend.product_studio',fromlist=['parsed_answer']).parsed_answer(field,answer) for field,_,answer in QUESTIONS}
    return {**spec,'name':'Generated test product','goal':'Manage work','stack':stack}

def test_generated_fastapi_accounts_and_private_crud_execute(tmp_path,monkeypatch):
    files=generate(sample_spec());validate(files)
    for name in ('backend/app.py','backend/spec.json'):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(files[name])
    monkeypatch.setenv('DATABASE_URL','sqlite:///'+str(tmp_path/'product.db'))
    spec=importlib.util.spec_from_file_location('generated_product',tmp_path/'backend/app.py');product=importlib.util.module_from_spec(spec);sys.modules[spec.name]=product;spec.loader.exec_module(product)
    with TestClient(product.app) as c:
        c.headers['X-Requested-With']='Product'
        invalid=c.post('/api/register',json={'email':'owner@example.test','password':'tiny-secret'})
        assert invalid.status_code==422 and 'tiny-secret' not in invalid.text
        response=c.post('/api/register',json={'email':'owner@example.test','password':'generated-test-password'})
        assert response.status_code==201,response.text
        item=c.post('/api/items/tasks',json={'title':'Private customer task','status':'todo'})
        assert item.status_code==201,item.text
        id=item.json()['id']
        assert c.post('/api/logout').status_code==200
        assert c.get('/api/items/tasks').status_code==401
        assert c.post('/api/register',json={'email':'other@example.test','password':'generated-test-password'}).status_code==201
        assert c.get('/api/items/tasks').json()==[]
        assert c.delete('/api/items/tasks/'+id).status_code==404
        assert c.put('/api/items/tasks/'+id,json={'title':'Steal record','status':'done'}).status_code==404
        assert c.post('/api/items/tasks',json={'title':'a','status':'b','owner':'foreign'}).status_code==422

def test_generated_frontend_builds_and_node_adapter_parses(tmp_path):
    for name,content in generate(sample_spec('react_express')).items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
    result=subprocess.run(['node','--check',str(tmp_path/'backend/server.mjs')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    (tmp_path/'frontend/node_modules').symlink_to(Path('frontend/node_modules').resolve(),target_is_directory=True)
    result=subprocess.run([str(Path('frontend/node_modules/.bin/vite').resolve()),'build'],cwd=tmp_path/'frontend',capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'frontend/dist/index.html').exists()

def test_vault_rejects_editor_access_and_foreign_ciphertext(private_client):
    c=private_client;owner_cookie=c.cookies.get('evolvyn_session');owner_org=c.org
    row,value=credential(c)
    foreign='foreign-cipher-'+uuid4().hex
    with module.conn() as db:
        data=db.execute('SELECT body FROM records WHERE id=%s',(row['id'],)).fetchone()['body']
        db.execute("INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,'vault_secret',%s)",(foreign,'foreign-org',json.dumps(data)))
    with pytest.raises(Exception) as error:module.VAULT.reveal_for_service('foreign-org',foreign,'provider')
    assert error.value.status_code==503
    email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':email,'password':'member-acceptance-password','name':'Editor'}).raise_for_status();member_cookie=c.cookies.get('evolvyn_session')
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/');c.headers['X-Organization-Id']=owner_org
    c.post('/api/organizations/members',json={'email':email,'role':'editor'}).raise_for_status()
    c.cookies.set('evolvyn_session',member_cookie,domain='testserver.local',path='/')
    assert c.get('/api/vault').status_code==403
    assert c.put('/api/vault/bindings/default',json={'provider':'evidence'}).status_code==403
    assert value not in c.get('/api/agents').text

def test_gateway_uses_vault_key_only_in_header_and_blocks_reflection(private_client,monkeypatch):
    c=private_client;row,value=credential(c)
    c.put('/api/vault/bindings/default',json={'provider':'provider','credential_id':row['id']}).raise_for_status()
    requests=[];reflect=[False]
    async def handler(request):
        assert request.headers['authorization']=='Bearer '+value
        assert value not in request.content.decode()
        requests.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':value if reflect[0] else 'A concise, reviewable response.'}}],'usage':{'completion_tokens':7,'unexpected_private_field':value}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    result=c.post('/api/agents/default/test')
    assert result.status_code==200 and result.json()['available'] is True,result.text
    assert value not in result.text and 'unexpected_private_field' not in result.text
    reflect[0]=True
    result=c.post('/api/agents/default/test')
    assert result.status_code==200 and result.json()['available'] is False
    assert value not in result.text

def test_source_build_respects_org_tool_deny_policy(private_client):
    c=private_client;product,result=build(c)
    policy=c.get('/api/governance/policy').json()
    c.put('/api/governance/policy',json={**policy,'denied_tools':['build_product']}).raise_for_status()
    response=c.post('/api/studio/products/'+product['id']+'/build',json={'revision':product['revision']})
    assert response.status_code==403
    assert c.get('/api/studio/builds').json()[0]['id']==result['id']

def test_reviewed_business_decision_versions_requirements_without_mutating_build(private_client):
    c=private_client;product,artifact=build(c)
    memory=c.post('/api/memory',json={'category':'decision','text':'Use an accessible dark theme for the next product revision'}).json()
    body={'memory_id':memory['id'],'revision':product['revision'],'changes':{'theme':'dark','accent':'#234567'}}
    assert c.post('/api/studio/products/'+product['id']+'/decisions',json=body).status_code==409
    c.post('/api/memory/'+memory['id']+'/decision',json={'accept':True}).raise_for_status()
    updated=c.post('/api/studio/products/'+product['id']+'/decisions',json=body)
    assert updated.status_code==200,updated.text
    assert updated.json()['revision']==product['revision']+1
    assert updated.json()['requirements']['theme']=='dark'
    assert updated.json()['decision_history'][0]['memory_id']==memory['id']
    prior=c.get('/api/studio/builds/'+artifact['id']).json()
    assert prior['spec']['theme']=='light' and prior['source_sha256']==artifact['source_sha256']
    assert c.post('/api/studio/products/'+product['id']+'/decisions',json=body).status_code==409

def test_gateway_rechecks_project_policy_before_credentials_or_network(private_client):
    from backend.model_access import model_data_scope
    from backend.providers import provider_config
    c=private_client;row,_=credential(c)
    c.put('/api/vault/bindings/default',json={'provider':'provider','credential_id':row['id']}).raise_for_status()
    business=c.post('/api/businesses',json={'name':'Privacy scope'}).json()
    project=c.post('/api/projects',json={'name':'Sensitive','goal':'Keep processing local','business_id':business['id']}).json()
    with model_scope(c.org,'business_analyst'),model_data_scope({'project_id':project['id']}):
        with pytest.raises(Exception) as error:provider_config('default')
        assert error.value.status_code==403

def test_background_actor_role_is_revalidated(private_client):
    from backend.policy import ACTOR,Principal
    c=private_client;identity=c.get('/api/auth/me').json()
    token=ACTOR.set(Principal(c.org,identity['account']['id'],'owner'))
    try:
        with module.conn() as db:db.execute("UPDATE memberships SET role='viewer' WHERE organization_id=%s AND account_id=%s",(c.org,identity['account']['id']))
        with pytest.raises(Exception) as error:module.POLICY.require(c.org,'write')
        assert error.value.status_code==403
    finally:ACTOR.reset(token)

def test_agent_capability_boundary_is_enforced_in_graph(private_client):
    c=private_client;conv=conversation(c)
    definition={'name':'Role boundary','goal':'Enforce specialist capability scope','entry':'read','nodes':[{'id':'read','type':'tool','agent_id':'marketing_analyst','tool':'analyze_business','arguments':{'conversation_id':conv['id'],'query':'conversion'}}],'edges':[]}
    graph=c.post('/api/harness/graphs',json=definition).json()
    response=c.post('/api/harness/graphs/'+graph['id']+'/run',json={'conversation_id':conv['id']});assert response.status_code==202,response.text
    id=response.json()['id'];c.get('/api/executions/'+id+'/live');run=c.get('/api/executions/'+id).json()
    assert run['state']=='FAILED' and run['graph_checkpoint']['tools_used']==0

def test_legacy_analysis_cannot_bypass_project_egress_policy(private_client,monkeypatch):
    c=private_client
    business=c.post('/api/businesses',json={'name':'Legacy privacy'}).json()
    project=c.post('/api/projects',json={'name':'Local source','goal':'Keep documents local','business_id':business['id']}).json()
    conv=c.post('/api/conversations',json={'title':'Legacy route','business_id':business['id'],'project_id':project['id']}).json()
    c.post('/api/conversations/'+conv['id']+'/files',files={'file':('funnel.csv',Path('sample-data/funnel.csv').read_bytes())}).raise_for_status()
    monkeypatch.setenv('MODEL_API_KEY','unusable-unit-test-key')
    response=c.post('/api/conversations/'+conv['id']+'/analyze',json={'text':'Keep private evidence local','mode':'provider'})
    assert response.status_code==403
    response=c.post('/api/conversations/'+conv['id']+'/analyze',json={'text':'Analyze locally','mode':'evidence'})
    assert response.status_code==200 and response.json()['state']=='WAITING_FOR_APPROVAL'

def test_background_specialists_use_individual_vault_routes_and_report_usage(private_client,monkeypatch):
    c=private_client;default,key1=credential(c);marketing,key2=credential(c,'groq')
    c.put('/api/vault/bindings/default',json={'provider':'provider','credential_id':default['id']}).raise_for_status()
    c.put('/api/vault/bindings/marketing_analyst',json={'provider':'groq','credential_id':marketing['id']}).raise_for_status()
    hosts=[]
    async def handler(request):
        hosts.append(request.url.host)
        expected=key2 if request.url.host=='api.groq.com' else key1
        assert request.headers['authorization']=='Bearer '+expected
        assert key1 not in request.content.decode() and key2 not in request.content.decode()
        context=json.loads(json.loads(request.content)['messages'][-1]['content'])
        source=context['facts'][0]['source']
        return httpx.Response(200,json={'choices':[{'message':{'content':'Review the 8% and 5% observations ['+source+']; validate before changing the product.'}}],'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    conv=conversation(c)
    response=c.post('/api/discussions',json={'conversation_id':conv['id'],'goal':'Review conversion with specialist model routing','mode':'default','allow_fallback':False,'max_rounds':1})
    assert response.status_code==202,response.text
    id=response.json()['id'];c.get('/api/executions/'+id+'/live');run=c.get('/api/executions/'+id).json()
    assert run['state']=='WAITING_FOR_APPROVAL',run
    assert run['discussion_result']['outputs']['marketing_analyst']['mode']=='groq'
    assert not any(o['fallback'] for o in run['discussion_result']['outputs'].values())
    assert hosts.count('api.groq.com')==1 and hosts.count('api.openai.com')==3
    rows=c.get('/api/usage').json()['providers']
    assert sum(r['calls'] for r in rows)==4
    assert sum(r['completion_tokens'] for r in rows)==40
    assert key1 not in json.dumps(run) and key2 not in json.dumps(run)

def test_known_route_secret_cannot_enter_model_context(private_client,monkeypatch):
    import asyncio
    c=private_client;row,value=credential(c)
    c.put('/api/vault/bindings/default',json={'provider':'provider','credential_id':row['id']}).raise_for_status()
    calls=[]
    async def handler(request):calls.append(request);raise AssertionError('Secret must be rejected before transport')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    with pytest.raises(Exception) as error:
        asyncio.run(module.AGENTS.respond(c.org,'supervisor',{}, {'facts':[],'evidence':[]},'Do not transmit '+value,{},'default',False))
    assert error.value.status_code==502 and calls==[]
    for secret in ('gsk_'+'A'*40,'AIza'+'B'*40):
        response=c.post('/api/memory',json={'text':secret})
        assert response.status_code==422 and secret not in response.text
