"""Trusted source adapters. User requirements are data, never executable interpolation."""
import ast
import json
from pathlib import Path

REACT = r'''import React, {useState,useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import spec from './spec.json';
import './style.css';
function App(){
 const [user,setUser]=useState(null),[mode,setMode]=useState('login'),[entity,setEntity]=useState(spec.entities[0]?.name||''),[rows,setRows]=useState([]),[error,setError]=useState('');
 const selected=spec.entities.find(e=>e.name===entity);
 async function api(path,options={}){const r=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json','X-Requested-With':'Product',...options.headers}});if(!r.ok)throw Error((await r.json()).detail||'Request failed');return r.json()}
 async function load(){if(user&&entity)setRows(await api('/items/'+entity))}
 useEffect(()=>{api('/me').then(setUser).catch(()=>{})},[]);
 useEffect(()=>{load().catch(e=>setError(e.message))},[user,entity]);
 async function submit(e){e.preventDefault();setError('');const form=e.currentTarget;const values=Object.fromEntries(new FormData(form));try{if(!user){setUser(await api('/'+mode,{method:'POST',body:JSON.stringify(values)}));form.reset()}else{const fields=selected.fields;for(const f of fields)if(f.type==='number')values[f.name]=Number(values[f.name]);await api('/items/'+entity,{method:'POST',body:JSON.stringify(values)});form.reset();await load()}}catch(e){setError(e.message)}}
 return <div className={'app '+spec.theme} style={{'--accent':spec.accent}}><aside><strong className="brand">{spec.name}</strong><p>{spec.goal}</p>{user&&spec.entities.map(e=><button className={entity===e.name?'active':''} key={e.name} onClick={()=>setEntity(e.name)}>{e.label}</button>)}<a href="http://localhost:3001" target="_blank" rel="noopener noreferrer">Open agent workspace ↗</a><small>{user?'Private account workspace':'Secure account access'}</small></aside><main><header><span>{user?user.email:spec.audience}</span>{user&&<button onClick={async()=>{await api('/logout',{method:'POST'});setUser(null);setRows([])}}>Sign out</button>}</header>{error&&<p role="alert" className="error">{error}</p>}{!user?<section className="auth"><small>WELCOME TO {spec.name.toUpperCase()}</small><h1>{mode==='login'?'Welcome back.':'Create your account.'}</h1><form onSubmit={submit}><label>Email<input name="email" type="email" required maxLength={254}/></label><label>Password<input name="password" type="password" required minLength={12} maxLength={128}/></label><button className="primary">{mode==='login'?'Sign in':'Create account'}</button></form><button onClick={()=>setMode(mode==='login'?'register':'login')}>{mode==='login'?'New here? Create an account':'Already have an account? Sign in'}</button></section>:<><small>YOUR WORKSPACE</small><h1>{selected?.label||spec.name}</h1>{spec.design?.elements?.length>0&&<section className="designed-page" aria-label="Designed page">{[...spec.design.elements].sort((a,b)=>a.y-b.y||a.x-b.x).map(e=><div key={e.id} className={"design-element "+e.kind} style={{gridColumn:e.width>700?"1 / -1":undefined}}>{e.kind==="heading"?<h2>{e.label}</h2>:e.kind==="button"?<span className="primary" aria-label="Button design pending action implementation">{e.label}</span>:e.kind==="image"?<div role="img" aria-label={e.label}>◇ {e.label}</div>:<p>{e.label}</p>}</div>)}</section>}<p>{spec.goal}</p><div className="stats"><strong>{rows.length}</strong><span>saved records</span></div>{selected&&<form className="create" onSubmit={submit}>{selected.fields.map(f=><label key={f.name}>{f.label}<input name={f.name} type={f.type==='number'?'number':f.type==='date'?'date':f.type==='email'?'email':'text'} required maxLength={2000} step={f.type==='number'?'any':undefined}/></label>)}<button className="primary">Add {selected.label}</button></form>}<section className="records">{!rows.length&&<p>No records yet. Add your first one above.</p>}{rows.map(row=><article key={row.id}><div>{Object.entries(row.data).map(([key,value])=><p key={key}><small>{selected.fields.find(f=>f.name===key)?.label||key}</small><span>{String(value)}</span></p>)}</div><button onClick={async()=>{try{await api('/items/'+entity+'/'+row.id,{method:'DELETE'});await load()}catch(e){setError(e.message)}}}>Delete</button></article>)}</section></>}</main></div>
}
createRoot(document.getElementById('root')).render(<App/>);
'''

