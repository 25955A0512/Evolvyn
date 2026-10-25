"""Synthetic provider boundaries; real registry, worker, PostgreSQL and scoped APIs."""
import asyncio,copy,json
from datetime import datetime,timezone,timedelta
from uuid import uuid4
import httpx,pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend import app as module
from backend import social_mcp
from backend.social_contract import Observation,metrics,forecast


def observation():
    return {'provider':'instagram','account_id':'12345','account_name':'Synthetic store','captured_at':datetime.now(timezone.utc).isoformat(),'posts':[{'id':'post1','published_at':'2026-01-01T00:00:00+00:00','url':'https://www.instagram.com/p/synthetic/','text':'Synthetic product post','likes':10,'comments':2}], 'comment_sample':[{'id':'comment1','text':'Please contact test@example.test or @person','published_at':'2026-01-02T00:00:00+00:00'}],'coverage':'Synthetic controlled boundary, lifetime counters, not live data.'}

def test_metrics_unknown_values_redaction_and_contract():
    row=Observation.model_validate(observation()).model_dump(mode='json')
    assert metrics(row)=={'posts_observed':1,'followers':None,'likes':10,'comments':2,'views':None,'interactions':12,'interactions_per_100_views':None}
    assert 'test@example.test' not in row['comment_sample'][0]['text'] and '@person' not in row['comment_sample'][0]['text']
    row['posts'][0]['likes']=None;assert metrics(row)['interactions'] is None
    row['posts']=[];assert metrics(row)['likes'] is None
    for edit in ('duplicate','negative','url','timezone','provider','future','string'):
        bad=observation()
        if edit=='duplicate':bad['posts']*=2
        if edit=='negative':bad['posts'][0]['likes']=-1
        if edit=='url':bad['posts'][0]['url']='https://evil.example/track'
        if edit=='timezone':bad['captured_at']='2026-01-02T00:00:00'
        if edit=='provider':bad['provider']='youtube'
        if edit=='future':bad['posts'][0]['published_at']='2099-01-01T00:00:00+00:00'
        if edit=='string':bad['posts'][0]['likes']='10'
        with pytest.raises(ValidationError):Observation.model_validate(bad)

def daily_history():
    end=datetime.now(timezone.utc);rows=[]
    for n in range(29):
        obs=Observation.model_validate(observation()).model_dump(mode='json');obs['captured_at']=(end-timedelta(days=28-n)).isoformat();obs['posts'][0]['likes']=n*10
        rows.append({'observation':obs,'metrics':metrics(obs),'config_binding':'same'})
    return rows

def test_forecast_gates_and_backtest():
    rows=daily_history();result=forecast(rows)
    assert result['status']=='available' and result['daily_estimate']==10 and result['mae']==0 and result['sample_size']==28
    assert 'not a calibrated' in result['uncertainty']
    assert forecast(rows[:10])['status']=='suppressed'
    for edit in ('cohort','stale','missing','revised','config','interval'):
        bad=copy.deepcopy(rows)
        if edit=='cohort':bad[-1]['observation']['posts'][0]['id']='new'
        if edit=='stale':bad[-1]['observation']['captured_at']=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
        if edit=='missing':bad[-1]['metrics']['interactions']=None
        if edit=='revised':bad[-1]['metrics']['interactions']=0
        if edit=='config':bad[-1]['config_binding']='rotated'
        if edit=='interval':bad[-1]['observation']['captured_at']=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        assert forecast(bad)['status']=='suppressed',edit

@pytest.fixture
def c():
    with TestClient(module.app,client=(uuid4().hex,40000)) as c:
        c.headers['X-Requested-With']='Evolvyn'
        c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'synthetic-social-password','name':'Social tests'}).raise_for_status()
        yield c

def source(c):
    conv=c.post('/api/conversations',json={'title':'Synthetic social acceptance'}).json()
    credential=c.post('/api/vault/credentials',json={'name':'Synthetic Meta credential, not live','provider':'mcp','value':'synthetic-meta-'+uuid4().hex});credential.raise_for_status()
    response=c.post('/api/growth/social/native',json={'conversation_id':conv['id'],'profile':'instagram_social','credential_id':credential.json()['id'],'account_id':'12345','name':'Synthetic social source'})
    response.raise_for_status()
    return conv,response.json(),credential.json()

def collect(c,source):
    response=c.post('/api/growth/social/'+source['id']+'/sync');response.raise_for_status();run=response.json()
    c.get('/api/executions/'+run['id']+'/live').raise_for_status()
    return c.get('/api/executions/'+run['id']).json()

