"""Tenant-scoped credential custody. Plaintext never has a read API or enters a run."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr

Provider = Literal['provider', 'groq', 'gemini', 'openrouter', 'mcp']
AGENTS = {
    'business_analyst': 'Business analyst', 'marketing_analyst': 'Marketing analyst',
    'product_manager': 'Product manager', 'architect': 'Software architect',
    'developer': 'Implementation agent', 'reviewer': 'Quality and security reviewer',
    'supervisor': 'Discussion supervisor',
}

def now(): return datetime.now(timezone.utc).isoformat()

class CredentialInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    provider: Provider
    value: SecretStr = Field(min_length=8, max_length=8192)

class BindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    credential_id: str | None = None
    provider: Literal['local', 'evidence', 'provider', 'groq', 'gemini', 'openrouter'] = 'local'
    model: str = Field(default='', max_length=150, pattern=r'^[A-Za-z0-9_.:/@-]*$')

class WorkspaceDefault(BindingInput):
    reset_agent_overrides:bool=False

class Vault:
    def __init__(self, conn, policy): self.conn, self.policy = conn, policy

    def cipher(self):
        key = os.getenv('EVOLVYN_VAULT_MASTER_KEY')
        if not key:
            path = Path(os.getenv('EVOLVYN_VAULT_KEY_FILE', '.local/vault.key'))
            if not path.exists():
                if os.getenv('APP_ENV') == 'production':
                    raise HTTPException(503, 'Vault master key is not provisioned; configure EVOLVYN_VAULT_KEY_FILE securely')
                path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'wb') as stream: stream.write(Fernet.generate_key())
                except FileExistsError: pass
            key = path.read_bytes()
        try: return Fernet(key)
        except (ValueError, TypeError): raise HTTPException(503, 'Vault master key is invalid')

    def rows(self, owner, kind):
        with self.conn() as c:
            return c.execute('SELECT id,body FROM records WHERE owner=%s AND kind=%s ORDER BY created DESC', (owner, kind)).fetchall()

    def metadata(self, row):
        return {'id': row['id'], **{k: v for k, v in row['body'].items() if k != 'ciphertext'}}

    def list(self, owner):
        self.policy.require(owner, 'manage_vault')
        return [self.metadata(row) for row in self.rows(owner, 'vault_secret')]

    def put(self, owner, body, id=None):
        self.policy.require(owner, 'manage_vault')
        from backend.agent_memory import reject_secrets
        reject_secrets(body.name)
        if body.value.get_secret_value() in body.name:raise HTTPException(422,'Credential values cannot be used as display names')
        if id is None and len(self.rows(owner,'vault_secret'))>=100:raise HTTPException(422,'Organization credential limit reached')
        id = id or str(uuid4())
        with self.conn() as c:
            prior = c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='vault_secret' FOR UPDATE", (owner, id)).fetchone()
            if prior and prior['body']['provider'] != body.provider: raise HTTPException(409, 'A replacement must keep the credential provider')
            data = {'name': body.name, 'provider': body.provider, 'enabled': True, 'version': prior['body']['version'] + 1 if prior else 1, 'updated_at': now()}
            clear = json.dumps({'owner': owner, 'id': id, 'provider': body.provider, 'value': body.value.get_secret_value()}).encode()
            data['ciphertext'] = self.cipher().encrypt(clear).decode()
            c.execute("INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,'vault_secret',%s) ON CONFLICT(id) DO UPDATE SET body=EXCLUDED.body WHERE records.owner=EXCLUDED.owner", (id, owner, json.dumps(data)))
        return self.metadata({'id': id, 'body': data})

    def rotate_for_service(self,owner,id,value,expected_version):
        """Renew an existing grant without reviving disabled or concurrently replaced keys."""
        self.policy.require(owner,'manage_vault')
        if not isinstance(value,str) or not 8<=len(value)<=8192:raise HTTPException(422,'Invalid renewed credential')
        with self.conn() as c:
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='vault_secret' FOR UPDATE",(owner,id)).fetchone()
            if not row or not row['body']['enabled'] or row['body']['provider']!='mcp' or row['body']['version']!=expected_version:raise HTTPException(409,'Credential was revoked or changed during renewal')
            data=row['body'];data.update(version=expected_version+1,updated_at=now())
            clear=json.dumps({'owner':owner,'id':id,'provider':'mcp','value':value}).encode()
            data['ciphertext']=self.cipher().encrypt(clear).decode()
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(data),owner,id))
        return self.metadata({'id':id,'body':data})

    def reveal_for_service(self, owner, id, provider):
        with self.conn() as c:
            row = c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='vault_secret'", (owner, id)).fetchone()
        if not row or not row['body']['enabled'] or row['body']['provider'] != provider: raise HTTPException(409, 'Credential is unavailable or provider does not match')
        try: data = json.loads(self.cipher().decrypt(row['body']['ciphertext'].encode()))
        except (InvalidToken, ValueError): raise HTTPException(503, 'Credential could not be decrypted with the configured vault key')
        if (data['owner'], data['id'], data['provider']) != (owner, id, provider): raise HTTPException(503, 'Credential integrity check failed')
        return data['value']

    def bindings(self, owner):
        return [{'id': row['id'], **row['body']} for row in self.rows(owner, 'model_binding')]

    def effective_routes(self,owner,agents):
        rows = self.bindings(owner)
        default=next((row for row in rows if row['agent']=='default'),None)
        # A single saved Gemini key is useful immediately, while explicit local,
        # evidence or per-agent choices remain authoritative. Never cross tenants.
        if not default:
            keys=[r for r in self.rows(owner,'vault_secret') if r['body']['enabled'] and r['body']['provider']=='gemini']
            if len(keys)==1:default={'agent':'default','provider':'gemini','credential_id':keys[0]['id'],'model':'','inferred':True}
        by_agent={r['agent']:r for r in rows}
        return {agent:by_agent.get(agent,default) for agent in agents}

    def route(self,owner,agent):return self.effective_routes(owner,[agent])[agent]

    def credential_for(self,owner,provider):
        default=next((r for r in self.bindings(owner) if r['agent']=='default' and r['provider']==provider and r.get('credential_id')),None)
        if default:return default['credential_id']
        keys=[r for r in self.rows(owner,'vault_secret') if r['body']['enabled'] and r['body']['provider']==provider]
        if len(keys)>1:raise HTTPException(409,'Several keys match this provider; choose a default credential in Key vault')
        return keys[0]['id'] if keys else None

    def bind(self, owner, agent, body,reset_overrides=False):
        self.policy.require(owner, 'manage_vault')
        from backend.agent_memory import reject_secrets
        reject_secrets(body.model)
        if agent != 'default' and agent not in AGENTS and not any(row['body']['agent']==agent for row in self.rows(owner,'agent_definition')): raise HTTPException(422, 'Unknown agent')
        if body.provider in ('local', 'evidence') and body.credential_id: raise HTTPException(422, 'Local routes do not accept credentials')
        if body.credential_id: self.reveal_for_service(owner, body.credential_id, body.provider)
        data = {**body.model_dump(), 'agent': agent, 'updated_at': now()}
        id = 'model-binding:' + owner + ':' + agent
        with self.conn() as c:
            c.execute("INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,'model_binding',%s) ON CONFLICT(id) DO UPDATE SET body=EXCLUDED.body WHERE records.owner=EXCLUDED.owner", (id, owner, json.dumps(data)))
            if reset_overrides:c.execute("DELETE FROM records WHERE owner=%s AND kind='model_binding' AND body->>'agent'!='default'",(owner,))
        return {'id': id, **data}

def install(app, auth, vault):
    @app.get('/api/vault')
    def overview(owner=Depends(auth)):
        entries = vault.list(owner)
        try: vault.cipher(); ready = True
        except HTTPException: ready = False
        agents={**AGENTS,**{row['body']['agent']:row['body']['name'] for row in vault.rows(owner,'agent_definition')}}
        return {'credentials': entries, 'bindings': vault.bindings(owner), 'agents': agents,'effective_routes':{agent:route or {'provider':'local','agent':agent} for agent,route in vault.effective_routes(owner,agents).items()}, 'ready': ready, 'encryption': 'Fernet authenticated encryption; master key outside PostgreSQL'}

    @app.put('/api/vault/workspace-default')
    def workspace_default(body:WorkspaceDefault,owner=Depends(auth)):
        vault.policy.require(owner,'manage_vault')
        if 'model' not in body.model_fields_set:
            prior=next((r for r in vault.bindings(owner) if r['agent']=='default' and r['provider']==body.provider and r.get('credential_id')==body.credential_id),None)
            if prior:body=body.model_copy(update={'model':prior.get('model','')})
        result=vault.bind(owner,'default',BindingInput(**body.model_dump(exclude={'reset_agent_overrides'})),body.reset_agent_overrides)
        return result

    @app.post('/api/vault/credentials')
    def create(body: CredentialInput, owner=Depends(auth)): return vault.put(owner, body)

    @app.put('/api/vault/credentials/{id}')
    def replace(id: str, body: CredentialInput, owner=Depends(auth)):
        if not any(row['id'] == id for row in vault.rows(owner, 'vault_secret')): raise HTTPException(404, 'Credential not found')
        return vault.put(owner, body, id)

    @app.delete('/api/vault/credentials/{id}')
    def revoke(id: str, owner=Depends(auth)):
        vault.policy.require(owner, 'manage_vault')
        with vault.conn() as c:
            row = c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='vault_secret' FOR UPDATE", (owner, id)).fetchone()
            if not row: raise HTTPException(404, 'Credential not found')
            data = {k: v for k, v in row['body'].items() if k != 'ciphertext'}
            data.update(enabled=False, revoked_at=now())
            c.execute('UPDATE records SET body=%s WHERE id=%s AND owner=%s', (json.dumps(data), id, owner))
        return {'revoked': True}

    @app.put('/api/vault/bindings/{agent}')
    def binding(agent: str, body: BindingInput, owner=Depends(auth)): return vault.bind(owner, agent, body)

    @app.delete('/api/vault/bindings/{agent}')
    def inherit(agent: str, owner=Depends(auth)):
        vault.policy.require(owner, 'manage_vault')
        with vault.conn() as c: c.execute("DELETE FROM records WHERE owner=%s AND kind='model_binding' AND body->>'agent'=%s", (owner, agent))
        return {'inheriting_default': True}
