"""Real API/PG/browser acceptance with an explicitly controlled model boundary."""
import os,re,socket,subprocess,time
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1];out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:3333'
config=root/'.local/qa-vite.config.mjs'
config.write_text("import {defineConfig} from '../frontend/node_modules/vite/dist/node/index.js';export default defineConfig({root:"+repr(str(root/'frontend'))+",server:{host:'127.0.0.1',port:3333,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8890'}}}});")
logs=[];processes=[]
try:
 for name,command in [('api',[str(root/'.venv/bin/python'),'-m','uvicorn','tests.qa_chat_app:app','--host','127.0.0.1','--port','8890','--no-access-log']),('web',['node','frontend/node_modules/vite/bin/vite.js','--config',str(config)])]:
  log=(root/'.local'/('qa-chat-'+name+'.log')).open('w');logs.append(log)
  environment={**os.environ,'PYTHONPATH':str(root)+':'+str(root/'tests')}
  # tests is a namespace here; use the fixture's direct module path.
  if name=='api':command[3]='qa_chat_app:app'
  processes.append(subprocess.Popen(command,cwd=root,env=environment,stdout=log,stderr=log))
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  page=browser.new_page(viewport={'width':1440,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  for _ in range(100):
   try:
    if page.request.get(base+'/api/health',timeout=1000).ok:break
   except Exception:pass
   if any(p.poll() is not None for p in processes):raise AssertionError('QA fixture failed; inspect private QA logs')
   time.sleep(.2)
  page.goto(base+'/signup');page.get_by_label('Workspace name',exact=True).fill('Controlled UI acceptance')
  page.get_by_label('Email',exact=True).fill('clean-'+uuid4().hex+'@example.test');page.get_by_label('Password',exact=True).fill('acceptance-'+uuid4().hex)
  page.get_by_role('button',name='Create your workspace',exact=True).click();page.wait_for_url(base+'/dashboard')
  page.goto(base+'/product-studio');studio=page.locator('.intelligent-product-studio')
  def composer_visible():
   box=studio.get_by_label('Message product agents',exact=True);expect(box).to_be_visible()
   bounds=box.bounding_box();assert bounds and bounds['y']>=0 and bounds['y']+bounds['height']<=page.viewport_size['height'],bounds
   assert page.locator('.studio-scroll').evaluate('(el)=>el.scrollHeight<=el.clientHeight+1')
  for width,height in [(1440,800),(1280,600),(1024,650),(390,844)]:
   page.set_viewport_size({'width':width,'height':height});composer_visible()
  page.set_viewport_size({'width':1280,'height':650})
  expect(page.locator('.studio-sidebar nav>button')).to_have_count(3)
  page.locator('.studio-advanced-nav>summary').click();expect(page.locator('.studio-sidebar').get_by_role('button',name='Key vault',exact=True)).to_be_visible();page.locator('.studio-advanced-nav>summary').click()
  page.get_by_role('button',name='Hide studio navigation',exact=True).click();expect(page.locator('.studio-sidebar')).to_be_hidden();composer_visible()
  page.reload();expect(page.get_by_role('button',name='Show studio navigation',exact=True)).to_be_visible();composer_visible()
  page.screenshot(path=str(out/'studio-visible-composer.png'))
  studio.locator('.tool-access>summary').click();menu=studio.locator('.connector-popover');expect(menu).to_be_visible()
  expect(menu.get_by_role('button',name='Add connector',exact=False)).to_be_visible();expect(menu.get_by_label('Search connections and tools')).to_be_visible()
  bounds=menu.bounding_box();assert bounds['y']>=0 and bounds['y']+bounds['height']<=650,bounds
  page.screenshot(path=str(out/'studio-connector-menu.png'));studio.locator('.tool-access>summary').click()
  # A verified cloud key becomes the shared default without a model picker.
  r=page.request.post(base+'/api/vault/model-key',data={'name':'Synthetic Gemini chat key','provider':'gemini','value':'synthetic-chat-key-'+uuid4().hex},headers={'X-Requested-With':'Evolvyn'});assert r.ok,r.status
  data=page.request.get(base+'/api/vault').json();assert all(r['resolved_model']=='gemini-2.5-flash-lite' for r in data['effective_routes'].values())
  page.goto(base+'/product-studio');composer=studio.get_by_label('Message product agents',exact=True)
  expect(studio.get_by_role('heading',name='What would you like to build?',exact=True)).to_be_visible()
  expect(studio.get_by_role('button',name='Send to product agents')).to_be_disabled()
  composer.fill('Build a controlled catalog');composer.press('Shift+Enter');expect(composer).to_have_value('Build a controlled catalog\n')
  assert page.request.get(base+'/api/studio/products').json()==[]
  composer.fill('Build a controlled catalog for this synthetic test')
  pending=[]
  def delayed_message(route):pending.append(route)
  page.route('**/api/studio/products/*/messages',delayed_message)
  composer.press('Enter');expect(studio.get_by_role('status')).to_contain_text('Saving your message and starting the agent')
  expect(composer).to_have_value('');expect(studio.get_by_role('button',name='Send to product agents')).to_be_disabled()
  composer.press('Enter')
  for _ in range(100):
   if pending:break
   page.wait_for_timeout(50)
  assert len(pending)==1
  pending[0].continue_();page.unroute('**/api/studio/products/*/messages',delayed_message)
  studio.get_by_role('button',name='Confirm setup & start building',exact=True).wait_for(timeout=30000)
  product=studio.get_by_label('Agent product',exact=True).input_value()
  composer.fill('Please help me refine the store requirements');composer.press('Enter')
  expect(studio.locator('.product-chat.assistant').filter(has_text='Controlled model fixture:')).to_have_count(2,timeout=30000)
  history=page.request.get(base+'/api/studio/products/'+product+'/agent-history').json()
  assert len(history)==2 and all(r['state']=='COMPLETED' for r in history)
  page.goto(base+'/growth');page.goto(base+'/product-studio');expect(studio.get_by_label('Agent product',exact=True)).to_have_value(product)
  expect(studio.locator('.product-chat.assistant').filter(has_text='Controlled model fixture:')).to_have_count(2)
  # A rejected queue request restores the user's draft and never creates a fake reply.
  page.route('**/api/studio/products/*/messages',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"Synthetic queue unavailable; draft retained"}'))
  composer.fill('Keep this unsent draft');composer.press('Enter');expect(composer).to_have_value('Keep this unsent draft')
  expect(studio.get_by_role('alert')).to_contain_text('Synthetic queue unavailable')
  assert len(page.request.get(base+'/api/studio/products/'+product+'/agent-history').json())==2
  for width,height in [(1280,650),(390,844)]:
   page.set_viewport_size({'width':width,'height':height});composer_visible();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  page.screenshot(path=str(out/'chat-enter-and-route.png'))
  assert not errors,errors
  print('CHAT INPUT PASS: automatically verified workspace key → actual vault/default route persistence → Shift+Enter newline → Enter sends once → immediate pending message under delayed queue → controlled LLM chat → navigation/history restoration → failed-request draft recovery → desktop/mobile. No live Gemini acceptance claimed.',flush=True)
  browser.close()
finally:
 for process in reversed(processes):
  process.terminate()
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 for log in logs:log.close()
