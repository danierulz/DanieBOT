#!/usr/bin/env bash
# Migración de datos Cloud SQL → Neon.
# Ejecutar donde haya acceso a Cloud SQL (Cloud Shell, VM con VPC, o con proxy).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Credenciales: Python carga .env (evita problemas con $ en contraseñas).

CLOUD_SQL_INSTANCE="${CLOUD_SQL_CONNECTION_NAME:-laslocaswhatsapp:us-central1:laslocas-dbng}"
PROXY_PORT="${CLOUD_SQL_PROXY_PORT:-5433}"
PROXY_PID=""

cleanup() {
  if [[ -n "$PROXY_PID" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
    kill "$PROXY_PID" 2>/dev/null || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

start_proxy_if_needed() {
  local host="${DB_HOST:-}"
  if [[ "$host" == 127.0.0.1 ]] || [[ "$host" == localhost ]]; then
    return 0
  fi
  if [[ "$host" == *":"*":"* ]] && [[ "$host" != *.* ]]; then
    export CLOUD_SQL_CONNECTION_NAME="$host"
  fi
  if [[ -n "${SOURCE_DATABASE_URL:-}" ]]; then
    return 0
  fi
  if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo ">> Usando IP privada DB_HOST=$host (requiere red/VPC)."
    return 0
  fi

  if ! command -v cloud-sql-proxy >/dev/null 2>&1; then
    echo "cloud-sql-proxy no instalado. En Cloud Shell:"
    echo "  curl -o cloud-sql-proxy -L https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.3/cloud-sql-proxy.linux.amd64"
    echo "  chmod +x cloud-sql-proxy && sudo mv cloud-sql-proxy /usr/local/bin/"
    exit 1
  fi

  echo ">> Iniciando Cloud SQL Auth Proxy en 127.0.0.1:${PROXY_PORT} ..."
  cloud-sql-proxy "$CLOUD_SQL_INSTANCE" --port "$PROXY_PORT" &
  PROXY_PID=$!
  sleep 3

  export DB_HOST=127.0.0.1
  export DB_PORT="$PROXY_PORT"
}

METHOD="${1:-pg_dump}"
shift || true

start_proxy_if_needed

if [[ -z "${TARGET_DATABASE_URL:-}" ]] && [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: Definí TARGET_DATABASE_URL o DATABASE_URL (Neon pooler)." >&2
  exit 1
fi

case "$METHOD" in
  verify)
    exec python3 scripts/migrate_cloudsql_to_neon.py --verify-only "$@"
    ;;
  copy)
    exec python3 scripts/migrate_cloudsql_to_neon.py --method copy "$@"
    ;;
  pg_dump|*)
    exec python3 scripts/migrate_cloudsql_to_neon.py --method pg_dump "$@"
    ;;
esac
