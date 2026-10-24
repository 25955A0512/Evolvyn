import asyncio
import time
import csv
from itertools import islice
from typing import Literal
import io
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

import httpx
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from backend.retrieval import retrieve
from backend.providers import response_chunks
from backend.file_parser import extract, SUPPORTED
from backend.registry import ToolRegistry, Tool, ToolContext, ToolDenied, ScopeQuery, AnalysisOutput, CandidateInput, RankingOutput
from backend.mcp_gateway import invoke_rank
from backend.strategy import recommendations
from backend.model_strategy import propose as propose_strategy
from backend.text_insights import signals
REGISTRY=ToolRegistry()

DB = os.getenv('DATABASE_URL', 'postgresql://evolvyn@127.0.0.1:5432/evolvyn')
JOBS = {}
STOPPING=False
from backend.execution_queue import WORKER, claim as claim_job, pending as pending_jobs, LEASE_SECONDS
TOKEN = os.getenv('EVOLVYN_ACCESS_TOKEN') or secrets.token_urlsafe(32)

def conn():
    return psycopg.connect(DB, row_factory=dict_row)

from backend.policy import PolicyEngine
POLICY=PolicyEngine(conn)

def init():
    with conn() as c:
        from backend.identity import initialize
        initialize(c)
        c.execute('CREATE TABLE IF NOT EXISTS records (id text PRIMARY KEY, owner text NOT NULL, kind text NOT NULL, body jsonb NOT NULL, created timestamptz DEFAULT now())')
        c.execute('CREATE INDEX IF NOT EXISTS records_tenant_kind_created ON records(owner,kind,created DESC)')
        from backend.commerce import initialize as initialize_commerce
        initialize_commerce(c)
        c.execute("UPDATE records SET body = body || %s::jsonb WHERE kind='execution' AND body->>'state' IN ('RUNNING','CREATED') AND body->>'question' IS NULL", (json.dumps({'state':'FAILED','error':'Process interrupted; rerun analysis. No action executed.'}),))

def save(owner, kind, body, id=None):
    id = id or str(uuid4())
    if kind not in ('audit','demo_session'):POLICY.resource(owner,'write',kind,body,id)
    with conn() as c:
        c.execute('INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET body=EXCLUDED.body WHERE records.owner=EXCLUDED.owner', (id, owner, kind, json.dumps(body)))
    return {'id': id, **body}

def get(owner, id, kind):
    with conn() as c:
        row = c.execute('SELECT * FROM records WHERE id=%s AND owner=%s AND kind=%s', (id, owner, kind)).fetchone()
    if not row:
        raise HTTPException(404, 'Record not found')
    POLICY.resource(owner,'read',kind,row['body'],row['id'])
    body={'id':row['id'],**row['body']}
    if kind=='document' and body.get('commerce'):
        from backend.commerce import metrics
        with conn() as c:body['commerce']=metrics(c,owner,id)
    return body

def listing(owner, kind):
    with conn() as c:
        rows = c.execute('SELECT * FROM records WHERE owner=%s AND kind=%s ORDER BY created DESC', (owner, kind)).fetchall()
    result=[]
    for row in rows:
        try:POLICY.resource(owner,'read',kind,row['body'],row['id'])
        except HTTPException as error:
            if error.status_code in (403,404):continue
            raise
        result.append({'id':row['id'],**row['body']})
    return result

def auth(request:Request,authorization: str = Header(default=''),x_organization_id:str=Header(default='')):
    from backend.identity import resolve
    organization=resolve(request,authorization,x_organization_id,conn)
    if organization:return organization
    if secrets.compare_digest(authorization, 'Bearer ' + TOKEN):return 'initial-workspace'
    if authorization.startswith('Bearer ') and len(authorization)<256:
        import hashlib
        digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
        with conn() as c:
            row=c.execute("SELECT owner FROM records WHERE kind='demo_session' AND body->>'digest'=%s AND (body->>'expires_at')::timestamptz>now()",(digest,)).fetchone()
        if row:return row['owner']
    raise HTTPException(401,'Authentication required or sample session expired')

@asynccontextmanager
async def lifespan(app):
    global STOPPING
    STOPPING=False
    init()
    scheduler=asyncio.create_task(schedule_loop())
    try:yield
    finally:
        STOPPING=True
        scheduler.cancel()
        await asyncio.gather(scheduler,return_exceptions=True)
    tasks=list(JOBS.values())
    for task in tasks: task.cancel()
    if tasks: await asyncio.gather(*tasks,return_exceptions=True)

app = FastAPI(title='Evolvyn', lifespan=lifespan)

class Conversation(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    goal: str = Field(default='Improve paid conversion', max_length=1000)
    business_id: str | None = None
    project_id: str | None = None

from backend.evidence_tools import ContextCall

class Message(BaseModel):
    mode: Literal['default','provider','evidence','local','groq','gemini','openrouter'] = 'provider'
    allow_fallback: bool = False
    workflow_id: str | None = None
    context_tools: list[ContextCall] = Field(default_factory=list,max_length=3)
    public_research: bool = False
    market_query: str = Field(default='',max_length=200)
    analysis_kind: Literal['business','operations'] = 'business'
    text: str = Field(min_length=1, max_length=8000)

class Decision(BaseModel):
    approve: bool
    plan: str = Field(min_length=1, max_length=4000)
    recommendation_id: str | None = None

@app.get('/api/health')
def health():
    with conn() as c:
        c.execute('SELECT 1')
    return {'status': 'ok'}

@app.get('/api/conversations')
def conversations(owner=Depends(auth)):
    return listing(owner, 'conversation')

@app.post('/api/conversations')
def create(body: Conversation, owner=Depends(auth)):
    if body.business_id: get(owner,body.business_id,'business')
    if body.project_id:
        project=get(owner,body.project_id,'project')
        if project['business_id']!=body.business_id:raise HTTPException(422,'Project belongs to a different business')
    return save(owner, 'conversation', {**body.model_dump(), 'messages': [], 'files': [],'created_at':datetime.now(timezone.utc).isoformat()})

@app.get('/api/conversations/{id}')
def conversation(id: str, owner=Depends(auth)):
    return get(owner, id, 'conversation')

@app.post('/api/conversations/{id}/files')
async def upload(id: str, file: UploadFile = File(...), owner=Depends(auth)):
    convo = get(owner, id, 'conversation')
    if len(convo['files']) >= 10:
        raise HTTPException(422, 'Maximum 10 documents per conversation')
    from backend.agent_memory import reject_secrets
    name = Path(file.filename or '').name
    reject_secrets(name)
    if Path(name).suffix.lower() not in SUPPORTED:
        raise HTTPException(415,'Supported formats: TXT, CSV, PDF and DOCX')
    raw = await file.read(2_000_001)
    if len(raw)>2_000_000:raise HTTPException(413,'Maximum file size is 2 MB')
    try:content=await asyncio.to_thread(extract,raw,name)
    except ValueError as exc:raise HTTPException(422,str(exc))
    if not content.strip():raise HTTPException(422,'Document contains no readable text')
    reject_secrets(content)
    from backend.commerce import parse as parse_commerce,persist as persist_commerce
    try:parsed=parse_commerce(content) if name.lower().endswith('.csv') else None
    except csv.Error:raise HTTPException(422,'CSV quoting or row structure is invalid')
    with conn() as c:
        row=c.execute("SELECT body FROM records WHERE id=%s AND owner=%s AND kind='conversation' FOR UPDATE",(id,owner)).fetchone()
        current=row['body']
        if len(current['files'])>=10:raise HTTPException(422,'Maximum 10 documents per conversation')
        if c.execute("SELECT id FROM records WHERE owner=%s AND kind='execution' AND body->>'conversation'=%s AND body->>'state' IN ('RUNNING','CREATED')",(owner,id)).fetchone():
            raise HTTPException(409,'Wait for the running analysis before changing its evidence')
        document_id=str(uuid4())
        c.execute('INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,%s,%s)',(document_id,owner,'document',json.dumps({'name':name,'content':content,'conversation':id})))
        commerce=persist_commerce(c,owner,document_id,parsed) if parsed else None
        if commerce:
            c.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s AND owner=%s",(json.dumps({'commerce':commerce}),document_id,owner))
        current['files'].append({'id':document_id,'name':name,**({'import':{'kind':commerce['kind'],'dataset_id':document_id}} if commerce else {})})
        c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(current),id))
    return {'id':document_id,'name':name,**({'commerce':commerce} if commerce else {})}


