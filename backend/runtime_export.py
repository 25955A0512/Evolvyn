"""Bundle the actual Evolvyn runtime, never tenant configuration, records or secrets."""
from pathlib import Path
import json

def bundle(root=None):
    root=root or Path(__file__).resolve().parents[1]
    paths=[]
    for folder,patterns in [('backend',('*.py','template_assets/package*.json','template_assets/node-api/package*.json')),('frontend',('src/**/*.tsx','src/**/*.ts','src/**/*.css','public/assets/tabler/*.svg','public/assets/tabler/LICENSE.txt','public/assets/tabler/manifest.json','package.json','package-lock.json','tsconfig.json','vite.config.js','index.html','Dockerfile','nginx.conf')),('compiler',('*.mjs','Dockerfile')),('sample-data',('*.txt','*.csv',))]:
        for pattern in patterns:paths.extend((root/folder).glob(pattern))
    for name in ('requirements.lock','scripts/container_start.py','scripts/verify_local_model.py'):
        paths.append(root/name)
    files={}
    for path in sorted(set(paths)):
        if not path.is_file() or path.is_symlink():continue
        relative=path.relative_to(root).as_posix()
        if any(part in {'.local','.env','node_modules','__pycache__','.git','dist'} for part in path.relative_to(root).parts):raise ValueError('Runtime export path denied')
        files['evolvyn/'+relative]=path.read_text()
    files['evolvyn/Dockerfile']='FROM python:3.12.14-slim\nWORKDIR /app\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\nCOPY requirements.lock ./\nRUN pip install --no-cache-dir --require-hashes -r requirements.lock\nCOPY backend ./backend\nCOPY frontend ./frontend\nCOPY sample-data ./sample-data\nCOPY scripts ./scripts\nCOPY scripts/container_start.py scripts/verify_local_model.py ./\nRUN useradd --create-home --uid 10001 evolvyn && chown -R evolvyn:evolvyn /app\nUSER evolvyn\nEXPOSE 8000\nCMD ["python","container_start.py"]\n'
    files['evolvyn/frontend/nginx.conf']=files['evolvyn/frontend/nginx.conf'].replace('http://api:8000','http://agents_api:8000')
    files['evolvyn/.dockerignore']='.git\n.env\n**/.env\n.local\n**/.local\n.venv\n**/node_modules\n**/__pycache__\n**/dist\n'
    files['evolvyn/runtime.json']=json.dumps({'version':'1.0','components':['langgraph','graph_harness','bounded_loops','mcp_gateway','tool_ontology','model_gateway','reviewed_memory','governance','canvas','growth'],'configuration':'Fresh deployment; no tenant data, credentials, existing policies, live integrations or models are copied. Configure the new runtime through its console.','console':'http://localhost:3001','identity_boundary':'Separate origin, database and account sessions; no automatic access to product records.'},indent=2)
    files['scripts/prepare_product.py']='''"""Create private generated-product deployment configuration without printing secrets."""
from pathlib import Path
import secrets,os,base64
root=Path(__file__).resolve().parents[1]
target=root/'.env'
if not target.exists():
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as stream:
  stream.write('POSTGRES_PASSWORD='+secrets.token_urlsafe(32)+'\\nAGENT_POSTGRES_PASSWORD='+secrets.token_urlsafe(32)+'\\nAGENT_ACCESS_TOKEN='+secrets.token_urlsafe(32)+'\\n')
else:
 text=target.read_text()
 with target.open('a') as stream:
  for key in ('AGENT_POSTGRES_PASSWORD','AGENT_ACCESS_TOKEN'):
   if not any(line.startswith(key+'=') for line in text.splitlines()):stream.write('\\n'+key+'='+secrets.token_urlsafe(32)+'\\n')
if not any(line.startswith('AGENT_SESSION_COOKIE=') for line in target.read_text().splitlines()):
 with target.open('a') as stream:stream.write('\\nAGENT_SESSION_COOKIE=evolvyn_agent_'+secrets.token_hex(8)+'\\n')
if not any(line.startswith('AGENT_COMPILER_TOKEN=') for line in target.read_text().splitlines()):
 with target.open('a') as stream:stream.write('\\nAGENT_COMPILER_TOKEN='+secrets.token_urlsafe(32)+'\\n')
vault=root/'evolvyn/.local/vault.key'
vault.parent.mkdir(parents=True,exist_ok=True)
if not vault.exists():
 fd=os.open(vault,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(base64.urlsafe_b64encode(secrets.token_bytes(32)))
print('Private product and agent runtime configuration ready. No secret values displayed.')
'''
    return files

