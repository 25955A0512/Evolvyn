import asyncio
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend import app as module

@pytest.fixture
def client():
    with TestClient(module.app) as c:
        c.headers['Authorization']='Bearer '+module.TOKEN
        yield c

def server(c,profile='evidence_utilities'):
    row=c.post('/api/mcp/servers',json={'name':'Evidence '+uuid4().hex[:6],'profile':profile}).json()
    probed=c.post('/api/mcp/servers/'+row['id']+'/probe');assert probed.status_code==200,probed.text
    assert probed.json()['status']=='healthy',probed.text
    return probed.json()

def test_persistent_mcp_crud_discovery_and_dynamic_tool_invocation(client):
    one=server(client);two=server(client,'business_strategy')
    assert len(client.get('/api/mcp/servers').json())==2
    assert {'compare_rates','validate_funnel'}<= {t['name'] for t in one['tools']}
    registration=client.post('/api/tool-registry',json={'name':'evidence.compare','description':'Compare observed rates','adapter':'mcp','server_id':one['id'],'remote_tool':'compare_rates','capabilities':['analytics.compare'],'entities':['conversion']})
    assert registration.status_code==200,registration.text
    tool=registration.json()
    assert client.get('/api/tool-registry?entity=conversion').json()[0]['name']=='evidence.compare'
    invoked=client.post('/api/tool-registry/evidence.compare/invoke',json={'arguments':{'before':5,'after':6}})
    assert invoked.status_code==200,invoked.text
    assert invoked.json()['result']['change_percentage_points']==1
    assert client.delete('/api/mcp/servers/'+one['id']).status_code==409
    assert client.patch('/api/tool-registry/'+tool['id'],json={'enabled':False}).status_code==200
    assert client.delete('/api/mcp/servers/'+one['id']).status_code==200
    assert client.post('/api/tool-registry/evidence.compare/invoke',json={'arguments':{'before':5,'after':6}}).status_code==404

def test_tool_registration_is_persistent_and_cannot_run_arbitrary_code(client):
    bad=client.post('/api/tool-registry',json={'name':'shell','description':'Bad','adapter':'builtin','builtin':'os.system'})
    assert bad.status_code==422
    alias=client.post('/api/tool-registry',json={'name':'business.review','description':'Scoped analytics','adapter':'builtin','builtin':'analyze_business','capabilities':['business.intelligence']})
    assert alias.status_code==200
    assert any(t['name']=='business.review' for t in client.get('/api/tools').json())
    assert client.post('/api/mcp/servers',json={'name':'Shell','profile':'business_strategy','command':'sh'}).status_code==422

def test_tool_write_requires_one_time_argument_bound_approval(client):
    convo=client.post('/api/conversations',json={'title':'Governed note'}).json()
    args={'conversation_id':convo['id'],'text':'Approved project context'}
    assert client.post('/api/tools/create_internal_note/invoke',json={'arguments':args}).status_code==403
    pending=client.post('/api/tool-registry/create_internal_note/request-approval',json={'arguments':args})
    assert pending.status_code==200,pending.text
    decision=client.post('/api/tool-approvals/'+pending.json()['id']+'/decision',json={'approve':True})
    assert decision.status_code==200 and decision.json()['state']=='COMPLETED',decision.text
    note=decision.json()['result']
    assert module.get('initial-workspace',note['id'],'project_note')['text']==args['text']
    assert client.post('/api/tool-approvals/'+pending.json()['id']+'/decision',json={'approve':True}).status_code==409

def test_central_allowlist_and_risk_policy_controls_tools(client):
    original=client.get('/api/governance/policy').json()
    updated={**original,'tool_allowlist':['prioritize_actions'],'denied_tools':['create_internal_note']}
    assert client.put('/api/governance/policy',json=updated).status_code==200
    result=client.post('/api/governance/evaluate',json={'tool':'create_internal_note','risk':'internal_write','permission':'workspace.write'})
    assert result.json()['allowed'] is False
    response=client.post('/api/tool-registry/create_internal_note/request-approval',json={'arguments':{'conversation_id':'missing','text':'x'}})
    assert response.status_code in (403,404)
    client.put('/api/governance/policy',json=original)

