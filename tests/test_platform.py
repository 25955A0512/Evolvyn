import asyncio
import io
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from docx import Document
from pydantic import BaseModel
from backend import app as module
from backend.file_parser import extract
from backend.mcp_gateway import invoke_rank
from backend.registry import ToolRegistry,ToolContext,Tool,ToolDenied

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    with TestClient(module.app) as c:
        c.headers['Authorization']='Bearer '+module.TOKEN
        yield c

def prepare(c):
    business=c.post('/api/businesses',json={'name':'Platform acceptance','goal':'Improve activation'}).json()
    project=c.post('/api/projects',json={'name':'Conversion improvement','goal':'Validate the funnel','business_id':business['id'],'data_policy':'allow_selected_provider'}).json()
    conversation=c.post('/api/conversations',json={'title':'Platform acceptance run','business_id':business['id'],'project_id':project['id']}).json()
    for name in ['funnel.csv','customer-feedback.txt']:
        response=c.post('/api/conversations/'+conversation['id']+'/files',files={'file':(name,Path('sample-data/'+name).read_bytes())});assert response.status_code==200
    return conversation

def completed_analysis(c,conversation):
    response=c.post('/api/conversations/'+conversation['id']+'/runs',json={'text':'Analyze conversion and onboarding friction','mode':'evidence'})
    assert response.status_code==202;id=response.json()['id']
    c.get('/api/executions/'+id+'/live')
    result=c.get('/api/executions/'+id).json()
    assert result['state']=='WAITING_FOR_APPROVAL',result
    return result

def test_full_evidence_recommendation_action_measurement_journey(client):
    c=prepare(client);run=completed_analysis(client,c)
    report=run['report']
    assert len(report['recommendations'])==3
    assert 'MCP stdio' in report['strategy_engine']
    assert any(t['id']=='onboarding' for t in report['themes'])
    assert any('onboarding' in r['title'].lower() for r in report['recommendations'])
    assert report['recommendations'][0]['priority_score']>=report['recommendations'][1]['priority_score']
    recommendation=report['recommendations'][1]
    approved=client.post('/api/executions/'+run['id']+'/decision',json={'approve':True,'plan':recommendation['title'],'recommendation_id':recommendation['id']})
    assert approved.status_code==200
    artifact=approved.json()['artifact']
    tasks=client.get('/api/tasks?conversation_id='+c['id']).json()
    assert len(tasks)==len(recommendation['tasks'])
    assert client.patch('/api/tasks/'+tasks[0]['id'],json={'status':'done','notes':'Evidence definitions reviewed'}).json()['status']=='done'
    uploaded=client.post('/api/conversations/'+c['id']+'/files',files={'file':('followup.csv',Path('sample-data/followup.csv').read_bytes())}).json()
    measured=client.post('/api/artifacts/'+artifact+'/measure',json={'document_id':uploaded['id'],'notes':'Synthetic pre/post comparison only'})
    assert measured.status_code==200
    assert measured.json()['change_percentage_points']==1
    assert 'not proof of causation' in measured.json()['classification']
    assert client.get('/api/artifacts/'+artifact+'/measurements').json()[0]['id']==measured.json()['id']
    reopened=client.get('/api/conversations/'+c['id']).json()
    assert reopened['messages'][-1]['report']['recommendations'][1]['id']==recommendation['id']

def test_approval_rejects_forged_recommendation(client):
    c=prepare(client);run=completed_analysis(client,c)
    assert client.post('/api/executions/'+run['id']+'/decision',json={'approve':True,'plan':'Injected action','recommendation_id':'not-in-this-run'}).status_code==422
    assert client.get('/api/executions/'+run['id']).json()['state']=='WAITING_FOR_APPROVAL'
    assert not client.get('/api/tasks?conversation_id='+c['id']).json()

def test_project_scope_and_tool_authorization(client):
    foreign=module.save('other-owner','business',{'name':'Private'})
    assert client.post('/api/projects',json={'name':'Leak','goal':'Leak','business_id':foreign['id']}).status_code==404
    c=prepare(client)
    invalid=client.post('/api/tools/analyze_business/invoke',json={'arguments':{'conversation_id':c['id'],'query':'activation','permissions':['admin']}})
    assert invalid.status_code==422
    assert client.post('/api/tools/deploy_production/invoke',json={'arguments':{}}).status_code==403
    output=client.post('/api/tools/analyze_business/invoke',json={'arguments':{'conversation_id':c['id'],'query':'activation'}})
    assert output.status_code==200 and output.json()['trace']