def scoped_documents(owner,conversation):
    if conversation.get('files'):
        return [get(owner,file['id'],'document') for file in conversation['files']]
    if not conversation.get('business_id'):return []
    # Reuse only the same project scope; local-only project data never crosses into another project.
    with conn() as c:
        rows=c.execute("SELECT d.id,d.body FROM records d JOIN records v ON v.id=d.body->>'conversation' AND v.owner=d.owner AND v.kind='conversation' WHERE d.owner=%s AND d.kind='document' AND v.body->>'business_id'=%s AND (v.body->>'project_id') IS NOT DISTINCT FROM %s ORDER BY d.created DESC LIMIT 20",(owner,conversation['business_id'],conversation.get('project_id'))).fetchall()
    return [get(owner,row['id'],'document') for row in reversed(rows)]

def business_context(owner,conversation):
    context={'goal':conversation.get('goal','')}
    if conversation.get('business_id'):context['business']=get(owner,conversation['business_id'],'business')
    if conversation.get('project_id'):context['project']=get(owner,conversation['project_id'],'project')
    return context

def analyze(documents, query="business feedback onboarding conversion"):
    from backend.commerce import report as commerce_report
    commerce=commerce_report(documents)
    facts, evidence = [], []
    for doc in documents:
        if doc['name'].lower().endswith('.csv'):
            rows = csv.DictReader(io.StringIO(doc['content']))
            for number, row in enumerate(islice(rows,1000), 2):
                try:
                    visits, paid = int(row['visits']), int(row['paid'])
                    if visits <= 0 or paid < 0 or paid > visits:
                        continue
                    facts.append({'period': row.get('period', str(number)), 'visits': visits, 'paid': paid, 'conversion': round(paid/visits*100, 2), 'source': f"{doc['name']}:row {number}"})
                except (KeyError, ValueError, TypeError):
                    continue
        else:
            evidence.append({'source': doc['name'], 'excerpt': doc['content'][:1800], 'classification': 'user-provided, unverified'})
    evidence = retrieve(documents, query)
    if not facts and not evidence and not commerce:
        raise HTTPException(422, 'Upload sales CSV (order_id, product_id/sku, quantity, unit_price), catalog CSV (product_id/sku, name, price), text evidence, or a period/visits/paid funnel CSV first')
    if commerce:
        evidence.insert(0,{'source':commerce['primary']['source'],'citation':commerce['primary']['citation'],'excerpt':json.dumps(commerce['primary']),'score':1,'classification':'SQL-calculated observations from user-provided business data'})
    decline=len(facts)>=2 and facts[-1]['conversion']<facts[0]['conversion']
    hypothesis=('Conversion is lower in the final uploaded row. Investigate onboarding friction as one unvalidated possibility; row order does not establish chronology or causality.' if decline else 'No causal explanation has been established. Validate the supplied evidence before choosing an intervention.')
    return {**({'commerce':commerce} if commerce else {}),'facts': facts[:100], 'evidence': evidence, 'themes':signals(documents), 'hypothesis': hypothesis, 'plan': ('Create an internal brief to interview customers about onboarding friction and design a controlled experiment.' if decline else 'Create an internal brief to validate the strongest evidence and define a measurable experiment.'), 'recommendation_kind':'Rule-based starting point, not a model-validated recommendation', 'success_metric': ('Compare dated, nonoverlapping sales snapshots using available gross/net sales, distinct orders and the corresponding average order value; keep gross and net definitions separate; validate equal coverage and use an appropriate control before attributing lift.' if commerce and commerce['primary']['kind']=='sales' else 'Collect dated sales lines before measuring sales impact; catalog prices are not realized revenue.' if commerce else 'Compare paid / visits over a predefined 14-day observation period with an appropriate control. No improvement has been measured.' if facts else 'Define an observable outcome and collect a baseline before running an experiment. No business improvement has been measured.'), 'market_research': 'No market research was included in this analysis.'}

async def model_summary(report,question,mode='provider'):
    # The compatibility endpoint shares the same tenant routing and data gateway.
    return ''.join([chunk async for chunk in response_chunks(report,question,[],mode)])

@app.post('/api/conversations/{id}/analyze')
async def run(id: str, body: Message, owner=Depends(auth)):
    from backend.agent_memory import reject_secrets
    reject_secrets(body.text)
    if owner.startswith('demo-'):raise HTTPException(403,'Use the evidence-only background workflow in a sample workspace')
    convo = get(owner, id, 'conversation')
    docs = scoped_documents(owner,convo)
    with model_access.model_scope(owner,'business_analyst'):
        POLICY.data(owner,convo,model_access.effective_mode(body.mode))
    report = analyze(docs, body.text)
    events = [{'stage':'observe','detail':f'Read {len(docs)} authorized documents'}, {'stage':'analyze','detail':f"Calculated e-commerce metrics from structured sales/catalog data" if report.get('commerce') else f"Calculated {len(report['facts'])} conversion observations"}]
    execution = save(owner, 'execution', {'conversation':id, 'state':'RUNNING','events':events,'report':report})
    try:
        with model_access.model_scope(owner,'business_analyst'),model_access.model_data_scope(convo):
            summary = await model_summary(report,body.text,body.mode)
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        execution.update(state='FAILED', error='Provider request failed or timed out. No action executed.')
        save(owner,'execution',{k:v for k,v in execution.items() if k!='id'},execution['id'])
        raise HTTPException(502, 'Provider unavailable; execution recorded as failed')
    execution.update(state='WAITING_FOR_APPROVAL')
    events.append({'stage':'approval','detail':'Waiting for approval to create an internal experiment brief'})
    save(owner,'execution',{k:v for k,v in execution.items() if k!='id'},execution['id'])
    convo['messages'] += [{'role':'user','text':body.text}, {'role':'assistant','text':summary,'execution':execution['id'],'report':report}]
    save(owner,'conversation',{k:v for k,v in convo.items() if k!='id'},id)
    return execution

