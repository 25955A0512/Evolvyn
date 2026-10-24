"""Execute the trusted generated Express adapter against an isolated PostgreSQL schema."""
import json,os,socket,subprocess,time,shutil
from pathlib import Path
from uuid import uuid4
import httpx,psycopg
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from psycopg import sql
from backend.product_templates import generate
from backend.product_studio import QUESTIONS,parsed_answer
spec={key:parsed_answer(key,answer) for key,_,answer in QUESTIONS}
spec.update(name='Generated Node acceptance',goal='Validate private CRUD',stack='react_express')
root=Path('.local/validation/node-runtime').resolve();root.mkdir(parents=True,exist_ok=True)
for name,content in generate(spec).items():
 path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
modules=Path('backend/template_assets/node-api/node_modules').resolve()
(root/'backend/node_modules').symlink_to(modules,target_is_directory=True) if not (root/'backend/node_modules').exists() else None
schema='node_accept_'+uuid4().hex
with psycopg.connect('postgresql://evolvyn@127.0.0.1:5432/evolvyn') as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
environment={'PATH':os.defpath,'PGHOST':'127.0.0.1','PGPORT':'5432','PGUSER':'evolvyn','PGDATABASE':'evolvyn','PGOPTIONS':'-c search_path='+schema,'PORT':str(port)}
process=None
try:
 with (root/'server.log').open('w') as output:
  process=subprocess.Popen([shutil.which('node'),str(root/'backend/server.mjs')],cwd=root/'backend',env=environment,stdout=output,stderr=output)
  with httpx.Client(base_url='http://127.0.0.1:'+str(port),headers={'X-Requested-With':'Product'}) as c:
   for _ in range(100):
    if process.poll() is not None:raise RuntimeError('Generated Node server failed; inspect private server.log')
    try:
     if c.get('/api/health').status_code==200:break
    except httpx.HTTPError:pass
    time.sleep(.1)
   response=c.post('/api/register',json={'email':'node-owner@example.test','password':'node-acceptance-password'});assert response.status_code==201,response.text
   response=c.post('/api/items/tasks',json={'title':'Private Node record','status':'todo'});assert response.status_code==201,response.text
   id=response.json()['id'];assert c.get('/api/items/tasks').json()[0]['data']['title']=='Private Node record'
   assert c.post('/api/logout').status_code==200
   assert c.get('/api/items/tasks').status_code==401
   assert c.post('/api/register',json={'email':'node-other@example.test','password':'node-acceptance-password'}).status_code==201
   assert c.get('/api/items/tasks').json()==[]
   assert c.delete('/api/items/tasks/'+id).status_code==404
   assert c.put('/api/items/tasks/'+id,json={'title':'Steal','status':'done'}).status_code==404
   print('GENERATED EXPRESS + REAL POSTGRESQL: startup → accounts → private CRUD → logout → cross-account isolation PASS')
finally:
 if process:
  process.terminate()
  try:process.wait(timeout=5)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 with psycopg.connect('postgresql://evolvyn@127.0.0.1:5432/evolvyn') as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