def test_schedule_runs_persist_and_never_approve(client):
    c=prepare(client)
    schedule=client.post('/api/schedules',json={'conversation_id':c['id'],'query':'Review onboarding evidence','interval_minutes':1}).json()
    response=client.post('/api/schedules/'+schedule['id']+'/run')
    assert response.status_code==200
    id=response.json()['id'];client.get('/api/executions/'+id+'/live')
    assert client.get('/api/executions/'+id).json()['state']=='WAITING_FOR_APPROVAL'
    assert not client.get('/api/tasks?conversation_id='+c['id']).json()
    assert client.patch('/api/schedules/'+schedule['id'],json={'enabled':False}).json()['enabled'] is False
    assert client.get('/api/schedules').json()[0]['last_run']==id

def test_remove_file_checks_scope_and_persists(client):
    first=prepare(client);second=prepare(client)
    doc=client.get('/api/conversations/'+first['id']).json()['files'][0]
    assert client.delete('/api/conversations/'+second['id']+'/files/'+doc['id']).status_code==404
    assert client.delete('/api/conversations/'+first['id']+'/files/'+doc['id']).status_code==200
    assert all(f['id']!=doc['id'] for f in client.get('/api/conversations/'+first['id']).json()['files'])

def test_docx_extraction():
    document=Document();document.add_paragraph('Customers report onboarding friction and slow activation.')
    buffer=io.BytesIO();document.save(buffer)
    assert 'onboarding friction' in extract(buffer.getvalue(),'feedback.docx')

def test_invalid_binary_document_is_rejected(client):
    c=prepare(client)
    assert client.post('/api/conversations/'+c['id']+'/files',files={'file':('broken.pdf',b'not a PDF')}).status_code==422

@pytest.mark.anyio
async def test_real_mcp_handshake_and_ranking():
    result=await invoke_rank([{'id':'a','title':'Validate baseline','impact':5,'confidence':.9,'effort':1},{'id':'b','title':'Expensive experiment','impact':3,'confidence':.3,'effort':5}])
    assert [r['id'] for r in result]==['a','b'] and result[0]['score']==4.5

@pytest.mark.anyio
async def test_registry_checks_permissions_and_budget():
    class Input(BaseModel):value:int
    class Output(BaseModel):value:int
    async def handler(arguments,context):return {'value':arguments.value}
    registry=ToolRegistry();registry.register(Tool('safe','Read',Input,Output,handler))
    with pytest.raises(ToolDenied):await registry.invoke('safe',{'value':1},ToolContext('x',permissions=frozenset()))
    context=ToolContext('x',remaining=1)
    assert await registry.invoke('safe',{'value':1},context)=={'value':1}
    with pytest.raises(ToolDenied):await registry.invoke('safe',{'value':1},context)

@pytest.fixture
def anyio_backend():return 'asyncio'

def test_pdf_text_extraction():
    from pypdf import PdfWriter
    from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 700 Td (Synthetic customer report: onboarding is confusing.) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    buffer=io.BytesIO();writer.write(buffer)
    assert 'onboarding is confusing' in extract(buffer.getvalue(),'report.pdf')

def test_provider_failure_can_explicitly_fall_back(client,monkeypatch):
    import httpx
    real=module.response_chunks
    async def fail_provider(report,question,history,mode='provider'):
        if mode=='provider':raise httpx.ReadTimeout('redacted-upstream')
        async for item in real(report,question,history,mode):yield item
    monkeypatch.setattr(module,'response_chunks',fail_provider)
    c=prepare(client)
    r=client.post('/api/conversations/'+c['id']+'/runs',json={'text':'Analyze the evidence','mode':'provider','allow_fallback':True})
    client.get('/api/executions/'+r.json()['id']+'/live')
    result=client.get('/api/executions/'+r.json()['id']).json()
    assert result['state']=='WAITING_FOR_APPROVAL'
    assert 'unavailable' in result['report']['provider_status']
    assert 'no model was called' in result['output']
    assert len(result['report']['recommendations'])==3
    assert 'redacted-upstream' not in json.dumps(result)

