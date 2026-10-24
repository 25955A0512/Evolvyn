"""Exact sales metrics, governed execution, connector context and durable outcome history."""
import json
from pathlib import Path
from uuid import uuid4
from decimal import Decimal
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import app as module
from backend.commerce import parse,compare

SALES=Path('sample-data/ecommerce-sales.csv').read_text()
FOLLOWUP=Path('sample-data/ecommerce-followup.csv').read_text()
CATALOG=Path('sample-data/ecommerce-catalog.csv').read_text()

@pytest.fixture
def c():
    with TestClient(module.app,client=(uuid4().hex,40000)) as c:
        c.headers['X-Requested-With']='Evolvyn'
        c.post('/api/auth/register',json={'email':uuid4().hex+'@example.test','password':'commerce-acceptance-password','name':'Commerce acceptance'}).raise_for_status()
        yield c

def upload(c,conv,text=SALES,name='sales.csv'):
    response=c.post('/api/conversations/'+conv['id']+'/files',files={'file':(name,text.encode())});response.raise_for_status();return response.json()
def workspace(c):
    business=c.post('/api/businesses',json={'name':'Tea shop','kind':'ecommerce','goal':'Grow sales with measured experiments'}).json()
    return c.post('/api/conversations',json={'title':'Sales intelligence','business_id':business['id']}).json()
def run(c,conv,**options):
    response=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Which products drive revenue, and what should we do next?','mode':'evidence',**options});response.raise_for_status()
    id=response.json()['id'];c.get('/api/executions/'+id+'/live')
    result=c.get('/api/executions/'+id).json();assert result['state']=='WAITING_FOR_APPROVAL',result
    return result

def test_sales_csv_parser_uses_decimal_and_line_items():
    result=parse(SALES)
    assert result['kind']=='sales' and result['currency']=='USD'
    assert result['rows'][0]['unit_price']==Decimal('10.10')
    assert result['rows'][0]['order_id']==result['rows'][1]['order_id']
    assert parse('period,visits,paid\nSep,100,20\n') is None

@pytest.mark.parametrize('text',[
    SALES.replace('10.10','NaN',1),SALES.replace('10.10','-1',1),SALES.replace('10.10','10.101',1),
    SALES.replace('2,10.10','-2,10.10',1),SALES.replace('0.20,0','21,0',1),
    SALES.replace('2026-09-01','not-a-date',1),SALES.replace('USD','EUR',1),
    SALES.replace('USD','',1),SALES+SALES.splitlines()[1]+'\n',
    SALES.replace('quantity','unknown_quantity',1),SALES.replace('unit_price','order_total',1),
    SALES.replace('USD,paid','USD,unrecognized',1),
])
def test_invalid_sales_is_rejected_without_inventing_or_silently_dropping_rows(text):
    with pytest.raises(HTTPException) as error:parse(text)
    assert error.value.status_code==422

def test_sql_metrics_count_orders_once_and_handle_discounts_refunds_exclusions(c):
    conv=workspace(c);document=upload(c,conv);m=document['commerce']
    assert m['gross_sales']=='50.30' and m['discounts']=='0.20' and m['refunds']=='5.00'
    assert m['net_revenue']=='45.10' and m['orders']==2 and m['average_order_value']=='22.55'
    assert m['units_sold']==4 and m['excluded_lines']==1
    assert m['products'][0]['product_id']=='TEA' and m['products'][0]['net_revenue']=='30.10'
    assert 'PostgreSQL' in m['calculation_engine']
    with module.conn() as db:
        assert db.execute('SELECT count(*) AS count FROM commerce_sales WHERE document_id=%s',(document['id'],)).fetchone()['count']==4
    assert c.get('/api/documents/'+document['id']+'/commerce').json()==m
    assert len(c.get('/api/documents/'+document['id']+'/commerce/rows').json()['rows'])==4
    current=c.get('/api/conversations/'+conv['id']).json()
    assert current['files'][0]['import']['kind']=='sales'

def test_sales_import_does_not_silently_truncate_at_legacy_funnel_limit(c):
    conv=workspace(c)
    header='order_id,order_date,sku,quantity,unit_price,discount,refund,currency\n'
    text=header+''.join(f'O{i},2026-09-01,TEA,1,1.00,0,0,USD\n' for i in range(1200))
    metrics=upload(c,conv,text)['commerce']
    assert metrics['orders']==1200 and metrics['net_revenue']=='1200.00'
    too_large=header+''.join(f'O{i},2026-09-01,TEA,1,1.00,0,0,USD\n' for i in range(5001))
    with pytest.raises(HTTPException) as error:parse(too_large)
    assert error.value.status_code==422 and '5000' in error.value.detail

