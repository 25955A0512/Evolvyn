"""Local Compose/nginx validation only. Does not create or test AWS resources."""
import json,os,subprocess,tempfile,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));os.chdir(root)
from scripts.configure_oauth import write_private,read_values
runtime={**os.environ,'DOCKER_CONFIG':str(root/'.local/cache/docker'),'EVOLVYN_TRUSTED_PROXY_CIDR':'172.31.0.0/16'}
def run(command):return subprocess.run(command,env=runtime,capture_output=True,check=True)
config=json.loads(run(['docker','compose','--env-file','.local/deploy.env','-f','compose.yaml','-f','compose.aws.yaml','config','--format','json']).stdout)
ports=config['services']['web']['ports'];assert len(ports)==1 and str(ports[0]['published'])=='8080' and ports[0]['host_ip']=='0.0.0.0'
assert all(not config['services'][name].get('ports') for name in ('api','db','compiler'))
with tempfile.TemporaryDirectory(dir=root/'.local') as temp:
    folder=Path(temp);env=folder/'config.env';compose=folder/'compose.yaml';value='controlled$#literal'
    write_private(env,{'OAUTH_GOOGLE_CLIENT_SECRET':value});assert read_values(env)['OAUTH_GOOGLE_CLIENT_SECRET']==value
    compose.write_text('services:\n  test:\n    image: nginx:1.28-alpine\n    environment:\n      VALUE: ${OAUTH_GOOGLE_CLIENT_SECRET}\n')
    result=json.loads(run(['docker','compose','--env-file',str(env),'-f',str(compose),'config','--format','json']).stdout)
    assert result['services']['test']['environment']['VALUE'].replace('$$','$')==value
    # Only replace upstream DNS so nginx -t can run with no network or API container.
    text=(root/'deploy/nginx.aws.conf.template').read_text().replace('${EVOLVYN_TRUSTED_PROXY_CIDR}','172.31.0.0/16').replace('http://api:8000','http://127.0.0.1:8000')
    conf=folder/'nginx.conf';conf.write_text(text)
    run(['docker','run','--rm','--network','none','-v',str(conf)+':/etc/nginx/conf.d/default.conf:ro','nginx:1.28-alpine','nginx','-t'])
print('AWS CONFIG PASS: one ALB-facing web port, private API/database/compiler, nginx syntax, literal private configuration. No AWS resources provisioned or live OAuth claimed.')
