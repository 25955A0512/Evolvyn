import asyncio
import json
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import app as module
from backend.retrieval import retrieve
from backend import providers

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    with TestClient(module.app) as c:
        c.headers['Authorization']='Bearer '+module.TOKEN
        yield c

def setup(c):
    business=c.post('/api/businesses',json={'name':'Example SaaS','goal':'Improve onboarding','product':'Task tracker'}).json()
    conversation=c.post('/api/conversations',json={'title':'Feedback research','business_id':business['id']}).json()
    text=('General company context. '*100)+'\nThe onboarding activation screen freezes for new customers.\n'+('Unrelated financial notes. '*80)
    r=c.post('/api/conversations/'+conversation['id']+'/files',files={'file':('feedback.txt',text.encode())})
    assert r.status_code==200
    return conversation

def test_retrieval_ranks_late_passages_and_preserves_offsets():
    text='unrelated intro '*300+'Onboarding activation screen freezes. '+'irrelevant notes '*300
    docs=[{'id':'d1','name':'feedback.txt','content':text}]
    result=retrieve(docs,'onboarding activation screen freezes')
    assert result[0]['score']>0
    assert result[0]['start']>1000
    assert 'screen freezes' in result[0]['excerpt']
    assert text[result[0]['start']:result[0]['end']]==result[0]['excerpt']
    assert result[0]['document_id']=='d1'

def test_background_analysis_stream_and_approval(client):
    c=setup(client)
    r=client.post(f"/api/conversations/{c['id']}/runs",json={'text':'Explain onboarding activation issues'})
    assert r.status_code==202;run=r.json()
    response=client.get('/api/executions/'+run['id']+'/live')
    snapshots=[json.loads(x[6:]) for x in response.text.split('\n\n') if x.startswith('data: ')]
    assert snapshots and snapshots[-1]['state']=='WAITING_FOR_APPROVAL'
    assert snapshots[-1]['output'].startswith('Deterministic evidence mode')
    assert snapshots[-1]['report']['evidence'][0]['score']>0
    saved=client.get('/api/conversations/'+c['id']).json()
    assert 'screen freezes' in saved['messages'][-1]['text']
    assert saved['business_id'] in [b['id'] for b in client.get('/api/businesses').json()]
    approved=client.post('/api/executions/'+run['id']+'/decision',json={'approve':True,'plan':'Interview affected customers'})
    assert approved.status_code==200
    assert client.get('/api/artifacts/'+approved.json()['artifact']).json()['plan']=='Interview affected customers'

def test_cancel_prevents_late_provider_completion(client,monkeypatch):
    async def delayed(*args):
        yield 'first real provider chunk'
        await asyncio.sleep(3)
        yield 'must not finish'
    monkeypatch.setattr(module,'response_chunks',delayed)
    c=setup(client)
    r=client.post('/api/conversations/'+c['id']+'/runs',json={'text':'onboarding'})
    id=r.json()['id']
    cancelled=client.post('/api/executions/'+id+'/cancel')
    assert cancelled.status_code==200
    final=client.get('/api/executions/'+id).json()
    assert final['state']=='CANCELLED'
    assert client.post('/api/executions/'+id+'/decision',json={'approve':True,'plan':'Bypass cancellation'}).status_code==409
    assert not final.get('artifact')

def test_background_failure_is_persisted_and_redacted(client,monkeypatch):
    async def failed(*args):
        raise httpx.ReadTimeout('secret-in-upstream-exception')
        yield
    monkeypatch.setattr(module,'response_chunks',failed)
    c=setup(client);r=client.post('/api/conversations/'+c['id']+'/runs',json={'text':'onboarding'})
    events=client.get('/api/executions/'+r.json()['id']+'/live')
    assert 'secret-in-upstream-exception' not in events.text
    final=client.get('/api/executions/'+r.json()['id']).json()
    assert final['state']=='FAILED'
    assert client.get('/api/conversations/'+c['id']).json()['messages'][-1]['text']==final['error']

