"""A fixed private compiler endpoint; generated JavaScript is never executed in the API."""
import os,re
import httpx

async def compile_frontend(files):
    url=os.getenv('EVOLVYN_COMPILER_URL','')
    if not url and os.getenv('EVOLVYN_COMPILER_HOSTPORT'):
        hostport=os.environ['EVOLVYN_COMPILER_HOSTPORT']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*:[0-9]{1,5}',hostport) or not 1<=int(hostport.rsplit(':',1)[1])<=65535:
            return {'status':'unavailable','detail':'Private compiler address is invalid'}
        url='http://'+hostport
    if not url:return {'status':'unavailable','detail':'No isolated compiler configured; source/contract validation only'}
    # Operator configuration only; neither a model nor a product supplies destinations.
    # Source-only files under src; dependency scripts and arbitrary paths never run.
    def allowed(path):
        value=path.removeprefix('frontend/src/')
        return path.startswith('frontend/src/') and re.fullmatch(r'[A-Za-z0-9_./-]+',value) and all(part not in ('.','..','') for part in value.split('/')) and value.endswith(('.js','.jsx','.ts','.tsx','.css','.json'))
    inputs={k.removeprefix('frontend/src/'):v for k,v in files.items() if allowed(k)}
    try:
        async with httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False) as client:
            response=await client.post(url.rstrip('/')+'/compile',json={'files':inputs},headers={'X-Compiler-Token':os.getenv('EVOLVYN_COMPILER_TOKEN','')})
            response.raise_for_status();result=response.json()
        if result.get('status') not in ('passed','failed'):raise ValueError('Invalid compiler receipt')
        if result['status']=='passed':
            if not re.fullmatch('[0-9a-f]{64}',str(result.get('sha256',''))) or type(result.get('bytes')) is not int or not 0<result['bytes']<=4_000_000:raise ValueError('Incomplete compiler receipt')
        return {k:v for k,v in result.items() if k in ('status','checks','bytes','sha256','detail')}
    except Exception:return {'status':'unavailable','detail':'Compiler connection or receipt unavailable; no successful compilation was inferred'}
