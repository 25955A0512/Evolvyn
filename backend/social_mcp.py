"""Read-only official social APIs behind trusted MCP. No provider credentials in arguments."""
import asyncio,os,re
from datetime import datetime,timezone
import httpx
from mcp.server.fastmcp import FastMCP
from backend.social_contract import Observation
from backend.instagram_identity import verify_bound_profile
server=FastMCP('Evolvyn authorized social observations')

def stamp(value):return str(value).replace('Z','+00:00')
async def observe(provider,account_id,token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',account_id):raise ValueError('Invalid account ID')
    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    async with asyncio.timeout(24),httpx.AsyncClient(timeout=7,follow_redirects=False) as c:
        async def get(host,path,params):
            chunks=[];size=0
            async with c.stream('GET',host+path,params=params,headers=headers) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes():
                    size+=len(chunk)
                    if size>200000:raise ValueError('Provider response exceeds budget')
                    chunks.append(chunk)
            import json
            value=json.loads(b''.join(chunks))
            if not isinstance(value,dict):raise ValueError('Invalid provider response')
            return value
        if provider in ('instagram','instagram_login'):
            host='https://graph.instagram.com' if provider=='instagram_login' else 'https://graph.facebook.com';version=os.getenv('EVOLVYN_META_API_VERSION','v23.0')
            if not re.fullmatch(r'v\d{2}\.0',version):raise ValueError('Invalid Meta API version')
            profile=await get(host,f'/{version}/{account_id}',{'fields':'id,user_id,username,followers_count' if provider=='instagram_login' else 'id,username,followers_count'})
            if provider=='instagram_login':verify_bound_profile(profile,account_id)
            elif str(profile.get('id'))!=account_id:raise ValueError('Authorized account mismatch')
            comment_status='Permitted comment sample collected where available.'
            try:media=await get(host,f'/{version}/{account_id}/media',{'fields':'id,caption,timestamp,like_count,comments_count,permalink,comments.limit(10){id,text,timestamp}','limit':25})
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in (400,403):raise
                media=await get(host,f'/{version}/{account_id}/media',{'fields':'id,caption,timestamp,like_count,comments_count,permalink','limit':25})
                comment_status='Comment-text request was rejected; only supported post counters collected.'
            if not isinstance(media.get('data'),list):raise ValueError('Invalid media list')
            posts=[];comments=[]
            for p in media.get('data',[])[:25]:
                posts.append({'id':p['id'],'published_at':stamp(p['timestamp']),'url':p['permalink'],'text':str(p.get('caption',''))[:1000],'likes':p.get('like_count'),'comments':p.get('comments_count')})
                for x in p.get('comments',{}).get('data',[]):
                    if len(comments)<20:comments.append({'id':x['id'],'text':str(x.get('text',''))[:1000],'published_at':stamp(x['timestamp'])})
            value={'provider':'instagram','account_id':account_id,'account_name':profile.get('username',account_id),'followers':profile.get('followers_count'),'posts':posts,'comment_sample':comments,'coverage':'Latest up to 25 returned professional-account posts and up to 20 permitted comments. Lifetime counters, not period activity. Views/reach/shares/saves are not collected. Meta permissions/app review required. '+comment_status}
        elif provider=='youtube':
            host='https://www.googleapis.com/youtube/v3'
            data=await get(host,'/channels',{'part':'snippet,statistics,contentDetails','mine':'true','maxResults':1})
            profiles=data.get('items',[])
            if len(profiles)!=1 or profiles[0].get('id')!=account_id:raise ValueError('OAuth channel does not match the selected account')
            p=profiles[0];playlist=p['contentDetails']['relatedPlaylists']['uploads']
            uploads=await get(host,'/playlistItems',{'part':'contentDetails','playlistId':playlist,'maxResults':25})
            ids=','.join(x['contentDetails']['videoId'] for x in uploads.get('items',[]))
            videos=await get(host,'/videos',{'part':'snippet,statistics','id':ids,'maxResults':25}) if ids else {'items':[]}
            posts=[]
            for x in videos.get('items',[]):
                stats=x.get('statistics',{})
                posts.append({'id':x['id'],'published_at':stamp(x['snippet']['publishedAt']),'url':'https://www.youtube.com/watch?v='+x['id'],'text':str(x['snippet'].get('title',''))[:1000],'likes':int(stats['likeCount']) if 'likeCount' in stats else None,'comments':int(stats['commentCount']) if 'commentCount' in stats else None,'views':int(stats['viewCount']) if 'viewCount' in stats else None})
            stats=p.get('statistics',{})
            value={'provider':provider,'account_id':account_id,'account_name':p['snippet']['title'],'followers':None if stats.get('hiddenSubscriberCount') else int(stats['subscriberCount']) if 'subscriberCount' in stats else None,'posts':posts,'comment_sample':[],'coverage':'Up to 25 uploaded videos for the OAuth-authorized channel. Lifetime views/likes/comment counts; not unique viewers or period activity. Comment text, reach and revenue are not collected. youtube.readonly OAuth and Data API access required.'}
        else:raise ValueError('Unsupported native provider')
    import json
    if token and token in json.dumps(value):raise ValueError('Credential reflection rejected')
    return Observation.model_validate({**value,'captured_at':datetime.now(timezone.utc).isoformat()}).model_dump(mode='json')

@server.tool()
async def social_account_snapshot(account_id:str,conversation_id:str)->dict:
    """Return social-v1 first-party account/posts observations; never publishes or spends."""
    token=os.getenv('EVOLVYN_SOCIAL_TOKEN','');provider=os.getenv('EVOLVYN_SOCIAL_PROVIDER','')
    if not token:raise ValueError('Authorized provider credential required')
    return await observe(provider,account_id,token)
if __name__=='__main__':server.run(transport='stdio')