def test_social_lifecycle_real_stdio_discovery_worker_persistence_and_review(c,monkeypatch):
    conv,s,credential=source(c)
    assert any(t['name']=='social_account_snapshot' for t in c.get('/api/mcp/servers').json()[0]['tools'])
    before=c.get('/api/growth/social',params={'conversation_id':conv['id']}).json()[0]
    assert before['latest'] is None and before['last_success_at'] is None
    calls=[]
    async def boundary(owner,server,tool,args):
        calls.append(args);return observation()
    monkeypatch.setattr(module.MCP_REGISTRY,'call',boundary)
    result=collect(c,s);assert result['state']=='COMPLETED',result
    assert calls==[{'account_id':'12345','conversation_id':conv['id']}]
    rows=c.get('/api/growth/social',params={'conversation_id':conv['id']}).json();row=rows[0]
    assert row['latest']['metrics']['interactions']==12 and len(row['history'])==1
    assert row['last_success_at'] and row['last_execution']['state']=='COMPLETED'
    assert '[email redacted]' in row['latest']['observation']['comment_sample'][0]['text']
    exported=c.get('/api/growth/social/'+s['id']+'/report');assert exported.status_code==200
    assert exported.json()['snapshot']['id']==row['latest']['id'] and exported.headers['cache-control']=='no-store'
    # Reopening live observation is not a second provider request or snapshot.
    c.get('/api/executions/'+result['id']+'/live');assert len(calls)==1
    assert c.post('/api/growth/social/'+s['id']+'/sync').status_code==429
    review=c.post('/api/growth/social/'+s['id']+'/review',json={'mode':'evidence'});review.raise_for_status()
    c.get('/api/executions/'+review.json()['id']+'/live')
    review=c.get('/api/executions/'+review.json()['id']).json();assert review['state']=='COMPLETED',review
    assert set(review['graph_checkpoint']['nodes'])=={'business_intelligence','customer_research','growth_strategy'}
    assert 'no model was called' in review['graph_checkpoint']['nodes']['growth_strategy']['output']['text']
    monitor=c.post('/api/growth/social/'+s['id']+'/monitor',json={'enabled':True,'interval_minutes':1440});monitor.raise_for_status()
    assert any(x.get('social_source_id')==s['id'] for x in c.get('/api/schedules').json())
    assert c.post('/api/growth/social/'+s['id']+'/monitor',json={'enabled':False}).json()['enabled'] is False
    c.delete('/api/growth/social/'+s['id']).raise_for_status()
    assert c.post('/api/growth/social/'+s['id']+'/sync').status_code==409
    row=c.get('/api/growth/social',params={'conversation_id':conv['id']}).json()[0]
    assert not row['enabled'] and len(row['history'])==1 and row['forecast']['status']=='suppressed'
    assert c.get('/api/tasks').json()==[] # collection and review never execute business actions

@pytest.mark.parametrize('failure',['account','schema','provider','revocation'])
def test_rejected_observations_never_saved(c,monkeypatch,failure):
    conv,s,cred=source(c)
    async def boundary(*args):
        if failure=='provider':raise RuntimeError('synthetic upstream secret must not leak')
        data=observation()
        if failure=='account':data['account_id']='other'
        if failure=='schema':data['posts'][0]['likes']=-1
        if failure=='revocation':c.delete('/api/vault/credentials/'+cred['id']).raise_for_status()
        return data
    monkeypatch.setattr(module.MCP_REGISTRY,'call',boundary)
    result=collect(c,s);assert result['state']=='FAILED',result
    row=c.get('/api/growth/social',params={'conversation_id':conv['id']}).json()[0]
    assert row['latest'] is None and row['last_success_at'] is None
    assert 'synthetic upstream secret' not in json.dumps(result)


def test_scope_local_policy_and_trash(c,monkeypatch):
    conv,s,cred=source(c)
    settings=c.get('/api/governance/policy').json()
    c.put('/api/governance/policy',json={**settings,'allow_external_processing':False}).raise_for_status()
    assert c.post('/api/growth/social/'+s['id']+'/sync').status_code==403
    c.put('/api/governance/policy',json=settings).raise_for_status()
    c.delete('/api/conversations/'+conv['id']).raise_for_status()
    assert c.get('/api/growth/social',params={'conversation_id':conv['id']}).status_code==404
    assert c.get('/api/growth/social/'+s['id']+'/report').status_code==404
    c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'other-social-password','name':'Other tenant'}).raise_for_status()
    assert c.post('/api/growth/social/'+s['id']+'/sync').status_code==404

