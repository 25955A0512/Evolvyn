"""Public login UX + actual backend redirect/state/PKCE; provider pages are intercepted fixtures."""
import json,os,re,subprocess,time
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1];out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:3335';config=root/'.local/qa-public-oauth-vite.config.mjs'
config.write_text("import {defineConfig} from '../frontend/node_modules/vite/dist/node/index.js';export default defineConfig({root:"+repr(str(root/'frontend'))+",server:{host:'127.0.0.1',port:3335,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8892'}}}});")
processes=[];logs=[]
try:
 for name,command in [('api',[str(root/'.venv/bin/python'),'-m','uvicorn','qa_oauth_login_app:app','--host','127.0.0.1','--port','8892','--no-access-log']),('web',['node','frontend/node_modules/vite/bin/vite.js','--config',str(config)])]:
  log=(root/'.local'/('qa-public-oauth-'+name+'.log')).open('w');logs.append(log)
  processes.append(subprocess.Popen(command,cwd=root,env={**os.environ,'PYTHONPATH':str(root)+':'+str(root/'tests')},stdout=log,stderr=log))
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  page=browser.new_page(viewport={'width':1280,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  for _ in range(100):
   try:
    if page.request.get(base+'/api/health',timeout=1000).ok:break
   except Exception:pass
   if any(p.poll() is not None for p in processes):raise AssertionError('OAuth fixture failed; inspect private logs')
   time.sleep(.2)
  def unavailable(route):
   response=route.fetch();rows=response.json()
   for p in rows:p['enabled']=False
   route.fulfill(response=response,json=rows)
  def temporarily_down(route):route.fulfill(status=503,content_type='application/json',body='{}')
  page.route('**/api/auth/providers',temporarily_down);page.goto(base+'/login')
  expect(page.locator('.oauth-availability')).to_contain_text('could not be checked')
  expect(page.locator('.account-access .oauth-setup')).to_have_count(0)
  page.unroute('**/api/auth/providers',temporarily_down)
  page.route('**/api/auth/providers',unavailable)
  page.get_by_role('button',name='Retry sign-in options',exact=True).click()
  expect(page.get_by_role('button',name='Sign in with Google Unavailable',exact=True)).to_be_disabled()
  expect(page.get_by_role('button',name='Sign in with GitHub Unavailable',exact=True)).to_be_disabled()
  expect(page.locator('.oauth-availability')).to_contain_text('continue with email')
  expect(page.locator('.account-access .oauth-setup')).to_have_count(0)
  assert 'OAUTH_GOOGLE_CLIENT_SECRET' not in page.locator('.account-access').inner_text()
  page.screenshot(path=str(out/'public-oauth-unconfigured.png'))
  page.unroute('**/api/auth/providers',unavailable)
  # Configured provider: the actual API issues the redirect and browser-bound PKCE state.
  # We intercept the provider URL; no live account or Google/GitHub login is claimed.
  for provider,host,path in [('Google','accounts.google.com','/o/oauth2/v2/auth'),('GitHub','github.com','/login/oauth/authorize')]:
   page.route('https://'+host+'/**',lambda route:route.fulfill(status=200,content_type='text/html',body='<h1>Controlled provider authorization boundary</h1>'))
   page.goto(base+'/login');button=page.get_by_role('link',name='Sign in with '+provider,exact=True);expect(button).to_be_visible()
   assert button.get_attribute('href')=='/api/auth/oauth/'+provider.lower()+'/start'
   with page.expect_response(lambda response:response.url==base+'/api/auth/oauth/'+provider.lower()+'/start') as authorization:
    button.click(no_wait_after=True)
   response=authorization.value;assert response.status==303
   destination=response.headers['location'];u=urlsplit(destination);q=parse_qs(u.query)
   assert u.scheme=='https' and u.hostname==host
   assert u.path==path and q['code_challenge_method']==['S256'] and q['state'][0]
   assert q['redirect_uri']==[base+'/api/auth/oauth/'+provider.lower()+'/callback']
   assert 'controlled-ui-secret' not in destination and 'client_secret' not in q
  page.goto(base+'/signup');expect(page.get_by_role('link',name='Sign up with Google',exact=True)).to_be_visible()
  page.get_by_label('Workspace name',exact=True).fill('Controlled OAuth UI acceptance');page.get_by_label('Email',exact=True).fill('oauth-ui-'+uuid4().hex+'@example.test');page.get_by_label('Password',exact=True).fill('acceptance-'+uuid4().hex)
  page.get_by_role('button',name='Create your workspace',exact=True).click();page.wait_for_url(base+'/dashboard')
  page.goto(base+'/team-settings');page.get_by_text('Deployment sign-in setup',exact=True).click()
  expect(page.locator('.oauth-setup')).to_contain_text('Deployment administrator setup')
  page.set_viewport_size({'width':390,'height':844});page.goto(base+'/login')
  # Authenticated routes may redirect; start a separate browser context to inspect mobile signup.
  mobile=browser.new_page(viewport={'width':390,'height':844});mobile.goto(base+'/signup')
  expect(mobile.get_by_role('link',name='Sign up with Google',exact=True)).to_be_visible()
  assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
  mobile.screenshot(path=str(out/'public-oauth-configured-mobile.png'),full_page=True)
  assert not errors,errors
  print('PUBLIC OAUTH PASS: compact unavailable state, no public deployment instructions, actual configured Google/GitHub start redirects with PKCE/browser state, email signup preserved, authenticated owner setup, mobile. Provider pages are controlled fixtures; live OAuth credentials still required.')
  browser.close()
finally:
 for process in reversed(processes):
  process.terminate()
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 for log in logs:log.close()
