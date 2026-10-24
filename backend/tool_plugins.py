"""Persistent tool adapters, capability discovery and transaction-bound human approvals."""
import hashlib
import json
from datetime import datetime,timezone
from typing import Literal
from uuid import uuid4,uuid5,NAMESPACE_URL
from fastapi import Depends,HTTPException
from jsonschema import Draft202012Validator,ValidationError as SchemaValidationError
from pydantic import BaseModel,ConfigDict,Field
from backend.policy import RISK
from backend.registry import ToolContext
from backend.mcp_registry import is_external

class Registration(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=80,pattern=r'^[A-Za-z][A-Za-z0-9_.-]*$')
    description:str=Field(min_length=1,max_length=1000)
    adapter:Literal['builtin','mcp']
    builtin:str|None=None
    server_id:str|None=None
    remote_tool:str|None=None
    capabilities:list[str]=Field(default=[],max_length=20)
    entities:list[str]=Field(default=[],max_length=20)
    enabled:bool=True

class Invoke(BaseModel):
    model_config=ConfigDict(extra='forbid')
    arguments:dict

class NoteInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str
    text:str=Field(min_length=1,max_length=4000)
class NoteOutput(BaseModel):
    id:str
    conversation:str
    text:str


def fingerprint(spec):return hashlib.sha256(json.dumps(spec,sort_keys=True,default=str).encode()).hexdigest()

def digest(name,args,version):return fingerprint({'name':name,'arguments':args,'version':version})

class ToolPlugins:
    def __init__(self,registry,mcp,policy,get,save,listing):
        self.registry=registry;self.mcp=mcp;self.policy=policy;self.get=get;self.save=save;self.listing=listing
    def spec(self,owner,name):
        if name in self.registry.tools:
            tool=self.registry.tools[name]
            return {'name':name,'description':tool.description,'adapter':'builtin','builtin':name,'input_schema':tool.input_schema.model_json_schema(),'output_schema':tool.output_schema.model_json_schema(),'risk':tool.risk,'permission':tool.permission,'timeout_seconds':tool.timeout,'capabilities':[name],'entities':[],'enabled':True,'idempotent':tool.risk=='read' or getattr(tool,'idempotent',False)}
        row=next((t for t in self.listing(owner,'registered_tool') if t['name']==name),None)
        if not row or not row['enabled']:raise HTTPException(404,'Registered tool is unavailable')
        if row['adapter']=='builtin':
            base=self.spec(owner,row['builtin'])
            return {**base,**{k:row[k] for k in ('name','description','capabilities','entities')},'registration_id':row['id'],'id':row['id']}
        server=self.mcp.server(owner,row['server_id'])
        discovered=next((t for t in server.get('tools',[]) if t['name']==row['remote_tool']),None)
        if not discovered:raise HTTPException(409,'Probe the MCP server to discover this tool')
        return {**row,'input_schema':discovered['input_schema'],'output_schema':None,'protocol_output_schema':discovered.get('output_schema'),'risk':server['risk'],'permission':'workspace.read' if server['risk']=='read' else 'workspace.write','timeout_seconds':server['timeout_seconds'],'idempotent':server['risk']=='read','server_version':fingerprint({k:server.get(k) for k in ('profile','url','auth_env','credential_id','credential_version','risk','enabled','updated_at','tools')})}
    def catalog(self,owner,capability='',entity=''):
        names=list(self.registry.tools)+[t['name'] for t in self.listing(owner,'registered_tool') if t['enabled']]
        result=[]
        for name in names:
            try:spec=self.spec(owner,name)
            except HTTPException:continue
            if capability and capability not in spec['capabilities']:continue
            if entity and entity not in spec['entities']:continue
            from backend.runtime_catalog import annotate
            result.append(annotate(spec))
        return result
    def validate(self,owner,name,arguments):
        def reject_credentials(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if str(key).lower().replace('_','').replace('-','') in {'apikey','password','authorization','accesstoken','clientsecret','secretkey'}:raise HTTPException(422,'Credentials must use a scoped environment binding, never tool arguments')
                    reject_credentials(item)
            elif isinstance(value,list):
                for item in value:reject_credentials(item)
        reject_credentials(arguments)
        spec=self.spec(owner,name)
        try:Draft202012Validator(spec['input_schema']).validate(arguments)
        except SchemaValidationError:raise HTTPException(422,'Tool arguments do not match the registered input contract; inspect the tool schema and supply the required fields')
        if spec.get('builtin')=='create_experiment_brief':self.get(owner,arguments['execution_id'],'execution')
        conversation=self.get(owner,arguments['conversation_id'],'conversation') if arguments.get('conversation_id') else None
        if spec['adapter']=='mcp' and is_external(self.mcp.server(owner,spec['server_id'])):
            if not self.policy.settings(owner)['allow_external_processing']:raise HTTPException(403,'Organization policy forbids external processing')
            if conversation:self.policy.data(owner,conversation,'mcp')
        return spec
    async def invoke(self,owner,name,arguments,context,approved=False):
        spec=self.validate(owner,name,arguments)
        if spec['adapter']=='mcp' and context.execution_id and is_external(self.mcp.server(owner,spec['server_id'])):
            execution=self.get(owner,context.execution_id,'execution')
            conversation=self.get(owner,execution['conversation'],'conversation')
            self.policy.data(owner,conversation,'mcp')
        self.policy.tool(owner,name,spec['risk'],spec['permission'],context.permissions,approved)
        context.approved=approved
        context.exposed_name=name
        if spec['adapter']=='builtin':
            return await self.registry.invoke(spec['builtin'],arguments,context)
        if context.remaining<=0:raise HTTPException(403,'Tool-call budget exhausted')
        context.remaining-=1
        result=await self.mcp.call(owner,spec['server_id'],spec['remote_tool'],arguments)
        context.trace.append({'stage':'tool','detail':name+': validated MCP invocation','tool':name,'risk':spec['risk']})
        return result
    def request(self,owner,name,arguments):
        spec=self.validate(owner,name,arguments)
        self.policy.require(owner,'write')
        # Check allowlists and risk ceilings without granting execution.
        self.policy.tool(owner,name,spec['risk'],spec['permission'],{'workspace.read','workspace.write'},True)
        linked_conversation=arguments.get('conversation_id')
        if spec.get('builtin')=='create_experiment_brief':linked_conversation=self.get(owner,arguments['execution_id'],'execution')['conversation']
        return self.save(owner,'tool_approval',{'tool':name,'arguments':arguments,'spec':spec,'binding':digest(name,arguments,fingerprint(spec)),'state':'WAITING_FOR_APPROVAL','requested_at':datetime.now(timezone.utc).isoformat(),'conversation':linked_conversation})
    async def decide(self,owner,id,approve):
        self.policy.require(owner,'approve');self.get(owner,id,'tool_approval')
        with self.policy.conn() as c:
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='tool_approval' FOR UPDATE",(owner,id)).fetchone();body=row['body']
            if body['state']!='WAITING_FOR_APPROVAL':raise HTTPException(409,'Approval was already consumed')
            current=self.spec(owner,body['tool'])
            if digest(body['tool'],body['arguments'],fingerprint(current))!=body['binding']:raise HTTPException(409,'Tool or server configuration changed; request approval again')
            body.update(state='EXECUTING' if approve else 'REJECTED',decided_at=datetime.now(timezone.utc).isoformat(),decided_by=self.policy.principal(owner).account)
            c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(body),id))
        if not approve:return {'id':id,**body}
        context=ToolContext(owner,permissions=frozenset({'workspace.read','workspace.write'}),idempotency_key=id)
        try:
            result=await self.invoke(owner,body['tool'],body['arguments'],context,True)
            body.update(state='COMPLETED',result=result,trace=context.trace)
        except Exception:
            # A remote write may have succeeded before the connection broke. Never retry it automatically.
            body.update(state='FAILED',error='Tool failed or outcome is uncertain; reconcile the action before a new request.')
        return self.save(owner,'tool_approval',body,id)


