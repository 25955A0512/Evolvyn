"""PostgreSQL leases and bounded recovery; live processes are not the queue."""
import json
import secrets
from datetime import datetime,timedelta,timezone
from contextvars import ContextVar

WORKER=ContextVar('execution_worker',default=None)
LEASE_SECONDS=60
MAX_ATTEMPTS=2

def claim(conn,owner,id):
    with conn() as c:
        c.execute("SELECT pg_advisory_xact_lock(hashtext('evolvyn_execution_capacity'))")
        row=c.execute("SELECT body FROM records WHERE id=%s AND owner=%s AND kind='execution' FOR UPDATE",(id,owner)).fetchone()
        if not row:return None
        body=row['body']
        if body['state'] not in ('CREATED','RUNNING'):return None
        expiry=body.get('lease_until')
        if expiry and datetime.fromisoformat(expiry)>datetime.now(timezone.utc):return None
        active=c.execute("SELECT count(*) AS count FROM records WHERE kind='execution' AND body->>'state'='RUNNING' AND (body->>'lease_until')::timestamptz>now()").fetchone()['count']
        if active>=4:return None
        if body.get('attempt',0)>=MAX_ATTEMPTS:
            body.update(state='FAILED',error='Execution recovery limit reached. Start a new analysis after checking the source and provider.')
            c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(body),id));return None
        body.update(state='RUNNING',attempt=body.get('attempt',0)+1,worker=secrets.token_hex(16),lease_until=(datetime.now(timezone.utc)+timedelta(seconds=LEASE_SECONDS)).isoformat())
        c.execute('UPDATE records SET body=%s WHERE id=%s',(json.dumps(body),id))
        return {'id':id,**body}


def pending(conn,capacity):
    if capacity<=0:return []
    with conn() as c:
        return c.execute("SELECT id,owner,body FROM records WHERE kind='execution' AND body->>'question' IS NOT NULL AND body->>'state' IN ('CREATED','RUNNING') AND (body->>'lease_until' IS NULL OR (body->>'lease_until')::timestamptz<now()) ORDER BY created LIMIT %s",(capacity,)).fetchall()
