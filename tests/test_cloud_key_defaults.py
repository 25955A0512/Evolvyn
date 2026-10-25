"""Cloud-only UI workflow: verified key, real vault/default routing, controlled HTTPS."""
import asyncio,json
from types import SimpleNamespace
from uuid import uuid4
import httpx,pytest
from test_connected_identity import c,save_key
from backend import app as m,cloud_models,gemini_gateway,groq_gateway
from backend.model_access import model_scope,effective_mode,key_for,model_for
from backend.providers import PROVIDERS,response_chunks
from backend.model_errors import ModelFailure


def boundary(monkeypatch,fail=None):
    seen=[];original=httpx.AsyncClient
    async def handler(request):
        seen.append(request)
        if request.method=='GET':
            if request.url.host=='api.groq.com':return httpx.Response(200,json={'data':[{'id':'llama-3.3-70b-versatile','active':True},{'id':'whisper-large-v3','active':True},{'id':'llama-3.1-8b-instant','active':False}]})
            return httpx.Response(200,json={'models':[{'name':'models/'+name,'supportedGenerationMethods':['generateContent']} for name in ['gemini-2.5-flash-lite','gemini-2.5-flash','gemini-image-model','gemini-live-audio','gemini-preview-future']]})
        if fail:return httpx.Response(fail,json={'error':{'message':'synthetic private upstream error'}})
        payload=json.loads(request.content)
        if request.url.host=='api.groq.com':
            assert 'max_completion_tokens' in payload and payload['stream'] is False
            text=(json.dumps({'ok':True}) if not any(marker in json.dumps(payload['messages']) for marker in ('PRODUCT_PLAN_JSON','PRODUCT_INTERVIEW_JSON')) else json.dumps({'reply':'Synthetic Groq planning reply: who will use the product?','proposed_requirements':{}})) if payload.get('response_format') else 'Synthetic Groq specialist response.'
            return httpx.Response(200,json={'choices':[{'message':{'content':text},'finish_reason':'stop'}],'usage':{'prompt_tokens':12,'completion_tokens':8,'total_tokens':20}})
        assert request.url.host=='generativelanguage.googleapis.com'
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}],'usageMetadata':{'promptTokenCount':12,'candidatesTokenCount':8,'totalTokenCount':20}})
    stub=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw),Timeout=httpx.Timeout)
    monkeypatch.setattr(cloud_models,'httpx',stub);monkeypatch.setattr(gemini_gateway,'httpx',stub);monkeypatch.setattr(groq_gateway,'httpx',stub)
    return seen

@pytest.mark.parametrize('provider',['gemini','groq'])
def test_save_verifies_supported_model_and_assigns_every_agent(c,monkeypatch,provider):
    seen=boundary(monkeypatch);key='synthetic-cloud-key-'+uuid4().hex
    # An obsolete local default and role override cannot hijack the new key.
    c.put('/api/vault/bindings/default',json={'provider':'local'}).raise_for_status()
    c.put('/api/vault/bindings/reviewer',json={'provider':'evidence'}).raise_for_status()
    r=c.post('/api/vault/model-key',json={'name':'Synthetic '+provider,'provider':provider,'value':key});r.raise_for_status()
    assert r.json()['verified_model']==cloud_models.SUPPORTED[provider][0]
    routes=c.get('/api/vault').json()['effective_routes']
    for agent in routes:
        with model_scope(c.org,agent):
            assert effective_mode('default')==provider and key_for(provider,PROVIDERS[provider])==key
            assert model_for(provider,PROVIDERS[provider])==cloud_models.SUPPORTED[provider][0]
    assert {route['credential_id'] for route in routes.values()}=={r.json()['id']}
    assert len(c.get('/api/vault').json()['bindings'])==1
    assert key not in c.get('/api/vault').text
    assert len(seen)==2
    assert c.post('/api/providers/'+provider+'/test').json()['available'] is True


def test_existing_groq_key_recovers_legacy_local_default(c,monkeypatch):
    row,key=save_key(c,'groq');c.put('/api/vault/bindings/default',json={'provider':'local','model':'qwen2.5-1.5b-instruct'}).raise_for_status()
    seen=boundary(monkeypatch)
    with model_scope(c.org,'architect'):
        assert effective_mode('default')=='groq'
        async def run():return ''.join([chunk async for chunk in response_chunks({'facts':[],'evidence':[],'_response_schema':{'type':'object'}},'Return JSON',[],'default')])
        assert json.loads(asyncio.run(run()))=={'ok':True}
    assert seen[-1].headers['Authorization']=='Bearer '+key
    assert json.loads(seen[-1].content)['model']=='llama-3.3-70b-versatile'

@pytest.mark.parametrize('status',[400,401,403,404,429,503])
def test_failed_key_verification_preserves_previous_default(c,monkeypatch,status):
    boundary(monkeypatch);r=c.post('/api/vault/model-key',json={'name':'Valid existing','provider':'gemini','value':'synthetic-good-key'});r.raise_for_status()
    before=c.get('/api/vault').json();boundary(monkeypatch,status)
    result=c.post('/api/vault/model-key',json={'name':'Rejected key','provider':'groq','value':'synthetic-bad-key'})
    assert result.status_code==502 and 'synthetic private upstream' not in result.text
    after=c.get('/api/vault').json();assert before['bindings']==after['bindings'] and before['credentials']==after['credentials']


