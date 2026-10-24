"""Real database/MCP lifecycle, with explicitly mocked external OAuth/model transports."""
import asyncio,json
from urllib.parse import parse_qs,urlparse
from uuid import uuid4
import httpx,pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend import app as module
from backend.model_access import model_scope,effective_mode,key_for
from backend.providers import PROVIDERS,response_chunks

@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv('EVOLVYN_VAULT_MASTER_KEY',Fernet.generate_key().decode())
    with TestClient(module.app,client=(uuid4().hex,50000)) as client:
        client.headers['X-Requested-With']='Evolvyn'
        response=client.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'connected-identity-acceptance','name':'Synthetic connector workspace'})
        assert response.status_code==201,response.text
        client.org=response.json()['organization_id'];yield client

def save_key(c,provider='gemini'):
    key='unit-model-key-'+uuid4().hex
    response=c.post('/api/vault/credentials',json={'name':'Synthetic model credential','provider':provider,'value':key})
    assert response.status_code==200,response.text
    return response.json(),key

def test_saved_gemini_key_defaults_all_roles_and_explicit_selection(c):
    row,key=save_key(c)
    for role in ('supervisor','business_analyst','marketing_analyst','product_manager','architect','developer','reviewer'):
        with model_scope(c.org,role):
            assert effective_mode('default')=='gemini'
            assert key_for('gemini',PROVIDERS['gemini'])==key
    c.put('/api/vault/bindings/reviewer',json={'provider':'evidence'}).raise_for_status()
    with model_scope(c.org,'reviewer'):
        assert effective_mode('default')=='evidence'
        assert key_for('gemini',PROVIDERS['gemini'])==key
    c.put('/api/vault/bindings/default',json={'provider':'gemini','credential_id':row['id'],'model':'gemini-2.5-flash-lite'}).raise_for_status()
    c.put('/api/vault/workspace-default',json={'provider':'gemini','credential_id':row['id'],'reset_agent_overrides':True}).raise_for_status()
    assert next(r for r in c.get('/api/vault').json()['bindings'] if r['agent']=='default')['model']=='gemini-2.5-flash-lite'
    assert set(r['provider'] for r in c.get('/api/vault').json()['effective_routes'].values())=={'gemini'}
    with model_scope('another-organization','supervisor'):assert effective_mode('default')=='local' and key_for('gemini',PROVIDERS['gemini'])!=key
    assert key not in c.get('/api/vault').text

def test_default_selection_never_guesses_between_multiple_keys(c):
    first,key=save_key(c);save_key(c)
    with model_scope(c.org,'architect'):
        assert effective_mode('default')=='local'
        with pytest.raises(Exception):key_for('gemini',PROVIDERS['gemini'])
    c.put('/api/vault/workspace-default',json={'provider':'gemini','credential_id':first['id']}).raise_for_status()
    with model_scope(c.org,'architect'):assert effective_mode('default')=='gemini'

def configure_github(monkeypatch):
    monkeypatch.setenv('OAUTH_GITHUB_CLIENT_ID','synthetic-oauth-client')
    monkeypatch.setenv('OAUTH_GITHUB_CLIENT_SECRET','synthetic-oauth-secret')

def begin(c):
    response=c.post('/api/integrations/github/authorize');assert response.status_code==200,response.text
    query=parse_qs(urlparse(response.json()['authorize_url']).query)
    assert query['scope']==['read:user'] and query['code_challenge_method']==['S256']
    assert query['redirect_uri']==['http://localhost:3000/api/auth/oauth/github/callback']
    return query['state'][0]

def mocked_github(monkeypatch):
    credential='unit-github-access-'+uuid4().hex;seen=[]
    async def handler(request):
        seen.append((request.method,request.url.host,request.url.path))
        if request.url.host=='github.com':
            assert 'code_verifier=' in request.content.decode()
            return httpx.Response(200,json={'access_token':credential})
        assert str(request.url)=='https://api.github.com/user'
        assert request.headers['Authorization']=='Bearer '+credential
        return httpx.Response(200,json={'id':123456,'login':'synthetic-acceptance'})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    return credential,seen

