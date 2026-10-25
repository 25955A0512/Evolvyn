"""Isolated OAuth UI fixture. Provider applications/authorization pages are CONTROLLED."""
import atexit,os
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from cryptography.fernet import Fernet
base_db=os.getenv('DATABASE_URL','postgresql://evolvyn@127.0.0.1:5432/evolvyn');schema='qa_oauth_'+uuid4().hex
with psycopg.connect(base_db) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
def cleanup():
    with psycopg.connect(base_db) as c:c.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
atexit.register(cleanup)
os.environ.update(DATABASE_URL=make_conninfo(base_db,options='-c search_path='+schema),PUBLIC_ORIGIN='http://127.0.0.1:3335',ALLOWED_HOSTS='localhost,127.0.0.1',COOKIE_SECURE='0',EVOLVYN_VAULT_MASTER_KEY=Fernet.generate_key().decode())
for provider in ('GOOGLE','GITHUB'):
    os.environ['OAUTH_'+provider+'_CLIENT_ID']='controlled-ui-client'
    os.environ['OAUTH_'+provider+'_CLIENT_SECRET']='controlled-ui-secret'
from backend.app import app
