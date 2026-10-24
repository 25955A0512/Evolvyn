"""Controlled model fixtures exercise real persistence, tools and approval paths."""
import json
import pytest
from fastapi.testclient import TestClient
from backend import app as module
from backend.product_studio import QUESTIONS

@pytest.fixture
def client():
    with TestClient(module.app) as c:
        c.headers['Authorization']='Bearer '+module.TOKEN
        yield c

def finish(c, response):
    assert response.status_code==202,response.text
    id=response.json()['id'];c.get('/api/executions/'+id+'/live')
    return c.get('/api/executions/'+id).json()

def product(c, complete=False):
    p=c.post('/api/studio/products',json={'name':'Service desk','goal':'Track customer support requests securely'}).json()
    if complete:
        for key,_,value in QUESTIONS:
            r=c.post('/api/studio/products/'+p['id']+'/answers',json={'field':key,'text':value,'revision':p['revision']})
            assert r.status_code==200,r.text
            p=r.json()
    return p

@pytest.fixture
def models(monkeypatch):
    calls=[]
    async def chunks(report,question,history,mode):
        calls.append(question)
        if 'PRODUCT_INTERVIEW_JSON' in question:
            result={'reply':'Which customers will use this service desk?','proposed_requirements':{'theme':'dark'}}
        elif 'PRODUCT_ARCHITECTURE_JSON' in question:
            result={'nodes':[{'id':'web','label':'React'},{'id':'api','label':'API'},{'id':'db','label':'PostgreSQL'}],'edges':[{'source':'web','target':'api'},{'source':'api','target':'db'}],'notes':'Private accounts'}
        elif 'PRODUCT_EXPERIENCE_JSON' in question:
            result={'headline':'Resolve customer requests','description':'Your private service desk','sections':[{'heading':'Requests','text':'Manage your approved request records.'}]}
        elif 'PRODUCT_REVIEW_JSON' in question:
            result={'approved':True,'summary':'Source design reviewed; runtime not tested','issues':['Verify domain acceptance before deployment']}
        else:
            yield '# Service desk PRD\nTrack customer support requests. Acceptance: authenticated records persist.'
            return
        yield json.dumps(result)
    monkeypatch.setitem(module.GRAPH_HARNESS.s,'response_chunks',chunks)
    return calls

def test_auto_chat_without_csv_is_real_response_and_persists(client,monkeypatch):
    async def respond(*args):return {'text':'Unique model answer to your greeting','mode':'local','fallback':False}
    monkeypatch.setattr(module.AGENTS,'respond',respond)
    conv=client.post('/api/conversations',json={'title':'General chat'}).json()
    run=finish(client,client.post('/api/conversations/'+conv['id']+'/runs',json={'text':'hi','analysis_kind':'auto','mode':'local'}))
    assert run['state']=='COMPLETED',(run.get('error'),run.get('graph_checkpoint'))
    assert run['engine']=='assistant_chat' and run['output']=='Unique model answer to your greeting'
    saved=client.get('/api/conversations/'+conv['id']).json()
    assert saved['messages'][-1]['text']==run['output']
    assert not run.get('artifact') and not run.get('report')

def test_chat_provider_failure_is_actionable_and_persisted(client,monkeypatch):
    async def unavailable(*args):raise RuntimeError('private upstream detail')
    monkeypatch.setattr(module.AGENTS,'respond',unavailable)
    conv=client.post('/api/conversations',json={'title':'General chat'}).json()
    run=finish(client,client.post('/api/conversations/'+conv['id']+'/runs',json={'text':'hello','analysis_kind':'assistant','mode':'local'}))
    assert run['state']=='FAILED' and 'Key vault' in run['error']
    assert 'private upstream' not in json.dumps(run)
    assert 'Upload sales CSV' not in run['error']

