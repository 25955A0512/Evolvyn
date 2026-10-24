from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from backend import app as module

@pytest.fixture
def client():
    with TestClient(module.app) as c:
        c.headers['X-Requested-With']='Evolvyn'
        yield c

def register(c):
    email=uuid4().hex+'@example.test'
    response=c.post('/api/auth/register',json={'email':email,'password':'test-private-password-123','name':'Test organization'})
    assert response.status_code==201,response.text
    return email,response.json()

def test_registration_cookie_and_private_persistence(client):
    email,identity=register(client)
    me=client.get('/api/auth/me').json()
    assert me['account']['email']==email and me['role']=='owner'
    assert 'password' not in str(me)
    response=client.post('/api/businesses',json={'name':'Private business'})
    assert response.status_code==200
    assert client.get('/api/businesses').json()[0]['id']==response.json()['id']
    assert 'HttpOnly' in client.cookies.jar._cookies['testserver.local']['/']['evolvyn_session']._rest
    assert client.get('/api/audit').json()

def test_logout_revokes_session_and_login_works(client):
    email,identity=register(client)
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/businesses').status_code==401
    assert client.post('/api/auth/login',json={'email':email,'password':'wrong'}).status_code==401
    response=client.post('/api/auth/login',json={'email':email,'password':'test-private-password-123'})
    assert response.status_code==200
    assert client.get('/api/auth/me').json()['account']['email']==email

def test_cookie_mutations_require_application_header(client):
    register(client)
    client.headers.pop('X-Requested-With')
    assert client.post('/api/businesses',json={'name':'CSRF'}).status_code==403
    client.headers['X-Requested-With']='Evolvyn'
    assert client.post('/api/businesses',headers={'Origin':'https://attacker.example'},json={'name':'Cross origin'}).status_code==403

def test_cross_organization_access_and_viewer_permissions(client):
    owner_email,owner=register(client)
    private=client.post('/api/businesses',json={'name':'Owner-only business'}).json()
    owner_cookie=client.cookies.get('evolvyn_session')
    member_email,member=register(client)
    member_cookie=client.cookies.get('evolvyn_session')
    assert client.get('/api/businesses').json()==[]
    assert client.post('/api/projects',json={'business_id':private['id'],'name':'Steal','goal':'Steal data'}).status_code==404
    client.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/')
    assert client.post('/api/organizations/members',json={'email':member_email,'role':'viewer'}).status_code==200
    client.cookies.set('evolvyn_session',member_cookie,domain='testserver.local',path='/')
    client.headers['X-Organization-Id']=owner['organization_id']
    assert client.get('/api/businesses').json()[0]['id']==private['id']
    assert client.post('/api/businesses',json={'name':'Unauthorized write'}).status_code==403
    assert client.get('/api/audit').status_code==403
    client.headers['X-Organization-Id']='unknown-org'
    assert client.get('/api/businesses').status_code==403

def test_editor_cannot_approve_actions(client):
    _,owner=register(client);owner_cookie=client.cookies.get('evolvyn_session')
    member_email,_=register(client);member_cookie=client.cookies.get('evolvyn_session')
    client.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/')
    client.post('/api/organizations/members',json={'email':member_email,'role':'editor'})
    client.cookies.set('evolvyn_session',member_cookie,domain='testserver.local',path='/')
    client.headers['X-Organization-Id']=owner['organization_id']
    assert client.post('/api/executions/anything/decision',json={'approve':True,'plan':'Bypass policy'}).status_code==403

def test_invalid_password_is_never_reflected(client):
    response=client.post('/api/auth/register',json={'email':'test@example.test','password':'secret','name':'Organization'})
    assert response.status_code==422 and 'secret' not in response.text
