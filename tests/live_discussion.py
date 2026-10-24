"""Real local-model LangGraph acceptance: no mocked model and no silent fallback."""
import json,time,secrets
from pathlib import Path
from uuid import uuid4
import httpx
start=time.monotonic()
with httpx.Client(base_url='http://localhost:3000',headers={'X-Requested-With':'Evolvyn'},timeout=360) as c:
 c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':secrets.token_urlsafe(24),'name':'Live specialist acceptance'}).raise_for_status()
 c.put('/api/vault/bindings/default',json={'provider':'local'}).raise_for_status()
 conv=c.post('/api/conversations',json={'title':'Real local specialist discussion'}).json()
 c.post('/api/conversations/'+conv['id']+'/files',files={'file':('funnel.csv',Path('sample-data/funnel.csv').read_bytes())}).raise_for_status()
 response=c.post('/api/discussions',json={'conversation_id':conv['id'],'goal':'Review these synthetic conversion observations. Propose one careful product investigation and list missing evidence. Cite the supplied source identifiers.','mode':'default','allow_fallback':False,'max_rounds':1,'max_seconds':300});response.raise_for_status();id=response.json()['id'];last=None
 with c.stream('GET','/api/executions/'+id+'/live') as stream:
  stream.raise_for_status()
  for line in stream.iter_lines():
   if line.startswith('data: '):
    run=json.loads(line[6:]);stage=run['events'][-1]['stage'] if run['events'] else run['state']
    if stage!=last:print('Actual specialist stage:',stage,flush=True);last=stage
 assert run['state']=='WAITING_FOR_APPROVAL',run.get('error')
 outputs=run['discussion_result']['outputs'];assert len(outputs)==4
 assert all(not result['fallback'] for result in outputs.values()),'Fallback cannot validate real model execution'
 result={'engine':run['engine'],'state':run['state'],'elapsed_seconds':round(time.monotonic()-start,2),'agents':{agent:{'mode':value['mode'],'model':value.get('model'),'classification':value['classification'],'usage':value.get('usage')} for agent,value in outputs.items()},'review_issues':run['discussion_result']['issues'],'reserved_output_tokens':run['discussion_checkpoint']['reserved_output_tokens']}
 c.post('/api/discussions/'+id+'/decision',json={'approve':False,'plan':'Acceptance run only; retain proposals for human inspection'}).raise_for_status()
 Path('.local/validation/live-discussion.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
 print('FOUR REAL LOCAL SPECIALISTS → LANGGRAPH HANDOFFS → REVIEW GATE: PASS',flush=True)
