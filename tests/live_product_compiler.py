"""Verify actual private compiler protocol, imports and failure receipts."""
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
script=r'''
import asyncio,httpx,os
from backend.product_templates import generate
from backend.product_studio import QUESTIONS,parsed_answer
from backend.source_compiler import compile_frontend
async def main():
 spec={key:parsed_answer(key,answer) for key,_,answer in QUESTIONS}
 for stack in ('react_fastapi','react_express'):
  files=generate({**spec,'stack':stack,'name':'Synthetic compiler validation','goal':'Verify emitted source','experience':{'headline':'Private records','description':'An explicit synthetic acceptance product','sections':[]}})
  result=await compile_frontend(files)
  assert result['status']=='passed',result
  assert result['sha256'] and result['bytes']>0
  files['frontend/src/main.jsx']='not valid javascript !!!'
  assert (await compile_frontend(files))['status']=='failed'
 async with httpx.AsyncClient(trust_env=False) as client:
  url=os.environ['EVOLVYN_COMPILER_URL']+'/compile'
  assert (await client.post(url,json={'files':{'main.jsx':'export default 1'}})).status_code==403
  headers={'X-Compiler-Token':os.environ['EVOLVYN_COMPILER_TOKEN']}
  for files in ({'main.jsx':'import "/etc/passwd"'}, {'main.jsx':'export default 1','../escape':'x'}):
   result=await client.post(url,headers=headers,json={'files':files})
   assert result.json()['status']=='failed',result.text
 print('Actual isolated compiler: both emitted stacks, syntax failures, unauthorized and disallowed imports/paths PASS')
asyncio.run(main())
'''
subprocess.run(['docker','compose','--env-file','.local/deploy.env','exec','-T','api','python','-'],cwd=root,input=script,text=True,check=True)
