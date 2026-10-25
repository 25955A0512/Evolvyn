"""Isolated social browser fixture. ONLY the upstream MCP call is synthetic.
Real authentication, stdio discovery, vault encryption, queue, SQL and APIs.
Never import in production.
"""
from qa_growth_app import app
from backend import app as module
from datetime import datetime,timezone
original=module.MCP_REGISTRY.call
async def controlled_call(owner,server_id,tool,arguments):
    if tool!='social_account_snapshot':return await original(owner,server_id,tool,arguments)
    return {'provider':'instagram','account_id':arguments['account_id'],'account_name':'Synthetic acceptance shop','captured_at':datetime.now(timezone.utc).isoformat(),'followers':40,'posts':[{'id':'synthetic1','published_at':'2026-01-01T00:00:00+00:00','url':'https://www.instagram.com/p/synthetic/','text':'Synthetic tea product','likes':10,'comments':2}], 'comment_sample':[{'id':'sample1','text':'@synthetic please add blue packaging','published_at':'2026-01-02T00:00:00+00:00'}],'coverage':'SYNTHETIC BROWSER TEST BOUNDARY. Lifetime counters, not live Instagram evidence.'}
module.MCP_REGISTRY.call=controlled_call
