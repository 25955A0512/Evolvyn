import json
import pytest
import httpx
from backend import model_strategy

@pytest.fixture
def anyio_backend():return 'asyncio'

@pytest.mark.anyio
async def test_structured_model_strategy_accepts_only_supplied_citations(monkeypatch):
    proposal={'title':'Investigate the reported issue','rationale':'Validate the supplied observation before making changes','evidence':['feedback.txt:characters 1–80'],'impact':3,'confidence':.5,'effort':2,'tasks':['Review the cited evidence'],'risks':['Unrepresentative sample'],'assumptions':['Source is correctly labeled']}
    async def handler(request):
        assert str(request.url)=='http://127.0.0.1:8081/v1/chat/completions'
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'recommendations':[proposal]})}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(model_strategy.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    report={'facts':[],'evidence':[{'source':'feedback.txt','citation':'feedback.txt:characters 1–80','excerpt':'Onboarding is confusing'}],'success_metric':'Measure activation'}
    result=await model_strategy.propose(report,'What should we investigate?','local')
    assert result[0]['title']==proposal['title'] and result[0]['classification'].startswith('Model-generated')
    proposal['evidence']=['fabricated-source']
    with pytest.raises(ValueError):await model_strategy.propose(report,'Question','local')

@pytest.mark.anyio
async def test_streaming_gateway_honors_graph_output_token_reservation(monkeypatch):
    from backend import providers
    requests=[]
    async def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,text='data: '+json.dumps({'choices':[{'delta':{'content':'Supported finding'}}]})+'\n\ndata: [DONE]\n\n')
    original=httpx.AsyncClient
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    report={'facts':[],'evidence':[],'_output_limit':128}
    result=''.join([part async for part in providers.response_chunks(report,'Review',[],'local')])
    assert result=='Supported finding'
    assert requests[0]['max_tokens']==128