SERVICES='''  agents_db:
    networks: [agent_private]
    image: postgres:17
    environment:
      POSTGRES_USER: evolvyn
      POSTGRES_DB: evolvyn
      POSTGRES_PASSWORD: ${AGENT_POSTGRES_PASSWORD:?Run python scripts/prepare_product.py}
    volumes: [agent_database:/var/lib/postgresql/data]
    healthcheck:
      test: [CMD-SHELL, pg_isready -U evolvyn]
      interval: 3s
      timeout: 3s
      retries: 30
  agents_vault_init:
    image: python:3.12.14-slim
    user: "0:0"
    network_mode: none
    read_only: true
    cap_drop: [ALL]
    cap_add: [CHOWN, DAC_OVERRIDE, FOWNER]
    security_opt: ["no-new-privileges:true"]
    volumes:
      - ./evolvyn/.local/vault.key:/source/vault.key:ro
      - agent_vault:/vault
    command:
      - python
      - -c
      - |
        import os
        from pathlib import Path
        source=Path('/source/vault.key').read_bytes();target=Path('/vault/vault.key')
        if target.exists() and target.read_bytes()!=source: raise SystemExit('Vault key mismatch; restore original key')
        if not target.exists():
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream: stream.write(source)
        os.chown(target,10001,10001);target.chmod(0o600)
  agents_api:
    networks: [agent_private, agent_compiler]
    build: ./evolvyn
    environment:
      OAUTH_GOOGLE_CLIENT_ID: ${AGENT_OAUTH_GOOGLE_CLIENT_ID:-}
      OAUTH_GOOGLE_CLIENT_SECRET: ${AGENT_OAUTH_GOOGLE_CLIENT_SECRET:-}
      OAUTH_GITHUB_CLIENT_ID: ${AGENT_OAUTH_GITHUB_CLIENT_ID:-}
      OAUTH_GITHUB_CLIENT_SECRET: ${AGENT_OAUTH_GITHUB_CLIENT_SECRET:-}
      APP_ENV: production
      EVOLVYN_COMPILER_URL: http://agents_compiler:8070
      EVOLVYN_AGENT_OUTPUT_TOKENS: ${AGENT_OUTPUT_TOKENS:-700}
      EVOLVYN_COMPILER_TOKEN: ${AGENT_COMPILER_TOKEN:?Run python scripts/prepare_product.py}
      DATABASE_URL: postgresql://evolvyn:${AGENT_POSTGRES_PASSWORD}@agents_db:5432/evolvyn
      EVOLVYN_ACCESS_TOKEN: ${AGENT_ACCESS_TOKEN:?Run python scripts/prepare_product.py}
      EVOLVYN_SESSION_COOKIE: ${AGENT_SESSION_COOKIE:?Run python scripts/prepare_product.py}
      EVOLVYN_VAULT_KEY_FILE: /run/evolvyn-secrets/vault.key
      PUBLIC_ORIGIN: http://localhost:3001
      ALLOWED_HOSTS: localhost,127.0.0.1
      COOKIE_SECURE: "0"
    volumes: [agent_vault:/run/evolvyn-secrets:ro]
    depends_on:
      agents_db: {condition: service_healthy}
      agents_vault_init: {condition: service_completed_successfully}
    healthcheck:
      test: [CMD, python, -c, "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"]
      interval: 5s
      timeout: 5s
      retries: 30
  agents_web:
    networks: [agent_private]
    build: ./evolvyn/frontend
    ports: [127.0.0.1:3001:80]
    depends_on:
      agents_api: {condition: service_healthy}
  agents_compiler:
    networks: [agent_compiler]
    build:
      context: ./evolvyn
      dockerfile: compiler/Dockerfile
    environment:
      EVOLVYN_COMPILER_TOKEN: ${AGENT_COMPILER_TOKEN:?Run python scripts/prepare_product.py}
    read_only: true
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    tmpfs: ["/tmp:size=32m,mode=1777"]
    mem_limit: 384m
    cpus: 1
    pids_limit: 64
'''

