"""Persistent organization-scoped MCP registry with safe transports and redacted health."""
import asyncio
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime,timezone
import ipaddress
import json
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse
import httpx
from fastapi import Depends,HTTPException
from jsonschema import Draft202012Validator
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel,Field,ConfigDict
from typing import Literal

def credential_prefix(owner):return 'EVOLVYN_MCP_'+hashlib.sha256(owner.encode()).hexdigest()[:12].upper()+'_'

PROFILES={'business_strategy':'backend.mcp_server','evidence_utilities':'backend.mcp_utilities','github':'backend.github_mcp'}
def is_external(server):return server['transport']=='streamable_http' or server.get('profile')=='github'
class ServerInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=100)
    transport:Literal['stdio','streamable_http']='stdio'
    profile:Literal['business_strategy','evidence_utilities','github']|None='business_strategy'
    url:str|None=Field(default=None,max_length=1000)
    auth_env:str|None=Field(default=None,pattern=r'^EVOLVYN_MCP_[A-Z0-9_]+$',max_length=100)
    credential_id:str|None=Field(default=None,max_length=100)
    enabled:bool=True
    risk:Literal['read','internal_write','external_write','critical']='read'
    timeout_seconds:int=Field(default=15,ge=2,le=30)

async def public_addresses(url,hosts):
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:raise ValueError('Use an HTTPS URL without embedded credentials or fragments')
    if parsed.port not in (None,443):raise ValueError('Only standard HTTPS port 443 is permitted')
    if parsed.hostname not in hosts:raise ValueError('Host must be explicitly allowed by organization governance')
    results=await asyncio.to_thread(socket.getaddrinfo,parsed.hostname,443,type=socket.SOCK_STREAM)
    ips={r[4][0] for r in results}
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):raise ValueError('Private, loopback and reserved destinations are forbidden')
    return parsed.hostname,sorted(ips)

class GuardedTransport(httpx.AsyncBaseTransport):
    def __init__(self,url,hosts):
        self.url=url;self.hosts=hosts
        proxy=os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        self.proxied=bool(proxy)
        self.inner=httpx.AsyncHTTPTransport(proxy=proxy or None,trust_env=True)
    async def handle_async_request(self,request):
        host,ips=await public_addresses(str(request.url),self.hosts)
        if host!=urlparse(self.url).hostname:raise ValueError('MCP transport changed destination')
        if not self.proxied:
            request.headers['host']=host
            request.extensions['sni_hostname']=host
            request.url=request.url.copy_with(host=ips[0])
        # Proxied requests retain their approved hostname for the trusted egress policy.
        return await self.inner.handle_async_request(request)
    async def aclose(self):await self.inner.aclose()

def decode(result):
    if result.isError:raise ValueError('MCP tool returned an error')
    structured=getattr(result,'structuredContent',None)
    if structured is not None:
        return structured['result'] if isinstance(structured,dict) and set(structured)=={'result'} else structured
    values=[]
    for block in result.content:
        if getattr(block,'type',None)=='text':
            try:values.append(json.loads(block.text))
            except ValueError:values.append(block.text)
    return values[0] if len(values)==1 else values

