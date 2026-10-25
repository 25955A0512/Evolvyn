"""Fixed-provider OAuth authorization code + PKCE, verified email, explicit account linking."""
import base64
import hashlib
import os
import secrets
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from fastapi import Depends,HTTPException,Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel,Field,ConfigDict
from backend.identity import password_hash,verify_password,session_cookie_name
from backend.oauth_config import public_origin,fingerprint

PROVIDERS={
 'google':{'name':'Google','authorize':'https://accounts.google.com/o/oauth2/v2/auth','token':'https://oauth2.googleapis.com/token','scope':'openid email profile'},
 'github':{'name':'GitHub','authorize':'https://github.com/login/oauth/authorize','token':'https://github.com/login/oauth/access_token','scope':'read:user user:email'},
}
def configuration(provider):
    if provider not in PROVIDERS:raise HTTPException(404,'Unknown sign-in provider')
    prefix='OAUTH_'+provider.upper()
    try:origin=public_origin(os.getenv('PUBLIC_ORIGIN','http://localhost:3000'),os.getenv('COOKIE_SECURE')=='1')
    except ValueError as error:raise HTTPException(503,str(error))
    if session_cookie_name().startswith(('__Host-','__Secure-')) and os.getenv('COOKIE_SECURE')!='1':raise HTTPException(503,'Prefixed session cookies require COOKIE_SECURE=1')
    return {**PROVIDERS[provider],'client_id':os.getenv(prefix+'_CLIENT_ID',''),'client_secret':os.getenv(prefix+'_CLIENT_SECRET',''),'redirect_uri':origin+'/api/auth/oauth/'+provider+'/callback'}
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def oauth_cookie_name():
    name=session_cookie_name()
    return 'evolvyn_oauth' if name=='evolvyn_session' else name+'_oauth'
def oauth_cookie_path(name):return '/' if name.startswith('__Host-') else '/api/auth/oauth'
def issue(response,account,organization,c):
    token=secrets.token_urlsafe(32)
    c.execute('DELETE FROM account_sessions WHERE expires<now()')
    c.execute('INSERT INTO account_sessions(digest,account_id,organization_id,expires) VALUES (%s,%s,%s,%s)',(digest(token),account,organization,datetime.now(timezone.utc)+timedelta(days=7)))
    response.set_cookie(session_cookie_name(),token,httponly=True,secure=os.getenv('COOKIE_SECURE')=='1',samesite='strict',max_age=604800,path='/')

async def provider_json(client,method,url,**kwargs):
    """Fixed provider callers only; bound reads before parsing untrusted JSON."""
    import json
    chunks=[];size=0
    async with client.stream(method,url,**kwargs) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            size+=len(chunk)
            if size>262144:raise ValueError('Provider response exceeds budget')
            chunks.append(chunk)
    value=json.loads(b''.join(chunks))
    if not isinstance(value,(dict,list)):raise ValueError('Invalid provider JSON')
    return value

async def verified_profile(provider,settings,code,verifier):
    import asyncio,re
    async with asyncio.timeout(30), httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
        result=await provider_json(client,'POST',settings['token'],data={'grant_type':'authorization_code','code':code,'client_id':settings['client_id'],'client_secret':settings['client_secret'],'redirect_uri':settings['redirect_uri'],'code_verifier':verifier},headers={'Accept':'application/json'})
        if not isinstance(result,dict):raise ValueError('Invalid token response')
        token=result.get('access_token')
        if not isinstance(token,str) or not 1<=len(token)<=8192 or any(c in token for c in ('\r','\n')):raise ValueError('Provider access token missing')
        headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
        if provider=='google':
            profile=await provider_json(client,'GET','https://openidconnect.googleapis.com/v1/userinfo',headers=headers)
            if not isinstance(profile,dict) or profile.get('email_verified') is not True:raise ValueError('Verified email required')
            subject=profile.get('sub');email=profile.get('email');name=profile.get('name') or 'My workspace'
        else:
            profile=await provider_json(client,'GET','https://api.github.com/user',headers=headers)
            if not isinstance(profile,dict) or type(profile.get('id')) is not int or profile['id']<=0:raise ValueError('Invalid GitHub identity')
            subject=str(profile['id']);name=profile.get('name') or profile.get('login') or 'My workspace'
            addresses=await provider_json(client,'GET','https://api.github.com/user/emails',headers=headers)
            if not isinstance(addresses,list) or len(addresses)>100 or any(not isinstance(item,dict) for item in addresses):raise ValueError('Invalid verified email response')
            email=next((item.get('email') for item in addresses if item.get('verified') is True and item.get('primary') is True),None)
        if not isinstance(subject,str) or not 1<=len(subject)<=255 or not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Invalid verified identity')
        return subject,email.lower(),str(name)[:100]

class PasswordChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)

def install(app,conn,auth):
    @app.middleware('http')
    async def browser_oauth_errors(request,call_next):
        response=await call_next(request)
        if request.url.path.startswith('/api/auth/oauth/') and request.url.path.endswith('/callback') and response.status_code>=400 and 'text/html' in request.headers.get('accept',''):
            from fastapi.responses import HTMLResponse
            message={400:'Authorization was cancelled, expired or invalid. Please start again.',401:'The provider identity could not be verified. No new session was created.',403:'Your initiating session or permissions are no longer valid. Sign in again before linking.',409:'This identity conflicts with an existing account. Sign in with your original method, then link the provider in account settings.',429:'Too many attempts. Wait a minute, then try again.',503:'Administrator OAuth configuration is required before sign-in.'}.get(response.status_code,'Authorization could not be completed. Please retry after checking provider setup.')
            response=HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evolvyn · Authorization</title><main><h1>Authorization could not be completed</h1><p>'+message+'</p><p><a href="/login">Return to sign in</a> · <a href="/integrations">Return to connections</a></p></main></html>',status_code=response.status_code,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
        return response
    def begin(provider,link=None,request=None,organization=None):
        settings=configuration(provider)
        if not settings['client_id'] or not settings['client_secret']:raise HTTPException(503,'This sign-in provider needs administrator OAuth configuration')
        state=secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        with conn() as c:
            c.execute('DELETE FROM oauth_states WHERE expires<now()')
            c.execute('INSERT INTO oauth_states(digest,provider,verifier,browser_digest,link_account,expires,session_digest,organization_id,config_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',(digest(state),provider,verifier,digest(browser),link,datetime.now(timezone.utc)+timedelta(minutes=10),digest(request.cookies.get(session_cookie_name(),'')) if link else None,organization,fingerprint(settings)))
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        url=settings['authorize']+'?'+urlencode({'response_type':'code','client_id':settings['client_id'],'redirect_uri':settings['redirect_uri'],'scope':settings['scope'],'state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
        response=RedirectResponse(url,status_code=303)
        response.set_cookie(oauth_cookie_name(),browser,httponly=True,secure=os.getenv('COOKIE_SECURE')=='1',samesite='lax',max_age=600,path=oauth_cookie_path(oauth_cookie_name()))
        response.headers['Cache-Control']='no-store'
        return response
    @app.get('/api/auth/providers')
    def providers():
        rows=[]
        for provider,base in PROVIDERS.items():
            settings=None;problem=None
            try:
                settings=configuration(provider);enabled=bool(settings['client_id'] and settings['client_secret'])
            except HTTPException as error:enabled=False;problem=error.detail
            rows.append({'id':provider,'name':base['name'],'enabled':enabled,'configuration_status':'ready_for_sign_in' if enabled else 'invalid_configuration' if problem else 'missing_credentials','configuration_error':problem,'start_url':'/api/auth/oauth/'+provider+'/start','setup':{'callback_url':settings['redirect_uri'] if settings else '', 'client_id_env':'OAUTH_'+provider.upper()+'_CLIENT_ID','client_secret_env':'OAUTH_'+provider.upper()+'_CLIENT_SECRET','console_url':'https://console.cloud.google.com/auth/clients' if provider=='google' else 'https://github.com/settings/developers','instructions':['Create a web OAuth application in the provider console.','Register this exact callback URL. For Google, add your email as a test user while the consent screen is in testing.','Run python scripts/configure_oauth.py --provider '+provider+' on the machine running Evolvyn. The client secret is entered with hidden input and saved only in ignored .local/deploy.env.','Recreate the API container with docker compose --env-file .local/deploy.env up -d --force-recreate api, then refresh this page.','Complete a real provider sign-in. Configuration alone is not proof of successful authorization.']}})
        return rows
    @app.get('/api/auth/oauth/{provider}/start')
    def start(provider:str):return begin(provider)
    @app.post('/api/auth/oauth/{provider}/link')
    def link(provider:str,request:Request,owner=Depends(auth)):
        account=getattr(request.state,'identity',{}).get('account_id')
        if not account:raise HTTPException(403,'Sign in to your account before linking')
        response=begin(provider,account,request,owner)
        # Fetch cannot navigate across providers; return only the fixed-provider URL and set cookie.
        from fastapi.responses import JSONResponse
        output=JSONResponse({'authorize_url':response.headers['location']},headers={'Cache-Control':'no-store'})
        output.raw_headers.extend([(key,value) for key,value in response.raw_headers if key.lower()==b'set-cookie'])
        return output
    @app.get('/api/auth/oauth/{provider}/callback')
    async def callback(provider:str,request:Request,state:str='',code:str=''):
        settings=configuration(provider)
        if not state or len(state)>200 or not code or len(code)>4096:raise HTTPException(400,'Authorization was cancelled or invalid')
        if state.startswith('cx_'):
            service=getattr(app.state,'connector_oauth',None)
            if not service:raise HTTPException(400,'Connector authorization is unavailable')
            return await service.callback(provider,request,state,code)
        with conn() as c:
            row=c.execute('DELETE FROM oauth_states WHERE digest=%s AND provider=%s AND expires>now() RETURNING *',(digest(state),provider)).fetchone()
        if not row or not secrets.compare_digest(row['browser_digest'],digest(request.cookies.get(oauth_cookie_name(),''))):raise HTTPException(400,'Sign-in state expired, consumed or belongs to another browser')
        if not row['config_digest'] or not secrets.compare_digest(row['config_digest'],fingerprint(settings)):raise HTTPException(400,'OAuth configuration changed; restart sign-in')
        def validate_link(c):
            if not row['link_account']:return
            session=c.execute('SELECT account_id FROM account_sessions WHERE digest=%s AND account_id=%s AND organization_id=%s AND expires>now() FOR SHARE',(row['session_digest'],row['link_account'],row['organization_id'])).fetchone()
            member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s FOR SHARE',(row['link_account'],row['organization_id'])).fetchone()
            if not session or not member:raise HTTPException(403,'The initiating session or membership was revoked; sign in before linking again')
        with conn() as c:validate_link(c)
        try:subject,email,name=await verified_profile(provider,settings,code,row['verifier'])
        except Exception:raise HTTPException(401,'Provider identity could not be verified; no session created')
        import psycopg
        response=RedirectResponse('/auth/callback',status_code=303);response.delete_cookie(oauth_cookie_name(),path=oauth_cookie_path(oauth_cookie_name()));response.headers['Cache-Control']='no-store'
        try:
            with conn() as c:
                validate_link(c)
                # Serialize subject linking and never auto-link by email.
                c.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('oauth:'+provider+':'+subject,))
                linked=c.execute('SELECT account_id FROM oauth_identities WHERE provider=%s AND subject=%s',(provider,subject)).fetchone()
                if row['link_account']:
                    account=row['link_account']
                    c.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('oauth-account:'+provider+':'+account,))
                    prior=c.execute('SELECT subject FROM oauth_identities WHERE account_id=%s AND provider=%s',(account,provider)).fetchone()
                    if prior and prior['subject']!=subject:raise HTTPException(409,'This account already has a different identity linked for this provider')
                    if linked and linked['account_id']!=account:raise HTTPException(409,'Provider identity already belongs to another account')
                elif linked:account=linked['account_id']
                else:
                    if c.execute('SELECT id FROM accounts WHERE email=%s',(email,)).fetchone():raise HTTPException(409,'An account already uses that email. Sign in with the original method, then explicitly link this provider in account settings.')
                    account=str(uuid4());organization=str(uuid4())
                    c.execute('INSERT INTO accounts(id,email,name,password_hash) VALUES (%s,%s,%s,%s)',(account,email,name,'oauth-only'))
                    c.execute('INSERT INTO organizations(id,name) VALUES (%s,%s)',(organization,name))
                    c.execute('INSERT INTO memberships(account_id,organization_id,role) VALUES (%s,%s,%s)',(account,organization,'owner'))
                if not linked:c.execute('INSERT INTO oauth_identities(provider,subject,account_id) VALUES (%s,%s,%s)',(provider,subject,account))
                membership=c.execute('SELECT organization_id FROM memberships WHERE account_id=%s'+(' AND organization_id=%s' if row['link_account'] else '')+' ORDER BY organization_id LIMIT 1',((account,row['organization_id']) if row['link_account'] else (account,))).fetchone()
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
