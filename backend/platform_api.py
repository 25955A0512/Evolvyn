"""Project, action, measurement and recurring-analysis APIs over private records."""
import json
from datetime import datetime,timedelta,timezone
from typing import Literal
from uuid import uuid4
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict

class ProjectInput(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    business_id:str
    goal:str=Field(min_length=1,max_length=1000)
    data_policy:Literal['local_only','allow_selected_provider']='local_only'

class TaskUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status:Literal['todo','in_progress','done','cancelled']
    notes:str=Field(default='',max_length=4000)

class Measurement(BaseModel):
    document_id:str
    notes:str=Field(default='',max_length=2000)

class ScheduleInput(BaseModel):
    conversation_id:str
    query:str=Field(min_length=3,max_length=2000)
    interval_minutes:int=Field(ge=1,le=10080)
    mode:Literal['evidence','provider','local','groq','gemini']='evidence'
    enabled:bool=True

class ScheduleToggle(BaseModel):
    enabled:bool


def install(app,services):
    auth,conn,get,save,listing,launch,Message,analyze=[services[k] for k in ('auth','conn','get','save','listing','launch','Message','analyze')]

    @app.get('/api/projects')
    def projects(business_id:str='',owner=Depends(auth)):
        if business_id:get(owner,business_id,'business')
        return [p for p in listing(owner,'project') if not business_id or p['business_id']==business_id]

    @app.post('/api/projects')
    def project(body:ProjectInput,owner=Depends(auth)):
        get(owner,body.business_id,'business')
        return save(owner,'project',{**body.model_dump(),'created_at':datetime.now(timezone.utc).isoformat()})

    @app.get('/api/tasks')
    def tasks(conversation_id:str='',owner=Depends(auth)):
        if conversation_id:get(owner,conversation_id,'conversation')
        return [t for t in listing(owner,'task') if not conversation_id or t['conversation']==conversation_id]

    @app.patch('/api/tasks/{id}')
    def update_task(id:str,body:TaskUpdate,owner=Depends(auth)):
        get(owner,id,'task')
        with conn() as c:
            row=c.execute("SELECT body FROM records WHERE id=%s AND owner=%s AND kind='task' FOR UPDATE",(id,owner)).fetchone()
            record=row['body'];record.update(body.model_dump());record['updated_at']=datetime.now(timezone.utc).isoformat()
            c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(record),id))
        return {'id':id,**record}

    @app.get('/api/reports')
    def reports(owner=Depends(auth)):
        return listing(owner,'artifact')

    @app.post('/api/artifacts/{id}/measure')
    def measure(id:str,body:Measurement,owner=Depends(auth)):
        artifact=get(owner,id,'artifact')
        document=get(owner,body.document_id,'document')
        if document['conversation']!=artifact.get('conversation'):raise HTTPException(422,'Measurement evidence must belong to the same conversation')
        if not document['name'].lower().endswith('.csv'):raise HTTPException(422,'Measurement requires a CSV with period,visits,paid columns')
        report=analyze([document],'measure conversion')
        if not report['facts'] or not artifact.get('baseline'):raise HTTPException(422,'A numerical baseline and follow-up observation are required')
        followup=report['facts'][-1];baseline=artifact['baseline']
        record={'artifact':id,'conversation':artifact['conversation'],'baseline':baseline,'followup':followup,'change_percentage_points':round(followup['conversion']-baseline['conversion'],2),'notes':body.notes,'classification':'Pre/post comparison of user-uploaded observations; not proof of causation','measured_at':datetime.now(timezone.utc).isoformat()}
        return save(owner,'measurement',record)

    @app.get('/api/artifacts/{id}/measurements')
    def measurements(id:str,owner=Depends(auth)):
        get(owner,id,'artifact')
        return [r for r in listing(owner,'measurement') if r['artifact']==id]

    @app.get('/api/schedules')
    def schedules(owner=Depends(auth)):
        return listing(owner,'schedule')

    @app.post('/api/schedules')
    def schedule(body:ScheduleInput,owner=Depends(auth)):
        get(owner,body.conversation_id,'conversation')
        return save(owner,'schedule',{**body.model_dump(),'next_run_at':(datetime.now(timezone.utc)+timedelta(minutes=body.interval_minutes)).isoformat(),'last_run':None,'last_error':None})

    @app.patch('/api/schedules/{id}')
    def toggle(id:str,body:ScheduleToggle,owner=Depends(auth)):
        current=get(owner,id,'schedule');current.update(enabled=body.enabled)
        return save(owner,'schedule',{k:v for k,v in current.items() if k!='id'},id)

    @app.post('/api/schedules/{id}/run')
    async def run_schedule(id:str,owner=Depends(auth)):
        schedule=get(owner,id,'schedule')
        run=await launch(schedule['conversation_id'],Message(text=schedule['query'],mode=schedule['mode'],allow_fallback=True),owner)
        schedule.update(last_run=run['id'],last_error=None,next_run_at=(datetime.now(timezone.utc)+timedelta(minutes=schedule['interval_minutes'])).isoformat())
        save(owner,'schedule',{k:v for k,v in schedule.items() if k!='id'},id)
        return run

    @app.get('/api/workflows')
    def workflows(owner=Depends(auth)):
        return {'nodes':[{'id':'observe','label':'Observe','detail':'Load authorized business files'},{'id':'retrieve','label':'Retrieve','detail':'Rank passages and retain source offsets'},{'id':'analyze','label':'Analyze','detail':'Calculate numerical observations via validated tools'},{'id':'strategy','label':'Prioritize','detail':'Evidence-linked proposals ranked by MCP tool'},{'id':'respond','label':'Explain','detail':'Provider response or explicitly labeled fallback'},{'id':'approval','label':'Human approval','detail':'Backend-enforced decision checkpoint'},{'id':'completed','label':'Execute','detail':'Create internal brief and actionable tasks atomically'},{'id':'measure','label':'Measure','detail':'Compare follow-up CSV observations against the stored baseline'}], 'edges':[['observe','retrieve'],['retrieve','analyze'],['analyze','strategy'],['strategy','respond'],['respond','approval'],['approval','completed'],['completed','measure']], 'limits':{'concurrent_runs':4,'run_seconds':45,'tool_calls':8,'output_tokens':700}}

    @app.delete('/api/conversations/{id}/files/{file_id}')
    def remove_file(id:str,file_id:str,owner=Depends(auth)):
        get(owner,id,'conversation');document=get(owner,file_id,'document')
        if document['conversation']!=id:raise HTTPException(404,'Record not found')
        with conn() as c:
            row=c.execute("SELECT body FROM records WHERE id=%s AND owner=%s FOR UPDATE",(id,owner)).fetchone()
            if c.execute("SELECT id FROM records WHERE owner=%s AND kind='execution' AND body->>'conversation'=%s AND body->>'state' IN ('RUNNING','CREATED')",(owner,id)).fetchone():raise HTTPException(409,'Wait for the active run before removing evidence')
            record=row['body'];record['files']=[f for f in record['files'] if f['id']!=file_id]
            c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(record),id))
            # Historical report excerpts remain as evidence used at the time.
            c.execute('DELETE FROM records WHERE id=%s AND owner=%s',(file_id,owner))
        return {'removed':file_id}