@app.get('/api/executions/{id}')
def execution(id: str, owner=Depends(auth)):
    return get(owner,id,'execution')

@app.get('/api/executions/{id}/events')
def stream(id: str, owner=Depends(auth)):
    run = get(owner,id,'execution')
    def emit():
        for event in run['events']:
            yield 'data: '+json.dumps(event)+'\n\n'
    return StreamingResponse(emit(),media_type='text/event-stream')

def commit_decision(id: str, decision: Decision, owner):
    POLICY.require(owner,'approve')
    from backend.agent_memory import reject_secrets
    reject_secrets(decision.plan)
    checked=get(owner,id,'execution')
    if checked.get('engine') in ('graph','langgraph_discussion'):raise HTTPException(409,'Use the specialized harness or discussion approval endpoint for this execution')
    # Row lock makes approval and execution one atomic, replay-safe transaction.
    with conn() as c:
        row = c.execute('SELECT * FROM records WHERE id=%s AND owner=%s AND kind=%s FOR UPDATE',(id,owner,'execution')).fetchone()
        if not row:
            raise HTTPException(404,'Record not found')
        run = row['body']
        if run['state'] != 'WAITING_FOR_APPROVAL':
            raise HTTPException(409,'Execution is no longer awaiting approval')
        run['state'] = 'COMPLETED' if decision.approve else 'CANCELLED'
        run['decision'] = decision.model_dump()
        if decision.recommendation_id and not any(r['id']==decision.recommendation_id for r in (run.get('report') or {}).get('recommendations',[])):
            raise HTTPException(422,'Recommendation is not part of this execution')
        if decision.approve:
            artifact = str(uuid4())
            selected=next((r for r in (run.get('report') or {}).get('recommendations',[]) if r['id']==decision.recommendation_id),None)
            if selected is None and (run.get('report') or {}).get('commerce'):
                selected=next(iter(run['report'].get('recommendations',[])),None)
            facts=(run.get('report') or {}).get('facts',[])
            commerce_baseline=(run.get('report') or {}).get('commerce',{}).get('primary')
            titles=selected['tasks'] if selected else ['Validate the cited evidence and record a baseline','Review the approved plan: '+decision.plan[:300],'Measure the experiment outcome and document limitations']
            task_ids=[]
            for title in titles:
                task_id=str(uuid4());task_ids.append(task_id)
                c.execute('INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,%s,%s)',(task_id,owner,'task',json.dumps({'title':title,'status':'todo','artifact':artifact,'execution':id,'conversation':run['conversation'],'notes':'','created_at':datetime.now(timezone.utc).isoformat()})))
            c.execute('INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,%s,%s)',(artifact,owner,'artifact',json.dumps({'plan':decision.plan,'execution':id,'conversation':run['conversation'],'type':'internal experiment brief','tasks':task_ids,'baseline':facts[-1] if facts else None,'commerce_baseline':commerce_baseline,'recommendation':selected,'outcome':'Internal tasks created; business impact not yet measured.'})))
            verified=c.execute("SELECT count(*) AS count FROM records WHERE owner=%s AND kind='task' AND body->>'artifact'=%s AND body->>'execution'=%s",(owner,artifact,id)).fetchone()['count']
            if verified!=len(task_ids):raise HTTPException(500,'Task verification failed; action rolled back')
            result={'tool':'create_experiment_brief','status':'succeeded','effect':'internal_write','artifact_id':artifact,'task_ids':task_ids,'verified_task_count':verified,'executed_at':datetime.now(timezone.utc).isoformat(),'external_effect':'No store, advertising account or external system was changed'}
            run['execution_result']=result
            c.execute("UPDATE records SET body=body || %s::jsonb WHERE owner=%s AND id=%s",(json.dumps({'execution_result':result}),owner,artifact))
            run['artifact'] = artifact
        run['events'].append({'stage':run['state'].lower(),'detail':'Approved brief and internal tasks persisted atomically' if decision.approve else 'Action rejected'})
        c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(run),id))
    return {'id':id,**run}

@app.post('/api/executions/{id}/decision')
async def decide(id: str, decision: Decision, owner=Depends(auth)):
    POLICY.require(owner,'approve')
    if not decision.approve:return commit_decision(id,decision,owner)
    context=ToolContext(owner,permissions=frozenset({'workspace.read','workspace.write'}),approved=True,idempotency_key=id)
    return await TOOL_PLUGINS.invoke(owner,'create_experiment_brief',{'execution_id':id,'plan':decision.plan,'recommendation_id':decision.recommendation_id},context,approved=True)

@app.get('/api/artifacts/{id}')
def artifact(id:str,owner=Depends(auth)):
    return get(owner,id,'artifact')

@app.get('/api/integrations')
def integrations(owner=Depends(auth)):
    return [{'name':'OpenAI','configured':bool(os.getenv('MODEL_API_KEY')),'status':'Credentials configured; connectivity requires a successful test' if os.getenv('MODEL_API_KEY') else 'No service credential configured'}, {'name':'Public discussion discovery','configured':True,'status':'Available without credentials; a research run verifies access'}, {'name':'Local MCP strategy toolkit','configured':True,'status':'Bundled adapter; successful workflow calls verify operation'}]

class ResearchQuery(BaseModel):
    query: str = Field(min_length=3,max_length=200)

@app.post('/api/conversations/{id}/research')
async def research(id:str, body:ResearchQuery, owner=Depends(auth),append_message:bool=True):
    convo=get(owner,id,'conversation')
    POLICY.data(owner,convo,'research')
    from backend.agent_memory import reject_secrets
    reject_secrets(body.query)
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            response=await client.get('https://hn.algolia.com/api/v1/search',params={'query':body.query,'tags':'story','hitsPerPage':5})
            response.raise_for_status()
            hits=response.json()['hits']
            from backend.research import enrich
            excerpts=await enrich(client,hits)
    except (httpx.HTTPError,KeyError,ValueError):
        raise HTTPException(502,'Public research source unavailable. Check access to hn.algolia.com; no research claims were generated.')
    sources=[{'title':str(h.get('title','Untitled'))[:500], 'url':'https://news.ycombinator.com/item?id='+str(h['objectID']), 'publication_date':h.get('created_at'), 'retrieved_at':datetime.now(timezone.utc).isoformat(), 'classification':'Public discussion excerpts and opinions; not verified market facts','excerpts':excerpts.get(str(h['objectID']),[])} for h in hits if str(h.get('objectID','')).isdigit()]
    record=save(owner,'research',{'conversation':id,'query':body.query,'sources':sources})
    if append_message:
        with conn() as c:
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='conversation' FOR UPDATE",(owner,id)).fetchone()
            current=row['body']
            current['messages'].append({'role':'assistant','sources':sources,'text':'Public discussion research for: '+body.query+'\n\n'+'\n'.join(s['title']+'\n'+s['url'] for s in sources)+'\n\nThese are discussion leads, not verified market claims. Research ID: '+record['id']})
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(current),owner,id))
    return record

