"""Actual LangGraph specialist handoffs, bounded critique loops and durable node replay."""
import asyncio
import json
import re
import time
from typing import TypedDict, Literal
from uuid import uuid4, uuid5, NAMESPACE_URL
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from langgraph.graph import StateGraph, START, END
from langsmith import tracing_context
from backend.execution_queue import WORKER
from backend.policy import ACTOR, Principal
from backend.model_access import model_scope, effective_mode
from backend.registry import ToolContext
from backend.agent_memory import reject_secrets

class ContextCall(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(max_length=80)
    arguments:dict=Field(default_factory=dict)
class DiscussInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str
    growth_report_id:str|None=None
    goal:str=Field(min_length=5,max_length=2000)
    mode:Literal['default','evidence','local','provider','groq','gemini','openrouter']='default'
    allow_fallback:bool=True
    max_rounds:int=Field(default=2,ge=1,le=3)
    max_seconds:int=Field(default=300,ge=10,le=600)
    max_output_tokens:int=Field(default=6144,ge=768,le=10000)
    context_tools:list[ContextCall]=Field(default_factory=list,max_length=3)
class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    approve:bool
    plan:str=Field(min_length=3,max_length=4000)
    acknowledge_issues:bool=False
class State(TypedDict):
    outputs:dict
    round:int
    issues:list[str]

class Discussion:
    def __init__(self,services,agents): self.s,self.agents=services,agents
    def review(self,outputs,report):
        issues=[]
        allowed={float(f['conversion']) for f in report.get('facts',[]) if 'conversion' in f}
        sources={e.get('citation',e.get('source','')) for e in report.get('evidence',[])}|{f.get('source','') for f in report.get('facts',[])}
        for agent,output in outputs.items():
            for number in re.findall(r'(?<![\w.])(\d+(?:\.\d+)?)\s*%',output['text']):
                if float(number) not in allowed: issues.append(agent+': percentage claim requires source verification')
            if not output.get('fallback') and sources and agent in ('business_analyst','marketing_analyst') and not any(source in output['text'] for source in sources): issues.append(agent+': exact evidence citation missing')
        return sorted(set(issues))
    async def run(self,owner,id):
        s=self.s;run=s['claim_job'](s['conn'],owner,id)
        if not run:s['JOBS'].pop(id,None);return
        worker=WORKER.set(run['worker']);actor_token=None
        heartbeat=asyncio.create_task(s['renew_lease'](owner,id));started=time.monotonic()
        cp=run.get('discussion_checkpoint') or {'outputs':{},'events':[],'reserved_output_tokens':0,'tool_calls':0}
        def checkpoint(**updates):
            if not s['change_execution'](owner,id,{'discussion_checkpoint':cp,'events':cp['events'],**updates}):raise asyncio.CancelledError()
        try:
            actor=run.get('actor')
            if actor:
                with s['conn']() as c:member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(actor,owner)).fetchone()
                if not member:raise HTTPException(403,'Requesting membership was revoked')
                actor_token=ACTOR.set(Principal(owner,actor,member['role']))
            body=DiscussInput.model_validate(run['discussion_input'])
            conversation=s['get'](owner,body.conversation_id,'conversation')
            settings=s['POLICY'].settings(owner)
            remaining=min(body.max_seconds,settings['max_run_seconds'])-run.get('elapsed_seconds',0)
            async with asyncio.timeout(max(.001,remaining)):
                if 'report' not in cp:
                    cp['tool_calls']+=1;checkpoint()
                    if cp['tool_calls']>settings['max_tool_calls']:raise ValueError('Tool budget exhausted')
                    cp['report']=await s['TOOL_PLUGINS'].invoke(owner,'analyze_business',{'conversation_id':conversation['id'],'query':body.goal},ToolContext(owner))
                    checkpoint()
                report=cp['report']
                if body.growth_report_id and not cp.get('growth_attached'):
                    growth=s['get'](owner,body.growth_report_id,'growth_report')
                    if growth['conversation']!=conversation['id']:raise HTTPException(422,'Growth report must belong to this conversation')
                    report['evidence'].append({'source':'growth-report:'+growth['id'],'citation':'growth-report:'+growth['id'],'excerpt':json.dumps({'market':growth['market'],'first_party_change':growth.get('first_party_change'),'actions':growth['actions'],'connector_evidence':growth['connector_evidence']})[:14000],'score':1})
                    cp['growth_attached']=True;checkpoint()
                for index,call in enumerate(body.context_tools):
                    marker='context_'+str(index)
                    if marker in cp:continue
                    spec=s['TOOL_PLUGINS'].validate(owner,call.name,call.arguments)
                    if spec['adapter']=='mcp' and s['TOOL_PLUGINS'].mcp.server(owner,spec['server_id'])['transport']=='streamable_http':s['POLICY'].data(owner,conversation,'mcp')
                    if spec['risk']!='read':raise HTTPException(403,'Discussion context accepts read-only tools')
                    if cp['tool_calls']>=settings['max_tool_calls']:raise ValueError('Tool budget exhausted')
                    cp['tool_calls']+=1;checkpoint()
                    value=await s['TOOL_PLUGINS'].invoke(owner,call.name,call.arguments,ToolContext(owner))
                    excerpt=json.dumps(value)[:6000];reject_secrets(excerpt)
                    report['evidence'].append({'source':call.name,'citation':'registered-tool:'+call.name,'excerpt':excerpt,'score':1})
                    cp[marker]=True;checkpoint()
                async def agent_step(state,agent):
                    round=state['round']+(1 if agent=='product_manager' else 0)
                    cache_key=agent+':'+str(round if agent in ('product_manager','reviewer') else 0)
                    if cache_key not in cp['outputs']:
                        with model_scope(owner,agent):
                            selected=effective_mode(body.mode)
                            s['POLICY'].data(owner,conversation,selected)
                        reserve=0 if selected=='evidence' else 768
                        if cp['reserved_output_tokens']+reserve>body.max_output_tokens:raise ValueError('Output token budget exhausted')
                        cp['reserved_output_tokens']+=reserve
                        cp['events'].append({'stage':agent,'detail':'Running specialist handoff','round':round});checkpoint()
                        output=await self.agents.respond(owner,agent,conversation,report,body.goal,state['outputs'],body.mode,body.allow_fallback)
                        cp['outputs'][cache_key]=output
                        cp['events'].append({'stage':agent,'detail':output['classification'],'round':round});checkpoint()
                    outputs={**state['outputs'],agent:cp['outputs'][cache_key]}
                    return {'outputs':outputs,'round':round,'issues':self.review(outputs,report) if agent=='reviewer' else state['issues']}
                graph=StateGraph(State)
                for agent in ('business_analyst','marketing_analyst','product_manager','reviewer'):
                    async def step(state,agent=agent):return await agent_step(state,agent)
                    graph.add_node(agent,step)
                graph.add_edge(START,'business_analyst');graph.add_edge('business_analyst','marketing_analyst');graph.add_edge('marketing_analyst','product_manager');graph.add_edge('product_manager','reviewer')
                graph.add_conditional_edges('reviewer',lambda state:'revise' if state['issues'] and state['round']<body.max_rounds else 'finish',{'revise':'product_manager','finish':END})
                with tracing_context(enabled=False):
                    result=await graph.compile().ainvoke({'outputs':{},'round':0,'issues':[]},{'recursion_limit':16})
                output='\n\n'.join('### '+agent.replace('_',' ').title()+'\n'+result['outputs'][agent]['text'] for agent in result['outputs'])
                cp['events'].append({'stage':'approval','detail':'Specialists finished; human review required before saving a decision'})
                checkpoint(state='WAITING_FOR_APPROVAL',output=output,discussion_result=result,report=report,elapsed_seconds=run.get('elapsed_seconds',0)+time.monotonic()-started)
                s['finish_message'](owner,conversation['id'],id,output)
        except asyncio.CancelledError:
            if s['stopping']():checkpoint(state='CREATED',worker=None,lease_until=None,elapsed_seconds=run.get('elapsed_seconds',0)+time.monotonic()-started)
            else:s['change_execution'](owner,id,{'state':'CANCELLED'})
            raise
        except Exception as error:
            reason='Discussion stopped by policy, unavailable evidence, provider validation or execution budget'
            if isinstance(error,ValueError) and str(error) in ('Tool budget exhausted','Output token budget exhausted'):reason=str(error)
            s['change_execution'](owner,id,{'state':'FAILED','error':reason,'discussion_checkpoint':cp,'events':cp['events']})
            s['finish_message'](owner,run['conversation'],id,reason)
        finally:
            heartbeat.cancel();await asyncio.gather(heartbeat,return_exceptions=True)
            if actor_token:ACTOR.reset(actor_token)
            WORKER.reset(worker);s['JOBS'].pop(id,None)

