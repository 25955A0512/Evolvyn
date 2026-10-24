from datetime import datetime,timezone
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from backend.policy import DEFAULTS

class PolicyInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    tool_allowlist:list[str]=Field(default=['*'],max_length=100)
    denied_tools:list[str]=Field(default=[],max_length=100)
    max_tool_risk:Literal['read','internal_write','external_write','critical']='external_write'
    max_tool_calls:int=Field(default=16,ge=1,le=64)
    max_run_seconds:int=Field(default=300,ge=10,le=600)
    allow_external_processing:bool=True
    allowed_mcp_hosts:list[str]=Field(default=[],max_length=30)

class ProjectAccess(BaseModel):
    model_config=ConfigDict(extra='forbid')
    access:Literal['organization','restricted']
    members:list[str]=Field(default=[],max_length=100)

def install(app,auth,policy,get,save,listing):
    @app.get('/api/governance/policy')
    def read(owner=Depends(auth)):
        return policy.settings(owner)
    @app.put('/api/governance/policy')
    def write(body:PolicyInput,owner=Depends(auth)):
        policy.require(owner,'manage_policy')
        return save(owner,'policy',{**body.model_dump(),'updated_at':datetime.now(timezone.utc).isoformat()},'policy-'+owner)
    @app.put('/api/projects/{id}/access')
    def project_access(id:str,body:ProjectAccess,owner=Depends(auth)):
        policy.require(owner,'manage_policy');project=get(owner,id,'project')
        if body.members:
            with policy.conn() as c:
                valid={r['account_id'] for r in c.execute('SELECT account_id FROM memberships WHERE organization_id=%s',(owner,)).fetchall()}
            if not set(body.members)<=valid:raise HTTPException(422,'Project members must belong to the organization')
        project.update(body.model_dump());return save(owner,'project',{k:v for k,v in project.items() if k!='id'},id)
    @app.post('/api/governance/evaluate')
    def evaluate(body:dict,owner=Depends(auth)):
        # Read-only policy explanations cannot grant a permission or approval.
        try:
            policy.tool(owner,str(body.get('tool','')),body.get('risk','read'),body.get('permission','workspace.read'),{'workspace.read'},False)
            return {'allowed':True,'approval_required':False}
        except HTTPException as e:return {'allowed':False,'approval_required':e.status_code==409,'reason':e.detail}
        except (KeyError,TypeError):raise HTTPException(422,'Invalid policy evaluation')
