"""Product interviews and deliverables composed on the existing governed graph harness."""
import json,re,os
from datetime import datetime,timezone
from typing import Literal
from uuid import uuid4
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from backend.registry import Tool
from backend.graph_harness import Definition
from backend.product_studio import QUESTIONS,parsed_answer,next_question,Entity
from backend.agent_memory import reject_secrets

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Scope(Strict):
    spec_id:str
    revision:int=Field(ge=1)
class Turn(Scope):
    text:str=Field(min_length=1,max_length=2000)
    mode:Literal['default','local','provider','groq','gemini','openrouter']='default'
    intent:Literal['chat','plan']='chat'
class Pipeline(Scope):
    mode:Literal['default','local','provider','groq','gemini','openrouter']='default'
    agents:list[Literal['prd','architecture','developer','reviewer']]=Field(default_factory=lambda:['prd','architecture','developer','reviewer'],min_length=1,max_length=4)
    build_source:bool=True
    generation:Literal["model","template"]="model"
class Interview(Strict):
    reply:str=Field(min_length=1,max_length=3000)
    proposed_requirements:dict[str,str]=Field(default_factory=dict,max_length=11)
class ProductPlan(Interview):
    reply:str=Field(min_length=1,max_length=600)
class FilePlan(Strict):
    files:list[str]=Field(max_length=512)
    scope:str
class DiagramNode(Strict):
    id:str=Field(pattern=r'^[a-z][a-z0-9_]{0,19}$')
    label:str=Field(min_length=1,max_length=70)
class DiagramEdge(Strict):
    source:str
    target:str
class Architecture(Strict):
    nodes:list[DiagramNode]=Field(min_length=3,max_length=8)
    edges:list[DiagramEdge]=Field(min_length=1,max_length=12)
    notes:str=Field(default='',max_length=1200)
    @model_validator(mode='after')
    def valid_edges(self):
        ids={n.id for n in self.nodes}
        if len(ids)!=len(self.nodes) or any(e.source not in ids or e.target not in ids for e in self.edges):raise ValueError('Invalid diagram references')
        return self
class Section(Strict):
    heading:str=Field(min_length=1,max_length=100)
    text:str=Field(min_length=1,max_length=500)
class Experience(Strict):
    headline:str=Field(min_length=1,max_length=150)
    description:str=Field(min_length=1,max_length=700)
    sections:list[Section]=Field(default_factory=list,max_length=4)
class Review(Strict):
    approved:bool=Field(description="Design consistency only; never permission to execute. Source writes still require human approval.")
    summary:str=Field(min_length=1,max_length=1500)
    issues:list[str]=Field(default_factory=list,max_length=10)
class TextResult(BaseModel):
    model_config=ConfigDict(extra='allow')
    facts:list=Field(default_factory=list)
    evidence:list=Field(default_factory=list)
    requirements_text:str=''
class ParseInterview(Strict):
    spec_id:str
    revision:int
    text:str=Field(max_length=16000)
    plan:bool=False
class Contracts(Scope):
    prd:str=Field(default='',max_length=16000)
    architecture:str=Field(default='',max_length=16000)
    developer:str=Field(default='',max_length=16000)
    reviewer:str=Field(default='',max_length=16000)
class Blueprint(Strict):
    prd:str=''
    architecture:Architecture|None=None
    experience:Experience|None=None
    review:Review|None=None
    can_build:bool
class Implement(Scope):
    blueprint:Blueprint
    mode:Literal["default","local","provider","groq","gemini","openrouter"]="default"
    generation:Literal["model","template"]="template"
    file_tokens:int=Field(default=4096,ge=1024,le=8192)
    token_budget:int=Field(default=65536,ge=8192,le=131072)
class Built(BaseModel):
    id:str
    state:str
    source_sha256:str

def decoded(text,model):
    reject_secrets(text)
    text=re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',text.strip())
    return model.model_validate_json(text)