STYLE = '''.designed-page{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;margin:28px 0}.design-element{padding:22px;border:1px solid #dce1d8;border-radius:12px}.design-element.heading,.design-element.navigation{grid-column:1/-1}.design-element .primary{display:inline-block;padding:12px 20px;border-radius:8px} *{box-sizing:border-box}body{margin:0;font:16px system-ui;color:#242724;background:#f8f9f7}button,input{font:inherit}button{cursor:pointer;border:1px solid #dce1d8;background:white;border-radius:8px;padding:10px 16px;color:inherit}button:hover{filter:brightness(.96)}input{border:1px solid #dce1d8;border-radius:7px;padding:12px;background:inherit;color:inherit;width:100%}label{display:grid;gap:7px;font-size:14px}form{display:grid;gap:18px}.app{min-height:100vh;display:grid;grid-template-columns:250px 1fr}.app.dark{color:#e5e9e2;background:#1b211d}.dark aside,.dark article,.dark .create{background:#252e27;border-color:#3c483e}.dark button{background:#303d33;border-color:#526555}.dark input{border-color:#526555}aside{padding:35px 24px;background:#edf0e9;border-right:1px solid #dfe4db;display:flex;flex-direction:column;gap:15px}aside .brand{font-size:24px;letter-spacing:-1px}aside p{font-size:14px;line-height:1.8;opacity:.65}aside small{margin-top:auto;opacity:.6}aside button{text-align:left}aside button.active{border-color:var(--accent);color:var(--accent)}main{padding:25px 45px}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:55px;font-size:14px}h1{font-size:38px;letter-spacing:-1.5px;font-weight:550}p{line-height:1.7}small{font-size:13px;letter-spacing:.5px;opacity:.7}.primary{background:var(--accent);color:white;border:0}.auth{max-width:420px;margin:70px auto}.auth>button{margin-top:20px}.stats{display:flex;gap:12px;align-items:center;margin:25px 0}.stats strong{font-size:28px;color:var(--accent)}.create{background:white;padding:24px;border:1px solid #e1e7dc;border-radius:12px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));align-items:end}.records{margin-top:25px;display:grid;gap:12px}article{display:flex;justify-content:space-between;gap:20px;background:white;padding:22px;border:1px solid #e1e7dc;border-radius:12px}article>div{display:flex;gap:35px;flex-wrap:wrap}article p{margin:0;display:grid;gap:7px}.error{background:#fee7e7;color:#9c2828;padding:15px;border-radius:8px}@media(max-width:700px){.app{grid-template-columns:1fr}aside{padding:20px;flex-direction:row;flex-wrap:wrap;align-items:center}aside p,aside small{display:none}main{padding:22px}header{margin-bottom:30px}h1{font-size:29px}}
'''

