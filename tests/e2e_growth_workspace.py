"""Real growth UI/API/SQL/approval/scheduler journey. Synthetic uploads; evidence route, no live LLM."""
import os,re,subprocess,time
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1];out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:3334';config=root/'.local/qa-growth-vite.config.mjs'
config.write_text("import {defineConfig} from '../frontend/node_modules/vite/dist/node/index.js';export default defineConfig({root:"+repr(str(root/'frontend'))+",server:{host:'127.0.0.1',port:3334,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8891'}}}});")
logs=[];processes=[]
try:
 for name,command in [('api',[str(root/'.venv/bin/python'),'-m','uvicorn','qa_growth_app:app','--host','127.0.0.1','--port','8891','--no-access-log']),('web',['node','frontend/node_modules/vite/bin/vite.js','--config',str(config)])]:
  log=(root/'.local'/('qa-growth-'+name+'.log')).open('w');logs.append(log)
  processes.append(subprocess.Popen(command,cwd=root,env={**os.environ,'PYTHONPATH':str(root)+':'+str(root/'tests')},stdout=log,stderr=log))
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  page=browser.new_page(viewport={'width':1512,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  for _ in range(100):
   try:
    if page.request.get(base+'/api/health',timeout=1000).ok:break
   except Exception:pass
   if any(p.poll() is not None for p in processes):raise AssertionError('QA fixture failed; inspect private logs')
   time.sleep(.2)
  page.goto(base+'/signup');page.get_by_label('Workspace name',exact=True).fill('Synthetic growth acceptance')
  page.get_by_label('Email',exact=True).fill('growth-'+uuid4().hex+'@example.test');page.get_by_label('Password',exact=True).fill('acceptance-'+uuid4().hex)
  page.get_by_role('button',name='Create your workspace',exact=True).click();page.wait_for_url(base+'/dashboard');page.goto(base+'/growth')
  g=page.get_by_label('Business growth workspace',exact=True)
  expect(g.get_by_role('heading',name='Grow your business.')).to_be_visible()
  expect(g).to_contain_text('Needs sales data')
  g.get_by_role('button',name='Business profile',exact=True).click()
  form=g.locator('.growth-profile');form.get_by_label('Business name',exact=True).fill('Synthetic tea shop');form.get_by_label('Business goal',exact=True).fill('Validate product clarity with measured sales outcomes')
  form.get_by_label('Reporting timezone',exact=True).fill('Asia/Kolkata');form.get_by_label('Reporting currency',exact=True).fill('USD')
  form.get_by_role('button',name='Save business profile',exact=True).click();expect(g.locator('.growth-notice')).to_contain_text('Business profile saved')
  g.get_by_role('button',name='Create evidence conversation',exact=True).click();expect(g.get_by_label('Growth conversation')).not_to_have_value('');conversation=g.get_by_label('Growth conversation').input_value()
  g.get_by_label('Growth evidence file').set_input_files(str(root/'sample-data/ecommerce-sales.csv'));expect(g.locator('.growth-notice')).to_contain_text('Evidence uploaded')
  g.get_by_label('Growth research query').fill('Which products contribute sales and what should we validate?')
  g.get_by_role('button',name='Analyze growth evidence',exact=True).click();expect(g.locator('.growth-notice')).to_contain_text('Evidence snapshot saved')
  expect(g.get_by_role('heading',name='Market discussion signal',exact=True)).to_be_visible();expect(g).to_contain_text('45.10')
  g.get_by_role('button',name='Overview',exact=True).click();expect(g.locator('.growth-kpis')).to_contain_text('45.10 USD');expect(g.locator('.growth-product-bars meter')).to_have_count(2)
  page.screenshot(path=str(out/'growth-overview.png'),full_page=True)
  g.get_by_role('button',name=re.compile('^Action plan')).click();g.get_by_label('Growth analysis route',exact=True).select_option('evidence')
  g.get_by_role('button',name='Start growth workflow',exact=True).click();g.get_by_role('button',name='Approve & create brief',exact=True).wait_for(timeout=30000)
  expect(g.locator('#growth-outcomes')).to_contain_text('No approved experiment')
  page.goto(base+'/product-studio');page.goto(base+'/growth');expect(g.get_by_label('Growth conversation')).to_have_value(conversation)
  g.get_by_role('button',name=re.compile('^Action plan')).click();g.get_by_role('button',name='Approve & create brief',exact=True).wait_for(timeout=30000);g.get_by_role('button',name='Approve & create brief',exact=True).click()
  expect(g.locator('.execution-result')).to_contain_text('Verified execution');expect(g.locator('#growth-outcomes .growth-task')).to_have_count(3)
  page.screenshot(path=str(out/'growth-actions.png'),full_page=True)
  g.get_by_role('button',name='Evidence',exact=True).click();g.get_by_label('Growth evidence file').set_input_files(str(root/'sample-data/ecommerce-followup.csv'));expect(g.locator('.growth-notice')).to_contain_text('Evidence uploaded')
  g.get_by_role('button',name=re.compile('^Action plan')).click();outcomes=g.locator('#growth-outcomes');outcomes.get_by_label('Follow-up CSV',exact=True).select_option(label='ecommerce-followup.csv');outcomes.get_by_role('button',name='Compare observations',exact=True).click();expect(outcomes).to_contain_text('24.90')
  g.get_by_role('button',name='Plan a campaign',exact=True).click();campaign=g.locator('.growth-campaign')
  fields={'Campaign objective':'Synthetic educational test','Channel':'Email','Audience':'Consented customers','Consent / legal basis':'Explicit opt-in','Audience exclusions':'Opted-out customers','Copy / creative brief':'Learn how to use our product','Call to action':'Learn more','Destination (HTTPS)':'https://example.test/products','Schedule timezone (IANA)':'Asia/Kolkata','Start time (ISO with UTC offset)':'2026-11-01T09:00:00+05:30','Duration (days)':'14','Budget cap':'100','Budget currency':'USD','Attribution tags':'utm_source=email&utm_campaign=education','Measured baseline / unknown':'Unknown; collect before launch','Success metric':'Qualified activation','Guardrails / frequency limit':'One email per customer','Stop conditions':'Pause on consent failures'}
  for label,value in fields.items():campaign.get_by_label(label,exact=True).fill(value)
  campaign.get_by_role('button',name='Save campaign draft',exact=True).click();expect(g.locator('.growth-notice')).to_contain_text('Campaign draft saved');expect(g).to_contain_text('Synthetic educational test · Draft')
  g.get_by_role('button',name='Monitoring',exact=True).click();g.get_by_role('button',name='Schedule evidence review',exact=True).click();expect(g.locator('.growth-notice')).to_contain_text('Recurring evidence review saved');expect(g).to_contain_text('Never run')
  g.get_by_role('button',name='Pause review',exact=True).click();expect(g).to_contain_text('Paused')
  page.reload();expect(g.get_by_label('Growth conversation')).to_have_value(conversation);g.get_by_role('button',name='Monitoring',exact=True).click();expect(g).to_contain_text('Paused')
  page.screenshot(path=str(out/'growth-monitoring.png'),full_page=True)
  for width,height in [(1280,650),(1024,768),(390,844)]:
   page.set_viewport_size({'width':width,'height':height});g.get_by_role('button',name='Overview',exact=True).click()
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Horizontal overflow at {width}'
   for label in ['Evidence','Action plan','Monitoring']:
    g.get_by_role('button',name=re.compile('^'+label)).click();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'{label} overflow at {width}'
  g.get_by_role('button',name='Overview',exact=True).click();page.screenshot(path=str(out/'growth-mobile.png'),full_page=True)
  assert not errors,errors
  print('GROWTH WORKSPACE PASS: profile → scoped upload → immutable SQL snapshot → overview → restored pending run → human approval → verified internal tasks → measured follow-up → campaign draft → persisted paused schedule; desktop/mobile. Synthetic files and evidence mode; no live model/social delivery claimed.',flush=True)
  browser.close()
finally:
 for process in reversed(processes):
  process.terminate()
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 for log in logs:log.close()
