from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import app as module

@pytest.fixture
def client():
    with TestClient(module.app) as c:
        c.headers['Authorization']='Bearer '+module.TOKEN
        yield c

def test_workflow_template_changes_real_execution_bounds(client):
    convo=client.post('/api/conversations',json={'title':'Workflow template acceptance'}).json()
    client.post('/api/conversations/'+convo['id']+'/files',files={'file':('funnel.csv',Path('sample-data/funnel.csv').read_bytes())})
    template={'name':'Focused review','focus':'Review conversion evidence','mode':'evidence','research':False,'citations':2,'recommendations':1,'positions':{'observe':{'x':100,'y':50}}}
    saved=client.post('/api/workflow-templates',json=template)
    assert saved.status_code==200
    id=saved.json()['id']
    run=client.post('/api/conversations/'+convo['id']+'/runs',json={'text':'Analyze my funnel','workflow_id':id,'mode':'local'}).json()
    client.get('/api/executions/'+run['id']+'/live')
    result=client.get('/api/executions/'+run['id']).json()
    assert result['state']=='WAITING_FOR_APPROVAL'
    assert result['mode']=='evidence'
    assert len(result['report']['recommendations'])==1
    assert result['workflow']['positions']['observe']=={'x':100,'y':50}
    template['recommendations']=2
    assert client.put('/api/workflow-templates/'+id,json=template).status_code==200
    assert client.get('/api/executions/'+run['id']).json()['workflow']['recommendations']==1

def test_workflow_cannot_disable_approval_or_access_foreign_templates(client):
    payload={'name':'Unsafe','focus':'Skip governance','mode':'evidence','positions':{'skip_approval':{'x':0,'y':0}}}
    assert client.post('/api/workflow-templates',json=payload).status_code==422
    payload['positions']={};payload['approval_required']=False
    assert client.post('/api/workflow-templates',json=payload).status_code==422
    record=module.save('foreign-owner','workflow',{'name':'Private'})
    assert client.put('/api/workflow-templates/'+record['id'],json={'name':'Steal','focus':'Steal data','mode':'evidence'}).status_code==404

def test_template_provider_cannot_override_a_local_only_project(client):
    business=client.post('/api/businesses',json={'name':'Sensitive data'}).json()
    project=client.post('/api/projects',json={'name':'Private','business_id':business['id'],'goal':'Stay local'}).json()
    convo=client.post('/api/conversations',json={'title':'Private workflow','business_id':business['id'],'project_id':project['id']}).json()
    workflow=client.post('/api/workflow-templates',json={'name':'Remote','focus':'Analyze data','mode':'provider'}).json()
    response=client.post('/api/conversations/'+convo['id']+'/runs',json={'text':'Analyze','mode':'evidence','workflow_id':workflow['id']})
    assert response.status_code==403