def test_due_schedule_is_claimed_once(client):
    c=prepare(client)
    body={'conversation_id':c['id'],'query':'Review the business evidence','interval_minutes':1,'mode':'evidence','enabled':True,'next_run_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),'last_run':None,'last_error':None}
    record=module.save('initial-workspace','schedule',body)
    # The live TestClient owns the event loop used by the real scheduler and its tasks.
    client.portal.call(module.schedule_tick)
    result=next(s for s in client.get('/api/schedules').json() if s['id']==record['id'])
    assert result['last_run']
    client.get('/api/executions/'+result['last_run']+'/live')
    client.portal.call(module.schedule_tick)
    after=next(s for s in client.get('/api/schedules').json() if s['id']==record['id'])
    assert after['last_run']==result['last_run']
    assert client.get('/api/executions/'+result['last_run']).json()['state']=='WAITING_FOR_APPROVAL'

def test_sample_workspace_isolated_from_private_data_and_credentials(client):
    private=prepare(client)
    response=client.post('/api/demo/session')
    assert response.status_code==200
    session=response.json()
    headers={'Authorization':'Bearer '+session['token']}
    assert client.get('/api/conversations/'+private['id'],headers=headers).status_code==404
    own=client.get('/api/conversations',headers=headers).json()
    assert len(own)==1 and own[0]['id']==session['conversation_id']
    client.get('/api/executions/'+session['execution_id']+'/live',headers=headers)
    final=client.get('/api/executions/'+session['execution_id'],headers=headers).json()
    assert final['state']=='WAITING_FOR_APPROVAL' and len(final['report']['recommendations'])==3
    assert client.post('/api/conversations/'+session['conversation_id']+'/runs',headers=headers,json={'text':'Use the private model key','mode':'provider'}).status_code==403
    assert client.post('/api/providers/test',headers=headers).json()['reason']=='sample_workspace_uses_evidence_mode'
    assert client.get('/api/conversations/'+session['conversation_id']).status_code==404

def test_invalid_priority_arguments_rejected_before_tool_execution(client):
    response=client.post('/api/tools/prioritize_actions/invoke',json={'arguments':{'candidates':[{'id':'x','title':'Exploit','impact':99,'confidence':1,'effort':0}]}})
    assert response.status_code==422

def test_shared_project_knowledge_reopens_without_reupload(client):
    original=prepare(client)
    new=client.post('/api/conversations',json={'title':'Continue project investigation','business_id':original['business_id'],'project_id':original['project_id']}).json()
    response=client.post('/api/conversations/'+new['id']+'/runs',json={'text':'What did customers report about onboarding?','mode':'evidence'})
    assert response.status_code==202
    id=response.json()['id'];client.get('/api/executions/'+id+'/live')
    report=client.get('/api/executions/'+id).json()['report']
    assert report['facts'] and report['evidence']
    assert report['knowledge_scope'].startswith('Prior uploaded evidence')
    different=client.post('/api/projects',json={'name':'Separate private project','goal':'Independent data','business_id':original['business_id']}).json()
    other=client.post('/api/conversations',json={'title':'Different scope','business_id':original['business_id'],'project_id':different['id']}).json()
    assert client.post('/api/conversations/'+other['id']+'/runs',json={'text':'Read the other project files','mode':'evidence'}).status_code==422

def test_operational_workflow_uses_shared_runtime_and_approval(client):
    conversation=client.post('/api/conversations',json={'title':'Log investigation'}).json()
    client.post('/api/conversations/'+conversation['id']+'/files',files={'file':('service-logs.txt',Path('sample-data/service-logs.txt').read_bytes())})
    response=client.post('/api/conversations/'+conversation['id']+'/runs',json={'text':'Investigate activation errors','analysis_kind':'operations','mode':'evidence'})
    id=response.json()['id'];client.get('/api/executions/'+id+'/live')
    execution=client.get('/api/executions/'+id).json()
    assert execution['state']=='WAITING_FOR_APPROVAL'
    assert execution['report']['operations']['log_analysis']['severity_counts']['ERROR']==2
    assert execution['report']['operations']['verification']['status']=='not_evaluated'
    assert any('incident' in r['title'].lower() for r in execution['report']['recommendations'])
    assert any(event.get('tool')=='investigate_operations' for event in execution['events'])