def test_revocation_never_falls_back_to_another_provider_or_local(c,monkeypatch):
    boundary(monkeypatch)
    for provider in ['gemini','groq']:
        r=c.post('/api/vault/model-key',json={'name':'Synthetic '+provider,'provider':provider,'value':'synthetic-cloud-'+provider});r.raise_for_status()
    c.delete('/api/vault/credentials/'+r.json()['id']).raise_for_status()
    with model_scope(c.org,'supervisor'):
        with pytest.raises(ModelFailure,match='Gemini or Groq'):effective_mode('default')


def test_model_key_requires_admin_scope_policy_and_supported_provider(c,monkeypatch):
    boundary(monkeypatch)
    assert c.post('/api/vault/model-key',json={'name':'Other','provider':'provider','value':'synthetic-openai-key'}).status_code==422
    policy=c.get('/api/governance/policy').json();c.put('/api/governance/policy',json={**policy,'allow_external_processing':False}).raise_for_status()
    assert c.post('/api/vault/model-key',json={'name':'Blocked','provider':'groq','value':'synthetic-cloud-key'}).status_code==403
    assert c.get('/api/providers').json() and {p['id'] for p in c.get('/api/providers').json()}=={'gemini','groq'}


def test_gemini_catalog_excludes_unsupported_modalities_and_preview(c,monkeypatch):
    boundary(monkeypatch)
    result=asyncio.run(gemini_gateway.available_models('synthetic-catalog-key'))
    assert {r['id'] for r in result['models']}==set(cloud_models.SUPPORTED['gemini'])

def test_no_key_is_actionable_at_queue_admission(c):
    conv=c.post('/api/conversations',json={'title':'Missing key'}).json()
    r=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Hello','mode':'default','analysis_kind':'assistant'})
    assert r.status_code in (422,503) and 'Gemini or Groq' in r.text


def test_key_verification_rechecks_role_before_saving(c,monkeypatch):
    original=httpx.AsyncClient
    async def revoked(request):
        if request.method=='GET':return httpx.Response(200,json={'models':[{'name':'models/gemini-2.5-flash-lite','supportedGenerationMethods':['generateContent']}]})
        with m.conn() as db:db.execute("UPDATE memberships SET role='viewer' WHERE organization_id=%s",(c.org,))
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]})
    stub=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(revoked),**kw),Timeout=httpx.Timeout);monkeypatch.setattr(gemini_gateway,'httpx',stub)
    r=c.post('/api/vault/model-key',json={'name':'Revoked role','provider':'gemini','value':'synthetic-cloud-key'})
    assert r.status_code==403
    with m.conn() as db:assert db.execute("SELECT count(*) n FROM records WHERE owner=%s AND kind='vault_secret'",(c.org,)).fetchone()['n']==0


def test_replace_cannot_revive_a_key_revoked_during_verification(c,monkeypatch):
    boundary(monkeypatch);r=c.post('/api/vault/model-key',json={'name':'Original','provider':'gemini','value':'synthetic-original-key'});r.raise_for_status();id=r.json()['id'];original=httpx.AsyncClient
    async def revoked(request):
        if request.method=='GET':return httpx.Response(200,json={'models':[{'name':'models/gemini-2.5-flash-lite','supportedGenerationMethods':['generateContent']}]})
        with m.conn() as db:db.execute("UPDATE records SET body=(body-'ciphertext') || '{\"enabled\":false}'::jsonb WHERE owner=%s AND id=%s",(c.org,id))
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]})
    monkeypatch.setattr(gemini_gateway,'httpx',SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(revoked),**kw),Timeout=httpx.Timeout))
    r=c.put('/api/vault/model-key/'+id,json={'name':'Replacement','provider':'gemini','value':'synthetic-replacement-key'})
    assert r.status_code==409
    with m.conn() as db:
        row=db.execute("SELECT body FROM records WHERE owner=%s AND id=%s",(c.org,id)).fetchone()['body'];assert not row['enabled'] and 'ciphertext' not in row


def test_groq_default_runs_actual_product_chat_graph(c,monkeypatch):
    seen=boundary(monkeypatch)
    saved=c.post('/api/vault/model-key',json={'name':'Groq project key','provider':'groq','value':'synthetic-product-groq-key'});saved.raise_for_status()
    product=c.post('/api/studio/products',json={'name':'Synthetic habit tracker','goal':'Build a habit tracking app with streaks'}).json()
    r=c.post('/api/studio/products/'+product['id']+'/messages',json={'spec_id':product['id'],'revision':product['revision'],'text':'Help me design a habit tracker','mode':'default','intent':'chat'});r.raise_for_status()
    c.get('/api/executions/'+r.json()['id']+'/live')
    done=c.get('/api/executions/'+r.json()['id']).json()
    assert done['state']=='COMPLETED',done.get('error')
    assert 'Synthetic Groq planning reply' in done['graph_checkpoint']['nodes']['proposal']['output']['reply']
    assert {request.url.host for request in seen}=={'api.groq.com'}
    assert 'synthetic-product-groq-key' not in json.dumps(done)
