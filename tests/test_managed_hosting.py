"""Managed hosting boundaries: no credentials in browser config, stable vault keys and scoped hosts."""
import asyncio,base64,hashlib,json,re
from pathlib import Path
from uuid import uuid4
import httpx,pytest,yaml
from cryptography.fernet import Fernet
from scripts.container_start import runtime_environment
from scripts.configure_vercel import configure,api_origin
from backend.source_compiler import compile_frontend

def render_env(**updates):return {'PORT':'10000','RENDER':'true','RENDER_EXTERNAL_HOSTNAME':'controlled-api.onrender.com','PUBLIC_ORIGIN':'https://controlled-app.vercel.app','COOKIE_SECURE':'1','EVOLVYN_VAULT_SEED':'controlled-seed-'+uuid4().hex,**updates}

def test_render_vault_survives_restart_without_local_disk():
    env=render_env();first=runtime_environment(env);second=runtime_environment(env)
    assert first['EVOLVYN_VAULT_MASTER_KEY']==second['EVOLVYN_VAULT_MASTER_KEY']
    encrypted=Fernet(first['EVOLVYN_VAULT_MASTER_KEY']).encrypt(b'controlled-provider-credential')
    assert Fernet(second['EVOLVYN_VAULT_MASTER_KEY']).decrypt(encrypted)==b'controlled-provider-credential'
    assert first['EVOLVYN_VAULT_MASTER_KEY']!=runtime_environment(render_env())['EVOLVYN_VAULT_MASTER_KEY']

def test_existing_vault_master_key_takes_precedence_for_database_migration():
    key=Fernet.generate_key().decode();assert runtime_environment(render_env(EVOLVYN_VAULT_MASTER_KEY=key))['EVOLVYN_VAULT_MASTER_KEY']==key

def test_render_only_exact_configured_hosts_allowed():
    value=runtime_environment(render_env())
    assert set(value['ALLOWED_HOSTS'].split(','))=={'localhost','127.0.0.1','controlled-api.onrender.com','controlled-app.vercel.app'}
    assert '*' not in value['ALLOWED_HOSTS'] and value['PORT']=='10000'

@pytest.mark.parametrize('updates',[{'PORT':'0'},{'PORT':'65536'},{'PORT':'bad'},{'EVOLVYN_VAULT_SEED':'short'},{'PUBLIC_ORIGIN':''},{'PUBLIC_ORIGIN':'http://public.example.test'},{'COOKIE_SECURE':'0'},{'RENDER_EXTERNAL_HOSTNAME':'bad.example,evil.example'}])
def test_invalid_hosting_settings_rejected(updates):
    with pytest.raises(ValueError):runtime_environment(render_env(**updates))

def test_local_compose_port_and_file_vault_behavior_preserved():
    value=runtime_environment({});assert value['PORT']=='8000' and 'EVOLVYN_VAULT_MASTER_KEY' not in value
    assert 'ALLOWED_HOSTS' not in value

@pytest.mark.parametrize('url',['http://controlled.onrender.com','https://controlled.onrender.com/path','https://user:secret@controlled.onrender.com','https://controlled.onrender.com?token=secret','https://controlled.onrender.com.evil.test','https://localhost','https://controlled.onrender.com:8443'])
def test_vercel_proxy_rejects_untrusted_or_credential_bearing_destinations(url):
    with pytest.raises(ValueError):api_origin(url)

def test_vercel_routes_api_before_spa_and_keeps_frontend_secret_free():
    original=json.loads(Path('frontend/vercel.json').read_text());result=configure(original,'https://controlled-api.onrender.com')
    assert result['rewrites'][0]=={'source':'/api/:path*','destination':'https://controlled-api.onrender.com/api/:path*'}
    fallback=result['rewrites'][-1]['source'];assert re.fullmatch(fallback,'/product-studio') and not re.fullmatch(fallback,'/api/auth/oauth/google/callback')
    assert result['headers']==original['headers'] and 'EVOLVYN_VAULT' not in json.dumps(result)
    assert original!=result # writer does not mutate the source template

def test_render_blueprint_uses_private_compiler_database_and_backend_only_keys():
    spec=yaml.safe_load(Path('render.yaml').read_text());services={s['name']:s for s in spec['services']}
    assert services['evolvyn-compiler']['type']=='pserv' and services['evolvyn-api']['numInstances']==1
    assert spec['databases'][0]['ipAllowList']==[]
    env={r['key']:r for r in services['evolvyn-api']['envVars']}
    assert env['EVOLVYN_VAULT_SEED']['generateValue'] is True and env['COOKIE_SECURE']['value']=='1'
    assert env['PUBLIC_ORIGIN']['sync'] is False and env['PGSSLMODE']['value']=='require'
    assert env['EVOLVYN_COMPILER_TOKEN']['fromService']['envVarKey']=='EVOLVYN_COMPILER_TOKEN'
    assert env['EVOLVYN_COMPILER_HOSTPORT']['fromService']['property']=='hostport'

def test_render_private_compiler_hostport_uses_real_receipt(monkeypatch):
    monkeypatch.delenv('EVOLVYN_COMPILER_URL',raising=False);monkeypatch.setenv('EVOLVYN_COMPILER_HOSTPORT','controlled-compiler:8070');monkeypatch.setenv('EVOLVYN_COMPILER_TOKEN','controlled-token')
    async def handler(request):
        assert str(request.url)=='http://controlled-compiler:8070/compile' and request.headers['X-Compiler-Token']=='controlled-token'
        return httpx.Response(200,json={'status':'passed','bytes':100,'sha256':'a'*64,'checks':['controlled compiler response']})
    original=httpx.AsyncClient;monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    assert asyncio.run(compile_frontend({'frontend/src/main.jsx':'export default 1'}))['status']=='passed'

@pytest.mark.parametrize('host',['https://evil.test','user:password@host:8070','compiler:99999','compiler:8070/path'])
def test_invalid_private_compiler_address_never_calls_network(monkeypatch,host):
    monkeypatch.delenv('EVOLVYN_COMPILER_URL',raising=False);monkeypatch.setenv('EVOLVYN_COMPILER_HOSTPORT',host)
    def forbidden(*a,**kw):raise AssertionError('Network must not be called')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    assert asyncio.run(compile_frontend({}))['status']=='unavailable'