def install(app,auth,harness):
    s=harness.s
    @app.get('/api/discussions')
    def listing(owner=Depends(auth)):return [row for row in s['listing'](owner,'execution') if row.get('engine')=='langgraph_discussion']
    @app.post('/api/discussions',status_code=202)
    async def start(body:DiscussInput,owner=Depends(auth)):
        conversation=s['get'](owner,body.conversation_id,'conversation');s['POLICY'].require(owner,'write');reject_secrets(body.goal)
        if body.growth_report_id and s['get'](owner,body.growth_report_id,'growth_report')['conversation']!=body.conversation_id:raise HTTPException(422,'Growth report must belong to this conversation')
        for agent in ('business_analyst','marketing_analyst','product_manager','reviewer'):
            with model_scope(owner,agent):s['POLICY'].data(owner,conversation,effective_mode(body.mode))
        for call in body.context_tools:
            spec=s['TOOL_PLUGINS'].validate(owner,call.name,call.arguments)
            if spec['adapter']=='mcp' and s['TOOL_PLUGINS'].mcp.server(owner,spec['server_id'])['transport']=='streamable_http':s['POLICY'].data(owner,conversation,'mcp')
            if spec['risk']!='read':raise HTTPException(422,'Only read-only evidence tools are supported')
        id=str(uuid4());data={'engine':'langgraph_discussion','state':'CREATED','question':body.goal,'mode':body.mode,'conversation':body.conversation_id,'actor':s['POLICY'].principal(owner).account,'events':[],'discussion_input':body.model_dump(),'output':'','graph':{'nodes':['business_analyst','marketing_analyst','product_manager','reviewer'],'edges':[['business_analyst','marketing_analyst'],['marketing_analyst','product_manager'],['product_manager','reviewer'],['reviewer','product_manager']],'max_rounds':body.max_rounds}}
        with s['conn']() as c:
            c.execute("SELECT pg_advisory_xact_lock(hashtext('evolvyn_discussion_capacity'))")
            count=c.execute("SELECT count(*) AS count FROM records WHERE kind='execution' AND body->>'state' IN ('CREATED','RUNNING')").fetchone()['count']
            if count>=8:raise HTTPException(429,'Execution capacity is full')
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='conversation' FOR UPDATE",(owner,body.conversation_id)).fetchone()
            conv=row['body'];conv['messages'] += [{'role':'user','text':body.goal},{'role':'assistant','text':'Specialists are reviewing your evidence…','execution':id}]
            c.execute("INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,'execution',%s)",(id,owner,json.dumps(data)))
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(conv),owner,body.conversation_id))
        s['JOBS'][id]=asyncio.create_task(harness.run(owner,id))
        return {'id':id,**data}
    @app.post('/api/discussions/{id}/decision')
    def decide(id:str,body:Decision,owner=Depends(auth)):
        s['POLICY'].require(owner,'approve');run=s['get'](owner,id,'execution');reject_secrets(body.plan)
        with s['conn']() as c:
            locked=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='execution' FOR UPDATE",(owner,id)).fetchone();data=locked['body']
            if data.get('engine')!='langgraph_discussion' or data['state']!='WAITING_FOR_APPROVAL':raise HTTPException(409,'Discussion is not awaiting a decision')
            if body.approve and data['discussion_result']['issues'] and not body.acknowledge_issues:raise HTTPException(409,'Review unresolved guardrail issues and explicitly acknowledge them')
            data.update(state='COMPLETED' if body.approve else 'CANCELLED',decision={'approved':body.approve,'plan':body.plan,'acknowledged_issues':body.acknowledge_issues,'actor':s['POLICY'].principal(owner).account})
            if body.approve:
                from datetime import datetime,timezone,timedelta
                conversation=s['get'](owner,run['conversation'],'conversation');memory_id=str(uuid5(NAMESPACE_URL,'discussion-decision:'+owner+':'+id))
                memory={'project_id':conversation.get('project_id'),'conversation':conversation['id'],'text':body.plan,'category':'decision','agent':'shared','state':'ACCEPTED','origin':'reviewed_discussion','source_ids':[id],'provenance':'Human-reviewed decision; not an independently verified market fact','created_at':datetime.now(timezone.utc).isoformat(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=90)).isoformat()}
                c.execute("INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,'agent_memory',%s)",(memory_id,owner,json.dumps(memory)))
                data['memory_id']=memory_id
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(data),owner,id))
        return {'id':id,**data}
