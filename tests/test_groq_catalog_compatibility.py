"""Current Groq catalogs must not be rejected by a stale model-ID allowlist."""
import json
from types import SimpleNamespace
import httpx,pytest
from test_connected_identity import c
from backend import cloud_models,groq_gateway
from backend.model_access import model_scope,model_for
from backend.providers import PROVIDERS


def catalog_boundary(monkeypatch,models,results=None):
    seen=[];original=httpx.AsyncClient
    async def handle(request):
        assert request.url.host=='api.groq.com'
        assert request.headers['Authorization']=='Bearer synthetic-catalog-token'
        if request.method=='GET':return httpx.Response(200,json={'data':models})
        body=json.loads(request.content);seen.append(body)
        response=(results or {}).get(body['model'],200)
        if isinstance(response,int) and response!=200:return httpx.Response(response,json={'error':{'message':'private upstream detail'}})
        text=response if isinstance(response,str) else '{"ok":true}'
        return httpx.Response(200,json={'choices':[{'message':{'content':text},'finish_reason':'stop'}]})
    stub=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handle),**kw),Timeout=httpx.Timeout)
    monkeypatch.setattr(cloud_models,'httpx',stub);monkeypatch.setattr(groq_gateway,'httpx',stub)
    return seen


def save(c):return c.post('/api/vault/model-key',json={'name':'Groq catalog acceptance','provider':'groq','value':'synthetic-catalog-token'})

@pytest.mark.parametrize('id',['openai/gpt-oss-20b','openai/gpt-oss-120b','qwen/qwen3-32b','mistral-saba-24b','future-vendor/text-chat'])
def test_other_catalog_chat_models_are_probed_and_become_real_default(c,monkeypatch,id):
    seen=catalog_boundary(monkeypatch,[{'id':id,'active':True},{'id':'llama-3.3-70b-versatile','active':False},{'id':'whisper-large-v3','active':True},{'id':'openai/gpt-oss-safeguard-20b','active':True}])
    result=save(c);assert result.status_code==200,result.text
    assert result.json()['verified_model']==id
    assert len(seen)==1 and seen[0]['model']==id and seen[0]['response_format']=={'type':'json_object'}
    if id.startswith('openai/gpt-oss-'):
        assert seen[0]['reasoning_effort']=='low' and seen[0]['include_reasoning'] is False and seen[0]['max_completion_tokens']==512
    elif id.startswith('qwen/'):
        assert seen[0]['reasoning_effort']=='none' and seen[0]['reasoning_format']=='hidden'
    else:assert 'reasoning_effort' not in seen[0]
    with model_scope(c.org,'developer'):assert model_for('groq',PROVIDERS['groq'])==id
    assert all(r['model']==id and r['provider']=='groq' for r in c.get('/api/vault').json()['effective_routes'].values())

@pytest.mark.parametrize('error',[400,403,404,'not JSON','{}'])
def test_model_specific_failure_checks_another_model_in_same_provider(c,monkeypatch,error):
    seen=catalog_boundary(monkeypatch,[{'id':'llama-3.3-70b-versatile'},{'id':'mistral-saba-24b'}],{'llama-3.3-70b-versatile':error})
    result=save(c);assert result.status_code==200,result.text
    assert result.json()['verified_model']=='mistral-saba-24b'
    assert [b['model'] for b in seen]==['llama-3.3-70b-versatile','mistral-saba-24b']

@pytest.mark.parametrize('error',[401,429,503])
def test_global_auth_quota_and_availability_failures_do_not_burn_other_probes(c,monkeypatch,error):
    seen=catalog_boundary(monkeypatch,[{'id':'llama-3.3-70b-versatile'},{'id':'mistral-saba-24b'}],{'llama-3.3-70b-versatile':error})
    result=save(c);assert result.status_code==502 and 'private upstream detail' not in result.text
    assert len(seen)==1
    assert c.get('/api/vault').json()['credentials']==[]


def test_audio_tool_moderation_inactive_and_invalid_identifiers_are_excluded(c,monkeypatch):
    ids=['whisper-large-v3','playai-tts','groq/compound-mini','meta-llama/llama-guard-4-12b','openai/gpt-oss-safeguard-20b','embedding-v1','speech-model','vendor/audio','bad\nname']
    seen=catalog_boundary(monkeypatch,[{'id':id,'active':True} for id in ids]+[{'id':'text-model','active':False}])
    result=save(c);assert result.status_code==502 and 'key may be valid' in result.text
    assert not seen and c.get('/api/vault').json()['credentials']==[]


def test_verification_attempts_are_bounded_and_failed_replacement_preserves_grant(c,monkeypatch):
    catalog_boundary(monkeypatch,[{'id':'mistral-saba-24b'}]);saved=save(c);saved.raise_for_status();before=c.get('/api/vault').json()
    ids=['text-chat-'+str(i) for i in range(12)]
    seen=catalog_boundary(monkeypatch,[{'id':id} for id in ids],{id:400 for id in ids})
    result=c.put('/api/vault/model-key/'+saved.json()['id'],json={'name':'Replacement','provider':'groq','value':'synthetic-catalog-token'})
    assert result.status_code==502 and 'previous key and default were kept' in result.text
    assert len(seen)==5
    after=c.get('/api/vault').json();assert before['credentials']==after['credentials'] and before['bindings']==after['bindings']
