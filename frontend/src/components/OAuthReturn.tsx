import {useEffect,useState} from 'react';
import {useNavigate} from 'react-router-dom';
export function OAuthReturn(){
 const navigate=useNavigate(),[error,setError]=useState('');
 useEffect(()=>{let active=true;fetch('/api/auth/me',{credentials:'same-origin',headers:{Authorization:'Bearer cookie','X-Requested-With':'Evolvyn'}}).then(async response=>{if(!response.ok)throw Error('The sign-in session could not be verified. Please try again.');const me=await response.json();if(!me.account)throw Error('No account session was created.');if(active){sessionStorage.setItem('evolvyn-token','cookie');sessionStorage.setItem('evolvyn-organization',me.organization_id);navigate('/dashboard',{replace:true});}}).catch(e=>active&&setError(e.message));return()=>{active=false;};},[]);
 return <main className="login" role="status"><h1>{error?'Sign in could not be completed':'Completing secure sign-in…'}</h1>{error&&<><p role="alert">{error}</p><button onClick={()=>navigate('/login',{replace:true})}>Return to sign in</button></>}</main>;
}
