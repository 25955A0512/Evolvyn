"""Fifteen-day recoverable conversation/product deletion with scoped content cleanup."""
import json
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from fastapi import Depends,HTTPException
ACCESS=ContextVar('trash_access',default=False)
@contextmanager
def access():
    token=ACCESS.set(True)
    try:yield
    finally:ACCESS.reset(token)

class Trash:
    def __init__(self,s):self.s=s
    def mark(self,owner,id,kind):
        s=self.s;s['POLICY'].require(owner,'write');row=s['get'](owner,id,kind)
        now=datetime.now(timezone.utc);ids={id}
        if kind=='product_spec' and row.get('conversation_id'):ids.add(row['conversation_id'])
        with s['conn']() as c:
            roots=c.execute('SELECT id,body FROM records WHERE owner=%s AND id=ANY(%s) ORDER BY id FOR UPDATE',(owner,list(ids))).fetchall()
            if any(r['body'].get('trashed_at') for r in roots):raise HTTPException(409,'Already in trash')
            active=c.execute("SELECT id FROM records WHERE owner=%s AND kind='execution' AND body->>'conversation'=ANY(%s) AND body->>'state' IN ('CREATED','RUNNING','WAITING_FOR_APPROVAL') FOR UPDATE",(owner,list(ids))).fetchall()
            for run in active:c.execute("UPDATE records SET body=body || %s::jsonb WHERE owner=%s AND id=%s",(json.dumps({'state':'CANCELLED','error':'Conversation moved to trash'}),owner,run['id']))
            c.execute("UPDATE records SET body=body || '{\"state\":\"CANCELLED\",\"error\":\"Conversation moved to trash\"}'::jsonb WHERE owner=%s AND kind='product_build' AND body->>'state'='BUILDING' AND body->>'spec_id'=ANY(%s)",(owner,list(ids)))
            data={'target_id':id,'target_kind':kind,'title':row.get('title') or row.get('name'),'project_id':row.get('project_id'),'root_ids':list(ids),'trashed_at':now.isoformat(),'purge_at':(now+timedelta(days=15)).isoformat(),'actor':s['POLICY'].principal(owner).account}
            c.execute("UPDATE records SET body=body || %s::jsonb WHERE owner=%s AND id=ANY(%s)",(json.dumps({'trashed_at':data['trashed_at'],'purge_at':data['purge_at']}),owner,list(ids)))
            c.execute("INSERT INTO records(id,owner,kind,body) VALUES(%s,%s,'trash_entry',%s)",('trash:'+id,owner,json.dumps(data)))
        for run in active:
            task=s['JOBS'].get(run['id'])
            if task:task.cancel()
        return {'trashed':True,**data}
    def entries(self,owner):
        self.purge(owner)
        return self.s['listing'](owner,'trash_entry')
    def restore(self,owner,id):
        s=self.s;s['POLICY'].require(owner,'write')
        entry=s['get'](owner,id,'trash_entry')
        if datetime.fromisoformat(entry['purge_at'])<=datetime.now(timezone.utc):
            self.purge(owner);raise HTTPException(410,'The fifteen-day retention period has expired')
        with access():
            target=s['get'](owner,entry['target_id'],entry['target_kind']);s['POLICY'].resource(owner,'write',entry['target_kind'],target,entry['target_id'])
        with s['conn']() as c:
            # Lock the tombstone so restore and retention cleanup cannot both win.
            locked=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='trash_entry' FOR UPDATE",(owner,id)).fetchone()
            if not locked:raise HTTPException(410,'Trash entry was already removed')
            if datetime.fromisoformat(locked['body']['purge_at'])<=datetime.now(timezone.utc):raise HTTPException(410,'Retention period expired')
            c.execute("UPDATE records SET body=body-'trashed_at'-'purge_at' WHERE owner=%s AND id=ANY(%s)",(owner,entry['root_ids']))
            c.execute('DELETE FROM records WHERE owner=%s AND id=%s',(owner,id))
        return {'restored':True,'target_id':entry['target_id'],'target_kind':entry['target_kind']}
    def purge(self,owner=None):
        s=self.s
        with s['conn']() as c:
            entries=c.execute("SELECT id,owner,body FROM records WHERE kind='trash_entry' AND body->>'purge_at'<=%s"+(' AND owner=%s' if owner else '')+' FOR UPDATE SKIP LOCKED',([datetime.now(timezone.utc).isoformat(),owner] if owner else [datetime.now(timezone.utc).isoformat()])).fetchall()
            for entry in entries:
                tenant=entry['owner'];roots=set(entry['body']['root_ids'])
                rows=c.execute('SELECT id,kind,body FROM records WHERE owner=%s',(tenant,)).fetchall();remove=set(roots)
                fields=('conversation','conversation_id','spec_id','build_id','execution','artifact','graph_id')
                # Follow ownership links, not text mentions or shared business/project IDs.
                for _ in range(12):
                    old=len(remove)
                    for r in rows:
                        b=r['body']
                        if r['kind']!='document' and any(isinstance(b.get(f),str) and b[f] in remove for f in fields):remove.add(r['id'])
                    if len(remove)==old:break
                graphs={r['body']['graph_id'] for r in rows if r['id'] in remove and r['kind']=='execution' and r['body'].get('graph_id')}
                for graph in graphs:
                    if not any(r['kind']=='execution' and r['id'] not in remove and r['body'].get('graph_id')==graph for r in rows):remove.add(graph)
                docs={doc['id'] for r in rows if r['id'] in roots and r['kind']=='conversation' for doc in r['body'].get('files',[])}
                shared={doc['id'] for r in rows if r['id'] not in remove and r['kind']=='conversation' for doc in r['body'].get('files',[])}
                for document in docs&shared:
                    parent=next((r['id'] for r in rows if r['kind']=='conversation' and r['id'] not in remove and any(d.get('id')==document for d in r['body'].get('files',[]))),None)
                    if parent:c.execute("UPDATE records SET body=jsonb_set(body,'{conversation}',%s::jsonb) WHERE owner=%s AND id=%s",(json.dumps(parent),tenant,document))
                remove.update(docs-shared)
                for _ in range(12):
                    old=len(remove)
                    for r in rows:
                        if r['kind']=='agent_memory' and any(v in remove for v in r['body'].get('source_ids',[])):remove.add(r['id'])
                    if len(remove)==old:break
                c.execute('DELETE FROM records WHERE owner=%s AND id=ANY(%s)',(tenant,list(remove|{entry['id']})))
        return len(entries)
    def install(self,app,auth):
        @app.get('/api/trash')
        def entries(owner=Depends(auth)):return self.entries(owner)
        @app.post('/api/trash/{id}/restore')
        def restore(id:str,owner=Depends(auth)):return self.restore(owner,id)
        @app.delete('/api/conversations/{id}')
        def conversation(id:str,owner=Depends(auth)):
            # Product conversations must be deleted together with their project artifacts.
            with self.s['conn']() as c:p=c.execute("SELECT id FROM records WHERE owner=%s AND kind='product_spec' AND body->>'conversation_id'=%s",(owner,id)).fetchone()
            return self.mark(owner,p['id'],'product_spec') if p else self.mark(owner,id,'conversation')
        @app.delete('/api/studio/products/{id}')
        def product(id:str,owner=Depends(auth)):return self.mark(owner,id,'product_spec')
