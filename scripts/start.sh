#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
source .local/runtime.env
if ! docker container inspect evolvyn-db >/dev/null 2>&1; then
  bash scripts/install.sh
fi
docker start evolvyn-db >/dev/null
for attempt in {1..30}; do
  if docker exec evolvyn-db pg_isready -U evolvyn >/dev/null; then break; fi
  sleep 1
done
model_pid=''
if [ -f .local/models/qwen2.5-1.5b-instruct-q4_k_m.gguf ] && [ -x .local/llama/llama-b11840/llama-server ]; then
  bash scripts/start_local_model.sh >.local/model.log 2>&1 &
  model_pid=$!
fi
.venv/bin/uvicorn backend.app:app --no-access-log --host 127.0.0.1 --port 8000 &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true; if [ -n "$model_pid" ]; then kill "$model_pid" 2>/dev/null || true; fi' EXIT INT TERM
for attempt in {1..30}; do
  if ! kill -0 "$backend_pid" 2>/dev/null; then wait "$backend_pid"; exit 1; fi
  if curl --fail --silent http://127.0.0.1:8000/api/health >/dev/null; then break; fi
  sleep 1
done
kill -0 "$backend_pid"
curl --fail --silent http://127.0.0.1:8000/api/health >/dev/null
npm --prefix frontend run dev
