"""Reviewed, scoped long-term memory. Retrieved text is data, never instructions."""
import re
import json
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.retrieval import tokens

def reject_secrets(text):
    if re.search(r'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{25,}|AKIA[0-9A-Z]{16})\b|-----BEGIN .*PRIVATE KEY-----', text):
        raise HTTPException(422, 'Credentials belong in the key vault, not memory or prompts')

class MemoryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: str | None = None
    conversation: str | None = None
    category: Literal['fact', 'preference', 'decision', 'lesson', 'market_observation'] = 'decision'
    text: str = Field(min_length=3, max_length=4000)
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    agent: str = Field(default='shared', max_length=60)
    retention_days: int = Field(default=90, ge=1, le=3650)

class Memory:
    def __init__(self, get, save, listing, policy): self.get, self.save, self.listing, self.policy = get, save, listing, policy
    def propose(self, owner, body, origin='user'):
        self.policy.require(owner, 'write'); reject_secrets(body.text)
        if body.conversation:
            conversation = self.get(owner, body.conversation, 'conversation')
            if body.project_id and body.project_id != conversation.get('project_id'): raise HTTPException(422, 'Memory scope does not match conversation')
            body = body.model_copy(update={'project_id': conversation.get('project_id')})
        if body.project_id: self.get(owner, body.project_id, 'project')
        for id in body.source_ids:
            row = self.policy.raw(owner, id)
            self.policy.resource(owner, 'read', row['kind'], row['body'], id)
            source_project = self.policy.project_for(owner, row['kind'], row['body'], id)
            if (source_project or {}).get('id') != body.project_id: raise HTTPException(422, 'Memory provenance must belong to the same project scope')
        return self.save(owner, 'agent_memory', {**body.model_dump(), 'state': 'DRAFT', 'origin': origin, 'provenance': 'source-linked observation' if body.source_ids else 'user-provided claim or preference; not independently verified', 'created_at': datetime.now(timezone.utc).isoformat(), 'expires_at': (datetime.now(timezone.utc) + timedelta(days=body.retention_days)).isoformat()})
    def recall(self, owner, query, project_id=None, agent='shared', limit=8):
        terms = set(tokens(query)); now = datetime.now(timezone.utc)
        rows = [row for row in self.listing(owner, 'agent_memory') if row['state'] == 'ACCEPTED' and row.get('project_id') == project_id and row['agent'] in ('shared', agent) and datetime.fromisoformat(row['expires_at']) > now]
        scored = [(len(terms & set(tokens(row['text']))), row) for row in rows]
        return [{**row, 'retrieval_score': score, 'retrieval_method': 'lexical overlap with scope and retention filters'} for score, row in sorted(scored, key=lambda pair: pair[0], reverse=True) if score or not terms][:limit]
    def decide(self, owner, id, accept):
        self.policy.require(owner, 'approve'); row = self.get(owner, id, 'agent_memory')
        if row['state'] != 'DRAFT': raise HTTPException(409, 'Memory was already reviewed')
        with self.policy.conn() as c:
            locked=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='agent_memory' FOR UPDATE",(owner,id)).fetchone();body=locked['body']
            if body['state']!='DRAFT':raise HTTPException(409,'Memory was already reviewed')
            body.update(state='ACCEPTED' if accept else 'REJECTED',reviewed_by=self.policy.principal(owner).account,reviewed_at=datetime.now(timezone.utc).isoformat())
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(body),owner,id))
        return {'id':id,**body}


def install(app, auth, memory):
    @app.get('/api/memory')
    def entries(owner=Depends(auth)): return memory.listing(owner, 'agent_memory')
    @app.post('/api/memory')
    def propose(body: MemoryInput, owner=Depends(auth)): return memory.propose(owner, body)
    @app.get('/api/memory/recall')
    def recall(q: str = '', project_id: str | None = None, agent: str = 'shared', owner=Depends(auth)):
        if len(q) > 2000: raise HTTPException(422, 'Query is too long')
        if project_id: memory.get(owner, project_id, 'project')
        return memory.recall(owner, q, project_id, agent)
    @app.post('/api/memory/{id}/decision')
    def decide(id: str, body: dict, owner=Depends(auth)):
        if set(body) != {'accept'} or not isinstance(body['accept'], bool): raise HTTPException(422, 'Boolean accept decision required')
        return memory.decide(owner, id, body['accept'])
    @app.delete('/api/memory/{id}')
    def forget(id: str, owner=Depends(auth)):
        memory.policy.require(owner, 'approve'); memory.get(owner, id, 'agent_memory')
        with memory.policy.conn() as c: c.execute("DELETE FROM records WHERE owner=%s AND id=%s AND kind='agent_memory'", (owner, id))
        return {'deleted': True}