@app.get('/api/tools')
def tools(owner=Depends(auth)):
    return TOOL_PLUGINS.catalog(owner)

class Business(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    product: str = Field(default='',max_length=1000)
    goal: str = Field(default='Improve paid conversion',min_length=1,max_length=1000)
    kind: Literal['general','ecommerce']='general'

@app.get('/api/businesses')
def businesses(owner=Depends(auth)):
    return listing(owner,'business')

@app.post('/api/businesses')
def create_business(body:Business,owner=Depends(auth)):
    return save(owner,'business',body.model_dump())

@app.get('/api/conversations/{id}/retrieve')
def search_documents(id:str,q:str='',owner=Depends(auth)):
    if not q or len(q)>1000:raise HTTPException(422,'Query must be 1–1000 characters')
    convo=get(owner,id,'conversation')
    return retrieve(scoped_documents(owner,convo),q)

def change_execution(owner,id,patch,allowed=('RUNNING','CREATED')):
    with conn() as c:
        row=c.execute('SELECT body FROM records WHERE id=%s AND owner=%s AND kind=%s FOR UPDATE',(id,owner,'execution')).fetchone()
        if not row:raise HTTPException(404,'Record not found')
        body=row['body']
        if body['state'] not in allowed:return None
        if WORKER.get() and body.get('worker')!=WORKER.get():return None
        body.update(patch)
        c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(body),id))
        return {'id':id,**body}

def finish_message(owner,conversation,execution,text,report=None):
    with conn() as c:
        row=c.execute('SELECT body FROM records WHERE id=%s AND owner=%s FOR UPDATE',(conversation,owner)).fetchone()
        body=row['body']
        current=get(owner,execution,'execution')
        if WORKER.get() and current.get('worker')!=WORKER.get():return
        for message in body['messages']:
            if message.get('execution')==execution and message['role']=='assistant':
                message['text']=text
                if report:message['report']=report
        c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(body),conversation))

async def perform_job(owner,id,question,mode="provider",allow_fallback=False):
    if get(owner,id,'execution').get('engine')=='langgraph_discussion':
        await DISCUSSION.run(owner,id);return
    if get(owner,id,'execution').get('engine')=='graph':
        await GRAPH_HARNESS.run(owner,id);return
    execution=claim_job(conn,owner,id)
    if not execution:
        JOBS.pop(id,None);return
    worker_token=WORKER.set(execution['worker'])
    conversation=execution['conversation']
    events=list(execution.get('events',[]))
    heartbeat=asyncio.create_task(renew_lease(owner,id))
    def checkpoint(stage,detail,**patch):
        events.append({'stage':stage,'detail':detail,'at':datetime.now(timezone.utc).isoformat()})
        if not change_execution(owner,id,{'events':list(events),**patch}):raise asyncio.CancelledError()
    try:
        async with asyncio.timeout(150 if mode=='local' else 45):
            checkpoint('observe','Loading authorized documents',state='RUNNING')
            await asyncio.sleep(0)
            convo=get(owner,conversation,'conversation')
            workflow=execution.get('workflow') or {}
            research_status={'status':'not_requested','detail':'No live research requested for this run'}
            if workflow.get('research') or execution.get('public_research'):
                checkpoint('research','Discovering public discussion sources for this workflow')
                try:
                    researched=await research(conversation,ResearchQuery(query=execution.get('market_query') or question[:200]),owner,append_message=False)
                    research_status={'status':'succeeded','research_id':researched['id'],'query':researched['query']}
                    convo=get(owner,conversation,'conversation')
                except Exception:
                    research_status={'status':'unavailable','detail':'Public discussion source unavailable; no fresh external result was inferred'}
                    checkpoint('research_unavailable','External research is unavailable; continuing with uploaded evidence')
            docs=scoped_documents(owner,convo)
            if execution.get('report',{} ) and execution['report'].get('recommendations'):
                report=execution['report']
                checkpoint('recover','Recovered completed evidence and strategy checkpoint; restarting the interrupted model response')
            else:
                context=ToolContext(owner)
                tool_name='investigate_operations' if execution.get('analysis_kind')=='operations' else 'analyze_business'
                report=await REGISTRY.invoke(tool_name,{'conversation_id':conversation,'query':question},context)
                events.extend(context.trace)
                report['evidence']=report['evidence'][:workflow.get('citations',5)]
                if execution.get('context_tools'):
                    from backend.evidence_tools import collect
                    trace_start=len(context.trace)
                    extra,statuses=await collect(TOOL_PLUGINS,owner,convo,[ContextCall.model_validate(v) for v in execution['context_tools']],context)
                    events.extend(context.trace[trace_start:])
                    report['evidence']+=extra;report['connector_status']=statuses
                    checkpoint('context','Read selected registered tools through the shared policy gateway',report=report)
                report['business_context']=business_context(owner,convo)
                report['knowledge_scope']='Current attachments' if convo.get('files') else 'Prior uploaded evidence from this business and project'
                with conn() as c:
                    prior_research=c.execute("SELECT body FROM records WHERE owner=%s AND kind='research' AND body->>'conversation'=%s ORDER BY created DESC LIMIT 1",(owner,conversation)).fetchone()
                if prior_research and research_status['status']!='unavailable':report['market_sources']=prior_research['body']['sources']
                if execution.get('analysis_kind')=='operations':
                    from backend.operations import proposals as operational_proposals
                    proposals=operational_proposals(report)
                else:proposals=recommendations(report)
                if mode!='evidence':
                    checkpoint('strategy','Generating schema-validated proposals with the selected model',report=report)
                    try:
                        proposals=await propose_strategy(report,question,mode)
                        report['recommendation_kind']='Model-generated hypotheses with schema-validated evidence references'
                    except Exception:
                        report['strategy_fallback']='Structured model proposals unavailable; showing evidence-linked heuristic proposals.'
                ranking=await REGISTRY.invoke('prioritize_actions',{'candidates':[{key:r[key] for key in ('id','title','impact','confidence','effort')} for r in proposals]},context)
                by_id={r['id']:r for r in proposals}
                report['recommendations']=[dict(by_id[row['id']],priority_score=row['score']) for row in ranking['ranked']][:workflow.get('recommendations',3)]
                report['strategy_engine']=ranking.get('engine','mcp')
                report['plan']=report['recommendations'][0]['title']+': '+report['recommendations'][0]['rationale']
                checkpoint('strategy','Prioritized evidence-linked proposals through the shared tool registry',report=report)
            report['business_context']=business_context(owner,convo)
            report['research_status']=research_status
            with conn() as c:
                latest=c.execute("SELECT body FROM records WHERE owner=%s AND kind='research' AND body->>'conversation'=%s ORDER BY created DESC LIMIT 1",(owner,conversation)).fetchone()
            if latest and research_status['status']!='unavailable':
                report['market_sources']=latest['body']['sources']
                report['market_research']='Includes prior public discussion discovery; these sources are unverified discussion leads, not established market facts.'
            checkpoint('retrieve',f"Retrieved {len(report['evidence'])} passages with source offsets",report=report)
            await asyncio.sleep(0)
            checkpoint('analyze',f"Calculated e-commerce metrics from structured sales/catalog data" if report.get('commerce') else f"Calculated {len(report['facts'])} conversion observations")
            checkpoint('respond',('Generating with local AI on this machine' if mode=='local' else ('Requesting selected provider: '+mode if mode!='evidence' else 'Rendering deterministic evidence; no model is called')))
            output=''
            try:
                async for delta in response_chunks(report,question,convo['messages'][:-2],mode):
                    output+=delta
                    if not change_execution(owner,id,{'output':output}):raise asyncio.CancelledError()
                    await asyncio.sleep(0)
            except (httpx.HTTPError,ValueError,KeyError,IndexError):
                if not allow_fallback:raise
                report['provider_status']='The model provider was unavailable or rejected authentication. Showing deterministic evidence and heuristic recommendations instead.'
                checkpoint('fallback',report['provider_status'],report=report)
                output=''
                async for delta in response_chunks(report,question,convo['messages'][:-2],'evidence'):
                    output+=delta
                    if not change_execution(owner,id,{'output':output}):raise asyncio.CancelledError()
            if not output:raise ValueError('Empty model output')
            events.append({'stage':'approval','detail':'Waiting for authorization to create an internal experiment brief','at':datetime.now(timezone.utc).isoformat()})
            if change_execution(owner,id,{'state':'WAITING_FOR_APPROVAL','events':events,'report':report,'output':output}):
                finish_message(owner,conversation,id,output,report)
    except asyncio.CancelledError:
        if STOPPING:
            change_execution(owner,id,{'state':'CREATED','worker':None,'lease_until':None,'events':events+[{'stage':'paused','detail':'Worker stopped; queued for checkpoint recovery'}]})
        else:
            changed=change_execution(owner,id,{'state':'CANCELLED','events':events+[{'stage':'cancelled','detail':'Stopped before any action was executed'}]})
            if changed:finish_message(owner,conversation,id,'Analysis cancelled. No action was executed.')
        raise
    except httpx.HTTPStatusError as exc:
        error=('Provider authentication failed. Update MODEL_API_KEY securely in environment settings, or explicitly choose evidence-only mode.' if exc.response.status_code==401 else 'Provider request was rejected. Check provider configuration, access and quota.')
        changed=change_execution(owner,id,{'state':'FAILED','error':error,'events':events+[{'stage':'failed','detail':error}]})
        if changed:finish_message(owner,conversation,id,error)
    except Exception:
        # Error internals may include secret headers or business text; never persist them.
        changed=change_execution(owner,id,{'state':'FAILED','error':f'Analysis failed or exceeded its {150 if mode=="local" else 45}-second budget. No action executed.','events':events+[{'stage':'failed','detail':'Analysis failed; retry after checking provider configuration and input.'}]})
        if changed:finish_message(owner,conversation,id,changed['error'])
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat,return_exceptions=True)
        WORKER.reset(worker_token)
        JOBS.pop(id,None)