def test_github_browser_authorization_creates_real_mcp_registry_and_revoke(c,monkeypatch):
    configure_github(monkeypatch);credential,seen=mocked_github(monkeypatch)
    state=begin(c)
    response=c.get('/api/auth/oauth/github/callback',params={'state':state,'code':'unit-authorization-code'},follow_redirects=False)
    assert response.status_code==303,response.text
    assert response.headers['location']=='/integrations?connection=github'
    status=c.get('/api/integrations/connections').json()['github']['connection']
    assert status['state']=='connected' and status['login']=='synthetic-acceptance'
    tools=c.get('/api/tool-registry').json();github=[t for t in tools if t['name'].startswith('github_')]
    assert {t['name'] for t in github}=={'github_repository','github_issues','github_repositories'}
    assert all(t['risk']=='read' for t in github)
    assert credential not in c.get('/api/vault').text and credential not in json.dumps(status)
    with module.conn() as db:
        row=db.execute("SELECT body FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['body']
        assert credential not in json.dumps(row) and row['ciphertext']
    assert c.get('/api/auth/oauth/github/callback',params={'state':state,'code':'unit-authorization-code'},follow_redirects=False).status_code==400
    assert c.post('/api/integrations/github/test').json()['state']=='connected'
    assert c.delete('/api/integrations/github').status_code==200
    assert c.get('/api/integrations/connections').json()['github']['connection']['state']=='disconnected'
    assert not [t for t in c.get('/api/tool-registry').json() if t['name'].startswith('github_')]
    with module.conn() as db:assert 'ciphertext' not in db.execute("SELECT body FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['body']

def test_github_callback_rejects_other_browser_and_revoked_session(c,monkeypatch):
    configure_github(monkeypatch);state=begin(c)
    c.cookies.delete('evolvyn_session_connector')
    assert c.get('/api/auth/oauth/github/callback',params={'state':state,'code':'test'},follow_redirects=False).status_code==400
    state=begin(c)
    c.post('/api/auth/sessions/revoke-all').raise_for_status()
    assert c.get('/api/auth/oauth/github/callback',params={'state':state,'code':'test'},follow_redirects=False).status_code==403

def test_oauth_setup_is_visible_without_credentials_and_v1_enforces_auth(c,monkeypatch):
    for provider in ('GOOGLE','GITHUB'):
        monkeypatch.delenv('OAUTH_'+provider+'_CLIENT_ID',raising=False);monkeypatch.delenv('OAUTH_'+provider+'_CLIENT_SECRET',raising=False)
    providers=c.get('/api/auth/providers').json()
    assert len(providers)==2 and all(not p['enabled'] and p['setup']['callback_url'] for p in providers)
    response=c.post('/api/integrations/github/authorize');assert response.status_code==503
    assert c.get('/api/v1/vault').status_code==200
    assert len(c.get('/api/v1/vault').headers['X-Request-ID'])==32
    c.cookies.clear();assert c.get('/api/v1/vault').status_code==401

@pytest.fixture
def anyio_backend():return 'asyncio'

@pytest.mark.anyio
async def test_native_gemini_json_and_output_budget_guard(c,monkeypatch):
    row,key=save_key(c)
    async def handler(request):
        assert request.url.host=='generativelanguage.googleapis.com' and request.url.path.endswith(':generateContent')
        assert request.headers['x-goog-api-key']==key and key not in request.content.decode()
        body=json.loads(request.content);assert body['generationConfig']['thinkingConfig']=={'thinkingBudget':0}
        assert body['generationConfig']['responseMimeType']=='application/json'
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"reply":"Synthetic provider-generated response","proposed_requirements":{}}'}]}}],'usageMetadata':{'promptTokenCount':12,'candidatesTokenCount':10,'totalTokenCount':22}})
    original=httpx.AsyncClient;monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    with model_scope(c.org,'product_manager'):
        report={'facts':[],'evidence':[],'_response_schema':{'type':'object'}}
        text=''.join([chunk async for chunk in response_chunks(report,'Question',[],'default')])
        assert json.loads(text)['reply']=='Synthetic provider-generated response' and report['usage']['total_tokens']==22
    from backend.gemini_gateway import completion
    from backend.model_errors import ModelFailure
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'candidates':[{'finishReason':'MAX_TOKENS'}]})),**kwargs))
    with pytest.raises(ModelFailure) as error:await completion([{'role':'user','content':'Question'}],'gemini-2.5-flash',key,100)
    assert error.value.code=='model_output_limit'

