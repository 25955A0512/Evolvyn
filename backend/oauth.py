"""Fixed-provider OAuth authorization code + PKCE, verified email, explicit account linking."""
import base64
import hashlib
import os
import secrets
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode,urlparse
from uuid import uuid4
import httpx
from fastapi import Depends,HTTPException,Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel,Field,ConfigDict
from backend.identity import password_hash,verify_password,session_cookie_name

PROVIDERS={
 'google':{'name':'Google','authorize':'https://accounts.google.com/o/oauth2/v2/auth','token':'https://oauth2.googleapis.com/token','scope':'openid email profile'},
 'github':{'name':'GitHub','authorize':'https://github.com/login/oauth/authorize','token':'https://github.com/login/oauth/access_token','scope':'read:user user:email'},
}
def configuration(provider):
    if provider not in PROVIDERS:raise HTTPException(404,'Unknown sign-in provider')
    prefix='OAUTH_'+provider.upper()
    origin=os.getenv('PUBLIC_ORIGIN','http://localhost:3000').split(',')[0].rstrip('/')
    parsed=urlparse(origin)
    if parsed.scheme!='https' and parsed.hostname not in ('localhost','127.0.0.1'):raise HTTPException(503,'OAuth requires an HTTPS public origin')
    return {**PROVIDERS[provider],'client_id':os.getenv(prefix+'_CLIENT_ID',''),'client_secret':os.getenv(prefix+'_CLIENT_SECRET',''),'redirect_uri':origin+'/api/auth/oauth/'+provider+'/callback'}
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def oauth_cookie_name():
    name=session_cookie_name()
    return 'evolvyn_oauth' if name=='evolvyn_session' else name+'_oauth'
def issue(response,account,organization,c):
    token=secrets.token_urlsafe(32)
    c.execute('DELETE FROM account_sessions WHERE expires<now()')
    c.execute('INSERT INTO account_sessions(digest,account_id,organization_id,expires) VALUES (%s,%s,%s,%s)',(digest(token),account,organization,datetime.now(timezone.utc)+timedelta(days=7)))
    response.set_cookie(session_cookie_name(),token,httponly=True,secure=os.getenv('COOKIE_SECURE')=='1',samesite='strict',max_age=604800,path='/')

async def verified_profile(provider,settings,code,verifier):
    async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
        response=await client.post(settings['token'],data={'grant_type':'authorization_code','code':code,'client_id':settings['client_id'],'client_secret':settings['client_secret'],'redirect_uri':settings['redirect_uri'],'code_verifier':verifier},headers={'Accept':'application/json'})
        response.raise_for_status();token=response.json().get('access_token')
        if not token or not isinstance(token,str) or len(token)>8192:raise ValueError('Provider access token missing')
        headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
        if provider=='google':
            response=await client.get('https://openidconnect.googleapis.com/v1/userinfo',headers=headers);response.raise_for_status();profile=response.json()
            if profile.get('email_verified') is not True:raise ValueError('Verified email required')
            subject=profile['sub'];email=profile['email'];name=profile.get('name','My workspace')
        else:
            response=await client.get('https://api.github.com/user',headers=headers);response.raise_for_status();profile=response.json()
            subject=str(profile['id']);name=profile.get('name') or profile.get('login','My workspace')
            response=await client.get('https://api.github.com/user/emails',headers=headers);response.raise_for_status()
            addresses=response.json()
            email=next((item['email'] for item in addresses if item.get('verified') is True and item.get('primary') is True),None)
            if not email:raise ValueError('Verified primary email required')
        if not isinstance(subject,str) or not 1<=len(subject)<=255 or not isinstance(email,str) or '@' not in email or len(email)>254:raise ValueError('Invalid identity')
        return subject,email.strip().lower(),str(name)[:100]

class PasswordChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)

