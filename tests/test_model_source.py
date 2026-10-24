"""Model source contracts use controlled model responses and real persistence/approval."""
import json
import pytest
from fastapi.testclient import TestClient
from backend import app as m
from backend.model_source import ModelSourceBuilder,safe_path
from backend.product_studio import QUESTIONS
from test_product_intelligence import models,finish,product

@pytest.fixture
def client():
 with TestClient(m.app) as c:
  c.headers['Authorization']='Bearer '+m.TOKEN
  yield c

FILES={
 'frontend/src/main.jsx':"import React from 'react';import {createRoot} from 'react-dom/client';import {Catalog} from './features/Catalog.jsx';createRoot(document.getElementById('root')).render(<Catalog/>);",
 'frontend/src/features/Catalog.jsx':"import React from 'react';export function Catalog(){return <h1>Controlled model clothing catalog</h1>}",
 'frontend/package.json':json.dumps({'name':'controlled-model-catalog','dependencies':{'react':'19.1.0','react-dom':'19.1.0'}}),
 'frontend/index.html':'<div id="root"></div><script type="module" src="/src/main.jsx"></script>',
 'backend/app.py':'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/health")\ndef health():return {"ready":True}\n',
 'backend/requirements.txt':'fastapi==0.115.12\nuvicorn==0.34.2\n',
 'Dockerfile':'FROM python:3.12-slim\nWORKDIR /app\nCOPY backend ./\n',
 'compose.yaml':'services:\n  app:\n    build: .\n  db:\n    image: postgres:17\n',
}

@pytest.fixture
def source_model(monkeypatch,models):
 calls=[];original=ModelSourceBuilder.__init__
 def init(self,s):
  original(self,s)
  async def stream(report,prompt,history,mode):
   calls.append(prompt)
   if 'PRODUCT_SOURCE_MANIFEST_JSON' in prompt:
    yield json.dumps({'files':[{'path':p,'purpose':'Controlled source test '+p} for p in FILES]})
   else:
    path=next(p for p in FILES if 'contents of '+p+' only' in prompt)
    rows=m.listing('initial-workspace','product_build');assert len(rows)==1
    assert set(rows[0]['files'])==set(list(FILES)[:list(FILES).index(path)])
    yield FILES[path]
  self.stream=stream
 monkeypatch.setattr(ModelSourceBuilder,'__init__',init)
 return calls

def approved_model_build(c,mode="local"):
 p=product(c,True);run=finish(c,c.post('/api/studio/products/'+p['id']+'/agent-build',json={'spec_id':p['id'],'revision':p['revision'],'mode':mode}))
 assert run['state']=='WAITING_FOR_APPROVAL',run.get('error')
 assert 'file_plan' not in run['graph_checkpoint']['nodes']
 assert c.get('/api/studio/builds').json()==[]
 c.post('/api/harness/executions/'+run['id']+'/decision',json={'approve':True,'binding':run['graph_checkpoint']['pending']['binding']}).raise_for_status()
 c.get('/api/executions/'+run['id']+'/live')
 return p,c.get('/api/executions/'+run['id']).json()

def test_real_file_by_file_persistence_not_template_inventory(client,source_model,monkeypatch):
 monkeypatch.delenv('EVOLVYN_COMPILER_URL',raising=False)
 p,run=approved_model_build(client)
 assert run['state']=='COMPLETED',run.get('error')
 build=client.get('/api/studio/builds/'+run['graph_checkpoint']['nodes']['implementation']['output']['id']).json()
 assert build['generation']=='model' and build['state']=='READY'
 assert build['files']==FILES and len(source_model)==len(FILES)+1
 assert [v['detail'] for v in build['events'] if v['stage']=='file_created']==['Created '+path for path in FILES]
 assert not any(path.startswith('evolvyn/') for path in build['files'])
 assert build['frontend_build']['status']=='unavailable'
 assert build['implemented_capabilities']==[] # Source text is not a runtime proof.

@pytest.mark.parametrize('path',['../escape.py','/etc/passwd','a//b.py','a/../b.py','a\\b.py','frontend/package-lock.json','a.sh'])
def test_unsafe_or_fabricated_file_paths_rejected(path):
 with pytest.raises(ValueError):safe_path(path)

def test_failed_generation_retains_only_completed_files(client,models,monkeypatch):
 original=ModelSourceBuilder.__init__
 def init(self,s):
  original(self,s)
  async def stream(report,prompt,history,mode):
   if 'MANIFEST_JSON' in prompt:yield json.dumps({'files':[{'path':p,'purpose':'test'} for p in FILES]})
   elif 'contents of frontend/src/main.jsx only' in prompt:yield FILES['frontend/src/main.jsx']
   else:raise RuntimeError('raw private upstream detail')
  self.stream=stream
 monkeypatch.setattr(ModelSourceBuilder,'__init__',init)
 p,run=approved_model_build(client)
 assert run['state']=='FAILED'
 build=client.get('/api/studio/builds').json()[0]
 assert build['state']=='FAILED' and list(build['files'])==['frontend/src/main.jsx']
 assert 'raw private' not in json.dumps(build)

