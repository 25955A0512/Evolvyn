"""Explicit read-only connector context shared by chat and the governed tool gateway."""
import json
from datetime import datetime,timezone
from pydantic import BaseModel,ConfigDict,Field
from fastapi import HTTPException
from backend.agent_memory import reject_secrets

class ContextCall(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=80)
    arguments:dict=Field(default_factory=dict)

def validate(service,owner,conversation,calls):
    for call in calls:
        if call.arguments.get('conversation_id',conversation['id'])!=conversation['id']:raise HTTPException(422,'Context tools must use the active conversation scope')
        spec=service.validate(owner,call.name,call.arguments)
        if spec['risk']!='read':raise HTTPException(422,'Analysis context accepts read-only tools; writes require a separate approved action')
        service.policy.tool(owner,call.name,spec['risk'],spec['permission'],{'workspace.read'})
        if spec['adapter']=='mcp' and service.mcp.server(owner,spec['server_id'])['transport']=='streamable_http':service.policy.data(owner,conversation,'mcp')

async def collect(service,owner,conversation,calls,context):
    validate(service,owner,conversation,calls)
    evidence=[];statuses=[]
    for call in calls:
        try:
            result=await service.invoke(owner,call.name,call.arguments,context)
            excerpt=json.dumps(result)[:6000];reject_secrets(excerpt)
            now=datetime.now(timezone.utc).isoformat()
            evidence.append({'source':call.name,'citation':'registered-tool:'+call.name,'excerpt':excerpt,'retrieved_at':now,'classification':'Actual registered tool result; external claims, freshness and comparability require verification','score':1})
            statuses.append({'tool':call.name,'status':'succeeded','retrieved_at':now})
        except HTTPException as error:
            if error.status_code in (401,403,404,409,422):raise
            statuses.append({'tool':call.name,'status':'unavailable','detail':'Connector failed; continuing with internal evidence. No external result was inferred.'})
        except Exception:
            statuses.append({'tool':call.name,'status':'unavailable','detail':'Connector failed; continuing with internal evidence. No external result was inferred.'})
    return evidence,statuses
