#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [ -z "${DOCKER_CONFIG:-}" ] && [ ! -w "$HOME" ]; then export DOCKER_CONFIG="$PWD/.local/cache/docker"; fi
umask 077
mkdir -p .local
if [ "$(docker container inspect --format '{{.State.Running}}' evolvyn-db 2>/dev/null || true)" = true ]; then
  docker exec evolvyn-db pg_dump -U evolvyn -d evolvyn --no-owner --no-acl > .local/database.sql.tmp
  mv .local/database.sql.tmp .local/database.sql
fi
if [ -f .local/deploy.env ] && [ -n "$(docker compose --env-file .local/deploy.env ps -q db)" ]; then
  docker compose --env-file .local/deploy.env exec -T db pg_dump -U evolvyn -d evolvyn --data-only --no-owner --no-acl > .local/production-data.sql.tmp
  mv .local/production-data.sql.tmp .local/production-data.sql
fi
