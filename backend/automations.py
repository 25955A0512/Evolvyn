"""Upload-triggered, condition-gated reviews; durable events, deduplication and human action gates."""
import json
from contextvars import ContextVar
from datetime import datetime,timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid5,NAMESPACE_URL
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from backend.policy import ACTOR,Principal
from backend.agent_memory import reject_secrets

EVENT=ContextVar('automation_event',default=None)
class Condition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    metric:Literal['net_revenue','gross_sales','orders','average_order_value','inventory_units']
    op:Literal['lt','gt','eq']
    value:Decimal=Field(ge=0,le=Decimal('1000000000000'),allow_inf_nan=False)
class Create(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=2,max_length=100)
    conversation_id:str
    query:str=Field(min_length=5,max_length=2000)
    mode:Literal['default','evidence','local','provider','groq','gemini','openrouter']='default'
    condition:Condition|None=None
    enabled:bool=True
class Toggle(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool

def enqueue(c,owner,conversation_id,document_id,automation_id=None):
    rows=c.execute("SELECT id,body FROM records WHERE owner=%s AND kind='automation' AND body->>'conversation_id'=%s AND body->>'enabled'='true' AND (%s::text IS NULL OR id=%s)",(owner,conversation_id,automation_id,automation_id)).fetchall()
    for row in rows:
        id=str(uuid5(NAMESPACE_URL,'upload:'+row['id']+':'+document_id))
        data={'automation_id':row['id'],'conversation':conversation_id,'document_id':document_id,'state':'PENDING','created_at':datetime.now(timezone.utc).isoformat()}
        c.execute("INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,'automation_event',%s) ON CONFLICT(id) DO NOTHING",(id,owner,json.dumps(data)))

class Automations:
    def __init__(self,s):self.s=s
    async def tick(self,owner_filter=None,id_filter=None):
        s=self.s;results=[]
        with s['conn']() as c:
            rows=c.execute("SELECT id,owner,body FROM records WHERE kind='automation_event' AND body->>'state'='PENDING' AND (%s::text IS NULL OR owner=%s) AND (%s::text IS NULL OR body->>'automation_id'=%s) ORDER BY created LIMIT 4 FOR UPDATE SKIP LOCKED",(owner_filter,owner_filter,id_filter,id_filter)).fetchall()
            for row in rows:
                owner,id,data=row['owner'],row['id'],row['body'];token=None;event_token=None
                try:
                    automation=s['POLICY'].raw(owner,data['automation_id'],'automation')['body']
                    if not automation['enabled']:data.update(state='SKIPPED',detail='Automation was paused')
                    else:
                        actor=automation.get('actor')
                        if actor:
                            member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(actor,owner)).fetchone()
                            if not member:raise HTTPException(403,'Creator membership revoked')
                            token=ACTOR.set(Principal(owner,actor,member['role']))
                        else:token=ACTOR.set(Principal(owner,None,'owner' if owner=='initial-workspace' else 'demo'))
                        current=s['get'](owner,automation['conversation_id'],'conversation')
                        previous=c.execute("SELECT id FROM records WHERE owner=%s AND kind='execution' AND body->>'automation_event_id'=%s",(owner,id)).fetchone()
                        if previous:data.update(state='QUEUED',execution_id=previous['id'],detail='Recovered the already-created execution')
                        else:
                            document=s['get'](owner,data['document_id'],'document')
                            if document['conversation']!=automation['conversation_id']:raise HTTPException(403,'Event scope mismatch')
                            condition=automation.get('condition');matches=bool(current['files'] and current['files'][-1]['id']==data['document_id'])
                            if condition and matches:
                                observed=document.get('commerce',{}).get(condition['metric'])
                                matches=observed is not None and {'lt':lambda:Decimal(str(observed))<Decimal(condition['value']),'gt':lambda:Decimal(str(observed))>Decimal(condition['value']),'eq':lambda:Decimal(str(observed))==Decimal(condition['value'])}[condition['op']]()
                                data['condition_result']={'metric':condition['metric'],'observed':observed,'matched':matches}
                            if not matches:data.update(state='SKIPPED',detail='Upload was superseded, condition was false, or the required metric was unavailable')
                            else:
                                event_token=EVENT.set(id)
                                execution=await s['launch'](automation['conversation_id'],s['Message'](text=automation['query'],mode=automation['mode'],allow_fallback=False),owner)
                                data.update(state='QUEUED',execution_id=execution['id'],detail='Review queued; consequential actions still require approval')
                except HTTPException as error:
                    if error.status_code in (409,429):continue # Durable backpressure: retry after the active review finishes.
                    data.update(state='FAILED',detail='Evidence, creator access, route or policy validation failed; no action approved')
                except Exception:data.update(state='FAILED',detail='Automation could not queue a review; no action approved')
                finally:
                    if event_token is not None:EVENT.reset(event_token)
                    if token is not None:ACTOR.reset(token)
                data['processed_at']=datetime.now(timezone.utc).isoformat()
                c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(data),owner,id));results.append({'id':id,**data})
        return results

def install(app,auth,service):
    s=service.s
    @app.get('/api/automations')
    def listing(owner=Depends(auth)):return s['listing'](owner,'automation')
    @app.post('/api/automations')
    def create(body:Create,owner=Depends(auth)):
        s['get'](owner,body.conversation_id,'conversation');s['POLICY'].require(owner,'write');reject_secrets(body.query);reject_secrets(body.name)
        if len(s['listing'](owner,'automation'))>=20:raise HTTPException(422,'Maximum 20 upload automations per workspace')
        return s['save'](owner,'automation',{**json.loads(body.model_dump_json()),'actor':s['POLICY'].principal(owner).account,'trigger':'document_uploaded','created_at':datetime.now(timezone.utc).isoformat()})
    @app.patch('/api/automations/{id}')
    def toggle(id:str,body:Toggle,owner=Depends(auth)):
        row=s['get'](owner,id,'automation');return s['save'](owner,'automation',{k:v for k,v in {**row,'enabled':body.enabled}.items() if k!='id'},id)
    @app.get('/api/automations/{id}/events')
    def events(id:str,owner=Depends(auth)):
        s['get'](owner,id,'automation');return [e for e in s['listing'](owner,'automation_event') if e['automation_id']==id]
    @app.post('/api/automations/{id}/run')
    async def run(id:str,owner=Depends(auth)):
        row=s['get'](owner,id,'automation');s['POLICY'].require(owner,'write')
        if not row['enabled']:raise HTTPException(409,'Resume this automation first')
        conversation=s['get'](owner,row['conversation_id'],'conversation')
        if not conversation['files']:raise HTTPException(422,'Upload evidence to the selected conversation first')
        with s['conn']() as c:enqueue(c,owner,row['conversation_id'],conversation['files'][-1]['id'],id)
        await service.tick(owner,id)
        return [e for e in s['listing'](owner,'automation_event') if e['automation_id']==id]
