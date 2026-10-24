"""Central, deterministic authorization for resources, tool risks and data processing."""
from contextvars import ContextVar
from dataclasses import dataclass
from fastapi import HTTPException

REQUEST = ContextVar('policy_request', default=None)
ACTOR = ContextVar('execution_actor', default=None)
RISK = {'read':0,'internal_write':1,'external_write':2,'critical':3}
DEFAULTS = {'tool_allowlist':['*'],'denied_tools':[],'max_tool_risk':'external_write','max_tool_calls':16,'max_run_seconds':300,'allow_external_processing':True,'allowed_mcp_hosts':[]}

@dataclass(frozen=True)
class Principal:
    organization:str
    account:str|None
    role:str

class PolicyEngine:
    def __init__(self,conn):self.conn=conn
    def principal(self,owner):
        explicit=ACTOR.get()
        if explicit:
            if explicit.organization!=owner:raise HTTPException(403,'Organization scope mismatch')
            if explicit.account:
                with self.conn() as c:member=c.execute('SELECT role FROM memberships WHERE account_id=%s AND organization_id=%s',(explicit.account,owner)).fetchone()
                if not member:raise HTTPException(403,'Execution membership was revoked')
                return Principal(owner,explicit.account,member['role'])
            return explicit
        request=REQUEST.get();identity=getattr(request.state,'identity',None) if request else None
        if identity:
            if identity['organization_id']!=owner:raise HTTPException(403,'Organization scope mismatch')
            return Principal(owner,identity.get('account_id'),identity['role'])
        return Principal(owner,None,'demo' if owner.startswith('demo-') else 'owner')
    def settings(self,owner):
        with self.conn() as c:row=c.execute("SELECT body FROM records WHERE owner=%s AND kind='policy' LIMIT 1",(owner,)).fetchone()
        return {key:(row['body'].get(key,value) if row else value) for key,value in DEFAULTS.items()}
    def require(self,owner,action):
        p=self.principal(owner)
        if action in ('manage_policy','manage_registry','approve','manage_members','manage_vault') and p.role not in ('owner','admin'):
            # Sample owners can approve only their own fixed internal demonstration action.
            if not (p.role=='demo' and action=='approve'):raise HTTPException(403,'Administrator permission required')
        if action not in ('read',) and p.role=='viewer':raise HTTPException(403,'Viewer access is read-only')
        return p
    def raw(self,owner,id,kind=None):
        with self.conn() as c:
            row=c.execute('SELECT id,kind,body FROM records WHERE owner=%s AND id=%s',(owner,id)).fetchone()
        if not row or (kind and row['kind']!=kind):raise HTTPException(404,'Record not found')
        return row
    def project_for(self,owner,kind,body,id=None,depth=0):
        if depth>5:return None
        if kind=='project':return {'id':id,**body}
        if body.get('project_id'):row=self.raw(owner,body['project_id'],'project');return {'id':row['id'],**row['body']}
        if body.get('conversation') or body.get('conversation_id'):
            row=self.raw(owner,body.get('conversation') or body['conversation_id'],'conversation');return self.project_for(owner,row['kind'],row['body'],row['id'],depth+1)
        if body.get('execution'):
            row=self.raw(owner,body['execution'],'execution');return self.project_for(owner,row['kind'],row['body'],row['id'],depth+1)
        if body.get('artifact'):
            row=self.raw(owner,body['artifact'],'artifact');return self.project_for(owner,row['kind'],row['body'],row['id'],depth+1)
        return None
    def resource(self,owner,action,kind,body,id=None):
        p=self.require(owner,action)
        if kind=='canvas' and body.get('graph'):
            self.resource(owner,action,'agent_graph',body['graph'])
        if kind=='agent_graph':
            def scopes(value,depth=0):
                if depth>14:return
                if isinstance(value,dict):
                    if isinstance(value.get('conversation_id'),str):yield value['conversation_id']
                    for item in value.values():yield from scopes(item,depth+1)
                elif isinstance(value,list):
                    for item in value:yield from scopes(item,depth+1)
            for conversation_id in set(scopes(body.get('nodes',[]))):
                record=self.raw(owner,conversation_id,'conversation')
                self.resource(owner,action,'conversation',record['body'],record['id'])
        project=self.project_for(owner,kind,body,id)
        if project and project.get('access')=='restricted' and p.role not in ('owner','admin') and p.account not in project.get('members',[]):
            raise HTTPException(404 if action=='read' else 403,'Project access denied')
        return p
    def tool(self,owner,name,risk,permission,permissions,approved=False):
        p=self.require(owner,'write' if risk!='read' else 'read');settings=self.settings(owner)
        if permission not in permissions:raise HTTPException(403,'Required tool permission is absent')
        if name in settings['denied_tools'] or ('*' not in settings['tool_allowlist'] and name not in settings['tool_allowlist']):raise HTTPException(403,'Tool denied by organization policy')
        if RISK[risk]>RISK[settings['max_tool_risk']]:raise HTTPException(403,'Tool risk exceeds organization policy')
        if risk!='read' and not approved:raise HTTPException(409,'Human approval is required for this tool')
        # approved is issued only by the server after an administrator's argument-bound decision.
    def data(self,owner,conversation,mode):
        self.resource(owner,'write','conversation',conversation)
        if mode not in ('local','evidence'):
            project=self.project_for(owner,'conversation',conversation)
            if not self.settings(owner)['allow_external_processing'] or (project and project.get('data_policy')=='local_only'):
                raise HTTPException(403,'Data policy requires local processing')
