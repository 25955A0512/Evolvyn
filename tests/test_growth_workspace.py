"""Growth profile, immutable evidence, draft-only campaigns and scoped workflow history."""
from uuid import uuid4
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import app as module

@pytest.fixture
def c():
    with TestClient(module.app,client=(uuid4().hex,40000)) as c:
        c.headers['X-Requested-With']='Evolvyn'
        c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'growth-workspace-test-password','name':'Growth tests'}).raise_for_status()
        yield c

def profile(**extra):return {'name':'Test store','kind':'ecommerce','goal':'Measure sales and validate a campaign','timezone':'Asia/Kolkata','reporting_currency':'INR','website':'https://example.test','business_model':'Direct to consumer','reporting_objectives':'Weekly revenue and outcomes',**extra}
def setup(c):
    b=c.post('/api/businesses',json=profile());b.raise_for_status()
    v=c.post('/api/conversations',json={'title':'Growth evidence','business_id':b.json()['id']});v.raise_for_status();v=v.json()
    u=c.post('/api/conversations/'+v['id']+'/files',files={'file':('sales.csv',Path('sample-data/ecommerce-sales.csv').read_bytes())});u.raise_for_status()
    r=c.post('/api/growth/reports',json={'conversation_id':v['id'],'query':'Improve product clarity and sales'});r.raise_for_status()
    return b.json(),v,r.json(),u.json()
def draft(**extra):
    return dict(objective='Test a customer education campaign',channel='Email',audience='Consented customers',consent_basis='Explicit marketing opt-in',exclusions='Opt-outs and suppressed customers',copy='Explore our product use cases',cta='Learn more',destination='https://example.test/products',timezone='Asia/Kolkata',starts_at='2026-11-01T10:00:00+05:30',duration_days=14,budget='100.00',currency='INR',attribution_tags='utm_source=email&utm_campaign=education',baseline='Unknown; collect prior to launch',success_metric='Qualified activation',guardrails='One message per opted-in customer',stop_conditions='Pause on complaints or consent failures',**extra)

def test_profile_validation_and_authorization(c):
    b=c.post('/api/businesses',json=profile());b.raise_for_status();b=b.json()
    result=c.put('/api/businesses/'+b['id'],json=profile(name='Revised store'));assert result.status_code==200 and result.json()['name']=='Revised store'
    for changes in ({'timezone':'Made/Up'},{'website':'http://example.test'},{'website':'https://user:pass@example.test'},{'reporting_currency':'rupees'}):
        assert c.post('/api/businesses',json=profile(**changes)).status_code==422
    c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'another-test-password','name':'Other tenant'}).raise_for_status()
    assert c.put('/api/businesses/'+b['id'],json=profile()).status_code==404

def test_growth_snapshot_provenance_not_changed_by_later_upload(c):
    b,v,r,u=setup(c)
    assert r['business_id']==b['id'] and r['sources'][0]['document_id']==u['id']
    assert r['report']['commerce']['primary']['net_revenue']=='45.10'
    source=r['sources'][0];assert source['currency']=='USD' and source['mapping_version']=='evolvyn-commerce-v1'
    assert source['included_lines']==3 and source['excluded_lines']==1 and source['content_sha256']
    assert source['provider_account'] is None and r['forecast']['status']=='suppressed'
    c.post('/api/conversations/'+v['id']+'/files',files={'file':('followup.csv',Path('sample-data/ecommerce-followup.csv').read_bytes())}).raise_for_status()
    w=c.get('/api/growth/conversations/'+v['id']+'/workspace');w.raise_for_status();w=w.json()
    assert len(w['conversation']['files'])==2 and len(w['reports'][0]['sources'])==1
    assert w['reports'][0]['report']['commerce']['primary']['net_revenue']=='45.10' and w['publishing']['available'] is False

def test_campaign_draft_persistence_no_external_action_or_approval(c):
    _,v,r,_=setup(c)
    row=c.post('/api/growth/reports/'+r['id']+'/campaigns',json=draft());row.raise_for_status();row=row.json()
    assert row['state']=='DRAFT' and row['publishing_available'] is False and row['plan']['budget']=='100.00'
    w=c.get('/api/growth/conversations/'+v['id']+'/workspace').json()
    assert w['campaigns'][0]['id']==row['id'] and w['tasks']==[] and w['artifacts']==[] and w['executions']==[]
    assert c.post('/api/growth/reports/'+r['id']+'/campaigns',json={**draft(),'approved':True}).status_code==422