def test_interview_proposal_requires_confirmation_and_cannot_replay(client,models):
    p=product(client);base='/api/studio/products/'+p['id']
    run=finish(client,client.post(base+'/messages',json={'spec_id':p['id'],'revision':p['revision'],'text':'Use a dark theme','mode':'local'}))
    assert run['state']=='COMPLETED',(run.get('error'),run.get('graph_checkpoint'))
    assert client.get(base).json()['requirements']=={}
    assert len(client.get(base+'/agent-history').json())==1
    body={'spec_id':p['id'],'revision':p['revision']}
    accepted=client.post(base+'/proposals/'+run['id']+'/accept',json=body)
    assert accepted.status_code==200,accepted.text
    assert accepted.json()['requirements']['theme']=='dark'
    assert client.post(base+'/proposals/'+run['id']+'/accept',json=body).status_code==409

def test_product_pipeline_approval_generates_actual_artifacts(client,models,monkeypatch):
    monkeypatch.delenv('EVOLVYN_COMPILER_URL',raising=False)
    p=product(client,True);base='/api/studio/products/'+p['id']
    run=finish(client,client.post(base+'/agent-build',json={'spec_id':p['id'],'revision':p['revision'],'mode':'local'}))
    assert run['state']=='WAITING_FOR_APPROVAL',(run.get('error'),run.get('graph_checkpoint'))
    assert not client.get('/api/studio/builds').json()
    binding=run['graph_checkpoint']['pending']['binding']
    assert client.post('/api/harness/executions/'+run['id']+'/decision',json={'approve':True,'binding':'wrong'}).status_code==409
    client.post('/api/harness/executions/'+run['id']+'/decision',json={'approve':True,'binding':binding}).raise_for_status()
    client.get('/api/executions/'+run['id']+'/live')
    final=client.get('/api/executions/'+run['id']).json()
    assert final['state']=='COMPLETED',(final.get('error'),final.get('graph_checkpoint'))
    build_id=final['graph_checkpoint']['nodes']['implementation']['output']['id']
    built=client.get('/api/studio/builds/'+build_id).json()
    assert built['state']=='READY' and built['frontend_build']['status']=='unavailable'
    assert built['files']['docs/PRD.md'].startswith('# Service desk')
    assert 'flowchart LR' in built['files']['docs/ARCHITECTURE.md']
    assert json.loads(built['files']['frontend/src/product-experience.json'])['headline']=='Resolve customer requests'
    assert 'product-experience.json' in built['files']['frontend/src/main.jsx']
    assert len(models)==4
    assert client.post('/api/harness/executions/'+run['id']+'/decision',json={'approve':True,'binding':binding}).status_code==409

def test_reviewer_rejection_never_builds(client,models,monkeypatch):
    original=module.GRAPH_HARNESS.s['response_chunks']
    async def reject(report,question,history,mode):
        if 'PRODUCT_REVIEW_JSON' in question:yield json.dumps({'approved':False,'summary':'Unsafe scope','issues':['Revise privacy']})
        else:
            async for chunk in original(report,question,history,mode):yield chunk
    monkeypatch.setitem(module.GRAPH_HARNESS.s,'response_chunks',reject)
    p=product(client,True)
    run=finish(client,client.post('/api/studio/products/'+p['id']+'/agent-build',json={'spec_id':p['id'],'revision':p['revision'],'mode':'local'}))
    assert run['state']=='COMPLETED',(run.get('error'),run.get('graph_checkpoint'))
    assert 'implementation' not in run['graph_checkpoint']['nodes']
    assert not client.get('/api/studio/builds').json()

def test_invalid_model_architecture_fails_before_write(client,models,monkeypatch):
    async def bad(*args):yield '{"nodes":[],"edges":[]}'
    monkeypatch.setitem(module.GRAPH_HARNESS.s,'response_chunks',bad)
    p=product(client,True)
    run=finish(client,client.post('/api/studio/products/'+p['id']+'/agent-build',json={'spec_id':p['id'],'revision':p['revision'],'mode':'local','agents':['architecture']}))
    assert run['state']=='FAILED',run
    assert not client.get('/api/studio/builds').json()

