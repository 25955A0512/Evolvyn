#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [ -z "${DOCKER_CONFIG:-}" ] && [ ! -w "$HOME" ]; then export DOCKER_CONFIG="$PWD/.local/cache/docker"; fi
bash scripts/build_containers.sh
docker compose --env-file .local/deploy.env -f compose.yaml -f compose.offline.yaml up -d --no-build --wait
if [ -s .local/production-data.sql ]; then
  empty=$(docker compose --env-file .local/deploy.env exec -T db psql -U evolvyn -d evolvyn -Atc 'SELECT (SELECT count(*) FROM records)+(SELECT count(*) FROM accounts)')
  if [ "$empty" = 0 ]; then
    docker compose --env-file .local/deploy.env exec -T db psql -U evolvyn -d evolvyn -v ON_ERROR_STOP=1 < .local/production-data.sql
  fi
fi
curl --fail --silent http://127.0.0.1:3000/api/health
