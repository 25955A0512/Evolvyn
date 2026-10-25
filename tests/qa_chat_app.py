"""Real app/browser/DB with explicitly controlled provider model inventory."""
import httpx
from qa_clean_studio_app import app
from backend import gemini_gateway
from types import SimpleNamespace
original=httpx.AsyncClient
async def inventory(request):
    assert request.url.host=='generativelanguage.googleapis.com' and request.url.path=='/v1beta/models'
    return httpx.Response(200,json={'models':[{'name':'models/synthetic-visible-model','displayName':'Synthetic listed model','supportedGenerationMethods':['generateContent']}]})
gemini_gateway.httpx=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(inventory),**kw),Timeout=httpx.Timeout)
