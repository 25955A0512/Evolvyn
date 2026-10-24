from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://localhost:3000/')
 with page.expect_response(lambda r:r.url.endswith('/api/demo/session')) as response:
  page.get_by_role('button',name='Try a sample business').click()
 data=response.value.json();assert data['analysis_mode']=='local'
 page.get_by_role('button',name='Approve & create brief').wait_for(timeout=160000)
 assert page.get_by_label('Analysis mode').input_value()=='local'
 assert page.locator('.recommendation').count()>=1
 assert 'Deterministic evidence mode' not in page.locator('.markdown').last.inner_text()
 assert page.get_by_text('Model-generated hypotheses with schema-validated evidence references',exact=True).count()>0
 page.locator('.recommendations').evaluate("node => {const box=document.querySelector('.scroll');box.scrollTop+=node.getBoundingClientRect().top-box.getBoundingClientRect().top-20;}")
 page.screenshot(path='/workspace/Evolvyn/.local/validation/real-ai-desktop.png',full_page=True)
 page.get_by_role('button',name='Review this action').first.click()
 page.get_by_role('button',name='Approve & create brief').click()
 page.get_by_role('button',name='Open saved experiment brief').wait_for()
 page.set_viewport_size({'width':390,'height':844})
 if page.get_by_role('button',name='Collapse sidebar').is_visible():page.get_by_role('button',name='Collapse sidebar').click()
 page.get_by_label('Message Evolvyn').wait_for()
 page.screenshot(path='/workspace/Evolvyn/.local/validation/real-ai-mobile.png',full_page=True)
 assert not errors,errors
 print('ONE-CLICK REAL LOCAL AI: model-selected sample → actual generation → schema-validated recommendations → approval → artifact; desktop/mobile PASS')
 browser.close()