def test_catalog_prices_never_become_revenue(c):
    conv=workspace(c);document=upload(c,conv,CATALOG,'catalog.csv');m=document['commerce']
    assert m['products']==2 and m['inventory_units']==40 and m['out_of_stock']==1
    assert m['net_revenue'] is None and m['orders'] is None and m['average_order_value'] is None
    result=run(c,conv)
    assert 'without sales data' in result['output']
    assert 'catalog-quality' in result['report']['recommendations'][0]['title']

def test_missing_adjustments_do_not_become_invented_zero_discounts_or_net_revenue(c):
    conv=workspace(c)
    minimal='order_id,order_date,sku,qty,price,currency\nA,2026-09-01,TEA,2,0.10,USD\n'
    m=upload(c,conv,minimal)['commerce']
    assert m['gross_sales']=='0.20' and m['gross_average_order_value']=='0.20'
    assert m['net_revenue'] is None and m['average_order_value'] is None
    assert m['discounts'] is None and m['refunds'] is None
    assert m['products'][0]['gross_sales']=='0.20' and m['products'][0]['net_revenue'] is None
    assert m['warnings']
    result=run(c,conv)
    assert 'unavailable' in result['output'] and 'gross sales' in result['report']['recommendations'][0]['rationale']

def test_malformed_import_is_atomic_and_removing_source_cascades_structured_rows(c):
    conv=workspace(c)
    bad=c.post('/api/conversations/'+conv['id']+'/files',files={'file':('bad.csv',SALES.replace('10.10','NaN',1).encode())})
    assert bad.status_code==422 and c.get('/api/conversations/'+conv['id']).json()['files']==[]
    document=upload(c,conv)
    assert c.delete('/api/conversations/'+conv['id']+'/files/'+document['id']).status_code==200
    with module.conn() as db:
        assert db.execute('SELECT count(*) AS count FROM commerce_sales WHERE document_id=%s',(document['id'],)).fetchone()['count']==0

def test_chat_to_registered_action_approval_verification_measurement_and_reload(c):
    conv=workspace(c);baseline=upload(c,conv);result=run(c,conv)
    assert '45.10' in result['output'] and '22.55' in result['output'] and 'Unknown' not in result['report']['commerce']['primary']['net_revenue']
    assert result['report']['commerce']['primary']['dataset_id']==baseline['id']
    proposal=result['report']['recommendations'][0]
    assert proposal['evidence'][0]=='commerce:'+baseline['id'] and proposal['risks']
    assert c.get('/api/tasks').json()==[]
    direct=c.post('/api/tool-registry/create_experiment_brief/invoke',json={'arguments':{'execution_id':result['id'],'plan':proposal['title']}})
    assert direct.status_code in (403,409)
    accepted=c.post('/api/executions/'+result['id']+'/decision',json={'approve':True,'plan':proposal['title'],'recommendation_id':proposal['id']})
    assert accepted.status_code==200,accepted.text
    accepted=accepted.json();assert accepted['state']=='COMPLETED'
    actual=accepted['execution_result'];assert actual['tool']=='create_experiment_brief' and actual['verified_task_count']==3
    assert len(c.get('/api/tasks',params={'conversation_id':conv['id']}).json())==3
    assert c.post('/api/executions/'+result['id']+'/decision',json={'approve':True,'plan':'Replay'}).status_code==409
    assert c.post('/api/artifacts/'+accepted['artifact']+'/measure',json={'document_id':baseline['id']}).status_code==422
    followup=upload(c,conv,FOLLOWUP,'followup.csv')
    measured=c.post('/api/artifacts/'+accepted['artifact']+'/measure',json={'document_id':followup['id'],'notes':'Same two-day observation span, no causal inference'})
    assert measured.status_code==200,measured.text
    measure=measured.json();assert measure['changes']['net_revenue']['absolute_change']=='24.90'
    assert measure['changes']['average_order_value']['after']=='35.00' and measure['comparable_duration'] is True
    assert 'not causal' in measure['classification']
    assert c.get('/api/executions/'+result['id']).json()['execution_result']==actual
    assert c.get('/api/artifacts/'+accepted['artifact']+'/measurements').json()[0]['id']==measure['id']
    assert c.get('/api/conversations/'+conv['id']).json()['messages'][-1]['execution']==result['id']
    # Latest snapshot selection never adds the baseline and follow-up together.
    repeated=run(c,conv)
    assert repeated['report']['commerce']['primary']['net_revenue']=='70.00'

