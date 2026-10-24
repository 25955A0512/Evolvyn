"""Requirements interview, versioned LangGraph source builds and persistent scoped prototypes."""
import io
import json
import re
import zipfile
import hashlib
from uuid import uuid4
from datetime import datetime,timezone
from typing import Literal,TypedDict
from fastapi import Depends,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,Field
from langgraph.graph import StateGraph,START,END
from langsmith import tracing_context
from backend.agent_memory import reject_secrets
from backend.product_templates import generate,validate

STACKS=[{'id':'react_fastapi','name':'React + FastAPI + PostgreSQL','supported':True},{'id':'react_express','name':'React + Express + PostgreSQL','supported':True},{'id':'custom','name':'Custom stack — requirements and architecture only','supported':False}]
QUESTIONS=[
 ('audience','Who will use this product, and what problem must it solve?','People who need a private workspace to manage their work.'),
 ('stack','Which technology stack should this project use?','react_fastapi'),
 ('theme','Should the product use a light or dark theme?','light'),
 ('accent','What primary brand color should it use? Enter a hex color.','#336b58'),
 ('features','What features should the product include? Separate them with commas.','Private accounts, create records, view records, delete records'),
 ('entities','What data should it manage? Confirm or edit this JSON data model.','[{"name":"tasks","label":"Tasks","fields":[{"name":"title","label":"Title","type":"text"},{"name":"status","label":"Status","type":"text"}]}]'),
 ('authentication','Confirm private email/password accounts. Team SSO and custom roles require an additional adapter.','private_accounts'),
 ('privacy','What privacy classification applies: internal, confidential, or public?','internal'),
 ('integrations','Which integrations will it need? These are requirements until explicitly connected.','None for the first version'),
 ('acceptance','What outcomes must pass before you accept the product?','Users can register and sign in; records persist; users cannot read other users records; layout works on mobile.'),
 ('deployment','Where should it eventually run? Include region or compliance constraints.','Local Docker first; cloud deployment after review'),
]
class FieldSpec(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label:str=Field(min_length=1,max_length=60)
    type:Literal['text','number','email','date']='text'
class Entity(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label:str=Field(min_length=1,max_length=60)
    fields:list[FieldSpec]=Field(min_length=1,max_length=10)
class NewProduct(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=2,max_length=100)
    goal:str=Field(min_length=5,max_length=2000)
    project_id:str|None=None
class Answer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    field:str
    text:str=Field(min_length=1,max_length=8000)
    revision:int=Field(ge=1)
class BuildRequest(BaseModel):
    revision:int=Field(ge=1)
class ApplyDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    memory_id:str
    revision:int=Field(ge=1)
    changes:dict[str,str]=Field(min_length=1,max_length=11)
class BuildState(TypedDict):
    files:dict
    attempts:int
    checks:list
    error:str

def next_question(spec):
    return next(({'field':key,'question':question,'suggested_answer':suggestion} for key,question,suggestion in QUESTIONS if key not in spec['requirements']),None)
def parsed_answer(field,text):
    if len(text)>8000:raise HTTPException(422,'Requirement answer is too long')
    reject_secrets(text)
    if field=='entities':
        try:
            value=[Entity.model_validate(row).model_dump() for row in json.loads(text)]
            if not 1<=len(value)<=6 or len({row['name'] for row in value})!=len(value) or any(len({f['name'] for f in row['fields']})!=len(row['fields']) for row in value):raise ValueError()
            return value
        except Exception:raise HTTPException(422,'Data model must be JSON with 1–6 unique entities and 1–10 unique typed fields each')
    if field=='accent' and not re.fullmatch(r'#[0-9a-fA-F]{6}',text):raise HTTPException(422,'Use a six-digit hex color')
    if field=='theme' and text not in ('light','dark'):raise HTTPException(422,'Choose light or dark')
    if field=='stack' and len(text)>150:raise HTTPException(422,'Stack choice is too long')
    if field=='authentication' and text!='private_accounts':raise HTTPException(422,'Verified adapters currently implement private_accounts; custom auth requires a separate adapter')
    if field=='privacy' and text not in ('internal','confidential','public'):raise HTTPException(422,'Choose internal, confidential or public')
    if field in ('features','integrations'):return [part.strip() for part in re.split(r'[,\n]',text) if part.strip()][:20]
    return text.strip()

class Studio:
    def __init__(self,get,save,listing,policy):self.get,self.save,self.listing,self.policy=get,save,listing,policy
    def present(self,row):return {**row,'next_question':next_question(row),'ready':next_question(row) is None}
    async def build(self,owner,id,revision,approved=False):
        spec=self.get(owner,id,'product_spec');self.policy.require(owner,'write')
        if spec['revision']!=revision:raise HTTPException(409,'Requirements changed; refresh before building')
        if next_question(spec):raise HTTPException(422,'Complete the requirements interview first')
        self.policy.tool(owner,'build_product','internal_write','workspace.write',{'workspace.write'},approved)
        requirements={**spec['requirements'],'name':spec['name'],'goal':spec['goal']}
        if requirements['stack'] not in ('react_fastapi','react_express'):raise HTTPException(422,'This stack has no verified build adapter. Its requirements are saved; select a supported adapter or connect an isolated custom-code runner.')
        id_build=str(uuid4());events=[]
        record={'spec_id':id,'project_id':spec.get('project_id'),'revision':revision,'spec':requirements,'state':'BUILDING','events':events,'engine':'LangGraph + trusted source adapters','created_at':datetime.now(timezone.utc).isoformat(),'files':{},'implemented_capabilities':['Private account registration and sign-in','Owner-scoped entity CRUD','Responsive themed React UI','PostgreSQL configuration and Docker source','Complete isolated Evolvyn agent runtime and console'],'pending_requirements':[feature for feature in requirements.get('features',[]) if feature.lower() not in {'private accounts','create records','view records','delete records','update records','crud'}],'integration_status':'Requested integrations are recorded as requirements; connector implementation is separate.'}
        self.save(owner,'product_build',record,id_build)
        def persist(stage,detail):events.append({'stage':stage,'detail':detail});self.save(owner,'product_build',record,id_build)
        async def architect(state):
            persist('architect','Resolved chosen stack, data model, private-account boundary and UI theme')
            return {'attempts':state['attempts'],'files':{},'checks':[],'error':''}
        async def developer(state):
            persist('developer','Generated frontend, authenticated backend, database configuration and Docker source')
            return {'files':generate(requirements),'attempts':state['attempts']+1,'checks':[],'error':''}
        async def reviewer(state):
            try:checks=validate(state['files']);error=''
            except Exception:checks=[];error='Source validation failed'
            persist('reviewer','Validated source manifest and Python syntax; arbitrary generated code was not executed')
            return {'checks':checks,'error':error}
        graph=StateGraph(BuildState);graph.add_node('architect',architect);graph.add_node('developer',developer);graph.add_node('reviewer',reviewer)
        graph.add_edge(START,'architect');graph.add_edge('architect','developer');graph.add_edge('developer','reviewer');graph.add_conditional_edges('reviewer',lambda state:'retry' if state['error'] and state['attempts']<2 else 'done',{'retry':'developer','done':END})
        try:
            with tracing_context(enabled=False):
                result=await graph.compile().ainvoke({'files':{},'attempts':0,'checks':[],'error':''},{'recursion_limit':10})
            record.update(state='READY' if not result['error'] else 'FAILED',files=result['files'],checks=result['checks'],error=result['error'],source_sha256=hashlib.sha256(json.dumps(result['files'],sort_keys=True).encode()).hexdigest(),validation_scope='Source/contract validation only. Run the generated application and project-specific acceptance tests before deployment.')
        except Exception:record.update(state='FAILED',error='Build adapter failed; requirements are retained')
        return self.save(owner,'product_build',record,id_build)

def install(app,auth,studio):
    @app.get('/api/studio/stacks')
    def stacks(owner=Depends(auth)):return STACKS
    @app.get('/api/studio/products')
    def products(owner=Depends(auth)):return [studio.present(row) for row in studio.listing(owner,'product_spec')]
    @app.post('/api/studio/products')
    def create(body:NewProduct,owner=Depends(auth)):
        reject_secrets(body.goal);reject_secrets(body.name)
        if body.project_id:studio.get(owner,body.project_id,'project')
        row=studio.save(owner,'product_spec',{**body.model_dump(),'requirements':{},'revision':1,'messages':[{'role':'user','text':body.goal},{'role':'assistant','text':QUESTIONS[0][1]}]})
        return studio.present(row)
    @app.get('/api/studio/products/{id}')
    def read(id:str,owner=Depends(auth)):return studio.present(studio.get(owner,id,'product_spec'))
    @app.post('/api/studio/products/{id}/answers')
    def answer(id:str,body:Answer,owner=Depends(auth)):
        studio.get(owner,id,'product_spec');studio.policy.require(owner,'write')
        if body.field not in {row[0] for row in QUESTIONS}:raise HTTPException(422,'Unknown requirement')
        value=parsed_answer(body.field,body.text)
        with studio.policy.conn() as c:
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_spec' FOR UPDATE",(owner,id)).fetchone();data=row['body']
            if data['revision']!=body.revision:raise HTTPException(409,'Requirements changed; refresh before answering')
            data['requirements'][body.field]=value;data['revision']+=1
            data['messages'].append({'role':'user','text':body.field+': '+body.text})
            question=next_question(data);data['messages'].append({'role':'assistant','text':question['question'] if question else 'Requirements captured. Review your choices, then build a versioned product starter.'})
            studio.policy.resource(owner,'write','product_spec',data,id)
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(data),owner,id))
        return studio.present({'id':id,**data})
    @app.post('/api/studio/products/{id}/build')
    async def build(id:str,body:BuildRequest,owner=Depends(auth)):
        studio.policy.require(owner,'approve')
        return await studio.build(owner,id,body.revision,approved=True)
    @app.post('/api/studio/products/{id}/decisions')
    def apply_decision(id:str,body:ApplyDecision,owner=Depends(auth)):
        product=studio.get(owner,id,'product_spec');studio.get(owner,body.memory_id,'agent_memory');studio.policy.require(owner,'write')
        known={row[0] for row in QUESTIONS}
        if not set(body.changes)<=known:raise HTTPException(422,'Decision contains an unknown requirement field')
        changes={key:parsed_answer(key,value) for key,value in body.changes.items()}
        with studio.policy.conn() as c:
            source=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='agent_memory' FOR UPDATE",(owner,body.memory_id)).fetchone()
            if not source:raise HTTPException(404,'Decision memory was removed')
            memory=source['body']
            if memory.get('state')!='ACCEPTED' or memory.get('category')!='decision' or datetime.fromisoformat(memory['expires_at'])<=datetime.now(timezone.utc):raise HTTPException(409,'Use a current, reviewed decision')
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_spec' FOR UPDATE",(owner,id)).fetchone();data=row['body']
            if data['revision']!=body.revision:raise HTTPException(409,'Requirements changed; review this decision against the current revision')
            if memory.get('project_id')!=data.get('project_id'):raise HTTPException(422,'Decision must belong to the same project scope')
            data['requirements'].update(changes);data['revision']+=1
            data.setdefault('decision_history',[]).append({'memory_id':body.memory_id,'changes':changes,'revision':data['revision'],'actor':studio.policy.principal(owner).account})
            data['messages'].append({'role':'assistant','text':'Applied your reviewed decision to '+', '.join(changes)+'. Prior source builds are unchanged; rebuild to apply this requirements revision.'})
            studio.policy.resource(owner,'write','product_spec',data,id)
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(data),owner,id))
        return studio.present({'id':id,**data})
    @app.get('/api/studio/builds')
    def builds(owner=Depends(auth)):return studio.listing(owner,'product_build')
    @app.get('/api/studio/builds/{id}')
    def read_build(id:str,owner=Depends(auth)):return studio.get(owner,id,'product_build')
    @app.get('/api/studio/builds/{id}/download')
    def download(id:str,owner=Depends(auth)):
        row=studio.get(owner,id,'product_build')
        if row['state']!='READY':raise HTTPException(409,'Build is not ready')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            for path,content in row['files'].items():archive.writestr(path,content)
        return Response(stream.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="evolvyn-product.zip"','Cache-Control':'no-store'})
    def entity(owner,id,name):
        row=studio.get(owner,id,'product_build')
        if row['state']!='READY':raise HTTPException(409,'Build is not ready')
        spec=next((e for e in row['spec']['entities'] if e['name']==name),None)
        if not spec:raise HTTPException(404,'Entity not found')
        return row,spec
    @app.get('/api/studio/builds/{id}/preview/{name}')
    def rows(id:str,name:str,owner=Depends(auth)):
        entity(owner,id,name)
        return [row for row in studio.listing(owner,'prototype_item') if row['build_id']==id and row['entity']==name]
    @app.post('/api/studio/builds/{id}/preview/{name}')
    def insert(id:str,name:str,body:dict,owner=Depends(auth)):
        row,spec=entity(owner,id,name)
        if set(body)!={f['name'] for f in spec['fields']}:raise HTTPException(422,'Supply exactly the configured fields')
        for field in spec['fields']:
            value=body[field['name']]
            if field['type']=='number':
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not __import__('math').isfinite(value):raise HTTPException(422,'Invalid number')
            elif not isinstance(value,str) or not value.strip() or len(value)>2000:raise HTTPException(422,'Invalid field')
            else:
                reject_secrets(value)
                if field['type']=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise HTTPException(422,'Invalid email')
                if field['type']=='date':
                    try:__import__('datetime').date.fromisoformat(value)
                    except ValueError:raise HTTPException(422,'Invalid date')
        return studio.save(owner,'prototype_item',{'build_id':id,'project_id':row.get('project_id'),'entity':name,'data':body})
    @app.delete('/api/studio/builds/{id}/preview/{name}/{item}')
    def delete(id:str,name:str,item:str,owner=Depends(auth)):
        entity(owner,id,name);row=studio.get(owner,item,'prototype_item');studio.policy.require(owner,'write')
        if row['build_id']!=id or row['entity']!=name:raise HTTPException(404,'Record not found')
        with studio.policy.conn() as c:c.execute("DELETE FROM records WHERE owner=%s AND id=%s AND kind='prototype_item'",(owner,item))
        return {'deleted':True}
