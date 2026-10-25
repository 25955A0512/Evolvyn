"""Instagram OAuth boundary tests; no live Meta credentials or acceptance claim."""
import asyncio,json
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from urllib.parse import urlparse,parse_qs
from uuid import uuid4
import httpx,pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend import app as module
from backend import instagram_oauth
from backend.oauth import digest

@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv('EVOLVYN_VAULT_MASTER_KEY',Fernet.generate_key().decode())
    monkeypatch.setenv('OAUTH_INSTAGRAM_CLIENT_ID','synthetic-instagram-app')
    monkeypatch.setenv('OAUTH_INSTAGRAM_CLIENT_SECRET','synthetic-instagram-app-secret')
    with TestClient(module.app,client=(uuid4().hex,43000)) as c:
        c.headers['X-Requested-With']='Evolvyn'
        r=c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'synthetic-instagram-password','name':'Instagram test'});r.raise_for_status();c.org=r.json()['organization_id']
        c.conv=c.post('/api/conversations',json={'title':'Instagram evidence'}).json()['id'];yield c

def begin(c,comments=False):
    r=c.post('/api/integrations/instagram/authorize',json={'conversation_id':c.conv,'read_comments':comments});r.raise_for_status()
    query=parse_qs(urlparse(r.json()['authorize_url']).query)
    assert query['redirect_uri']==['http://localhost:3000/api/integrations/instagram/callback']
    assert query['scope']==['instagram_business_basic'+(',instagram_business_manage_comments' if comments else '')]
    return query['state'][0]

def mock_provider(monkeypatch,case='ok',after_profile=None):
    token='synthetic-instagram-access-'+uuid4().hex;seen=[]
    async def handler(request):
        seen.append(request)
        if request.url.host=='api.instagram.com':
            assert request.method=='POST' and request.url.path=='/oauth/access_token'
            fields=parse_qs(request.content.decode());assert fields['client_secret']==['synthetic-instagram-app-secret'] and fields['grant_type']==['authorization_code']
            if case=='failure':return httpx.Response(400,json={'error':'Sensitive upstream response must not be reflected'})
            return httpx.Response(200,json={'access_token':token,'user_id':12345,'expires_in':3600})
        if request.url.path=='/access_token':
            assert request.url.host=='graph.instagram.com' and request.url.params['grant_type']=='ig_exchange_token' and request.url.params['access_token']==token
            return httpx.Response(200,json={'access_token':token,'expires_in':5184000})
        assert token not in str(request.url)
        assert request.url.host=='graph.instagram.com' and request.headers['Authorization']=='Bearer '+token
        assert request.url.params['fields']=='id,user_id,username'
        if after_profile:after_profile()
        return httpx.Response(200,json={'user_id':'other' if case=='mismatch' else '12345','username':'synthetic_shop'})
    original=httpx.AsyncClient
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    return token,seen

def callback(c,state,**extra):
    return c.get('/api/integrations/instagram/callback',params={'state':state,'code':'synthetic-code',**extra},follow_redirects=False)

