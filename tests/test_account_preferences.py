from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend import app as module

@pytest.fixture
def clients():
    with TestClient(module.app,client=(uuid4().hex,50001)) as a,TestClient(module.app,client=(uuid4().hex,50002)) as b:
        for c in (a,b):
            c.headers['X-Requested-With']='Evolvyn'
            c.email=uuid4().hex+'@example.test';c.password='preference-test-password'
            c.identity=c.post('/api/auth/register',json={'email':c.email,'password':c.password,'name':'Preference acceptance'}).json()
        yield a,b

def test_preferences_are_personal_and_persist_across_sessions(clients):
    a,b=clients
    defaults=a.get('/api/account/preferences').json()
    assert defaults=={'theme':'system','text_size':'normal','sound':False,'browser_notifications':False}
    chosen={**defaults,'theme':'dark','text_size':'large','sound':True}
    assert a.put('/api/account/preferences',json=chosen).json()==chosen
    assert b.get('/api/account/preferences').json()==defaults
    a.post('/api/auth/logout').raise_for_status()
    a.post('/api/auth/login',json={'email':a.email,'password':a.password}).raise_for_status()
    assert a.get('/api/account/preferences').json()==chosen

def test_preferences_validate_schema_and_cross_origin_writes(clients):
    a,_=clients
    for body in ({'theme':'blue'},{'theme':'dark','account_id':'someone-else'},{'sound':'true'},{'secret':'must-not-persist'}):
        assert a.put('/api/account/preferences',json=body).status_code==422
    assert a.put('/api/account/preferences',json={'theme':'dark'},headers={'Origin':'https://attacker.example'}).status_code==403
    assert a.get('/api/account/preferences').json()['theme']=='system'
    a.headers['Authorization']='Bearer '+module.TOKEN
    assert a.get('/api/account/preferences').status_code==403

def test_viewer_can_change_own_appearance_without_business_write_access(clients):
    admin,viewer=clients
    admin.post('/api/organizations/members',json={'email':viewer.email,'role':'viewer'}).raise_for_status()
    viewer.headers['X-Organization-Id']=admin.identity['organization_id']
    response=viewer.put('/api/account/preferences',json={'theme':'dark'})
    assert response.status_code==200,response.text
    assert viewer.post('/api/conversations',json={'title':'Must not write business data'}).status_code==403
    assert admin.get('/api/account/preferences').json()['theme']=='system'
    viewer.headers.pop('X-Organization-Id')
    assert viewer.get('/api/account/preferences').json()['theme']=='dark'

def test_graph_provider_selection_never_silently_substitutes_evidence(clients,monkeypatch):
    a,_=clients;monkeypatch.delenv('MODEL_API_KEY',raising=False)
    conv=a.post('/api/conversations',json={'title':'Strict capability'}).json()
    graph=a.post('/api/harness/graphs',json={'name':'Strict provider','goal':'Use the real selected provider','entry':'agent','nodes':[{'id':'agent','type':'agent','mode':'provider','prompt':'Explain authorized evidence'}]}).json()
    response=a.post('/api/harness/graphs/'+graph['id']+'/run',json={'conversation_id':conv['id']})
    assert response.status_code==202,response.text
    id=response.json()['id'];a.get('/api/executions/'+id+'/live')
    execution=a.get('/api/executions/'+id).json()
    assert execution['state']=='FAILED' and not execution['output']
    assert 'Deterministic evidence mode' not in str(execution)

def test_capability_graph_honors_the_registered_role_token_limit(clients,monkeypatch):
    a,_=clients;calls=[]
    async def renderer(report,question,history,mode):
        calls.append(report['_output_limit']);yield 'A bounded model finding'
    monkeypatch.setitem(module.GRAPH_HARNESS.s,'response_chunks',renderer)
    a.post('/api/agents',json={'agent':'limited_role','name':'Limited role','goal':'Review authorized evidence only','output_tokens':64}).raise_for_status()
    conv=a.post('/api/conversations',json={'title':'Role budget'}).json()
    graph=a.post('/api/harness/graphs',json={'name':'Role budget','goal':'Honor the registered budget','entry':'agent','nodes':[{'id':'agent','type':'agent','agent_id':'limited_role','mode':'local'}]}).json()
    run=a.post('/api/harness/graphs/'+graph['id']+'/run',json={'conversation_id':conv['id']}).json()
    a.get('/api/executions/'+run['id']+'/live')
    result=a.get('/api/executions/'+run['id']).json()
    assert result['state']=='COMPLETED' and calls==[64]
    assert result['graph_checkpoint']['tokens_reserved']==64
