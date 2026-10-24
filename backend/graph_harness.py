"""Bounded declarative agent graphs with durable node checkpoints and argument-bound approvals."""
import asyncio
import hashlib
import json
import re
from datetime import datetime,timezone
from typing import Literal
from uuid import uuid4
from fastapi import Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,model_validator
from backend.registry import ToolContext
from backend.tool_plugins import fingerprint,digest
from backend.policy import ACTOR,Principal
from backend.model_access import model_scope,effective_mode
from backend.execution_queue import WORKER

class Retry(BaseModel):
    model_config=ConfigDict(extra='forbid')
    attempts:int=Field(default=1,ge=1,le=4)
    backoff_seconds:float=Field(default=.2,ge=0,le=3)
class Condition(BaseModel):
    path:str=Field(max_length=300)
    op:Literal['exists','eq','gt','gte','lt','lte','contains']='exists'
    value:object=None
class Node(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
    type:Literal['tool','agent','condition','approval','result']
    agent_id:str=Field(default='supervisor',pattern=r'^[a-z][a-z0-9_]{2,59}$')
    max_visits:int=Field(default=10,ge=1,le=100)
    tool:str|None=None
    arguments:dict=Field(default_factory=dict)
    prompt:str=Field(default='',max_length=2000)
    mode:Literal['default','evidence','local','provider','groq','gemini','openrouter']='evidence'
    condition:Condition|None=None
    retry:Retry=Field(default_factory=Retry)
    timeout_seconds:int=Field(default=30,ge=1,le=120)
class Edge(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source:str
    target:str
    when:Literal['always','true','false','approved','rejected']='always'
class Definition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=100)
    goal:str=Field(min_length=3,max_length=2000)
    entry:str
    nodes:list[Node]=Field(min_length=1,max_length=32)
    edges:list[Edge]=Field(default_factory=list,max_length=64)
    max_steps:int=Field(default=32,ge=1,le=100)
    max_tool_calls:int=Field(default=16,ge=1,le=64)
    max_output_tokens:int=Field(default=2048,ge=128,le=8192)
    max_seconds:int=Field(default=180,ge=5,le=600)
    @model_validator(mode='after')
    def graph(self):
        ids={n.id for n in self.nodes}
        if len(ids)!=len(self.nodes) or self.entry not in ids:raise ValueError('Node IDs must be unique and entry must exist')
        if any(e.source not in ids or e.target not in ids for e in self.edges):raise ValueError('Edge references an unknown node')
        if any(n.type=='tool' and not n.tool for n in self.nodes):raise ValueError('Tool nodes require a registered tool name')
        if any(n.type=='condition' and not n.condition for n in self.nodes):raise ValueError('Condition nodes require a predicate')
        reached={self.entry}
        for _ in self.nodes:
            reached.update(e.target for e in self.edges if e.source in reached)
        if reached!=ids:raise ValueError('Every node must be reachable')
        return self
class PlanInput(BaseModel):
    goal:str=Field(min_length=3,max_length=2000)
    conversation_id:str
    mode:Literal['default','evidence','local','provider','groq','gemini','openrouter']='evidence'
class Start(BaseModel):
    conversation_id:str
class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    approve:bool
    binding:str


def path_value(state,path):
    if not re.fullmatch(r'nodes(?:\.[A-Za-z0-9_]+){1,20}',path):raise ValueError('References must point to bounded node outputs')
    value=state
    for part in path.split('.'):
        value=value[int(part)] if isinstance(value,list) and part.isdigit() else value[part]
    return value

def resolve(value,state,depth=0):
    if depth>12:raise ValueError('Argument nesting limit exceeded')
    if isinstance(value,dict):
        if set(value)=={'$ref'}:return path_value(state,value['$ref'])
        return {key:resolve(item,state,depth+1) for key,item in value.items()}
    if isinstance(value,list):return [resolve(item,state,depth+1) for item in value]
    return value

def predicate(condition,state):
    try:value=path_value(state,condition.path)
    except (KeyError,IndexError):return False if condition.op=='exists' else (_ for _ in ()).throw(ValueError('Condition input is missing'))
    other=condition.value
    if condition.op=='exists':return value is not None
    if condition.op=='eq':return value==other
    if condition.op=='contains':return other in value
    return {'gt':lambda:value>other,'gte':lambda:value>=other,'lt':lambda:value<other,'lte':lambda:value<=other}[condition.op]()

def cycle_nodes(definition):
    adjacency={n.id:[] for n in definition.nodes}
    for edge in definition.edges:adjacency[edge.source].append(edge.target)
    result=set()
    for start in adjacency:
        pending=list(adjacency[start]);visited=set()
        while pending:
            current=pending.pop()
            if current==start:result.add(start);break
            if current not in visited:visited.add(current);pending.extend(adjacency[current])
    return result

def propagate_skips(definition,cp,cyclic):
    cp.setdefault('skipped',[]);cp.setdefault('active_edges',[])
    for _ in definition.nodes:
        changed=False;closed=set(cp['nodes'])|set(cp['skipped'])
        for node in definition.nodes:
            if node.id==definition.entry or node.id in cyclic or node.id in closed or node.id in cp['queue'] or (cp['current'] and cp['current']['id']==node.id):continue
            incoming=[(i,e) for i,e in enumerate(definition.edges) if e.target==node.id]
            if incoming and all(e.source in closed for _,e in incoming) and not any(i in cp['active_edges'] for i,_ in incoming):
                cp['skipped'].append(node.id);changed=True
        if not changed:break

def next_ready(definition,cp,cyclic):
    propagate_skips(definition,cp,cyclic)
    closed=set(cp['nodes'])|set(cp['skipped'])
    for _ in range(len(cp['queue'])):
        target=cp['queue'].pop(0)
        if target in closed and target not in cyclic:continue
        parents=[e.source for e in definition.edges if e.target==target]
        if target==definition.entry or target in cyclic or all(parent in closed for parent in parents):return target
        cp['queue'].append(target)
    raise ValueError('No runnable node: graph dependencies could not be resolved')

class GraphHarness:
    def __init__(self,services):self.s=services
    def event(self,checkpoint,node,detail,**extra):
        checkpoint['events'].append({'stage':node,'detail':detail,'at':datetime.now(timezone.utc).isoformat(),**extra})
        checkpoint['events']=checkpoint['events'][-200:]
    def checkpoint(self,owner,id,checkpoint_data,**updates):
        if len(json.dumps(checkpoint_data))>600_000:raise ValueError('Checkpoint state budget exceeded')
        result=self.s['change_execution'](owner,id,{'graph_checkpoint':checkpoint_data,'events':checkpoint_data['events'],**updates})
        if not result:raise asyncio.CancelledError()
    async def run(self,owner,id):
        s=self.s;run=s['claim_job'](s['conn'],owner,id)
        if not run:s['JOBS'].pop(id,None);return
        worker=WORKER.set(run['worker']);actor_token=None
        actor=run.get('actor')
        if actor:
            with s['conn']() as c:member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(actor,owner)).fetchone()
            if not member:
                s['change_execution'](owner,id,{'state':'FAILED','error':'The requesting account no longer has organization access'})
                WORKER.reset(worker);s['JOBS'].pop(id,None);return
            actor_token=ACTOR.set(Principal(owner,actor,member['role']))
        heartbeat=asyncio.create_task(s['renew_lease'](owner,id))
        definition=Definition.model_validate(run['definition']);nodes={n.id:n for n in definition.nodes};cyclic=cycle_nodes(definition)
        cp=run.get('graph_checkpoint') or {'queue':[definition.entry],'nodes':{},'steps':0,'tools_used':0,'tokens_reserved':0,'visits':{},'events':[],'current':None,'grant':None}
        settings=s['POLICY'].settings(owner)
        remaining_seconds=min(definition.max_seconds,settings['max_run_seconds'])-run.get('elapsed_seconds',0)
        import time
        started=time.monotonic()
        try:
            conversation=s['get'](owner,run['conversation'],'conversation')
            if remaining_seconds<=0:raise TimeoutError()
            async with asyncio.timeout(remaining_seconds):
                while cp['current'] or cp['queue']:
                    if not cp['current']:
                        if cp['steps']>=definition.max_steps:raise ValueError('Graph step/iteration budget exhausted')
                        node_id=next_ready(definition,cp,cyclic);cp['steps']+=1
                        cp['visits'][node_id]=cp['visits'].get(node_id,0)+1
                        if cp['visits'][node_id]>nodes[node_id].max_visits:raise ValueError('Graph step/iteration budget exhausted for this node')
                        cp['current']={'id':node_id,'visit':cp['visits'][node_id],'status':'pending'}
                    current=cp['current'];node=nodes[current['id']];outcome='always';arguments=resolve(node.arguments,cp)
                    self.event(cp,node.id,'Running '+node.type+' node',node_type=node.type)
                    self.checkpoint(owner,id,cp)
                    if node.type=='tool':
                        if s.get('AGENTS'):
                            role=s['AGENTS'].definition(owner,node.agent_id)
                            if not role.get('unrestricted_tools') and node.tool not in role['allowed_tools']:raise HTTPException(403,'Tool is outside this agent capability set')
                        spec=s['TOOL_PLUGINS'].validate(owner,node.tool,arguments)
                        if current['status']=='executing' and spec['risk']!='read' and not spec['idempotent']:
                            raise ValueError('Interrupted non-idempotent tool outcome is uncertain; reconcile before retrying')
                        binding=digest(node.tool,arguments,fingerprint(spec))+':'+str(cp['steps'])
                        approved=cp.get('grant')==binding
                        if spec['risk']!='read' and not approved:
                            cp['pending']={'node':node.id,'tool':node.tool,'arguments':arguments,'risk':spec['risk'],'binding':binding,'kind':'tool'}
                            self.event(cp,node.id,'Waiting for human approval of these exact arguments',risk=spec['risk'])
                            self.checkpoint(owner,id,cp,state='WAITING_FOR_APPROVAL',elapsed_seconds=run.get('elapsed_seconds',0)+time.monotonic()-started)
                            return
                        cp['grant']=None;current['status']='executing'
                        self.checkpoint(owner,id,cp)
                        context=ToolContext(owner,permissions=frozenset({'workspace.read','workspace.write'}),remaining=min(definition.max_tool_calls,settings['max_tool_calls'])-cp['tools_used'],approved=approved,idempotency_key=id+':'+node.id+':'+str(current['visit']))
                        last_error=None;output=None
                        for attempt in range(node.retry.attempts):
                            if context.remaining<=0:raise ValueError('Tool budget exhausted')
                            cp['tools_used']+=1
                            self.checkpoint(owner,id,cp)
                            try:
                                async with asyncio.timeout(node.timeout_seconds):output=await s['TOOL_PLUGINS'].invoke(owner,node.tool,arguments,context,approved)
                                last_error=None;break
                            except Exception as error:
                                if not retryable(error):raise
                                last_error=error
                                if spec['risk']!='read' and not spec['idempotent']:raise
                                if attempt+1<node.retry.attempts:
                                    self.event(cp,node.id,'Transient tool failure; bounded retry',attempt=attempt+1)
                                    await asyncio.sleep(node.retry.backoff_seconds*2**attempt)

                        if last_error:raise last_error
                        cp['events'].extend(context.trace)
                    elif node.type=='agent':
                        with model_scope(owner,node.agent_id):
                            selected_mode=effective_mode(node.mode)
                            s['POLICY'].data(owner,conversation,selected_mode)
                            reserve=0 if selected_mode=='evidence' else min(512 if selected_mode=='local' else 700,definition.max_output_tokens-cp['tokens_reserved'])
                            if selected_mode!='evidence' and reserve<1:raise ValueError('Model output-token budget exhausted')
                            report=arguments.get('report')
                            if not isinstance(report,dict) or 'facts' not in report or 'evidence' not in report:
                                report={'facts':[],'evidence':[{'source':'Prior authorized tool output','citation':'workflow node outputs','excerpt':json.dumps(arguments)[:5000]}]}
                            report=dict(report,_output_limit=reserve or 512)
                            if s.get('MEMORY'):
                                recalled=s['MEMORY'].recall(owner,node.prompt or definition.goal,conversation.get('project_id'),node.agent_id,4)
                                report['evidence']=list(report['evidence'])+[{'source':'Reviewed memory','citation':'memory:'+m['id'],'excerpt':m['text']} for m in recalled]
                            text=''
                            for attempt in range(node.retry.attempts):
                                if cp['tokens_reserved']+reserve>definition.max_output_tokens:raise ValueError('Model output-token budget exhausted')
                                cp['tokens_reserved']+=reserve;self.checkpoint(owner,id,cp,output='')
                                text=''
                                try:
                                    async with asyncio.timeout(node.timeout_seconds):
                                        async for chunk in s['response_chunks'](report,((s['AGENTS'].definition(owner,node.agent_id)['goal']+'\n') if s.get('AGENTS') else '')+(node.prompt or definition.goal),[],node.mode):
                                            text+=chunk;self.checkpoint(owner,id,cp,output=text)
                                    break
                                except Exception as error:
                                    if not retryable(error) or attempt+1>=node.retry.attempts:raise
                                    self.event(cp,node.id,'Transient model failure; retrying within the same provider and budget',attempt=attempt+1)
                                    await asyncio.sleep(node.retry.backoff_seconds*2**attempt)
                            output={'text':text,'usage':report.get('usage'),'token_budget_reserved':reserve}
                    elif node.type=='condition':output=predicate(node.condition,cp);outcome='true' if output else 'false'
                    elif node.type=='approval':
                        binding=fingerprint({'node':node.id,'arguments':arguments,'step':cp['steps'],'execution':id})
                        if cp.get('grant') not in (binding,'rejected:'+binding):
                            cp['pending']={'node':node.id,'kind':'checkpoint','binding':binding,'arguments':arguments,'risk':'review'}
                            self.checkpoint(owner,id,cp,state='WAITING_FOR_APPROVAL',elapsed_seconds=run.get('elapsed_seconds',0)+time.monotonic()-started);return
                        output=cp['grant']==binding;outcome='approved' if output else 'rejected';cp['grant']=None
                    else:output=arguments.get('value',arguments)
                    cp['nodes'][node.id]={'output':output,'status':'COMPLETED','visit':current['visit']}
                    self.event(cp,node.id,'Node completed')
                    cp.pop('pending',None);cp['current']=None
                    for edge_index,edge in enumerate(definition.edges):
                        if edge.source==node.id and edge.when in ('always',outcome):
                            cp.setdefault('active_edges',[])
                            if edge_index not in cp['active_edges']:cp['active_edges'].append(edge_index)
                            if edge.target not in cp['queue'] and (edge.target in cyclic or edge.target not in cp['nodes']):cp['queue'].append(edge.target)
                    propagate_skips(definition,cp,cyclic)
                    self.checkpoint(owner,id,cp)
                text=next((entry['output']['text'] for entry in reversed(list(cp['nodes'].values())) if isinstance(entry['output'],dict) and entry['output'].get('text')),json.dumps(list(cp['nodes'].values())[-1]['output'],indent=2))
                self.event(cp,'completed','Graph completed within its execution and tool budgets')
                self.checkpoint(owner,id,cp,state='COMPLETED',output=text,elapsed_seconds=run.get('elapsed_seconds',0)+time.monotonic()-started)
                s['finish_message'](owner,run['conversation'],id,text)
        except asyncio.CancelledError:
            if s['stopping']():self.checkpoint(owner,id,cp,state='CREATED',worker=None,lease_until=None,elapsed_seconds=run.get('elapsed_seconds',0)+time.monotonic()-started)
            else:s['change_execution'](owner,id,{'state':'CANCELLED'})
            raise
        except Exception as error:
            # Policy and budget reasons are safe; raw remote/provider errors are never exposed.
            reason=('Policy denied this execution' if isinstance(error,HTTPException) else 'Node input/output validation or execution failed; inspect configuration and source availability')
            safe_prefixes=('Graph step/iteration budget','Model output-token budget','Tool budget','Checkpoint state budget','Interrupted non-idempotent tool outcome','No runnable node','References must point','Argument nesting limit','Condition input is missing')
            if isinstance(error,ValueError) and str(error).startswith(safe_prefixes):reason=str(error)
            if isinstance(error,TimeoutError):reason='Execution or node time budget exceeded'
            self.event(cp,'failed',reason[:300])
            s['change_execution'](owner,id,{'state':'FAILED','error':reason[:300] or 'Execution time budget exceeded','graph_checkpoint':cp,'events':cp['events']})
            s['finish_message'](owner,run['conversation'],id,'Workflow failed: '+(reason[:300] or 'Time budget exceeded'))
        finally:
            heartbeat.cancel();await asyncio.gather(heartbeat,return_exceptions=True)
            if actor_token:ACTOR.reset(actor_token)
            WORKER.reset(worker);s['JOBS'].pop(id,None)


