"""Unit contracts and real PostgreSQL integration across growth, canvas and shared runtime."""
import asyncio
import io
import json
import time
import zipfile
from uuid import uuid4
from urllib.parse import parse_qs,urlparse
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend import app as module
from backend.canvas import Drawing,prompt
from backend.product_studio import QUESTIONS
from backend.growth import public_windows,measured_change

@pytest.fixture
def c():
    with TestClient(module.app,client=(uuid4().hex,40000)) as client:
        client.headers['X-Requested-With']='Evolvyn'
        client.email=uuid4().hex+'@example.test'
        client.post('/api/auth/register',json={'email':client.email,'password':'evolution-private-password','name':'Evolution tests'}).raise_for_status()
        yield client

def canvas(**updates):
    return {'name':'Customer page','elements':[{'id':'headline','kind':'heading','label':'Customer insights','x':40,'y':30,'width':900,'height':100}],**updates}
def product(c):
    row=c.post('/api/studio/products',json={'name':'Customer research','goal':'Understand customer feedback and improve activation'}).json()
    for key,_,answer in QUESTIONS:
        response=c.post('/api/studio/products/'+row['id']+'/answers',json={'field':key,'text':answer,'revision':row['revision']});response.raise_for_status();row=response.json()
    return row
def evidence(c):
    row=c.post('/api/conversations',json={'title':'Growth evidence'}).json()
    c.post('/api/conversations/'+row['id']+'/files',files={'file':('feedback.txt',b'Customers report slow onboarding and pricing concerns. Interview the affected users.')}).raise_for_status()
    c.post('/api/conversations/'+row['id']+'/files',files={'file':('funnel.csv',b'period,visits,paid\n2026-09,100,12\n2026-10,100,8\n')}).raise_for_status()
    return row
def wait(c,id):
    for _ in range(300):
        row=c.get('/api/executions/'+id).json()
        if row['state'] not in ('CREATED','RUNNING'):return row
        time.sleep(.03)
    raise AssertionError('Execution did not finish in integration budget')

def test_canvas_prompt_is_bounded_structured_data():
    d=Drawing.model_validate(canvas(strokes=[[{'x':20,'y':30},{'x':80,'y':90}]]))
    value=prompt(d.model_dump())
    assert 'Customer insights' in value and 'not OCR' in value and '1200 by 900' in value
    with pytest.raises(ValidationError):Drawing.model_validate(canvas(elements=[{'id':'a','label':'Bad geometry','x':float('nan'),'y':0}]))
    with pytest.raises(ValidationError):Drawing.model_validate(canvas(strokes=[[{'x':1,'y':1}]*6001]))
    with pytest.raises(ValidationError):Drawing.model_validate(canvas(elements=[{'id':'same','label':'A','x':0,'y':0},{'id':'same','label':'B','x':0,'y':0}]))

