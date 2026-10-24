#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
mkdir -p .local/llama
archive=.local/llama/runtime.tar.gz
if [ ! -f "$archive" ]; then
  curl --fail --location --silent --show-error --max-time 120 https://github.com/ggml-org/llama.cpp/releases/download/b11840/llama-b11840-bin-ubuntu-x64.tar.gz -o "$archive"
fi
printf '%s\n' '5f6e72e772a1264df279d6b7a848570fdc00e5d968b72e7a917d19e07da96400  .local/llama/runtime.tar.gz' | sha256sum --check
tar -xzf "$archive" -C .local/llama

chmod -R a+rX .local/llama/llama-b11840
# Public runtime dependencies supplied by the trusted execution image for offline containers.
python3 - <<'PY'
from pathlib import Path
import shutil,hashlib,json
runtime=Path('.local/llama/llama-b11840')
manifest={}
for name in ('libgomp.so.1','libzstd.so.1'):
    source=Path('/lib/x86_64-linux-gnu')/name
    if source.exists():
        shutil.copy2(source,runtime/name)
        (runtime/name).chmod(0o644)
        with source.open('rb') as file:manifest[name]=hashlib.file_digest(file,'sha256').hexdigest()
(runtime/'system-libraries.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
