"""Instagram Login authorization into existing scoped social sources and encrypted vault.
No login identity linking or publication; provider calls require live acceptance.
"""
import asyncio,html,json,logging,os,re,secrets
from httpx import URL
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
import httpx
from fastapi import Depends,HTTPException,Request
from fastapi.responses import JSONResponse,RedirectResponse,HTMLResponse
from pydantic import BaseModel,ConfigDict
from backend.oauth import digest,provider_json
from backend.oauth_config import public_origin,fingerprint
from backend.identity import session_cookie_name
from backend.policy import ACTOR,Principal
from backend.social_growth import Native
from backend.vault import CredentialInput


class RedactTokenURLs(logging.Filter):
    """Meta requires GET parameters for token exchange/refresh. Never log their query."""
    def filter(self,record):
        if isinstance(record.args,tuple):
            record.args=tuple(str(a.copy_with(query=b'')) if isinstance(a,URL) and a.host=='graph.instagram.com' and a.path in ('/access_token','/refresh_access_token') else a for a in record.args)
        return True
logging.getLogger('httpx').addFilter(RedactTokenURLs())

def token_response(value):
    token=value.get('access_token');ttl=value.get('expires_in')
    if not isinstance(token,str) or not 8<=len(token)<=8192 or any(c in token for c in ('\r','\n')) or type(ttl) is not int or not 86400<ttl<=60*86400:raise ValueError('Invalid long-lived token response')
    return token,ttl

def api_version():
    version=os.getenv('EVOLVYN_META_API_VERSION','v23.0')
    if not re.fullmatch(r'v\d{2}\.0',version):raise HTTPException(503,'Invalid configured Meta API version')
    return version

def configuration():
    try:origin=public_origin(os.getenv('PUBLIC_ORIGIN','http://localhost:3000'),os.getenv('COOKIE_SECURE')=='1')
    except ValueError as error:raise HTTPException(503,str(error))
    if session_cookie_name().startswith(('__Host-','__Secure-')) and os.getenv('COOKIE_SECURE')!='1':raise HTTPException(503,'Secure cookies require HTTPS configuration')
    return {'client_id':os.getenv('OAUTH_INSTAGRAM_CLIENT_ID',''),'client_secret':os.getenv('OAUTH_INSTAGRAM_CLIENT_SECRET',''),'redirect_uri':origin+'/api/integrations/instagram/callback'}
