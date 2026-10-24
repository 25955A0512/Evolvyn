"""Live browser check: routing, setup UX, vault defaults and actual PRD DOCX export."""
import io,os,re,zipfile
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
base=os.getenv('EVOLVYN_TEST_URL','http://localhost:3000')
out=Path('.local/validation');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto(base+'/signup')
 expect(page.get_by_role('button',name=re.compile('^Sign up with Google'))).to_be_visible()
 page.get_by_role('button',name=re.compile('^Sign up with Google')).click()
 expect(page.locator('.oauth-setup')).to_contain_text('/api/auth/oauth/google/callback')
 page.get_by_label('Workspace name',exact=True).fill('Synthetic connected acceptance')
 page.get_by_label('Email',exact=True).fill('connected-'+uuid4().hex+'@example.test')
 page.get_by_label('Password',exact=True).fill('acceptance-'+uuid4().hex)
 page.get_by_role('button',name='Create your workspace',exact=True).click()
 page.wait_for_url(base+'/dashboard')
 page.evaluate("sessionStorage.setItem('evolvyn-organization','stale-organization')")
 page.goto(base+'/auth/callback');page.wait_for_url(base+'/dashboard')
 headers={'X-Requested-With':'Evolvyn'}
 def get(path):
  response=page.request.get(base+'/api'+path);assert response.ok,(path,response.status);return response.json()
 def post(path,body,method='POST'):
  response=page.request.fetch(base+'/api'+path,method=method,data=body,headers=headers);assert response.ok,(path,response.status,response.text()[:300]);return response.json()
 for route,text in [('/product-studio','Build your next business product.'),('/discussionroom','Think it through with your team.'),('/keyvault','One default. The right key for every agent.'),('/mcp-registry','Connect your agent tools.'),('/monitoring','Keep the loop running'),('/workflows','Inside the workflow'),('/integrations','Connect GitHub to Evolvyn'),('/team-settings','Account & team'),('/audit-logs','Workspace audit logs')]:
  page.goto(base+route);page.get_by_role('heading',name=text,exact=True).wait_for(timeout=20000)
  page.reload();page.get_by_role('heading',name=text,exact=True).wait_for(timeout=20000)
  assert page.url==base+route
 page.goto(base+'/product-studio')
 page.locator('.agent-workspace').get_by_role('button',name='Key vault',exact=True).click();page.wait_for_url(base+'/keyvault')
 page.go_back();page.get_by_role('heading',name='Build your next business product.',exact=True).wait_for()
 page.goto(base+'/integrations');page.get_by_role('button',name='Connect GitHub',exact=True).click()
 expect(page.locator('.oauth-setup')).to_contain_text('OAUTH_GITHUB_CLIENT_ID')
 page.screenshot(path=str(out/'github-oauth-setup.png'))
 # Synthetic credential only: validates routing UI, never used for a model call.
 credential=post('/vault/credentials',{'name':'Synthetic routing test · not a live API key','provider':'gemini','value':'unit-not-real-'+uuid4().hex})
 page.goto(base+'/keyvault')
 page.get_by_role('button',name='Use for all agents',exact=True).click()
 page.get_by_role('status').filter(has_text='All agents now inherit this key').wait_for()
 assert all(r['provider']=='gemini' for r in get('/vault')['effective_routes'].values())
 page.screenshot(path=str(out/'gemini-default-routes.png'))
 page.request.delete(base+'/api/vault/credentials/'+credential['id'],headers=headers)
 product=post('/studio/products',{'name':'Synthetic PRD workspace','goal':'An e-commerce clothing catalog and order tracker'})
 page.goto(base+'/product-studio')
 page.get_by_label('Agent product',exact=True).select_option(product['id'])
 page.get_by_role('button',name='PRD',exact=True).click()
 page.get_by_role('button',name='Edit PRD draft',exact=True).click()
 page.get_by_label('PRD draft',exact=True).fill('# Clothing storefront\nUsers browse clothing and track orders.\nAcceptance: private accounts and persisted orders.')
 page.get_by_role('button',name='Save PRD draft',exact=True).click()
 expect(page.locator('.product-workbench-pane')).to_contain_text('Document revision 1')
 with page.expect_download() as download:page.get_by_role('button',name='Download PRD · DOCX',exact=True).click()
 path=out/'synthetic-prd.docx';download.value.save_as(path)
 with zipfile.ZipFile(path) as doc:assert b'Users browse clothing' in doc.read('word/document.xml')
 page.reload();page.get_by_label('Agent product',exact=True).select_option(product['id']);page.get_by_role('button',name='PRD',exact=True).click()
 expect(page.locator('.product-workbench-pane')).to_contain_text('Clothing storefront')
 page.screenshot(path=str(out/'editable-prd-docx.png'))
 page.set_viewport_size({'width':1050,'height':950})
 assert page.locator('.product-deliverable-tabs').evaluate('(node)=>node.scrollWidth<=node.clientWidth+1')
 page.screenshot(path=str(out/'product-readable-layout.png'))
 page.goto(base+'/not-a-route');expect(page.get_by_role('heading',name='Page not found',exact=True)).to_be_visible()
 assert not errors,errors
 browser.close()
 print('CONNECTED ROUTES PASS: OAuth setup → signup → every module deep link/refresh → back navigation → GitHub setup → Gemini all-agent binding → editable persisted PRD → real DOCX download → readable layout/no browser errors')