PYTHON = r'''"""Generated application: accounts, private CRUD, PostgreSQL/SQLite and static React UI."""
import os,json,secrets,hashlib,hmac,time,sqlite3,re
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager,asynccontextmanager
from collections import defaultdict,deque
from fastapi import FastAPI,HTTPException,Request,Response,Depends
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field,ConfigDict
SPEC=json.loads(Path(__file__).with_name('spec.json').read_text())
DB=os.getenv('DATABASE_URL','sqlite:///./product.db')
@contextmanager
def conn():
 if DB.startswith('postgres'):
  import psycopg
  from psycopg.rows import dict_row
  c=psycopg.connect(DB,row_factory=dict_row)
 else:
  c=sqlite3.connect(DB.removeprefix('sqlite:///'));c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
 class Query:
  def execute(self,sql,args=()):return c.execute(sql if DB.startswith('postgres') else sql.replace('%s','?'),args)
 try:yield Query();c.commit()
 except BaseException:c.rollback();raise
 finally:c.close()
@asynccontextmanager
async def lifespan(app):
 with conn() as c:
  c.execute('CREATE TABLE IF NOT EXISTS users(id text PRIMARY KEY,email text UNIQUE NOT NULL,password text NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS sessions(digest text PRIMARY KEY,owner text NOT NULL REFERENCES users(id),expires double precision NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS items(id text PRIMARY KEY,owner text NOT NULL REFERENCES users(id),entity text NOT NULL,data text NOT NULL)')
 yield
app=FastAPI(title=SPEC['name'],lifespan=lifespan)
@app.exception_handler(RequestValidationError)
async def invalid(request,error):
 return JSONResponse(status_code=422,content={'detail':[{'loc':e['loc'],'msg':e['msg'],'type':e['type']} for e in error.errors()]})
buckets=defaultdict(deque)
@app.middleware('http')
async def guard(request,call_next):
 if request.method not in ('GET','HEAD','OPTIONS'):
  if request.headers.get('x-requested-with')!='Product':return __import__('fastapi').responses.JSONResponse(status_code=403,content={'detail':'Application header required'})
  origin=request.headers.get('origin')
  if origin and origin!=os.getenv('PUBLIC_ORIGIN',str(request.base_url).rstrip('/')):return __import__('fastapi').responses.JSONResponse(status_code=403,content={'detail':'Origin denied'})
 length=request.headers.get('content-length','0')
 if not length.isdigit() or int(length)>50000:return __import__('fastapi').responses.JSONResponse(status_code=413,content={'detail':'Payload too large'})
 if request.url.path in ('/api/login','/api/register'):
  bucket=buckets[(request.client.host if request.client else 'unknown')];now=time.monotonic()
  while bucket and bucket[0]<now-60:bucket.popleft()
  if len(bucket)>=20:return __import__('fastapi').responses.JSONResponse(status_code=429,content={'detail':'Try again in a minute'})
  bucket.append(now)
 response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='no-referrer';response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'";return response
class Credentials(BaseModel):
 model_config=ConfigDict(extra='forbid')
 email:str=Field(min_length=5,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
 password:str=Field(min_length=12,max_length=128)
def password_hash(value,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.scrypt(value.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def current(request:Request):
 token=request.cookies.get('product_session','')
 with conn() as c:row=c.execute('SELECT u.id,u.email FROM users u JOIN sessions s ON s.owner=u.id WHERE s.digest=%s AND s.expires>%s',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
 if not row:raise HTTPException(401,'Sign in required')
 return dict(row)
def session(response,user):
 token=secrets.token_urlsafe(32)
 with conn() as c:
  c.execute('DELETE FROM sessions WHERE expires<%s',(time.time(),))
  c.execute('INSERT INTO sessions(digest,owner,expires) VALUES (%s,%s,%s)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],time.time()+86400))
 response.set_cookie('product_session',token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE')=='1',max_age=86400)
 return user
@app.get('/api/health')
def health():
 try:
  with conn() as c:c.execute('SELECT 1')
 except Exception:raise HTTPException(503,'Database unavailable')
 return {'status':'ok'}
@app.post('/api/register',status_code=201)
def register(body:Credentials,response:Response):
 user={'id':str(uuid4()),'email':body.email.lower()}
 try:
  with conn() as c:c.execute('INSERT INTO users(id,email,password) VALUES (%s,%s,%s)',(user['id'],user['email'],password_hash(body.password)))
 except Exception:raise HTTPException(409,'Account could not be created')
 return session(response,user)
@app.post('/api/login')
def login(body:Credentials,response:Response):
 with conn() as c:row=c.execute('SELECT * FROM users WHERE email=%s',(body.email.lower(),)).fetchone()
 stored=row['password'] if row else '0'*32+':'+'0'*128
 if not hmac.compare_digest(password_hash(body.password,stored.split(':')[0]),stored):raise HTTPException(401,'Invalid credentials')
 return session(response,{'id':row['id'],'email':row['email']})
@app.get('/api/me')
def me(user=Depends(current)):return user
@app.post('/api/logout')
def logout(request:Request,response:Response):
 with conn() as c:c.execute('DELETE FROM sessions WHERE digest=%s',(hashlib.sha256(request.cookies.get('product_session','').encode()).hexdigest(),))
 response.delete_cookie('product_session');return {'signed_out':True}
def entity_spec(entity):
 found=next((e for e in SPEC['entities'] if e['name']==entity),None)
 if not found:raise HTTPException(404,'Entity not found')
 return found
def validated(entity,data):
 spec=entity_spec(entity);fields={f['name']:f for f in spec['fields']}
 if set(data)!=set(fields):raise HTTPException(422,'Supply exactly the configured fields')
 for key,value in data.items():
  if fields[key]['type']=='number':
   if isinstance(value,bool) or not isinstance(value,(int,float)) or not __import__('math').isfinite(value):raise HTTPException(422,'Invalid number')
  elif not isinstance(value,str) or not value.strip() or len(value)>2000:raise HTTPException(422,'Invalid field')
  elif fields[key]['type']=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise HTTPException(422,'Invalid email')
  elif fields[key]['type']=='date':
   try:__import__('datetime').date.fromisoformat(value)
   except ValueError:raise HTTPException(422,'Invalid date')
 return data
@app.get('/api/items/{entity}')
def items(entity:str,user=Depends(current)):
 entity_spec(entity)
 with conn() as c:rows=c.execute('SELECT id,data FROM items WHERE owner=%s AND entity=%s',(user['id'],entity)).fetchall()
 return [{'id':r['id'],'data':json.loads(r['data'])} for r in rows]
@app.post('/api/items/{entity}',status_code=201)
def create(entity:str,data:dict,user=Depends(current)):
 validated(entity,data);id=str(uuid4())
 with conn() as c:c.execute('INSERT INTO items(id,owner,entity,data) VALUES (%s,%s,%s,%s)',(id,user['id'],entity,json.dumps(data)))
 return {'id':id,'data':data}
@app.put('/api/items/{entity}/{id}')
def update(entity:str,id:str,data:dict,user=Depends(current)):
 validated(entity,data)
 with conn() as c:
  result=c.execute('UPDATE items SET data=%s WHERE id=%s AND owner=%s AND entity=%s',(json.dumps(data),id,user['id'],entity))
  if not result.rowcount:raise HTTPException(404,'Record not found')
 return {'id':id,'data':data}
@app.delete('/api/items/{entity}/{id}')
def delete(entity:str,id:str,user=Depends(current)):
 entity_spec(entity)
 with conn() as c:
  result=c.execute('DELETE FROM items WHERE id=%s AND owner=%s AND entity=%s',(id,user['id'],entity))
  if not result.rowcount:raise HTTPException(404,'Record not found')
 return {'deleted':True}
if Path('static').is_dir():app.mount('/',StaticFiles(directory='static',html=True),name='frontend')
'''

