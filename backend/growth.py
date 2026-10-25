"""Comparable public discussion windows + first-party evidence, never invented market growth."""
from backend.mcp_registry import is_external
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Literal
import httpx
from fastapi import Depends,HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.agent_memory import MemoryInput,reject_secrets
from backend.registry import ToolContext
from backend.discussion import ContextCall
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit
from pydantic import field_validator

class CampaignDraft(BaseModel):
    """A saved plan, never authority to publish or spend."""
    model_config=ConfigDict(extra='forbid')
    objective:str=Field(min_length=3,max_length=500)
    channel:str=Field(min_length=2,max_length=100)
    audience:str=Field(min_length=3,max_length=1000)
    consent_basis:str=Field(min_length=3,max_length=1000)
    exclusions:str=Field(min_length=3,max_length=1000)
    creative_copy:str=Field(alias='copy',min_length=3,max_length=4000)
    cta:str=Field(min_length=2,max_length=150)
    destination:str=Field(max_length=2000)
    timezone:str=Field(max_length=80)
    starts_at:datetime
    duration_days:int=Field(ge=1,le=90)
    budget:Decimal=Field(ge=0,le=1000000,max_digits=9,decimal_places=2)
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    attribution_tags:str=Field(min_length=3,max_length=500)
    baseline:str=Field(min_length=3,max_length=1000)
    success_metric:str=Field(min_length=3,max_length=1000)
    guardrails:str=Field(min_length=3,max_length=1000)
    stop_conditions:str=Field(min_length=3,max_length=1000)
    @field_validator('*',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value
    @field_validator('destination')
    @classmethod
    def destination_valid(cls,value):
        p=urlsplit(value)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment:raise ValueError('Use an HTTPS destination without credentials or fragment')
        return value
    @field_validator('timezone')
    @classmethod
    def timezone_valid(cls,value):
        try:ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError):raise ValueError('Use an IANA timezone')
        return value
    @field_validator('starts_at')
    @classmethod
    def aware(cls,value):
        if value.tzinfo is None:raise ValueError('Schedule must include a UTC offset')
        return value

class GrowthInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str
    product_id:str|None=None
    query:str=Field(min_length=3,max_length=200)
    public_research:bool=False
    window_days:int=Field(default=30,ge=7,le=90)
    context_tools:list[ContextCall]=Field(default_factory=list,max_length=3)
class ActionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action_id:str

async def public_windows(query,days):
    now=int(datetime.now(timezone.utc).timestamp());period=days*86400
    async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
        async def window(start,end):
            chunks=[];size=0
            async with client.stream('GET','https://hn.algolia.com/api/v1/search_by_date',params={'query':query,'tags':'story','hitsPerPage':5,'numericFilters':f'created_at_i>={start},created_at_i<{end}'}) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    size+=len(chunk)
                    if size>1_000_000:raise ValueError('Research response exceeds budget')
                    chunks.append(chunk)
            value=json.loads(b''.join(chunks))
            count=int(value['nbHits'])
            if count<0:raise ValueError('Invalid discussion count')
            sources=[{'title':str(hit.get('title') or 'Discussion')[:300],'url':'https://news.ycombinator.com/item?id='+str(hit['objectID']),'citation':'hn:'+str(hit['objectID']),'published_at':hit.get('created_at'),'classification':'Unverified public discussion; not a customer sample'} for hit in value.get('hits',[])[:5] if str(hit.get('objectID','')).isdigit()]
            return {'count':count,'start':datetime.fromtimestamp(start,timezone.utc).isoformat(),'end':datetime.fromtimestamp(end,timezone.utc).isoformat(),'sources':sources}
        previous,current=await asyncio.gather(window(now-2*period,now-period),window(now-period,now))
    return {'status':'available','provider':'Hacker News via Algolia','query':query,'window_days':days,'previous':previous,'current':current,'absolute_change':current['count']-previous['count'],'relative_change_percent':round(100*(current['count']-previous['count'])/previous['count'],2) if previous['count'] else None,'classification':'Change in indexed discussion activity for this query, not market size, revenue, demand or representative sentiment'}

