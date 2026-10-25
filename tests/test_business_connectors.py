"""Actual DB/vault/MCP lifecycle, controlled external HTTP; never live credentials."""
import asyncio,hashlib,hmac,json,time
from types import SimpleNamespace
from urllib.parse import urlencode,urlparse,parse_qs
from uuid import uuid4
import httpx,pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend import app as module,business_connectors as bc,business_mcp as bm
from backend.mcp_registry import is_external

@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv('PUBLIC_ORIGIN','http://localhost:3000');monkeypatch.setenv('COOKIE_SECURE','0')
    monkeypatch.setenv('EVOLVYN_VAULT_MASTER_KEY',Fernet.generate_key().decode())
    for p in bc.PROVIDERS:
        monkeypatch.setenv('OAUTH_'+p.upper()+'_CLIENT_ID','synthetic-client-'+p)
        monkeypatch.setenv('OAUTH_'+p.upper()+'_CLIENT_SECRET','synthetic-secret-'+p)
    with TestClient(module.app,client=(uuid4().hex,50000)) as client:
        client.headers['X-Requested-With']='Evolvyn'
        r=client.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'synthetic-connector-password','name':'Connector acceptance'});r.raise_for_status();client.org=r.json()['organization_id'];yield client

def begin(c,p):
    r=c.post('/api/integrations/'+p+'/authorize',json={'shop':'synthetic-store.myshopify.com'} if p=='shopify' else {});r.raise_for_status()
    query=parse_qs(urlparse(r.json()['authorize_url']).query)
    assert query['redirect_uri']==['http://localhost:3000/api/integrations/'+p+'/callback']
    assert 'code_challenge' in query if p=='google_drive' else True
    return query['state'][0]

def callback(c,p,state,**extra):
    params={'code':'synthetic-one-time-code','state':state,**extra}
    if p=='shopify':
        params.update(shop='synthetic-store.myshopify.com',timestamp=str(int(time.time())))
        params['hmac']=hmac.new(b'synthetic-secret-shopify',urlencode(sorted(params.items())).encode(),hashlib.sha256).hexdigest()
    return c.get('/api/integrations/'+p+'/callback',params=params,follow_redirects=False)

def provider(monkeypatch,case=None):
    seen=[];original=httpx.AsyncClient
    async def handle(request):
        seen.append(request.url.host+request.url.path)
        path=request.url.path
        if path in ('/token','/api/oauth.v2.access','/admin/oauth/access_token'):
            p='google_drive' if request.url.host=='oauth2.googleapis.com' else 'slack' if 'slack' in request.url.host else 'shopify'
            body={'access_token':'synthetic-access-'+p,'scope':(' ' if p=='google_drive' else ',').join(bc.PROVIDERS[p]['scopes']),'expires_in':3600}
            if p=='google_drive':body['refresh_token']='synthetic-refresh-drive'
            if p=='slack':body.update(ok=True,team={'id':'TTEST123'})
            if case=='scope':body['scope']=''
            return httpx.Response(200,json=body)
        if path=='/drive/v3/about':return httpx.Response(200,json={'user':{'permissionId':'DRIVE123','displayName':'Synthetic Drive'}})
        if path=='/api/auth.test':return httpx.Response(200,json={'ok':True,'team_id':'TOTHER' if case=='identity' else 'TTEST123','team':'Synthetic Slack','bot_id':'BTEST123'})
        if path.endswith('/graphql.json'):return httpx.Response(200,json={'data':{'shop':{'id':'gid://shopify/Shop/123','name':'Synthetic store','myshopifyDomain':'synthetic-store.myshopify.com'}}})
        raise AssertionError('Unexpected provider endpoint')
    stub=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    monkeypatch.setattr(bc,'httpx',stub);monkeypatch.setattr(bm,'httpx',stub)
    return seen