@app.post('/api/conversations/{id}/runs',status_code=202)
async def launch(id:str,body:Message,owner=Depends(auth)):
    from backend.agent_memory import reject_secrets
    reject_secrets(body.text)
    convo=get(owner,id,'conversation')
    workflow=get(owner,body.workflow_id,'workflow') if body.workflow_id else None
    if workflow:body=body.model_copy(update={'mode':workflow['mode'],'text':body.text+'\nWorkflow focus: '+workflow['focus']})
    if owner.startswith('demo-') and body.mode not in ('evidence','local'):
        raise HTTPException(403,'Sample workspaces use evidence-only mode. Open your private workspace to use configured model credentials.')
    if convo.get('project_id'):
        project=get(owner,convo['project_id'],'project')
        # The centralized data policy resolves the configured model route below.
    from backend.model_access import model_scope,effective_mode
    with model_scope(owner,'business_analyst'):POLICY.data(owner,convo,effective_mode(body.mode))
    from backend.evidence_tools import validate as validate_context
    validate_context(TOOL_PLUGINS,owner,convo,body.context_tools)
    if body.public_research or (workflow and workflow.get('research')):
        POLICY.data(owner,convo,'research')
        if body.public_research and len(body.market_query.strip())<3:raise HTTPException(422,'Enter an explicit public research query (3–200 characters)')
        reject_secrets(body.market_query)
    # Preflight catches invalid evidence before creating a background execution.
    analyze(scoped_documents(owner,convo),body.text)
    if len(JOBS)>=4:raise HTTPException(429,'Four analyses are already running; wait for a slot')
    with conn() as c:
        row=c.execute('SELECT body FROM records WHERE id=%s AND owner=%s FOR UPDATE',(id,owner)).fetchone()
        convo=row['body']
        active=c.execute("SELECT id FROM records WHERE owner=%s AND kind='execution' AND body->>'conversation'=%s AND body->>'state' IN ('CREATED','RUNNING')",(owner,id)).fetchone()
        if active:raise HTTPException(409,'This conversation already has a running analysis')
        execution_id=str(uuid4())
        execution={'conversation':id,'state':'CREATED','events':[],'output':'','question':body.text,'mode':body.mode,'allow_fallback':body.allow_fallback,'workflow':workflow,'context_tools':[v.model_dump() for v in body.context_tools],'public_research':body.public_research,'market_query':body.market_query,'analysis_kind':body.analysis_kind,'actor':POLICY.principal(owner).account,'report':None}
        c.execute('INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,%s,%s)',(execution_id,owner,'execution',json.dumps(execution)))
        convo['messages'] += [{'role':'user','text':body.text},{'role':'assistant','text':'Analysis in progress…','execution':execution_id}]
        c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(convo),id))
    task=asyncio.create_task(perform_job(owner,execution_id,body.text,body.mode,body.allow_fallback))
    JOBS[execution_id]=task
    return {'id':execution_id,**execution}

@app.post('/api/executions/{id}/cancel')
async def cancel_job(id:str,owner=Depends(auth)):
    previous=get(owner,id,'execution')
    changed=change_execution(owner,id,{'state':'CANCELLED','events':previous['events']+[{'stage':'cancelled','detail':'Cancelled by workspace owner; no action executed'}]},allowed=('RUNNING','CREATED','WAITING_FOR_APPROVAL'))
    if not changed:raise HTTPException(409,'Execution is already terminal')
    if id in JOBS:JOBS[id].cancel()
    finish_message(owner,previous['conversation'],id,'Analysis cancelled. No action was executed.')
    return changed

