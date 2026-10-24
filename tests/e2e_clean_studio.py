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
 for name,command in [('api',[str(root/'.venv/bin/python'),'-m','uvicorn','tests.qa_clean_studio_app:app','--host','127.0.0.1','--port','8890','--no-access-log']),('web',['node','frontend/node_modules/vite/bin/vite.js','--config',str(config)])]:
  log=(root/'.local'/('qa-clean-'+name+'.log')).open('w');logs.append(log)
  environment={**os.environ,'PYTHONPATH':str(root)+':'+str(root/'tests')}
  # tests is a namespace here; use the fixture's direct module path.
  if name=='api':command[3]='qa_clean_studio_app:app'
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
  expect(page.locator('.studio-sidebar nav>button')).to_have_count(4)
  page.locator('.studio-advanced-nav>summary').click();expect(page.locator('.studio-sidebar').get_by_role('button',name='Key vault',exact=True)).to_be_visible();page.locator('.studio-advanced-nav>summary').click()
  page.get_by_role('button',name='Hide studio navigation',exact=True).click();expect(page.locator('.studio-sidebar')).to_be_hidden();composer_visible()
  page.reload();expect(page.get_by_role('button',name='Show studio navigation',exact=True)).to_be_visible();composer_visible()
  page.screenshot(path=str(out/'studio-visible-composer.png'))
  studio.locator('.tool-access>summary').click();menu=studio.locator('.connector-popover');expect(menu).to_be_visible()
  expect(menu.get_by_role('button',name='Add connector',exact=False)).to_be_visible();expect(menu.get_by_label('Search connections and tools')).to_be_visible()
  bounds=menu.bounding_box();assert bounds['y']>=0 and bounds['y']+bounds['height']<=650,bounds
  page.screenshot(path=str(out/'studio-connector-menu.png'));studio.locator('.tool-access>summary').click()
  studio.get_by_label('Message product agents',exact=True).fill('Build a controlled catalog for this synthetic test')
  studio.get_by_role('button',name='Send to product agents',exact=True).click()
  studio.get_by_role('button',name='Confirm setup & start building',exact=True).click(timeout=20000)
  studio.get_by_role('button',name='Approve source implementation',exact=True).wait_for(timeout=20000)
  assert studio.get_by_role('navigation',name='Project file tree',exact=True).count()==0
  studio.get_by_role('button',name='Approve source implementation',exact=True).click()
  studio.get_by_text('Source ready · runtime not started',exact=True).first.wait_for(timeout=30000)
  studio.get_by_role('button',name='Open generated files',exact=False).click();expect(studio.get_by_role('navigation',name='Project file tree')).to_be_visible()
  expect(studio.locator('.product-source-code')).to_contain_text('8 files')
  studio.get_by_label('Search project files',exact=True).fill('Catalog.jsx');studio.locator('button[title="frontend/src/features/Catalog.jsx"]').click()
  expect(studio.locator('.product-source-code pre')).to_contain_text('Controlled model clothing catalog')
  composer_visible();page.screenshot(path=str(out/'studio-real-created-files.png'))
  product=studio.get_by_label('Agent product',exact=True).input_value()
  studio.get_by_role('button',name='Overview & agents',exact=True).click();studio.get_by_role('button',name='Run product agents',exact=True).click()
  studio.get_by_role('button',name='Approve source implementation',exact=True).wait_for(timeout=20000)
  page.goto(base+'/growth');page.goto(base+'/product-studio')
  expect(studio.get_by_label('Agent product',exact=True)).to_have_value(product)
  studio.get_by_role('button',name='Approve source implementation',exact=True).wait_for(timeout=20000)
  assert studio.get_by_role('navigation',name='Project file tree',exact=True).count()==0 # Previous build is not passed off as the new run's files.
  studio.get_by_role('button',name='Approve source implementation',exact=True).click()
  studio.get_by_text('Source ready · runtime not started',exact=True).first.wait_for(timeout=30000)

  studio.locator('.product-header-actions summary').click();studio.get_by_role('button',name='Move product conversation to trash',exact=True).click()
  expect(studio.get_by_label('Agent product',exact=True)).to_have_value('')
  studio.locator('.product-header-actions summary').click();studio.get_by_role('button',name='Open product trash',exact=True).click()
  trash=page.get_by_role('dialog',name='Trash',exact=True);expect(trash).to_contain_text('15 days');trash.get_by_role('button',name='Restore',exact=True).click()
  expect(trash).to_contain_text('Trash is empty');page.get_by_role('button',name='Close trash',exact=True).click()
  studio.get_by_label('Agent product',exact=True).select_option(product)
  expect(studio.locator('.product-source-code')).to_contain_text('8 files');composer_visible()
  page.set_viewport_size({'width':390,'height':844});composer_visible();page.screenshot(path=str(out/'studio-clean-mobile.png'))
  page.set_viewport_size({'width':1280,'height':800})
  response=page.request.post(base+'/api/conversations',data={'title':'Business trash acceptance'},headers={'X-Requested-With':'Evolvyn'});assert response.ok
  page.goto(base+'/dashboard');page.get_by_role('button',name='Move Business trash acceptance to trash',exact=True).click()
  page.get_by_role('button',name='Open conversation trash',exact=True).click()
  trash=page.get_by_role('dialog',name='Trash',exact=True);expect(trash).to_contain_text('Business trash acceptance');trash.get_by_role('button',name='Restore',exact=True).click();expect(trash).to_contain_text('Trash is empty');page.get_by_role('button',name='Close trash',exact=True).click()
  expect(page.locator('.conversation-history-row').filter(has_text='Business trash acceptance')).to_be_visible()
  assert not errors,errors
  print('CLEAN STUDIO PASS: visible composer at desktop/short/zoom-equivalent/mobile sizes; hide/show navigation and refresh; compact actual connectors menu; controlled model → approval → one-by-one persisted files → nested source tree; trash → restore; retained source. No live LLM or deployed generated-app runtime claimed.',flush=True)
  browser.close()
finally:
 for process in reversed(processes):
  process.terminate()
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 for log in logs:log.close()
