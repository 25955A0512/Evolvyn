"""Reject missing or modified model weights before starting inference."""
import hashlib
import json
import os
from pathlib import Path

def verify(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['filename']!='qwen2.5-1.5b-instruct-q4_k_m.gguf':raise ValueError('Unexpected model identity')
    expected=manifest['sha256']
    if len(expected)!=64:raise ValueError('Missing model checksum')
    with (directory/manifest['filename']).open('rb') as file:
        if hashlib.file_digest(file,'sha256').hexdigest()!=expected:raise ValueError('Model checksum mismatch')
    return True

if __name__=='__main__':
    import sys
    try:verify(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'.local/models')
    except (OSError,ValueError,KeyError):
        print('Local model unavailable or verification failed; run the verified model installer.',file=sys.stderr)
        sys.exit(1)
    print('Local model checksum verified')
