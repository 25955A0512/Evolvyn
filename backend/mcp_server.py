"""Real local MCP integration: deterministic strategy prioritization over stdio."""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

class Candidate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str
    title:str=Field(max_length=200)
    impact:int=Field(ge=1,le=5)
    confidence:float=Field(ge=0,le=1)
    effort:int=Field(ge=1,le=5)

server=FastMCP('Evolvyn strategy toolkit')

@server.tool()
def prioritize_actions(candidates:list[Candidate])->list[dict]:
    """Rank up to ten proposed actions by impact * confidence / effort. Scores are heuristic, not measured business impact."""
    if len(candidates)>10:raise ValueError('Maximum ten actions')
    return sorted([{'id':c.id,'score':round(c.impact*c.confidence/c.effort,4)} for c in candidates],key=lambda r:r['score'],reverse=True)

if __name__=='__main__':server.run(transport='stdio')
