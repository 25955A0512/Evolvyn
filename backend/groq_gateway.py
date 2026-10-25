"""Bounded fixed-destination Groq chat adapter; no tokens in prompts or URLs."""
import json
import httpx
from backend.model_errors import ModelFailure
from backend.agent_memory import reject_secrets

async def completion(messages,model,credential,limit=700,json_output=False,max_chars=16000):
    if not credential:raise ModelFailure('model_not_configured','Save a Gemini or Groq key in Key vault.')
    payload={'model':model,'messages':messages,'max_completion_tokens':min(8192,max(1,limit)),'temperature':0.1,'stream':False}
    if json_output:payload['response_format']={'type':'json_object'}
    async with httpx.AsyncClient(timeout=httpx.Timeout(40,connect=8),follow_redirects=False) as client:
        async with client.stream('POST','https://api.groq.com/openai/v1/chat/completions',headers={'Authorization':'Bearer '+credential},json=payload) as response:
            response.raise_for_status();chunks=[];size=0
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>200000:raise ModelFailure('provider_output_limit','Groq response exceeded the response size limit.')
                chunks.append(chunk)
    data=json.loads(b''.join(chunks));choices=data.get('choices') or []
    if not choices:raise ModelFailure('model_response_empty','Groq returned no answer. Test the key in Key vault.')
    if choices[0].get('finish_reason')=='length':raise ModelFailure('model_output_limit','Groq reached the response token limit. Shorten this request or retry with a larger agent budget.')
    text=choices[0].get('message',{}).get('content')
    if not isinstance(text,str) or not text.strip() or len(text)>min(64000,max_chars):raise ModelFailure('model_response_empty','Groq returned no usable answer.')
    reject_secrets(text)
    if credential in text:raise ModelFailure('credential_reflection','Provider output was rejected by the credential guardrail.')
    if json_output:
        try:json.loads(text)
        except ValueError:raise ModelFailure('agent_output_invalid','Groq returned invalid structured output. No invalid project changes were accepted.') from None
    return {'choices':[{'message':{'content':text}}],'usage':{k:v for k,v in data.get('usage',{}).items() if k in ('prompt_tokens','completion_tokens','total_tokens') and type(v) is int and v>=0}}
