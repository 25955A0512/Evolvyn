"""Allowlisted MCP gateway; subprocess command and tool name are server-controlled."""
import asyncio
import json
import os
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel,Field

class RankedAction(BaseModel):
    id:str
    score:float=Field(ge=0,le=5)

async def invoke_rank(candidates):
    # Do not forward provider keys, workspace tokens or database credentials to MCP.
    environment={'PATH':os.defpath,'PYTHONPATH':str(Path(__file__).resolve().parent.parent)}
    parameters=StdioServerParameters(command=sys.executable,args=['-m','backend.mcp_server'],env=environment)
    async with asyncio.timeout(12):
        async with stdio_client(parameters) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                discovered=await session.list_tools()
                if not any(t.name=='prioritize_actions' for t in discovered.tools):raise ValueError('Required MCP tool missing')
                result=await session.call_tool('prioritize_actions',{'candidates':candidates})
                if result.isError:raise ValueError('MCP call failed')
                structured=getattr(result,'structuredContent',None)
                if structured and isinstance(structured.get('result'),list):payload=structured['result']
                else:
                    payload=[]
                    for content in result.content:
                        if getattr(content,'type',None)=='text':
                            decoded=json.loads(content.text)
                            payload.extend(decoded if isinstance(decoded,list) else [decoded])
                ranked=[RankedAction.model_validate(row).model_dump() for row in payload]
                if {r['id'] for r in ranked}!={c['id'] for c in candidates}:raise ValueError('MCP returned unexpected action identities')
                return ranked
