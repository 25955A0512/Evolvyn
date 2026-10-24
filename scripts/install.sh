#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.local/cache/uv}"
uv venv --allow-existing .venv
uv pip sync --python .venv/bin/python requirements.lock --require-hashes
npm --cache "$PWD/.local/cache/npm" --prefix frontend ci --no-audit --no-fund
npm --prefix frontend run build
mkdir -p .local
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets
p=Path('.local/runtime.env')
if not p.exists():
    p.write_text('export EVOLVYN_ACCESS_TOKEN='+secrets.token_urlsafe(32)+'\n')
    p.chmod(0o600)
PY
bash scripts/install_local_runtime.sh
if [ "${EVOLVYN_SKIP_LOCAL_MODEL:-0}" != 1 ] && [ ! -s .local/models/qwen2.5-1.5b-instruct-q4_k_m.gguf ]; then
  if ! .venv/bin/python scripts/install_local_model.py; then
    echo 'Local model weights remain unavailable; the application can run its labeled evidence-only fallback.' >&2
  fi
fi
# Local development container only. Trust auth is bound exclusively to loopback.
if ! docker container inspect evolvyn-db >/dev/null 2>&1; then
  docker run -d --name evolvyn-db -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=evolvyn -e POSTGRES_DB=evolvyn -p 127.0.0.1:5432:5432 postgres:17@sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe
else
  docker start evolvyn-db >/dev/null
fi
for attempt in {1..30}; do
  if docker exec evolvyn-db pg_isready -U evolvyn >/dev/null; then
    if [ -f .local/database.sql ] && [ "$(docker exec evolvyn-db psql -U evolvyn -d evolvyn -Atc "SELECT to_regclass('public.records') IS NULL")" = t ]; then
      docker exec -i evolvyn-db psql -U evolvyn -d evolvyn -v ON_ERROR_STOP=1 < .local/database.sql
    fi
    exit 0
  fi
  sleep 1
done
exit 1