@pytest.mark.parametrize('fallback',[False,True])
def test_native_instagram_http_boundary(monkeypatch,fallback):
    original=httpx.AsyncClient;requests=[];token='synthetic-boundary-token'
    def handler(request):
        requests.append(request)
        assert request.headers['authorization']=='Bearer '+token
        assert request.url.host=='graph.facebook.com' and token not in str(request.url)
        if request.url.path.endswith('/12345'):return httpx.Response(200,json={'id':'12345','username':'Synthetic','followers_count':50})
        fields=request.url.params.get('fields','')
        if fallback and 'comments.limit' in fields:return httpx.Response(403,json={'error':'No comment scope'})
        return httpx.Response(200,json={'data':[{'id':'post1','timestamp':'2026-01-01T00:00:00Z','permalink':'https://www.instagram.com/p/test/','like_count':9,'comments_count':3,'comments':{'data':[{'id':'c','text':'@name I want blue','timestamp':'2026-01-02T00:00:00Z'}]}}]})
    monkeypatch.setattr(social_mcp.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    result=asyncio.run(social_mcp.observe('instagram','12345',token))
    assert result['posts'][0]['likes']==9 and metrics(result)['interactions']==12
    assert result['comment_sample'][0]['text'].startswith('[handle redacted]')
    assert len(requests)==(3 if fallback else 2)
    if fallback:assert 'request was rejected' in result['coverage']

@pytest.mark.parametrize('case',['wrong_account','rate_limit','malformed','oversize','reflection'])
def test_native_provider_failures(monkeypatch,case):
    original=httpx.AsyncClient;token='synthetic-private-token'
    def handler(request):
        if case=='rate_limit':return httpx.Response(429,json={'error':'quota'})
        if case=='malformed':return httpx.Response(200,content=b'not JSON')
        if case=='oversize':return httpx.Response(200,content=b'x'*200001)
        if request.url.path.endswith('/12345'):return httpx.Response(200,json={'id':'wrong' if case=='wrong_account' else '12345','username':token if case=='reflection' else 'Synthetic'})
        return httpx.Response(200,json={'data':[]})
    monkeypatch.setattr(social_mcp.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises((ValueError,httpx.HTTPStatusError)):asyncio.run(social_mcp.observe('instagram','12345',token))


def test_scheduler_collects_without_model_or_business_write(c,monkeypatch):
    conv,s,cred=source(c)
    calls=[]
    async def boundary(*args):calls.append(1);return observation()
    monkeypatch.setattr(module.MCP_REGISTRY,'call',boundary)
    response=c.post('/api/growth/social/'+s['id']+'/monitor',json={'enabled':True,'interval_minutes':1440});response.raise_for_status();schedule=response.json()
    with module.conn() as db:db.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(json.dumps({'next_run_at':'2020-01-01T00:00:00+00:00'}),schedule['id']))
    c.portal.call(module.schedule_tick)
    row=c.get('/api/schedules').json()[0]
    assert row['last_run'] and not row['last_error']
    c.get('/api/executions/'+row['last_run']+'/live')
    assert c.get('/api/executions/'+row['last_run']).json()['state']=='COMPLETED'
    assert len(calls)==1 and len(c.get('/api/growth/social',params={'conversation_id':conv['id']}).json()[0]['history'])==1
    assert c.get('/api/tasks').json()==[]
    c.post('/api/growth/social/'+s['id']+'/monitor',json={'enabled':False}).raise_for_status()
    c.portal.call(module.schedule_tick);assert len(calls)==1

@pytest.mark.parametrize('role',['viewer','editor'])
def test_social_project_and_write_boundaries(c,role):
    conv,s,cred=source(c)
    owner_cookie=c.cookies.get('evolvyn_session');org=c.get('/api/auth/me').json()['organization_id']
    business=c.post('/api/businesses',json={'name':'Synthetic store','kind':'ecommerce','goal':'Protect social evidence'});business.raise_for_status()
    project=c.post('/api/projects',json={'name':'Restricted social','business_id':business.json()['id'],'goal':'Protect customer data','data_policy':'allow_selected_provider'});project.raise_for_status();project=project.json()
    with module.conn() as db:db.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(json.dumps({'project_id':project['id']}),conv['id']))
    email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':email,'password':'member-social-password','name':'Member'}).raise_for_status();member_cookie=c.cookies.get('evolvyn_session')
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/');c.headers['X-Organization-Id']=org
    c.post('/api/organizations/members',json={'email':email,'role':role}).raise_for_status()
    c.cookies.set('evolvyn_session',member_cookie,domain='testserver.local',path='/')
    assert c.get('/api/growth/social',params={'conversation_id':conv['id']}).status_code==200
    if role=='viewer':
        assert c.post('/api/growth/social/'+s['id']+'/sync').status_code==403
        assert c.post('/api/growth/social/'+s['id']+'/monitor',json={}).status_code==403
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/')
    c.put('/api/projects/'+project['id']+'/access',json={'access':'restricted','members':[]}).raise_for_status()
    c.cookies.set('evolvyn_session',member_cookie,domain='testserver.local',path='/')
    assert c.get('/api/growth/social',params={'conversation_id':conv['id']}).status_code==404
    assert c.post('/api/growth/social/'+s['id']+'/sync').status_code in (403,404)


