"""Actual local API/compiler processes with Render-style configuration; no cloud deployment claim."""
import json,os,secrets,shutil,socket,subprocess,sys,tempfile,time
from pathlib import Path
from uuid import uuid4
import httpx,psycopg
from cryptography.fernet import Fernet
from psycopg import sql
from psycopg.conninfo import make_conninfo
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));os.chdir(root)
out=root/'.local/validation';out.mkdir(parents=True,exist_ok=True)
database=os.getenv('DATABASE_URL','postgresql://evolvyn@127.0.0.1:5432/evolvyn');schema='managed_'+uuid4().hex
with psycopg.connect(database) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
processes=[];logs=[]
try:
    port=free_port();env={**os.environ,'PORT':str(port),'RENDER':'true','RENDER_EXTERNAL_HOSTNAME':'controlled-api.onrender.com','PUBLIC_ORIGIN':'https://controlled-app.vercel.app','COOKIE_SECURE':'1','APP_ENV':'production','EVOLVYN_SESSION_COOKIE':'__Host-evolvyn_session','EVOLVYN_VAULT_SEED':secrets.token_urlsafe(48),'EVOLVYN_ACCESS_TOKEN':secrets.token_urlsafe(32),'DATABASE_URL':make_conninfo(database,options='-c search_path='+schema)}
    env.pop('EVOLVYN_VAULT_MASTER_KEY',None);env.pop('EVOLVYN_VAULT_KEY_FILE',None)
    log=(out/'managed-api.log').open('w');logs.append(log)
    api=subprocess.Popen([sys.executable,'scripts/container_start.py'],env=env,stdout=log,stderr=log);processes.append(api)
    with httpx.Client(trust_env=False,timeout=2) as client:
        for _ in range(100):
            if api.poll() is not None:raise AssertionError('Managed API failed; inspect private process log')
            try:
                if client.get(f'http://127.0.0.1:{port}/api/health').status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.2)
        response=client.get(f'http://127.0.0.1:{port}/api/health',headers={'Host':'controlled-api.onrender.com'});assert response.status_code==200 and response.json()['status']=='ok'
        assert client.get(f'http://127.0.0.1:{port}/api/health',headers={'Host':'controlled-app.vercel.app'}).status_code==200
        assert client.get(f'http://127.0.0.1:{port}/api/health',headers={'Host':'untrusted.example'}).status_code==400
        providers=client.get(f'http://127.0.0.1:{port}/api/auth/providers').json()
        assert all(p['setup']['callback_url'].startswith('https://controlled-app.vercel.app/api/auth/oauth/') for p in providers)
        auth={'Authorization':'Bearer '+env['EVOLVYN_ACCESS_TOKEN'],'X-Requested-With':'Evolvyn'}
        controlled_key='controlled-not-live-'+uuid4().hex
        created=client.post(f'http://127.0.0.1:{port}/api/vault/credentials',headers=auth,json={'name':'Controlled restart acceptance','provider':'gemini','value':controlled_key})
        assert created.status_code==200 and controlled_key not in created.text
        credential_id=created.json()['id']
    api.terminate();api.wait(timeout=20);processes.remove(api)
    api=subprocess.Popen([sys.executable,'scripts/container_start.py'],env=env,stdout=log,stderr=log);processes.append(api)
    with httpx.Client(trust_env=False,timeout=2) as client:
        for _ in range(100):
            if api.poll() is not None:raise AssertionError('API restart failed; inspect private process log')
            try:
                if client.get(f'http://127.0.0.1:{port}/api/health').status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.2)
        vault=client.get(f'http://127.0.0.1:{port}/api/vault',headers=auth)
        assert vault.status_code==200 and controlled_key not in vault.text and credential_id in vault.text
        with psycopg.connect(make_conninfo(database,options='-c search_path='+schema)) as c:
            encrypted=c.execute("SELECT body->>'ciphertext' FROM records WHERE id=%s",(credential_id,)).fetchone()[0]
        from scripts.container_start import runtime_environment
        master=runtime_environment(env)['EVOLVYN_VAULT_MASTER_KEY']
        stored=json.loads(Fernet(master).decrypt(encrypted.encode()))
        assert stored['value']==controlled_key and stored['id']==credential_id and stored['owner']=='initial-workspace'
    with tempfile.TemporaryDirectory(dir=root/'.local') as temp:
        folder=Path(temp);shutil.copy2(root/'compiler/server.mjs',folder/'server.mjs');(folder/'node_modules').symlink_to(root/'frontend/node_modules',target_is_directory=True)
        compiler_port=free_port();token=secrets.token_urlsafe(32);compiler_env={**os.environ,'PORT':str(compiler_port),'EVOLVYN_COMPILER_TOKEN':token}
        log=(out/'managed-compiler.log').open('w');logs.append(log)
        compiler=subprocess.Popen(['node',str(folder/'server.mjs')],env=compiler_env,stdout=log,stderr=log);processes.append(compiler)
        with httpx.Client(trust_env=False,timeout=5) as client:
            for _ in range(100):
                if compiler.poll() is not None:raise AssertionError('Managed compiler failed; inspect private process log')
                try:
                    if client.get(f'http://127.0.0.1:{compiler_port}/health').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.2)
            url=f'http://127.0.0.1:{compiler_port}/compile'
            assert client.post(url,json={'files':{'main.jsx':'export default ()=>null'}}).status_code==403
            r=client.post(url,headers={'X-Compiler-Token':token},json={'files':{'main.jsx':'export default ()=>null'}})
            assert r.status_code==200 and r.json()['status']=='passed' and r.json()['bytes']>0
        compiler.terminate();compiler.wait(timeout=10);processes.remove(compiler)
    invalid=subprocess.run([sys.executable,'scripts/container_start.py'],env={**os.environ,'PORT':'invalid'},capture_output=True)
    assert invalid.returncode!=0
    print('MANAGED HOSTING PASS: actual API/compiler honor assigned ports; SQL health, exact host allowlist, HTTPS callbacks, encrypted vault retained/decrypted after API restart, compiler authentication/compilation, nonzero invalid configuration and clean shutdown. No Vercel/Render resources or live OAuth tested.')
finally:
    for process in reversed(processes):
        process.terminate()
        try:process.wait(timeout=20)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    for log in logs:log.close()
    with psycopg.connect(database) as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