def test_concurrent_run_rejected(client,monkeypatch):
    async def delayed(*args):
        await asyncio.sleep(3)
        yield 'reply'
    monkeypatch.setattr(module,'response_chunks',delayed)
    c=setup(client)
    first=client.post('/api/conversations/'+c['id']+'/runs',json={'text':'first question'})
    assert first.status_code==202
    assert client.post('/api/conversations/'+c['id']+'/runs',json={'text':'second question'}).status_code==409
    client.post('/api/executions/'+first.json()['id']+'/cancel')

def test_cross_owner_run_and_retrieval_denied(client):
    foreign=module.save('different-owner','conversation',{'title':'Private','files':[],'messages':[]})
    for path in ['/api/conversations/'+foreign['id']+'/retrieve?q=test','/api/executions/'+foreign['id']+'/live']:
        assert client.get(path).status_code==404
    assert client.post('/api/conversations/'+foreign['id']+'/runs',json={'text':'steal data'}).status_code==404

@pytest.mark.anyio
async def test_provider_stream_adapter(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-not-a-real-key')
    async def handler(request):
        assert request.url.host=='api.openai.com'
        assert request.headers['Authorization']=='Bearer test-not-a-real-key'
        body=json.loads(request.content)
        assert body['stream'] is True and body['max_tokens']==700
        assert any(m['content']=='Previous question' for m in body['messages'])
        payload='data: '+json.dumps({'choices':[{'delta':{'content':'Observed '}}]})+'\n\n'
        payload+='data: '+json.dumps({'choices':[{'delta':{'content':'evidence.'}}]})+'\n\ndata: [DONE]\n\n'
        return httpx.Response(200,text=payload)
    original=httpx.AsyncClient
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    chunks=[chunk async for chunk in providers.response_chunks({'facts':[],'evidence':[]},'Question',[{'role':'user','text':'Previous question'}])]
    assert chunks==['Observed ','evidence.']

@pytest.fixture
def anyio_backend():return 'asyncio'

@pytest.mark.anyio
async def test_explicit_evidence_mode_never_sends_configured_key(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','present-but-must-not-be-sent')
    def forbidden(*args,**kwargs):raise AssertionError('Evidence mode made a network request')
    monkeypatch.setattr(providers.httpx,'AsyncClient',forbidden)
    result=[chunk async for chunk in providers.response_chunks({'facts':[],'evidence':[]},'question',[],mode='evidence')]
    assert 'no model was called' in ''.join(result)

def test_provider_authentication_error_is_actionable(client,monkeypatch):
    async def unauthorized(*args):
        request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')
        response=httpx.Response(401,request=request)
        raise httpx.HTTPStatusError('secret-in-error',request=request,response=response)
        yield
    monkeypatch.setattr(module,'response_chunks',unauthorized)
    c=setup(client)
    execution=client.post('/api/conversations/'+c['id']+'/runs',json={'text':'Review onboarding'}).json()
    client.get('/api/executions/'+execution['id']+'/live')
    result=client.get('/api/executions/'+execution['id']).json()
    assert result['state']=='FAILED'
    assert 'authentication failed' in result['error']
    assert 'secret-in-error' not in json.dumps(result)

@pytest.mark.anyio
async def test_local_provider_needs_no_key_and_tracks_reported_usage(monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    async def handler(request):
        assert str(request.url)=='http://127.0.0.1:8081/v1/chat/completions'
        assert 'authorization' not in request.headers
        request_body=json.loads(request.content)
        assert request_body['max_tokens']==512
        data='data: '+json.dumps({'choices':[{'delta':{'content':'Local model response'}}]})+'\n\n'
        data+='data: '+json.dumps({'choices':[],'usage':{'prompt_tokens':80,'completion_tokens':3,'total_tokens':83}})+'\n\ndata: [DONE]\n\n'
        return httpx.Response(200,text=data)
    original=httpx.AsyncClient
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    report={'facts':[],'evidence':[]}
    output=''.join([chunk async for chunk in providers.response_chunks(report,'question',[],mode='local')])
    assert output=='Local model response'
    assert report['usage']['total_tokens']==83 and report['usage']['cost_usd']==0
