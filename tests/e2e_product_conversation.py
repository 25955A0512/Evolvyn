"""Actual local-model browser acceptance for chat-first planning and restored builds.
Requires the running app, PostgreSQL, local Qwen and private compiler. No model
response or execution result is replaced in this test.
"""
import os,re,time
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
base=os.getenv('EVOLVYN_TEST_URL','http://localhost:3000')
out=Path('.local/validation');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1600,'height':1050});errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto(base+'/signup')
 page.get_by_label('Workspace name',exact=True).fill('Synthetic conversational builder acceptance')
 page.get_by_label('Email',exact=True).fill('chat-studio-'+uuid4().hex+'@example.test')
 page.get_by_label('Password',exact=True).fill('acceptance-'+uuid4().hex)
 page.get_by_role('button',name='Create your workspace',exact=True).click()
 page.wait_for_url(base+'/dashboard')
 def get(path):
  r=page.request.get(base+'/api'+path);assert r.ok,(path,r.status);return r.json()
 def finished(id):
  for _ in range(330):
   run=get('/executions/'+id)
   if run['state'] not in ('CREATED','RUNNING'):return run
   time.sleep(1)
  raise AssertionError('Workflow exceeded acceptance time budget')
 page.goto(base+'/product-studio');studio=page.locator('.intelligent-product-studio')
 expect(studio.get_by_role('heading',name='What would you like to build?',exact=True)).to_be_visible()
 expect(studio.locator('.product-deliverables')).to_be_hidden()
 assert not studio.get_by_label('AI product name',exact=True).count()
 assert studio.locator('.product-conversation').bounding_box()['width']>900
 page.screenshot(path=str(out/'product-chat-first.png'))
 studio.get_by_label('Product agent model route',exact=True).select_option('local')
 studio.get_by_label('Message product agents',exact=True).fill('Build a private clothing product catalog for a small shop. Track products with a name and price, private accounts and create/view/delete records. Use React FastAPI PostgreSQL, light theme and green accent. No payments or external integrations in the first version.')
 with page.expect_response(lambda r:'/studio/products/' in r.url and r.url.endswith('/messages') and r.request.method=='POST') as response:
  studio.get_by_role('button',name='Send to product agents',exact=True).click()
 assert response.value.status==202
 interview=response.value.json();product_id=studio.get_by_label('Agent product',exact=True).input_value()
 assert product_id and 'product='+product_id in page.url
 # Leave while the model works: the backend execution must persist independently.
 page.locator('.studio-sidebar').get_by_role('button',name='Growth insights',exact=True).click()
 page.wait_for_url(base+'/growth')
 page.locator('.studio-sidebar').get_by_role('button',name='Build a product',exact=True).click()
 page.wait_for_url(re.compile('/product-studio'))
 expect(studio.get_by_label('Agent product',exact=True)).to_have_value(product_id)
 plan=finished(interview['id']);assert plan['state']=='COMPLETED',plan.get('error')
 proposal=plan['graph_checkpoint']['nodes']['proposal']['output']
 assert len(proposal['proposed_requirements'])==11,proposal
 studio.get_by_role('button',name='Confirm setup & start building',exact=True).wait_for(timeout=10000)
 page.screenshot(path=str(out/'product-chat-proposed-setup.png'))
 with page.expect_response(lambda r:r.url.endswith('/confirm-and-build')) as response:
  studio.get_by_role('button',name='Confirm setup & start building',exact=True).click()
 result=response.value.json();assert result.get('execution'),result
 run_id=result['execution']['id']
 page.locator('.studio-sidebar').get_by_role('button',name='Growth insights',exact=True).click()
 page.wait_for_url(base+'/growth')
 page.locator('.studio-sidebar').get_by_role('button',name='Build a product',exact=True).click()
 page.wait_for_url(re.compile('/product-studio'))
 expect(studio.get_by_label('Agent product',exact=True)).to_have_value(product_id)
 expect(studio.locator('.product-run-feed')).to_be_visible()
 assert get('/studio/products/'+product_id)['last_build_run']==run_id
 page.screenshot(path=str(out/'product-chat-restored-build.png'))
 final=finished(run_id)
 reviewer_requested_changes=False
 if final['state']=='COMPLETED' and final.get('graph_checkpoint',{}).get('nodes',{}).get('contracts',{}).get('output',{}).get('can_build') is False:
  # A real LLM is allowed to disagree. Verify that its rejection blocks source,
  # then exercise the existing user-selectable three-agent + human review path.
  reviewer_requested_changes=True
  assert not get('/studio/builds')
  expect(studio.locator('.product-run-feed')).to_contain_text('reviewer requested changes')
  page.screenshot(path=str(out/'product-chat-review-request.png'))
  studio.get_by_role('button',name='Overview & agents',exact=True).click()
  studio.get_by_label('Enable Quality reviewer',exact=True).uncheck()
  with page.expect_response(lambda r:r.url.endswith('/agent-build')) as response:
   studio.get_by_role('button',name='Run product agents',exact=True).click()
  run_id=response.value.json()['id'];final=finished(run_id)
 assert final['state']=='WAITING_FOR_APPROVAL',(final['state'],final.get('error'),final.get('graph_checkpoint',{}).get('nodes',{}).get('contracts'))
 studio.get_by_role('button',name=re.compile('^Open planned folder structure')).click()
 expect(studio.get_by_role('navigation',name='Project file tree',exact=True)).to_be_visible()
 expect(studio.locator('.product-source-code')).to_contain_text('contents pending approval')
 assert not get('/studio/builds')
 page.screenshot(path=str(out/'product-chat-planned-tree.png'))
 studio.get_by_role('button',name='Approve source implementation',exact=True).click()
 studio.get_by_text('Source ready · runtime not started',exact=True).first.wait_for(timeout=90000)
 final=get('/executions/'+run_id);assert final['state']=='COMPLETED',final.get('error')
 build_id=final['graph_checkpoint']['nodes']['implementation']['output']['id'];build=get('/studio/builds/'+build_id)
 assert build['frontend_build']['status']=='passed',build.get('frontend_build')
 assert build['files']['backend/app.py'] and build['files']['docs/PRD.md']
 page.reload();expect(studio.get_by_label('Agent product',exact=True)).to_have_value(product_id)
 expect(studio.locator('.product-run-feed')).to_contain_text('Source ready')
 if studio.get_by_role('button',name='Open workspace',exact=True).is_visible():studio.get_by_role('button',name='Open workspace',exact=True).click()
 studio.get_by_role('button',name='Source tree',exact=True).click()
 expect(studio.get_by_role('navigation',name='Project file tree',exact=True)).to_be_visible()
 page.screenshot(path=str(out/'product-chat-generated-tree.png'))
 page.set_viewport_size({'width':390,'height':844})
 studio.get_by_role('button',name='Hide workspace',exact=True).click()
 studio.get_by_role('button',name='New product',exact=True).click()
 expect(studio.get_by_role('heading',name='What would you like to build?',exact=True)).to_be_visible()
 assert studio.evaluate('(node)=>node.scrollWidth<=node.clientWidth+1')
 page.screenshot(path=str(out/'product-chat-mobile.png'),full_page=True)
 page.reload();expect(studio.get_by_role('heading',name='What would you like to build?',exact=True)).to_be_visible()
 # The previous project is retained even after explicitly opening a new conversation.
 studio.get_by_label('Agent product',exact=True).select_option(product_id)
 expect(studio.locator('.product-run-feed')).to_contain_text('Source ready')
 assert not errors,errors
 print('LIVE REVIEW RESULT: '+('four-agent rejection blocked source; explicit three-agent + human-review build verified' if reviewer_requested_changes else 'four-agent design review accepted, then human source approval verified'),flush=True)
 print('CHAT STUDIO PASS: actual local model → complete proposed setup → confirm starts durable graph → navigate away/back during both runs → planned folder tree → approval → real compiled source → reload restoration → mobile/new-product/history',flush=True)
 browser.close()
