"""Reusable bounded workflow templates. Layout edits cannot bypass governance."""
from datetime import datetime,timezone
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict

STAGES={'observe','retrieve','analyze','strategy','respond','approval','completed','measure'}
class Position(BaseModel):
    model_config=ConfigDict(extra='forbid')
    x:float=Field(ge=0,le=1800,allow_inf_nan=False)
    y:float=Field(ge=0,le=1200,allow_inf_nan=False)
class Workflow(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=100)
    focus:str=Field(min_length=3,max_length=1000)
    mode:Literal['default','evidence','local','provider','groq','gemini','openrouter']='local'
    research:bool=False
    citations:int=Field(default=5,ge=1,le=5)
    recommendations:int=Field(default=3,ge=1,le=3)
    positions:dict[str,Position]=Field(default_factory=dict,max_length=8)

def install(app,auth,get,save,listing):
    @app.get('/api/workflow-templates')
    def templates(owner=Depends(auth)):return listing(owner,'workflow')

    @app.post('/api/workflow-templates')
    def create(body:Workflow,owner=Depends(auth)):
        if not set(body.positions)<=STAGES:raise HTTPException(422,'Unknown workflow stage')
        if len(listing(owner,'workflow'))>=100:raise HTTPException(422,'Maximum 100 workflow templates')
        return save(owner,'workflow',{**body.model_dump(),'updated_at':datetime.now(timezone.utc).isoformat()})

    @app.put('/api/workflow-templates/{id}')
    def update(id:str,body:Workflow,owner=Depends(auth)):
        get(owner,id,'workflow')
        if not set(body.positions)<=STAGES:raise HTTPException(422,'Unknown workflow stage')
        return save(owner,'workflow',{**body.model_dump(),'updated_at':datetime.now(timezone.utc).isoformat()},id)