def test_changed_requirements_invalidate_approved_build(client,models):
    p=product(client,True);base='/api/studio/products/'+p['id']
    run=finish(client,client.post(base+'/agent-build',json={'spec_id':p['id'],'revision':p['revision'],'mode':'local'}))
    assert run['state']=='WAITING_FOR_APPROVAL',run.get('error')
    client.post(base+'/answers',json={'revision':p['revision'],'field':'theme','text':'dark'}).raise_for_status()
    binding=run['graph_checkpoint']['pending']['binding']
    client.post('/api/harness/executions/'+run['id']+'/decision',json={'approve':True,'binding':binding}).raise_for_status()
    client.get('/api/executions/'+run['id']+'/live')
    assert client.get('/api/executions/'+run['id']).json()['state']=='FAILED'
    assert not client.get('/api/studio/builds').json()

@pytest.mark.anyio
async def test_compiler_adapter_filters_inputs_and_receipts(monkeypatch):
    import httpx
    from backend import source_compiler
    monkeypatch.setenv('EVOLVYN_COMPILER_URL','http://compiler:8070')
    monkeypatch.setenv('EVOLVYN_COMPILER_TOKEN','unit-compiler-token')
    async def handler(request):
        assert request.headers['X-Compiler-Token']=='unit-compiler-token'
        assert json.loads(request.content)=={'files':{'main.jsx':'valid source'}}
        return httpx.Response(200,json={'status':'passed','sha256':'a'*64,'bytes':120,'private':'must not propagate'})
    original=httpx.AsyncClient
    monkeypatch.setattr(source_compiler.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    receipt=await source_compiler.compile_frontend({'frontend/src/main.jsx':'valid source','backend/private.py':'never sent'})
    assert receipt=={'status':'passed','sha256':'a'*64,'bytes':120}

@pytest.fixture
def anyio_backend():return 'asyncio'

def test_chat_uses_gateway_with_valid_history_contract(client,monkeypatch):
    import httpx
    async def handler(request):
        body=json.loads(request.content)
        assert request.url.host=='127.0.0.1'
        assert 'hello from browser' in json.dumps(body['messages'])
        return httpx.Response(200,json={'choices':[{'message':{'content':'Gateway-generated greeting'}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    conv=client.post('/api/conversations',json={'title':'Gateway chat'}).json()
    run=finish(client,client.post('/api/conversations/'+conv['id']+'/runs',json={'text':'hello from browser','analysis_kind':'auto','mode':'local'}))
    assert run['state']=='COMPLETED',run.get('error')
    assert run['output']=='Gateway-generated greeting'

def test_product_agents_reject_evidence_only_route_without_fake_reply(client):
    client.put('/api/vault/bindings/default',json={'provider':'evidence'}).raise_for_status()
    p=product(client)
    response=client.post('/api/studio/products/'+p['id']+'/messages',json={'spec_id':p['id'],'revision':p['revision'],'text':'Hello, help with the product','mode':'default'})
    assert response.status_code==422 and 'real model' in response.text
    assert client.get('/api/studio/products/'+p['id']+'/agent-history').json()==[]

def test_product_agent_endpoints_do_not_leak_other_organizations(client):
    foreign=module.save('foreign-organization','product_spec',{'name':'Other product','goal':'Private','requirements':{},'revision':1})
    assert client.get('/api/studio/products/'+foreign['id']+'/agent-history').status_code==404
    response=client.post('/api/studio/products/'+foreign['id']+'/messages',json={'spec_id':foreign['id'],'revision':1,'text':'Read this product','mode':'local'})
    assert response.status_code==404

@pytest.mark.anyio
async def test_incomplete_compiler_receipt_never_claims_success(monkeypatch):
    import httpx
    from backend import source_compiler
    monkeypatch.setenv('EVOLVYN_COMPILER_URL','http://compiler:8070')
    original=httpx.AsyncClient
    monkeypatch.setattr(source_compiler.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'status':'passed'})),**kwargs))
    assert (await source_compiler.compile_frontend({'frontend/src/main.jsx':'source'}))['status']=='unavailable'
