"""Verify catalog-listed text/JSON models without changing the selected provider."""
import asyncio,json,re
import httpx
from httpx import HTTPStatusError
from backend.model_errors import ModelFailure,failure

# Preferences are ordering hints, not a gate on the provider's current catalog.
# Gemini remains a constrained adapter; Groq compatibility is verified per model.
SUPPORTED={'gemini':('gemini-2.5-flash-lite','gemini-2.5-flash'),'groq':('llama-3.3-70b-versatile','llama-3.1-8b-instant')}
GROQ_PREFERRED=(*SUPPORTED['groq'],'openai/gpt-oss-20b','openai/gpt-oss-120b','qwen/qwen3-32b')

def groq_candidates(catalog,credential):
    if not isinstance(catalog,dict) or not isinstance(catalog.get('data'),list) or len(catalog['data'])>200 or credential in json.dumps(catalog):raise ValueError('Invalid provider model catalog')
    candidates=set()
    for row in catalog['data']:
        if not isinstance(row,dict) or row.get('active') is False:continue
        id=row.get('id','')
        if not isinstance(id,str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,150}',id):continue
        # Do not attempt speech, moderation, embedding or autonomous tool systems.
        if re.search(r'whisper|(?:^|[/_-])(?:tts|audio|speech|embedding|embed|guard|safeguard|moderation|compound|orpheus|playai|canopy|thinking)(?:$|[/_-])|deepseek.*r1',id,re.I):continue
        if row.get('supports_chat') is False or row.get('supports_json') is False:continue
        candidates.add(id)
    return sorted(candidates,key=lambda id:(GROQ_PREFERRED.index(id) if id in GROQ_PREFERRED else len(GROQ_PREFERRED),id))[:5]

async def validate(provider,credential):
    if provider not in SUPPORTED:raise ModelFailure('provider_not_supported','Only Gemini and Groq are supported for agent keys.')
    try:
        async with asyncio.timeout(65):
            if provider=='gemini':
                from backend.gemini_gateway import available_models,completion
                catalog=await available_models(credential);ids={m['id'] for m in catalog['models']}
                candidates=[m for m in SUPPORTED[provider] if m in ids]
            else:
                from backend.groq_gateway import completion
                from backend.oauth import provider_json
                async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
                    catalog=await provider_json(client,'GET','https://api.groq.com/openai/v1/models',headers={'Authorization':'Bearer '+credential})
                candidates=groq_candidates(catalog,credential)
            if not candidates:raise ModelFailure('provider_model_unavailable',('Groq returned no active text-chat candidates. The key may be valid; enable a chat model in its Groq project and retry. No key was changed.' if provider=='groq' else 'This key exposes no platform-supported Gemini chat models. Check provider access and retry.'))
            for model in candidates:
                try:
                    kwargs={'timeout_seconds':15} if provider=='groq' else {}
                    limit=512 if provider=='groq' and model.startswith('openai/gpt-oss-') else 128
                    response=await completion([{'role':'system','content':'Return only valid JSON.'},{'role':'user','content':'Reply with {"ok":true} as JSON.'}],model,credential,limit,True,**kwargs)
                    if json.loads(response['choices'][0]['message']['content'])!={'ok':True}:raise ModelFailure('agent_output_invalid','The model did not follow the JSON check.')
                    return model
                except HTTPStatusError as error:
                    # Model permissions/decommissioning can differ within one key.
                    # Never retry across providers or bypass global auth/quota errors.
                    if error.response.status_code not in (400,403,404):raise
                except ModelFailure as error:
                    if error.code not in ('agent_output_invalid','model_response_empty','model_response_blocked','model_output_limit','provider_model_unavailable'):raise
            raise ModelFailure('model_compatibility','None of the checked '+('Groq' if provider=='groq' else 'Gemini')+' models passed the chat and JSON check. Check model permissions, then retry. The previous key and default were kept.')
    except Exception as error:
        code,message=failure(error)
        if code=='execution_failed':code,message='model_validation_failed','The provider did not return a valid chat response. Check API access and retry. The previous default was kept.'
        raise ModelFailure(code,message) from None
