"""Real authenticated MCP HTTP process plus tenant-scoped registry host approval."""
import asyncio,os,socket,subprocess,time
from pathlib import Path
from uuid import uuid4
import httpx,pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from backend.custom_mcp import create_app
from backend.mcp_registry import decode
from test_connected_identity import c

@pytest.fixture
def starter():
    root=Path(__file__).resolve().parents[1];(root/'.local').mkdir(exist_ok=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    token='synthetic-'+uuid4().hex
    log=(root/'.local/custom-mcp-protocol.log').open('w')
    process=subprocess.Popen([str(root/'.venv/bin/python'),'-m','backend.custom_mcp'],cwd=root,env={'PATH':os.defpath,'PYTHONPATH':str(root),'PORT':str(port),'MCP_SERVER_TOKEN':token},stdout=log,stderr=log)
    base='http://127.0.0.1:'+str(port)
    try:
        for _ in range(100):
            if process.poll() is not None:raise AssertionError('MCP starter did not start; inspect private protocol log')
            try:
                if httpx.get(base+'/health',timeout=.5,trust_env=False).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        else:raise AssertionError('MCP readiness timeout')
        yield base,token
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
        assert token not in (root/'.local/custom-mcp-protocol.log').read_text()


def test_remote_server_rejects_unauthorized_hosts_origins_and_oversized_bodies(starter):
    base,token=starter
    assert httpx.post(base+'/mcp',json={},trust_env=False).status_code==401
    assert httpx.post(base+'/mcp',headers={'Authorization':'Bearer wrong'},json={},trust_env=False).status_code==401
    headers={'Authorization':'Bearer '+token}
    assert httpx.get(base+'/health',headers={'Host':'attacker.example'},trust_env=False).status_code==400
    rejected=httpx.post(base+'/mcp',headers={**headers,'Origin':'https://attacker.example'},json={},trust_env=False)
    assert rejected.status_code==400 and rejected.text=='Invalid Origin header'
    r=httpx.post(base+'/mcp',headers=headers,content=b'x'*65537,trust_env=False);assert r.status_code==413 and token not in r.text


def test_real_http_discovery_and_calculation_tools(starter):
    base,token=starter
    async def run():
        def factory(headers=None,timeout=None,auth=None):return httpx.AsyncClient(headers=headers,timeout=timeout or 10,auth=auth,trust_env=False,follow_redirects=False)
        async with streamablehttp_client(base+'/mcp',headers={'Authorization':'Bearer '+token},httpx_client_factory=factory) as (read,write,_):
            async with ClientSession(read,write) as session:
                initialized=await session.initialize();assert initialized.serverInfo.name=='My business metrics'
                tools=(await session.list_tools()).tools;assert {t.name for t in tools}=={'calculate_conversion','compare_conversion_rates'}
                result=decode(await session.call_tool('calculate_conversion',{'visits':200,'paid':30}));assert result=={'visits':200,'paid':30,'conversion_percent':15.0}
                result=decode(await session.call_tool('compare_conversion_rates',{'before':10,'after':12}));assert result['change_percentage_points']==2 and result['causality_established'] is False
                invalid=await session.call_tool('calculate_conversion',{'visits':0,'paid':3});assert invalid.isError
    asyncio.run(run())


def public_dns(monkeypatch,ip='8.8.8.8'):
    monkeypatch.setattr(socket,'getaddrinfo',lambda host,port,**kwargs:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,port))])


def test_host_approval_is_explicit_idempotent_and_preserves_other_policy(c,monkeypatch):
    public_dns(monkeypatch)
    prior=c.get('/api/governance/policy').json();prior.update(allowed_mcp_hosts=['already-approved.example'],denied_tools=['unsafe_tool'],max_tool_calls=5)
    c.put('/api/governance/policy',json=prior).raise_for_status()
    for _ in range(2):
        r=c.post('/api/mcp/hosts/approve',json={'url':'https://starter-mcp.example/mcp'});assert r.status_code==200,r.text
    after=c.get('/api/governance/policy').json();assert after=={**prior,'allowed_mcp_hosts':['already-approved.example','starter-mcp.example']}
    result=c.post('/api/mcp/servers',json={'name':'My business metrics','transport':'streamable_http','profile':None,'url':'https://starter-mcp.example/mcp','risk':'read'})
    assert result.status_code==200,result.text
    assert result.json()['status']=='unchecked' and result.json()['tools']==[]

@pytest.mark.parametrize('url',['http://starter.example/mcp','https://user:password@starter.example/mcp','https://starter.example:8443/mcp','https://starter.example/mcp?token=secret','https://starter.example/mcp#fragment','https://[invalid-address]/mcp'])
def test_host_approval_rejects_unsafe_urls_without_saving(c,monkeypatch,url):
    public_dns(monkeypatch)
    assert c.post('/api/mcp/hosts/approve',json={'url':url}).status_code==422
    assert c.get('/api/governance/policy').json()['allowed_mcp_hosts']==[]

@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','169.254.169.254','::1'])
def test_host_approval_does_not_allow_private_or_reserved_destinations(c,monkeypatch,ip):
    public_dns(monkeypatch,ip)
    assert c.post('/api/mcp/hosts/approve',json={'url':'https://private.example/mcp'}).status_code==422
    assert c.get('/api/governance/policy').json()['allowed_mcp_hosts']==[]


def test_host_approval_checks_role_external_policy_and_tenant(c,monkeypatch):
    public_dns(monkeypatch)
    c.post('/api/mcp/hosts/approve',json={'url':'https://owner.example/mcp'}).raise_for_status()
    c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','name':'Other tenant','password':'synthetic-other-tenant-password'}).raise_for_status()
    assert c.get('/api/governance/policy').json()['allowed_mcp_hosts']==[]
    policy=c.get('/api/governance/policy').json();c.put('/api/governance/policy',json={**policy,'allow_external_processing':False}).raise_for_status()
    assert c.post('/api/mcp/hosts/approve',json={'url':'https://blocked.example/mcp'}).status_code==403
    from backend import app as m
    with m.conn() as db:db.execute("UPDATE memberships SET role='viewer' WHERE organization_id!=%s",(c.org,))
    assert c.post('/api/mcp/hosts/approve',json={'url':'https://viewer.example/mcp'}).status_code==403

@pytest.mark.parametrize('token',['','short','x'*129,'unsafe token with spaces'*2])
def test_starter_refuses_missing_or_weak_token_configuration(token):
    with pytest.raises(ValueError):create_app(token,public_host='localhost')


def test_host_approval_rechecks_administrator_membership_after_dns(c,monkeypatch):
    from backend import app as m
    def changed(host,port,**kwargs):
        with m.conn() as db:db.execute("UPDATE memberships SET role='viewer' WHERE organization_id=%s",(c.org,))
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',port))]
    monkeypatch.setattr(socket,'getaddrinfo',changed)
    r=c.post('/api/mcp/hosts/approve',json={'url':'https://revoked.example/mcp'})
    assert r.status_code==403
    assert c.get('/api/governance/policy').json()['allowed_mcp_hosts']==[]
