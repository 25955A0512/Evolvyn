"""Optional live Gemini acceptance for model-authored source; no mocked responses.
Set EVOLVYN_TEST_GEMINI_KEY privately to run. Controlled, credential-free UI and
source-boundary acceptance is tests/e2e_clean_studio.py instead.
"""
import os,time
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
key=os.getenv('EVOLVYN_TEST_GEMINI_KEY')
if not key:
 print('SKIPPED: live model-authored source acceptance requires EVOLVYN_TEST_GEMINI_KEY configured privately; no live-provider pass is claimed.')
 raise SystemExit(0)
base=os.getenv('EVOLVYN_TEST_URL','http://localhost:3000');out=Path('.local/validation');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1440,'height':850});credential=None;errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 try:
  page.goto(base+'/signup');page.get_by_label('Workspace name',exact=True).fill('Synthetic live Gemini source acceptance')
  page.get_by_label('Email',exact=True).fill('gemini-source-'+uuid4().hex+'@example.test');page.get_by_label('Password',exact=True).fill('acceptance-'+uuid4().hex)
  page.get_by_role('button',name='Create your workspace',exact=True).click();page.wait_for_url(base+'/dashboard')
  headers={'X-Requested-With':'Evolvyn'}
  def get(path):
   r=page.request.get(base+'/api'+path);assert r.ok,(path,r.status);return r.json()
  def write(path,body,method='POST'):
   r=page.request.fetch(base+'/api'+path,method=method,data=body,headers=headers);assert r.ok,(path,r.status);return r.json()
  credential=write('/vault/credentials',{'name':'Temporary live acceptance credential','provider':'gemini','value':key})
  write('/vault/workspace-default',{'provider':'gemini','credential_id':credential['id'],'reset_agent_overrides':True},'PUT')
  page.goto(base+'/product-studio');studio=page.locator('.intelligent-product-studio')
  studio.get_by_label('Message product agents',exact=True).fill('Build a private personal product catalog. React, FastAPI and PostgreSQL; private accounts and owner-scoped product records with name and price. Small first version, no payments or external integrations.')
  studio.get_by_role('button',name='Send to product agents',exact=True).click()
  studio.get_by_role('button',name='Confirm setup & start building',exact=True).click(timeout=120000)
  product=studio.get_by_label('Agent product',exact=True).input_value()
  page.goto(base+'/growth');page.goto(base+'/product-studio');expect(studio.get_by_label('Agent product',exact=True)).to_have_value(product)
  studio.get_by_role('button',name='Approve source implementation',exact=True).wait_for(timeout=300000)
  assert studio.get_by_role('navigation',name='Project file tree',exact=True).count()==0
  studio.get_by_role('button',name='Approve source implementation',exact=True).click()
  studio.get_by_text('Source ready · runtime not started',exact=True).first.wait_for(timeout=150000)
  saved=get('/studio/products/'+product);run=get('/executions/'+saved['last_build_run'])
  assert run['state']=='COMPLETED',run.get('error')
  build=get('/studio/builds/'+run['graph_checkpoint']['nodes']['implementation']['output']['id'])
  assert build['generation']=='model' and build['frontend_build']['status']=='passed'
  created=[event for event in build['events'] if event['stage']=='file_created']
  assert len(created)==len(build['files']) and not any(path.startswith('evolvyn/') for path in build['files'])
  page.reload();expect(studio.get_by_label('Agent product',exact=True)).to_have_value(product)
  expect(studio.get_by_role('navigation',name='Project file tree')).to_be_visible()
  page.screenshot(path=str(out/'live-gemini-model-source.png'))
  assert not errors,errors
  print('LIVE GEMINI SOURCE PASS: scoped key → actual model plan → restored durable graph → explicit approval → individual model-authored files → actual frontend compilation → reload. Generated backend was not executed.')
 finally:
  if credential:
   try:page.request.delete(base+'/api/vault/credentials/'+credential['id'],headers={'X-Requested-With':'Evolvyn'})
   except Exception:pass
  browser.close()
