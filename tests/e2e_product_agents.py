"""Legacy trusted starter adapter + actual local role calls and browser acceptance.
AI-authored files are covered by the controlled source-generation acceptance.
"""
import ast,json,os,re,time,sys
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
tree=ast.parse(Path('backend/product_studio.py').read_text())
QUESTIONS=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='QUESTIONS' for t in n.targets))
base=os.getenv('EVOLVYN_TEST_URL','http://localhost:3000')
out=Path('.local/validation');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1600,'height':1050});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(base)
    page.get_by_role('button',name='Create account',exact=True).click()
    page.get_by_label('Workspace name',exact=True).fill('Synthetic builder acceptance')
    page.get_by_label('Email',exact=True).fill('product-agent-'+uuid4().hex+'@example.test')
    page.get_by_label('Password',exact=True).fill('acceptance-'+uuid4().hex)
    page.get_by_role('button',name='Create your workspace',exact=True).click()
    page.get_by_role('heading',name=re.compile('Your next idea')).wait_for()
    def call(path,body=None):
        response=page.request.post(base+'/api'+path,data=body,headers={'X-Requested-With':'Evolvyn'}) if body is not None else page.request.get(base+'/api'+path)
        assert response.ok,(path,response.status,response.text()[:500])
        return response.json()
    def completed(id):
        for _ in range(330):
            result=call('/executions/'+id)
            if result['state'] not in ('CREATED','RUNNING'):return result
            time.sleep(1)
        raise AssertionError('Run did not finish within acceptance budget')
    conv=call('/conversations',{'title':'Synthetic greeting acceptance'})
    run=completed(call('/conversations/'+conv['id']+'/runs',{'text':'Hello, what can Evolvyn help me do?','analysis_kind':'auto','mode':'local'})['id'])
    assert run['state']=='COMPLETED' and run['output'],(run['state'],run.get('error'))
    assert run['chat_result']['mode']=='local'
    print('Real file-free local-model chat persisted: PASS',flush=True)
    product=call('/studio/products',{'name':'Synthetic service desk','goal':'A private support request tracker for a small business. Use dark theme.'})
    interview=completed(call('/studio/products/'+product['id']+'/messages',{'spec_id':product['id'],'revision':product['revision'],'text':'Use a dark theme. Ask me what you need to know about the users.','mode':'local'})['id'])
    assert interview['state']=='COMPLETED',(interview['state'],interview.get('error'))
    assert interview['graph_checkpoint']['nodes']['proposal']['output']['reply']
    print('Real local requirements interview and typed proposal: PASS',flush=True)
    # Explicitly supplied test decisions, not fabricated model outputs.
    for field,_,answer in QUESTIONS:
        if field=='theme':answer='dark'
        product=call('/studio/products/'+product['id']+'/answers',{'field':field,'text':answer,'revision':product['revision']})
    page.locator('.home-actions').get_by_role('button',name=re.compile('^Build a product')).click()
    studio=page.locator('.intelligent-product-studio')
    studio.get_by_label('Agent product',exact=True).select_option(product['id'])
    studio.get_by_label('Product agent model route',exact=True).select_option('local')
    # This acceptance case deliberately uses three enabled agents plus human review.
    # Reviewer rejection is covered separately and must never be overridden automatically.
    if studio.get_by_role('button',name='Open workspace',exact=True).is_visible():studio.get_by_role('button',name='Open workspace',exact=True).click()
    studio.get_by_label('Enable Quality reviewer',exact=True).uncheck()
    call('/studio/products/'+product['id']+'/agent-build',{'spec_id':product['id'],'revision':product['revision'],'mode':'local','agents':['prd','architecture','developer'],'generation':'template'})
    page.reload();page.locator('.agent-workspace').wait_for()
    studio.get_by_role('button',name='Approve source implementation',exact=True).wait_for(timeout=330000)
    page.screenshot(path=str(out/'product-agents-approval.png'))
    expect(studio.locator('.product-implementation-approval')).to_contain_text('exact')
    studio.get_by_role('button',name='Approve source implementation',exact=True).click()
    studio.get_by_text('Source ready · runtime not started',exact=True).first.wait_for(timeout=90000)
    studio.get_by_role('button',name='Architecture',exact=True).click()
    expect(studio.locator('.architecture-diagram svg')).to_be_visible()
    page.screenshot(path=str(out/'product-agents-architecture.png'))
    studio.get_by_role('button',name='Source tree',exact=True).click()
    expect(studio.get_by_role('navigation',name='Project file tree')).to_be_visible()
    studio.get_by_label('Search project files',exact=True).fill('PRD.md')
    studio.locator('button[title="docs/PRD.md"]').click()
    expect(studio.locator('.product-source-code pre')).not_to_be_empty()
    page.screenshot(path=str(out/'product-agents-source.png'))
    studio.get_by_role('button',name='Build results',exact=True).click()
    expect(studio).to_contain_text('Frontend compiler: passed')
    expect(studio).to_contain_text('Application runtime: not started')
    page.screenshot(path=str(out/'product-agents-validation.png'))
    studio.get_by_role('button',name='Prototype',exact=True).click()
    preview=studio.locator('.product-preview')
    preview.get_by_label('Title',exact=True).fill('Synthetic support request')
    preview.get_by_label('Status',exact=True).fill('Open')
    preview.get_by_role('button',name='Add Tasks',exact=True).click()
    expect(preview.locator('.prototype-records')).to_contain_text('Synthetic support request')
    page.reload()
    page.locator('.agent-workspace').wait_for()
    studio=page.locator('.intelligent-product-studio')
    studio.get_by_label('Agent product',exact=True).select_option(product['id'])
    if studio.get_by_role('button',name='Open workspace',exact=True).is_visible():studio.get_by_role('button',name='Open workspace',exact=True).click()
    studio.get_by_role('button',name='Prototype',exact=True).click()
    expect(studio.locator('.prototype-records')).to_contain_text('Synthetic support request')
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'product-agents-mobile.png'),full_page=True)
    assert not errors,errors
    browser.close()
    print('Live product agents → approval → real compilation → tree/diagram → persisted prototype: PASS')
