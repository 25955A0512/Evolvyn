"""Isolated browser fixture. Model responses are CONTROLLED, never live acceptance."""
import atexit,asyncio,json,os
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from cryptography.fernet import Fernet
base_db=os.getenv('DATABASE_URL','postgresql://evolvyn@127.0.0.1:5432/evolvyn');schema='qa_clean_'+uuid4().hex
with psycopg.connect(base_db) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
def cleanup():
 with psycopg.connect(base_db) as c:c.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
atexit.register(cleanup)
os.environ.update(DATABASE_URL=make_conninfo(base_db,options='-c search_path='+schema),PUBLIC_ORIGIN='http://127.0.0.1:3333',ALLOWED_HOSTS='localhost,127.0.0.1',EVOLVYN_VAULT_MASTER_KEY=Fernet.generate_key().decode())
from backend import app as m
from backend.product_studio import QUESTIONS
from backend.model_source import ModelSourceBuilder
from test_model_source import FILES
async def role(report,question,history,mode):
 await asyncio.sleep(.1)
 if 'PRODUCT_PLAN_JSON' in question:out={'reply':'Controlled model fixture: review this proposed catalog setup.','proposed_requirements':{key:json.loads(value) if key=='entities' else value for key,_,value in QUESTIONS}}
 elif 'PRODUCT_ARCHITECTURE_JSON' in question:out={'nodes':[{'id':'web','label':'React'},{'id':'api','label':'FastAPI'},{'id':'db','label':'PostgreSQL'}],'edges':[{'source':'web','target':'api'},{'source':'api','target':'db'}],'notes':'Controlled design fixture, not a deployment.'}
 elif 'PRODUCT_EXPERIENCE_JSON' in question:out={'headline':'Controlled catalog','description':'Synthetic browser acceptance','sections':[]}
 elif 'PRODUCT_REVIEW_JSON' in question:out={'approved':True,'summary':'Controlled design consistency response; human approval required.','issues':[]}
 else:yield '# Controlled PRD\nSynthetic model boundary for UI acceptance.';return
 yield json.dumps(out)
m.GRAPH_HARNESS.s['response_chunks']=role
original=ModelSourceBuilder.__init__
def init(self,s):
 original(self,s)
 async def source(report,prompt,history,mode):
  if 'MANIFEST_JSON' in prompt:yield json.dumps({'files':[{'path':p,'purpose':'Controlled fixture file'} for p in FILES]});return
  await asyncio.sleep(.8)
  yield next(content for path,content in FILES.items() if 'contents of '+path+' only' in prompt)
 self.stream=source
ModelSourceBuilder.__init__=init
app=m.app