def response_schema(model):
    # Harness references deliberately have a different meaning from JSON Schema
    # references. Inline our finite, nonrecursive response contracts before use.
    schema=model.model_json_schema();definitions=schema.pop('$defs',{})
    def inline(value):
        if isinstance(value,list):return [inline(item) for item in value]
        if isinstance(value,dict):
            if '$ref' in value:return inline(definitions[value['$ref'].rsplit('/',1)[-1]])
            return {key:inline(item) for key,item in value.items()}
        return value
    schema=inline(schema)
    if model in (Interview,ProductPlan):
        schema['properties']['proposed_requirements']={'type':'object','properties':{key:{'type':'string'} for key,_,_ in QUESTIONS},'additionalProperties':False,'maxProperties':11 if model is ProductPlan else 2}
        fields=schema['properties']['proposed_requirements']['properties']
        for key,values in {'theme':['light','dark'],'stack':['react_fastapi','react_express','custom'],'authentication':['private_accounts'],'privacy':['internal','confidential','public']}.items():fields[key]['enum']=values
        fields['accent']['pattern']='^#[0-9a-fA-F]{6}$'
        if model is ProductPlan:
            proposal=schema['properties']['proposed_requirements']
            proposal['required']=[key for key,_,_ in QUESTIONS]
            for value in fields.values():value['minLength']=1
            for key in ('audience','features','integrations','acceptance','deployment'):fields[key]['maxLength']=140
            fields['entities']={'type':'array','items':response_schema(Entity),'minItems':1,'maxItems':6}
            # Emit the actionable setup before explanation; this keeps compact
            # local-model budgets from being spent on prose and an empty plan.
            reply={**schema['properties']['reply'],'maxLength':180}
            schema['properties']={'proposed_requirements':proposal,'reply':reply}
            schema['required']=['proposed_requirements','reply']
    if model is Architecture:
        # Match the actual supported three-tier adapter and fit the per-agent
        # output budget. An oversized graph must not be truncated into a build.
        nodes=schema['properties']['nodes'];nodes.update(minItems=3,maxItems=3)
        nodes['items']['properties']['id']['enum']=['web','api','db']
        nodes['items']['properties']['label']['maxLength']=50
        edges=schema['properties']['edges'];edges.update(minItems=2,maxItems=2)
        for key in ('source','target'):edges['items']['properties'][key]['enum']=['web','api','db']
        schema['properties']['notes']['maxLength']=240
    if model is Experience:
        schema['properties']['description']['maxLength']=240
        schema['properties']['sections']['maxItems']=2
        schema['properties']['sections']['items']['properties']['text']['maxLength']=200
    if model is Review:
        schema['properties']['summary']['maxLength']=300
        schema['properties']['issues'].update(maxItems=3,items={'type':'string','maxLength':160})
    return schema

