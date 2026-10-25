"""Read-only SaaS OAuth grants, bound to an active Evolvyn session and encrypted vault.

Provider payloads are untrusted. Only allowlisted metadata enters connection records;
access/refresh tokens remain in a single encrypted MCP credential.
"""
import base64,hashlib,hmac,json,os,re,secrets
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
import httpx
from fastapi import Depends,HTTPException,Request
from fastapi.responses import JSONResponse,RedirectResponse,HTMLResponse
from pydantic import BaseModel,ConfigDict,Field
from backend.oauth import digest,provider_json
from backend.oauth_config import public_origin,fingerprint
from backend.identity import session_cookie_name
from backend.policy import ACTOR,Principal
from backend.vault import CredentialInput

PROVIDERS={
 'google_drive':{'name':'Google Drive','authorize':'https://accounts.google.com/o/oauth2/v2/auth','token':'https://oauth2.googleapis.com/token','scopes':['https://www.googleapis.com/auth/drive.readonly'],'console':'https://console.cloud.google.com/auth/clients','tools':['drive_files','drive_text']},
 'slack':{'name':'Slack','authorize':'https://slack.com/oauth/v2/authorize','token':'https://slack.com/api/oauth.v2.access','scopes':['channels:read','channels:history'],'console':'https://api.slack.com/apps','tools':['slack_channels','slack_history']},
 'shopify':{'name':'Shopify','scopes':['read_products','read_orders'],'console':'https://dev.shopify.com/dashboard','tools':['shopify_products','shopify_orders']},
}
def now():return datetime.now(timezone.utc)
def shop_domain(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,61}[a-z0-9]\.myshopify\.com|[a-z0-9]\.myshopify\.com',value):raise HTTPException(422,'Enter your store hostname, for example mystore.myshopify.com')
    return value

def settings(provider):
    if provider not in PROVIDERS:raise HTTPException(404,'Unknown account connector')
    try:origin=public_origin(os.getenv('PUBLIC_ORIGIN','http://localhost:3000'),os.getenv('COOKIE_SECURE')=='1')
    except ValueError as e:raise HTTPException(503,str(e))
    if session_cookie_name().startswith(('__Host-','__Secure-')) and os.getenv('COOKIE_SECURE')!='1':raise HTTPException(503,'Prefixed session cookies require COOKIE_SECURE=1')
    prefix='OAUTH_'+provider.upper()
    return {**PROVIDERS[provider],'client_id':os.getenv(prefix+'_CLIENT_ID',''),'client_secret':os.getenv(prefix+'_CLIENT_SECRET',''),'redirect_uri':origin+'/api/integrations/'+provider+'/callback'}

def cookie_name(provider):return session_cookie_name()+'_cx_'+provider

def cookie_path():return '/' if session_cookie_name().startswith('__Host-') else '/api/integrations'

def valid_token(value):
    if not isinstance(value,str) or not 8<=len(value)<=6000 or any(c in value for c in ('\r','\n')):raise ValueError('Invalid credential envelope')
    return value

def shopify_signature(request,secret,expected_shop):
    pairs=list(request.query_params.multi_items())
    if len({k for k,v in pairs})!=len(pairs) or request.query_params.get('shop')!=expected_shop:raise ValueError('Shop callback mismatch')
    supplied=request.query_params.get('hmac','')
    message=urlencode(sorted((k,v) for k,v in pairs if k not in ('hmac','signature')))
    expected=hmac.new(secret.encode(),message.encode(),hashlib.sha256).hexdigest()
    if not re.fullmatch('[0-9a-f]{64}',supplied) or not hmac.compare_digest(expected,supplied):raise ValueError('Shop callback signature invalid')
    stamp=int(request.query_params.get('timestamp','0'))
    if abs(now().timestamp()-stamp)>600:raise ValueError('Shop callback expired')

