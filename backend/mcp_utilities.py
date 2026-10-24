"""Second real MCP server profile for validating numerical evidence."""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel,Field
server=FastMCP('Evolvyn evidence utilities')
@server.tool()
def compare_rates(before:float,after:float)->dict:
    """Compare two percentages; this is an observation, not causal attribution."""
    if not 0<=before<=100 or not 0<=after<=100:raise ValueError('Rates must be percentages in 0–100')
    return {'before':before,'after':after,'change_percentage_points':round(after-before,6),'causality_established':False}
@server.tool()
def validate_funnel(visits:int,paid:int)->dict:
    """Calculate conversion from valid non-negative funnel counts."""
    if visits<=0 or paid<0 or paid>visits:raise ValueError('Invalid funnel counts')
    return {'visits':visits,'paid':paid,'conversion_percent':round(paid/visits*100,6)}
if __name__=='__main__':server.run(transport='stdio')
