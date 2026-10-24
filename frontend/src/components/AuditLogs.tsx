import { useEffect,useState } from 'react';
import type { client } from '../api';
export function AuditLogs({api,onClose}:{api:ReturnType<typeof client>;onClose:()=>void}) {
 const [rows,setRows]=useState<any[]>([]),[error,setError]=useState('');
 useEffect(()=>{api.json('/audit').then(setRows).catch(e=>setError(e.message));},[api]);
 return <div className="panel-shade"><section className="platform-panel" role="dialog" aria-label="Workspace audit logs"><header><h2>Workspace audit logs</h2><button onClick={onClose}>Close</button></header>{error&&<p className="error" role="alert">{error}</p>}<p>Latest recorded server actions. Request bodies and secret values are excluded.</p>{rows.map(r=><article key={r.id}><strong>{r.action||r.method} {r.path||r.provider}</strong><p>{r.at} · {r.status||r.state} · Actor {r.actor||'system'}</p></article>)}{!rows.length&&!error&&<p>No audit events are available.</p>}</section></div>;
}
