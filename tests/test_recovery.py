import asyncio
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from backend import app as module
from backend.execution_queue import claim,WORKER

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    with TestClient(module.app) as c:
        c.headers['Authorization']='Bearer '+module.TOKEN
        yield c

def prepared(c):
    conversation=c.post('/api/conversations',json={'title':'Recovery validation'}).json()
    c.post('/api/conversations/'+conversation['id']+'/files',files={'file':('funnel.csv',Path('sample-data/funnel.csv').read_bytes())})
    return conversation

def test_expired_lease_recovers_the_same_strategy_checkpoint(client):
    conversation=prepared(client)
    run=client.post('/api/conversations/'+conversation['id']+'/runs',json={'text':'Analyze conversion','mode':'evidence'}).json()
    client.get('/api/executions/'+run['id']+'/live')
    checkpoint=client.get('/api/executions/'+run['id']).json()
    ids=[r['id'] for r in checkpoint['report']['recommendations']]
    checkpoint.update(state='RUNNING',worker='dead-process',lease_until=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat(),attempt=1,output='interrupted partial output')
    module.save('initial-workspace','execution',{k:v for k,v in checkpoint.items() if k!='id'},run['id'])
    client.portal.call(module.dispatch_pending)
    client.get('/api/executions/'+run['id']+'/live')
    recovered=client.get('/api/executions/'+run['id']).json()
    assert recovered['state']=='WAITING_FOR_APPROVAL'
    assert recovered['attempt']==2
    assert [r['id'] for r in recovered['report']['recommendations']]==ids
    assert any(e['stage']=='recover' for e in recovered['events'])
    assert not client.get('/api/tasks?conversation_id='+conversation['id']).json()

def test_stale_worker_cannot_overwrite_a_new_lease(client):
    record=module.save('initial-workspace','execution',{'state':'CREATED','question':'test','events':[],'attempt':0})
    owned=claim(module.conn,'initial-workspace',record['id'])
    assert owned and owned['worker']
    token=WORKER.set('stale-worker')
    try:assert module.change_execution('initial-workspace',record['id'],{'state':'WAITING_FOR_APPROVAL'}) is None
    finally:WORKER.reset(token)
    assert module.get('initial-workspace',record['id'],'execution')['state']=='RUNNING'

def test_recovery_attempt_limit_is_terminal(client):
    record=module.save('initial-workspace','execution',{'state':'CREATED','question':'test','events':[],'attempt':2})
    assert claim(module.conn,'initial-workspace',record['id']) is None
    assert module.get('initial-workspace',record['id'],'execution')['state']=='FAILED'

def test_project_local_policy_blocks_remote_provider(client):
    business=client.post('/api/businesses',json={'name':'Sensitive business'}).json()
    project=client.post('/api/projects',json={'name':'Local processing','goal':'Protect evidence','business_id':business['id']}).json()
    convo=client.post('/api/conversations',json={'title':'Private analysis','business_id':business['id'],'project_id':project['id']}).json()
    client.post('/api/conversations/'+convo['id']+'/files',files={'file':('funnel.csv',Path('sample-data/funnel.csv').read_bytes())})
    for mode in ['provider','groq','gemini']:
        assert client.post('/api/conversations/'+convo['id']+'/runs',json={'text':'Analyze evidence','mode':mode}).status_code==403