NODE = r'''import express from 'express';import pg from 'pg';import crypto from 'node:crypto';import fs from 'node:fs';
const spec=JSON.parse(fs.readFileSync(new URL('./spec.json',import.meta.url))),pool=new pg.Pool({connectionString:process.env.DATABASE_URL}),app=express();
await pool.query('CREATE TABLE IF NOT EXISTS users(id text PRIMARY KEY,email text UNIQUE NOT NULL,password text NOT NULL)');await pool.query('CREATE TABLE IF NOT EXISTS sessions(digest text PRIMARY KEY,owner text REFERENCES users(id),expires double precision NOT NULL)');await pool.query('CREATE TABLE IF NOT EXISTS items(id text PRIMARY KEY,owner text REFERENCES users(id),entity text,data jsonb)');
app.disable('x-powered-by');app.use(express.json({limit:'50kb'}));const buckets=new Map();
app.use((req,res,next)=>{res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'");if(!['GET','HEAD','OPTIONS'].includes(req.method)){if(req.get('X-Requested-With')!=='Product')return res.status(403).json({detail:'Application header required'});if(req.get('origin')&&req.get('origin')!==(process.env.PUBLIC_ORIGIN||req.protocol+'://'+req.get('host')))return res.status(403).json({detail:'Origin denied'})}next()});
function hash(p,salt=crypto.randomBytes(16).toString('hex')){return salt+':'+crypto.scryptSync(p,Buffer.from(salt,'hex'),64).toString('hex')}
function digest(s){return crypto.createHash('sha256').update(s).digest('hex')}
function cookie(req){return (req.get('cookie')||'').split(';').map(s=>s.trim()).find(s=>s.startsWith('product_session='))?.slice(16)||''}
app.get('/api/health',async(req,res)=>{try{await pool.query('SELECT 1');res.json({status:'ok'})}catch{res.status(503).json({detail:'Database unavailable'})}});
for(const method of ['register','login'])app.post('/api/'+method,async(req,res,next)=>{try{const now=Date.now(),recent=(buckets.get(req.ip)||[]).filter(t=>now-t<60000);if(recent.length>=20)return res.status(429).json({detail:'Try again in a minute'});recent.push(now);buckets.set(req.ip,recent);if(buckets.size>10000)for(const [ip,times]of buckets)if(now-times.at(-1)>60000)buckets.delete(ip);let{email,password}=req.body;if(typeof email!=='string'||email.length>254||!/^\S+@\S+\.\S+$/.test(email)||typeof password!=='string'||password.length<12||password.length>128)return res.status(422).json({detail:'Valid email and password of 12–128 characters required'});email=email.toLowerCase();let user;if(method==='register'){user={id:crypto.randomUUID(),email};try{await pool.query('INSERT INTO users VALUES($1,$2,$3)',[user.id,email,hash(password)])}catch{return res.status(409).json({detail:'Account could not be created'})}}else{const row=(await pool.query('SELECT * FROM users WHERE email=$1',[email])).rows[0],stored=row?.password||'0'.repeat(32)+':'+'0'.repeat(128);if(!crypto.timingSafeEqual(Buffer.from(hash(password,stored.split(':')[0])),Buffer.from(stored)))return res.status(401).json({detail:'Invalid credentials'});user={id:row.id,email:row.email}}const token=crypto.randomBytes(32).toString('base64url');await pool.query('DELETE FROM sessions WHERE expires<$1',[Date.now()]);await pool.query('INSERT INTO sessions VALUES($1,$2,$3)',[digest(token),user.id,Date.now()+86400000]);res.cookie('product_session',token,{httpOnly:true,sameSite:'strict',secure:process.env.COOKIE_SECURE==='1',maxAge:86400000});res.status(method==='register'?201:200).json(user)}catch(e){next(e)}});
app.post('/api/logout',async(req,res,next)=>{try{await pool.query('DELETE FROM sessions WHERE digest=$1',[digest(cookie(req))]);res.clearCookie('product_session');res.json({signed_out:true})}catch(e){next(e)}});
app.use('/api',async(req,res,next)=>{try{const row=(await pool.query('SELECT u.id,u.email FROM users u JOIN sessions s ON s.owner=u.id WHERE s.digest=$1 AND s.expires>$2',[digest(cookie(req)),Date.now()])).rows[0];if(!row)return res.status(401).json({detail:'Sign in required'});req.user=row;next()}catch(e){next(e)}});
app.get('/api/me',(req,res)=>res.json(req.user));
app.use('/api/items/:entity',(req,res,next)=>{req.entity=spec.entities.find(e=>e.name===req.params.entity);if(!req.entity)return res.status(404).json({detail:'Entity not found'});next()});
function validate(entity,data){if(!data||Array.isArray(data)||typeof data!=='object'||Object.keys(data).length!==entity.fields.length)return false;return entity.fields.every(f=>Object.hasOwn(data,f.name)&&(f.type==='number'?typeof data[f.name]==='number'&&Number.isFinite(data[f.name]):typeof data[f.name]==='string'&&data[f.name].trim()&&data[f.name].length<=2000&&(f.type!=='email'||/^\S+@\S+\.\S+$/.test(data[f.name]))&&(f.type!=='date'||/^\d{4}-\d{2}-\d{2}$/.test(data[f.name])&&!Number.isNaN(Date.parse(data[f.name])))))}
app.get('/api/items/:entity',async(req,res,next)=>{try{res.json((await pool.query('SELECT id,data FROM items WHERE owner=$1 AND entity=$2',[req.user.id,req.entity.name])).rows)}catch(e){next(e)}});
app.post('/api/items/:entity',async(req,res,next)=>{try{if(!validate(req.entity,req.body))return res.status(422).json({detail:'Supply valid configured fields'});const id=crypto.randomUUID();await pool.query('INSERT INTO items VALUES($1,$2,$3,$4)',[id,req.user.id,req.entity.name,req.body]);res.status(201).json({id,data:req.body})}catch(e){next(e)}});
app.put('/api/items/:entity/:id',async(req,res,next)=>{try{if(!validate(req.entity,req.body))return res.status(422).json({detail:'Supply valid configured fields'});const r=await pool.query('UPDATE items SET data=$1 WHERE id=$2 AND owner=$3 AND entity=$4',[req.body,req.params.id,req.user.id,req.entity.name]);if(!r.rowCount)return res.status(404).json({detail:'Record not found'});res.json({id:req.params.id,data:req.body})}catch(e){next(e)}});
app.delete('/api/items/:entity/:id',async(req,res,next)=>{try{const r=await pool.query('DELETE FROM items WHERE id=$1 AND owner=$2 AND entity=$3',[req.params.id,req.user.id,req.entity.name]);if(!r.rowCount)return res.status(404).json({detail:'Record not found'});res.json({deleted:true})}catch(e){next(e)}});
app.use(express.static('static'));app.use((err,req,res,next)=>res.status(err.status===413?413:500).json({detail:'Request failed'}));app.listen(Number(process.env.PORT)||8000,'0.0.0.0');
'''

