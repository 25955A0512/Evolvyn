"""Real browser acceptance: visible run results, connector setup and durable automations."""
import os,re
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect

root=Path(__file__).resolve().parents[1]
out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
base=os.getenv('EVOLVYN_TEST_URL','http://localhost:3000')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1536,'height':864});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base)
    page.get_by_role('button',name='Create account',exact=True).click()
    page.get_by_label('Workspace name',exact=True).fill('Experience acceptance')
    page.get_by_label('Email',exact=True).fill('experience-'+uuid4().hex+'@example.test')
    page.get_by_label('Password',exact=True).fill('experience-password-'+uuid4().hex)
    page.get_by_role('button',name='Create your workspace',exact=True).click()
    page.get_by_role('heading',name=re.compile('Your next idea')).wait_for()
    headers={'X-Requested-With':'Evolvyn'}
    def post(path,data):
        r=page.request.post(base+'/api'+path,headers=headers,data=data);assert r.ok,r.text()[:500];return r.json()
    conversation=post('/conversations',{'title':'Visible sales investigation'})
    page.reload()
    page.get_by_role('button',name=re.compile('^Visible sales investigation')).click()
    expect(page.locator('main > header')).to_contain_text('Visible sales investigation')
    page.locator('.composer input[type=file]').set_input_files(str(root/'sample-data/ecommerce-sales.csv'))
    expect(page.locator('.files')).to_contain_text('ecommerce-sales.csv')
    page.get_by_label('Analysis mode').select_option('evidence')
    interrupted=[]
    def interrupt_once(route):
        if not interrupted:
            interrupted.append(True);route.abort('failed')
        else:route.continue_()
    page.route('**/api/executions/*/live',interrupt_once)
    page.get_by_label('Message Evolvyn').fill('Calculate sales metrics and propose an investigation with a measurement plan.')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/runs')) as started:
        page.get_by_role('button',name='Run analysis',exact=True).click()
    run=started.value.json()
    page.locator('.run-summary').get_by_role('button',name='Review action',exact=True).wait_for(timeout=45000)
    assert interrupted, 'Live-stream recovery was not exercised'
    composer=page.locator('.composer').bounding_box()
    assert composer['height']<260,composer
    summary=page.locator('.run-summary').bounding_box()
    assert summary['y']+summary['height']<864,summary
    page.locator('.run-summary').get_by_role('button',name='View results',exact=True).click()
    metrics=page.get_by_label('Calculated e-commerce metrics').first
    expect(metrics).to_contain_text('45.10 USD')
    page.screenshot(path=str(out/'visible-agent-results.png'))
    page.locator('.run-summary').get_by_role('button',name='Review action',exact=True).click()
    page.get_by_role('button',name='Approve & create brief',exact=True).scroll_into_view_if_needed()
    assert not page.request.get(base+'/api/tasks').json()
    page.get_by_role('button',name='Ask platform help',exact=True).click()
    help=page.get_by_role('dialog',name='Evolvyn platform help')
    expect(help).to_contain_text('Support AI is not configured')
    help.get_by_label('Ask about Evolvyn').fill('How can I connect a tool?')
    help.get_by_role('button',name='Send help question').click()
    expect(help.get_by_role('alert')).to_contain_text('No AI answer was generated')
    help.get_by_role('button',name='Close platform help').click()
    page.get_by_role('button',name=re.compile('^Agent control center')).click()
    page.get_by_label('Search connector catalog').fill('Shopify')
    expect(page.locator('.connector-market-card')).to_have_count(1)
    expect(page.locator('.connector-market-card')).to_contain_text('not connected')
    page.get_by_role('button',name='Configure Shopify',exact=True).click()
    page.get_by_label('Search connector catalog').fill('Evidence utilities')
    page.get_by_role('button',name='Configure Evidence utilities',exact=True).click()
    page.locator('.connector-market-card').get_by_text(re.compile('MCP healthy')).wait_for(timeout=30000)
    page.get_by_label('Search connector catalog').fill('')
    page.screenshot(path=str(out/'connector-marketplace.png'))
    # Close the control center and enter the existing studio through home navigation.
    page.reload()
    page.get_by_role('button',name='Build a product',exact=True).click()
    studio=page.locator('.agent-workspace')
    studio.get_by_role('button',name='Canvas',exact=True).click()
    studio.get_by_role('button',name='Automations',exact=True).click()
    studio.locator('.automation-template').filter(has=page.get_by_role('heading',name='Conditional review',exact=True)).click()
    studio.get_by_label('Automation conversation').select_option(conversation['id'])
    studio.get_by_label('Name',exact=True).fill('Review low sales')
    studio.get_by_label('Automation goal').fill('Review net revenue and propose an evidence-linked investigation')
    studio.locator('select[name=mode]').select_option('evidence')
    studio.get_by_label('Metric threshold').fill('50')
    studio.get_by_role('button',name='Save automation',exact=True).click()
    studio.get_by_role('status').filter(has_text='Automation saved').wait_for()
    studio.get_by_role('button',name='Pause',exact=True).click()
    studio.get_by_role('button',name='Resume',exact=True).wait_for()
    studio.get_by_role('button',name='Resume',exact=True).click()
    # Existing run still awaits approval: reject it before the next review.
    post('/executions/'+run['id']+'/decision',{'approve':False,'plan':'Review a new automated run instead'})
    studio.get_by_role('button',name='Check latest upload',exact=True).click()
    studio.get_by_text(re.compile('Actual event history')).click()
    expect(studio.locator('.automation-event')).to_contain_text('QUEUED',timeout=30000)
    page.screenshot(path=str(out/'canvas-automations.png'))
    studio.get_by_role('button',name='Open conversation / results',exact=True).click()
    page.locator('.run-summary').get_by_role('button',name='Review action',exact=True).wait_for(timeout=45000)
    page.reload()
    page.get_by_role('button',name=re.compile('^Visible sales investigation')).click()
    page.locator('.run-summary').get_by_role('button',name='Review action',exact=True).wait_for()
    page.set_viewport_size({'width':1280,'height':650})
    assert page.locator('main > .scroll').bounding_box()['height']>200
    assert page.locator('.composer').bounding_box()['height']<260
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    page.screenshot(path=str(out/'visible-agent-mobile.png'))
    assert not errors,errors
    browser.close()
print('PASS: compact visible results, truthful connectors, unavailable help, saved conditional review, approval gate and mobile layout')
