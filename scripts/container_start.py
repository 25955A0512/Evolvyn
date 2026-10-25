"""Optional local model plus one API worker; honors managed hosting ports/secrets."""
import base64
import hashlib
import os
import signal
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


def runtime_environment(environment):
    """Resolve operator/platform configuration without logging any secret values."""
    result=dict(environment)
    try:port=int(result.get('PORT','8000'))
    except ValueError:raise ValueError('PORT must be an integer')
    if not 1<=port<=65535:raise ValueError('PORT is outside the supported range')
    result['PORT']=str(port)
    seed=result.get('EVOLVYN_VAULT_SEED','')
    if not result.get('EVOLVYN_VAULT_MASTER_KEY') and seed:
        if not 32<=len(seed)<=8192:raise ValueError('Vault seed must contain at least 32 characters')
        result['EVOLVYN_VAULT_MASTER_KEY']=base64.urlsafe_b64encode(hashlib.sha256(seed.encode()).digest()).decode()
    if result.get('RENDER')=='true':
        hosts=[h.strip() for h in result.get('ALLOWED_HOSTS','localhost,127.0.0.1').split(',') if h.strip()]
        hostname=result.get('RENDER_EXTERNAL_HOSTNAME','')
        origin=result.get('PUBLIC_ORIGIN','')
        if not origin:raise ValueError('Set PUBLIC_ORIGIN to the Vercel production HTTPS origin')
        project=Path(__file__).resolve().parent
        if not (project/'backend').is_dir():project=project.parent
        if str(project) not in sys.path:sys.path.insert(0,str(project))
        from backend.oauth_config import public_origin
        origin=public_origin(origin,result.get('COOKIE_SECURE')=='1')
        if not origin.startswith('https://'):raise ValueError('Managed public hosting requires HTTPS')
        result['PUBLIC_ORIGIN']=origin
        for host in (hostname,urlsplit(origin).hostname):
            if host:
                if not all(c.isalnum() or c in '.-' for c in host):raise ValueError('Invalid hosting hostname')
                hosts.append(host)
        result['ALLOWED_HOSTS']=','.join(dict.fromkeys(hosts))
    return result


def main():
    try:os.environ.update(runtime_environment(os.environ))
    except ValueError as error:print(str(error),file=sys.stderr);return 1
    model=Path('/models/qwen2.5-1.5b-instruct-q4_k_m.gguf')
    binary=Path('/runtime/llama-b11840/llama-server')
    children=[];stopping=False
    def request_stop(signum=None,frame=None):
        nonlocal stopping
        stopping=True
        # Never wait inside a signal handler: the interrupted Popen.wait may
        # already hold its waitpid lock. Reentrant waits can deadlock shutdown.
        for child in reversed(children):
            if child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    try:
        model_verified=False
        if model.is_file() and binary.is_file():
            try:
                from verify_local_model import verify
                model_verified=verify(model.parent)
            except Exception:print('Local model verification failed; the API will expose the labeled fallback.',file=sys.stderr)
        if model_verified and not stopping:
            children.append(subprocess.Popen([str(binary),'--model',str(model),'--host','127.0.0.1','--port','8081','--alias','qwen2.5-1.5b-instruct','--threads','4','--ctx-size','4096','--parallel','1','--n-predict','1536']))
        if stopping:return 0
        children.append(subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','0.0.0.0','--port',os.environ['PORT'],'--no-access-log','--proxy-headers','--forwarded-allow-ips','*']))
        status=children[-1].wait()
        return 0 if stopping else status
    finally:
        for child in reversed(children):
            if child.poll() is None:child.terminate()
        for child in reversed(children):
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait()


if __name__=='__main__':sys.exit(main())
