import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from backend import app as module
from backend.registry import Tool

@pytest.fixture
def client():
    with TestClient(module.app) as c:
        c.headers['Authorization']='Bearer '+module.TOKEN
        yield c

def conversation(c):
    row=c.post('/api/conversations',json={'title':'Graph acceptance'}).json()
    c.post('/api/conversations/'+row['id']+'/files',files={'file':('funnel.csv',Path('sample-data/funnel.csv').read_bytes())})
    return row

def run(c,conv,definition):
    response=c.post('/api/harness/graphs',json=definition);assert response.status_code==200,response.text
    response=c.post('/api/harness/graphs/'+response.json()['id']+'/run',json={'conversation_id':conv['id']});assert response.status_code==202,response.text
    id=response.json()['id'];c.get('/api/executions/'+id+'/live')
    return c.get('/api/executions/'+id).json()

def test_goal_decomposition_graph_executes_and_requires_bound_approval(client):
    conv=conversation(client)
    plan=client.post('/api/harness/plan',json={'goal':'Analyze business conversion and save a reviewed note','conversation_id':conv['id'],'mode':'evidence'}).json()
    assert len(plan['subgoals'])==4
    pending=run(client,conv,plan['definition'])
    assert pending['state']=='WAITING_FOR_APPROVAL',pending
    binding=pending['graph_checkpoint']['pending']['binding']
    assert client.post('/api/harness/executions/'+pending['id']+'/decision',json={'approve':True,'binding':'tampered'}).status_code==409
    assert client.post('/api/executions/'+pending['id']+'/decision',json={'approve':True,'plan':'Bypass'}).status_code==409
    approved=client.post('/api/harness/executions/'+pending['id']+'/decision',json={'approve':True,'binding':binding})
    assert approved.status_code==200,approved.text
    client.get('/api/executions/'+pending['id']+'/live')
    result=client.get('/api/executions/'+pending['id']).json()
    assert result['state']=='COMPLETED',result
    assert set(result['graph_checkpoint']['nodes'])=={'evidence','explain','record','result'}
    assert module.listing('initial-workspace','project_note')
    assert client.post('/api/harness/executions/'+pending['id']+'/decision',json={'approve':True,'binding':binding}).status_code==409

def test_graph_condition_routes_and_joins_once(client):
    conv=conversation(client)
    definition={'name':'Fork and join','goal':'Combine authorized results','entry':'start','nodes':[
        {'id':'start','type':'result','arguments':{'value':5}},
        {'id':'left','type':'result','arguments':{'value':'left'}},
        {'id':'right','type':'result','arguments':{'value':'right'}},
        {'id':'middle','type':'result','arguments':{'value':'middle'}},
        {'id':'join','type':'result','arguments':{'value':{'left':{'$ref':'nodes.left.output'},'right':{'$ref':'nodes.middle.output'}}}}],
        'edges':[{'source':'start','target':'left'},{'source':'start','target':'right'},{'source':'left','target':'join'},{'source':'right','target':'middle'},{'source':'middle','target':'join'}]}
    result=run(client,conv,definition)
    assert result['state']=='COMPLETED',result
    assert result['graph_checkpoint']['visits']['join']==1
    assert result['graph_checkpoint']['nodes']['join']['output']=={'left':'left','right':'middle'}

def test_graph_conditional_branch_skips_unselected_path(client):
    conv=conversation(client)
    definition={'name':'Condition','goal':'Only choose matching branch','entry':'start','nodes':[
      {'id':'start','type':'result','arguments':{'value':8}},
      {'id':'choose','type':'condition','condition':{'path':'nodes.start.output','op':'gt','value':5}},
      {'id':'yes','type':'result','arguments':{'value':'matched'}},
      {'id':'no','type':'result','arguments':{'value':'must not run'}},
      {'id':'join','type':'result','arguments':{'value':'done'}}],
      'edges':[{'source':'start','target':'choose'},{'source':'choose','target':'yes','when':'true'},{'source':'choose','target':'no','when':'false'},{'source':'yes','target':'join'},{'source':'no','target':'join'}]}
    result=run(client,conv,definition)
    assert result['state']=='COMPLETED',result
    assert 'no' not in result['graph_checkpoint']['nodes']
    assert result['graph_checkpoint']['nodes']['yes']['output']=='matched'

def test_graph_cycles_fail_at_explicit_iteration_limit(client):
    conv=conversation(client)
    definition={'name':'Bounded loop','goal':'Prove termination','entry':'loop','max_steps':3,'nodes':[{'id':'loop','type':'result','arguments':{'value':'bounded'}}],'edges':[{'source':'loop','target':'loop'}]}
    result=run(client,conv,definition)
    assert result['state']=='FAILED' and 'budget exhausted' in result['error']
    assert result['graph_checkpoint']['steps']==3

def test_transient_tool_retries_are_bounded_and_recorded(client,monkeypatch):
    class Input(BaseModel):value:int
    class Output(BaseModel):value:int
    attempts=[]
    async def flaky(args,context):
        attempts.append(1)
        if len(attempts)<3:raise httpx.ConnectError('redacted transport failure')
        return {'value':args.value}
    tool=Tool('temporary_flaky','Read for retry validation',Input,Output,flaky)
    module.REGISTRY.register(tool)
    try:
        conv=conversation(client)
        definition={'name':'Retry','goal':'Recover a transient read','entry':'read','nodes':[{'id':'read','type':'tool','tool':'temporary_flaky','arguments':{'value':7},'retry':{'attempts':3,'backoff_seconds':0}}],'edges':[]}
        result=run(client,conv,definition)
        assert result['state']=='COMPLETED',result
        assert len(attempts)==3 and result['graph_checkpoint']['tools_used']==3
    finally:module.REGISTRY.tools.pop('temporary_flaky')

def test_graph_tool_budget_prevents_extra_calls(client):
    conv=conversation(client)
    definition={'name':'Budget','goal':'Respect total calls','entry':'first','max_tool_calls':1,'nodes':[
      {'id':'first','type':'tool','tool':'analyze_business','arguments':{'conversation_id':conv['id'],'query':'conversion'}},
      {'id':'second','type':'tool','tool':'analyze_business','arguments':{'conversation_id':conv['id'],'query':'conversion'}}],
      'edges':[{'source':'first','target':'second'}]}
    result=run(client,conv,definition)
    assert result['state']=='FAILED' and 'budget' in result['error'].lower()
    assert result['graph_checkpoint']['tools_used']==1

def test_graph_reserves_tokens_before_each_agent_node(client,monkeypatch):
    calls=[]
    async def generate(report,question,history,mode):
        calls.append(report['_output_limit'])
        yield 'A bounded finding'
    monkeypatch.setitem(module.GRAPH_HARNESS.s,'response_chunks',generate)
    conv=conversation(client)
    definition={'name':'Model budget','goal':'Bound model generation','entry':'first','max_output_tokens':128,'nodes':[
        {'id':'first','type':'agent','mode':'local'}, {'id':'second','type':'agent','mode':'local'}],
        'edges':[{'source':'first','target':'second'}]}
    result=run(client,conv,definition)
    assert result['state']=='FAILED' and 'output-token budget' in result['error']
    assert calls==[128] and result['graph_checkpoint']['tokens_reserved']==128
