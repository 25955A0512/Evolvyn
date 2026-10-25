"""Private browser fixture: real app/DB/MCP; controlled provider HTTP responses."""
import os
from types import SimpleNamespace
import httpx
from qa_clean_studio_app import app
from backend import business_connectors as bc,business_mcp as bm
for p in bc.PROVIDERS:
    os.environ['OAUTH_'+p.upper()+'_CLIENT_ID']='synthetic-client-'+p
    os.environ['OAUTH_'+p.upper()+'_CLIENT_SECRET']='synthetic-secret-'+p
original=httpx.AsyncClient
async def handler(request):
    if request.url.path in ('/token','/api/oauth.v2.access','/admin/oauth/access_token'):
        p='google_drive' if request.url.host=='oauth2.googleapis.com' else 'slack' if request.url.host=='slack.com' else 'shopify'
        return httpx.Response(200,json={'access_token':'synthetic-access-'+p,'scope':(' ' if p=='google_drive' else ',').join(bc.PROVIDERS[p]['scopes']),'expires_in':3600,'refresh_token':'synthetic-refresh-token','ok':True,'team':{'id':'TTEST123'}})
    if request.url.path=='/drive/v3/about':return httpx.Response(200,json={'user':{'permissionId':'DRIVE123','displayName':'Synthetic Drive'}})
    if request.url.path=='/api/auth.test':return httpx.Response(200,json={'ok':True,'bot_id':'BTEST123','team_id':'TTEST123','team':'Synthetic Slack'})
    if request.url.path.endswith('/graphql.json'):return httpx.Response(200,json={'data':{'shop':{'id':'gid://shopify/Shop/123','name':'Synthetic Shopify','myshopifyDomain':'synthetic-store.myshopify.com'}}})
    raise AssertionError('Unexpected provider endpoint')
stub=SimpleNamespace(AsyncClient=lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
bc.httpx=stub;bm.httpx=stub