def test_rejected_action_and_denied_tool_make_no_tasks(c):
    conv=workspace(c);upload(c,conv);result=run(c,conv)
    policy=c.get('/api/governance/policy').json()
    c.put('/api/governance/policy',json={**policy,'denied_tools':['create_experiment_brief']}).raise_for_status()
    assert c.post('/api/executions/'+result['id']+'/decision',json={'approve':True,'plan':'Denied'}).status_code==403
    assert c.get('/api/tasks').json()==[]
    assert c.get('/api/executions/'+result['id']).json()['state']=='WAITING_FOR_APPROVAL'
    assert c.post('/api/executions/'+result['id']+'/decision',json={'approve':False,'plan':'Reject'}).json()['state']=='CANCELLED'
    assert c.get('/api/reports').json()==[]

def test_measurement_rejects_renamed_baseline_overlaps_currency_and_missing_dates(c):
    conv=workspace(c);baseline=upload(c,conv)['commerce']
    for text in (SALES,SALES.replace('USD','EUR'),SALES.replace('2026-09-01','2026-08-01').replace('2026-09-02','2026-08-02'),SALES.replace('2026-09-01','').replace('2026-09-02','')):
        after=upload(c,conv,text)['commerce']
        with pytest.raises(HTTPException):compare(baseline,after)

def test_main_chat_invokes_real_read_only_mcp_and_records_result(c):
    conv=workspace(c);upload(c,conv)
    server=c.post('/api/mcp/servers',json={'name':'Evidence comparison','profile':'evidence_utilities'}).json()
    assert c.post('/api/mcp/servers/'+server['id']+'/probe').json()['status']=='healthy'
    c.post('/api/tool-registry',json={'name':'sales.compare','description':'Compare two observed rates','adapter':'mcp','server_id':server['id'],'remote_tool':'compare_rates','entities':['sales']}).raise_for_status()
    result=run(c,conv,context_tools=[{'name':'sales.compare','arguments':{'before':4,'after':6}}])
    assert result['report']['connector_status'][0]['status']=='succeeded'
    evidence=next(e for e in result['report']['evidence'] if e['source']=='sales.compare')
    assert json.loads(evidence['excerpt'])['change_percentage_points']==2 and evidence['retrieved_at']
    assert any(e.get('tool')=='sales.compare' for e in result['events'])
    invalid=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Read context','mode':'evidence','context_tools':[{'name':'sales.compare','arguments':{}}]})
    assert invalid.status_code==422 and 'input contract' in invalid.json()['detail']
    response=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Read context','mode':'evidence','context_tools':[{'name':'create_internal_note','arguments':{'conversation_id':conv['id'],'text':'Unapproved write'}}]})
    assert response.status_code==422

def test_market_source_failure_does_not_block_local_sales_analysis(c,monkeypatch):
    conv=workspace(c);upload(c,conv)
    async def offline(*args,**kwargs):raise httpx.ConnectError('offline-private-error')
    monkeypatch.setattr(module,'research',offline)
    result=run(c,conv,public_research=True,market_query='public tea retail discussion')
    assert result['report']['research_status']['status']=='unavailable' and '45.10' in result['output']
    assert 'offline-private-error' not in json.dumps(result)
    assert not result['report'].get('market_sources')

