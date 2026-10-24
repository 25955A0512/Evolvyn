"""Comparable public discussion windows + first-party evidence, never invented market growth."""
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
            if spec['adapter']=='mcp' and s['TOOL_PLUGINS'].mcp.server(owner,spec['server_id'])['transport']=='streamable_http':s['POLICY'].data(owner,conversation,'mcp')
            value=await s['TOOL_PLUGINS'].invoke(owner,call.name,call.arguments,ToolContext(owner))
            excerpt=json.dumps(value)[:6000];reject_secrets(excerpt)
            external.append({'citation':'registered-tool:'+call.name,'source':call.name,'excerpt':excerpt,'classification':'Connector-provided observation; verify scope and freshness'})
        market={'status':'not_requested','classification':'No live market source requested'}
        if body.public_research:
            try:market=await public_windows(body.query,body.window_days)
            except (httpx.HTTPError,ValueError,KeyError,TypeError,asyncio.TimeoutError):market={'status':'unavailable','classification':'Public source unavailable. Continuing with first-party evidence; no market trend inferred.'}
        row=s['save'](owner,'growth_report',{'conversation':body.conversation_id,'project_id':conversation.get('project_id'),'product_id':body.product_id,'query':body.query,'created_at':datetime.now(timezone.utc).isoformat(),'market':market,'report':report,'first_party_change':measured_change(report.get('facts',[])),'connector_evidence':external,'actions':actions(report,market),'classification':'Evidence-led experiment suggestions. No causal growth or market dominance has been established.'})
        return row
    @app.post('/api/growth/reports/{id}/propose')
    def propose(id:str,body:ActionInput,owner=Depends(auth)):
        row=s['get'](owner,id,'growth_report');action=next((a for a in row['actions'] if a['id']==body.action_id),None)
        if not action:raise HTTPException(422,'Unknown report action')
        return memory.propose(owner,MemoryInput(conversation=row['conversation'],category='decision',source_ids=[id],text=action['title']+'\n'+action['suggestion']+'\nMeasurement: '+action['metric']),origin='growth_report')
