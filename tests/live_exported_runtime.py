"""Execute exported runtime source with isolated PostgreSQL; verify real MCP and policy."""
import os,json,secrets,socket,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
import httpx,psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from cryptography.fernet import Fernet
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.product_templates import generate
from backend.product_studio import QUESTIONS,parsed_answer

root=Path(__file__).resolve().parents[1]
target=root/'.local/validation/exported-runtime';target.mkdir(parents=True,exist_ok=True)
spec={key:parsed_answer(key,answer) for key,_,answer in QUESTIONS}
spec.update(name='Exported runtime acceptance',goal='Validate the actual included agent runtime')
files=generate(spec)
for name,content in files.items():
    path=target/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
subprocess.run([sys.executable,'scripts/prepare_product.py'],cwd=target,check=True,stdout=subprocess.DEVNULL)
subprocess.run(['docker','compose','--project-name','evolvyn-export-acceptance','config','--quiet'],cwd=target,check=True)
# Compile both the product UI and bundled console, using the already pinned installed dependencies.
for folder in (target/'frontend',target/'evolvyn/frontend'):
    modules=folder/'node_modules'
    if not modules.exists():modules.symlink_to(root/'frontend/node_modules',target_is_directory=True)
    with (folder/'build.log').open('w') as output:subprocess.run(['npm','run','build'],cwd=folder,check=True,stdout=output,stderr=output)
schema='export_accept_'+uuid4().hex
database='postgresql://evolvyn@127.0.0.1:5432/evolvyn'
with psycopg.connect(database) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
environment={'PATH':os.defpath,'DATABASE_URL':make_conninfo(database,options='-c search_path='+schema),'APP_ENV':'production','EVOLVYN_SESSION_COOKIE':'export_runtime_session','EVOLVYN_ACCESS_TOKEN':secrets.token_urlsafe(32),'EVOLVYN_VAULT_MASTER_KEY':Fernet.generate_key().decode(),'PUBLIC_ORIGIN':'http://127.0.0.1:'+str(port),'ALLOWED_HOSTS':'localhost,127.0.0.1'}
process=None
try:
    with (target/'runtime.log').open('w') as output:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(port)],cwd=target/'evolvyn',env=environment,stdout=output,stderr=output)
        with httpx.Client(base_url=environment['PUBLIC_ORIGIN'],headers={'X-Requested-With':'Evolvyn'},timeout=30) as c:
            for _ in range(100):
                if process.poll() is not None:raise RuntimeError('Exported runtime stopped; inspect private runtime.log')
                try:
                    if c.get('/api/health').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            response=c.post('/api/auth/register',json={'email':'export@example.test','password':'export-runtime-private-password','name':'Fresh exported team'});assert response.status_code==201,response.text
            assert c.cookies.get('export_runtime_session') and not c.cookies.get('evolvyn_session')
            runtime=c.get('/api/runtime').json();assert len(runtime['components'])==9
            assert c.get('/api/canvas').json()==[] and c.get('/api/growth/reports').json()==[]
            assert c.get('/api/vault').json()['credentials']==[]
            assert c.get('/api/auth/providers').json()[0]['enabled'] is False
            server=c.post('/api/mcp/servers',json={'name':'Exported evidence','profile':'evidence_utilities'}).json()
            response=c.post('/api/mcp/servers/'+server['id']+'/probe');assert response.status_code==200 and response.json()['status']=='healthy',response.text
            response=c.post('/api/tool-registry',json={'name':'export.compare','description':'Compare observed rates','adapter':'mcp','server_id':server['id'],'remote_tool':'compare_rates','capabilities':['compare'],'entities':['conversion']});assert response.status_code==200,response.text
            response=c.post('/api/tool-registry/export.compare/invoke',json={'arguments':{'before':4,'after':6}});assert response.status_code==200 and response.json()['result']['change_percentage_points']==2,response.text
            assert c.get('/api/runtime/ontology',params={'entity':'conversion'}).json()['tools'][0]['name']=='export.compare'
            policy=c.get('/api/governance/policy').json()
            c.put('/api/governance/policy',json={**policy,'denied_tools':['export.compare']}).raise_for_status()
            assert c.post('/api/tool-registry/export.compare/invoke',json={'arguments':{'before':4,'after':6}}).status_code==403
            # The exported runtime can itself generate another complete source package.
            product=c.post('/api/studio/products',json={'name':'Nested product','goal':'Ensure export remains self-contained'}).json()
            for key,_,answer in QUESTIONS:
                response=c.post('/api/studio/products/'+product['id']+'/answers',json={'field':key,'text':answer,'revision':product['revision']});response.raise_for_status();product=response.json()
            response=c.post('/api/studio/products/'+product['id']+'/build',json={'revision':product['revision']});response.raise_for_status()
            assert response.json()['state']=='READY',response.text[:400]
            assert 'evolvyn/frontend/src/components/DesignCanvas.tsx' in response.json()['files']
            print('EXPORTED RUNTIME PASS: Compose config → product + agent console compile → independent API startup → fresh accounts/vault/data → real stdio MCP → typed ontology → governance deny → self-contained nested product export')
finally:
    if process:
        process.terminate()
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    with psycopg.connect(database) as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