def test_truncated_file_gets_one_bounded_retry(client,models,monkeypatch):
 from backend.model_errors import ModelFailure
 original=ModelSourceBuilder.__init__;attempts=[]
 def init(self,s):
  original(self,s)
  async def stream(report,prompt,history,mode):
   if 'MANIFEST_JSON' in prompt:yield json.dumps({'files':[{'path':p,'purpose':'test'} for p in FILES]});return
   attempts.append(report['_output_limit'])
   raise ModelFailure('model_output_limit','Controlled provider truncation')
   yield ''
  self.stream=stream
 monkeypatch.setattr(ModelSourceBuilder,'__init__',init)
 p,run=approved_model_build(client)
 assert run['state']=='FAILED'
 build=client.get('/api/studio/builds').json()[0]
 assert attempts==[512,512] # Local provider retains its own lower allowance.
 assert len([e for e in build['events'] if e['stage']=='retry'])==1
 assert not build['files'] and build['error_code']=='model_output_limit'

def test_native_gemini_source_calls_use_scoped_key_and_larger_file_allowance(client,models,monkeypatch):
 import httpx
 from backend.vault import CredentialInput,BindingInput
 key='unit-gemini-source-key-not-real';credential=m.VAULT.put('initial-workspace',CredentialInput(name='Controlled source provider',provider='gemini',value=key))
 m.VAULT.bind('initial-workspace','developer',BindingInput(credential_id=credential['id'],provider='gemini',model='gemini-2.5-flash'))
 seen=[];original=httpx.AsyncClient
 async def transport(request):
  assert request.url.host=='generativelanguage.googleapis.com'
  assert request.headers['x-goog-api-key']==key and key not in str(request.url)
  body=json.loads(request.content);text=body['contents'][-1]['parts'][0]['text'];assert key not in text
  seen.append(body['generationConfig']['maxOutputTokens'])
  if 'MANIFEST_JSON' in text:out=json.dumps({'files':[{'path':p,'purpose':'Controlled native gateway test'} for p in FILES]})
  else:out=next(content for path,content in FILES.items() if 'contents of '+path+' only' in text)
  return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':out}]}}]})
 monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(transport),**kwargs))
 monkeypatch.delenv('EVOLVYN_COMPILER_URL',raising=False)
 _,run=approved_model_build(client,"default")
 assert run['state']=='COMPLETED',run.get('error')
 assert seen==[2048]+[4096]*len(FILES)

def test_trashing_active_generation_cancels_and_restores_only_saved_files(client,models,monkeypatch):
 import asyncio,time
 original=ModelSourceBuilder.__init__
 def init(self,s):
  original(self,s)
  async def stream(report,prompt,history,mode):
   if 'MANIFEST_JSON' in prompt:yield json.dumps({'files':[{'path':p,'purpose':'test cancellation'} for p in FILES]});return
   path=next(p for p in FILES if 'contents of '+p+' only' in prompt)
   if path!='frontend/src/main.jsx':await asyncio.sleep(10)
   yield FILES[path]
  self.stream=stream
 monkeypatch.setattr(ModelSourceBuilder,'__init__',init)
 p=product(client,True)
 run=finish(client,client.post('/api/studio/products/'+p['id']+'/agent-build',json={'spec_id':p['id'],'revision':p['revision'],'mode':'local'}))
 assert run['state']=='WAITING_FOR_APPROVAL'
 client.post('/api/harness/executions/'+run['id']+'/decision',json={'approve':True,'binding':run['graph_checkpoint']['pending']['binding']}).raise_for_status()
 for _ in range(100):
  builds=client.get('/api/studio/builds').json()
  if builds and builds[0]['files']:break
  time.sleep(.02)
 assert builds and list(builds[0]['files'])==['frontend/src/main.jsx']
 client.delete('/api/studio/products/'+p['id']).raise_for_status()
 assert client.get('/api/studio/builds/'+builds[0]['id']).status_code==404
 entry=client.get('/api/trash').json()[0]
 client.post('/api/trash/'+entry['id']+'/restore').raise_for_status()
 restored=client.get('/api/studio/builds/'+builds[0]['id']).json()
 assert restored['state']=='CANCELLED' and list(restored['files'])==['frontend/src/main.jsx']
 assert client.get('/api/executions/'+run['id']).json()['state']=='CANCELLED'

@pytest.mark.parametrize('volume',[r'C:\Users\private:/data','/var/run/docker.sock:/var/run/docker.sock','../private:/data',{'type':'bind','source':'/private','target':'/data'}])
def test_generated_compose_cannot_mount_private_host_paths(volume):
 from backend.model_source import validate_source
 import yaml
 files=dict(FILES);files['compose.yaml']=yaml.safe_dump({'services':{'app':{'build':'.','volumes':[volume]},'db':{'image':'postgres:17'}}})
 with pytest.raises(ValueError):validate_source(files)
