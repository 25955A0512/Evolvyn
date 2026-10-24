"""Verify real API/proxy logs omit synthetic OAuth codes, state and query strings."""
import datetime,os,subprocess,time
from uuid import uuid4
import httpx
base=os.getenv('EVOLVYN_TEST_URL','http://localhost:3000')
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
code='synthetic-authorization-code-'+uuid4().hex
state='synthetic-state-'+uuid4().hex
response=httpx.get(base+'/api/auth/oauth/google/callback',params={'state':state,'code':code},follow_redirects=False,trust_env=False)
assert response.status_code==400 and code not in response.text and state not in response.text
assert len(response.headers.get('X-Request-ID',''))==32
time.sleep(.5)
result=subprocess.run(['docker','compose','--env-file','.local/deploy.env','logs','--since',start,'api','web'],check=True,capture_output=True,text=True)
assert code not in result.stdout and code not in result.stderr and state not in result.stdout and state not in result.stderr,'Synthetic OAuth marker appeared in access logs'
assert 'request_id' in result.stdout,'Expected safe request correlation metadata'
print('LIVE OAUTH LOG REDACTION PASS: code/state/query omitted from actual API and nginx logs; safe request ID retained')
