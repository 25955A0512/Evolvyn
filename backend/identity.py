"""Password accounts, private organization memberships and revocable cookie sessions."""
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from fastapi import Depends,HTTPException,Request,Response
from pydantic import BaseModel,Field

class AccountInput(BaseModel):
    email:str=Field(min_length=5,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password:str=Field(min_length=12,max_length=128)
    name:str=Field(default='My workspace',min_length=1,max_length=100)

class LoginInput(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    password:str=Field(min_length=1,max_length=128)

class MembershipInput(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    role:str=Field(pattern='^(admin|editor|viewer)$')

class OrganizationInput(BaseModel):
    name:str=Field(min_length=1,max_length=100)


def initialize(c):
    c.execute('CREATE TABLE IF NOT EXISTS accounts (id text PRIMARY KEY,email text UNIQUE NOT NULL,name text NOT NULL,password_hash text NOT NULL,created timestamptz DEFAULT now())')
    c.execute('CREATE TABLE IF NOT EXISTS organizations (id text PRIMARY KEY,name text NOT NULL,created timestamptz DEFAULT now())')
    c.execute('CREATE TABLE IF NOT EXISTS memberships (account_id text REFERENCES accounts(id),organization_id text REFERENCES organizations(id),role text NOT NULL,PRIMARY KEY(account_id,organization_id))')
    c.execute('CREATE TABLE IF NOT EXISTS account_sessions (digest text PRIMARY KEY,account_id text REFERENCES accounts(id),organization_id text REFERENCES organizations(id),expires timestamptz NOT NULL)')


def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    derived=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex()
    return salt+':'+derived


def verify_password(password,stored):
    return hmac.compare_digest(password_hash(password,stored.split(':',1)[0]),stored)


def resolve(request,authorization,organization,conn):
    token=request.cookies.get('evolvyn_session')
    if not token or authorization not in ('','Bearer cookie'):return None
    digest=hashlib.sha256(token.encode()).hexdigest()
    with conn() as c:
        session=c.execute('SELECT * FROM account_sessions WHERE digest=%s AND expires>now()',(digest,)).fetchone()
        if not session:return None
        org=organization or session['organization_id']
        member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(session['account_id'],org)).fetchone()
        if not member:raise HTTPException(403,'Organization membership required')
    role=member['role']
    if request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('x-requested-with')!='Evolvyn':raise HTTPException(403,'Same-origin application request header required')
        origin=request.headers.get('origin')
        allowed=set(os.getenv('PUBLIC_ORIGIN',str(request.base_url).rstrip('/')).split(','))
        if os.getenv('APP_ENV','development')!='production':allowed.update({'http://127.0.0.1:5173','http://localhost:5173'})
        if origin and origin not in allowed:raise HTTPException(403,'Cross-origin request denied')
        if role=='viewer':raise HTTPException(403,'Viewer access is read-only')
        if role=='editor' and (request.url.path.endswith('/decision') or '/members' in request.url.path or request.url.path.startswith('/api/organizations')):
            raise HTTPException(403,'An organization administrator must approve this action')
    request.state.identity={'account_id':session['account_id'],'organization_id':org,'role':role}
    return org


def install(app,conn,auth):
    def start_session(response,account,organization,c):
        token=secrets.token_urlsafe(32)
        c.execute('INSERT INTO account_sessions(digest,account_id,organization_id,expires) VALUES (%s,%s,%s,%s)',(hashlib.sha256(token.encode()).hexdigest(),account,organization,datetime.now(timezone.utc)+timedelta(days=7)))
        response.set_cookie('evolvyn_session',token,httponly=True,secure=os.getenv('COOKIE_SECURE')=='1',samesite='strict',max_age=604800,path='/')
        return {'account_id':account,'organization_id':organization,'authentication':'http_only_cookie'}

    @app.post('/api/auth/register',status_code=201)
    def register(body:AccountInput,response:Response):
        email=body.email.strip().lower();account=str(uuid4());organization=str(uuid4())
        import psycopg
        try:
            with conn() as c:
                c.execute('INSERT INTO accounts(id,email,name,password_hash) VALUES (%s,%s,%s,%s)',(account,email,body.name,password_hash(body.password)))
                c.execute('INSERT INTO organizations(id,name) VALUES (%s,%s)',(organization,body.name))
                c.execute('INSERT INTO memberships(account_id,organization_id,role) VALUES (%s,%s,%s)',(account,organization,'owner'))
                return start_session(response,account,organization,c)
        except psycopg.errors.UniqueViolation:raise HTTPException(409,'An account with that email already exists')

    @app.post('/api/auth/login')
    def login(body:LoginInput,response:Response):
        with conn() as c:
            account=c.execute('SELECT * FROM accounts WHERE email=%s',(body.email.strip().lower(),)).fetchone()
            stored=account['password_hash'] if account else '00000000000000000000000000000000:'+'0'*64
            if not verify_password(body.password,stored):raise HTTPException(401,'Invalid email or password')
            membership=c.execute('SELECT organization_id FROM memberships WHERE account_id=%s ORDER BY organization_id LIMIT 1',(account['id'],)).fetchone()
            if not membership:raise HTTPException(403,'No organization membership is available')
            return start_session(response,account['id'],membership['organization_id'],c)

    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        if request.headers.get('x-requested-with')!='Evolvyn':raise HTTPException(403,'Application request header required')
        token=request.cookies.get('evolvyn_session','')
        with conn() as c:c.execute('DELETE FROM account_sessions WHERE digest=%s',(hashlib.sha256(token.encode()).hexdigest(),))
        response.delete_cookie('evolvyn_session',path='/')
        return {'signed_out':True}

    @app.get('/api/auth/me')
    def me(request:Request,owner=Depends(auth)):
        identity=getattr(request.state,'identity',None)
        if not identity:return {'organization_id':owner,'role':'owner' if owner=='initial-workspace' else 'demo','account':None,'organizations':[]}
        with conn() as c:
            account=c.execute('SELECT id,email,name FROM accounts WHERE id=%s',(identity['account_id'],)).fetchone()
            organizations=c.execute('SELECT o.id,o.name,m.role FROM organizations o JOIN memberships m ON m.organization_id=o.id WHERE m.account_id=%s ORDER BY o.created',(identity['account_id'],)).fetchall()
        return {**identity,'account':account,'organizations':organizations}

    @app.get('/api/organizations/members')
    def members(owner=Depends(auth)):
        with conn() as c:return c.execute('SELECT a.id,a.email,a.name,m.role FROM accounts a JOIN memberships m ON m.account_id=a.id WHERE m.organization_id=%s',(owner,)).fetchall()

    @app.post('/api/organizations/members')
    def add_member(body:MembershipInput,request:Request,owner=Depends(auth)):
        if getattr(request.state,'identity',{}).get('role') not in ('owner','admin'):raise HTTPException(403,'Organization administrator required')
        with conn() as c:
            account=c.execute('SELECT id FROM accounts WHERE email=%s',(body.email.strip().lower(),)).fetchone()
            if not account:raise HTTPException(404,'That person must create an account first')
            existing=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(account['id'],owner)).fetchone()
            if existing and existing['role']=='owner':raise HTTPException(403,'The owner role cannot be changed here')
            c.execute('INSERT INTO memberships(account_id,organization_id,role) VALUES (%s,%s,%s) ON CONFLICT(account_id,organization_id) DO UPDATE SET role=EXCLUDED.role',(account['id'],owner,body.role))
        return {'account_id':account['id'],'organization_id':owner,'role':body.role}

    @app.post('/api/organizations')
    def create_organization(body:OrganizationInput,request:Request,owner=Depends(auth)):
        identity=getattr(request.state,'identity',None)
        if not identity:raise HTTPException(403,'An account is required')
        id=str(uuid4())
        with conn() as c:
            c.execute('INSERT INTO organizations(id,name) VALUES (%s,%s)',(id,body.name))
            c.execute('INSERT INTO memberships(account_id,organization_id,role) VALUES (%s,%s,%s)',(identity['account_id'],id,'owner'))
        return {'id':id,'name':body.name,'role':'owner'}