@pytest.mark.parametrize('p',list(bc.PROVIDERS))
def test_oauth_real_mcp_vault_lifecycle(c,monkeypatch,p):
    seen=provider(monkeypatch);state=begin(c,p);r=callback(c,p,state);assert r.status_code==303,r.text
    status=c.get('/api/integrations/business-connections').json()[p]
    assert status['connection']['state']=='connected'
    assert 'access_token' not in json.dumps(status) and 'synthetic-secret' not in json.dumps(status)
    tools=[r for r in c.get('/api/tool-registry').json() if r['name'] in bc.PROVIDERS[p]['tools']]
    assert len(tools)==2 and all(r['risk']=='read' for r in tools)
    servers=c.get('/api/mcp/servers').json();server=next(r for r in servers if r['profile']==p)
    assert is_external(server) and {t['name'] for t in server['tools']}==set(bc.PROVIDERS[p]['tools'])
    with module.conn() as db:
        credential=db.execute("SELECT body FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['body']
        assert credential['ciphertext'] and 'synthetic-access' not in json.dumps(credential)
    assert callback(c,p,state).status_code==400
    assert c.post('/api/integrations/'+p+'/test').json()['state']=='connected'
    assert c.delete('/api/integrations/'+p).status_code==200
    assert c.get('/api/integrations/business-connections').json()[p]['connection']['state']=='disconnected'
    assert not any(t['name'] in bc.PROVIDERS[p]['tools'] for t in c.get('/api/tool-registry').json())
    with module.conn() as db:assert 'ciphertext' not in db.execute("SELECT body FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['body']
    assert seen

@pytest.mark.parametrize('case',['browser','session','config','scope','denied'])
def test_invalid_authorizations_never_save_grants(c,monkeypatch,case):
    provider(monkeypatch,case);state=begin(c,'google_drive')
    if case=='browser':c.cookies.delete(bc.cookie_name('google_drive'))
    if case=='session':c.post('/api/auth/sessions/revoke-all').raise_for_status()
    if case=='config':monkeypatch.setenv('OAUTH_GOOGLE_DRIVE_CLIENT_SECRET','changed-private-config')
    r=callback(c,'google_drive',state,**({'error':'access_denied'} if case=='denied' else {}))
    assert r.status_code in (400,403,502),r.text
    with module.conn() as db:assert db.execute("SELECT count(*) n FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['n']==0


def test_shopify_host_and_signature_and_slack_identity(c,monkeypatch):
    provider(monkeypatch)
    for host in ['https://test.myshopify.com','test.myshopify.com.evil.example','127.0.0.1','test.myshopify.com/path']:
        assert c.post('/api/integrations/shopify/authorize',json={'shop':host}).status_code==422
    state=begin(c,'shopify')
    assert c.get('/api/integrations/shopify/callback',params={'state':state,'code':'synthetic','shop':'synthetic-store.myshopify.com','hmac':'0'*64,'timestamp':str(int(time.time()))}).status_code==502
    provider(monkeypatch,'identity');assert callback(c,'slack',begin(c,'slack')).status_code==502


def test_refresh_grant_updates_only_same_live_vault_version(c,monkeypatch):
    provider(monkeypatch);assert callback(c,'google_drive',begin(c,'google_drive')).status_code==303
    with module.conn() as db:
        db.execute("UPDATE records SET body=body || '{\"expires_at\":\"2020-01-01T00:00:00+00:00\"}'::jsonb WHERE owner=%s AND kind='integration_connection'",(c.org,))
    assert c.post('/api/integrations/google_drive/test').json()['state']=='connected'
    vault=c.get('/api/vault').json()['credentials'];assert vault[0]['version']==2


def test_missing_config_and_managed_profile_bypass_rejected(c,monkeypatch):
    monkeypatch.delenv('OAUTH_SLACK_CLIENT_SECRET')
    assert not c.get('/api/integrations/business-connections').json()['slack']['configured']
    assert c.post('/api/integrations/slack/authorize',json={}).status_code==503
    assert c.post('/api/mcp/servers',json={'name':'Bypass','profile':'slack'}).status_code==422
    assert c.post('/api/integrations/google_drive/authorize',json={'redirect_uri':'https://evil.example'}).status_code==422
    c.cookies.clear();assert c.get('/api/integrations/business-connections').status_code==401


def test_local_only_blocks_native_provider_tools(c,monkeypatch):
    provider(monkeypatch);assert callback(c,'slack',begin(c,'slack')).status_code==303
    policy=c.get('/api/governance/policy').json()
    c.put('/api/governance/policy',json={**policy,'allow_external_processing':False}).raise_for_status()
    assert c.post('/api/tool-registry/slack_channels/invoke',json={'arguments':{'limit':1}}).status_code==403
    assert c.post('/api/integrations/slack/test').status_code==403
    assert c.delete('/api/integrations/slack').status_code==200

@pytest.mark.anyio
async def test_read_adapters_are_bounded_and_do_not_return_customer_data(monkeypatch):
    original=httpx.AsyncClient;seen=[]
    async def handle(request):
        seen.append(request)
        if request.url.path.endswith('/files'):return httpx.Response(200,json={'files':[{'id':'f1','name':'Synthetic document'}]})
        if request.url.path.endswith('conversations.history'):return httpx.Response(200,json={'ok':True,'messages':[{'ts':'1','text':'Synthetic feedback','user':'not-exported'}]})
        query=json.loads(request.content)['query'];assert 'customer' not in query.lower() and 'email' not in query.lower()
        return httpx.Response(200,json={'data':{'orders':{'nodes':[{'id':'1','totalPriceSet':{'shopMoney':{'amount':'12','currencyCode':'USD'}}}]}}})
    monkeypatch.setattr(bm,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handle),**kw)))
    monkeypatch.setenv('EVOLVYN_BUSINESS_TOKEN','synthetic-tool-token');monkeypatch.setenv('EVOLVYN_BUSINESS_PROVIDER','google_drive')
    assert (await bm.drive_files())['data'][0]['id']=='f1'
    with pytest.raises(ValueError):await bm.drive_files(21)
    monkeypatch.setenv('EVOLVYN_BUSINESS_PROVIDER','slack')
    assert 'user' not in (await bm.slack_history('CTEST123'))['data'][0]
    with pytest.raises(ValueError):await bm.slack_history('DPRIVATE123')
    monkeypatch.setenv('EVOLVYN_BUSINESS_PROVIDER','shopify');monkeypatch.setenv('EVOLVYN_SHOPIFY_SHOP','synthetic-store.myshopify.com')
    assert (await bm.shopify_orders())['data']['orders']['nodes'][0]['id']=='1'
    assert len(seen)==3

