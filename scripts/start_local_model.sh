#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
model=.local/models/qwen2.5-1.5b-instruct-q4_k_m.gguf
if [ ! -f "$model" ]; then
  echo 'Local model is not installed. Run .venv/bin/python scripts/install_local_model.py after allowing the model download domains.' >&2
  exit 1
fi
.venv/bin/python scripts/verify_local_model.py .local/models
binary=$(find .local/llama -type f -name llama-server -print -quit)
if [ -z "$binary" ]; then echo 'Run bash scripts/install_local_runtime.sh first.' >&2; exit 1; fi
exec "$binary" --model "$model" --host 127.0.0.1 --port 8081 --alias qwen2.5-1.5b-instruct --threads 4 --ctx-size 4096 --parallel 1 --n-predict 1536