def retryable(error,depth=0):
    import httpx
    if depth>4:return False
    if isinstance(error,BaseExceptionGroup):return bool(error.exceptions) and all(retryable(e,depth+1) for e in error.exceptions)
    if isinstance(error,(httpx.TransportError,TimeoutError)):return True
    return isinstance(error,httpx.HTTPStatusError) and error.response.status_code in (429,500,502,503,504)


def install(app,auth,harness):
    s=harness.s
    @app.post('/api/harness/plan')
    def plan(body:PlanInput,owner=Depends(auth)):
        s['get'](owner,body.conversation_id,'conversation')
        tool='investigate_operations' if any(word in body.goal.lower() for word in ('incident','logs','outage')) else 'analyze_business'
        definition={'name':body.goal[:80],'goal':body.goal,'entry':'evidence','nodes':[
            {'id':'evidence','type':'tool','agent_id':'business_analyst','tool':tool,'arguments':{'conversation_id':body.conversation_id,'query':body.goal},'retry':{'attempts':2,'backoff_seconds':.2}},
            {'id':'explain','type':'agent','agent_id':'product_manager','mode':body.mode,'prompt':body.goal,'arguments':{'report':{'$ref':'nodes.evidence.output'}},'timeout_seconds':90 if body.mode=='local' else 30},
            {'id':'record','type':'tool','agent_id':'product_manager','tool':'create_internal_note','arguments':{'conversation_id':body.conversation_id,'text':{'$ref':'nodes.explain.output.text'}}},
            {'id':'result','type':'result','arguments':{'value':{'$ref':'nodes.record.output'}}}
        ],'edges':[{'source':'evidence','target':'explain'},{'source':'explain','target':'record'},{'source':'record','target':'result'}]}
        return {'definition':Definition.model_validate(definition).model_dump(),'subgoals':[{'node':n['id'],'type':n['type'],'purpose':{'evidence':'Retrieve authorized evidence and calculate facts','explain':'Explain findings with the selected agent','record':'Request approval and save the resulting project note','result':'Return the executed result'}[n['id']]} for n in definition['nodes']]}
    @app.get('/api/harness/graphs')
    def graphs(owner=Depends(auth)):return s['listing'](owner,'agent_graph')
    @app.post('/api/harness/graphs')
    def save_graph(body:Definition,owner=Depends(auth)):
        s['POLICY'].require(owner,'write')
        for node in body.nodes:
            if node.type=='tool':s['TOOL_PLUGINS'].spec(owner,node.tool)
        return s['save'](owner,'agent_graph',body.model_dump())
    @app.put('/api/harness/graphs/{id}')
    def update_graph(id:str,body:Definition,owner=Depends(auth)):
        s['get'](owner,id,'agent_graph')
        for node in body.nodes:
            if node.type=='tool':s['TOOL_PLUGINS'].spec(owner,node.tool)
        return s['save'](owner,'agent_graph',body.model_dump(),id)
    @app.post('/api/harness/graphs/{id}/run',status_code=202)
    async def start(id:str,body:Start,owner=Depends(auth)):
        graph=s['get'](owner,id,'agent_graph');conversation=s['get'](owner,body.conversation_id,'conversation')
        definition=Definition.model_validate({k:v for k,v in graph.items() if k!='id'})
        for node in definition.nodes:
            if node.type=='agent':s['POLICY'].data(owner,conversation,node.mode)
        principal=s['POLICY'].require(owner,'write');execution_id=str(uuid4())
        record={'engine':'graph','conversation':body.conversation_id,'definition':definition.model_dump(),'graph_id':id,'question':definition.goal,'state':'CREATED','events':[],'output':'','report':None,'actor':principal.account}
        with s['conn']() as c:
            row=c.execute("SELECT body FROM records WHERE id=%s AND owner=%s FOR UPDATE",(body.conversation_id,owner)).fetchone()
            if c.execute("SELECT id FROM records WHERE owner=%s AND kind='execution' AND body->>'conversation'=%s AND body->>'state' IN ('CREATED','RUNNING')",(owner,body.conversation_id)).fetchone():raise HTTPException(409,'Conversation already has an active execution')
            c.execute('INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,%s,%s)',(execution_id,owner,'execution',json.dumps(record)))
            conv=row['body'];conv['messages'] += [{'role':'user','text':definition.goal},{'role':'assistant','text':'Agent graph is running…','execution':execution_id}]
            c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(conv),body.conversation_id))
        s['JOBS'][execution_id]=asyncio.create_task(harness.run(owner,execution_id))
        return {'id':execution_id,**record}
    @app.get('/api/harness/executions')
    def executions(owner=Depends(auth)):return [r for r in s['listing'](owner,'execution') if r.get('engine')=='graph']
    @app.post('/api/harness/executions/{id}/decision')
    async def decision(id:str,body:Decision,owner=Depends(auth)):
        s['POLICY'].require(owner,'approve');s['get'](owner,id,'execution')
        with s['conn']() as c:
            row=c.execute("SELECT body FROM records WHERE id=%s AND owner=%s FOR UPDATE",(id,owner)).fetchone();run=row['body']
            pending=run.get('graph_checkpoint',{}).get('pending')
            if run.get('engine')!='graph' or run['state']!='WAITING_FOR_APPROVAL' or not pending:raise HTTPException(409,'Graph is not awaiting approval')
            if body.binding!=pending['binding']:raise HTTPException(409,'Approval is stale or does not bind to these arguments')
            if pending['kind']=='tool':
                spec=s['TOOL_PLUGINS'].spec(owner,pending['tool'])
                if digest(pending['tool'],pending['arguments'],fingerprint(spec))+':'+str(run['graph_checkpoint']['steps'])!=body.binding:raise HTTPException(409,'Tool configuration changed; restart this graph')
                if not body.approve:
                    run.update(state='CANCELLED');run['events'].append({'stage':'rejected','detail':'Human rejected the pending action'})
                else:run['graph_checkpoint']['grant']=body.binding;run.update(state='CREATED',worker=None,lease_until=None,attempt=0)
            else:
                run['graph_checkpoint']['grant']=body.binding if body.approve else 'rejected:'+body.binding
                run.update(state='CREATED',worker=None,lease_until=None,attempt=0)
            c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(run),id))
        if run['state']=='CREATED':s['JOBS'][id]=asyncio.create_task(harness.run(owner,id))
        else:s['finish_message'](owner,run['conversation'],id,'Workflow cancelled after human rejection.')
        return {'id':id,**run}