@app.get('/api/executions/{id}/live')
async def live_events(id:str,owner=Depends(auth)):
    get(owner,id,'execution')
    async def emit():
        previous=None
        for _ in range(660):
            execution=get(owner,id,'execution')
            payload=json.dumps(execution)
            if payload!=previous:
                yield 'data: '+payload+'\n\n'
                previous=payload
            if execution['state'] not in ('RUNNING','CREATED'):return
            await asyncio.sleep(.25)
    return StreamingResponse(emit(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.post('/api/providers/test')
async def test_provider(owner=Depends(auth)):
    if owner.startswith('demo-'):return {'available':False,'reason':'sample_workspace_uses_evidence_mode'}
    if not os.getenv('MODEL_API_KEY'):
        return {'available':False,'reason':'missing_credential'}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response=await client.post('https://api.openai.com/v1/chat/completions',headers={'Authorization':'Bearer '+os.environ['MODEL_API_KEY']},json={'model':os.getenv('MODEL_NAME','gpt-4o-mini'),'max_tokens':5,'messages':[{'role':'user','content':'Reply OK.'}]})
        if response.status_code==401:return {'available':False,'reason':'authentication_rejected'}
        if response.status_code!=200:return {'available':False,'reason':'provider_rejected_request'}
        return {'available':bool(response.json().get('choices')),'reason':'responded'}
    except (httpx.HTTPError,ValueError):
        return {'available':False,'reason':'unavailable_or_timed_out'}


async def analyze_tool(arguments,context):
    conversation=get(context.owner,arguments.conversation_id,'conversation')
    docs=scoped_documents(context.owner,conversation)
    return analyze(docs,arguments.query)

async def prioritize_tool(arguments,context):
    candidates=[candidate.model_dump() for candidate in arguments.candidates]
    try:
        ranked=await invoke_rank(candidates)
        return {'ranked':ranked,'engine':'MCP stdio · Evolvyn strategy toolkit'}
    except Exception:
        # A computational fallback is visible and does not imply a successful MCP call.
        return {'ranked':sorted([{'id':r['id'],'score':round(r['impact']*r['confidence']/r['effort'],4)} for r in candidates],key=lambda r:r['score'],reverse=True),'engine':'Local deterministic fallback · MCP unavailable'}

REGISTRY.register(Tool('analyze_business','Calculate metrics and retrieve only authorized conversation evidence',ScopeQuery,AnalysisOutput,analyze_tool,timeout=8))
REGISTRY.register(Tool('prioritize_actions','Rank proposed actions with an allowlisted MCP tool; impact is a heuristic estimate',CandidateInput,RankingOutput,prioritize_tool,timeout=14))

from backend.platform_api import install as install_platform
install_platform(app,{name:globals()[name] for name in ('auth','conn','get','save','listing','launch','Message','analyze','POLICY')})

async def schedule_tick():
    """Claim due schedules under a row lock; never approve their proposed actions."""
    with conn() as c:
        rows=c.execute("SELECT id,owner,body FROM records WHERE kind='schedule' AND body->>'enabled'='true' AND (body->>'next_run_at')::timestamptz <= now() ORDER BY created LIMIT 4 FOR UPDATE SKIP LOCKED").fetchall()
        claimed=[]
        for row in rows:
            body=row['body']
            from datetime import timedelta
            body['next_run_at']=(datetime.now(timezone.utc)+timedelta(minutes=body['interval_minutes'])).isoformat()
            c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(body),row['id']))
            claimed.append((row['owner'],row['id'],body))
    for owner,id,body in claimed:
        actor_token=None
        try:
            if body.get('actor'):
                from backend.policy import ACTOR,Principal
                with conn() as c:member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(body['actor'],owner)).fetchone()
                if not member:
                    body['enabled']=False
                    raise HTTPException(403,'Schedule membership was revoked')
                actor_token=ACTOR.set(Principal(owner,body['actor'],member['role']))
            run=await launch(body['conversation_id'],Message(text=body['query'],mode=body['mode'],allow_fallback=True),owner)
            body.update(last_run=run['id'],last_error=None)
        except Exception:
            body['last_error']='Run could not start; check evidence and whether this conversation already has an active analysis.'
        finally:
            if actor_token:ACTOR.reset(actor_token)
        save(owner,'schedule',body,id)

async def schedule_loop():
    while True:
        try:
            await schedule_tick()
            await dispatch_pending()
            await MCP_REGISTRY.health_tick()
        except Exception:pass  # Database readiness is surfaced by /api/health; avoid sensitive logs.
        await asyncio.sleep(5)

class ToolInvocation(BaseModel):
    model_config={'extra':'forbid'}
    arguments:dict

@app.post('/api/tools/{name}/invoke')
async def invoke_tool(name:str,body:ToolInvocation,owner=Depends(auth)):
    from pydantic import ValidationError
    if not any(t['name']==name for t in TOOL_PLUGINS.catalog(owner)):raise HTTPException(403,'Tool unavailable or permission denied')
    try:
        context=ToolContext(owner)
        result=await TOOL_PLUGINS.invoke(owner,name,body.arguments,context)
        return {'result':result,'trace':context.trace}
    except ToolDenied:raise HTTPException(403,'Tool unavailable or permission denied')
    except ValidationError:raise HTTPException(422,'Tool arguments or output do not match the required schema')
    except __import__('jsonschema').ValidationError:raise HTTPException(422,'Tool arguments do not match the registered schema')
    except TimeoutError:raise HTTPException(504,'Tool execution exceeded its timeout')

