import json,time
from pathlib import Path
from uuid import uuid4
import httpx
started=time.monotonic()
with httpx.Client(base_url='http://localhost:3000',headers={'X-Requested-With':'Evolvyn'},timeout=180) as c:
 c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'local-model-acceptance-password','name':'Local AI acceptance'}).raise_for_status()
 status=c.post('/api/providers/local/test');status.raise_for_status();print('Actual local provider test:',status.json(),flush=True)
 assert status.json()['available'],'Local provider failed its actual completion request'
 business=c.post('/api/businesses',json={'name':'Northstar Tasks · synthetic AI acceptance','goal':'Investigate conversion using uploaded evidence'}).json()
 project=c.post('/api/projects',json={'name':'Local AI conversion review','goal':'Prioritize a measured investigation','business_id':business['id'],'data_policy':'local_only'}).json()
 conversation=c.post('/api/conversations',json={'title':'Real local AI analysis','business_id':business['id'],'project_id':project['id']}).json()
 for name in ['funnel.csv','customer-feedback.txt']:
  c.post('/api/conversations/'+conversation['id']+'/files',files={'file':(name,Path('sample-data/'+name).read_bytes())}).raise_for_status()
 run=c.post('/api/conversations/'+conversation['id']+'/runs',json={'text':'Analyze conversion and customer feedback. What should we investigate first? Cite the supplied sources and distinguish facts from hypotheses.','mode':'local','allow_fallback':False});run.raise_for_status();id=run.json()['id']
 last=None
 with c.stream('GET','/api/executions/'+id+'/live') as stream:
  stream.raise_for_status()
  for line in stream.iter_lines():
   if line.startswith('data: '):
    final=json.loads(line[6:]);stage=final['events'][-1]['stage'] if final['events'] else final['state']
    if stage!=last:print('Actual execution stage:',stage,flush=True);last=stage
 assert final['state']=='WAITING_FOR_APPROVAL',final.get('error')
 assert not final['output'].startswith('Deterministic evidence mode'), 'A fallback cannot validate real AI'
 assert final['report'].get('usage',{}).get('provider')=='Local AI · Qwen'
 assert not final['report'].get('provider_status'),'Unexpected narrative fallback'
 assert not final['report'].get('strategy_fallback'),'Structured recommendations fell back unexpectedly'
 approved=c.post('/api/executions/'+id+'/decision',json={'approve':True,'plan':final['report']['recommendations'][0]['title'],'recommendation_id':final['report']['recommendations'][0]['id']});approved.raise_for_status()
 assert c.get('/api/tasks?conversation_id='+conversation['id']).json()
 result={'provider':'Local Qwen 2.5 1.5B','state':approved.json()['state'],'conversation':conversation['id'],'execution':id,'model_generated_recommendations':not bool(final['report'].get('strategy_fallback')),'recommendation_kind':final['report'].get('recommendation_kind'),'usage':final['report']['usage'],'elapsed_seconds':round(time.monotonic()-started,2),'output':final['output'],'report':final['report']}
 Path('.local/validation/live-local-ai.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ('output','report')},indent=2),flush=True)
 print('Actual model response excerpt:',final['output'][:1600],flush=True)
 print('REAL LOCAL AI → APPROVAL → INTERNAL TASKS: PASS',flush=True)