async def verified_identity(client,provider,token,shop=None):
    headers={'Authorization':'Bearer '+token}
    if provider=='google_drive':
        data=await provider_json(client,'GET','https://www.googleapis.com/drive/v3/about',headers=headers,params={'fields':'user(permissionId,displayName)'})
        user=data.get('user',{});subject=user.get('permissionId');label=user.get('displayName')
    elif provider=='slack':
        data=await provider_json(client,'POST','https://slack.com/api/auth.test',headers=headers)
        if data.get('ok') is not True or not data.get('bot_id'):raise ValueError('Slack bot identity unavailable')
        subject=data.get('team_id');label=data.get('team')
    else:
        from backend.business_mcp import shopify_query
        data=await shopify_query(client,shop,token,'{ shop { id name myshopifyDomain } }')
        user=data['shop'];subject=user.get('id');label=user.get('name')
        if user.get('myshopifyDomain')!=shop:raise ValueError('Shop identity mismatch')
    if not isinstance(subject,str) or not subject or len(subject)>200 or not isinstance(label,str) or not label:raise ValueError('Provider identity unavailable')
    return subject,label[:100]

class ConnectInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    shop:str|None=Field(default=None,max_length=100)

class BusinessConnectors:
    def __init__(self,s):self.s=s
    def row(self,owner,provider):return next((r for r in self.s['listing'](owner,'integration_connection') if r['provider']==provider),None)
    def require(self,owner,external=True):
        p=self.s['POLICY'].require(owner,'manage_registry');self.s['POLICY'].require(owner,'manage_vault')
        if not p.account:raise HTTPException(403,'Sign in with a private account before authorizing')
        if external and not self.s['POLICY'].settings(owner)['allow_external_processing']:raise HTTPException(403,'External processing is disabled')
        return p
    def register(self,owner,row,server):
        existing=self.s['listing'](owner,'registered_tool')
        for tool in server['tools']:
            if tool['name'] not in PROVIDERS[row['provider']]['tools']:continue
            prior=next((r for r in existing if r['name']==tool['name']),None)
            if prior and prior.get('server_id')!=server['id']:continue
            self.s['save'](owner,'registered_tool',{'name':tool['name'],'description':tool['description'],'adapter':'mcp','builtin':None,'server_id':server['id'],'remote_tool':tool['name'],'capabilities':['business.evidence.read'],'entities':['business_evidence'],'enabled':True},prior['id'] if prior else None)
    async def access_token(self,owner,server):
        """Called only by the existing MCP transport; never returns tokens to browsers."""
        row=self.row(owner,server['profile'])
        if not row or row['state']=='disconnected' or row['server_id']!=server['id']:raise HTTPException(409,'Reconnect this provider')
        clear=self.s['VAULT'].reveal_for_service(owner,server['credential_id'],'mcp')
        bundle=json.loads(clear);token=valid_token(bundle['access_token'])
        if row.get('expires_at') and datetime.fromisoformat(row['expires_at'])<now()+timedelta(seconds=60):
            self.s['POLICY'].require(owner,'read')
            if row['provider']!='google_drive' or not bundle.get('refresh_token'):raise HTTPException(409,'Authorization expired; reconnect this provider')
            config=settings('google_drive')
            try:
                async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
                    result=await provider_json(client,'POST',config['token'],data={'grant_type':'refresh_token','client_id':config['client_id'],'client_secret':config['client_secret'],'refresh_token':bundle['refresh_token']})
                token=valid_token(result.get('access_token'));ttl=int(result.get('expires_in',0))
                if result.get('scope') is not None and not set(config['scopes']).issubset(set(re.split(r'[,\s]+',result['scope']))):raise ValueError('Read permission was revoked')
                if result.get('refresh_token'):bundle['refresh_token']=valid_token(result['refresh_token'])
                if not 60<=ttl<=86400:raise ValueError('Invalid expiry')
                bundle['access_token']=token
                # Renew only the existing administrator-approved grant. Readers do
                # not gain a vault write API; the original installer must retain
                # registry/vault authority, and version checks prevent revival.
                with self.s['conn']() as c:member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(row['actor'],owner)).fetchone()
                if not member or member['role'] not in ('owner','admin'):raise HTTPException(409,'The account installer must reconnect this provider')
                grant_actor=ACTOR.set(Principal(owner,row['actor'],member['role']))
                try:self.s['VAULT'].rotate_for_service(owner,server['credential_id'],json.dumps(bundle),server['credential_version'])
                finally:ACTOR.reset(grant_actor)
                with self.s['conn']() as c:
                    c.execute("UPDATE records SET body=body || %s::jsonb WHERE owner=%s AND id=%s AND kind='integration_connection' AND body->>'state'!='disconnected' AND body->>'updated_at'=%s",(json.dumps({'expires_at':(now()+timedelta(seconds=ttl)).isoformat()}),owner,row['id'],row['updated_at']))
            except HTTPException:raise
            except Exception:raise HTTPException(409,'Google Drive renewal failed; reconnect your account')
        return token
    def begin(self,provider,body,request,owner):
        p=self.require(owner);config=settings(provider)
        if not config['client_id'] or not config['client_secret']:raise HTTPException(503,'Provider app setup is required in Render. Open Setup for the exact variables and redirect URL.')
        shop=shop_domain(body.shop) if provider=='shopify' else None
        if body.shop and not shop:raise HTTPException(422,'Store hostname is only used for Shopify')
        self.s['VAULT'].cipher()
        state=secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        with self.s['conn']() as c:
            c.execute("DELETE FROM records WHERE kind='connector_oauth_state' AND body->>'expires'<%s",(now().isoformat(),))
            if c.execute("SELECT count(*) n FROM records WHERE owner=%s AND kind='connector_oauth_state'",(owner,)).fetchone()['n']>=5:raise HTTPException(429,'Finish a pending authorization or wait ten minutes')
            c.execute("INSERT INTO records(id,owner,kind,body) VALUES(%s,%s,'connector_oauth_state',%s)",('connector-state:'+digest(state),owner,json.dumps({'provider':provider,'actor':p.account,'session_digest':digest(request.cookies.get(session_cookie_name(),'')),'browser_digest':digest(browser),'verifier':verifier,'expires':(now()+timedelta(minutes=10)).isoformat(),'config_digest':fingerprint(config),'shop':shop})))
        params={'client_id':config['client_id'],'redirect_uri':config['redirect_uri'],'scope':','.join(config['scopes']) if provider!='google_drive' else ' '.join(config['scopes']),'state':state}
        if provider=='google_drive':params.update(response_type='code',access_type='offline',prompt='consent',code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(),code_challenge_method='S256')
        url=('https://'+shop+'/admin/oauth/authorize' if shop else config['authorize'])+'?'+urlencode(params)
        response=JSONResponse({'authorize_url':url},headers={'Cache-Control':'no-store'});response.set_cookie(cookie_name(provider),browser,httponly=True,secure=os.getenv('COOKIE_SECURE')=='1',samesite='lax',max_age=600,path=cookie_path());return response
    async def callback(self,provider,request):
        config=settings(provider);s=self.s;state=request.query_params.get('state','')
        if len(request.query_params)!=len(list(request.query_params.multi_items())) or len(state)>200 or len(request.query_params.get('code',''))>4096:raise HTTPException(400,'Invalid authorization response')
        with s['conn']() as c:row=c.execute("DELETE FROM records WHERE id=%s AND kind='connector_oauth_state' AND body->>'provider'=%s RETURNING owner,body",('connector-state:'+digest(state),provider)).fetchone()
        if not row:raise HTTPException(400,'Authorization expired or already consumed. Start again from Connections.')
        owner,data=row['owner'],row['body']
        if datetime.fromisoformat(data['expires'])<now() or not secrets.compare_digest(data['browser_digest'],digest(request.cookies.get(cookie_name(provider),''))) or not secrets.compare_digest(data['config_digest'],fingerprint(config)):raise HTTPException(400,'Authorization changed, expired or belongs to another browser')
        # The Strict session cookie is intentionally absent on cross-site returns.
        # The Lax, HttpOnly provider cookie binds the browser; the initiating
        # session and membership are independently checked in PostgreSQL below.
        current_session=request.cookies.get(session_cookie_name())
        if current_session and digest(current_session)!=data['session_digest']:raise HTTPException(403,'Use the same signed-in browser to finish authorization')
        with s['conn']() as c:
            member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(data['actor'],owner)).fetchone()
            active=c.execute('SELECT account_id FROM account_sessions WHERE digest=%s AND account_id=%s AND organization_id=%s AND expires>now()',(data['session_digest'],data['actor'],owner)).fetchone()
        if not member or not active:raise HTTPException(403,'The initiating session or membership was revoked')
        actor=ACTOR.set(Principal(owner,data['actor'],member['role']))
        try:
            self.require(owner)
            if request.query_params.get('error') or not request.query_params.get('code'):raise HTTPException(400,'Authorization was cancelled. Start again from Connections.')
            try:
                if provider=='shopify':shopify_signature(request,config['client_secret'],data['shop'])
                async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
                    fields={'client_id':config['client_id'],'client_secret':config['client_secret'],'code':request.query_params['code'],'redirect_uri':config['redirect_uri']}
                    if provider=='google_drive':fields.update(grant_type='authorization_code',code_verifier=data['verifier'])
                    endpoint='https://'+data['shop']+'/admin/oauth/access_token' if provider=='shopify' else config['token']
                    result=await provider_json(client,'POST',endpoint,**({'json':fields} if provider=='shopify' else {'data':fields}))
                    if provider=='slack' and result.get('ok') is not True:raise ValueError('Slack exchange failed')
                    token=valid_token(result.get('access_token'))
                    granted=set(re.split(r'[,\s]+',result.get('scope','')))
                    if not set(config['scopes']).issubset(granted):raise ValueError('Required read permissions missing')
                    subject,label=await verified_identity(client,provider,token,data['shop'])
                    if provider=='slack' and result.get('team',{}).get('id')!=subject:raise ValueError('Workspace identity mismatch')
                ttl=int(result.get('expires_in',0));expires=(now()+timedelta(seconds=ttl)).isoformat() if ttl>0 else None
                if provider=='google_drive' and not 60<=ttl<=86400:raise ValueError('Missing Drive expiry')
                bundle={'access_token':token}
                if provider=='google_drive' and result.get('refresh_token'):bundle['refresh_token']=valid_token(result['refresh_token'])
                if len(json.dumps(bundle))>8192:raise ValueError('Credential exceeds vault limit')
            except Exception:raise HTTPException(502,'Provider token exchange, read permissions or account verification failed. Check app setup, then reconnect. No account was marked connected.')
            prior=self.row(owner,provider)
            credential=s['VAULT'].put(owner,CredentialInput(name=config['name']+' OAuth grant',provider='mcp',value=json.dumps(bundle)),prior.get('credential_id') if prior else None)
            server=s['save'](owner,'mcp_server',{'name':config['name']+' · authorized read-only','transport':'stdio','profile':provider,'url':None,'auth_env':None,'credential_id':credential['id'],'enabled':True,'risk':'read','timeout_seconds':25,'status':'registered','tools':[],'shop':data['shop']},prior.get('server_id') if prior else None)
            connection=s['save'](owner,'integration_connection',{'provider':provider,'actor':data['actor'],'login':label,'subject':subject,'credential_id':credential['id'],'server_id':server['id'],'state':'needs_test','scopes':config['scopes'],'shop':data['shop'],'expires_at':expires,'last_success_at':None,'updated_at':now().isoformat()},prior['id'] if prior else None)
            checked=await s['MCP_REGISTRY'].probe(owner,server['id'])
            if checked['status']=='healthy':
                connection.update(state='connected',last_success_at=now().isoformat());s['save'](owner,'integration_connection',{k:v for k,v in connection.items() if k!='id'},connection['id']);self.register(owner,connection,checked)
            s['save'](owner,'audit',{'actor':data['actor'],'action':'connector.authorized','provider':provider,'state':connection['state'],'at':now().isoformat()})
        finally:ACTOR.reset(actor)
        response=RedirectResponse('/integrations?connection='+provider,status_code=303,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'});response.delete_cookie(cookie_name(provider),path=cookie_path());return response
    def install(self,app,auth):
        s=self.s;s['MCP_REGISTRY'].business_connectors=self
        @app.get('/api/integrations/business-connections')
        def status(owner=Depends(auth)):
            s['POLICY'].require(owner,'read');result={}
            for provider in PROVIDERS:
                config=settings(provider);row=self.row(owner,provider)
                if row and row['state']!='disconnected':
                    try:
                        server=s['MCP_REGISTRY'].server(owner,row['server_id'])
                        state='stale' if not row.get('last_success_at') or now()-datetime.fromisoformat(row['last_success_at'])>timedelta(minutes=5) else row['state']
                        if server['status']!='healthy':state='needs_test'
                        if row.get('expires_at') and datetime.fromisoformat(row['expires_at'])<now():state='renewal_required' if provider=='google_drive' else 'needs_authorization'
                        if not s['POLICY'].settings(owner)['allow_external_processing']:state='policy_blocked'
                        row={**row,'state':state}
                    except HTTPException:row={**row,'state':'needs_authorization'}
                result[provider]={'name':config['name'],'configured':bool(config['client_id'] and config['client_secret']),'connection':({k:v for k,v in row.items() if k not in ('credential_id',)} if row else None),'setup':{'console_url':config['console'],'callback_url':config['redirect_uri'],'variables':['OAUTH_'+provider.upper()+'_CLIENT_ID','OAUTH_'+provider.upper()+'_CLIENT_SECRET'],'scopes':config['scopes']}}
            return result
        @app.post('/api/integrations/{provider}/authorize')
        def authorize(provider:str,body:ConnectInput,request:Request,owner=Depends(auth)):return self.begin(provider,body,request,owner)
        @app.get('/api/integrations/{provider}/callback')
        async def callback(provider:str,request:Request):
            try:return await self.callback(provider,request)
            except HTTPException as e:
                if 'text/html' not in request.headers.get('accept',''):raise
                from html import escape
                return HTMLResponse('<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Connection needs attention</title><main><h1>Connection needs attention</h1><p>'+escape(str(e.detail))+'</p><a href="/integrations">Return to Connections and try again</a></main></html>',status_code=e.status_code,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
        @app.post('/api/integrations/{provider}/test')
        async def test(provider:str,owner=Depends(auth)):
            self.require(owner);settings(provider);row=self.row(owner,provider)
            if not row or row['state']=='disconnected':raise HTTPException(409,'Authorize this provider first')
            server=s['MCP_REGISTRY'].server(owner,row['server_id'])
            token=await self.access_token(owner,server)
            try:
                async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:subject,label=await verified_identity(client,provider,token,row.get('shop'))
                if subject!=row['subject']:raise ValueError('Account changed')
            except Exception:raise HTTPException(409,'Account verification failed; reconnect this provider')
            checked=await s['MCP_REGISTRY'].probe(owner,server['id'])
            # Preserve a renewal performed during this test.
            row=self.row(owner,provider);row.update(state='connected' if checked['status']=='healthy' else 'needs_test',last_checked_at=now().isoformat())
            if row['state']=='connected':row['last_success_at']=now().isoformat();self.register(owner,row,checked)
            s['save'](owner,'integration_connection',{k:v for k,v in row.items() if k!='id'},row['id'])
            return {'state':row['state'],'tools':len(checked['tools'])}
        @app.delete('/api/integrations/{provider}')
        def disconnect(provider:str,owner=Depends(auth)):
            self.require(owner,external=False);settings(provider);row=self.row(owner,provider)
            if not row:raise HTTPException(404,'Connection not found')
            with s['conn']() as c:
                c.execute("UPDATE records SET body=(body-'ciphertext') || '{\"enabled\":false}'::jsonb WHERE owner=%s AND id=%s AND kind='vault_secret'",(owner,row['credential_id']))
                c.execute("UPDATE records SET body=body || '{\"enabled\":false,\"status\":\"disabled\"}'::jsonb WHERE owner=%s AND id=%s AND kind='mcp_server'",(owner,row['server_id']))
                c.execute("UPDATE records SET body=body || '{\"enabled\":false}'::jsonb WHERE owner=%s AND kind='registered_tool' AND body->>'server_id'=%s",(owner,row['server_id']))
                c.execute("UPDATE records SET body=body || '{\"state\":\"disconnected\"}'::jsonb WHERE owner=%s AND id=%s",(owner,row['id']))
            return {'disconnected':True,'provider_authorization':'Local credentials erased and tools disabled. You can also revoke the app in provider settings.'}
