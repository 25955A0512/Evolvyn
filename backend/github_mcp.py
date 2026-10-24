"""Read-only GitHub tools over the real MCP protocol; no arbitrary paths or writes."""
import os,re
from datetime import datetime,timezone
from urllib.parse import quote
import httpx
from mcp.server.fastmcp import FastMCP
server=FastMCP('Evolvyn GitHub read-only')
def segment(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',value) or value in ('.','..'):raise ValueError('Invalid repository identifier')
    return quote(value,safe='')
async def get(path,params=None):
    token=os.environ.get('EVOLVYN_GITHUB_TOKEN','')
    if not token:raise ValueError('GitHub credential unavailable')
    async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
        async with client.stream('GET','https://api.github.com'+path,params=params,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}) as response:
            response.raise_for_status();chunks=[];size=0
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>200000:raise ValueError('GitHub response limit exceeded')
                chunks.append(chunk)
            import json
            data=json.loads(b''.join(chunks))
    return data
@server.tool()
async def github_repository(owner:str,repository:str)->dict:
    """Read repository description, language and observed repository counters. Not market measurements."""
    data=await get('/repos/'+segment(owner)+'/'+segment(repository))
    if not isinstance(data,dict) or data.get('private') is not False:raise ValueError('A verified public repository is required')
    return {'repository':{key:data.get(key) for key in ('full_name','description','html_url','language','default_branch','stargazers_count','open_issues_count','updated_at')},'retrieved_at':datetime.now(timezone.utc).isoformat(),'source':'https://github.com/'+segment(owner)+'/'+segment(repository)}
@server.tool()
async def github_issues(owner:str,repository:str,limit:int=10)->dict:
    """Read up to 20 open repository issues as dated untrusted customer/developer feedback."""
    if not 1<=limit<=20:raise ValueError('Limit must be 1–20')
    repository_info=await get('/repos/'+segment(owner)+'/'+segment(repository))
    if not isinstance(repository_info,dict) or repository_info.get('private') is not False:raise ValueError('A verified public repository is required')
    rows=await get('/repos/'+segment(owner)+'/'+segment(repository)+'/issues',{'state':'open','per_page':limit})
    if not isinstance(rows,list) or len(rows)>limit or any(not isinstance(r,dict) for r in rows):raise ValueError('Invalid GitHub issues response')
    return {'issues':[{key:r.get(key) for key in ('number','title','html_url','state','created_at','updated_at')}|{'body':str(r.get('body') or '')[:1800]} for r in rows if 'pull_request' not in r],'retrieved_at':datetime.now(timezone.utc).isoformat(),'source':'https://github.com/'+segment(owner)+'/'+segment(repository)+'/issues'}
@server.tool()
async def github_repositories(limit:int=10)->dict:
    """List authorized public repositories. Does not grant write or private-repository scope."""
    if not 1<=limit<=20:raise ValueError('Limit must be 1–20')
    rows=await get('/user/repos',{'visibility':'public','per_page':limit,'sort':'updated'})
    if not isinstance(rows,list) or len(rows)>limit or any(not isinstance(r,dict) or r.get('private') is not False for r in rows):raise ValueError('Invalid public repository response')
    return {'repositories':[{key:r.get(key) for key in ('full_name','description','html_url','language','updated_at')} for r in rows],'retrieved_at':datetime.now(timezone.utc).isoformat()}
if __name__=='__main__':server.run(transport='stdio')