class MCPRegistry:
    def __init__(self,get,save,listing,policy):self.get=get;self.save=save;self.listing=listing;self.policy=policy;self.vault=None
    def server(self,owner,id):
        row=self.get(owner,id,'mcp_server')
        if not row['enabled']:raise HTTPException(409,'MCP server is disabled')
        if row.get('credential_id') and self.vault:
            secret=next((r for r in self.vault.rows(owner,'vault_secret') if r['id']==row['credential_id']),None)
            if not secret or not secret['body']['enabled']:raise HTTPException(409,'MCP credential was revoked or is unavailable')
            row['credential_version']=secret['body']['version']
        return row
    @asynccontextmanager
    async def session(self,owner,row):
        if not row['enabled']:raise ValueError('Server disabled')
        async with asyncio.timeout(row['timeout_seconds']):
            if row['transport']=='stdio':
                env={'PATH':os.defpath,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
                if row.get('profile')=='github':
                    if not self.policy.settings(owner)['allow_external_processing']:raise HTTPException(403,'Organization policy forbids GitHub processing')
                    if not row.get('credential_id'):raise HTTPException(409,'Authorize GitHub first')
                    env['EVOLVYN_GITHUB_TOKEN']=self.vault.reveal_for_service(owner,row['credential_id'],'mcp')
                    env.update({key:os.environ[key] for key in ('HTTP_PROXY','HTTPS_PROXY','NO_PROXY','SSL_CERT_FILE') if os.getenv(key)})
                parameters=StdioServerParameters(command=sys.executable,args=['-m',PROFILES[row['profile']]],env=env)
                async with stdio_client(parameters) as (read,write):
                    async with ClientSession(read,write) as session:
                        await session.initialize();yield session
            else:
                hosts=self.policy.settings(owner)['allowed_mcp_hosts']
                await public_addresses(row['url'],hosts)
                headers={}
                if row.get('credential_id'):
                    headers['Authorization']='Bearer '+self.vault.reveal_for_service(owner,row['credential_id'],'mcp')
                elif row.get('auth_env'):
                    credential=os.getenv(row['auth_env'])
                    if not credential:raise ValueError('Missing configured credential binding')
                    headers['Authorization']='Bearer '+credential
                def factory(headers=None,timeout=None,auth=None):
                    return httpx.AsyncClient(headers=headers,timeout=timeout or httpx.Timeout(15),auth=auth,transport=GuardedTransport(row['url'],hosts),follow_redirects=False)
                async with streamablehttp_client(row['url'],headers=headers,timeout=row['timeout_seconds'],httpx_client_factory=factory) as (read,write,_):
                    async with ClientSession(read,write) as session:
                        await session.initialize();yield session
    async def probe(self,owner,id):
        row=self.server(owner,id)
        try:
            async with self.session(owner,row) as session:
                tools=(await session.list_tools()).tools
                discovered=[]
                for tool in tools[:100]:
                    input_schema=tool.inputSchema;output=getattr(tool,'outputSchema',None)
                    Draft202012Validator.check_schema(input_schema)
                    if output:Draft202012Validator.check_schema(output)
                    discovered.append({'name':tool.name,'description':(tool.description or '')[:1000],'input_schema':input_schema,'output_schema':output})
            row.update(status='healthy',tools=discovered,last_error=None)
        except Exception:row.update(status='unavailable',tools=[],last_error='Connection, authentication, schema or timeout check failed; credential values and remote errors are redacted.')
        row['last_checked_at']=datetime.now(timezone.utc).isoformat()
        return self.save(owner,'mcp_server',{k:v for k,v in row.items() if k!='id'},id)
    async def call(self,owner,id,name,arguments):
        row=self.server(owner,id)
        async with self.session(owner,row) as session:
            tools=(await session.list_tools()).tools
            tool=next((t for t in tools if t.name==name),None)
            if not tool:raise ValueError('Tool no longer exists on the MCP server')
            Draft202012Validator(tool.inputSchema).validate(arguments)
            result=await session.call_tool(name,arguments)
            # Validate the protocol's structured payload before unwrapping its result envelope.
            schema=getattr(tool,'outputSchema',None)
            if schema and getattr(result,'structuredContent',None) is not None:Draft202012Validator(schema).validate(result.structuredContent)
            value=decode(result)
            if len(json.dumps(value))>200_000:raise ValueError('MCP output limit exceeded')
            return value
    async def health_tick(self):
        with self.policy.conn() as c:
            rows=c.execute("SELECT owner,id FROM records WHERE kind='mcp_server' AND body->>'enabled'='true' AND (body->>'last_checked_at' IS NULL OR (body->>'last_checked_at')::timestamptz<now()-interval '60 seconds') ORDER BY created LIMIT 3").fetchall()
        for row in rows:
            try:await self.probe(row['owner'],row['id'])
            except Exception:pass

def install(app,auth,service):
    @app.get('/api/mcp/credential-prefix')
    def prefix(owner=Depends(auth)):return {'prefix':credential_prefix(owner)}
    @app.get('/api/mcp/profiles')
    def profiles(owner=Depends(auth)):return [{'id':key,'module':value} for key,value in PROFILES.items()]
    @app.get('/api/mcp/servers')
    def servers(owner=Depends(auth)):return service.listing(owner,'mcp_server')
    async def validate(owner,body):
        service.policy.require(owner,'manage_registry')
        if body.auth_env and not body.auth_env.startswith(credential_prefix(owner)):raise HTTPException(422,'Credential reference must use this organization’s MCP namespace')
        if body.transport=='stdio':
            if not body.profile or body.url or body.auth_env or body.credential_id:raise HTTPException(422,'Built-in stdio profiles do not accept commands, URLs or credentials')
            if body.risk!='read':raise HTTPException(422,'Built-in evidence tools are read-only')
        else:
            if body.auth_env and body.credential_id:raise HTTPException(422,'Choose one credential reference')
            if body.credential_id:
                if not service.vault:raise HTTPException(503,'Vault is unavailable')
                service.vault.reveal_for_service(owner,body.credential_id,'mcp')
            if not body.url:raise HTTPException(422,'Remote server URL is required')
            if 'risk' not in body.model_fields_set:body.risk='external_write'
            try:await public_addresses(body.url,service.policy.settings(owner)['allowed_mcp_hosts'])
            except (ValueError,OSError) as e:raise HTTPException(422,str(e))
    @app.post('/api/mcp/servers')
    async def register(body:ServerInput,owner=Depends(auth)):
        await validate(owner,body)
        if len(service.listing(owner,'mcp_server'))>=30:raise HTTPException(422,'Maximum 30 registered servers')
        return service.save(owner,'mcp_server',{**body.model_dump(),'status':'unchecked','tools':[],'last_checked_at':None,'updated_at':datetime.now(timezone.utc).isoformat()})
    @app.put('/api/mcp/servers/{id}')
    async def update(id:str,body:ServerInput,owner=Depends(auth)):
        await validate(owner,body);service.get(owner,id,'mcp_server')
        return service.save(owner,'mcp_server',{**body.model_dump(),'status':'unchecked','tools':[],'last_checked_at':None,'updated_at':datetime.now(timezone.utc).isoformat()},id)
    @app.post('/api/mcp/servers/{id}/probe')
    async def probe(id:str,owner=Depends(auth)):
        service.policy.require(owner,'manage_registry');return await service.probe(owner,id)
    @app.delete('/api/mcp/servers/{id}')
    def remove(id:str,owner=Depends(auth)):
        service.policy.require(owner,'manage_registry');service.get(owner,id,'mcp_server')
        with service.policy.conn() as c:
            bound=c.execute("SELECT id FROM records WHERE owner=%s AND kind='registered_tool' AND body->>'server_id'=%s AND body->>'enabled'='true'",(owner,id)).fetchone()
            if bound:raise HTTPException(409,'Disable or remove registered tools using this server first')
            c.execute("DELETE FROM records WHERE owner=%s AND id=%s AND kind='mcp_server'",(owner,id))
        return {'deleted':id}
