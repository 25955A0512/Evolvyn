"""Set a public Render API rewrite. Public origins only; no account tokens required."""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.oauth_config import public_origin

SPA={'source':'/((?!api).*)','destination':'/index.html'}

def api_origin(value):
    origin=public_origin(value,True);parsed=urlsplit(origin)
    if parsed.scheme!='https' or not parsed.hostname.endswith('.onrender.com') or parsed.port not in (None,443):
        raise ValueError('Use the actual Render HTTPS service URL ending in .onrender.com, with no path or credentials')
    return origin

def configure(config,origin):
    origin=api_origin(origin)
    return {**config,'rewrites':[{'source':'/api/:path*','destination':origin+'/api/:path*'},SPA]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-origin',help='Public HTTPS URL copied from the Render API service')
    parser.add_argument('--check',action='store_true',help='Check routing without changing files or contacting providers')
    args=parser.parse_args();path=Path(__file__).resolve().parents[1]/'frontend/vercel.json';config=json.loads(path.read_text())
    try:
        if args.api_origin and not args.check:
            config=configure(config,args.api_origin);path.write_text(json.dumps(config,indent=2)+'\n')
            print('Saved the public Render API rewrite. Commit frontend/vercel.json and redeploy Vercel.')
        route=next((r for r in config['rewrites'] if r['source']=='/api/:path*'),None)
        if not route:print('API proxy is not configured yet. Run with --api-origin after Render assigns the API URL.');return 1
        origin=api_origin(route['destination'].removesuffix('/api/:path*'))
        if config['rewrites'][0]!=route or config['rewrites'][-1]!=SPA:raise ValueError('API routing must precede the SPA fallback')
        print('API proxy configured for '+origin+'. This is a configuration check, not a live deployment test.')
        return 0
    except ValueError as error:print(str(error),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