@app.post('/api/demo/session')
async def demo_session():
    """Create an isolated, expiring sample workspace without exposing configured data."""
    import hashlib
    from datetime import timedelta
    with conn() as c:
        active=c.execute("SELECT count(*) AS count FROM records WHERE kind='demo_session' AND (body->>'expires_at')::timestamptz > now()").fetchone()['count']
    if active>=25:raise HTTPException(429,'Sample workspace capacity reached. Use your private workspace token instead.')
    owner='demo-'+str(uuid4());token=secrets.token_urlsafe(32)
    save(owner,'demo_session',{'digest':hashlib.sha256(token.encode()).hexdigest(),'expires_at':(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat()})
    business=save(owner,'business',{'name':'Northstar Tasks · sample','product':'Synthetic project management SaaS','goal':'Investigate paid conversion using synthetic evidence'})
    project=save(owner,'project',{'name':'Activation investigation','business_id':business['id'],'goal':'Validate the funnel and customer feedback'})
    conversation=save(owner,'conversation',{'title':'Find the next move for Northstar','goal':project['goal'],'business_id':business['id'],'project_id':project['id'],'files':[],'messages':[],'created_at':datetime.now(timezone.utc).isoformat()})
    root=Path(__file__).resolve().parent.parent/'sample-data'
    for name in ('funnel.csv','customer-feedback.txt'):
        document=save(owner,'document',{'name':name,'content':(root/name).read_text(),'conversation':conversation['id']})
        conversation['files'].append({'id':document['id'],'name':name})
    save(owner,'conversation',{k:v for k,v in conversation.items() if k!='id'},conversation['id'])
    sample_mode='evidence'
    try:
        async with httpx.AsyncClient(timeout=2,trust_env=False) as client:
            if (await client.get('http://127.0.0.1:8081/health')).status_code==200:sample_mode='local'
    except httpx.HTTPError:pass
    run=await launch(conversation['id'],Message(text='Analyze the funnel and customer feedback. What should we investigate first?',mode=sample_mode,allow_fallback=True),owner)
    return {'token':token,'conversation_id':conversation['id'],'business_id':business['id'],'execution_id':run['id'],'expires_in_hours':24,'analysis_mode':sample_mode,'classification':'Isolated synthetic demonstration with local AI' if sample_mode=='local' else 'Isolated synthetic demonstration with labeled evidence-only fallback'}

from backend.identity import install as install_identity
install_identity(app,conn,auth)
from backend.security import install as install_security
install_security(app,save)

@app.get('/api/audit')
def audit_records(request:Request,owner=Depends(auth)):
    identity=getattr(request.state,'identity',None)
    if owner!='initial-workspace' and (not identity or identity['role'] not in ('owner','admin')):raise HTTPException(403,'Administrator access required')
    return listing(owner,'audit')[:200]


async def renew_lease(owner,id):
    from datetime import timedelta
    while True:
        await asyncio.sleep(10)
        changed=change_execution(owner,id,{'lease_until':(datetime.now(timezone.utc)+timedelta(seconds=LEASE_SECONDS)).isoformat()})
        if not changed:return

async def dispatch_pending():
    for row in pending_jobs(conn,4-len(JOBS)):
        if row['id'] not in JOBS:
            body=row['body']
            JOBS[row['id']]=asyncio.create_task(perform_job(row['owner'],row['id'],body['question'],body.get('mode','evidence'),body.get('allow_fallback',True)))

@app.get('/api/providers')
async def provider_list(owner=Depends(auth)):
    from backend.providers import PROVIDERS
    entries=[]
    for id,config in PROVIDERS.items():
        with model_access.model_scope(owner,'business_analyst'):
            try:configured=not config['key'] or bool(model_access.key_for(id,config))
            except HTTPException:configured=False
        entry={'id':id,'name':config['name'],'model':os.getenv(config['model_env'],config['default_model']),'requires_api_key':bool(config['key']),'configured':configured}
        if id=='local':
            try:
                async with httpx.AsyncClient(timeout=2,trust_env=False) as client:
                    response=await client.get('http://127.0.0.1:8081/health')
                entry['available']=response.status_code==200
            except httpx.HTTPError:entry['available']=False
            entry['status']='ready' if entry['available'] else 'Model weights not installed or local server stopped'
        else:entry['status']='Credential configured; test connection' if entry['configured'] else 'Optional provider; no credential configured'
        entries.append(entry)
    return entries

@app.post('/api/providers/{provider}/test')
async def check_selected_provider(provider:str,owner=Depends(auth)):
    if provider not in ('local','provider','groq','gemini','openrouter'):raise HTTPException(404,'Unknown provider')
    if owner.startswith('demo-') and provider!='local':raise HTTPException(403,'Sample workspaces cannot use remote credentials')
    report={'facts':[],'evidence':[]}
    try:
        text=''
        async with asyncio.timeout(30):
            async for chunk in response_chunks(report,'Reply with a brief greeting.',[],provider):text+=chunk
        if text.startswith('Deterministic evidence mode'):return {'available':False,'reason':'missing_provider_credential'}
        return {'available':bool(text),'reason':'responded','usage':report.get('usage')}
    except Exception:return {'available':False,'reason':'Provider unavailable; check the model service or optional credentials'}

@app.get('/api/usage')
def usage(owner=Depends(auth)):
    runs=listing(owner,'execution')
    counts={};seen=set()
    from backend.providers import PROVIDERS
    for run in runs:
        entries=[]
        if (run.get('report') or {}).get('usage'):entries.append(run['report']['usage'])
        for output in run.get('discussion_checkpoint',{}).get('outputs',{}).values():
            reported=output.get('usage')
            if reported:
                mode=output.get('mode');entries.append({**reported,'provider':PROVIDERS.get(mode,{}).get('name',mode or 'Unknown'),'cost_usd':0 if mode=='local' else None})
        for entry in entries:
            key=entry.get('provider','Unknown');row=counts.setdefault(key,{'provider':key,'runs':0,'calls':0,'prompt_tokens':0,'completion_tokens':0,'known_cost_usd':0,'cost_is_complete':True})
            row['calls']+=1
            if (run['id'],key) not in seen:row['runs']+=1;seen.add((run['id'],key))
            row['prompt_tokens']+=entry.get('prompt_tokens') or 0;row['completion_tokens']+=entry.get('completion_tokens') or 0
            if entry.get('cost_usd') is None:row['cost_is_complete']=False
            else:row['known_cost_usd']+=entry['cost_usd']
    return {'providers':list(counts.values()),'total_runs':len(runs),'note':'Only provider-reported completions are counted; unreported failed attempts are excluded. Unknown prices are not estimated. Local CPU and electricity costs are excluded.'}

from backend.workflows import install as install_workflows
install_workflows(app,auth,get,save,listing)


async def operations_tool(arguments,context):
    from backend.operations import investigate
    conversation=get(context.owner,arguments.conversation_id,'conversation')
    documents=scoped_documents(context.owner,conversation)
    if not documents:raise HTTPException(422,'Upload authorized logs or a runbook first')
    return investigate(documents,arguments.query)

REGISTRY.register(Tool('investigate_operations','Triage uploaded alerts, inspect logs and changes, retrieve runbooks and report verification prerequisites; no live production monitoring is implied',ScopeQuery,AnalysisOutput,operations_tool,timeout=8))

from backend.policy_api import install as install_policy
install_policy(app,auth,POLICY,get,save,listing)


from backend.mcp_registry import MCPRegistry,install as install_mcp
MCP_REGISTRY=MCPRegistry(get,save,listing,POLICY)
install_mcp(app,auth,MCP_REGISTRY)
from backend.tool_plugins import ToolPlugins,install as install_tool_plugins,NoteInput,NoteOutput
TOOL_PLUGINS=ToolPlugins(REGISTRY,MCP_REGISTRY,POLICY,get,save,listing)
REGISTRY.policy=POLICY

async def create_note_tool(arguments,context):
    from uuid import uuid5,NAMESPACE_URL
    get(context.owner,arguments.conversation_id,'conversation')
    id=str(uuid5(NAMESPACE_URL,'evolvyn-note:'+context.owner+':'+context.idempotency_key)) if context.idempotency_key else None
    return save(context.owner,'project_note',{'conversation':arguments.conversation_id,'text':arguments.text},id)
REGISTRY.register(Tool('create_internal_note','Create a private project note after explicit human approval',NoteInput,NoteOutput,create_note_tool,permission='workspace.write',risk='internal_write',timeout=5,idempotent=True))
install_tool_plugins(app,auth,TOOL_PLUGINS)


from backend.graph_harness import GraphHarness,install as install_graph_harness
GRAPH_HARNESS=GraphHarness({name:globals()[name] for name in ('get','save','listing','conn','JOBS','POLICY','TOOL_PLUGINS','change_execution','claim_job','renew_lease','finish_message','response_chunks')})
GRAPH_HARNESS.s['stopping']=lambda:STOPPING
install_graph_harness(app,auth,GRAPH_HARNESS)


# The vault owns ciphertext only; model credentials live in a request-local scope.
from backend.vault import Vault, install as install_vault
from backend import model_access
VAULT=Vault(conn,POLICY)
model_access.VAULT=VAULT
model_access.POLICY=POLICY
MCP_REGISTRY.vault=VAULT
install_vault(app,auth,VAULT)
from backend.agent_memory import Memory,install as install_memory
MEMORY=Memory(get,save,listing,POLICY)
install_memory(app,auth,MEMORY)
from backend.agent_gateway import AgentGateway,install as install_agents
AGENTS=AgentGateway(get,save,listing,POLICY,MEMORY,VAULT,TOOL_PLUGINS)
install_agents(app,auth,AGENTS)
GRAPH_HARNESS.s['MEMORY']=MEMORY
GRAPH_HARNESS.s['AGENTS']=AGENTS
from backend.discussion import Discussion,install as install_discussion
DISCUSSION=Discussion({name:globals()[name] for name in ('get','save','listing','conn','JOBS','POLICY','TOOL_PLUGINS','change_execution','claim_job','renew_lease','finish_message')},AGENTS)
DISCUSSION.s['stopping']=lambda:STOPPING
install_discussion(app,auth,DISCUSSION)
from backend.product_studio import Studio,install as install_studio
STUDIO=Studio(get,save,listing,POLICY)
install_studio(app,auth,STUDIO)

_original_perform_job=perform_job
async def perform_job(owner,id,question,mode='provider',allow_fallback=False):
    from backend.policy import ACTOR,Principal
    actor_token=None
    try:
        body=POLICY.raw(owner,id,'execution')['body']
        if body.get('actor'):
            with conn() as c:member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(body['actor'],owner)).fetchone()
            if not member:raise HTTPException(403,'Execution membership was revoked')
            actor_token=ACTOR.set(Principal(owner,body['actor'],member['role']))
        conversation=get(owner,body['conversation'],'conversation')
        with model_access.model_scope(owner,'business_analyst'),model_access.model_data_scope(conversation):
            selected=model_access.effective_mode(mode)
            POLICY.data(owner,conversation,selected)
            await _original_perform_job(owner,id,question,selected,allow_fallback)
    except HTTPException:
        change_execution(owner,id,{'state':'FAILED','error':'Execution access or data policy changed; review authorization before retrying'})
    finally:
        if actor_token:ACTOR.reset(actor_token)
        if JOBS.get(id) is asyncio.current_task():JOBS.pop(id,None)

