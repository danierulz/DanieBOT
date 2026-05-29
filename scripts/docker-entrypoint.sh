#!/bin/sh
set -e

echo "[entrypoint] Aplicando migraciones y seeds de referencia..."
python -c "from database.run_migrations import apply_migrations_and_seed; apply_migrations_and_seed()"

echo "[entrypoint] Iniciando servidor..."
exec "$@"
