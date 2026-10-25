"""Approved, bounded model-authored source artifacts. Never executes generated code."""
import asyncio,hashlib,json,os,re
from pathlib import PurePosixPath
from datetime import datetime,timezone
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from backend.agent_memory import reject_secrets
from backend.model_access import model_scope,effective_mode
from backend.model_errors import failure,ModelFailure
from backend.providers import response_chunks
import ast
import yaml
from backend.source_compiler import compile_frontend

class SourceFile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    path:str=Field(min_length=1,max_length=180)
    purpose:str=Field(min_length=1,max_length=180)
class Manifest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    files:list[SourceFile]=Field(min_length=1,max_length=16)
    @model_validator(mode='after')
    def paths(self):
        paths=[row.path for row in self.files]
        if len(set(paths))!=len(paths):raise ValueError('Duplicate source path')
        for path in paths:safe_path(path)
        return self

def safe_path(path):
    p=PurePosixPath(path)
    if not re.fullmatch(r'[A-Za-z0-9_.\-/]+',path) or p.is_absolute() or any(part in ('..','.') for part in path.split('/')) or str(p)!=path or path.endswith('/') or len(p.parts)>8:raise ValueError('Unsafe source path')
    if p.name in ('package-lock.json','yarn.lock','pnpm-lock.yaml'):raise ValueError('Dependency locks must be produced by the package manager, never invented by a model')
    if p.suffix not in ('.jsx','.tsx','.js','.mjs','.ts','.json','.css','.html','.py','.txt','.md','.yaml','.yml','.toml','.sql','.example') and p.name not in ('Dockerfile','.gitignore','.dockerignore'):raise ValueError('Unsupported source file type')
    return path

def unfenced(text):
    match=re.fullmatch(r'\s*```[^\n]*\n(.*?)\n```\s*',text,flags=re.S)
    return match[1]+'\n' if match else text

def validate_source(files):
    checks=[]
    for path,text in files.items():
        safe_path(path)
        if path.endswith('.py'):ast.parse(text);checks.append('Python syntax: '+path)
        if path.endswith('.json'):json.loads(text)
    package=json.loads(files['frontend/package.json'])
    if not isinstance(package,dict) or not set(package.get('dependencies',{}))<={'react','react-dom','lucide-react'}:raise ValueError('Unsupported frontend dependencies')
    compose=yaml.safe_load(files['compose.yaml'])
    if not isinstance(compose,dict) or not {'app','db'}<=set(compose.get('services',{})):raise ValueError('Compose needs application and private PostgreSQL services')
    for name,service in compose['services'].items():
        if not isinstance(service,dict) or service.get('privileged') or service.get('network_mode')=='host' or service.get('pid')=='host' or service.get('devices') or service.get('cap_add') or service.get('volumes_from') or service.get('ipc')=='host' or service.get('uts')=='host' or service.get('userns_mode')=='host':raise ValueError('Unsafe container privileges')
        if name=='db' and service.get('ports'):raise ValueError('Database must not expose a host port')
        for volume in service.get('volumes',[]):
            value=volume if isinstance(volume,str) else volume.get('source','')
            if isinstance(volume,str):
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*:/[^:\\]*(?::(?:ro|rw))?',volume):raise ValueError('Only named data volumes are allowed')
            elif not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',str(value)) or volume.get('type')!='volume':raise ValueError('Only named data volumes are allowed')
    return checks+['Source paths and JSON parsed','Compose privilege and database-port checks passed','Generated application code was not executed; authentication and domain behavior remain unverified']