def test_oauth_creates_encrypted_scoped_native_source_without_manual_token(c,monkeypatch):
    token,seen=mock_provider(monkeypatch);state=begin(c,True)
    assert c.get('/api/integrations/instagram').json()['configured'] is True
    with module.conn() as db:body=db.execute("SELECT body FROM records WHERE kind='connector_oauth_state'").fetchone()['body']
    assert token not in json.dumps(body) and 'synthetic-instagram-app-secret' not in json.dumps(body)
    r=callback(c,state);assert r.status_code==303,r.text
    assert r.headers['location']=='/growth?conversation='+c.conv+'&social=connected'
    assert r.headers['cache-control']=='no-store' and token not in r.text and token not in r.headers.get('location','')
    source=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    assert source['oauth_provider']=='instagram' and source['account_id']=='12345' and source['last_success_at'] is None
    assert source['oauth_expires_at'] and not source['connection_issue']
    assert c.get('/api/vault').json()['credentials'][0]['provider']=='mcp'
    with module.conn() as db:
        credential=db.execute("SELECT body FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['body']
    assert token not in json.dumps(credential) and credential['ciphertext']
    assert len(seen)==3 and callback(c,state).status_code==400
    assert c.get('/api/tasks').json()==[]
    # Reauthorization updates the same source, not a second dashboard or monitor.
    other=begin(c);r=callback(c,other);assert r.status_code==303,r.text
    rows=c.get('/api/growth/social',params={'conversation_id':c.conv}).json();assert len(rows)==1 and rows[0]['id']==source['id']
    assert len(c.get('/api/vault').json()['credentials'])==1

@pytest.mark.parametrize('case',['denied','browser','expired','config','logout','membership','policy','mismatch','failure'])
def test_oauth_rejections_never_create_active_source_or_expose_secrets(c,monkeypatch,case):
    token,seen=mock_provider(monkeypatch,case);state=begin(c)
    if case=='browser':c.cookies.delete(instagram_oauth.cookie_name())
    if case=='expired':
        with module.conn() as db:db.execute("UPDATE records SET body=body || %s::jsonb WHERE kind='connector_oauth_state'",(json.dumps({'expires':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}),))
    if case=='config':monkeypatch.setenv('OAUTH_INSTAGRAM_CLIENT_SECRET','changed-app-secret')
    if case=='logout':c.post('/api/auth/logout').raise_for_status()
    if case=='membership':
        with module.conn() as db:db.execute('UPDATE memberships SET role=%s WHERE organization_id=%s',('viewer',c.org))
    if case=='policy':
        settings=c.get('/api/governance/policy').json();c.put('/api/governance/policy',json={**settings,'allow_external_processing':False}).raise_for_status()
    r=callback(c,state,error='access_denied' if case=='denied' else '')
    assert r.status_code>=400 and token not in r.text and 'Sensitive upstream' not in r.text
    with module.conn() as db:
        assert db.execute("SELECT count(*) AS n FROM records WHERE owner=%s AND kind='social_source'",(c.org,)).fetchone()['n']==0
        assert db.execute("SELECT count(*) AS n FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['n']==0
    if case not in ('mismatch','failure'):assert not seen

def test_revocation_during_exchange_and_local_only_reject_authorization(c,monkeypatch):
    def revoke():
        with module.conn() as db:db.execute('DELETE FROM account_sessions WHERE organization_id=%s',(c.org,))
    mock_provider(monkeypatch,after_profile=revoke);state=begin(c)
    assert callback(c,state).status_code==403
    with module.conn() as db:assert db.execute("SELECT count(*) AS n FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['n']==0

def test_missing_config_and_cross_tenant_scope(c,monkeypatch):
    monkeypatch.delenv('OAUTH_INSTAGRAM_CLIENT_SECRET')
    status=c.get('/api/integrations/instagram').json();assert not status['configured'] and status['setup']['variables']==['OAUTH_INSTAGRAM_CLIENT_ID','OAUTH_INSTAGRAM_CLIENT_SECRET']
    assert c.post('/api/integrations/instagram/authorize',json={'conversation_id':c.conv}).status_code==503
    assert c.post('/api/integrations/instagram/authorize',json={'conversation_id':str(uuid4())}).status_code==404
    assert c.post('/api/integrations/instagram/authorize',json={'conversation_id':c.conv,'redirect_uri':'https://evil.example'}).status_code==422


def test_expired_oauth_source_stops_collection(c,monkeypatch):
    mock_provider(monkeypatch);state=begin(c);assert callback(c,state).status_code==303
    source=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    with module.conn() as db:db.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(json.dumps({'oauth_expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}),source['id']))
    r=c.post('/api/growth/social/'+source['id']+'/sync');assert r.status_code==409
    assert c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]['connection_issue']


def test_meta_token_exchange_http_logs_never_expose_query_credentials(c,monkeypatch,caplog):
    import logging
    token,seen=mock_provider(monkeypatch)
    caplog.set_level(logging.INFO,logger='httpx')
    state=begin(c);r=callback(c,state);assert r.status_code==303,r.text
    assert token not in caplog.text and 'synthetic-instagram-app-secret' not in caplog.text
    assert 'ig_exchange_token' not in caplog.text


def test_token_renewal_and_disconnect_do_not_resurrect_credentials(c,monkeypatch):
    token,seen=mock_provider(monkeypatch);assert callback(c,begin(c)).status_code==303
    source=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    assert c.post('/api/integrations/instagram/'+source['id']+'/refresh').status_code==409
    old=(datetime.now(timezone.utc)-timedelta(days=54)).isoformat()
    with module.conn() as db:db.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(json.dumps({'oauth_authorized_at':old,'oauth_expires_at':(datetime.now(timezone.utc)+timedelta(days=6)).isoformat(),'oauth_refresh_after':old}),source['id']))
    original=httpx.AsyncClient;refreshed='synthetic-renewed-'+uuid4().hex;requests=[]
    async def handler(request):
        requests.append(request.url.path)
        if request.url.path=='/refresh_access_token':
            assert request.url.params['grant_type']=='ig_refresh_token' and request.url.params['access_token']==token
            return httpx.Response(200,json={'access_token':refreshed,'expires_in':5184000})
        assert request.headers['authorization']=='Bearer '+refreshed
        return httpx.Response(200,json={'user_id':'12345'})
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    c.portal.call(module.INSTAGRAM_OAUTH.refresh_tick)
    row=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    assert not row['connection_issue'] and not row['oauth_refresh_error'] and len(requests)==2
    assert datetime.fromisoformat(row['oauth_expires_at'])>datetime.now(timezone.utc)+timedelta(days=59)
    credential=c.get('/api/vault').json()['credentials'][0];assert credential['version']==2
    c.portal.call(module.INSTAGRAM_OAUTH.refresh_tick);assert len(requests)==2 # cooldown, not a tight loop
    c.delete('/api/growth/social/'+source['id']).raise_for_status()
    assert not c.get('/api/vault').json()['credentials'][0]['enabled']
    assert c.post('/api/integrations/instagram/'+source['id']+'/refresh').status_code==409

@pytest.mark.parametrize('case',['revoked','account','quota'])
def test_failed_renewal_preserves_revocation_and_reports_no_success(c,monkeypatch,case):
    mock_provider(monkeypatch);assert callback(c,begin(c)).status_code==303
    source=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    credential=c.get('/api/vault').json()['credentials'][0];old=(datetime.now(timezone.utc)-timedelta(days=54)).isoformat()
    with module.conn() as db:db.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(json.dumps({'oauth_authorized_at':old,'oauth_expires_at':(datetime.now(timezone.utc)+timedelta(days=6)).isoformat(),'oauth_refresh_after':old}),source['id']))
    original=httpx.AsyncClient
    async def handler(request):
        if request.url.path=='/refresh_access_token':
            if case=='quota':return httpx.Response(429,json={'error':'sensitive quota body'})
            return httpx.Response(200,json={'access_token':'synthetic-renewal-token','expires_in':5184000})
        if case=='revoked':(await asyncio.to_thread(c.delete,'/api/vault/credentials/'+credential['id'])).raise_for_status()
        return httpx.Response(200,json={'user_id':'wrong' if case=='account' else '12345'})
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    c.portal.call(module.INSTAGRAM_OAUTH.refresh_tick)
    row=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    assert row['oauth_refresh_error'] and row['oauth_authorized_at']==old
    assert datetime.fromisoformat(row['oauth_refresh_after'])>datetime.now(timezone.utc)+timedelta(hours=5)
    key=c.get('/api/vault').json()['credentials'][0];assert key['version']==1
    if case=='revoked':assert not key['enabled']
    assert 'sensitive quota body' not in json.dumps(row)


def test_local_only_project_cannot_begin_social_oauth(c):
    business=c.post('/api/businesses',json={'name':'Private shop','kind':'ecommerce','goal':'Private analytics'}).json()
    project=c.post('/api/projects',json={'name':'Local only','business_id':business['id'],'goal':'Keep data local'}).json()
    with module.conn() as db:db.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(json.dumps({'project_id':project['id']}),c.conv))
    assert c.post('/api/integrations/instagram/authorize',json={'conversation_id':c.conv}).status_code==403


def test_data_enveloped_token_exchange_connects_one_verified_account(c,monkeypatch):
    token='synthetic-envelope-token';original=httpx.AsyncClient
    async def handler(request):
        if request.url.host=='api.instagram.com':return httpx.Response(200,json={'data':[{'access_token':token,'user_id':12345,'permissions':['instagram_business_basic']}]})
        if request.url.path=='/access_token':return httpx.Response(200,json={'access_token':token,'expires_in':5184000})
        return httpx.Response(200,json={'user_id':'12345','username':'synthetic_shop'})
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    r=callback(c,begin(c));assert r.status_code==303,r.text
    source=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    assert source['account_id']=='12345' and not source['last_success_at']

@pytest.mark.parametrize('payload',[{},[],{'data':[]},{'data':[{},{}]},{'data':'wrong'},{'access_token':'synthetic','data':[{'user_id':12345}]},{'data':[{'access_token':'synthetic-token','user_id':'bad'}]}])
def test_ambiguous_or_invalid_token_envelopes_never_connect(c,monkeypatch,payload):
    original=httpx.AsyncClient
    async def handler(request):return httpx.Response(200,json=payload)
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    r=callback(c,begin(c));assert r.status_code==502
    assert 'authorization_code_' in r.json()['detail']
    assert c.get('/api/growth/social',params={'conversation_id':c.conv}).json()==[]

@pytest.mark.parametrize('stage',['authorization_code_exchange','long_lived_exchange','account_verification'])
def test_safe_stage_diagnostics_without_upstream_secret_reflection(c,monkeypatch,caplog,stage):
    original=httpx.AsyncClient;secret='synthetic-sensitive-upstream-body'
    async def handler(request):
        target='authorization_code_exchange' if request.url.host=='api.instagram.com' else 'long_lived_exchange' if request.url.path=='/access_token' else 'account_verification'
        if target==stage:return httpx.Response(400,json={'error':{'message':secret,'code':190,'error_subcode':460,'fbtrace_id':secret}})
        if target=='authorization_code_exchange':return httpx.Response(200,json={'data':[{'access_token':'synthetic-short-token','user_id':12345}]})
        if target=='long_lived_exchange':return httpx.Response(200,json={'access_token':'synthetic-long-token','expires_in':5184000})
        raise AssertionError('Unexpected provider call')
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    r=callback(c,begin(c));assert r.status_code==502
    detail=r.json()['detail'];assert stage in detail and 'Meta code 190' in detail and 'subcode 460' in detail
    assert secret not in r.text and secret not in caplog.text and 'synthetic-long-token' not in r.text
    assert c.get('/api/growth/social',params={'conversation_id':c.conv}).json()==[]

@pytest.mark.parametrize('profile,expected',[({'id':'12345','user_id':'67890','username':'synthetic_shop'},'67890'),({'id':'12345','username':'synthetic_shop'},'12345'),({'id':67890,'user_id':12345,'username':'synthetic_shop'},'12345')])
def test_oauth_verifies_named_ids_and_binds_canonical_account(c,monkeypatch,profile,expected):
    original=httpx.AsyncClient
    async def handler(request):
        if request.url.host=='api.instagram.com':return httpx.Response(200,json={'data':[{'access_token':'synthetic-short','user_id':12345}]})
        if request.url.path=='/access_token':return httpx.Response(200,json={'access_token':'synthetic-long','expires_in':5184000})
        assert request.url.params['fields']=='id,user_id,username'
        return httpx.Response(200,json=profile)
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    r=callback(c,begin(c));assert r.status_code==303,r.text
    row=c.get('/api/growth/social',params={'conversation_id':c.conv}).json()[0]
    assert row['account_id']==expected and row['oauth_token_subject']=='12345'
    assert row['oauth_identity']=={k:str(v) for k,v in profile.items() if k in ('id','user_id')}

@pytest.mark.parametrize('profile,stage',[({'id':'99999','user_id':'88888','username':'synthetic_shop'},'account_identity'),({'id':'not-numeric','user_id':'12345','username':'synthetic_shop'},'account_identifiers'),({'username':'synthetic_shop'},'account_identifiers'),({'id':'12345','username':'bad/name'},'account_profile'),({'id':True,'username':'synthetic_shop'},'account_identifiers')])
def test_identity_mapping_rejects_unrelated_and_malformed_accounts(c,monkeypatch,profile,stage):
    original=httpx.AsyncClient
    async def handler(request):
        if request.url.host=='api.instagram.com':return httpx.Response(200,json={'access_token':'synthetic-short','user_id':12345})
        if request.url.path=='/access_token':return httpx.Response(200,json={'access_token':'synthetic-long','expires_in':5184000})
        return httpx.Response(200,json=profile)
    monkeypatch.setattr(instagram_oauth,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)))
    r=callback(c,begin(c));assert r.status_code==502 and stage in r.json()['detail']
    assert c.get('/api/growth/social',params={'conversation_id':c.conv}).json()==[]
