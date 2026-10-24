from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend import app as module

@pytest.fixture
def client():
    with TestClient(module.app) as c:
        c.headers['X-Requested-With']='Evolvyn'
        yield c

def register(c):
    email=uuid4().hex+'@example.test'
    response=c.post('/api/auth/register',json={'email':email,'password':'policy-acceptance-password','name':'Policy workspace'})
    assert response.status_code==201,response.text
    return email,response.json(),c.cookies.get('evolvyn_session')

def use(c,cookie,org):
    c.cookies.set('evolvyn_session',cookie,domain='testserver.local',path='/')
    c.headers['X-Organization-Id']=org

def test_restricted_project_hides_linked_resources_from_nonmembers(client):
    _,owner,owner_cookie=register(client)
    business=client.post('/api/businesses',json={'name':'Sensitive business'}).json()
    project=client.post('/api/projects',json={'business_id':business['id'],'name':'Restricted work','goal':'Protect evidence'}).json()
    conversation=client.post('/api/conversations',json={'title':'Secret project conversation','business_id':business['id'],'project_id':project['id']}).json()
    schedule=client.post('/api/schedules',json={'conversation_id':conversation['id'],'query':'Private scheduled analysis','interval_minutes':60}).json()
    plan=client.post('/api/harness/plan',json={'goal':'Private project investigation','conversation_id':conversation['id']}).json()
    graph=client.post('/api/harness/graphs',json=plan['definition']).json()
    member_email,member,member_cookie=register(client)
    use(client,owner_cookie,owner['organization_id'])
    client.post('/api/organizations/members',json={'email':member_email,'role':'editor'}).raise_for_status()
    client.put('/api/projects/'+project['id']+'/access',json={'access':'restricted','members':[]}).raise_for_status()
    use(client,member_cookie,owner['organization_id'])
    assert client.get('/api/projects').json()==[]
    assert client.get('/api/conversations/'+conversation['id']).status_code==404
    assert client.get('/api/conversations').json()==[]
    assert client.get('/api/schedules').json()==[]
    assert client.get('/api/harness/graphs').json()==[]
    assert client.post('/api/schedules/'+schedule['id']+'/run').status_code==404
    assert client.post('/api/harness/graphs/'+graph['id']+'/run',json={'conversation_id':conversation['id']}).status_code==404
    assert client.post('/api/tools/analyze_business/invoke',json={'arguments':{'conversation_id':conversation['id'],'query':'read secret data'}}).status_code==404
    assert client.put('/api/projects/'+project['id']+'/access',json={'access':'organization','members':[]}).status_code==403
    use(client,owner_cookie,owner['organization_id'])
    client.put('/api/projects/'+project['id']+'/access',json={'access':'restricted','members':[member['account_id']]}).raise_for_status()
    use(client,member_cookie,owner['organization_id'])
    assert client.get('/api/conversations/'+conversation['id']).status_code==200
    assert len(client.get('/api/projects').json())==1
    assert client.put('/api/governance/policy',json=client.get('/api/governance/policy').json()).status_code==403
