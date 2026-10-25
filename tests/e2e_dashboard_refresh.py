"""Dashboard design acceptance against real APIs/DB; controlled model metadata/responses."""
import os,subprocess,time
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1];out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:3333';config=root/'.local/qa-dashboard-vite.config.mjs'
config.write_text("import {defineConfig} from '../frontend/node_modules/vite/dist/node/index.js';export default defineConfig({root:"+repr(str(root/'frontend'))+",server:{host:'127.0.0.1',port:3333,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8890'}}}});")
logs=[];processes=[]
try:
 for name,command in [('api',[str(root/'.venv/bin/python'),'-m','uvicorn','qa_dashboard_app:app','--host','127.0.0.1','--port','8890','--no-access-log']),('web',['node','frontend/node_modules/vite/bin/vite.js','--config',str(config)])]:
  log=(root/'.local'/('qa-dashboard-'+name+'.log')).open('w');logs.append(log);processes.append(subprocess.Popen(command,cwd=root,env={**os.environ,'PYTHONPATH':str(root)+':'+str(root/'tests')},stdout=log,stderr=log))
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);page=browser.new_page(viewport={'width':1440,'height':960});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  for _ in range(100):
   try:
    if page.request.get(base+'/api/health',timeout=1000).ok:break
   except Exception:pass
   if any(p.poll() is not None for p in processes):raise AssertionError('Dashboard fixture failed')
   time.sleep(.2)
  headers={'X-Requested-With':'Evolvyn'}
  def post(path,data):
   r=page.request.post(base+'/api'+path,data=data,headers=headers);assert r.ok,(path,r.status);return r.json()
  post('/auth/register',{'email':'dashboard-'+uuid4().hex+'@example.test','password':'dashboard-acceptance-'+uuid4().hex,'name':'Dashboard acceptance'})
  page.goto(base+'/keyvault');expect(page.get_by_role('heading',name='Key vault',exact=True)).to_be_visible()
  page.get_by_role('button',name='Add key',exact=True).click();dialog=page.get_by_role('dialog',name='Add a key');expect(dialog).to_be_visible()
  dialog.get_by_label('Secret value').fill('synthetic-dashboard-'+uuid4().hex);dialog.get_by_label('Credential name').fill('Synthetic Gemini');dialog.get_by_role('button',name='Save key',exact=True).click();expect(dialog).to_have_count(0)
  expect(page.locator('.dashboard-connector-card')).to_contain_text('Synthetic Gemini')
  page.get_by_role('button',name='Load available models',exact=True).click();dialog=page.get_by_role('dialog',name='Choose a model');dialog.get_by_label('Available Gemini model: Synthetic Gemini').select_option('synthetic-visible-model');dialog.get_by_role('button',name='Use for all agents',exact=True).click();expect(dialog).to_have_count(0)
  expect(page.locator('.default-model-stat')).to_contain_text('synthetic-visible-model');page.screenshot(path=str(out/'dashboard-keyvault.png'),full_page=True)
  page.get_by_role('navigation',name='Vault sections').get_by_role('button',name='Agent routes',exact=True).click();page.get_by_role('button',name='Add override',exact=True).click();dialog=page.get_by_role('dialog',name='Model route');dialog.get_by_label('Model route agent').select_option('reviewer');dialog.get_by_label('Route provider').select_option('evidence');dialog.get_by_role('button',name='Save route',exact=True).click();expect(page.locator('tr').filter(has_text='Quality and security reviewer')).to_contain_text('Override')
  page.get_by_role('button',name='Reset',exact=True).click();expect(page.locator('tr').filter(has_text='Quality and security reviewer')).to_contain_text('Workspace default')
  page.goto(base+'/keyvault');page.get_by_role('button',name='Add key',exact=True).click();page.keyboard.press('Escape');expect(page.get_by_role('dialog',name='Add a key',exact=True)).to_have_count(0)
  conv=post('/conversations',{'title':'Dashboard evidence'})
  page.goto(base+'/discussionroom');expect(page.get_by_role('heading',name='Discussion room',exact=True)).to_be_visible();page.get_by_label('Discussion conversation').select_option(conv['id'])
  page.get_by_role('button',name='Review our growth strategy',exact=False).click();expect(page.get_by_label('Decision or business goal')).to_have_value('Review our growth strategy')
  page.get_by_role('button',name='Discussion settings',exact=True).click();dialog=page.get_by_role('dialog',name='Discussion settings');expect(dialog).to_be_visible();page.keyboard.press('Escape');expect(dialog).to_have_count(0)
  page.screenshot(path=str(out/'dashboard-discussion.png'),full_page=True)
  page.get_by_label('Decision or business goal').press('Enter');expect(page.locator('.discussion-thread')).to_contain_text('Controlled specialist response',timeout=30000)
  page.goto(base+'/integrations');expect(page.get_by_role('heading',name='Connections',exact=True)).to_be_visible();nav=page.get_by_role('navigation',name='Connection sections');nav.get_by_role('button',name='Discover',exact=True).click();page.get_by_role('button',name='Configure Evidence utilities',exact=True).click();expect(page.get_by_role('status')).to_contain_text('MCP check complete',timeout=15000)
  nav.get_by_role('button',name='Connected',exact=True).click();expect(page.locator('.dashboard-connector-card').filter(has_text='Evidence utilities')).to_contain_text('MCP ready');page.get_by_role('button',name='Connect Google Drive',exact=True).click();setup=page.get_by_role('dialog',name='Google Drive setup');expect(setup).to_be_visible();expect(setup.get_by_label('Redirect URL')).to_have_value(__import__('re').compile(r'.*/api/integrations/google_drive/callback$'));expect(setup.get_by_label('Render environment variables')).to_have_value(__import__('re').compile('OAUTH_GOOGLE_DRIVE_CLIENT_ID'));page.keyboard.press('Escape');nav.get_by_role('button',name='Tools',exact=True).click();expect(page.get_by_role('table')).to_contain_text('analyze_business');page.screenshot(path=str(out/'dashboard-connections.png'),full_page=True)
  page.goto(base+'/growth');g=page.get_by_label('Business growth workspace');g.get_by_label('Growth conversation').select_option(conv['id']);g.get_by_role('button',name='Customize',exact=True).click();dialog=page.get_by_role('dialog',name='Customize dashboard');dialog.get_by_label('Performance summary',exact=True).uncheck();dialog.get_by_role('button',name='Done',exact=True).click();expect(g.get_by_label('Business performance')).to_be_hidden()
  page.reload();expect(g.get_by_label('Business performance')).to_be_hidden();g.get_by_role('button',name='Customize',exact=True).click();page.get_by_role('dialog',name='Customize dashboard',exact=True).get_by_label('Performance summary',exact=True).check();page.get_by_role('dialog',name='Customize dashboard',exact=True).get_by_role('button',name='Done').click();expect(g.get_by_label('Business performance')).to_be_visible()
  r=page.request.post(base+'/api/conversations/'+conv['id']+'/files',multipart={'file':{'name':'ecommerce-sales.csv','mimeType':'text/csv','buffer':(root/'sample-data/ecommerce-sales.csv').read_bytes()}},headers=headers);assert r.ok
  post('/growth/reports',{'conversation_id':conv['id'],'query':'Review observed sales performance'})
  page.reload();g.get_by_role('button',name='Table',exact=True).click();expect(g.get_by_role('table')).to_contain_text('Tea');expect(g.get_by_role('table')).to_contain_text('30.10');page.screenshot(path=str(out/'dashboard-growth.png'),full_page=True)
  post('/schedules',{'conversation_id':conv['id'],'query':'Synthetic scheduled review','interval_minutes':1440,'mode':'evidence'})
  page.goto(base+'/monitoring');expect(page.get_by_role('heading',name='Monitoring',exact=True)).to_be_visible();expect(page.get_by_label('Monitoring summary')).to_contain_text('1');expect(page.locator('.schedule-item')).to_contain_text('Synthetic scheduled review');page.get_by_role('button',name='Pause',exact=True).click();expect(page.locator('.schedule-item')).to_contain_text('Paused');page.screenshot(path=str(out/'dashboard-monitoring.png'),full_page=True)
  for route in ['/keyvault','/discussionroom','/integrations','/growth','/monitoring']:
   page.set_viewport_size({'width':390,'height':844});page.goto(base+route);page.wait_for_timeout(300);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),route+' horizontal overflow'
  page.goto(base+'/discussionroom');composer=page.get_by_label('Decision or business goal');expect(composer).to_be_visible();bounds=composer.bounding_box();assert bounds['y']+bounds['height']<=844,bounds;page.screenshot(path=str(out/'dashboard-discussion-mobile.png'),full_page=True)
  assert not errors,errors
  print('DASHBOARD PASS: native vault dialogs → encrypted key → real model-list boundary → default/override/reset → discussion prompt/settings/Enter → actual MCP stdio discovery → tools → widget persistence → SQL sales table → monitor pause → mobile. Controlled provider responses; no live-provider claims.',flush=True)
  browser.close()
finally:
 for p in reversed(processes):
  p.terminate()
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 for log in logs:log.close()
