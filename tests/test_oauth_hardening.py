"""Actual session/state persistence; external provider boundaries explicitly controlled."""
import asyncio
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from uuid import uuid4
import httpx,pytest
from fastapi.testclient import TestClient
from backend import app as m
from backend.oauth import configuration,verified_profile
from backend.oauth_config import public_origin
from scripts.configure_oauth import read_values,write_private

@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv('PUBLIC_ORIGIN','http://localhost:3000');monkeypatch.setenv('COOKIE_SECURE','0')
    monkeypatch.setenv('OAUTH_GOOGLE_CLIENT_ID','controlled-client');monkeypatch.setenv('OAUTH_GOOGLE_CLIENT_SECRET','controlled-secret')
    with TestClient(m.app,client=(uuid4().hex,40000)) as c:
        c.headers['X-Requested-With']='Evolvyn'
        c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'private-oauth-test-password','name':'OAuth tests'}).raise_for_status()
        yield c

def link(c):
    r=c.post('/api/auth/oauth/google/link');r.raise_for_status();return parse_qs(urlsplit(r.json()['authorize_url']).query)['state'][0]
def start(c):
    r=c.get('/api/auth/oauth/google/start',follow_redirects=False);assert r.status_code==303;return parse_qs(urlsplit(r.headers['location']).query)['state'][0]
def callback(c,state,**extra):return c.get('/api/auth/oauth/google/callback',params={'state':state,'code':'controlled-code'},follow_redirects=False,**extra)

def test_link_rejects_revoked_session_before_provider(c,monkeypatch):
    state=link(c);c.post('/api/auth/sessions/revoke-all').raise_for_status()
    async def forbidden(*a):raise AssertionError('No provider call is permitted')
    monkeypatch.setattr('backend.oauth.verified_profile',forbidden)
    assert callback(c,state).status_code==403
    with m.conn() as db:assert db.execute('SELECT count(*) AS n FROM oauth_identities').fetchone()['n']==0

def test_link_revalidates_after_provider_and_preserves_organization(c,monkeypatch):
    state=link(c)
    async def profile(*a):
        with m.conn() as db:db.execute('DELETE FROM account_sessions')
        return 'controlled-subject','controlled@example.test','Controlled'
    monkeypatch.setattr('backend.oauth.verified_profile',profile)
    assert callback(c,state).status_code==403
    with m.conn() as db:assert db.execute('SELECT count(*) AS n FROM oauth_identities').fetchone()['n']==0

def test_changed_client_configuration_invalidates_pending_state(c,monkeypatch):
    state=start(c);monkeypatch.setenv('OAUTH_GOOGLE_CLIENT_SECRET','rotated-controlled-secret')
    async def forbidden(*a):raise AssertionError('Changed config must fail before network')
    monkeypatch.setattr('backend.oauth.verified_profile',forbidden)
    assert callback(c,state).status_code==400 and callback(c,state).status_code==400

def test_account_cannot_accumulate_conflicting_provider_identities(c,monkeypatch):
    subject=['controlled-one']
    async def profile(*a):return subject[0],'controlled@example.test','Controlled'
    monkeypatch.setattr('backend.oauth.verified_profile',profile)
    assert callback(c,link(c)).status_code==303
    subject[0]='controlled-two';assert callback(c,link(c)).status_code==409
    assert c.get('/api/auth/security').json()['linked_providers']==['google']

def test_secure_host_cookie_oauth_uses_root_path(c,monkeypatch):
    monkeypatch.setenv('PUBLIC_ORIGIN','https://app.example.test');monkeypatch.setenv('COOKIE_SECURE','1');monkeypatch.setenv('EVOLVYN_SESSION_COOKIE','__Host-evolvyn_session')
    r=c.get('/api/auth/oauth/google/start',follow_redirects=False)
    assert r.status_code==303
    cookie=r.headers['set-cookie'];assert '__Host-evolvyn_session_oauth=' in cookie and 'Path=/' in cookie and 'Path=/api' not in cookie and 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=lax' in cookie

@pytest.mark.parametrize('value,secure',[
    ('http://public.example.test',False),('https://example.test/path',True),('https://user:password@example.test',True),
    ('https://example.test?x=1',True),('https://example.test#fragment',True),('ftp://localhost:3000',False),
    ('https://example.test',False),('http://localhost:3000',True),('https://*.example.test',True),('https://example.test:bad',True),
])
def test_invalid_public_origins_fail_closed(value,secure):
    with pytest.raises(ValueError):public_origin(value,secure)

def test_public_configuration_explains_errors_without_secret(c,monkeypatch):
    monkeypatch.setenv('PUBLIC_ORIGIN','https://app.example.test')
    rows=c.get('/api/auth/providers').json();assert all(not r['enabled'] and r['configuration_error'] for r in rows)
    assert 'controlled-secret' not in str(rows)

def test_cancelled_browser_callback_is_readable_and_never_reflects_query(c):
    r=c.get('/api/auth/oauth/google/callback?state=private-state&error=access_denied',headers={'Accept':'text/html'},follow_redirects=False)
    assert r.status_code==400 and 'Return to sign in' in r.text and 'private-state' not in r.text
    assert r.headers['cache-control']=='no-store'

@pytest.mark.parametrize('payload',[[],{'access_token':None},{'access_token':'x'*8193},{'access_token':'x\r\nInjected: header'}])
def test_malformed_provider_token_responses_rejected(monkeypatch,payload):
    monkeypatch.setenv('PUBLIC_ORIGIN','http://localhost:3000');monkeypatch.setenv('COOKIE_SECURE','0')
    async def handler(request):return httpx.Response(200,json=payload)
    original=httpx.AsyncClient;monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(ValueError):asyncio.run(verified_profile('google',configuration('google'),'controlled-code','controlled-verifier'))

def test_oversized_provider_body_is_bounded_before_parsing(monkeypatch):
    monkeypatch.setenv('PUBLIC_ORIGIN','http://localhost:3000');monkeypatch.setenv('COOKIE_SECURE','0')
    async def handler(request):return httpx.Response(200,content=b'x'*262145)
    original=httpx.AsyncClient;monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(ValueError,match='exceeds budget'):asyncio.run(verified_profile('google',configuration('google'),'controlled-code','controlled-verifier'))

def test_private_cli_preserves_other_secrets_and_quotes_values(tmp_path):
    path=tmp_path/'deploy.env';path.write_text('POSTGRES_PASSWORD=preserved-controlled-value\nPUBLIC_ORIGIN=http://localhost:3000\n')
    secret="controlled$#value"
    write_private(path,{'PUBLIC_ORIGIN':'https://app.example.test','OAUTH_GOOGLE_CLIENT_SECRET':secret,'COOKIE_SECURE':'1'})
    assert read_values(path)['OAUTH_GOOGLE_CLIENT_SECRET']==secret
    assert 'POSTGRES_PASSWORD=preserved-controlled-value' in path.read_text() and path.stat().st_mode&0o777==0o600
    before=path.read_bytes()
    with pytest.raises(ValueError):write_private(path,{'PUBLIC_ORIGIN':'bad\nvalue'})
    assert path.read_bytes()==before