def test_public_discussion_windows_have_equal_nonoverlapping_intervals(monkeypatch):
    seen=[]
    async def handler(request):
        seen.append(request)
        limits=request.url.params['numericFilters'].split(',')
        start=int(limits[0].split('>=')[1]);end=int(limits[1].split('<')[1])
        assert end-start==30*86400
        return httpx.Response(200,json={'nbHits':0 if len(seen)==1 else 4,'hits':[{'objectID':'123','title':'Privacy workflows','created_at':'2026-10-01T00:00:00Z'}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    result=asyncio.run(public_windows('privacy workflows',30))
    assert result['absolute_change']==4 and result['relative_change_percent'] is None
    assert result['previous']['end']==result['current']['start']
    assert 'not market size' in result['classification']

def test_first_party_growth_requires_a_single_dated_comparable_series():
    rows=[{'period':'2026-10','visits':100,'paid':8,'conversion':8,'source':'funnel.csv:row 2'},{'period':'2026-09','visits':100,'paid':12,'conversion':12,'source':'funnel.csv:row 3'}]
    result=measured_change(rows)
    assert result['before']['period']=='2026-09' and result['paid_outcomes_change_percent']==-33.33
    assert result['conversion_change_percentage_points']==-4
    assert measured_change([{**rows[0],'period':'before'},rows[1]])['status']=='insufficient'
    assert measured_change([{**rows[0],'source':'other.csv:row 2'},rows[1]])['status']=='insufficient'
    assert measured_change([{**rows[0],'period':'2026-09'},rows[1]])['status']=='insufficient'
    assert measured_change([{**rows[0],'period':'2026-99'},rows[1]])['status']=='insufficient'
    assert measured_change([rows[0],{**rows[1],'paid':0}])['paid_outcomes_change_percent'] is None

def test_generated_compose_separates_product_runtime_and_catches_invalid_yaml():
    import yaml
    from backend.product_templates import generate,validate
    from backend.product_studio import parsed_answer
    spec={key:parsed_answer(key,answer) for key,_,answer in QUESTIONS}
    files=generate({**spec,'name':'Isolated product','goal':'Preserve private network boundaries'})
    services=yaml.safe_load(files['compose.yaml'])['services']
    assert services['db']['networks']==services['app']['networks']==['product_private']
    assert services['agents_db']['networks']==['agent_private']
    assert services['agents_api']['networks']==['agent_private','agent_compiler']
    assert services['agents_compiler']['networks']==['agent_compiler']
    assert not services['agents_compiler'].get('volumes')
    assert 'OAUTH_GOOGLE_CLIENT_SECRET' in services['agents_api']['environment']
    assert services['agents_vault_init']['network_mode']=='none'
    assert not services['db'].get('ports') and not services['agents_api'].get('ports')
    assert 'Compose services and isolated product/agent networks validated' in validate(files)
    with pytest.raises(ValueError):validate({**files,'compose.yaml':'services: [\ninvalid: ['})

def test_growth_canvas_and_export_complete_evidence_to_product_loop(c,monkeypatch):
    conv=evidence(c);spec=product(c)
    async def offline(*args):raise httpx.ConnectError('offline')
    monkeypatch.setattr('backend.growth.public_windows',offline)
    result=c.post('/api/growth/reports',json={'conversation_id':conv['id'],'product_id':spec['id'],'query':'customer onboarding','public_research':True})
    assert result.status_code==200,result.text
    report=result.json();assert report['market']['status']=='unavailable'
    assert len(report['report']['facts'])==2 and report['report']['themes']
    proposed=c.post('/api/growth/reports/'+report['id']+'/propose',json={'action_id':'feedback_0'}).json()
    assert proposed['state']=='DRAFT' and proposed['source_ids']==[report['id']]
    c.post('/api/memory/'+proposed['id']+'/decision',json={'accept':True}).raise_for_status()
    updated=c.post('/api/studio/products/'+spec['id']+'/decisions',json={'memory_id':proposed['id'],'revision':spec['revision'],'changes':{'features':'Private accounts, onboarding checklist'}})
    updated.raise_for_status();spec=updated.json()
    execution=c.post('/api/discussions',json={'conversation_id':conv['id'],'growth_report_id':report['id'],'goal':'Review evidence and propose a measurable onboarding experiment','mode':'evidence'}).json()
    execution=wait(c,execution['id']);assert execution['state']=='WAITING_FOR_APPROVAL',execution
    assert execution['discussion_checkpoint']['growth_attached'] is True
    assert set(execution['discussion_result']['outputs'])=={'business_analyst','marketing_analyst','product_manager','reviewer'}
    accepted=c.post('/api/discussions/'+execution['id']+'/decision',json={'approve':True,'plan':'Test an onboarding checklist with a controlled customer cohort','acknowledge_issues':True})
    accepted.raise_for_status();assert accepted.json()['memory_id']
    drawing=c.post('/api/canvas',json=canvas()).json()
    applied=c.post('/api/canvas/'+drawing['id']+'/apply',json={'product_id':spec['id'],'revision':spec['revision'],'canvas_revision':drawing['revision']})
    assert applied.status_code==200,applied.text
    spec=applied.json();assert spec['requirements']['design']['elements'][0]['label']=='Customer insights'
    built=c.post('/api/studio/products/'+spec['id']+'/build',json={'revision':spec['revision']})
    assert built.status_code==200 and built.json()['state']=='READY',built.text[:500]
    artifact=built.json();assert 'onboarding checklist' in artifact['pending_requirements']
    archive=zipfile.ZipFile(io.BytesIO(c.get('/api/studio/builds/'+artifact['id']+'/download').content))
    paths=archive.namelist()
    for filename in ['evolvyn/backend/graph_harness.py','evolvyn/backend/mcp_gateway.py','evolvyn/backend/runtime_catalog.py','evolvyn/backend/agent_gateway.py','evolvyn/backend/growth.py','evolvyn/backend/oauth.py','evolvyn/frontend/src/components/DesignCanvas.tsx','evolvyn/frontend/vite.config.js','evolvyn/requirements.lock','scripts/prepare_product.py']:
        assert filename in paths,filename
    assert not any('.local/' in name or 'node_modules/' in name or name.endswith('.env') or 'vault.key' in name for name in paths)
    assert 'agents_api' in archive.read('compose.yaml').decode()
    assert 'spec.design' in archive.read('frontend/src/main.jsx').decode()
    assert 'Customer insights' in archive.read('frontend/src/spec.json').decode()
    assert c.post('/api/canvas/'+drawing['id']+'/apply',json={'product_id':spec['id'],'revision':spec['revision']-1,'canvas_revision':1}).status_code==409

def test_canvas_publishes_real_graph_with_bounded_cycle(c):
    conv=evidence(c)
    graph={'name':'Bounded review','goal':'Review evidence within one node visit','entry':'review','nodes':[{'id':'review','type':'agent','mode':'evidence','agent_id':'product_manager','prompt':'Review','arguments':{},'max_visits':1}],'edges':[{'source':'review','target':'review'}],'max_steps':3}
    drawing=c.post('/api/canvas',json=canvas(graph=graph,positions={'review':{'x':100,'y':80}})).json()
    published=c.post('/api/canvas/'+drawing['id']+'/publish-graph');published.raise_for_status()
    execution=c.post('/api/harness/graphs/'+published.json()['id']+'/run',json={'conversation_id':conv['id']});execution.raise_for_status()
    result=wait(c,execution.json()['id'])
    assert result['state']=='FAILED' and result['graph_checkpoint']['steps']<=3
    # A graph with dangling/unreachable nodes cannot be persisted through visual editing.
    graph['nodes'].append({'id':'unreachable','type':'result'})
    assert c.post('/api/canvas',json=canvas(graph=graph)).status_code==422

def test_ontology_uses_actual_tools_and_supports_semantic_filter(c):
    runtime=c.get('/api/runtime').json();assert len(runtime['components'])==9
    rows=c.get('/api/runtime/ontology',params={'entity':'product','action':'build'}).json()['tools']
    assert [t['name'] for t in rows]==['build_product']
    assert rows[0]['ontology']['input_contract']['properties']['spec_id']
    assert c.get('/api/tool-registry').json()[0]['ontology']['version']=='1.0'

def test_canvas_revision_conflicts_and_viewer_mutations_are_rejected(c):
    drawing=c.post('/api/canvas',json=canvas()).json()
    changed=c.put('/api/canvas/'+drawing['id'],json={'revision':1,'drawing':canvas(name='Revised page')})
    assert changed.status_code==200 and changed.json()['revision']==2
    assert c.put('/api/canvas/'+drawing['id'],json={'revision':1,'drawing':canvas(name='Stale page')}).status_code==409
    owner_cookie=c.cookies.get('evolvyn_session');owner=c.get('/api/auth/me').json()['organization_id']
    email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':email,'password':'viewer-private-password','name':'Viewer'}).raise_for_status();viewer=c.cookies.get('evolvyn_session')
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/')
    c.post('/api/organizations/members',json={'email':email,'role':'viewer'}).raise_for_status()
    c.cookies.set('evolvyn_session',viewer,domain='testserver.local',path='/');c.headers['X-Organization-Id']=owner
    assert c.get('/api/canvas').status_code==200
    assert c.post('/api/canvas',json=canvas()).status_code==403
    assert c.post('/api/canvas/'+drawing['id']+'/publish-graph').status_code==403
    assert c.post('/api/growth/reports',json={'conversation_id':'anything','query':'customer feedback'}).status_code==403

def test_growth_respects_local_only_policy_before_external_fetch(c,monkeypatch):
    conv=evidence(c)
    policy=c.get('/api/governance/policy').json()
    c.put('/api/governance/policy',json={**policy,'allow_external_processing':False}).raise_for_status()
    async def forbidden(*args):raise AssertionError('Policy must reject before network')
    monkeypatch.setattr('backend.growth.public_windows',forbidden)
    assert c.post('/api/growth/reports',json={'conversation_id':conv['id'],'query':'customer feedback','public_research':True}).status_code==403
    assert c.post('/api/growth/reports',json={'conversation_id':conv['id'],'query':'customer feedback','public_research':False}).status_code==200

def test_tenant_cannot_read_apply_or_discuss_another_tenants_data(c):
    conv=evidence(c);spec=product(c);drawing=c.post('/api/canvas',json=canvas()).json()
    report=c.post('/api/growth/reports',json={'conversation_id':conv['id'],'query':'customer feedback'}).json()
    c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'different-private-password','name':'Other tenant'}).raise_for_status()
    assert c.get('/api/canvas').json()==[] and c.get('/api/growth/reports').json()==[]
    assert c.post('/api/canvas/'+drawing['id']+'/apply',json={'product_id':spec['id'],'revision':spec['revision'],'canvas_revision':1}).status_code==404
    other=c.post('/api/conversations',json={'title':'Other tenant'}).json()
    assert c.post('/api/discussions',json={'conversation_id':other['id'],'growth_report_id':report['id'],'goal':'Read another tenant report','mode':'evidence'}).status_code==404

def configure(monkeypatch):
    monkeypatch.setenv('OAUTH_GOOGLE_CLIENT_ID','unit-client')
    monkeypatch.setenv('OAUTH_GOOGLE_CLIENT_SECRET','unit-secret')
    monkeypatch.setenv('PUBLIC_ORIGIN','http://testserver')
    # OAuth permits HTTP only on loopback; TestClient still uses testserver for callback.
    monkeypatch.setenv('PUBLIC_ORIGIN','http://localhost:3000')
def oauth_start(c):
    response=c.get('/api/auth/oauth/google/start',follow_redirects=False)
    assert response.status_code==303
    query=parse_qs(urlparse(response.headers['location']).query)
    assert query['code_challenge_method']==['S256'] and 'unit-secret' not in response.headers['location']
    return query['state'][0]

def test_oauth_fails_closed_when_unconfigured_and_does_not_expose_secrets(c,monkeypatch):
    monkeypatch.delenv('OAUTH_GOOGLE_CLIENT_SECRET',raising=False)
    assert c.get('/api/auth/oauth/google/start',follow_redirects=False).status_code==503
    assert c.get('/api/auth/providers').json()[0]['enabled'] is False
    configure(monkeypatch)
    assert 'unit-secret' not in c.get('/api/auth/providers').text

def test_oauth_state_browser_binding_replay_and_no_email_autolink(c,monkeypatch):
    configure(monkeypatch)
    async def profile(*args):return 'subject-'+uuid4().hex,c.email,'Existing email'
    monkeypatch.setattr('backend.oauth.verified_profile',profile)
    state=oauth_start(c)
    url='/api/auth/oauth/google/callback?state='+state+'&code=unit-code'
    assert c.get(url,follow_redirects=False).status_code==409
    assert c.get(url,follow_redirects=False).status_code==400
    state=oauth_start(c);c.cookies.delete('evolvyn_oauth')
    assert c.get('/api/auth/oauth/google/callback',params={'state':state,'code':'unit-code'},follow_redirects=False).status_code==400

def test_oauth_new_account_login_and_explicit_link(c,monkeypatch):
    configure(monkeypatch);subject=uuid4().hex;email=uuid4().hex+'@example.test'
    async def profile(*args):return subject,email,'Verified provider account'
    monkeypatch.setattr('backend.oauth.verified_profile',profile)
    state=oauth_start(c)
    assert c.get('/api/auth/oauth/google/callback',params={'state':state,'code':'unit-code'},follow_redirects=False).status_code==303
    assert c.get('/api/auth/me').json()['account']['email']==email
    assert c.post('/api/auth/login',json={'email':email,'password':'incorrect-password'}).status_code==401
    assert c.get('/api/auth/security').json()['linked_providers']==['google']
    # Original local account can explicitly link a different provider subject after authenticating.
    c.post('/api/auth/login',json={'email':c.email,'password':'evolution-private-password'}).raise_for_status()
    async def other_profile(*args):return 'linked-'+uuid4().hex,c.email,'Linked owner'
    monkeypatch.setattr('backend.oauth.verified_profile',other_profile)
    result=c.post('/api/auth/oauth/google/link');result.raise_for_status()
    state=parse_qs(urlparse(result.json()['authorize_url']).query)['state'][0]
    assert c.get('/api/auth/oauth/google/callback',params={'state':state,'code':'unit-code'},follow_redirects=False).status_code==303
    assert c.get('/api/auth/me').json()['account']['email']==c.email
    assert c.get('/api/auth/security').json()['linked_providers']==['google']

def test_oauth_profile_checks_verified_email_and_fixed_destinations(monkeypatch):
    from backend.oauth import verified_profile,configuration
    configure(monkeypatch);requests=[]
    async def handler(request):
        requests.append(request)
        if request.url.path=='/token':
            assert b'code_verifier=unit-verifier' in request.content and b'unit-secret' in request.content
            return httpx.Response(200,json={'access_token':'transient-access-token'})
        assert request.headers['authorization']=='Bearer transient-access-token'
        return httpx.Response(200,json={'sub':'unit-subject','email':'verified@example.test','email_verified':False})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    with pytest.raises(ValueError):asyncio.run(verified_profile('google',configuration('google'),'unit-code','unit-verifier'))
    assert [str(r.url) for r in requests]==['https://oauth2.googleapis.com/token','https://openidconnect.googleapis.com/v1/userinfo']

def test_github_identity_requires_verified_primary_email(monkeypatch):
    from backend.oauth import verified_profile,configuration
    monkeypatch.setenv('OAUTH_GITHUB_CLIENT_ID','github-unit-client')
    monkeypatch.setenv('OAUTH_GITHUB_CLIENT_SECRET','github-unit-secret')
    monkeypatch.setenv('PUBLIC_ORIGIN','http://localhost:3000')
    verified=[True]
    async def handler(request):
        if request.url.host=='github.com':return httpx.Response(200,json={'access_token':'unit-ephemeral-token'})
        assert request.url.host=='api.github.com' and request.headers['authorization']=='Bearer unit-ephemeral-token'
        if request.url.path=='/user':return httpx.Response(200,json={'id':123,'login':'developer'})
        return httpx.Response(200,json=[{'email':'primary@example.test','primary':True,'verified':verified[0]},{'email':'secondary@example.test','primary':False,'verified':True}])
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    assert asyncio.run(verified_profile('github',configuration('github'),'code','verifier'))==('123','primary@example.test','developer')
    verified[0]=False
    with pytest.raises(ValueError):asyncio.run(verified_profile('github',configuration('github'),'code','verifier'))

def test_password_change_and_global_session_revocation(c):
    assert c.post('/api/auth/password',json={'current_password':'wrong','new_password':'updated-private-password'}).status_code==401
    assert c.post('/api/auth/password',json={'current_password':'evolution-private-password','new_password':'updated-private-password'}).status_code==200
    assert c.get('/api/auth/me').status_code==401

    assert c.post('/api/auth/login',json={'email':c.email,'password':'evolution-private-password'}).status_code==401
    assert c.post('/api/auth/login',json={'email':c.email,'password':'updated-private-password'}).status_code==200
    assert c.post('/api/auth/sessions/revoke-all').status_code==200
    assert c.get('/api/auth/me').status_code==401

def test_exported_session_namespace_does_not_overwrite_parent_platform_cookie(c,monkeypatch):
    original_email=c.email
    monkeypatch.setenv('EVOLVYN_SESSION_COOKIE','evolvyn_generated_unit')
    email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':email,'password':'isolated-product-password','name':'Generated runtime'}).raise_for_status()
    assert c.cookies.get('evolvyn_session') and c.cookies.get('evolvyn_generated_unit')
    assert c.get('/api/auth/me').json()['account']['email']==email
    monkeypatch.delenv('EVOLVYN_SESSION_COOKIE')
    assert c.get('/api/auth/me').json()['account']['email']==original_email
    monkeypatch.setenv('EVOLVYN_SESSION_COOKIE','evolvyn_generated_unit')
    c.post('/api/auth/logout').raise_for_status()
    monkeypatch.delenv('EVOLVYN_SESSION_COOKIE')
    assert c.get('/api/auth/me').json()['account']['email']==original_email
