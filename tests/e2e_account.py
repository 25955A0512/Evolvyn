from playwright.sync_api import sync_playwright
from uuid import uuid4
from pathlib import Path
import os
base=os.getenv('EVOLVYN_TEST_URL','http://127.0.0.1:5173')
email='browser-'+uuid4().hex[:8]+'@example.test'
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('response',lambda r:print('API ERROR',r.status,r.url,r.text()[:300],flush=True) if '/api/' in r.url and r.status>=400 else None)
 page.goto(base+'/')
 page.get_by_role('button',name='Create account',exact=True).click()
 page.get_by_label('Workspace name',exact=True).fill('Account acceptance')
 page.get_by_label('Email',exact=True).fill(email)
 page.get_by_label('Password',exact=True).fill('browser-test-password-123')
 page.get_by_role('button',name='Create your workspace',exact=True).click()
 page.get_by_role('button',name='Add business',exact=True).wait_for()
 page.get_by_role('button',name='Add business',exact=True).click()
 page.get_by_label('Business name',exact=True).fill('Account SaaS')
 page.get_by_label('Business goal',exact=True).fill('Improve activation with cited evidence')
 page.get_by_role('button',name='Create business',exact=True).click()
 page.get_by_role('dialog').wait_for(state='hidden')
 page.get_by_label('Message Evolvyn').fill('Investigate onboarding friction using the uploaded evidence')
 page.locator('input[type=file]').set_input_files('/workspace/Evolvyn/sample-data/customer-feedback.txt')
 page.locator('.files').wait_for()
 page.get_by_label('Analysis mode').select_option('evidence')
 page.get_by_role('button',name='Run analysis').click()
 page.get_by_role('button',name='Approve & create brief').wait_for(timeout=30000)
 assert page.locator('.recommendation').count()==3
 page.get_by_role('button',name='Approve & create brief').click()
 page.get_by_role('button',name='Open saved experiment brief').wait_for()
 page.reload()
 page.get_by_role('button',name='Investigate onboarding friction using the uploaded evidence').click()
 page.get_by_role('button',name='Open saved experiment brief').wait_for()
 page.get_by_role('button',name='Agent workflow & tools',exact=True).click()
 page.get_by_role('img',name='Editable business improvement workflow').wait_for()
 page.get_by_label('Workflow name',exact=True).fill('Browser workflow acceptance')
 page.get_by_label('Workflow model',exact=True).select_option('evidence')
 page.get_by_label('Recommendations',exact=True).fill('1')
 node=page.locator('svg.workflow-canvas g').first
 box=node.bounding_box()
 page.mouse.move(box['x']+60,box['y']+30);page.mouse.down();page.mouse.move(box['x']+90,box['y']+45,steps=5);page.mouse.up()
 page.get_by_role('button',name='Save workflow',exact=True).click()
 page.get_by_text('Workflow saved',exact=True).wait_for()
 page.screenshot(path='/workspace/Evolvyn/.local/validation/workflow-canvas.png',full_page=True)
 page.get_by_role('button',name='Run in this conversation').click()
 page.get_by_text('Workflow started in your conversation',exact=True).wait_for()
 page.get_by_role('button',name='Close workspace panel',exact=True).click()
 page.get_by_role('button',name='Approve & create brief').wait_for(timeout=30000)
 assert page.locator('.recommendations').last.locator('.recommendation').count()==1
 page.get_by_label('Open account menu',exact=True).click()
 page.get_by_role('button',name='Account & team',exact=True).click()
 page.get_by_role('heading',name='Account & team',exact=True).wait_for()
 page.get_by_role('dialog',name='Workspace settings',exact=True).get_by_text(email,exact=True).first.wait_for()
 page.screenshot(path='/workspace/Evolvyn/.local/validation/account-team.png',full_page=True)
 assert not errors,errors
 print('Browser account registration, organization session, private upload/analysis/approval, refresh, team panel: PASS')
 b.close()