class ModelSourceBuilder:
    def __init__(self,s):self.s=s;self.stream=response_chunks
    async def build(self,owner,spec,blueprint,mode,approved,execution_id,file_tokens=4096,token_budget=65536):
        s=self.s;s['POLICY'].tool(owner,'implement_product_blueprint','internal_write','workspace.write',{'workspace.write'},approved)
        s['POLICY'].require(owner,'write')
        if spec['requirements']['stack'] not in ('react_fastapi','react_express'):raise HTTPException(422,'Select a supported source stack first')
        conversation=s['get'](owner,spec['conversation_id'],'conversation')
        id=str(uuid4());record={'spec_id':spec['id'],'project_id':spec.get('project_id'),'revision':spec['revision'],'execution_id':execution_id,'spec':{**spec['requirements'],'name':spec['name'],'goal':spec['goal']},'blueprint':blueprint,'generation':'model','engine':'Model-authored source · one persisted file per model call','created_at':datetime.now(timezone.utc).isoformat(),'state':'BUILDING','files':{},'events':[],'checks':[],'model_tokens_reserved':0,'model_calls':0,'implemented_capabilities':[],'pending_requirements':spec['requirements'].get('features',[]),'validation_scope':'Generated source is untrusted. Compilation is separate from backend runtime, security and business acceptance tests.','integration_status':'No integration is connected merely by generating its source.'}
        def save(stage,detail):
            # Revalidate every write: a deleted project/revoked access cancels the build.
            latest=s['get'](owner,spec['id'],'product_spec')
            if latest['revision']!=spec['revision']:raise HTTPException(409,'Requirements changed during source generation')
            record['events'].append({'stage':stage,'detail':detail,'at':datetime.now(timezone.utc).isoformat()})
            s['POLICY'].resource(owner,'write','product_build',record,id)
            with s['conn']() as c:
                locked=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_spec' FOR SHARE",(owner,spec['id'])).fetchone()
                if not locked or locked['body'].get('trashed_at'):raise HTTPException(410,'Product is in trash')
                if locked['body']['revision']!=spec['revision']:raise HTTPException(409,'Requirements changed during source generation')
                c.execute("INSERT INTO records(id,owner,kind,body) VALUES(%s,%s,'product_build',%s) ON CONFLICT(id) DO UPDATE SET body=EXCLUDED.body WHERE records.owner=EXCLUDED.owner",(id,owner,json.dumps(record)))
        save('source','Preparing a model-authored file manifest')
        cap=max(8192,min(131072,token_budget))
        per_file=max(1024,min(8192,file_tokens))
        record['source_limits']={'file_tokens':per_file,'token_budget':cap,'max_calls':34,'max_files':16}
        async def ask(prompt,limit,schema=None):
            with model_scope(owner,'developer'):
                selected=effective_mode(mode);s['POLICY'].data(owner,conversation,selected)
                if selected=='evidence':raise ModelFailure('model_not_configured','AI source generation requires a configured model, not evidence-only mode.')
                reserve=min(limit,512 if selected=='local' else 8192)
                if record['model_tokens_reserved']+reserve>cap or record['model_calls']>=34:raise ModelFailure('source_budget_exhausted','The bounded source-generation budget was exhausted. Saved files are retained.')
                record['model_tokens_reserved']+=reserve;record['model_calls']+=1
                context={'facts':[],'evidence':[{'source':'Confirmed product requirements','citation':'product:'+spec['id']+':'+str(spec['revision']),'excerpt':json.dumps(record['spec'])},{'source':'Reviewed design proposal','citation':'design blueprint','excerpt':json.dumps(blueprint)[:5000]}],'_output_limit':reserve,'_max_response_chars':64000}
                if schema:context['_response_schema_json']=json.dumps(schema)
                chunks=[]
                async for chunk in self.stream(context,prompt,[],mode):
                    chunks.append(chunk)
                    if sum(len(c) for c in chunks)>64000:raise ModelFailure('source_file_limit','Generated file exceeded the safe size limit.')
                record['last_model_usage']=context.get('usage')
                record.setdefault('usage_history',[]).append(context.get('usage'))
                result=unfenced(''.join(chunks));reject_secrets(result)
                if not result.strip():raise ModelFailure('model_response_empty','The model returned an empty source file.')
                return result
        try:
            from backend.product_agents import response_schema
            required={'frontend/src/main.jsx','frontend/index.html','frontend/package.json','Dockerfile','compose.yaml'}|({'backend/app.py','backend/requirements.txt'} if spec['requirements']['stack']=='react_fastapi' else {'backend/server.mjs','backend/package.json'})
            manifest_prompt='PRODUCT_SOURCE_MANIFEST_JSON. Plan the smallest complete source repository for the confirmed product. Return compact JSON with files [{path,purpose}]. Choose useful names and folders for THIS product; no template inventory. Include frontend/src/main.jsx, frontend/index.html, frontend/package.json, Dockerfile, compose.yaml, and '+('backend/app.py, backend/requirements.txt' if spec['requirements']['stack']=='react_fastapi' else 'backend/server.mjs, backend/package.json')+'. Include all imported frontend components and styles as separate files if useful. React frontend dependencies may only use react, react-dom, lucide-react. No lockfiles, binary assets, embedded copies of Evolvyn or invented credentials. At most 16 concise files.'
            for attempt in range(2):
                try:
                    manifest=Manifest.model_validate_json(await ask(manifest_prompt,2048,response_schema(Manifest)))
                    if not required<={f.path for f in manifest.files}:raise ValueError('Manifest omitted required build entry points')
                    break
                except ValueError as error:
                    # Retry only a malformed contract, never auth/quota/provider errors.
                    if isinstance(error,ModelFailure) or attempt:raise
                    save('manifest_retry','Manifest did not meet the source contract; requesting one corrected manifest')
                    manifest_prompt+=' Previous manifest was rejected. Return a fresh JSON object with only files, each with path and purpose. Include every required entry point exactly as named. Use unique safe relative paths, no lockfiles, and at most 16 files.'
            record['manifest']=manifest.model_dump()['files'];save('manifest',f'Model planned {len(manifest.files)} files. No file contents have been created yet.')
            for item in manifest.files:
                save('generating','Generating '+item.path)
                imports='\n'.join(f.path+': '+f.purpose for f in manifest.files)
                previous='\n'.join(path+'\n'+content[:2200] for path,content in list(record['files'].items())[-5:])[:9000]
                prompt='PRODUCT_SOURCE_FILE. Create the complete contents of '+item.path+' only. Purpose: '+item.purpose+'. This is approved source generation, not permission to execute or deploy. Return raw file contents, no Markdown fence or explanation. Implement the confirmed product behavior with coherent APIs/imports. Use environment variables for secrets, private password hashing and owner-scoped PostgreSQL data. Never hardcode credentials or claim successful tests. Frontend entry is main.jsx, React imports are relative to the listed src files; installed frontend dependencies are limited to react/react-dom/lucide-react. Compose must have app and db services, with no database host port, privileged mode or Docker socket mounts. Use npm install rather than inventing a lockfile. Keep files concise. Manifest:\n'+imports+'\nPreviously generated source contracts:\n'+previous
                content=None
                for attempt in range(2):
                    try:content=await ask(prompt,min(8192,per_file*(2**attempt)));break
                    except ModelFailure as error:
                        if error.code!='model_output_limit' or attempt:raise
                        save('retry','Retrying truncated file '+item.path+' once with a larger bounded output allowance')
                if '\x00' in content:raise ValueError('Invalid source content')
                record['files'][item.path]=content
                save('file_created','Created '+item.path)
            record['checks']=validate_source(record['files'])
            record['source_sha256']=hashlib.sha256(json.dumps(record['files'],sort_keys=True).encode()).hexdigest()
            save('compiler','Source files saved; validating the frontend in the private compiler')
            record['frontend_build']=await compile_frontend(record['files'])
            if record['frontend_build']['status']=='failed':raise ModelFailure('source_compilation_failed','Generated frontend did not compile. Saved source and the failure receipt are available for review.')
            record['state']='READY';save('ready','Source generation completed; application runtime has not been started')
        except asyncio.CancelledError:
            record.update(state='CANCELLED',error='Source generation was interrupted; completed files are retained.')
            try:save('cancelled',record['error'])
            except HTTPException:pass
            raise
        except Exception as error:
            code,message=failure(error)
            if isinstance(error,ValueError) and not isinstance(error,ModelFailure):code,message='source_contract_invalid',('The model returned an invalid file manifest after one correction attempt. No source files were created. Retry source generation with a smaller scope.' if not record.get('manifest') else 'A generated file failed source-contract validation. Completed files are retained; review the saved files before retrying.')
            record.update(state='FAILED',error_code=code,error=message)
            try:save('failed',message)
            except HTTPException:pass
        return {'id':id,**record}