def generate(spec, root=None):
    assets = (root/'frontend') if root else Path(__file__).with_name('template_assets')
    public = json.dumps(spec, ensure_ascii=False, indent=2)
    package = json.loads((assets/'package.json').read_text())
    package.update(name='generated-product', scripts={'dev':'vite --host 127.0.0.1','build':'vite build'})
    lock = json.loads((assets/'package-lock.json').read_text())
    lock['name'] = 'generated-product'; lock['packages']['']['name'] = 'generated-product'
    files={'frontend/package.json':json.dumps(package,indent=2),'frontend/package-lock.json':json.dumps(lock), 'frontend/index.html':'<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Product workspace</title></head><body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body></html>', 'frontend/src/main.jsx':REACT,'frontend/src/style.css':STYLE,'frontend/src/spec.json':public,'frontend/vite.config.js':"import {defineConfig} from 'vite';export default defineConfig({server:{proxy:{'/api':'http://localhost:8000'}}});",'backend/spec.json':public,'.gitignore':'.env\nnode_modules/\ndist/\n*.db\n__pycache__/\n', '.env.example':'POSTGRES_PASSWORD=replace-with-a-long-random-password\n', 'README.md':'# '+spec['name']+'\n\nGenerated starter implementing account authentication and private entity CRUD.\n\n1. Copy .env.example to .env and replace the database password.\n2. Run docker compose up --build -d.\n3. Open http://localhost:8000.\n\nThis is a starter, not a production security certification. Review generated source and add domain-specific business logic, email recovery, TLS, backups, monitoring and your acceptance tests before deployment. Requested integrations are recorded in spec.json and require explicit connector implementation.\n'}
    docker_front='FROM node:24-bookworm-slim AS web\nWORKDIR /web\nCOPY frontend/package*.json ./\nRUN npm ci --no-audit --no-fund\nCOPY frontend ./\nRUN npm run build\n'
    if spec['stack']=='react_fastapi':
        files.update({'backend/app.py':PYTHON,'backend/requirements.txt':'fastapi==0.115.12\nuvicorn==0.34.2\npsycopg[binary]==3.2.9\n','Dockerfile':docker_front+'FROM python:3.12-slim\nWORKDIR /app\nCOPY backend/requirements.txt ./\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY backend ./\nCOPY --from=web /web/dist ./static\nRUN useradd --uid 10001 --create-home product && chown -R product:product /app\nUSER product\nEXPOSE 8000\nCMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]\n'})
    elif spec['stack']=='react_express':
        files.update({'backend/server.mjs':NODE,'backend/package.json':(assets/'node-api/package.json').read_text(),'backend/package-lock.json':(assets/'node-api/package-lock.json').read_text(),'Dockerfile':docker_front+'FROM node:24-bookworm-slim\nWORKDIR /app\nCOPY backend/package*.json ./\nRUN npm ci --omit=dev --no-audit --no-fund\nCOPY backend ./\nCOPY --from=web /web/dist ./static\nUSER node\nEXPOSE 8000\nCMD ["node","server.mjs"]\n'})
    else: raise ValueError('No verified source adapter for this stack')
    files['compose.yaml']='''services:
  db:
    image: postgres:17
    environment:
      POSTGRES_USER: product
      POSTGRES_DB: product
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
    volumes: [product_database:/var/lib/postgresql/data]
    healthcheck:
      test: [CMD-SHELL, pg_isready -U product]
      interval: 3s
      timeout: 3s
      retries: 20
  app:
    build: .
    ports: [127.0.0.1:8000:8000]
    environment:
      DATABASE_URL: postgresql://product@db:5432/product
      PGPASSWORD: ${POSTGRES_PASSWORD}
      PUBLIC_ORIGIN: http://localhost:8000
    depends_on:
      db:
        condition: service_healthy
volumes:
  product_database:
'''
    from backend.runtime_export import attach
    return attach(files)

