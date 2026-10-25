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
            if response.status_code==404:raise ModelFailure('provider_model_unavailable','The Gemini model is unavailable for this key. Open Key vault and test or replace the key to refresh its supported model automatically.')
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

async def available_models(credential):
    """List provider-advertised generation models using a private header, never guessed IDs."""
    import asyncio,json,re
    from backend.model_errors import failure
    rows={};page=None;seen=set()
    try:
        async with asyncio.timeout(30),httpx.AsyncClient(timeout=httpx.Timeout(10,connect=5),follow_redirects=False) as client:
            for _ in range(3):
                params={'pageSize':100}
                if page:params['pageToken']=page
                chunks=[];size=0
                async with client.stream('GET','https://generativelanguage.googleapis.com/v1beta/models',headers={'x-goog-api-key':credential},params=params) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        size+=len(chunk)
                        if size>262144:raise ValueError('Model response exceeds budget')
                        chunks.append(chunk)
                result=json.loads(b''.join(chunks))
                if not isinstance(result,dict) or not isinstance(result.get('models',[]),list) or len(result.get('models',[]))>100 or credential in json.dumps(result):raise ValueError('Invalid model catalog')
                for row in result.get('models',[]):
                    if not isinstance(row,dict) or 'generateContent' not in row.get('supportedGenerationMethods',[]):continue
                    name=row.get('name','')
                    if not isinstance(name,str) or not name.startswith('models/'):continue
                    id=name.removeprefix('models/')
                    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,150}',id) or credential in json.dumps(row):raise ValueError('Invalid model metadata')
                    from backend.cloud_models import SUPPORTED
                    if id not in SUPPORTED['gemini']:continue
                    rows[id]={'id':id,'display_name':str(row.get('displayName',id))[:150]}
                page=result.get('nextPageToken')
                if not page:break
                if not isinstance(page,str) or len(page)>2048 or page in seen:raise ValueError('Invalid catalog pagination')
                seen.add(page)
    except Exception as error:
        code,message=failure(error)
        if code in ('execution_failed','provider_model_unavailable'):code,message='model_discovery_failed','Gemini model discovery failed. Verify API access for this key and retry; no route was changed.'
        raise ModelFailure(code,message) from None
    return {'models':sorted(rows.values(),key=lambda r:r['id']),'truncated':bool(page),'classification':'Platform-supported Gemini text/JSON models; listing does not prove successful generation or available quota.'}