def test_remote_mcp_registration_rejects_credential_urls_and_private_networks(client,monkeypatch):
    from backend import mcp_registry
    original=client.get('/api/governance/policy').json()
    client.put('/api/governance/policy',json={**original,'allowed_mcp_hosts':['localhost','private.example','public.example']})
    assert client.post('/api/mcp/servers',json={'name':'Bad','transport':'streamable_http','url':'http://localhost:8080/mcp'}).status_code==422
    assert client.post('/api/mcp/servers',json={'name':'Bad','transport':'streamable_http','url':'https://user:secret@public.example/mcp'}).status_code==422
    monkeypatch.setattr(mcp_registry.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    assert client.post('/api/mcp/servers',json={'name':'Rebind','transport':'streamable_http','url':'https://private.example/mcp'}).status_code==422
    assert client.post('/api/mcp/servers',json={'name':'Credential','auth_env':'MODEL_API_KEY'}).status_code==422
    client.put('/api/governance/policy',json=original)

def test_cross_organization_registry_objects_are_not_visible(client):
    foreign=module.save('different-org','mcp_server',{'name':'Private','enabled':True,'profile':'business_strategy','transport':'stdio'})
    assert client.post('/api/mcp/servers/'+foreign['id']+'/probe').status_code==404
    assert client.delete('/api/mcp/servers/'+foreign['id']).status_code==404

def test_credential_references_are_scoped_to_the_organization(client,monkeypatch):
    from backend import mcp_registry
    policy=client.get('/api/governance/policy').json()
    client.put('/api/governance/policy',json={**policy,'allowed_mcp_hosts':['public.example']})
    monkeypatch.setattr(mcp_registry.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    wrong=client.post('/api/mcp/servers',json={'name':'Foreign credential','transport':'streamable_http','url':'https://public.example/mcp','auth_env':'EVOLVYN_MCP_DIFFERENT_TOKEN'})
    assert wrong.status_code==422
    prefix=client.get('/api/mcp/credential-prefix').json()['prefix']
    allowed=client.post('/api/mcp/servers',json={'name':'Scoped credential','transport':'streamable_http','url':'https://public.example/mcp','auth_env':prefix+'TOKEN','risk':'external_write'})
    assert allowed.status_code==200
    assert 'TOKEN' in allowed.json()['auth_env']
    client.put('/api/governance/policy',json=policy)

def test_remote_tools_respect_org_and_project_data_policy(client,monkeypatch):
    from backend import mcp_registry
    policy=client.get('/api/governance/policy').json()
    monkeypatch.setattr(mcp_registry.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    client.put('/api/governance/policy',json={**policy,'allowed_mcp_hosts':['public.example']}).raise_for_status()
    remote=client.post('/api/mcp/servers',json={'name':'Remote tools','transport':'streamable_http','url':'https://public.example/mcp'}).json()
    assert remote['risk']=='external_write'
    remote.update(risk='read',status='healthy',tools=[{'name':'inspect','input_schema':{'type':'object','properties':{'conversation_id':{'type':'string'}},'required':['conversation_id']}}])
    module.save('initial-workspace','mcp_server',{k:v for k,v in remote.items() if k!='id'},remote['id'])
    client.post('/api/tool-registry',json={'name':'remote.inspect','description':'Policy test','adapter':'mcp','server_id':remote['id'],'remote_tool':'inspect'}).raise_for_status()
    business=client.post('/api/businesses',json={'name':'Local only'}).json()
    project=client.post('/api/projects',json={'name':'Sensitive evidence','goal':'Keep data local','business_id':business['id']}).json()
    conv=client.post('/api/conversations',json={'title':'Private evidence','business_id':business['id'],'project_id':project['id']}).json()
    calls=[]
    async def call(*args):calls.append(args);return {'ok':True}
    monkeypatch.setattr(module.MCP_REGISTRY,'call',call)
    response=client.post('/api/tool-registry/remote.inspect/invoke',json={'arguments':{'conversation_id':conv['id']}})
    assert response.status_code==403 and calls==[]
    unrestricted=client.post('/api/conversations',json={'title':'Organization policy test'}).json()
    client.put('/api/governance/policy',json={**policy,'allow_external_processing':False}).raise_for_status()
    response=client.post('/api/tool-registry/remote.inspect/invoke',json={'arguments':{'conversation_id':unrestricted['id']}})
    assert response.status_code==403 and calls==[]
    client.put('/api/governance/policy',json=policy).raise_for_status()


def test_tool_approval_invalidated_by_changed_risk_configuration(client):
    server_row=server(client)
    client.post('/api/tool-registry',json={'name':'changing.compare','description':'Version-bound approval','adapter':'mcp','server_id':server_row['id'],'remote_tool':'compare_rates'}).raise_for_status()
    approval=client.post('/api/tool-registry/changing.compare/request-approval',json={'arguments':{'before':5,'after':6}})
    assert approval.status_code==200
    server_row['risk']='critical'
    module.save('initial-workspace','mcp_server',{k:v for k,v in server_row.items() if k!='id'},server_row['id'])
    response=client.post('/api/tool-approvals/'+approval.json()['id']+'/decision',json={'approve':True})
    assert response.status_code==409