def attach(files):
    files.update(bundle())
    files['.dockerignore']='.git\n.env\n**/.env\n**/.local\nevolvyn\n**/node_modules\n**/__pycache__\n**/dist\n*.db\n'
    files['compose.yaml']=files['compose.yaml'].replace('\n  db:\n','\n  db:\n    networks: [product_private]\n').replace('\n  app:\n','\n  app:\n    networks: [product_private]\n')
    files['compose.yaml']=files['compose.yaml'].replace('volumes:\n  product_database:\n',SERVICES+'volumes:\n  product_database:\n  agent_database:\n  agent_vault:\n')
    files['compose.yaml']+='networks:\n  product_private:\n  agent_private:\n  agent_compiler:\n    internal: true\n'
    files['.gitignore']+='evolvyn/.local/\n'
    files['.env.example']+='AGENT_SESSION_COOKIE=evolvyn_agent_replace_with_unique_name\n'
    files['.env.example']+='AGENT_POSTGRES_PASSWORD=replace-with-a-different-long-random-password\nAGENT_ACCESS_TOKEN=replace-with-a-long-random-token\nAGENT_OAUTH_GOOGLE_CLIENT_ID=\nAGENT_OAUTH_GOOGLE_CLIENT_SECRET=\nAGENT_OAUTH_GITHUB_CLIENT_ID=\nAGENT_OAUTH_GITHUB_CLIENT_SECRET=\n'
    files['README.md']=files['README.md'].replace('1. Copy .env.example to .env and replace the database password.','1. Run python scripts/prepare_product.py to create private product and agent runtime configuration.')
    files['README.md']+='''
## Included Evolvyn agent runtime

Run `python scripts/prepare_product.py` before `docker compose up --build -d --wait`.
The product runs at http://localhost:8000 and its full agent console at http://localhost:3001.
Create a fresh private account in the console; it has its own database and sessions.
The source includes the same governed graph harness, bounded loops, LangGraph specialists,
MCP registry and gateway, typed tool ontology, per-agent model routing, encrypted vault,
reviewed memory, canvas, and growth review used by Evolvyn. No existing keys, models,
integrations, customer records, graph instances or deployment configuration are copied.
Evidence mode works without an API key. Configure keys and connectors in the new console.
Product records are not automatically sent to agents: upload authorized exports or connect
an explicitly authorized MCP adapter. Keep the two origins isolated in production and
configure TLS, OAuth callbacks, secrets, backups and resource limits before deployment.
The generated Compose stack separates product and agent private networks and database credentials.
To enable provider sign-in in the agent console, set AGENT_OAUTH_GOOGLE_CLIENT_ID/SECRET
or AGENT_OAUTH_GITHUB_CLIENT_ID/SECRET in the private root .env (use the full variable names
from .env.example). Register callbacks under http://localhost:3001/api/auth/oauth/{provider}/callback
for local use and use HTTPS callbacks for hosting.
Preserve evolvyn/.local/vault.key separately from database backups. Do not commit .env or .local.
Canvas labels and layouts are rendered as UI data; requested button actions and new domain
features still need project-specific implementation and acceptance tests.
'''
    return files
