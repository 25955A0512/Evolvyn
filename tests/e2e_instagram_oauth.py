"""Browser acceptance with an explicitly synthetic upstream MCP response."""
import os,subprocess,time
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1];out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:3334';config=root/'.local/qa-instagram-vite.config.mjs'
config.write_text("import {defineConfig} from '../frontend/node_modules/vite/dist/node/index.js';export default defineConfig({root:"+repr(str(root/'frontend'))+",server:{host:'127.0.0.1',port:3334,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8891'}}}});")
logs=[];processes=[]
try:
 for name,command in [('api',[str(root/'.venv/bin/python'),'-m','uvicorn','qa_instagram_app:app','--host','127.0.0.1','--port','8891','--no-access-log']),('web',['node','frontend/node_modules/vite/bin/vite.js','--config',str(config)])]:
  log=(root/'.local'/('qa-instagram-'+name+'.log')).open('w');logs.append(log);processes.append(subprocess.Popen(command,cwd=root,env={**os.environ,'PYTHONPATH':str(root)+':'+str(root/'tests')},stdout=log,stderr=log))
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);page=browser.new_page(viewport={'width':1440,'height':960});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  for _ in range(100):
   try:
    if page.request.get(base+'/api/health',timeout=1000).ok:break
   except Exception:pass
   if any(p.poll() is not None for p in processes):raise AssertionError('QA fixture failed; inspect private logs')
   time.sleep(.2)
  headers={'X-Requested-With':'Evolvyn'}
  def post(path,data):
   r=page.request.post(base+'/api'+path,data=data,headers=headers);assert r.ok,r.status;return r.json()
  post('/auth/register',{'email':'social-'+uuid4().hex+'@example.test','password':'social-acceptance-'+uuid4().hex,'name':'Synthetic social acceptance'})
  conv=post('/conversations',{'title':'Instagram OAuth evidence'})
  page.goto(base+'/growth');g=page.get_by_label('Business growth workspace',exact=True)
  g.get_by_label('Growth conversation').select_option(conv['id']);g.get_by_role('button',name='Social intelligence',exact=True).click();social=g.locator('.social-growth')
  expect(social.get_by_role('button',name='Connect with Instagram',exact=True)).to_be_enabled()
  page.route('https://www.instagram.com/oauth/authorize?**',lambda route:route.fulfill(status=200,content_type='text/html',body='<h1>Synthetic Instagram authorization boundary</h1>'))
  social.get_by_role('button',name='Connect with Instagram',exact=True).click();page.wait_for_url('https://www.instagram.com/oauth/authorize?**')
  from urllib.parse import urlparse,parse_qs
  query=parse_qs(urlparse(page.url).query);assert query['scope']==['instagram_business_basic']
  page.goto(base+'/api/integrations/instagram/callback?state='+query['state'][0]+'&code=synthetic-browser-code')
  page.wait_for_url(base+'/growth?**');expect(g.get_by_label('Growth conversation')).to_have_value(conv['id'])
  expect(social).to_contain_text('Instagram · synthetic_oauth_shop',timeout=15000)
  expect(social).to_contain_text('Not verified yet');expect(social).to_contain_text('Instagram authorization expires')
  social.get_by_role('button',name='Sync account',exact=True).click();expect(social).to_contain_text('Verified observation saved',timeout=15000)
  expect(social.locator('.growth-kpis')).to_contain_text('10');expect(social.get_by_role('table')).to_contain_text('Synthetic tea product');expect(social).to_contain_text('At least 29 comparable daily')
  social.get_by_text('Permitted comment sample · 1',exact=True).click();expect(social).to_contain_text('[handle redacted] please add blue packaging')
  social.get_by_label('Review model route',exact=True).select_option('evidence');social.get_by_role('button',name='Run business + research + strategy review',exact=True).click();expect(social).to_contain_text('Saved specialist review · COMPLETED',timeout=15000)
  with page.expect_download() as download:social.get_by_role('button',name='Export evidence report',exact=True).click()
  assert download.value.suggested_filename=='social-growth-report.json'
  social.get_by_role('button',name='Enable social monitoring',exact=True).click();expect(social).to_contain_text('Social monitoring scheduled')
  social.get_by_role('button',name='Pause social monitoring',exact=True).click();expect(social).to_contain_text('Social monitoring paused')
  page.goto(base+'/product-studio');page.goto(base+'/growth');g.get_by_role('button',name='Social intelligence',exact=True).click();expect(social).to_contain_text('Instagram · synthetic_oauth_shop');expect(social).to_contain_text('Saved specialist review · COMPLETED');expect(social).to_contain_text('Paused · Next due')
  page.screenshot(path=str(out/'instagram-oauth-desktop.png'),full_page=True)
  for width,height in [(1280,650),(390,844)]:
   page.set_viewport_size({'width':width,'height':height});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Overflow at {width}'
  page.screenshot(path=str(out/'instagram-oauth-mobile.png'),full_page=True)
  social.get_by_role('button',name='Disconnect source',exact=True).click();expect(social).to_contain_text('Disconnected: polling stopped');expect(social.get_by_role('button',name='Sync account',exact=True)).to_be_disabled()
  assert not errors,errors
  print('INSTAGRAM OAUTH BROWSER PASS: authorize click → browser-bound synthetic provider callback → encrypted token + native source → restored social workspace → synthetic upstream sync → durable metrics/comments → three evidence-role handoffs → JSON export → monitor/pause → navigation persistence → mobile → disconnect. No live provider/model claimed.',flush=True)
  browser.close()
finally:
 for p in reversed(processes):
  p.terminate()
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 for log in logs:log.close()