@pytest.fixture
def anyio_backend():return 'asyncio'

def test_role_downgrade_revokes_pending_authorization(c,monkeypatch):
    provider(monkeypatch);state=begin(c,'slack')
    with module.conn() as db:db.execute("UPDATE memberships SET role='viewer' WHERE organization_id=%s",(c.org,))
    assert callback(c,'slack',state).status_code==403
    assert c.post('/api/integrations/slack/authorize',json={}).status_code==403
    with module.conn() as db:assert db.execute("SELECT count(*) n FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['n']==0


def test_connections_are_isolated_between_organizations(c,monkeypatch):
    provider(monkeypatch);assert callback(c,'slack',begin(c,'slack')).status_code==303
    old=c.get('/api/mcp/servers').json()[0]['id']
    r=c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'synthetic-other-org-password','name':'Other organization'});r.raise_for_status()
    assert c.get('/api/integrations/business-connections').json()['slack']['connection'] is None
    assert c.post('/api/mcp/servers/'+old+'/probe').status_code==404
    assert c.post('/api/integrations/slack/test').status_code==409
    assert c.delete('/api/integrations/slack').status_code==404


def test_revocation_during_drive_refresh_cannot_restore_credential(c,monkeypatch):
    provider(monkeypatch);assert callback(c,'google_drive',begin(c,'google_drive')).status_code==303
    with module.conn() as db:db.execute("UPDATE records SET body=body || '{\"expires_at\":\"2020-01-01T00:00:00+00:00\"}'::jsonb WHERE owner=%s AND kind='integration_connection'",(c.org,))
    original=httpx.AsyncClient
    async def revoke(request):
        with module.conn() as db:db.execute("UPDATE records SET body=(body-'ciphertext') || '{\"enabled\":false}'::jsonb WHERE owner=%s AND kind='vault_secret'",(c.org,))
        return httpx.Response(200,json={'access_token':'synthetic-new-access','expires_in':3600})
    monkeypatch.setattr(bc,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(revoke),**kw)))
    assert c.post('/api/integrations/google_drive/test').status_code==409
    with module.conn() as db:
        secret=db.execute("SELECT body FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['body']
        assert not secret['enabled'] and 'ciphertext' not in secret

def test_existing_grant_can_renew_for_authorized_editor_without_vault_access(c,monkeypatch):
    from backend.policy import ACTOR,Principal
    provider(monkeypatch);assert callback(c,'google_drive',begin(c,'google_drive')).status_code==303
    reader=c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'synthetic-reader-password','name':'Reader'}).json()['account_id']
    with module.conn() as db:
        db.execute("INSERT INTO memberships(account_id,organization_id,role) VALUES(%s,%s,'editor')",(reader,c.org))
        db.execute("UPDATE records SET body=body || '{\"expires_at\":\"2020-01-01T00:00:00+00:00\"}'::jsonb WHERE owner=%s AND kind='integration_connection'",(c.org,))
        server_id=db.execute("SELECT id FROM records WHERE owner=%s AND kind='mcp_server'",(c.org,)).fetchone()['id']
    actor=ACTOR.set(Principal(c.org,reader,'editor'))
    try:
        with pytest.raises(Exception) as error:module.POLICY.require(c.org,'manage_vault')
        assert error.value.status_code==403
        server=module.MCP_REGISTRY.server(c.org,server_id)
        assert asyncio.run(module.BUSINESS_CONNECTORS.access_token(c.org,server)).startswith('synthetic-access-')
        assert ACTOR.get().account==reader
        with pytest.raises(Exception) as error:module.POLICY.require(c.org,'manage_vault')
        assert error.value.status_code==403
    finally:ACTOR.reset(actor)

