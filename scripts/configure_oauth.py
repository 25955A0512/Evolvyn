"""Private OAuth setup. Standard library only; no secrets in CLI arguments or output."""
import argparse,getpass,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.oauth_config import public_origin
KEYS=('PUBLIC_ORIGIN','ALLOWED_HOSTS','COOKIE_SECURE','OAUTH_GOOGLE_CLIENT_ID','OAUTH_GOOGLE_CLIENT_SECRET','OAUTH_GITHUB_CLIENT_ID','OAUTH_GITHUB_CLIENT_SECRET')

def read_values(path):
    result={}
    for line in path.read_text().splitlines() if path.exists() else []:
        key,sep,value=line.partition('=')
        if sep and key in KEYS:
            value=value.strip()
            if value.startswith("'") and value.endswith("'"):value=value[1:-1].replace("\\'","'")
            result[key]=value
    return result

def write_private(path,updates):
    lines=path.read_text().splitlines() if path.exists() else []
    lines=[line for line in lines if line.partition('=')[0] not in updates]
    for key,value in updates.items():
        if any(c in value for c in ('\r','\n','\0',"'",'\\')):raise ValueError('Use the original Google/GitHub credentials without quotes, backslashes or line breaks')
        lines.append(key+"='"+value.replace("'","\\'")+"'")
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False,encoding='utf-8',newline='\n') as file:
            temporary=file.name;os.chmod(temporary,0o600);file.write('\n'.join(lines)+'\n')
        os.replace(temporary,path);os.chmod(path,0o600)
    finally:
        if temporary and os.path.exists(temporary):os.unlink(temporary)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',choices=['google','github']);parser.add_argument('--origin',help='Public HTTPS origin or local HTTP origin, never credentials')
    parser.add_argument('--check',action='store_true',help='Show setup readiness without secret values or external calls')
    args=parser.parse_args();path=Path(__file__).resolve().parents[1]/'.local/deploy.env';values=read_values(path)
    providers=[args.provider] if args.provider else ['google','github']
    if not args.check:
        if not sys.stdin.isatty():parser.error('Interactive setup requires a terminal for hidden secret input; use --check for automation')
        if not path.exists():parser.error('Run python scripts/prepare_deployment.py first')
        raw=args.origin or input('Evolvyn origin ['+values.get('PUBLIC_ORIGIN','http://localhost:3000')+']: ').strip() or values.get('PUBLIC_ORIGIN','http://localhost:3000')
        secure=raw.startswith('https://');origin=public_origin(raw,secure)
        from urllib.parse import urlsplit
        hosts=list(dict.fromkeys([*(values.get('ALLOWED_HOSTS','localhost,127.0.0.1').split(',')),urlsplit(origin).hostname]))
        updates={'PUBLIC_ORIGIN':origin,'COOKIE_SECURE':'1' if secure else '0','ALLOWED_HOSTS':','.join(hosts)}
        for provider in providers:
            print(provider.title()+' callback: '+origin+'/api/auth/oauth/'+provider+'/callback')
            client=input(provider.title()+' client ID: ').strip();secret=getpass.getpass(provider.title()+' client secret (hidden): ')
            if not client or not secret.strip():raise ValueError('Client ID and secret are required; nothing was saved')
            updates['OAUTH_'+provider.upper()+'_CLIENT_ID']=client;updates['OAUTH_'+provider.upper()+'_CLIENT_SECRET']=secret
        write_private(path,updates);values.update(updates)
        print('Private OAuth configuration saved. Recreate the API container to apply it:')
        print('docker compose --env-file .local/deploy.env up -d --force-recreate api')
    try:origin=public_origin(values.get('PUBLIC_ORIGIN','http://localhost:3000'),values.get('COOKIE_SECURE')=='1')
    except ValueError as error:print('Origin configuration blocked: '+str(error));return 1
    ready=True
    for provider in providers:
        configured=all(values.get('OAUTH_'+provider.upper()+'_'+suffix) for suffix in ('CLIENT_ID','CLIENT_SECRET'))
        print(provider.title()+': '+('configured, live sign-in still needs verification' if configured else 'OAuth client credentials missing'))
        print('Callback: '+origin+'/api/auth/oauth/'+provider+'/callback');ready&=configured
    print('Readiness checks do not contact providers or prove live authorization.')
    return 0 if ready else 1
if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,EOFError,KeyboardInterrupt):print('Setup cancelled or invalid; retry with valid single-line settings. No secret values displayed.',file=sys.stderr);sys.exit(1)
