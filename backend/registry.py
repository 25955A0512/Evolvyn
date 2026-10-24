"""Shared typed tool execution, backend permission checks and bounded tool calls."""
import asyncio
from dataclasses import dataclass,field
from typing import Awaitable, Callable
from pydantic import BaseModel,ConfigDict,Field

class ToolDenied(Exception):pass

@dataclass
class ToolContext:
    owner:str
    permissions:frozenset[str]=frozenset({'workspace.read'})
    remaining:int=8
    trace:list=field(default_factory=list)
    approved:bool=False
    idempotency_key:str|None=None
    exposed_name:str|None=None

@dataclass
class Tool:
    name:str
    description:str
    input_schema:type[BaseModel]
    output_schema:type[BaseModel]
    handler:Callable[...,Awaitable[dict]]
    permission:str='workspace.read'
    risk:str='read'
    timeout:float=15
    idempotent:bool=False

class ToolRegistry:
    def __init__(self):self.tools={};self.policy=None
    def register(self,tool):
        if tool.name in self.tools:raise ValueError('Duplicate tool')
        self.tools[tool.name]=tool
    def metadata(self):
        return [{'name':t.name,'description':t.description,'input_schema':t.input_schema.model_json_schema(),'output_schema':t.output_schema.model_json_schema(),'permissions':[t.permission],'risk':t.risk,'timeout_seconds':t.timeout,'status':'available'} for t in self.tools.values()]
    async def invoke(self,name,arguments,context):
        tool=self.tools.get(name)
        if not tool or tool.permission not in context.permissions:raise ToolDenied('Tool is unavailable or permission was denied')
        if self.policy:self.policy.tool(context.owner,context.exposed_name or name,tool.risk,tool.permission,context.permissions,context.approved)
        if context.remaining<=0:raise ToolDenied('Tool-call budget exhausted')
        context.remaining-=1
        validated=tool.input_schema.model_validate(arguments)
        async with asyncio.timeout(tool.timeout):result=await tool.handler(validated,context)
        output=tool.output_schema.model_validate(result).model_dump()
        context.trace.append({'stage':'tool','detail':f'{name}: input and output schemas validated','tool':name,'risk':tool.risk})
        return output

class ScopeQuery(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str=Field(min_length=1,max_length=100)
    query:str=Field(min_length=1,max_length=8000)

class AnalysisOutput(BaseModel):
    model_config=ConfigDict(extra='allow')
    facts:list[dict]
    evidence:list[dict]
    hypothesis:str
    plan:str
    success_metric:str

class Candidate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(min_length=1,max_length=100)
    title:str=Field(min_length=1,max_length=200)
    impact:int=Field(ge=1,le=5)
    confidence:float=Field(ge=0,le=1)
    effort:int=Field(ge=1,le=5)

class CandidateInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidates:list[Candidate]=Field(min_length=1,max_length=10)

class RankedRow(BaseModel):
    id:str
    score:float=Field(ge=0,le=5)

class RankingOutput(BaseModel):
    ranked:list[RankedRow]
    engine:str = "mcp"