def actions(report,market):
    rows=[]
    if report.get('commerce'):
        from backend.commerce import proposals
        for index,item in enumerate(proposals(report)):
            rows.append({'id':'commerce_'+str(index),'title':item['title'],'type':'product','evidence':item['evidence'],'suggestion':item['rationale'],'metric':report['success_metric'],'confidence':'Observed sales contribution; proposed intervention is an unvalidated hypothesis'})
    for index,theme in enumerate(report.get('themes',[])[:4]):
        rows.append({'id':'feedback_'+str(index),'title':'Validate '+theme['label'].lower(),'type':'product','evidence':theme.get('sources',[]),'suggestion':'Interview affected customers, reproduce the reported friction, and scope a small product change before committing to a broad feature.','metric':'Baseline the affected task completion and support volume; compare after a controlled release.','confidence':'Keyword signal; qualitative validation required'})
    rows.append({'id':'promotion','title':'Test a targeted educational campaign','type':'marketing','evidence':[s['citation'] for s in market.get('current',{}).get('sources',[])[:3]],'suggestion':'Choose one audience and channel from verified customer interviews. Test a helpful use-case demo with a tagged landing page and a small fixed budget; compare qualified activation against a baseline.','metric':'Qualified activated accounts per campaign cost; stop if acquisition quality or privacy constraints fail.','confidence':'Experiment hypothesis, not a proven promotion strategy'})
    if not report.get('commerce') and not report.get('facts') and not report.get('themes'):rows.append({'id':'baseline','title':'Collect product and customer baselines','type':'measurement','evidence':[],'suggestion':'Upload dated funnel exports, retention cohorts and consented customer feedback. A public discussion count cannot show whether this product is growing.','metric':'Weekly activation, retention and recurring revenue measured from first-party data.','confidence':'Insufficient first-party evidence'})
    return rows

