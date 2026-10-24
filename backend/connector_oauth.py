"""Browser-bound account authorization into the existing encrypted vault/MCP registry."""
import base64,hashlib,json,secrets
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from fastapi import Depends,HTTPException,Request
from fastapi.responses import JSONResponse,RedirectResponse
from backend.oauth import configuration,digest
from backend.identity import session_cookie_name
from backend.policy import ACTOR,Principal
from backend.vault import CredentialInput

def cookie_name():return session_cookie_name()+'_connector'
class ConnectorOAuth:
    def __init__(self,s):self.s=s
    def status(self,owner):
        rows=self.s['listing'](owner,'integration_connection')
        return next((r for r in rows if r['provider']=='github'),None)
    async def callback(self,provider,request,state,code):
        s=self.s
        if provider!='github':raise HTTPException(400,'Connector provider mismatch')
        with s['conn']() as c:
            row=c.execute("DELETE FROM records WHERE id=%s AND kind='connector_oauth_state' AND body->>'provider'=%s RETURNING owner,body",('connector-state:'+digest(state),provider)).fetchone()
        if not row:raise HTTPException(400,'Connector authorization state expired or already consumed')
        owner,data=row['owner'],row['body']
        if datetime.fromisoformat(data['expires'])<datetime.now(timezone.utc) or not secrets.compare_digest(data['browser_digest'],digest(request.cookies.get(cookie_name(),''))):raise HTTPException(400,'Connector authorization belongs to another browser or expired')
        with s['conn']() as c:
            member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(data['actor'],owner)).fetchone()
            active=c.execute('SELECT account_id FROM account_sessions WHERE digest=%s AND account_id=%s AND organization_id=%s AND expires>now()',(data['session_digest'],data['actor'],owner)).fetchone()
        if not member or not active:raise HTTPException(403,'The initiating session or membership was revoked')
        actor=ACTOR.set(Principal(owner,data['actor'],member['role']))
        try:
            s['POLICY'].require(owner,'manage_registry');s['POLICY'].require(owner,'manage_vault')
            if not s['POLICY'].settings(owner)['allow_external_processing']:raise HTTPException(403,'External processing is disabled')
            settings=configuration('github')
            try:
                async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
                    response=await client.post(settings['token'],data={'grant_type':'authorization_code','code':code,'client_id':settings['client_id'],'client_secret':settings['client_secret'],'redirect_uri':settings['redirect_uri'],'code_verifier':data['verifier']},headers={'Accept':'application/json'})
                    response.raise_for_status();token=response.json().get('access_token')
                    if not isinstance(token,str) or not 8<=len(token)<=8192:raise ValueError('Missing token')
                    response=await client.get('https://api.github.com/user',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
                    response.raise_for_status();profile=response.json()
                    if type(profile.get('id')) is not int or not isinstance(profile.get('login'),str):raise ValueError('Invalid profile')
            except Exception:raise HTTPException(502,'GitHub authorization or profile verification failed. No connection was marked active.')
            prior=self.status(owner)
            credential=s['VAULT'].put(owner,CredentialInput(name='GitHub authorized connector',provider='mcp',value=token),prior.get('credential_id') if prior else None)
            server=s['save'](owner,'mcp_server',{'name':'GitHub · authorized read-only','transport':'stdio','profile':'github','url':None,'auth_env':None,'credential_id':credential['id'],'enabled':True,'risk':'read','timeout_seconds':20,'status':'registered','tools':[]},prior.get('server_id') if prior else None)
            checked=await s['MCP_REGISTRY'].probe(owner,server['id'])
            connection={'provider':'github','actor':data['actor'],'login':profile['login'][:100],'subject':str(profile['id']),'credential_id':credential['id'],'server_id':server['id'],'state':'connected' if checked['status']=='healthy' else 'needs_test','scope':'Public repositories; read-only tools','last_success_at':datetime.now(timezone.utc).isoformat(),'updated_at':datetime.now(timezone.utc).isoformat()}
            saved=s['save'](owner,'integration_connection',connection,prior['id'] if prior else None)
            if checked['status']=='healthy':self.register(owner,saved,checked)
            s['save'](owner,'audit',{'actor':data['actor'],'action':'connector.authorized','provider':'github','state':connection['state'],'at':connection['updated_at']})
        finally:ACTOR.reset(actor)
        response=RedirectResponse('/integrations?connection=github',status_code=303);response.delete_cookie(cookie_name(),path='/api/auth/oauth');response.headers['Cache-Control']='no-store'
        return response
    def register(self,owner,connection,server):
        existing=self.s['listing'](owner,'registered_tool')
        allowed={'github_repository','github_issues','github_repositories'}
        for tool in server['tools']:
            if tool['name'] not in allowed:continue
            prior=next((r for r in existing if r['name']==tool['name']),None)
            if prior and prior.get('server_id')!=server['id']:continue
            self.s['save'](owner,'registered_tool',{'name':tool['name'],'description':tool['description'],'adapter':'mcp','builtin':None,'server_id':server['id'],'remote_tool':tool['name'],'capabilities':['development.repository.read','business.feedback.read'],'entities':['repository','issue'],'enabled':True},prior['id'] if prior else None)
    def install(self,app,auth):
        app.state.connector_oauth=self;s=self.s
        @app.get('/api/integrations/connections')
        def connections(owner=Depends(auth)):
            s['POLICY'].require(owner,'read');row=self.status(owner)
            if row and row['state']!='disconnected':
                try:
                    server=s['MCP_REGISTRY'].server(owner,row['server_id'])
                    if server.get('status')!='healthy':row={**row,'state':'needs_test'}
                    if row['state']=='connected' and (datetime.now(timezone.utc)-datetime.fromisoformat(row['last_success_at'])).total_seconds()>300:row={**row,'state':'stale'}
                    if not s['POLICY'].settings(owner)['allow_external_processing']:row={**row,'state':'policy_blocked'}
                except HTTPException:row={**row,'state':'needs_authorization'}
            settings=configuration('github')
            return {'github':{'configured':bool(settings['client_id'] and settings['client_secret']),'connection':({k:v for k,v in row.items() if k not in ('credential_id',)} if row else None),'callback_url':settings['redirect_uri'],'scope':'Public repositories, read only. No repository writes or private-repository grants.'}}
        @app.post('/api/integrations/github/authorize')
        def authorize(request:Request,owner=Depends(auth)):
            principal=s['POLICY'].require(owner,'manage_registry');s['POLICY'].require(owner,'manage_vault')
            if not principal.account:raise HTTPException(403,'Sign in with a private account before authorizing a connector')
            if not s['POLICY'].settings(owner)['allow_external_processing']:raise HTTPException(403,'External processing is disabled')
            settings=configuration('github')
            if not settings['client_id'] or not settings['client_secret']:raise HTTPException(503,'Configure the GitHub OAuth app in private deployment settings first. See OAuth setup guidance.')
            state='cx_'+secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
            expires=datetime.now(timezone.utc)+timedelta(minutes=10)
            with s['conn']() as c:
                c.execute("DELETE FROM records WHERE kind='connector_oauth_state' AND body->>'expires'<%s",(datetime.now(timezone.utc).isoformat(),))
                count=c.execute("SELECT count(*) AS n FROM records WHERE owner=%s AND kind='connector_oauth_state'",(owner,)).fetchone()['n']
                if count>=5:raise HTTPException(429,'Finish an existing authorization or wait ten minutes')
                c.execute("INSERT INTO records(id,owner,kind,body) VALUES(%s,%s,'connector_oauth_state',%s)",('connector-state:'+digest(state),owner,json.dumps({'provider':'github','actor':principal.account,'session_digest':digest(request.cookies.get(session_cookie_name(),'')),'browser_digest':digest(browser),'verifier':verifier,'expires':expires.isoformat()})))
            challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            url=settings['authorize']+'?'+urlencode({'client_id':settings['client_id'],'redirect_uri':settings['redirect_uri'],'scope':'read:user','state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
            response=JSONResponse({'authorize_url':url});response.set_cookie(cookie_name(),browser,httponly=True,secure=__import__('os').getenv('COOKIE_SECURE')=='1',samesite='lax',max_age=600,path='/api/auth/oauth');response.headers['Cache-Control']='no-store';return response
        @app.post('/api/integrations/github/test')
        async def test(owner=Depends(auth)):
            s['POLICY'].require(owner,'manage_registry');row=self.status(owner)
            if not row or row['state']=='disconnected':raise HTTPException(409,'Authorize GitHub first')
            server=await s['MCP_REGISTRY'].probe(owner,row['server_id'])
            row['state']='connected' if server['status']=='healthy' else 'needs_test';row['last_checked_at']=server['last_checked_at']
            if row['state']=='connected':
                try:
                    credential=s['VAULT'].reveal_for_service(owner,row['credential_id'],'mcp')
                    async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
                        response=await client.get('https://api.github.com/user',headers={'Authorization':'Bearer '+credential,'Accept':'application/vnd.github+json'})
                        response.raise_for_status()
                        if str(response.json().get('id'))!=row['subject']:raise ValueError('GitHub identity changed')
                    row['last_success_at']=datetime.now(timezone.utc).isoformat()
                except Exception:row['state']='needs_authorization'
            if row['state']=='connected':self.register(owner,row,server)
            s['save'](owner,'integration_connection',{k:v for k,v in row.items() if k!='id'},row['id'])
            return {'state':row['state'],'tools':len(server['tools']),'last_checked_at':server['last_checked_at']}
        @app.delete('/api/integrations/github')
        def disconnect(owner=Depends(auth)):
            s['POLICY'].require(owner,'manage_registry');s['POLICY'].require(owner,'manage_vault');row=self.status(owner)
            if not row:raise HTTPException(404,'Connection not found')
            with s['conn']() as c:
                c.execute("UPDATE records SET body=(body-'ciphertext') || '{\"enabled\":false}'::jsonb WHERE owner=%s AND id=%s AND kind='vault_secret'",(owner,row['credential_id']))
                c.execute("UPDATE records SET body=body || '{\"enabled\":false,\"status\":\"disabled\"}'::jsonb WHERE owner=%s AND id=%s AND kind='mcp_server'",(owner,row['server_id']))
                c.execute("UPDATE records SET body=body || '{\"enabled\":false}'::jsonb WHERE owner=%s AND kind='registered_tool' AND body->>'server_id'=%s",(owner,row['server_id']))
                c.execute("UPDATE records SET body=body || '{\"state\":\"disconnected\"}'::jsonb WHERE owner=%s AND id=%s",(owner,row['id']))
            return {'disconnected':True,'provider_authorization':'Local credential erased and tools disabled. Revoke the OAuth app grant in GitHub settings if required.'}