def test_review_uses_default_gemini_for_all_roles_and_internal_evidence(c,monkeypatch):
    from pathlib import Path
    from backend import gemini_gateway
    conv,s,cred=source(c)
    async def boundary(*args):return observation()
    monkeypatch.setattr(module.MCP_REGISTRY,'call',boundary)
    assert collect(c,s)['state']=='COMPLETED'
    c.post('/api/conversations/'+conv['id']+'/files',files={'file':('sales.csv',Path('sample-data/ecommerce-sales.csv').read_bytes())}).raise_for_status()
    secret='synthetic-gemini-'+uuid4().hex
    key=c.post('/api/vault/credentials',json={'name':'Synthetic Gemini','provider':'gemini','value':secret}).json()
    c.put('/api/vault/workspace-default',json={'provider':'gemini','credential_id':key['id']}).raise_for_status()
    calls=[]
    async def completion(messages,model,key,*args,**kw):
        assert key==secret
        content=json.dumps(messages);assert secret not in content and 'social:' in content and '45.10' in content
        calls.append(content)
        return {'choices':[{'message':{'content':'Synthetic controlled model output; validate experiment against cited evidence.'}}],'usage':{'completion_tokens':15}}
    monkeypatch.setattr(gemini_gateway,'completion',completion)
    run=c.post('/api/growth/social/'+s['id']+'/review',json={'mode':'default'});run.raise_for_status()
    c.get('/api/executions/'+run.json()['id']+'/live')
    result=c.get('/api/executions/'+run.json()['id']).json()
    assert result['state']=='COMPLETED',result
    assert len(calls)==3 and 'Prior agent hypothesis' in calls[-1]
    assert secret not in json.dumps(result)

@pytest.mark.parametrize('provider',['instagram_login','youtube'])
def test_other_native_read_adapters_fixed_hosts_and_missing_counters(monkeypatch,provider):
    original=httpx.AsyncClient;hosts=[]
    def handler(request):
        hosts.append(request.url.host)
        if provider=='instagram_login':
            if request.url.path.endswith('/12345'):return httpx.Response(200,json={'id':'12345','username':'Synthetic'})
            return httpx.Response(200,json={'data':[]})
        if request.url.path.endswith('/channels'):return httpx.Response(200,json={'items':[{'id':'12345','snippet':{'title':'Synthetic'},'statistics':{'hiddenSubscriberCount':True},'contentDetails':{'relatedPlaylists':{'uploads':'playlist'}}}]})
        if request.url.path.endswith('/playlistItems'):return httpx.Response(200,json={'items':[{'contentDetails':{'videoId':'video1'}}]})
        return httpx.Response(200,json={'items':[{'id':'video1','snippet':{'title':'Synthetic','publishedAt':'2026-01-01T00:00:00Z'},'statistics':{'viewCount':'25'}}]})
    monkeypatch.setattr(social_mcp.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    row=asyncio.run(social_mcp.observe(provider,'12345','synthetic-token'))
    assert set(hosts)==({'graph.instagram.com'} if provider=='instagram_login' else {'www.googleapis.com'})
    assert metrics(row)['likes'] is None and row['followers'] is None

@pytest.mark.parametrize('change',['disconnect','cancel','rotation'])
def test_late_observation_cannot_commit_after_revocation_or_cancel(c,monkeypatch,change):
    conv,s,cred=source(c)
    async def boundary(*args):
        if change=='disconnect':c.delete('/api/growth/social/'+s['id']).raise_for_status()
        elif change=='cancel':
            row=c.get('/api/growth/social',params={'conversation_id':conv['id']}).json()[0]
            c.post('/api/executions/'+row['last_execution']['id']+'/cancel').raise_for_status()
        else:c.put('/api/vault/credentials/'+cred['id'],json={'name':'Rotated synthetic','provider':'mcp','value':'synthetic-replacement-'+uuid4().hex}).raise_for_status()
        return observation()
    monkeypatch.setattr(module.MCP_REGISTRY,'call',boundary)
    result=collect(c,s);assert result['state'] in ('FAILED','CANCELLED'),result
    row=c.get('/api/growth/social',params={'conversation_id':conv['id']}).json()[0]
    assert row['latest'] is None and not row['last_success_at']
