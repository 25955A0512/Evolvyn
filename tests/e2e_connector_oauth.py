"""Browser authorization redirects and real DB/vault/MCP, controlled consent/HTTP boundary."""
import hashlib,hmac,os,subprocess,time
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1];base='http://127.0.0.1:3333';out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
config=root/'.local/qa-connector-vite.config.mjs'
config.write_text("import {defineConfig} from '../frontend/node_modules/vite/dist/node/index.js';export default defineConfig({root:"+repr(str(root/'frontend'))+",server:{host:'127.0.0.1',port:3333,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8890'}}}});")
processes=[];logs=[]
try:
 for name,command in [('api',[str(root/'.venv/bin/python'),'-m','uvicorn','qa_business_connectors_app:app','--host','127.0.0.1','--port','8890','--no-access-log']),('web',['node','frontend/node_modules/vite/bin/vite.js','--config',str(config)])]:
  log=(root/'.local'/('qa-connector-'+name+'.log')).open('w');logs.append(log);processes.append(subprocess.Popen(command,cwd=root,env={**os.environ,'PYTHONPATH':str(root)+':'+str(root/'tests')},stdout=log,stderr=log))
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);page=browser.new_page(viewport={'width':1440,'height':960});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  for _ in range(100):
   try:
    if page.request.get(base+'/api/health',timeout=1000).ok:break
   except Exception:pass
   if any(p.poll() is not None for p in processes):raise AssertionError('Connector fixture failed')
   time.sleep(.2)
  r=page.request.post(base+'/api/auth/register',data={'email':uuid4().hex+'@example.test','password':'synthetic-connector-browser-password','name':'Connector browser'},headers={'X-Requested-With':'Evolvyn'});assert r.ok
  seen=[]
  def consent(route):
   url=urlparse(route.request.url);params=parse_qs(url.query);provider='google_drive' if url.hostname=='accounts.google.com' else 'slack' if url.hostname=='slack.com' else 'shopify';seen.append(provider)
   callback={'state':params['state'][0],'code':'synthetic-code'}
   if provider=='shopify':
    callback.update(shop='synthetic-store.myshopify.com',timestamp=str(int(time.time())))
    callback['hmac']=hmac.new(b'synthetic-secret-shopify',urlencode(sorted(callback.items())).encode(),hashlib.sha256).hexdigest()
   target=params['redirect_uri'][0]+'?'+urlencode(callback)
   route.fulfill(status=200,content_type='text/html',body='<script>location.href='+__import__('json').dumps(target)+'</script>')
  for pattern in ['https://accounts.google.com/o/oauth2/v2/auth**','https://slack.com/oauth/v2/authorize**','https://synthetic-store.myshopify.com/admin/oauth/authorize**']:page.route(pattern,consent)
  # Load the registry first: no AgentWorkspace CSS may have been cached.
  page.goto(base+'/mcp-registry')
  expect(page.locator('.control-nav > button')).to_have_count(2)
  expect(page.locator('.control-nav').get_by_role('button',name='Agent harness',exact=False)).to_have_count(0)
  expect(page.locator('.control-nav').get_by_role('button',name='Governance',exact=False)).to_have_count(0)
  accounts=page.get_by_role('region',name='OAuth accounts')
  accounts.locator('.dashboard-connector-card').filter(has=page.get_by_role('heading',name='Google Drive',exact=True)).get_by_role('button',name='Setup',exact=True).click()
  dialog=page.get_by_role('dialog',name='Google Drive setup');expect(dialog).to_be_visible()
  assert dialog.get_by_label('Redirect URL').evaluate("e=>getComputedStyle(e.parentElement).display")=='grid'
  assert dialog.get_by_label('Redirect URL').evaluate("e=>e.getBoundingClientRect().width")>300
  for width,height in [(1440,650),(390,700)]:
   page.set_viewport_size({'width':width,'height':height})
   action=dialog.get_by_role('button',name='Continue to Google Drive')
   expect(action).to_be_enabled();expect(action).to_be_in_viewport()
   assert dialog.evaluate('e=>e.scrollWidth<=e.clientWidth')
  page.screenshot(path=str(out/'registry-drive-setup-mobile.png'))
  page.keyboard.press('Escape');page.set_viewport_size({'width':1440,'height':960})
  names={'google_drive':'Google Drive','slack':'Slack','shopify':'Shopify'}
  for provider,name in names.items():
   page.goto(base+'/integrations');page.get_by_role('button',name='Connect '+name,exact=True).click()
   if provider=='shopify':
    dialog=page.get_by_role('dialog',name='Shopify setup');dialog.get_by_label('Shopify store hostname').fill('synthetic-store.myshopify.com');dialog.get_by_role('button',name='Continue to Shopify').click()
   page.wait_for_url('**/integrations?connection='+provider,timeout=30000)
   accounts=page.get_by_role('region',name='OAuth accounts');card=accounts.locator('.dashboard-connector-card').filter(has=page.get_by_role('heading',name=name,exact=True));expect(card).to_contain_text('connected');expect(card).to_contain_text('Synthetic')
   card.get_by_role('button',name='Test connection',exact=True).click();expect(accounts.get_by_role('status')).to_contain_text(name+': connected',timeout=20000)
  assert seen==list(names)
  page.screenshot(path=str(out/'oauth-business-accounts.png'),full_page=True)
  accounts=page.get_by_role('region',name='OAuth accounts');accounts.get_by_role('button',name='Disconnect Slack',exact=True).click();page.get_by_role('dialog',name='Disconnect account').get_by_role('button',name='Disconnect',exact=True).click();expect(accounts).to_contain_text('Local credentials erased')
  page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.get_by_label('Search integrations').fill('Shopify');expect(accounts.get_by_role('heading',name='Shopify',exact=True)).to_be_visible();expect(accounts.get_by_role('heading',name='Google Drive',exact=True)).to_have_count(0)
  page.goto(base+'/product-studio');expect(page.locator('.studio-sidebar').get_by_role('button',name='Canvas',exact=True)).to_have_count(0)
  page.goto(base+'/dashboard');expect(page.get_by_text('Open Canvas',exact=True)).to_have_count(0)
  page.goto(base+'/canvas');expect(page.get_by_role('heading',name='Page not found',exact=True)).to_be_visible()
  assert not errors,errors
  browser.close();print('CONNECTOR OAUTH PASS: Drive/Slack/Shopify consent redirect → controlled provider HTTP → verified identity → encrypted vault → actual stdio MCP registration → connection tests → disconnect confirmation → mobile/search. No live provider acceptance claimed.',flush=True)
finally:
 for p in reversed(processes):
  p.terminate()
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 for log in logs:log.close()
