#!/usr/bin/env bash
# Bootstrap DB local: Postgres + Alembic + seeds.
# Uso: ./scripts/dev-init.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.dev ]]; then
  echo "Falta .env.dev en la raíz del proyecto." >&2
  exit 1
fi

echo ">> Levantando Postgres (db)..."
docker compose up -d db

ready=0
for i in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U daniebot -d daniebot_dev >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" -ne 1 ]]; then
  echo "Postgres no respondió a tiempo. Revisá: docker compose logs db" >&2
  exit 1
fi

echo ">> Alembic upgrade head..."
docker compose run --rm app python -m alembic upgrade head

echo ">> Seeds (talles, categorías)..."
docker compose run --rm app python -c "from database.init_db import seed_reference_data; seed_reference_data()"

echo ""
echo "Listo. Arrancá la app con:"
echo "  docker compose up app"
echo "  http://localhost:5000"
