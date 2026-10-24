#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [ -z "${DOCKER_CONFIG:-}" ] && [ ! -w "$HOME" ]; then export DOCKER_CONFIG="$PWD/.local/cache/docker"; fi
python3 scripts/prepare_deployment.py
mkdir -p .local/wheels
PIP_CACHE_DIR="$PWD/.local/cache/pip" python3 -m pip download --require-hashes --only-binary=:all: -r requirements.lock --dest .local/wheels --disable-pip-version-check -q
npm --prefix frontend run build
python3 - <<'PY'
from pathlib import Path
import shutil,os,ssl
root=Path.cwd();context=root/'.local/container-build'
api=context/'api';web=context/'web'
api.mkdir(parents=True,exist_ok=True);web.mkdir(parents=True,exist_ok=True)
for name in ('backend','sample-data','frontend'):
    shutil.copytree(root/name,api/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','node_modules','dist'))
shutil.copytree(root/'.local/wheels',api/'wheels',dirs_exist_ok=True)
shutil.copy2(root/'requirements.lock',api/'requirements.lock')
(api/'scripts').mkdir(exist_ok=True)
shutil.copy2(root/'scripts/container_start.py',api/'scripts/container_start.py')
shutil.copy2(root/'scripts/verify_local_model.py',api/'scripts/verify_local_model.py')
shutil.copy2(root/'scripts/container_start.py',api/'container_start.py')
shutil.copy2(root/'scripts/verify_local_model.py',api/'verify_local_model.py')
certificate=Path(os.getenv('SSL_CERT_FILE','/etc/ssl/certs/ca-certificates.crt'))
ssl.create_default_context(cafile=str(certificate))
public_bundle=certificate.read_bytes()
if b'PRIVATE KEY' in public_bundle:raise ValueError('Refusing to copy a private key as a trust bundle')
(api/'ca_bundle.crt').write_bytes(public_bundle)
(api/'Dockerfile').write_text('FROM python:3.12.14-slim\nWORKDIR /app\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SSL_CERT_FILE=/app/ca_bundle.crt\nCOPY ca_bundle.crt ./\nCOPY requirements.lock ./\nCOPY wheels /wheels\nRUN pip install --no-index --find-links=/wheels --require-hashes -r requirements.lock && rm -rf /wheels\nCOPY backend ./backend\nCOPY frontend ./frontend\nCOPY scripts ./scripts\nCOPY sample-data ./sample-data\nCOPY container_start.py verify_local_model.py ./\nRUN useradd --create-home --uid 10001 evolvyn && chown -R evolvyn:evolvyn /app\nUSER evolvyn\nEXPOSE 8000\nCMD ["python","container_start.py"]\n')
shutil.copytree(root/'frontend/dist',web/'dist',dirs_exist_ok=True)
shutil.copy2(root/'frontend/nginx.conf',web/'nginx.conf')
compiler=context/'compiler';compiler.mkdir(exist_ok=True)
shutil.copytree(root/'frontend/node_modules',compiler/'node_modules',dirs_exist_ok=True)
shutil.copy2(root/'compiler/server.mjs',compiler/'server.mjs')
(compiler/'Dockerfile').write_text('FROM node:24-bookworm-slim\nWORKDIR /compiler\nCOPY --chown=node:node node_modules ./node_modules\nCOPY --chown=node:node server.mjs ./server.mjs\nUSER node\nEXPOSE 8070\nCMD ["node","server.mjs"]\n')
(web/'Dockerfile').write_text('FROM nginx:1.28-alpine\nCOPY dist /usr/share/nginx/html\nCOPY nginx.conf /etc/nginx/conf.d/default.conf\nRUN chown -R nginx:nginx /usr/share/nginx/html\nEXPOSE 80\n')
PY
docker compose --env-file .local/deploy.env -f compose.yaml -f compose.offline.yaml build
