"""Isolated dashboard acceptance with controlled model and catalog HTTP boundaries."""
import json,httpx
from types import SimpleNamespace
from qa_chat_app import app
from backend import gemini_gateway
original=httpx.AsyncClient
async def provider(request):
    assert request.url.host=='generativelanguage.googleapis.com'
    if request.method=='GET':return httpx.Response(200,json={'models':[{'name':'models/synthetic-visible-model','supportedGenerationMethods':['generateContent']}]})
    return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'Controlled specialist response. Validate the supplied evidence before changing the plan.'}]},'finishReason':'STOP'}]})
gemini_gateway.httpx=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(provider),**kw),Timeout=httpx.Timeout)
