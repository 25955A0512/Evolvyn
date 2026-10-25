"""Model inventory is read from the authenticated provider; routes never silently switch."""
import json
from uuid import uuid4
import httpx,pytest
from test_connected_identity import c,save_key
from backend import gemini_gateway


def boundary(monkeypatch,handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(gemini_gateway.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))


def test_inventory_then_explicit_default_drives_real_product_workflow(c,monkeypatch):
    row,key=save_key(c);seen=[]
    def handler(request):
        assert request.headers['x-goog-api-key']==key and key not in str(request.url)
        seen.append((request.method,request.url.path))
        if request.method=='GET':return httpx.Response(200,json={'models':[{'name':'models/gemini-2.5-flash-lite','displayName':'Synthetic current model','supportedGenerationMethods':['generateContent']},{'name':'models/synthetic-embedding','supportedGenerationMethods':['embedContent']}]})
        assert request.url.path.endswith('/gemini-2.5-flash-lite:generateContent')
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps({'reply':'Synthetic provider reply: who will use this store?','proposed_requirements':{}})}]},'finishReason':'STOP'}]})
    boundary(monkeypatch,handler)
    result=c.post('/api/vault/credentials/'+row['id']+'/models');result.raise_for_status()
    assert result.json()['models']==[{'id':'gemini-2.5-flash-lite','display_name':'Synthetic current model'}]
    assert key not in result.text
    c.put('/api/vault/workspace-default',json={'provider':'gemini','credential_id':row['id'],'model':'gemini-2.5-flash-lite','reset_agent_overrides':True}).raise_for_status()
    routes=c.get('/api/vault').json()['effective_routes'];assert all(r['resolved_model']=='gemini-2.5-flash-lite' for r in routes.values())
    product=c.post('/api/studio/products',json={'name':'Synthetic store','goal':'Sell products in an online store'}).json()
    run=c.post('/api/studio/products/'+product['id']+'/messages',json={'spec_id':product['id'],'revision':product['revision'],'text':'Who should we build this for?','mode':'default','intent':'chat'});run.raise_for_status()
    c.get('/api/executions/'+run.json()['id']+'/live')
    done=c.get('/api/executions/'+run.json()['id']).json()
    assert done['state']=='COMPLETED',done
    assert 'who will use this store?' in done['graph_checkpoint']['nodes']['proposal']['output']['reply']
    assert key not in json.dumps(done) and any(method=='POST' for method,path in seen)

@pytest.mark.parametrize('case',['denied','oversized','malformed','reflection','loop'])
def test_discovery_failure_changes_no_routes_or_exposes_key(c,monkeypatch,case):
    row,key=save_key(c);before=c.get('/api/vault').json()['bindings']
    def handler(request):
        if case=='denied':return httpx.Response(403,json={'error':key})
        if case=='oversized':return httpx.Response(200,content=b'x'*262145)
        if case=='malformed':return httpx.Response(200,content=b'not-json')
        if case=='reflection':return httpx.Response(200,json={'models':[{'name':'models/model','displayName':key,'supportedGenerationMethods':['generateContent']}]})
        return httpx.Response(200,json={'models':[],'nextPageToken':'repeat'})
    boundary(monkeypatch,handler)
    r=c.post('/api/vault/credentials/'+row['id']+'/models');assert r.status_code==502 and key not in r.text
    assert c.get('/api/vault').json()['bindings']==before


def test_inventory_cannot_cross_tenants_or_external_policy(c,monkeypatch):
    row,key=save_key(c)
    def handler(request):raise AssertionError('No provider call authorized')
    boundary(monkeypatch,handler)
    settings=c.get('/api/governance/policy').json();c.put('/api/governance/policy',json={**settings,'allow_external_processing':False}).raise_for_status()
    assert c.post('/api/vault/credentials/'+row['id']+'/models').status_code==403
    c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'other-model-password','name':'Other tenant'}).raise_for_status()
    assert c.post('/api/vault/credentials/'+row['id']+'/models').status_code in (403,404,409)


def test_unavailable_model_is_actionable_and_never_switches(c,monkeypatch):
    row,key=save_key(c);calls=[]
    def handler(request):calls.append(request.url.path);return httpx.Response(404,json={'error':{'message':key}})
    boundary(monkeypatch,handler)
    c.put('/api/vault/workspace-default',json={'provider':'gemini','credential_id':row['id'],'model':'retired-synthetic-model'}).raise_for_status()
    result=c.post('/api/agents/product_manager/test').json()
    assert not result['available'] and result['error_code']=='provider_model_unavailable' and 'test or replace' in result['reason']
    assert len(calls)==1 and key not in json.dumps(result)
