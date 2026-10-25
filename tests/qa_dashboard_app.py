"""Isolated real API/DB/browser; explicitly controlled Gemini and Groq HTTPS."""
import json,httpx
from types import SimpleNamespace
from qa_chat_app import app
from backend import gemini_gateway,groq_gateway,cloud_models
original=httpx.AsyncClient
TEXT='Controlled specialist response. Validate the supplied evidence before changing the plan.'+'\n\n'+'\n\n'.join('Synthetic detail '+str(i)+': this paragraph exercises reading and scrolling of a long specialist answer. No live account was accessed.' for i in range(12))
async def provider(request):
    if request.method=='GET':
        if request.url.host=='api.groq.com':return httpx.Response(200,json={'data':[{'id':'openai/gpt-oss-20b','active':True},{'id':'whisper-large-v3','active':True}]})
        return httpx.Response(200,json={'models':[{'name':'models/gemini-2.5-flash-lite','supportedGenerationMethods':['generateContent']}]})
    body=json.loads(request.content)
    if request.url.host=='api.groq.com':return httpx.Response(200,json={'choices':[{'message':{'content':'{"ok":true}' if body.get('response_format') else TEXT},'finish_reason':'stop'}]})
    text='{"ok":true}' if body['generationConfig']['maxOutputTokens']==128 else TEXT
    return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':text}]},'finishReason':'STOP'}]})
stub=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(provider),**kw),Timeout=httpx.Timeout)
gemini_gateway.httpx=stub;groq_gateway.httpx=stub;cloud_models.httpx=stub