@pytest.mark.parametrize('changes',[{'destination':'http://example.test'},{'destination':'https://user:pw@example.test'},{'budget':'-1'},{'budget':'NaN'},{'budget':'1.001'},{'currency':'USD/INR'},{'starts_at':'2026-11-01T10:00:00'},{'timezone':'Made/Up'},{'consent_basis':''},{'duration_days':0}])
def test_invalid_campaigns_never_saved(c,changes):
    _,v,r,_=setup(c)
    assert c.post('/api/growth/reports/'+r['id']+'/campaigns',json={**draft(),**changes}).status_code==422
    assert c.get('/api/growth/conversations/'+v['id']+'/workspace').json()['campaigns']==[]

def test_growth_history_tenant_project_and_trash_boundaries(c):
    b,v,r,_=setup(c)
    other=c.post('/api/conversations',json={'title':'Another workspace'}).json()
    assert c.get('/api/growth/conversations/'+other['id']+'/workspace').json()['reports']==[]
    c.delete('/api/conversations/'+v['id']).raise_for_status()
    assert c.get('/api/growth/conversations/'+v['id']+'/workspace').status_code==404
    assert c.post('/api/growth/reports/'+r['id']+'/campaigns',json=draft()).status_code==404
    c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'other-growth-password','name':'Other tenant'}).raise_for_status()
    assert c.get('/api/growth/conversations/'+v['id']+'/workspace').status_code==404
    assert c.post('/api/growth/reports/'+r['id']+'/campaigns',json=draft()).status_code==404

def test_growth_workflow_history_approval_and_outcome_are_persisted(c):
    _,v,r,_=setup(c)
    start=c.post('/api/conversations/'+v['id']+'/runs',json={'text':r['query'],'mode':'evidence','analysis_kind':'business'});start.raise_for_status();id=start.json()['id']
    c.get('/api/executions/'+id+'/live')
    result=c.get('/api/growth/conversations/'+v['id']+'/workspace').json()
    execution=next(e for e in result['executions'] if e['id']==id);assert execution['state']=='WAITING_FOR_APPROVAL'
    assert result['tasks']==[] and result['artifacts']==[]
    decision={'approve':True,'plan':execution['report']['plan']}
    approved=c.post('/api/executions/'+id+'/decision',json=decision);approved.raise_for_status()
    assert c.post('/api/executions/'+id+'/decision',json=decision).status_code==409
    w=c.get('/api/growth/conversations/'+v['id']+'/workspace').json();assert w['tasks'] and w['artifacts']
    a=w['artifacts'][0];assert a['execution_result']['verified_task_count']==len(w['tasks'])
    f=c.post('/api/conversations/'+v['id']+'/files',files={'file':('followup.csv',Path('sample-data/ecommerce-followup.csv').read_bytes())}).json()
    c.post('/api/artifacts/'+a['id']+'/measure',json={'document_id':f['id']}).raise_for_status()
    w=c.get('/api/growth/conversations/'+v['id']+'/workspace').json();assert w['measurements'][0]['changes']['net_revenue']['absolute_change']=='24.90'

@pytest.mark.parametrize('role',['viewer','editor'])
def test_growth_workspace_project_and_mutation_access(c,role):
    b,v,r,_=setup(c)
    owner_cookie=c.cookies.get('evolvyn_session');organization=c.get('/api/auth/me').json()['organization_id']
    project=c.post('/api/projects',json={'name':'Restricted growth','business_id':b['id'],'goal':'Protect sales'}).json()
    # Bind this conversation to a real restricted project, using the record persistence boundary.
    with module.conn() as db:
        db.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(__import__('json').dumps({'project_id':project['id']}),v['id']))
    member_email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':member_email,'password':'member-growth-password','name':'Member'}).raise_for_status();member_cookie=c.cookies.get('evolvyn_session')
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/');c.headers['X-Organization-Id']=organization
    c.post('/api/organizations/members',json={'email':member_email,'role':role}).raise_for_status()
    c.put('/api/projects/'+project['id']+'/access',json={'access':'restricted','members':[]}).raise_for_status()
    c.cookies.set('evolvyn_session',member_cookie,domain='testserver.local',path='/')
    assert c.get('/api/growth/conversations/'+v['id']+'/workspace').status_code==404
    assert c.post('/api/growth/reports/'+r['id']+'/campaigns',json=draft()).status_code in (403,404)
    if role=='viewer':
        assert c.put('/api/businesses/'+b['id'],json=profile()).status_code==403

def test_campaign_credentials_never_enter_draft_arguments(c):
    _,v,r,_=setup(c)
    response=c.post('/api/growth/reports/'+r['id']+'/campaigns',json={**draft(),'copy':'sk-'+('unit'*20)})
    assert response.status_code==422
    assert c.get('/api/growth/conversations/'+v['id']+'/workspace').json()['campaigns']==[]