def test_drive_reuses_complete_google_web_client_but_keeps_separate_consent(c,monkeypatch):
    for suffix in ('_CLIENT_ID','_CLIENT_SECRET'):monkeypatch.delenv('OAUTH_GOOGLE_DRIVE'+suffix)
    monkeypatch.setenv('OAUTH_GOOGLE_CLIENT_ID','synthetic-shared-google-client')
    monkeypatch.setenv('OAUTH_GOOGLE_CLIENT_SECRET','synthetic-shared-google-secret')
    status=c.get('/api/integrations/business-connections').json()['google_drive']
    assert status['configured'] and status['setup']['variables']==['OAUTH_GOOGLE_CLIENT_ID','OAUTH_GOOGLE_CLIENT_SECRET']
    r=c.post('/api/integrations/google_drive/authorize',json={});r.raise_for_status()
    query=parse_qs(urlparse(r.json()['authorize_url']).query)
    assert query['client_id']==['synthetic-shared-google-client']
    assert query['redirect_uri']==['http://localhost:3000/api/integrations/google_drive/callback']
    assert query['scope']==['https://www.googleapis.com/auth/drive.readonly'] and query['prompt']==['consent']
    monkeypatch.setenv('OAUTH_GOOGLE_DRIVE_CLIENT_ID','synthetic-dedicated-but-incomplete')
    assert not c.get('/api/integrations/business-connections').json()['google_drive']['configured']
    assert c.post('/api/integrations/google_drive/authorize',json={}).status_code==503
