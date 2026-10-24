"""Real browser vertical slice through the existing chat, tools, approvals and outcomes UI."""
import json,os,re
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect

root=Path(__file__).resolve().parents[1]
out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
base=os.getenv('EVOLVYN_TEST_URL','http://localhost:3000')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1536,'height':960});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base)
    page.get_by_role('button',name='Create account',exact=True).click()
    page.get_by_label('Workspace name',exact=True).fill('Northstar merchant team')
    page.get_by_label('Email',exact=True).fill('commerce-'+uuid4().hex+'@example.test')
    page.get_by_label('Password',exact=True).fill('commerce-browser-password-'+uuid4().hex)
    page.get_by_role('button',name='Create your workspace',exact=True).click()
    page.get_by_role('button',name='Add business',exact=True).click()
    page.get_by_label('Business name',exact=True).fill('Northstar Tea Shop')
    page.locator('select[name=kind]').select_option('ecommerce')
    page.get_by_label('Product or service',exact=True).fill('Tea and mugs')
    page.get_by_label('Business goal',exact=True).fill('Use sales evidence to prioritize product improvements')
    page.get_by_role('button',name='Create business',exact=True).click()
    page.get_by_role('dialog').wait_for(state='hidden')
    assert page.request.get(base+'/api/businesses').json()[0]['kind']=='ecommerce'
    page.locator('.composer input[type=file]').set_input_files(str(root/'sample-data/ecommerce-sales.csv'))
    page.locator('.files').get_by_text('Parsed sales data').wait_for()
    headers={'X-Requested-With':'Evolvyn'}
    def post(path,data):
        r=page.request.post(base+'/api'+path,headers=headers,data=data);assert r.ok,r.text()[:500];return r.json()
    # Real bundled transport, not a fabricated third-party connection.
    server=post('/mcp/servers',{'name':'Merchant comparison evidence','profile':'evidence_utilities'})
    assert post('/mcp/servers/'+server['id']+'/probe',{})['status']=='healthy'
    post('/tool-registry',{'name':'merchant.compare','description':'Compare observed rates, without inferring market growth','adapter':'mcp','server_id':server['id'],'remote_tool':'compare_rates','entities':['sales']})
    picker=page.locator('.composer .tool-access')
    picker.locator('summary').first.click()
    picker.get_by_role('button',name='Refresh available connections').click()
    picker.get_by_role('checkbox',name='merchant.compare',exact=True).check()
    picker.get_by_label('Arguments for merchant.compare').fill(json.dumps({'before':4,'after':6}))
    picker.get_by_label('Arguments for merchant.compare').press('Tab')
    picker.locator('summary').first.click()
    page.get_by_label('Analysis mode').select_option('evidence')
    page.get_by_text('Market research options',exact=True).click()
    page.get_by_label('Include public research',exact=True).check()
    page.get_by_label('Public research query',exact=True).fill('ecommerce retail')
    page.get_by_label('Message Evolvyn').fill('Calculate revenue, orders, average order value and product performance. Propose one evidence-linked investigation, with risks and a measurement plan.')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/runs')) as started:
        page.get_by_role('button',name='Run analysis',exact=True).click()
    assert started.value.ok,started.value.text()
    execution_id=started.value.json()['id']
    page.get_by_role('button',name='Approve & create brief',exact=True).wait_for(timeout=65000)
    metrics=page.get_by_label('Calculated e-commerce metrics').first
    expect(metrics).to_contain_text('45.10 USD')
    expect(metrics).to_contain_text('22.55 USD')
    expect(metrics).to_contain_text('30.10')
    result=page.request.get(base+'/api/executions/'+execution_id).json()
    assert result['report']['commerce']['primary']['orders']==2
    assert result['report']['connector_status'][0]['status']=='succeeded'
    market=result['report']['research_status']['status']
    if market=='succeeded':
        for s in result['report'].get('market_sources',[]):assert s['url'].startswith('https://news.ycombinator.com/') and s['retrieved_at']
    else:assert market=='unavailable' and not result['report'].get('market_sources')
    assert page.request.get(base+'/api/tasks').json()==[]
    if page.locator('.chat-research').get_attribute('open') is not None:page.get_by_text('Market research options',exact=True).click()
    metrics.scroll_into_view_if_needed()
    page.screenshot(path=str(out/'ecommerce-analysis.png'))
    page.get_by_role('button',name='Approve & create brief',exact=True).click()
    page.locator('.execution-result').filter(has_text='3 tracked tasks').wait_for()
    persisted=page.request.get(base+'/api/executions/'+execution_id).json()
    assert persisted['execution_result']['verified_task_count']==3
    artifact=persisted['artifact']
    page.locator('.composer input[type=file]').set_input_files(str(root/'sample-data/ecommerce-followup.csv'))
    expect(page.locator('.files')).to_contain_text('ecommerce-followup.csv')
    page.get_by_role('button',name='Saved reports & outcomes',exact=True).click()
    panel=page.locator('.platform-panel')
    report=panel.locator('.saved-report').filter(has_text='Saved sales baseline')
    expect(report).to_contain_text('45.10 USD')
    conversation=page.request.get(base+'/api/conversations').json()[0]
    followup=next(f for f in conversation['files'] if f['name']=='ecommerce-followup.csv')
    report.locator('select[name=document_id]').select_option(followup['id'])
    report.locator('button').filter(has_text=re.compile('Compare|Measure|Save')).last.click()
    expect(report.locator('.measurement')).to_contain_text('24.90')
    expect(report.locator('.measurement')).to_contain_text('not causal')
    report.locator('.measurement').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'ecommerce-outcome.png'))
    panel.get_by_role('button',name='Close workspace panel').click()
    page.get_by_role('button',name=re.compile('^Agent control center')).click()
    page.get_by_text('What does the Agent control center do?',exact=True).click()
    expect(page.locator('.control-purpose')).to_contain_text('same connections')
    boxes=page.locator('.control-nav>button').evaluate_all('rows=>rows.map(e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height}})')
    assert all(boxes[i]['bottom']<=boxes[i+1]['top'] for i in range(len(boxes)-1)),boxes
    assert all(b['height']>=82 for b in boxes)
    page.screenshot(path=str(out/'control-center-readable.png'))
    page.get_by_role('button',name='Close agent control center',exact=True).click()
    page.reload()
    messages=page.request.get(base+'/api/conversations/'+conversation['id']).json()['messages']
    assert any(m.get('execution')==execution_id and m['role']=='assistant' for m in messages)
    assert page.request.get(base+'/api/executions/'+execution_id).json()['state']=='COMPLETED'
    assert page.request.get(base+'/api/artifacts/'+artifact+'/measurements').json()[0]['changes']['net_revenue']['absolute_change']=='24.90'
    # Reopen saved history using its actual persisted title.
    page.locator('.sidebar-scroll').get_by_role('button').filter(has_text=conversation['title']).first.click()
    page.get_by_label('Calculated e-commerce metrics').first.wait_for()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'ecommerce-mobile.png'))
    assert not errors,errors
    print('ECOMMERCE BROWSER PASS: existing business/chat UI → validated CSV → real SQL metrics → real read-only MCP → live public research or explicit outage → proposal → approval → verified internal tasks → dated follow-up → saved measurement/history → readable control center → reload/mobile. Research status: '+market)
    browser.close()
