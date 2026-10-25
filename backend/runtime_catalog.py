"""Discover the actual shared runtime and a bounded tool ontology."""
from fastapi import Depends

# Stable entity/action terms; custom registrations extend these terms via metadata.
BUILTIN_ONTOLOGY={
 'sync_growth_social':(['social_account','post','evidence'],['observe','ingest']),
 'analyze_business':(['business','customer_feedback','evidence'],['observe','analyze']),
 'investigate_operations':(['incident','evidence'],['observe','analyze']),
 'prioritize_actions':(['recommendation'],['rank']),
 'create_internal_note':(['decision','conversation'],['create']),
 'create_experiment_brief':(['experiment','task'],['create','verify']),
 'build_product':(['product','source_artifact'],['build']),
 'recall_agent_memory':(['memory'],['retrieve']),
}
def annotate(spec):
    entities,actions=BUILTIN_ONTOLOGY.get(spec.get('builtin',spec['name']),(['external_resource'] if spec['adapter']=='mcp' else ['workspace'],['invoke']))
    return {**spec,'ontology':{'version':'1.0','entities':sorted(set(entities+spec.get('entities',[]))),'actions':sorted(set(actions+spec.get('capabilities',[]))),'effect':spec['risk'],'input_contract':spec['input_schema'],'output_contract':spec.get('output_schema')}}
def install(app,auth,tools,policy):
    @app.get('/api/runtime')
    def runtime(owner=Depends(auth)):
        return {'version':'1.0','components':[
          {'id':'harness','name':'Goal execution & bounded graph loops','endpoint':'/api/harness/graphs'},
          {'id':'specialists','name':'LangGraph discussion and critique','endpoint':'/api/discussions'},
          {'id':'mcp','name':'Extensible MCP gateway','endpoint':'/api/mcp/servers'},
          {'id':'tools','name':'Typed tool ontology','endpoint':'/api/runtime/ontology'},
          {'id':'models','name':'Default and per-agent model gateway','endpoint':'/api/vault'},
          {'id':'memory','name':'Reviewed scoped memory','endpoint':'/api/memory'},
          {'id':'governance','name':'Resource, data, risk and approval policy','endpoint':'/api/governance/policy'},
          {'id':'canvas','name':'Visual requirements and executable workflows','endpoint':'/api/canvas'},
          {'id':'growth','name':'Evidence and market signal review','endpoint':'/api/growth/reports'}],
          'policy':policy.settings(owner),'export_mode':'Complete isolated Evolvyn runtime source, fresh identity and database, no credentials or customer records copied'}
    @app.get('/api/runtime/ontology')
    def ontology(entity:str='',action:str='',owner=Depends(auth)):
        rows=[annotate(t) for t in tools.catalog(owner)]
        return {'version':'1.0','tools':[t for t in rows if (not entity or entity in t['ontology']['entities']) and (not action or action in t['ontology']['actions'])]}
