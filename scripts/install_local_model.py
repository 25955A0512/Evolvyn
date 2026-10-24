"""Install pinned official Qwen GGUF weights with authoritative LFS SHA-256 verification."""
import hashlib
import json
import os
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'.local/models'

def install():
    manifest=json.loads((ROOT/'config/local-model.json').read_text())
    repository,revision,filename,digest=[manifest[k] for k in ('repository','revision','filename','sha256')]
    TARGET.mkdir(parents=True,exist_ok=True);TARGET.chmod(0o755)
    output=TARGET/filename
    if output.exists():
        with output.open('rb') as file:valid=hashlib.file_digest(file,'sha256').hexdigest()==digest
        if valid:
            (TARGET/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            (TARGET/'manifest.json').chmod(0o644)
            print('Local model already verified');return
    temporary=output.with_suffix('.download');checksum=hashlib.sha256();received=0;last_report=0
    print(f'Fetching pinned Qwen model ({manifest["size"]//1_000_000} MB); SHA-256 will be verified before use',flush=True)
    with httpx.Client(timeout=120,follow_redirects=True) as client:
        with client.stream('GET',f'https://huggingface.co/{repository}/resolve/{revision}/{filename}',params={'download':'true'}) as response:
            response.raise_for_status()
            with temporary.open('wb') as file:
                for chunk in response.iter_bytes(1024*1024):
                    file.write(chunk);checksum.update(chunk);received+=len(chunk)
                    if received-last_report>=128*1024*1024:
                        print(f'Downloaded {received//1_000_000} MB',flush=True);last_report=received
    if received!=manifest['size'] or checksum.hexdigest()!=digest:
        temporary.unlink(missing_ok=True);raise ValueError('Model integrity check failed; artifact rejected')
    os.replace(temporary,output);output.chmod(0o644)
    (TARGET/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (TARGET/'manifest.json').chmod(0o644)
    print('Local model downloaded and checksum verified',flush=True)

if __name__=='__main__':
    import sys
    try:install()
    except httpx.HTTPError:
        print('Model download unavailable. Allow huggingface.co and us.aws.cdn.hf.co in environment settings, then rerun this installer.',file=sys.stderr)
        sys.exit(2)
