"""Generate private local deployment secrets without displaying or overwriting them."""
from pathlib import Path
import secrets
import os
import socket
from urllib.parse import urlparse
path=Path(__file__).resolve().parents[1]/'.local/deploy.env'
path.parent.mkdir(parents=True,exist_ok=True)
if not path.exists():
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as file:
        file.write('POSTGRES_PASSWORD='+secrets.token_urlsafe(32)+'\nEVOLVYN_ACCESS_TOKEN='+secrets.token_urlsafe(32)+'\nPUBLIC_ORIGIN=http://localhost:3000\nALLOWED_HOSTS=localhost,127.0.0.1\nCOOKIE_SECURE=0\n')
for name in ('models','llama'):
    (path.parent/name).mkdir(exist_ok=True)
    (path.parent/name).chmod(0o755)
proxy=urlparse(os.getenv('HTTPS_PROXY',os.getenv('HTTP_PROXY',''))).hostname
if proxy:
    try:
        ip=socket.gethostbyname(proxy)
        lines=[line for line in path.read_text().splitlines() if not line.startswith(('EVOLVYN_PROXY_HOST=','EVOLVYN_PROXY_IP='))]
        lines.extend(['EVOLVYN_PROXY_HOST='+proxy,'EVOLVYN_PROXY_IP='+ip])
        path.write_text('\n'.join(lines)+'\n');path.chmod(0o600)
    except OSError:pass
print('Private deployment configuration ready; no secret values displayed')
