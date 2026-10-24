import json
from datetime import datetime,timedelta,timezone
import pytest
from fastapi.testclient import TestClient
from backend import app as m
@pytest.fixture
def client():
 with TestClient(m.app) as c:
  c.headers['Authorization']='Bearer '+m.TOKEN
  yield c

def test_conversation_trash_restore_and_retention(client):
 conv=client.post('/api/conversations',json={'title':'Recover this conversation'}).json()
 client.post('/api/conversations/'+conv['id']+'/files',files={'file':('feedback.csv',b'sku,name,price\nT,Tea,5\n','text/csv')}).raise_for_status()
 conv=client.get('/api/conversations/'+conv['id']).json();doc=conv['files'][0]['id']
 response=client.delete('/api/conversations/'+conv['id']);assert response.status_code==200,response.text
 assert client.get('/api/conversations/'+conv['id']).status_code==404
 assert client.get('/api/documents/'+doc+'/commerce').status_code==404
 assert not client.get('/api/conversations').json()
 rows=client.get('/api/trash').json();assert len(rows)==1
 assert 14.9<(datetime.fromisoformat(rows[0]['purge_at'])-datetime.now(timezone.utc)).total_seconds()/86400<=15
 client.post('/api/trash/'+rows[0]['id']+'/restore').raise_for_status()
 assert client.get('/api/conversations/'+conv['id']).status_code==200
 assert client.get('/api/documents/'+doc+'/commerce').status_code==200
 client.delete('/api/conversations/'+conv['id']).raise_for_status()
 with m.conn() as c:c.execute("UPDATE records SET body=jsonb_set(body,'{purge_at}',%s::jsonb) WHERE id=%s",(json.dumps((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()),'trash:'+conv['id']))
 assert client.get('/api/trash').json()==[]
 with m.conn() as c:assert not c.execute('SELECT id FROM records WHERE id=ANY(%s)',([conv['id'],doc],)).fetchall()

def test_trash_blocks_runs_approvals_children_and_foreign_restore(client):
 p=client.post('/api/studio/products',json={'name':'Private project','goal':'Manage business records privately'}).json()
 conv=m.PRODUCT_AGENTS.conversation('initial-workspace',p)
 build=m.save('initial-workspace','product_build',{'spec_id':p['id'],'files':{'secret.txt':'private'}})
 run=m.save('initial-workspace','execution',{'conversation':conv['id'],'state':'WAITING_FOR_APPROVAL','events':[]})
 report=m.save('initial-workspace','artifact',{'execution':run['id']})
 task=m.save('initial-workspace','task',{'artifact':report['id']})
 client.delete('/api/studio/products/'+p['id']).raise_for_status()
 assert client.get('/api/studio/products/'+p['id']).status_code==404
 assert client.get('/api/studio/builds/'+build['id']).status_code==404
 assert client.get('/api/executions/'+run['id']).status_code==404
 assert client.post('/api/conversations/'+conv['id']+'/runs',json={'text':'hello','mode':'local','analysis_kind':'assistant'}).status_code==404
 with pytest.raises(Exception):m.get('initial-workspace',task['id'],'task')
 rows=client.get('/api/trash').json();assert len(rows)==1
 foreign=m.save('other-org','trash_entry',{'target_id':'not-owned','target_kind':'conversation','purge_at':(datetime.now(timezone.utc)+timedelta(days=15)).isoformat()})
 assert client.post('/api/trash/'+foreign['id']+'/restore').status_code==404
 client.post('/api/trash/'+rows[0]['id']+'/restore').raise_for_status()
 assert client.get('/api/studio/builds/'+build['id']).status_code==200
 assert client.get('/api/executions/'+run['id']).json()['state']=='CANCELLED'

def test_shared_documents_and_shared_graph_are_not_purged_with_other_chat(client):
 first=client.post('/api/conversations',json={'title':'First'}).json();second=client.post('/api/conversations',json={'title':'Second'}).json()
 client.post('/api/conversations/'+first['id']+'/files',files={'file':('notes.csv',b'sku,name,price\nT,Tea,5\n','text/csv')}).raise_for_status()
 doc=client.get('/api/conversations/'+first['id']).json()['files'][0]
 with m.conn() as c:c.execute("UPDATE records SET body=jsonb_set(body,'{files}',%s::jsonb) WHERE id=%s",(json.dumps([doc]),second['id']))
 graph=m.save('initial-workspace','agent_graph',{'name':'Shared graph'})
 runs=[m.save('initial-workspace','execution',{'conversation':conv['id'],'graph_id':graph['id'],'state':'COMPLETED','events':[]}) for conv in (first,second)]
 client.delete('/api/conversations/'+first['id']).raise_for_status()
 assert client.get('/api/documents/'+doc['id']+'/commerce').status_code==200
 with m.conn() as c:c.execute("UPDATE records SET body=jsonb_set(body,'{purge_at}','\"2000-01-01T00:00:00+00:00\"'::jsonb) WHERE id=%s",('trash:'+first['id'],))
 client.get('/api/trash')
 assert client.get('/api/executions/'+runs[1]['id']).status_code==200
 assert m.get('initial-workspace',graph['id'],'agent_graph')
 assert client.get('/api/documents/'+doc['id']+'/commerce').status_code==200

def test_viewer_cannot_trash_or_restore(client):
 client.headers.pop('Authorization');client.headers['X-Requested-With']='Evolvyn'
 identity=client.post('/api/auth/register',json={'email':'trash-role@example.test','password':'private-role-password','name':'Role test'}).json()
 conv=client.post('/api/conversations',json={'title':'Owner only deletion'}).json()
 client.delete('/api/conversations/'+conv['id']).raise_for_status()
 entry=client.get('/api/trash').json()[0]
 with m.conn() as c:c.execute("UPDATE memberships SET role='viewer' WHERE organization_id=%s",(identity['organization_id'],))
 assert client.post('/api/trash/'+entry['id']+'/restore').status_code==403
 with m.conn() as c:c.execute("UPDATE memberships SET role='owner' WHERE organization_id=%s",(identity['organization_id'],))
 client.post('/api/trash/'+entry['id']+'/restore').raise_for_status()
 with m.conn() as c:c.execute("UPDATE memberships SET role='viewer' WHERE organization_id=%s",(identity['organization_id'],))
 assert client.delete('/api/conversations/'+conv['id']).status_code==403

def test_source_linked_memory_is_hidden_and_purged(client):
 from backend.agent_memory import MemoryInput
 conv=client.post('/api/conversations',json={'title':'Forget source context'}).json()
 client.post('/api/conversations/'+conv['id']+'/files',files={'file':('source.txt',b'Private customer feedback','text/plain')}).raise_for_status()
 doc=client.get('/api/conversations/'+conv['id']).json()['files'][0]['id']
 memory=m.MEMORY.propose('initial-workspace',MemoryInput(text='Reviewed source-linked observation',source_ids=[doc]))
 m.MEMORY.decide('initial-workspace',memory['id'],True)
 client.delete('/api/conversations/'+conv['id']).raise_for_status()
 assert client.get('/api/memory').json()==[]
 with m.conn() as c:c.execute("UPDATE records SET body=jsonb_set(body,'{purge_at}','\"2000-01-01T00:00:00+00:00\"'::jsonb) WHERE id=%s",('trash:'+conv['id'],))
 client.get('/api/trash')
 with m.conn() as c:assert not c.execute('SELECT id FROM records WHERE id=%s',(memory['id'],)).fetchone()