def test_agent_quota_failure_has_actionable_saved_diagnostic(c,monkeypatch):
    save_key(c)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(lambda request:httpx.Response(429,json={'error':'private provider detail'})),**kwargs))
    product=c.post('/api/studio/products',json={'name':'Synthetic store','goal':'An online clothing store'}).json()
    run=c.post('/api/studio/products/'+product['id']+'/messages',json={'spec_id':product['id'],'revision':1,'text':'Who are the customers?','mode':'default'}).json()
    c.get('/api/executions/'+run['id']+'/live')
    final=c.get('/api/executions/'+run['id']).json()
    assert final['state']=='FAILED' and final['error_code']=='provider_quota'
    assert 'quota' in final['error'] and 'private provider detail' not in json.dumps(final)

def test_prd_edit_conflict_docx_export_and_tenant_boundary(c):
    from xml.etree import ElementTree as ET
    import io,zipfile
    product=c.post('/api/studio/products',json={'name':'Synthetic storefront','goal':'A clothing catalog and orders workspace'}).json();path='/api/studio/products/'+product['id']+'/prd'
    assert c.get(path).json()['revision']==0 and c.get(path+'.docx').status_code==409
    text='# Product requirements\nUsers browse clothing & track orders.\n<script>text, never executable markup</script>'
    response=c.put(path,json={'revision':0,'text':text});assert response.status_code==200,response.text
    assert response.json()['revision']==1
    assert c.put(path,json={'revision':0,'text':'stale overwrite'}).status_code==409
    document=c.get(path+'.docx');assert document.status_code==200
    assert 'wordprocessingml.document' in document.headers['content-type']
    with zipfile.ZipFile(io.BytesIO(document.content)) as archive:
        xml=archive.read('word/document.xml');ET.fromstring(xml)
        assert b'&lt;script&gt;' in xml and b'<script>' not in xml and b'Users browse clothing &amp;' in xml
    foreign=module.save('other-organization','product_spec',{'name':'Other product','goal':'Private','requirements':{},'revision':1})
    assert c.get('/api/studio/products/'+foreign['id']+'/prd.docx').status_code==404

def test_discussion_without_upload_invokes_real_gateway_and_persists_no_fake_metrics(c,monkeypatch):
    save_key(c);calls=[]
    original=httpx.AsyncClient
    async def handler(request):
        calls.append(request.url.host)
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Synthetic model response asking about the business goal. No measurements available.'}]}}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    conv=c.post('/api/conversations',json={'title':'General specialist discussion'}).json()
    response=c.post('/api/discussions',json={'conversation_id':conv['id'],'goal':'hi','mode':'default','max_rounds':1})
    assert response.status_code==202,response.text
    id=response.json()['id'];c.get('/api/executions/'+id+'/live');run=c.get('/api/executions/'+id).json()
    assert run['state']=='WAITING_FOR_APPROVAL',run
    assert len(calls)==4 and all(h=='generativelanguage.googleapis.com' for h in calls)
    assert run['report'] is None and run['discussion_checkpoint']['tool_calls']==0
    assert not module.listing(c.org,'task')