def measured_change(facts):
    """Compare one uploaded series only when period labels establish chronology."""
    unknown={'status':'insufficient','classification':'Comparable first-party period data is missing, duplicated or spans multiple files. No product growth inferred.'}
    if len(facts)<2:return unknown
    files={f.get('source','').rsplit(':row ',1)[0] for f in facts}
    if len(files)!=1:return unknown
    try:
        if any(not re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?',f['period']) for f in facts):return unknown
        if len({len(f['period']) for f in facts})!=1 or len({f['period'] for f in facts})!=len(facts):return unknown
        for f in facts:datetime.fromisoformat(f['period']+'-01' if len(f['period'])==7 else f['period'])
        rows=sorted(facts,key=lambda f:f['period']);before,after=rows[0],rows[-1]
        return {'status':'available','before':before,'after':after,'visits_change_percent':round(100*(after['visits']-before['visits'])/before['visits'],2),'paid_outcomes_change_percent':round(100*(after['paid']-before['paid'])/before['paid'],2) if before['paid'] else None,'conversion_change_percentage_points':round(after['conversion']-before['conversion'],2),'classification':'Observed change between dated uploaded periods in one series. Period definitions are user-provided; this does not establish causality, recurring revenue, unique customers or market growth.'}
    except (KeyError,TypeError,ValueError,ZeroDivisionError):return unknown

def install(app,auth,s,memory):
    @app.get('/api/growth/conversations/{id}/workspace')
    def workspace(id:str,owner=Depends(auth)):
        conversation=s['get'](owner,id,'conversation')
        kinds=['growth_report','growth_campaign','execution','schedule','task','artifact','measurement']
        with s['conn']() as c:
            rows=c.execute("SELECT id,kind,body FROM records WHERE owner=%s AND kind=ANY(%s) AND (body->>'conversation'=%s OR body->>'conversation_id'=%s) ORDER BY created DESC",(owner,kinds,id,id)).fetchall()
        accessible=[]
        for row in rows:
            try:s['POLICY'].resource(owner,'read',row['kind'],row['body'],row['id'])
            except HTTPException as error:
                if error.status_code in (403,404):continue
                raise
            accessible.append(row)
        def linked(kind):
            return [{'id':r['id'],**r['body']} for r in accessible if r['kind']==kind]
        return {'conversation':conversation,'reports':linked('growth_report'),'campaigns':linked('growth_campaign'),
                'executions':linked('execution'),'schedules':linked('schedule'),'tasks':linked('task'),
                'artifacts':linked('artifact'),'measurements':linked('measurement'),
                'publishing':{'available':False,'reason':'No verified social publisher is implemented. Save a draft; publishing and spend remain unavailable.'}}

    @app.post('/api/growth/reports/{id}/campaigns')
    def campaign(id:str,body:CampaignDraft,owner=Depends(auth)):
        row=s['get'](owner,id,'growth_report');s['POLICY'].require(owner,'write')
        reject_secrets(body.model_dump_json())
        return s['save'](owner,'growth_campaign',{'conversation':row['conversation'],'project_id':row.get('project_id'),
            'growth_report_id':id,'business_id':row.get('business_id'),'plan':body.model_dump(mode='json',by_alias=True),
            'state':'DRAFT','publishing_available':False,'created_at':datetime.now(timezone.utc).isoformat(),
            'actor':s['POLICY'].principal(owner).account,'classification':'Unapproved campaign plan. No delivery or spend has occurred.'})

    @app.get('/api/growth/reports')
    def reports(owner=Depends(auth)):return s['listing'](owner,'growth_report')
    @app.post('/api/growth/reports')
    async def create(body:GrowthInput,owner=Depends(auth)):
        reject_secrets(body.query);conversation=s['get'](owner,body.conversation_id,'conversation');s['POLICY'].require(owner,'write')
        if body.product_id:
            product=s['get'](owner,body.product_id,'product_spec')
            if product.get('project_id')!=conversation.get('project_id'):raise HTTPException(422,'Product and evidence must share project scope')
        if body.public_research:s['POLICY'].data(owner,conversation,'research')
        try:report=await s['TOOL_PLUGINS'].invoke(owner,'analyze_business',{'conversation_id':body.conversation_id,'query':body.query},ToolContext(owner))
        except HTTPException as error:
            if error.status_code!=422:raise
            report={'facts':[],'evidence':[],'themes':[],'classification':'No usable first-party evidence. Upload customer feedback and performance data.'}
        external=[]
        for call in body.context_tools:
            spec=s['TOOL_PLUGINS'].validate(owner,call.name,call.arguments)
            if spec['risk']!='read':raise HTTPException(422,'Growth evidence accepts read-only tools')
            # An explicit same-conversation argument prevents cross-project ingestion.
            if call.arguments.get('conversation_id',body.conversation_id)!=body.conversation_id:raise HTTPException(422,'Connector context must match this conversation')
            if spec['adapter']=='mcp' and is_external(s['TOOL_PLUGINS'].mcp.server(owner,spec['server_id'])):s['POLICY'].data(owner,conversation,'mcp')
            value=await s['TOOL_PLUGINS'].invoke(owner,call.name,call.arguments,ToolContext(owner))
            excerpt=json.dumps(value)[:6000];reject_secrets(excerpt)
            external.append({'citation':'registered-tool:'+call.name,'source':call.name,'excerpt':excerpt,'retrieved_at':datetime.now(timezone.utc).isoformat(),'server_id':spec.get('server_id'),'classification':'Connector-provided observation; verify scope and freshness'})
        market={'status':'not_requested','classification':'No live market source requested'}
        if body.public_research:
            try:market=await public_windows(body.query,body.window_days)
            except (httpx.HTTPError,ValueError,KeyError,TypeError,asyncio.TimeoutError):market={'status':'unavailable','classification':'Public source unavailable. Continuing with first-party evidence; no market trend inferred.'}
        captured=datetime.now(timezone.utc).isoformat()
        sources=[]
        for document in s['scoped_documents'](owner,conversation):
            data=document.get('commerce') or {}
            sources.append({'document_id':document['id'],'name':document['name'],'kind':data.get('kind','document'),
                'citation':data.get('citation'),'content_sha256':data.get('content_sha256'),
                'period':data.get('period'),'currency':data.get('currency'),'included_lines':data.get('included_lines'),
                'excluded_lines':data.get('excluded_lines'),'dated_lines':data.get('dated_lines'),
                'warnings':data.get('warnings',[]),'captured_at':captured,
                'provider':'user upload','mapping_version':'evolvyn-commerce-v1' if data else 'evolvyn-document-v1',
                'provider_account':None,'freshness':'Live sync not configured; capture time is not source freshness'})
        row=s['save'](owner,'growth_report',{'conversation':body.conversation_id,'business_id':conversation.get('business_id'),'project_id':conversation.get('project_id'),'product_id':body.product_id,'query':body.query,'created_at':captured,'sources':sources,'analysis_method':'Deterministic evidence extraction and SQL metrics. Suggestions are rule-based hypotheses; specialist review uses the selected model route.','forecast':{'status':'suppressed','reason':'Comparable complete first-party history and baseline backtesting are not established. No forecast generated.'},'market':market,'report':report,'first_party_change':measured_change(report.get('facts',[])),'connector_evidence':external,'actions':actions(report,market),'classification':'Evidence-led experiment suggestions. No causal growth or market dominance has been established.'})
        return row
    @app.post('/api/growth/reports/{id}/propose')
    def propose(id:str,body:ActionInput,owner=Depends(auth)):
        row=s['get'](owner,id,'growth_report');action=next((a for a in row['actions'] if a['id']==body.action_id),None)
        if not action:raise HTTPException(422,'Unknown report action')
        return memory.propose(owner,MemoryInput(conversation=row['conversation'],category='decision',source_ids=[id],text=action['title']+'\n'+action['suggestion']+'\nMeasurement: '+action['metric']),origin='growth_report')
