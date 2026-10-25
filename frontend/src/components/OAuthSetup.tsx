import { useEffect, useState } from 'react';
import { ConnectorArt } from './ConnectorGallery';
export function OAuthSetup({provider}:{provider?:string}) {
  const [rows,setRows]=useState<any[]>([]);
  useEffect(()=>{fetch('/api/auth/providers').then(r=>r.json()).then(setRows).catch(()=>{});},[]);
  return <section className="oauth-setup"><h3>Set up secure sign-in and connections</h3><p>OAuth client credentials belong to the administrator running Evolvyn. Your Gemini key is used for AI and cannot authorize Google or GitHub accounts.</p>{rows.filter(p=>!provider||p.id===provider).map(p=><details key={p.id} open={!!provider}><summary>{p.name} · {p.enabled?'configured · live sign-in needs verification':'administrator setup required'}</summary>{p.configuration_error&&<p role="alert">{p.configuration_error}</p>}<a href={p.setup?.console_url} target="_blank" rel="noopener noreferrer">Open {p.name} developer console ↗</a><ol>{p.setup?.instructions.map((text:string,i:number)=><li key={i}>{text}</li>)}</ol><label>Exact callback URL<code>{p.setup?.callback_url}</code></label><p>Private environment variable names:</p><pre>{p.setup?.client_id_env}=<br/>{p.setup?.client_secret_env}=</pre><p>No secret values are shown or requested here.</p></details>)}</section>;
}
export function OAuthButtons({register=false}:{register?:boolean}) {
  const [rows,setRows]=useState<any[]>([]),[selected,setSelected]=useState('');
  useEffect(()=>{fetch('/api/auth/providers').then(r=>r.json()).then(setRows).catch(()=>{});},[]);
  return <><div className="oauth-providers">{rows.map(p=>p.enabled?<a className="oauth-provider" key={p.id} href={p.start_url}><ConnectorArt name={p.name} size={18}/>{register?'Sign up':'Sign in'} with {p.name}</a>:<button type="button" className="oauth-provider" key={p.id} onClick={()=>setSelected(selected===p.id?'':p.id)}><ConnectorArt name={p.name} size={18}/>{register?'Sign up':'Sign in'} with {p.name}<small>Setup required</small></button>)}</div>{selected&&<OAuthSetup provider={selected}/>}</>;
}