def test_discussion_role_can_ask_agents_but_not_edit_or_approve(c,monkeypatch):
    owner_cookie=c.cookies.get('evolvyn_session');org=c.org
    conv=c.post('/api/conversations',json={'title':'Shared discussion'}).json()
    email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':email,'password':'synthetic-discussion-password','name':'Discussion member'}).raise_for_status()
    member_cookie=c.cookies.get('evolvyn_session')
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/')
    c.post('/api/organizations/members',json={'email':email,'role':'discussant'}).raise_for_status()
    c.cookies.set('evolvyn_session',member_cookie,domain='testserver.local',path='/');c.headers['X-Organization-Id']=org
    async def respond(*args):return {'text':'Controlled agent reply for permission testing','mode':'local','fallback':False}
    monkeypatch.setattr(module.AGENTS,'respond',respond)
    assert c.get('/api/conversations').status_code==200
    run=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Can we discuss the product?','analysis_kind':'assistant','mode':'local'})
    assert run.status_code==202,run.text
    c.get('/api/executions/'+run.json()['id']+'/live')
    assert c.get('/api/executions/'+run.json()['id']).json()['state']=='COMPLETED'
    assert c.post('/api/businesses',json={'name':'Unauthorized edit'}).status_code==403
    assert c.post('/api/integrations/github/authorize').status_code==403
    assert c.put('/api/vault/workspace-default',json={'provider':'local'}).status_code==403
    assert c.post('/api/executions/'+run.json()['id']+'/decision',json={'approve':True,'plan':'Bypass approval'}).status_code==403

def test_support_uses_saved_workspace_default_without_business_document_access(c,monkeypatch):
    row,key=save_key(c)
    for name in ('EVOLVYN_HELP_GEMINI_KEY','EVOLVYN_HELP_GROQ_KEY'):monkeypatch.delenv(name,raising=False)
    conv=c.post('/api/conversations',json={'title':'Private evidence'}).json()
    sentinel='private-business-marker-'+uuid4().hex
    c.post('/api/conversations/'+conv['id']+'/files',files={'file':('private.txt',sentinel.encode())}).raise_for_status()
    async def handler(request):
        assert sentinel not in request.content.decode() and key not in request.content.decode()
        assert request.headers['x-goog-api-key']==key
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Synthetic Gemini support response'}]}}]})
    original=httpx.AsyncClient;monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    response=c.post('/api/help/ask',json={'question':'How do I build a product?'})
    assert response.status_code==200,response.text
    assert response.json()['messages'][-1]['text']=='Synthetic Gemini support response'

@pytest.mark.anyio
async def test_github_adapter_refuses_private_unknown_and_traversal(monkeypatch):
    from backend import github_mcp
    calls=[]
    async def private(path,params=None):calls.append(path);return {'private':True}
    monkeypatch.setattr(github_mcp,'get',private)
    with pytest.raises(ValueError):await github_mcp.github_repository('owner','repo')
    with pytest.raises(ValueError):await github_mcp.github_issues('owner','repo')
    count=len(calls)
    with pytest.raises(ValueError):await github_mcp.github_repository('../escape','repo')
    assert len(calls)==count
    async def malformed(path,params=None):return {'full_name':'unknown/repository'}
    monkeypatch.setattr(github_mcp,'get',malformed)
    with pytest.raises(ValueError):await github_mcp.github_repository('owner','repo')

def test_github_context_is_blocked_for_local_only_project_before_network(c,monkeypatch):
    business=c.post('/api/businesses',json={'name':'Private project'}).json()
    project=c.post('/api/projects',json={'business_id':business['id'],'name':'Local evidence','goal':'Keep data local','data_policy':'local_only'}).json()
    conv=c.post('/api/conversations',json={'title':'Local only','business_id':business['id'],'project_id':project['id']}).json()
    server=module.save(c.org,'mcp_server',{'name':'Synthetic GitHub policy test','enabled':True,'transport':'stdio','profile':'github','risk':'read','timeout_seconds':20,'tools':[{'name':'github_repository','description':'Synthetic read schema','input_schema':{'type':'object'},'output_schema':None}]})
    module.save(c.org,'registered_tool',{'name':'github_repository','description':'Synthetic adapter binding','adapter':'mcp','server_id':server['id'],'remote_tool':'github_repository','capabilities':[],'entities':[],'enabled':True})
    async def forbidden(*args):raise AssertionError('Local-only project reached an external connector')
    monkeypatch.setattr(module.MCP_REGISTRY,'call',forbidden)
    response=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Review repository feedback','mode':'evidence','context_tools':[{'name':'github_repository','arguments':{}}]})
    assert response.status_code==403 and 'local' in response.text
