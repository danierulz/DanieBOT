#!/usr/bin/env python3
"""Arranque Cloud Run: migraciones DB y luego Uvicorn en PORT."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _log_db_diagnostics(log: logging.Logger) -> None:
    from database.db_url import build_database_url

    url = build_database_url()
    if not url or "://" not in url:
        log.error(
            "Sin DATABASE_URL (secreto en Cloud Run). "
            "Creá DATABASE_URL en Secret Manager con la URL pooler de Neon "
            "(postgresql+psycopg2://user:pass@ep-...-pooler....neon.tech/NOMBRE_DB?sslmode=require). "
            "DB_USER/DB_PASSWORD por separado ya no se usan."
        )
        return

    host_part = url.split("@")[-1].split("?")[0] if "@" in url else "(mal formada)"
    log.info("DATABASE_URL configurada → %s", host_part)

    conn = os.getenv("CLOUD_SQL_CONNECTION_NAME", "").strip()
    if conn:
        sock = f"/cloudsql/{conn}/.s.PGSQL.5432"
        log.info("Cloud SQL socket %s existe=%s", sock, os.path.exists(sock))


def _preflight_db(log: logging.Logger) -> None:
    """Conexión rápida antes de migrar (falla claro si el secreto está mal)."""
    from sqlalchemy import create_engine, text

    from database.db_url import build_database_url, get_sqlalchemy_connect_args

    url = build_database_url()
    if not url or "://" not in url:
        if os.getenv("K_SERVICE"):
            raise RuntimeError("DATABASE_URL ausente en Cloud Run")
        log.warning("Sin DATABASE_URL — migraciones omitidas.")
        return

    args = get_sqlalchemy_connect_args()
    args.setdefault("connect_timeout", 15)
    engine = create_engine(url, pool_pre_ping=True, connect_args=args)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("Conexión a base de datos OK.")
    finally:
        engine.dispose()


def main() -> None:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("entrypoint")

    _log_db_diagnostics(log)

    try:
        _preflight_db(log)
        log.info("Aplicando migraciones y seeds de referencia...")
        from database.run_migrations import apply_migrations_and_seed

        apply_migrations_and_seed()
    except Exception:
        log.exception(
            "Fallo al conectar o migrar la base de datos; no se inicia el servidor. "
            "Revisá el secreto DATABASE_URL (URL completa, contraseña URL-encoded si tiene @#$)."
        )
        sys.exit(1)

    os.environ["DB_MIGRATIONS_DONE"] = "1"

    port = os.getenv("PORT", "8080")
    host = "0.0.0.0"
    log.info("Iniciando uvicorn en %s:%s", host, port)

    os.execvp(
        "uvicorn",
        ["uvicorn", "main:app", "--host", host, "--port", str(port), "--app-dir", str(ROOT)],
    )


if __name__ == "__main__":
    main()