def install(app,conn,auth):
    def begin(provider,link=None):
        settings=configuration(provider)
        if not settings['client_id'] or not settings['client_secret']:raise HTTPException(503,'This sign-in provider needs administrator OAuth configuration')
        state=secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        with conn() as c:
            c.execute('DELETE FROM oauth_states WHERE expires<now()')
            c.execute('INSERT INTO oauth_states(digest,provider,verifier,browser_digest,link_account,expires) VALUES (%s,%s,%s,%s,%s,%s)',(digest(state),provider,verifier,digest(browser),link,datetime.now(timezone.utc)+timedelta(minutes=10)))
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        url=settings['authorize']+'?'+urlencode({'response_type':'code','client_id':settings['client_id'],'redirect_uri':settings['redirect_uri'],'scope':settings['scope'],'state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
        response=RedirectResponse(url,status_code=303)
        response.set_cookie(oauth_cookie_name(),browser,httponly=True,secure=os.getenv('COOKIE_SECURE')=='1',samesite='lax',max_age=600,path='/api/auth/oauth')
        response.headers['Cache-Control']='no-store'
        return response
    @app.get('/api/auth/providers')
    def providers():
        rows=[]
        for provider,base in PROVIDERS.items():
            try:
                settings=configuration(provider);enabled=bool(settings['client_id'] and settings['client_secret'])
            except HTTPException:enabled=False
            rows.append({'id':provider,'name':base['name'],'enabled':enabled,'start_url':'/api/auth/oauth/'+provider+'/start'})
        return rows
    @app.get('/api/auth/oauth/{provider}/start')
    def start(provider:str):return begin(provider)
    @app.post('/api/auth/oauth/{provider}/link')
    def link(provider:str,request:Request,owner=Depends(auth)):
        account=getattr(request.state,'identity',{}).get('account_id')
        if not account:raise HTTPException(403,'Sign in to your account before linking')
        response=begin(provider,account)
        # Fetch cannot navigate across providers; return only the fixed-provider URL and set cookie.
        from fastapi.responses import JSONResponse
        output=JSONResponse({'authorize_url':response.headers['location']})
        output.raw_headers.extend([(key,value) for key,value in response.raw_headers if key.lower()==b'set-cookie'])
        return output
    @app.get('/api/auth/oauth/{provider}/callback')
    async def callback(provider:str,request:Request,state:str='',code:str=''):
        settings=configuration(provider)
        if not state or len(state)>200 or not code or len(code)>4096:raise HTTPException(400,'Authorization was cancelled or invalid')
        with conn() as c:
            row=c.execute('DELETE FROM oauth_states WHERE digest=%s AND provider=%s AND expires>now() RETURNING *',(digest(state),provider)).fetchone()
        if not row or not secrets.compare_digest(row['browser_digest'],digest(request.cookies.get(oauth_cookie_name(),''))):raise HTTPException(400,'Sign-in state expired, consumed or belongs to another browser')
        try:subject,email,name=await verified_profile(provider,settings,code,row['verifier'])
        except Exception:raise HTTPException(401,'Provider identity could not be verified; no session created')
        import psycopg
        response=RedirectResponse('/',status_code=303);response.delete_cookie(oauth_cookie_name(),path='/api/auth/oauth');response.headers['Cache-Control']='no-store'
        try:
            with conn() as c:
                # Serialize subject linking and never auto-link by email.
                c.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('oauth:'+provider+':'+subject,))
                linked=c.execute('SELECT account_id FROM oauth_identities WHERE provider=%s AND subject=%s',(provider,subject)).fetchone()
                if row['link_account']:
                    account=row['link_account']
                    if linked and linked['account_id']!=account:raise HTTPException(409,'Provider identity already belongs to another account')
                elif linked:account=linked['account_id']
                else:
                    if c.execute('SELECT id FROM accounts WHERE email=%s',(email,)).fetchone():raise HTTPException(409,'An account already uses that email. Sign in with the original method, then explicitly link this provider in account settings.')
                    account=str(uuid4());organization=str(uuid4())
                    c.execute('INSERT INTO accounts(id,email,name,password_hash) VALUES (%s,%s,%s,%s)',(account,email,name,'oauth-only'))
                    c.execute('INSERT INTO organizations(id,name) VALUES (%s,%s)',(organization,name))
                    c.execute('INSERT INTO memberships(account_id,organization_id,role) VALUES (%s,%s,%s)',(account,organization,'owner'))
                if not linked:c.execute('INSERT INTO oauth_identities(provider,subject,account_id) VALUES (%s,%s,%s)',(provider,subject,account))
                membership=c.execute('SELECT organization_id FROM memberships WHERE account_id=%s ORDER BY organization_id LIMIT 1',(account,)).fetchone()
                if not membership:raise HTTPException(403,'No active organization membership')
                issue(response,account,membership['organization_id'],c)
        except psycopg.errors.UniqueViolation:raise HTTPException(409,'Identity was registered concurrently; retry sign-in')
        return response
    @app.get('/api/auth/security')
    def security(request:Request,owner=Depends(auth)):
        account=getattr(request.state,'identity',{}).get('account_id')
        if not account:raise HTTPException(403,'An account is required')
        with conn() as c:
            sessions=c.execute('SELECT expires FROM account_sessions WHERE account_id=%s AND expires>now() ORDER BY expires DESC',(account,)).fetchall()
            identities=c.execute('SELECT provider FROM oauth_identities WHERE account_id=%s',(account,)).fetchall()
        return {'active_sessions':len(sessions),'linked_providers':[r['provider'] for r in identities]}
    @app.post('/api/auth/sessions/revoke-all')
    def revoke(request:Request,owner=Depends(auth)):
        account=getattr(request.state,'identity',{}).get('account_id')
        if not account:raise HTTPException(403,'An account is required')
        with conn() as c:c.execute('DELETE FROM account_sessions WHERE account_id=%s',(account,))
        return {'revoked':True}
    @app.post('/api/auth/password')
    def change(body:PasswordChange,request:Request,owner=Depends(auth)):
        account=getattr(request.state,'identity',{}).get('account_id')
        if not account:raise HTTPException(403,'An account is required')
        with conn() as c:
            row=c.execute('SELECT password_hash FROM accounts WHERE id=%s FOR UPDATE',(account,)).fetchone()
            if not verify_password(body.current_password,row['password_hash']):raise HTTPException(401,'Current password is invalid')
            c.execute('UPDATE accounts SET password_hash=%s WHERE id=%s',(password_hash(body.new_password),account))
            c.execute('DELETE FROM account_sessions WHERE account_id=%s',(account,))
        return {'changed':True,'sign_in_required':True}
