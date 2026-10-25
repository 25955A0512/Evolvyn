"""Deployable read-only MCP starter; uses existing numerical tools, no business DB."""
import asyncio,hmac,os,re
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount,Route
from backend.mcp_utilities import compare_rates,validate_funnel


def create_app(token=None,public_host=None):
    token=token if token is not None else os.getenv('MCP_SERVER_TOKEN','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token):raise ValueError('Set MCP_SERVER_TOKEN to a private URL-safe random token of 32–128 characters')
    public_host=public_host if public_host is not None else os.getenv('MCP_PUBLIC_HOST') or os.getenv('RENDER_EXTERNAL_HOSTNAME','')
    if public_host and not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?',public_host):raise ValueError('MCP_PUBLIC_HOST must be a hostname without a scheme, path or port')
    hosts=['localhost','127.0.0.1']+([public_host.lower()] if public_host else [])
    security=TransportSecuritySettings(enable_dns_rebinding_protection=True,allowed_hosts=[h+':*' for h in hosts]+hosts,allowed_origins=['https://'+h for h in hosts]+['http://localhost:*','http://127.0.0.1:*'])
    server=FastMCP('My business metrics',stateless_http=True,json_response=True,transport_security=security)

    @server.tool()
    def calculate_conversion(visits:int,paid:int)->dict:
        """Calculate conversion from supplied counts. No store account or customer data is read."""
        return validate_funnel(visits,paid)

    @server.tool()
    def compare_conversion_rates(before:float,after:float)->dict:
        """Compare supplied percentage rates. Observed change does not establish causation."""
        return compare_rates(before,after)

    protocol=server.streamable_http_app()
    @asynccontextmanager
    async def lifespan(app):
        async with server.session_manager.run():yield
    async def health(request):return JSONResponse({'status':'ok','transport':'streamable_http','tools':['calculate_conversion','compare_conversion_rates']})
    app=Starlette(routes=[Route('/health',health),Mount('/',app=protocol)],lifespan=lifespan)
    app.state.mcp_server=server
    return TrustedHostMiddleware(BearerBoundary(app,token),allowed_hosts=hosts)


class BearerBoundary:
    def __init__(self,app,token):self.app=app;self.expected=('Bearer '+token).encode()
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['path']=='/health':return await self.app(scope,receive,send)
        headers=dict(scope['headers'])
        if not hmac.compare_digest(headers.get(b'authorization',b''),self.expected):
            return await JSONResponse({'detail':'Bearer authorization required'},401,headers={'WWW-Authenticate':'Bearer','Cache-Control':'no-store'})(scope,receive,send)
        # Bound even chunked JSON bodies before the MCP protocol parser reads them.
        if scope['method'] in ('POST','DELETE'):
            chunks=[];size=0
            try:
                async with asyncio.timeout(10):
                    while True:
                        message=await receive()
                        if message['type']=='http.disconnect':return
                        body=message.get('body',b'');size+=len(body)
                        if size>65536:return await JSONResponse({'detail':'MCP request exceeds 64 KiB'},413)(scope,receive,send)
                        chunks.append(body)
                        if not message.get('more_body',False):break
            except TimeoutError:return await JSONResponse({'detail':'MCP request timed out'},408)(scope,receive,send)
            pending=True
            original_receive=receive
            async def buffered_receive():
                nonlocal pending
                if pending:
                    pending=False
                    return {'type':'http.request','body':b''.join(chunks),'more_body':False}
                return await original_receive()
            receive=buffered_receive
        await self.app(scope,receive,send)


def main():
    import uvicorn
    port=int(os.getenv('PORT','8071'))
    if not 1<=port<=65535:raise ValueError('PORT must be between 1 and 65535')
    uvicorn.run(create_app(),host='0.0.0.0',port=port,access_log=False,limit_concurrency=32)

if __name__=='__main__':main()