class ProductBuildToolInput(BaseModel):
    model_config={'extra':'forbid'}
    spec_id:str
    revision:int=Field(ge=1)
class ProductBuildToolOutput(BaseModel):
    model_config={'extra':'allow'}
    id:str
    state:str
async def build_product_tool(arguments,context):
    return await STUDIO.build(context.owner,arguments.spec_id,arguments.revision,approved=context.approved)
REGISTRY.register(Tool('build_product','Generate a versioned authenticated product starter from approved requirements; never execute arbitrary generated code',ProductBuildToolInput,ProductBuildToolOutput,build_product_tool,permission='workspace.write',risk='internal_write',timeout=30))

class RecallInput(BaseModel):
    model_config={'extra':'forbid'}
    query:str=Field(max_length=2000)
    project_id:str|None=None
    agent:str='shared'
class RecallOutput(BaseModel):
    memories:list[dict]
async def recall_memory_tool(arguments,context):
    if arguments.project_id:get(context.owner,arguments.project_id,'project')
    return {'memories':MEMORY.recall(context.owner,arguments.query,arguments.project_id,arguments.agent)}
REGISTRY.register(Tool('recall_agent_memory','Retrieve reviewed agent memory with project, role, retention and provenance filters',RecallInput,RecallOutput,recall_memory_tool,timeout=5))


from backend.canvas import install as install_canvas
install_canvas(app,auth,get,save,listing,POLICY)
from backend.runtime_catalog import install as install_runtime_catalog
install_runtime_catalog(app,auth,TOOL_PLUGINS,POLICY)
from backend.growth import install as install_growth
install_growth(app,auth,{name:globals()[name] for name in ('get','save','listing','POLICY','TOOL_PLUGINS')},MEMORY)
from backend.oauth import install as install_oauth
install_oauth(app,conn,auth)


class BriefActionInput(BaseModel):
    model_config={'extra':'forbid'}
    execution_id:str
    plan:str=Field(min_length=1,max_length=4000)
    recommendation_id:str|None=None
class BriefActionOutput(BaseModel):
    model_config={'extra':'allow'}
    id:str
    state:str
async def create_experiment_brief_tool(arguments,context):
    from backend.agent_memory import reject_secrets
    reject_secrets(arguments.plan)
    if not context.approved:raise HTTPException(403,'Server-issued approval is required')
    return commit_decision(arguments.execution_id,Decision(approve=True,plan=arguments.plan,recommendation_id=arguments.recommendation_id),context.owner)
REGISTRY.register(Tool('create_experiment_brief','Create and verify tracked internal experiment tasks after explicit approval; never changes an external store',BriefActionInput,BriefActionOutput,create_experiment_brief_tool,permission='workspace.write',risk='internal_write',timeout=10,idempotent=True))

@app.get('/api/documents/{id}/commerce')
def commerce_dataset(id:str,owner=Depends(auth)):
    document=get(owner,id,'document')
    if not document.get('commerce'):raise HTTPException(422,'This document has no validated e-commerce import')
    return document['commerce']

@app.get('/api/documents/{id}/commerce/rows')
def commerce_rows(id:str,offset:int=0,limit:int=50,owner=Depends(auth)):
    document=get(owner,id,'document')
    if not document.get('commerce'):raise HTTPException(422,'This document has no validated e-commerce import')
    if offset<0 or not 1<=limit<=100:raise HTTPException(422,'Use a nonnegative offset and limit 1–100')
    table='commerce_sales' if document['commerce']['kind']=='sales' else 'commerce_catalog'
    with conn() as c:rows=c.execute('SELECT * FROM '+table+' WHERE document_id=%s ORDER BY row_number LIMIT %s OFFSET %s',(id,limit,offset)).fetchall()
    return {'dataset_id':id,'rows':[{k:(str(v) if isinstance(v,__import__('decimal').Decimal) else v.isoformat() if isinstance(v,__import__('datetime').date) else v) for k,v in row.items()} for row in rows]}