def cookie_name():return session_cookie_name()+'_instagram'
def cookie_path():return '/' if cookie_name().startswith('__Host-') else '/api/integrations/instagram'
def stamp():return datetime.now(timezone.utc)
class Start(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str
    read_comments:bool=False

class InstagramOAuth:
    def __init__(self,s,growth):self.s=s;self.growth=growth
    def authorize_scope(self,owner,conversation_id):
        s=self.s;p=s['POLICY'].require(owner,'manage_registry');s['POLICY'].require(owner,'manage_vault')
        if not p.account:raise HTTPException(403,'Sign in to your private workspace before connecting Instagram')
        conv=s['get'](owner,conversation_id,'conversation');s['POLICY'].data(owner,conv,'mcp')
        return p
    def validate_session(self,owner,data):
        with self.s['conn']() as c:
            member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(data['actor'],owner)).fetchone()
            active=c.execute('SELECT account_id FROM account_sessions WHERE digest=%s AND account_id=%s AND expires>now()',(data['session_digest'],data['actor'])).fetchone()
        if not member or not active:raise HTTPException(403,'Initiating session or membership was revoked; start again')
        return Principal(owner,data['actor'],member['role'])
    async def finish(self,request,state,code,error):
        s=self.s
        if not state or len(state)>200:raise HTTPException(400,'Invalid authorization state')
        with s['conn']() as c:row=c.execute("DELETE FROM records WHERE id=%s AND kind='connector_oauth_state' AND body->>'provider'='instagram' RETURNING owner,body",('connector-state:'+digest(state),)).fetchone()
        if not row:raise HTTPException(400,'Authorization expired or already consumed; start again')
        owner,data=row['owner'],row['body'];settings=configuration()
        if datetime.fromisoformat(data['expires'])<stamp() or not secrets.compare_digest(data['browser_digest'],digest(request.cookies.get(cookie_name(),''))):raise HTTPException(400,'Authorization belongs to another browser or expired')
        if not secrets.compare_digest(data['config_digest'],fingerprint(settings)):raise HTTPException(400,'Instagram application configuration changed; restart authorization')
        actor=ACTOR.set(self.validate_session(owner,data))
        credential_id=None
        try:
            self.authorize_scope(owner,data['conversation_id'])
            if error:raise HTTPException(400,'Instagram authorization was declined; no account connected')
            if not code or len(code)>8192:raise HTTPException(400,'Missing or invalid authorization code')
            version=api_version()
            try:
                issued_at=stamp()
                async with asyncio.timeout(30),httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
                    result=await provider_json(client,'POST','https://api.instagram.com/oauth/access_token',data={'client_id':settings['client_id'],'client_secret':settings['client_secret'],'grant_type':'authorization_code','redirect_uri':settings['redirect_uri'],'code':code})
                    token=result.get('access_token');subject=str(result.get('user_id',''))
                    if not isinstance(token,str) or not 8<=len(token)<=8192 or any(x in token for x in ('\r','\n')) or not re.fullmatch(r'\d{1,100}',subject):raise ValueError('Invalid token response')
                    exchanged=await provider_json(client,'GET','https://graph.instagram.com/access_token',params={'grant_type':'ig_exchange_token','client_secret':settings['client_secret'],'access_token':token})
                    token,ttl=token_response(exchanged)
                    profile=await provider_json(client,'GET','https://graph.instagram.com/'+version+'/me',params={'fields':'user_id,username'},headers={'Authorization':'Bearer '+token})
                    if str(profile.get('user_id'))!=subject or not isinstance(profile.get('username'),str) or not re.fullmatch(r'[A-Za-z0-9._]{1,30}',profile['username']) or token in json.dumps(profile):raise ValueError('Instagram account verification failed')
                    expires_at=(issued_at+timedelta(seconds=ttl)).isoformat()
            except Exception:raise HTTPException(502,'Instagram token exchange or account verification failed. Check the Meta app, account eligibility, redirect URI and permissions. No connection was marked verified.') from None
            # Revalidate after the external call; neither logout nor a policy change grants a connection.
            self.validate_session(owner,data);self.authorize_scope(owner,data['conversation_id'])
            prior=next((r for r in s['listing'](owner,'social_source') if r.get('oauth_provider')=='instagram' and r['conversation']==data['conversation_id'] and r['account_id']==subject),None)
            prior_credential=None
            if prior:prior_credential=s['get'](owner,prior['managed_server_id'],'mcp_server').get('credential_id')
            credential=s['VAULT'].put(owner,CredentialInput(name='Instagram authorized · '+profile['username'][:65],provider='mcp',value=token),prior_credential)
            credential_id=credential['id']
            if prior:
                server=s['get'](owner,prior['managed_server_id'],'mcp_server');server.update(enabled=True,status='registered')
                s['save'](owner,'mcp_server',{k:v for k,v in server.items() if k!='id'},server['id'])
                checked=await s['MCP_REGISTRY'].probe(owner,server['id'])
                if checked['status']!='healthy':raise HTTPException(502,'Instagram MCP discovery failed; retry the connection')
                tool=s['get'](owner,prior['managed_tool_id'],'registered_tool');tool['enabled']=True
                s['save'](owner,'registered_tool',{k:v for k,v in tool.items() if k!='id'},tool['id'])
                source={**prior,'enabled':True,'oauth_expires_at':expires_at}
                source['config_binding']=self.growth.binding(owner,source)
            else:
                source=await self.growth.create_native(owner,Native(conversation_id=data['conversation_id'],profile='instagram_login_social',credential_id=credential_id,account_id=subject,name='Instagram · '+profile['username'][:70]))
            self.validate_session(owner,data);self.authorize_scope(owner,data['conversation_id'])
            source.update(oauth_actor=data['actor'],oauth_refresh_after=(stamp()+timedelta(days=1)).isoformat(),oauth_refresh_error=None,oauth_provider='instagram',oauth_expires_at=expires_at,oauth_authorized_at=stamp().isoformat(),oauth_requested_scopes=data['scopes'])
            s['save'](owner,'social_source',{k:v for k,v in source.items() if k!='id'},source['id'])
            s['save'](owner,'audit',{'actor':data['actor'],'action':'connector.authorized','provider':'instagram','source_id':source['id'],'at':stamp().isoformat()})
        except BaseException:
            if credential_id:
                # Never leave a usable newly-issued token after a failed local connection.
                with s['conn']() as c:c.execute("UPDATE records SET body=(body-'ciphertext') || '{\"enabled\":false}'::jsonb WHERE owner=%s AND id=%s AND kind='vault_secret'",(owner,credential_id))
            raise
        finally:ACTOR.reset(actor)
        return RedirectResponse('/growth?'+urlencode({'conversation':data['conversation_id'],'social':'connected'}),status_code=303)
    async def refresh(self,owner,id):
        s=self.s;source=self.growth.scope(owner,id,True)
        self.authorize_scope(owner,source['conversation'])
        if not source['enabled'] or source.get('oauth_provider')!='instagram':raise HTTPException(409,'Active Instagram OAuth source required')
        if self.growth.binding(owner,source)!=source['config_binding']:raise HTTPException(409,'Authorization changed; reconnect Instagram')
        if stamp()-datetime.fromisoformat(source['oauth_authorized_at'])<timedelta(days=1):raise HTTPException(409,'Meta tokens can only be refreshed after they are at least 24 hours old')
        server=s['MCP_REGISTRY'].server(owner,source['managed_server_id']);credential_id=server['credential_id'];version=server['credential_version']
        token=s['VAULT'].reveal_for_service(owner,credential_id,'mcp');issued_at=stamp()
        try:
            async with asyncio.timeout(25),httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
                result=await provider_json(client,'GET','https://graph.instagram.com/refresh_access_token',params={'grant_type':'ig_refresh_token','access_token':token})
                refreshed,ttl=token_response(result)
                profile=await provider_json(client,'GET','https://graph.instagram.com/'+api_version()+'/me',params={'fields':'user_id'},headers={'Authorization':'Bearer '+refreshed})
                if str(profile.get('user_id'))!=source['account_id']:raise ValueError('Account changed')
        except Exception:raise HTTPException(502,'Instagram renewal failed. Check app access or reconnect the account; no renewal was recorded.') from None
        self.authorize_scope(owner,source['conversation'])
        # Expected version + enabled check prevents refresh from resurrecting a revoked credential.
        s['VAULT'].rotate_for_service(owner,credential_id,refreshed,version)
        with s['conn']() as c:
            current=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s FOR UPDATE",(owner,id)).fetchone()['body']
            if not current['enabled'] or current.get('oauth_authorized_at')!=source['oauth_authorized_at']:raise HTTPException(409,'Authorization changed during renewal; reconnect')
            current.update(oauth_expires_at=(issued_at+timedelta(seconds=ttl)).isoformat(),oauth_authorized_at=issued_at.isoformat(),oauth_refresh_after=(issued_at+timedelta(days=1)).isoformat(),oauth_refresh_error=None)
            current['config_binding']=self.growth.binding(owner,current)
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(current),owner,id))
        return {'renewed':True,'expires_at':current['oauth_expires_at']}
    async def refresh_tick(self):
        s=self.s
        # Claim at most one due grant and persist cooldown before any network call.
        with s['conn']() as c:
            row=c.execute("SELECT owner,id,body FROM records WHERE kind='social_source' AND body->>'enabled'='true' AND body->>'oauth_provider'='instagram' AND (body->>'oauth_expires_at')::timestamptz<now()+interval '7 days' AND (body->>'oauth_expires_at')::timestamptz>now() AND (body->>'oauth_refresh_after')::timestamptz<=now() ORDER BY created LIMIT 1 FOR UPDATE SKIP LOCKED").fetchone()
            if not row:return
            c.execute("UPDATE records SET body=body || %s::jsonb WHERE id=%s",(json.dumps({'oauth_refresh_after':(stamp()+timedelta(hours=6)).isoformat()}),row['id']))
        with s['conn']() as c:member=c.execute('SELECT role FROM memberships WHERE organization_id=%s AND account_id=%s',(row['owner'],row['body'].get('oauth_actor'))).fetchone()
        actor=ACTOR.set(Principal(row['owner'],row['body'].get('oauth_actor'),member['role'] if member else 'viewer'))
        try:await self.refresh(row['owner'],row['id'])
        except Exception:
            with s['conn']() as c:c.execute("UPDATE records SET body=body || %s::jsonb WHERE owner=%s AND id=%s",(json.dumps({'oauth_refresh_error':'Instagram renewal unavailable; reconnect before authorization expires.'}),row['owner'],row['id']))
        finally:ACTOR.reset(actor)
    def install(self,app,auth):
        s=self.s
        @app.get('/api/integrations/instagram')
        def status(owner=Depends(auth)):
            s['POLICY'].require(owner,'read');config=configuration();admin=s['POLICY'].principal(owner).role in ('owner','admin')
            return {'configured':bool(config['client_id'] and config['client_secret']),'callback_url':config['redirect_uri'],'setup':({'variables':['OAUTH_INSTAGRAM_CLIENT_ID','OAUTH_INSTAGRAM_CLIENT_SECRET'],'instructions':'Configure Instagram API with Instagram Login in your Meta application. Save its Instagram App ID/secret privately in Render, register this exact redirect URI, and enable the app for approved accounts. App review/advanced access is required for other businesses.'} if admin else None),'token_lifecycle':'Long-lived token expiry is saved after provider exchange. The running backend attempts renewal within seven days of expiry. Revoked/expired grants require reconnecting; a sleeping backend cannot guarantee renewal.'}
        @app.post('/api/integrations/instagram/authorize')
        def authorize(body:Start,request:Request,owner=Depends(auth)):
            p=self.authorize_scope(owner,body.conversation_id);settings=configuration()
            if not settings['client_id'] or not settings['client_secret']:raise HTTPException(503,'The Evolvyn administrator must configure the Instagram application in Render first')
            state='ig_'+secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32);scopes=['instagram_business_basic']+(['instagram_business_manage_comments'] if body.read_comments else [])
            with s['conn']() as c:
                c.execute("DELETE FROM records WHERE kind='connector_oauth_state' AND body->>'expires'<%s",(stamp().isoformat(),))
                count=c.execute("SELECT count(*) AS n FROM records WHERE owner=%s AND kind='connector_oauth_state'",(owner,)).fetchone()['n']
                if count>=5:raise HTTPException(429,'Finish an authorization or wait ten minutes')
                c.execute("INSERT INTO records(id,owner,kind,body) VALUES(%s,%s,'connector_oauth_state',%s)",('connector-state:'+digest(state),owner,json.dumps({'provider':'instagram','actor':p.account,'conversation_id':body.conversation_id,'session_digest':digest(request.cookies.get(session_cookie_name(),'')),'browser_digest':digest(browser),'expires':(stamp()+timedelta(minutes=10)).isoformat(),'config_digest':fingerprint(settings),'scopes':scopes})))
            url='https://www.instagram.com/oauth/authorize?'+urlencode({'client_id':settings['client_id'],'redirect_uri':settings['redirect_uri'],'response_type':'code','scope':','.join(scopes),'state':state,'enable_fb_login':'0'})
            response=JSONResponse({'authorize_url':url},headers={'Cache-Control':'no-store'});response.set_cookie(cookie_name(),browser,httponly=True,secure=os.getenv('COOKIE_SECURE')=='1',samesite='lax',max_age=600,path=cookie_path());return response
        @app.post('/api/integrations/instagram/{id}/refresh')
        async def refresh(id:str,owner=Depends(auth)):return await self.refresh(owner,id)
        @app.get('/api/integrations/instagram/callback')
        async def callback(request:Request,state:str='',code:str='',error:str=''):
            try:response=await self.finish(request,state,code,error)
            except HTTPException as failure:
                if 'text/html' not in request.headers.get('accept',''):raise
                response=HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evolvyn Instagram connection</title><h1>Instagram connection needs attention</h1><p>'+html.escape(str(failure.detail))+'</p><a href="/growth?social=retry">Return to Growth Insights and try again</a>',status_code=failure.status_code)
            response.delete_cookie(cookie_name(),path=cookie_path());response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer';return response
