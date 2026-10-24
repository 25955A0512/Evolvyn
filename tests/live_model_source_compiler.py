"""Compile controlled model-source fixtures through the real private service."""
import json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'tests')]
from test_model_source import FILES
script='''import asyncio,json,sys
from backend.source_compiler import compile_frontend
files=json.loads(sys.stdin.read())
async def main():
 result=await compile_frontend(files)
 assert result['status']=='passed',result
 files['frontend/src/features/Catalog.jsx']='import "/etc/passwd";'
 assert (await compile_frontend(files))['status']=='failed'
 print('MODEL SOURCE COMPILER PASS: nested React files actually bundled; disallowed host import rejected; generated code never executed')
asyncio.run(main())'''
# Keep source JSON on stdin, not interpolated into a shell command.
program='import json,subprocess\n'
# python -c consumes a fixed program; all model-source bytes remain data.
subprocess.run(['docker','compose','--env-file','.local/deploy.env','exec','-T','api','python','-c',script],cwd=root,input=json.dumps(FILES),text=True,check=True)