def install(app,auth,service):
    @app.get('/api/tool-registry')
    def tools(capability:str='',entity:str='',owner=Depends(auth)):return service.catalog(owner,capability,entity)
    @app.post('/api/tool-registry')
    def register(body:Registration,owner=Depends(auth)):
        service.policy.require(owner,'manage_registry')
        if body.name in service.registry.tools or any(t['name']==body.name for t in service.listing(owner,'registered_tool')):raise HTTPException(409,'Tool name already exists')
        if body.adapter=='builtin':
            if body.builtin not in service.registry.tools or body.server_id or body.remote_tool:raise HTTPException(422,'Select an existing built-in implementation')
        else:
            if not body.server_id or not body.remote_tool:raise HTTPException(422,'MCP server and discovered tool are required')
            server=service.mcp.server(owner,body.server_id)
            if not any(t['name']==body.remote_tool for t in server.get('tools',[])):raise HTTPException(422,'Probe the MCP server before registering a discovered tool')
        return service.save(owner,'registered_tool',{**body.model_dump(),'updated_at':datetime.now(timezone.utc).isoformat()})
    @app.patch('/api/tool-registry/{id}')
    def toggle(id:str,body:dict,owner=Depends(auth)):
        service.policy.require(owner,'manage_registry');row=service.get(owner,id,'registered_tool')
        if set(body)!={'enabled'} or not isinstance(body['enabled'],bool):raise HTTPException(422,'Only enabled may be changed here')
        row.update(body);return service.save(owner,'registered_tool',{k:v for k,v in row.items() if k!='id'},id)
    @app.delete('/api/tool-registry/{id}')
    def remove(id:str,owner=Depends(auth)):
        service.policy.require(owner,'manage_registry');service.get(owner,id,'registered_tool')
        with service.policy.conn() as c:c.execute("DELETE FROM records WHERE owner=%s AND id=%s AND kind='registered_tool'",(owner,id))
        return {'deleted':id}
    @app.post('/api/tool-registry/{name}/invoke')
    async def invoke(name:str,body:Invoke,owner=Depends(auth)):
        from jsonschema import ValidationError
        try:
            context=ToolContext(owner)
            return {'result':await service.invoke(owner,name,body.arguments,context),'trace':context.trace}
        except ValidationError:raise HTTPException(422,'Arguments do not match the discovered tool schema')
        except HTTPException:raise
        except TimeoutError:raise HTTPException(504,'Tool execution exceeded its timeout')
        except Exception:raise HTTPException(502,'Tool unavailable or output validation failed')
    @app.post('/api/tool-registry/{name}/request-approval')
    def request(name:str,body:Invoke,owner=Depends(auth)):
        from jsonschema import ValidationError
        try:return service.request(owner,name,body.arguments)
        except ValidationError:raise HTTPException(422,'Arguments do not match tool schema')
    @app.get('/api/tool-approvals')
    def approvals(owner=Depends(auth)):return service.listing(owner,'tool_approval')
    @app.post('/api/tool-approvals/{id}/decision')
    async def decision(id:str,body:dict,owner=Depends(auth)):
        if set(body)!={'approve'} or not isinstance(body['approve'],bool):raise HTTPException(422,'A Boolean approval decision is required')
        return await service.decide(owner,id,body['approve'])
