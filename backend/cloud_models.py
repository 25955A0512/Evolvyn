"""Only platform-supported text/JSON models; key validation never changes provider."""
import asyncio,json
import httpx
from backend.model_errors import ModelFailure,failure

SUPPORTED={'gemini':('gemini-2.5-flash-lite','gemini-2.5-flash'),'groq':('llama-3.3-70b-versatile','llama-3.1-8b-instant')}
async def validate(provider,credential):
    if provider not in SUPPORTED:raise ModelFailure('provider_not_supported','Only Gemini and Groq are supported for agent keys.')
    try:
        async with asyncio.timeout(65):
            if provider=='gemini':
                from backend.gemini_gateway import available_models,completion
                catalog=await available_models(credential);ids={m['id'] for m in catalog['models']}
            else:
                from backend.groq_gateway import completion
                from backend.oauth import provider_json
                async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
                    catalog=await provider_json(client,'GET','https://api.groq.com/openai/v1/models',headers={'Authorization':'Bearer '+credential})
                if not isinstance(catalog,dict) or not isinstance(catalog.get('data'),list) or len(catalog['data'])>200 or credential in json.dumps(catalog):raise ValueError('Invalid provider model catalog')
                ids={m.get('id') for m in catalog['data'] if isinstance(m,dict) and m.get('active') is not False and isinstance(m.get('id'),str)}
            candidates=[m for m in SUPPORTED[provider] if m in ids]
            if not candidates:raise ModelFailure('provider_model_unavailable','This key exposes no platform-supported chat models. Check provider access and retry.')
            for i,model in enumerate(candidates):
                try:
                    response=await completion([{'role':'system','content':'Return only valid JSON.'},{'role':'user','content':'Reply with {"ok":true} as JSON.'}],model,credential,128,True)
                    if not isinstance(json.loads(response['choices'][0]['message']['content']),dict):raise ValueError('Invalid JSON response')
                    return model
                except httpx.HTTPStatusError as error:
                    if error.response.status_code not in (400,404) or i==len(candidates)-1:raise
            raise ValueError('No compatible model')
    except Exception as error:
        code,message=failure(error)
        if code=='execution_failed':code,message='model_validation_failed','The provider did not return a valid chat response. Check API access and retry. The previous default was kept.'
        raise ModelFailure(code,message) from None
