"""Native fixed-destination Gemini adapter shared by agent and strategy callers."""
from urllib.parse import quote
import httpx
from backend.agent_memory import reject_secrets
from backend.model_errors import ModelFailure

async def completion(messages,model,credential,limit=700,json_output=False,max_chars=16000):
    if not credential:raise ModelFailure('model_not_configured','Gemini needs a saved, active workspace credential.')
    model=model.removeprefix('models/')
    generation={'maxOutputTokens':limit,'temperature':0.1}
    # Flash 2.5 thinking consumes the same generation budget. Small agent
    # contracts require a response rather than exhausting it on hidden thinking.
    if model.startswith('gemini-2.5-flash'):generation['thinkingConfig']={'thinkingBudget':0}
    if json_output:generation['responseMimeType']='application/json'
    body={'systemInstruction':{'parts':[{'text':'\n'.join(m['content'] for m in messages if m['role']=='system')}]},'contents':[{'role':'model' if m['role']=='assistant' else 'user','parts':[{'text':m['content']}]} for m in messages if m['role'] in ('user','assistant')],'generationConfig':generation}
    url='https://generativelanguage.googleapis.com/v1beta/models/'+quote(model.removeprefix('models/'),safe='')+':generateContent'
    async with httpx.AsyncClient(timeout=httpx.Timeout(40,connect=8),follow_redirects=False) as client:
        async with client.stream('POST',url,headers={'x-goog-api-key':credential},json=body) as response:
            response.raise_for_status();chunks=[];size=0
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>200_000:raise ModelFailure('provider_output_limit','Provider response exceeded the safe response size limit.')
                chunks.append(chunk)
            import json
            payload=json.loads(b''.join(chunks))
    candidates=payload.get('candidates') or []
    if not candidates:raise ModelFailure('model_response_blocked','Gemini returned no candidate. Check provider safety restrictions and model availability.')
    candidate=candidates[0]
    if candidate.get('finishReason')=='MAX_TOKENS':raise ModelFailure('model_output_limit','Gemini exhausted the response token budget. Shorten the request or increase the configured agent budget.')
    text=''.join(p.get('text','') for p in candidate.get('content',{}).get('parts',[]) if not p.get('thought'))
    if not text.strip() or len(text)>min(64000,max_chars):raise ModelFailure('model_response_empty','Gemini returned no usable response. Check the selected model and provider restrictions.')
    reject_secrets(text)
    if credential in text:raise ModelFailure('credential_reflection','Provider output was rejected by the credential guardrail.')
    counts=payload.get('usageMetadata',{})
    usage={b:counts[a] for a,b in [('promptTokenCount','prompt_tokens'),('candidatesTokenCount','completion_tokens'),('totalTokenCount','total_tokens')] if type(counts.get(a)) is int and counts[a]>=0}
    return {'choices':[{'message':{'content':text}}],'usage':usage}