class ProductAgents:
    def __init__(self,services):self.s=services
    def spec(self,owner,id,revision):
        spec=self.s['get'](owner,id,'product_spec')
        if spec['revision']!=revision:raise HTTPException(409,'Requirements changed; refresh before continuing')
        return spec
    def conversation(self,owner,spec):
        s=self.s;s['POLICY'].require(owner,'write')
        with s['conn']() as c:
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_spec' FOR UPDATE",(owner,spec['id'])).fetchone();data=row['body']
            if not data.get('conversation_id'):
                id=str(uuid4());body={'title':data['name']+' · product discussion','goal':data['goal'],'project_id':data.get('project_id'),'business_id':None,'files':[],'messages':[],'created_at':datetime.now(timezone.utc).isoformat()}
                if body['project_id']:body['business_id']=s['get'](owner,body['project_id'],'project')['business_id']
                s['POLICY'].resource(owner,'write','conversation',body,id)
                c.execute('INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,%s,%s)',(id,owner,'conversation',json.dumps(body)))
                data['conversation_id']=id;c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(data),owner,spec['id']))
            id=data['conversation_id']
        return s['get'](owner,id,'conversation')
    async def graph(self,owner,spec,definition):
        definition=Definition.model_validate(definition);conversation=self.conversation(owner,spec)
        from backend.model_access import model_scope,effective_mode
        for node in definition.nodes:
            if node.type=='agent':
                with model_scope(owner,node.agent_id):
                    from backend.model_errors import ModelFailure
                    try:selected=effective_mode(node.mode)
                    except ModelFailure:raise HTTPException(422,'Product agents need a saved Gemini or Groq key in Key vault.') from None
                    if selected=='evidence':raise HTTPException(422,'Product agents need a saved Gemini or Groq key in Key vault.')
        graph=self.s['save'](owner,'agent_graph',definition.model_dump())
        run=await self.s['GRAPH_HARNESS'].start(owner,graph['id'],conversation['id'])
        key='last_interview_run' if any(n.id=='interview' for n in definition.nodes) else 'last_build_run'
        with self.s['conn']() as c:c.execute("UPDATE records SET body=body || %s::jsonb WHERE owner=%s AND id=%s",(json.dumps({'last_agent_run':run['id'],key:run['id']}),owner,spec['id']))
        return run
    async def requirements(self,args,context):
        spec=self.spec(context.owner,args.spec_id,args.revision)
        snapshot={'name':spec['name'],'goal':spec['goal'],'revision':spec['revision'],'requirements':spec['requirements'],'missing':[key for key,_,_ in QUESTIONS if key not in spec['requirements']]}
        with self.s['conn']() as c:document=c.execute("SELECT body->>'text' AS text FROM records WHERE owner=%s AND id=%s AND kind='product_document'",(context.owner,'prd:'+spec['id'])).fetchone()
        if document:snapshot['prd_draft']=document['text'][:6000]
        text=json.dumps(snapshot,ensure_ascii=False)
        messages=self.s['get'](context.owner,spec['conversation_id'],'conversation')['messages'][:-2] if spec.get('conversation_id') else []
        conversation_text=json.dumps([{'role':m['role'],'text':m['text'][:2000]} for m in messages[-6:]])
        return {'facts':[],'evidence':[{'source':'User-approved requirements','citation':'product:'+spec['id']+':'+str(spec['revision']),'excerpt':text}],'requirements_text':text,'conversation_text':conversation_text}
    async def parse_interview(self,args,context):
        self.spec(context.owner,args.spec_id,args.revision)
        text=args.text
        if args.plan:
            # Model planning uses a typed entity array rather than asking the LLM
            # to double-escape nested JSON. Normalize into the existing reviewed
            # proposal contract; parsed_answer still validates every entity.
            reject_secrets(text)
            value=json.loads(re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',text.strip()))
            proposed=value.get('proposed_requirements',{})
            if isinstance(proposed.get('entities'),list):proposed['entities']=json.dumps(proposed['entities'])
            text=json.dumps(value)
        parsed=decoded(text,Interview)
        known={key for key,_,_ in QUESTIONS}
        if not set(parsed.proposed_requirements)<=known:raise ValueError('Unknown requirement proposal')
        for key,value in parsed.proposed_requirements.items():parsed_answer(key,value)
        return parsed.model_dump()
    async def file_plan(self,args,context):
        spec=self.spec(context.owner,args.spec_id,args.revision)
        if next_question(spec):raise HTTPException(422,'Confirm the proposed setup before planning source')
        if spec['requirements']['stack'] not in ('react_fastapi','react_express'):return {'files':[],'scope':'Custom stack: architecture only; no verified source adapter'}
        from backend.product_templates import generate
        files=sorted(generate({**spec['requirements'],'name':spec['name'],'goal':spec['goal']}))
        return {'files':files,'scope':'Planned paths from the selected source adapter. No source artifact is saved by this planning step; agent documents may add files.'}
    async def contracts(self,args,context):
        self.spec(context.owner,args.spec_id,args.revision)
        result={'prd':args.prd,'architecture':decoded(args.architecture,Architecture).model_dump() if args.architecture else None,'experience':decoded(args.developer,Experience).model_dump() if args.developer else None,'review':decoded(args.reviewer,Review).model_dump() if args.reviewer else None}
        reject_secrets(json.dumps(result));result['can_build']=not result['review'] or result['review']['approved']
        return Blueprint.model_validate(result).model_dump()
    async def implement(self,args,context):
        spec=self.spec(context.owner,args.spec_id,args.revision)
        if not args.blueprint.can_build or (args.blueprint.review and not args.blueprint.review.approved):raise HTTPException(409,'Reviewer requested changes; revise the product before implementation')
        blueprint=args.blueprint.model_dump();blueprint['execution_id']=context.execution_id
        if args.generation=='model':
            from backend.model_source import ModelSourceBuilder
            builder=ModelSourceBuilder(self.s)
            build=await builder.build(context.owner,spec,blueprint,args.mode,context.approved,context.execution_id,args.file_tokens,args.token_budget)
        else:build=await self.s['STUDIO'].build(context.owner,spec['id'],args.revision,approved=context.approved,blueprint=blueprint)
        if build['state']!='READY':raise __import__('backend.model_errors',fromlist=['ModelFailure']).ModelFailure(build.get('error_code','source_build_failed'),build.get('error','The source build failed; inspect saved files and the build result.'))
        return {k:build[k] for k in ('id','state','source_sha256')}
    def install(self,app,auth):
        s=self.s
        @app.get('/api/studio/products/{id}/agent-history')
        def history(id:str,owner=Depends(auth)):
            spec=s['get'](owner,id,'product_spec')
            if not spec.get('conversation_id'):return []
            with s['conn']() as c:rows=c.execute("SELECT id,body FROM records WHERE owner=%s AND kind='execution' AND body->>'conversation'=%s ORDER BY created DESC LIMIT 40",(owner,spec['conversation_id'])).fetchall()
            return [{'id':r['id'],**r['body']} for r in rows if any(n['id']=='requirements' and n.get('arguments',{}).get('spec_id')==id for n in r['body'].get('definition',{}).get('nodes',[]))]
        for name,model,out,handler,risk in [
          ('read_product_requirements',Scope,TextResult,self.requirements,'read'),
          ('parse_product_interview',ParseInterview,Interview,self.parse_interview,'read'),
          ('validate_product_blueprint',Contracts,Blueprint,self.contracts,'read'),
          ('plan_product_source',Scope,FilePlan,self.file_plan,'read'),
          ('implement_product_blueprint',Implement,Built,self.implement,'internal_write')]:
            s['REGISTRY'].register(Tool(name,name.replace('_',' '),model,out,handler,permission='workspace.write' if risk!='read' else 'workspace.read',risk=risk,timeout=120))
        def base(spec,goal):return {'name':goal[:100],'goal':goal[:2000],'entry':'requirements','nodes':[{'id':'requirements','type':'tool','tool':'read_product_requirements','arguments':{'spec_id':spec['id'],'revision':spec['revision']}}],'edges':[],'max_seconds':600,'max_output_tokens':8192,'max_tool_calls':5,'max_steps':12}
        def report(evidence=None):return {'facts':[],'evidence':evidence or [{'source':'Confirmed requirements','citation':'product requirements','excerpt':{'$ref':'nodes.requirements.output.requirements_text'}}]}
        def agent(id,role,prompt,mode,evidence=None):
            models={'interview':Interview,'planner':ProductPlan,'architecture':Architecture,'developer':Experience,'reviewer':Review}
            context=report(evidence)
            if id in models:
                schema=response_schema(models[id])
                # JSON Schema is opaque data, not graph argument references.
                if id=='planner':context['_response_schema_json']=json.dumps(schema)
                else:context['_response_schema']=schema
            return {'id':id,'type':'agent','agent_id':role,'prompt':prompt,'mode':mode,'timeout_seconds':90,'output_tokens':(2048 if id=='planner' else 3072 if id=='prd' else 1024),'arguments':{'report':context}}
        def connect(definition):definition['edges']=[{'source':a['id'],'target':b['id']} for a,b in zip(definition['nodes'],definition['nodes'][1:])]
        @app.post('/api/studio/products/{id}/messages',status_code=202)
        async def message(id:str,body:Turn,owner=Depends(auth)):
            if id!=body.spec_id:raise HTTPException(422,'Product scope mismatch')
            reject_secrets(body.text);spec=self.spec(owner,id,body.revision);d=base(spec,body.text)
            prompt='PRODUCT_INTERVIEW_JSON. Current user message: '+body.text[:800]+'. Speak directly to this product owner: answer their message and ask one focused question about a missing decision. Return JSON with reply containing your actual conversational answer, and proposed_requirements containing at most two decisions explicitly supplied by the user. Use an empty object if none. Never repeat these instructions as your reply. Allowed proposal keys: '+','.join(k for k,_,_ in QUESTIONS)+'. Stack values react_fastapi/react_express/custom; theme light/dark; accent #rrggbb; authentication private_accounts; privacy internal/confidential/public. Do not guess unconfirmed values or claim implementation. The confirmed snapshot and original goal are attached.'
            if body.intent=='plan':
                prompt='PRODUCT_PLAN_JSON. Latest user message: '+body.text[:300]+'. Propose a COMPLETE practical first version using the goal and prior discussion. Return {reply,proposed_requirements}. Speak naturally; unspecified choices are suggestions awaiting confirmation. Ask at most one critical question, not a questionnaire. Include all missing keys: audience, stack, theme, accent, features, entities, authentication, privacy, integrations, acceptance, deployment. Values are short strings; use None for no integrations. Return compact JSON on one line. stack react_fastapi/react_express (custom only if requested); theme light/dark; accent #rrggbb; authentication private_accounts; privacy internal/confidential/public. entities: array [{name,label,fields:[{name,label,type}]}], one product-specific entity, two fields, snake_case names, type text/number/email/date. features/integrations: comma-separated. Reply in one short sentence under 120 characters; total JSON under 500 tokens. Retain confirmed choices unless asked to change. Adapter supports accounts and entity CRUD; advanced features/integrations/deployment are pending, never claim them working.'
            node=agent('planner' if body.intent=='plan' else 'interview','product_manager',prompt[:2000],body.mode,[*report()['evidence'],{'source':'Prior discussion','citation':'product conversation','excerpt':{'$ref':'nodes.requirements.output.conversation_text'}},{'source':'Latest user message','citation':'current product message','excerpt':body.text}])
            # Keep the stable interview node ID used by stored history and clients.
            node['id']='interview'
            if body.intent=='plan':node['timeout_seconds']=120
            d['nodes'] += [node,{'id':'proposal','type':'tool','tool':'parse_product_interview','arguments':{'spec_id':id,'revision':body.revision,'text':{'$ref':'nodes.interview.output.text'},'plan':body.intent=='plan'}}]
            connect(d);return await self.graph(owner,spec,d)
        @app.post('/api/studio/products/{id}/proposals/{execution_id}/accept')
        def accept(id:str,execution_id:str,body:Scope,owner=Depends(auth)):
            spec=self.spec(owner,id,body.revision);execution=s['get'](owner,execution_id,'execution');s['POLICY'].require(owner,'write')
            proposal=execution.get('graph_checkpoint',{}).get('nodes',{}).get('proposal',{}).get('output')
            node=next((n for n in execution['definition']['nodes'] if n['id']=='proposal'),None)
            if execution['state']!='COMPLETED' or not proposal or not node or node.get('tool')!='parse_product_interview' or node['arguments'].get('spec_id')!=id or node['arguments'].get('revision')!=body.revision or body.spec_id!=id:raise HTTPException(409,'Use a completed proposal for this exact product revision')
            updates={key:parsed_answer(key,value) for key,value in Interview.model_validate(proposal).proposed_requirements.items()}
            if not updates:raise HTTPException(422,'No requirement changes were proposed')
            with s['conn']() as c:
                row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_spec' FOR UPDATE",(owner,id)).fetchone();data=row['body']
                if data['revision']!=body.revision:raise HTTPException(409,'Proposal is stale')
                data['requirements'].update(updates);data['revision']+=1
                data.setdefault('proposal_history',[]).append({'execution_id':execution_id,'changes':updates,'actor':s['POLICY'].principal(owner).account})
                c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(data),owner,id))
            return s['STUDIO'].present({'id':id,**data})
        @app.post('/api/studio/products/{id}/agent-build',status_code=202)
        async def pipeline(id:str,body:Pipeline,owner=Depends(auth)):
            if id!=body.spec_id:raise HTTPException(422,'Product scope mismatch')
            spec=self.spec(owner,id,body.revision)
            if next_question(spec):raise HTTPException(422,'Confirm the required product decisions before building')
            if body.build_source and spec['requirements']['stack'] not in ('react_fastapi','react_express'):raise HTTPException(422,'This stack supports architecture/PRD drafts only; select a supported source adapter or generate blueprint only')
            d=base(spec,'Build '+spec['name']+' from approved requirements');selected=set(body.agents)
            if body.build_source and body.generation=='template':d['nodes'].append({'id':'file_plan','type':'tool','tool':'plan_product_source','arguments':{'spec_id':id,'revision':spec['revision']}})
            prompts={'prd':('product_manager','PRODUCT_PRD. Write a concise project-specific PRD in Markdown: problem, users, core workflows, acceptance criteria, integration dependencies and unresolved risks. Only approved scope; do not claim features already implemented.'),'architecture':('architect','PRODUCT_ARCHITECTURE_JSON. Design the proposed architecture for THIS confirmed product. Return JSON with nodes (objects with id and label), edges (objects with source and target node IDs), and notes describing actual boundaries. Use exactly three nodes with IDs web, api, db. Label them with the confirmed frontend framework, backend framework, and PostgreSQL. Use exactly two edges: web to api, and api to db. Notes must describe private-account and owner-data boundaries. Keep all text brief. Connected components are proposed architecture, not proof of a deployed service. No invented live integrations. Do not repeat these instructions as node labels or notes.'),'developer':('developer','PRODUCT_EXPERIENCE_JSON. Design the actual product interface copy from its approved purpose, not a generic task app. Return only JSON with a product-specific headline, description, and sections (objects with heading and text). Write the actual interface copy, not descriptions of these fields. Maximum 3 sections. The verified adapter implements accounts and entity CRUD; describe unsupported integrations as requirements, not working features. No executable code or fictional business outcomes.'),'reviewer':('reviewer','PRODUCT_REVIEW_JSON. Review the proposed interface against approved requirements. Return only JSON with approved (a boolean decision), summary (your actual specific review), and issues (an array of specific unresolved issues, empty if none). Do not copy instructions or generic field descriptions into the result. This is a source-design review, not executed tests or deployment. Here approved means design consistency, not permission to execute: true still pauses for human source approval. Mark false only for a concrete contradiction or unsafe design. Internal/confidential privacy is valid for a private application; public launch is not implied. Do not invent public-access or payment requirements. Use a one-sentence summary under 160 characters; list unresolved domain work as issues.')}
            for phase in ('prd','architecture','developer','reviewer'):
                if phase in selected:
                    role,prompt=prompts[phase];evidence=None
                    if phase=='reviewer' and 'developer' in selected:evidence=[{'source':'Proposed interface','citation':'developer draft','excerpt':{'$ref':'nodes.developer.output.text'}},*report()['evidence']]
                    d['nodes'].append(agent(phase,role,prompt,body.mode,evidence))
            d['nodes'].append({'id':'contracts','type':'tool','tool':'validate_product_blueprint','arguments':{'spec_id':id,'revision':body.revision,**{phase:({'$ref':'nodes.'+phase+'.output.text'} if phase in selected else '') for phase in ('prd','architecture','developer','reviewer')}}})
            if body.build_source:
                d['nodes'] += [{'id':'review_gate','type':'condition','condition':{'path':'nodes.contracts.output.can_build','op':'eq','value':True}},{'id':'implementation','type':'tool','tool':'implement_product_blueprint','timeout_seconds':120,'arguments':{'spec_id':id,'revision':body.revision,'blueprint':{'$ref':'nodes.contracts.output'},'mode':body.mode,'generation':body.generation,'file_tokens':max(1024,min(8192,int(os.getenv('EVOLVYN_PRODUCT_FILE_TOKENS','4096')))),'token_budget':max(8192,min(131072,int(os.getenv('EVOLVYN_PRODUCT_TOKEN_BUDGET','65536'))))}},{'id':'changes_needed','type':'result','arguments':{'value':{'$ref':'nodes.contracts.output.review'}}}]
                connect(d);d['edges']=[e for e in d['edges'] if e['source'] not in ('review_gate','implementation')]+[{'source':'review_gate','target':'implementation','when':'true'},{'source':'review_gate','target':'changes_needed','when':'false'}]
            else:connect(d)
            return await self.graph(owner,spec,d)

        @app.post('/api/studio/products/{id}/proposals/{execution_id}/confirm-and-build',status_code=202)
        async def confirm_and_build(id:str,execution_id:str,body:Pipeline,owner=Depends(auth)):
            # Existing acceptance persists the reviewed revision; the durable graph
            # starts in this request, without depending on a mounted browser view.
            updated=accept(id,execution_id,Scope(spec_id=body.spec_id,revision=body.revision),owner)
            if not updated['ready']:return {'product':updated,'execution':None,'launch_error':'Some decisions are missing. Continue in chat to complete the setup.'}
            try:
                execution=await pipeline(id,body.model_copy(update={'revision':updated['revision']}),owner)
                return {'product':updated,'execution':execution}
            except HTTPException as error:
                return {'product':updated,'execution':None,'launch_error':str(error.detail)}
