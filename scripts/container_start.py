"""Optional local model plus one API worker; no model download at runtime."""
import os
import subprocess
import signal
import sys
from pathlib import Path
model=Path('/models/qwen2.5-1.5b-instruct-q4_k_m.gguf')
binary=Path('/runtime/llama-b11840/llama-server')
children=[]
def stop(signum=None,frame=None,exitcode=0):
    for child in reversed(children):
        if child.poll() is None:child.terminate()
    for child in reversed(children):
        try:child.wait(timeout=15)
        except subprocess.TimeoutExpired:child.kill()
    sys.exit(exitcode)
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
model_verified=False
if model.is_file() and binary.is_file():
    try:
        from verify_local_model import verify
        model_verified=verify(model.parent)
    except Exception:print('Local model verification failed; the API will expose the labeled fallback.',file=sys.stderr)
if model_verified:
    children.append(subprocess.Popen([str(binary),'--model',str(model),'--host','127.0.0.1','--port','8081','--alias','qwen2.5-1.5b-instruct','--threads','4','--ctx-size','4096','--parallel','1','--n-predict','1536']))
children.append(subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','0.0.0.0','--port','8000','--proxy-headers','--forwarded-allow-ips','*']))
status=children[-1].wait();stop(exitcode=status)