def validate(files):
    checks=[]
    for path,content in files.items():
        from pathlib import PurePosixPath
        parsed=PurePosixPath(path)
        if parsed.is_absolute() or '..' in parsed.parts or '\\' in path: raise ValueError('Unsafe artifact path')
        if path.endswith('.py'):ast.parse(content);checks.append('Python syntax: '+path)
        if path.endswith('.json'):json.loads(content)
    if not files.get('frontend/src/main.jsx') or not files.get('Dockerfile'):raise ValueError('Missing required source artifacts')
    import yaml
    try:
        compose=yaml.safe_load(files['compose.yaml'])
        services=compose['services']
        if any(services[name].get('networks')!=['product_private'] for name in ('app','db')):raise ValueError('Product network boundary missing')
        if any(services[name].get('networks')!=['agent_private'] for name in ('agents_db','agents_api','agents_web')):raise ValueError('Agent network boundary missing')
        if any(services[name].get('ports') for name in ('db','agents_db','agents_api')):raise ValueError('Private service port exposed')
        checks.append('Compose services and isolated product/agent networks validated')
    except (yaml.YAMLError,KeyError,TypeError):raise ValueError('Invalid generated Compose source')
    checks += ['Manifest paths validated','Frontend and backend contracts generated','Authentication and owner-scoped CRUD included','No generated code executed in platform API']
    return checks