def test_configured_public_source_is_fetched_cited_and_dated_in_real_chat_workflow(c,monkeypatch):
    conv=workspace(c);upload(c,conv);seen=[]
    async def handler(request):
        seen.append(str(request.url))
        assert request.url.host=='hn.algolia.com'
        if request.url.path.endswith('/search'):
            assert request.url.params['query']=='public tea retail discussion'
            return httpx.Response(200,json={'hits':[{'objectID':'123','title':'Retail product comparison discussion','created_at':'2026-09-01T00:00:00Z'}]})
        return httpx.Response(200,json={'text':'Public discussion, not measured store sales','children':[]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    result=run(c,conv,public_research=True,market_query='public tea retail discussion')
    source=result['report']['market_sources'][0]
    assert source['url']=='https://news.ycombinator.com/item?id=123'
    assert source['publication_date']=='2026-09-01T00:00:00Z' and source['retrieved_at']
    assert source['url'] in result['output'] and source['url'] in result['report']['recommendations'][0]['evidence']
    assert result['report']['research_status']['status']=='succeeded' and len(seen)==2
    assert '45.10' in result['output'] and c.get('/api/conversations/'+conv['id']).json()['messages'][-1]['execution']==result['id']

def test_local_only_project_denies_external_research_before_network(c,monkeypatch):
    business=c.post('/api/businesses',json={'name':'Private store','kind':'ecommerce'}).json()
    project=c.post('/api/projects',json={'name':'Local only','business_id':business['id'],'goal':'Keep sales private'}).json()
    conv=c.post('/api/conversations',json={'title':'Private sales','business_id':business['id'],'project_id':project['id']}).json();upload(c,conv)
    async def forbidden(*args,**kwargs):raise AssertionError('Network must not be reached')
    monkeypatch.setattr(module,'research',forbidden)
    response=c.post('/api/conversations/'+conv['id']+'/runs',json={'text':'Review private sales','mode':'evidence','public_research':True,'market_query':'private category'})
    assert response.status_code==403
    result=run(c,conv);assert result['report']['commerce']['primary']['net_revenue']=='45.10'

def test_tenant_and_viewer_cannot_access_structured_sales_or_approve(c):
    conv=workspace(c);document=upload(c,conv);result=run(c,conv)
    owner_cookie=c.cookies.get('evolvyn_session');owner=c.get('/api/auth/me').json()['organization_id']
    email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':email,'password':'commerce-viewer-password','name':'Other tenant'}).raise_for_status();other=c.cookies.get('evolvyn_session')
    assert c.get('/api/documents/'+document['id']+'/commerce').status_code==404
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/')
    c.post('/api/organizations/members',json={'email':email,'role':'viewer'}).raise_for_status()
    c.cookies.set('evolvyn_session',other,domain='testserver.local',path='/');c.headers['X-Organization-Id']=owner
    assert c.get('/api/documents/'+document['id']+'/commerce').status_code==200
    assert c.post('/api/executions/'+result['id']+'/decision',json={'approve':True,'plan':'Viewer bypass'}).status_code==403

def test_private_project_sales_and_action_approvals_keep_their_scope(c):
    business=c.post('/api/businesses',json={'name':'Restricted merchant','kind':'ecommerce'}).json()
    project=c.post('/api/projects',json={'name':'Private sales','business_id':business['id'],'goal':'Protect merchant evidence'}).json()
    conv=c.post('/api/conversations',json={'title':'Restricted sales','business_id':business['id'],'project_id':project['id']}).json();document=upload(c,conv);result=run(c,conv)
    c.put('/api/projects/'+project['id']+'/access',json={'access':'restricted','members':[]}).raise_for_status()
    approval=c.post('/api/tool-registry/create_experiment_brief/request-approval',json={'arguments':{'execution_id':result['id'],'plan':'Create the reviewed internal investigation'}})
    assert approval.status_code==200,approval.text
    assert approval.json()['conversation']==conv['id']
    owner_cookie=c.cookies.get('evolvyn_session');owner=c.get('/api/auth/me').json()['organization_id']
    email=uuid4().hex+'@example.test'
    c.post('/api/auth/register',json={'email':email,'password':'project-editor-password','name':'Editor'}).raise_for_status();editor_cookie=c.cookies.get('evolvyn_session')
    c.cookies.set('evolvyn_session',owner_cookie,domain='testserver.local',path='/')
    c.post('/api/organizations/members',json={'email':email,'role':'editor'}).raise_for_status()
    c.cookies.set('evolvyn_session',editor_cookie,domain='testserver.local',path='/');c.headers['X-Organization-Id']=owner
    assert c.get('/api/documents/'+document['id']+'/commerce/rows').status_code==404
    assert c.get('/api/tool-approvals').json()==[]
    assert c.post('/api/tool-registry/create_experiment_brief/request-approval',json={'arguments':{'execution_id':result['id'],'plan':'Try to read restricted sales'}}).status_code==404
