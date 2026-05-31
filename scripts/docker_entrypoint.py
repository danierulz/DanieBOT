#!/usr/bin/env python3
"""Arranque Cloud Run: migraciones DB y luego Uvicorn en PORT."""
from __future__ import annotations

import logging
import os
import sys


def _log_cloud_sql_diagnostics(log: logging.Logger) -> None:
    conn = os.getenv("CLOUD_SQL_CONNECTION_NAME", "").strip()
    if not conn:
        log.info("CLOUD_SQL_CONNECTION_NAME no definido (conexión TCP vía DB_HOST).")
        return
    sock = f"/cloudsql/{conn}/.s.PGSQL.5432"
    log.info(
        "Cloud SQL: connection=%s socket=%s existe=%s",
        conn,
        sock,
        os.path.exists(sock),
    )
    if not os.path.exists(sock):
        log.error(
            "Socket Cloud SQL ausente. Revisá --add-cloudsql-instances en el deploy "
            "y rol Cloud SQL Client en la cuenta de servicio de Cloud Run."
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("entrypoint")

    _log_cloud_sql_diagnostics(log)
    log.info("Aplicando migraciones y seeds de referencia...")

    try:
        from database.run_migrations import apply_migrations_and_seed

        apply_migrations_and_seed()
    except Exception:
        log.exception("Fallo al migrar la base de datos; no se inicia el servidor.")
        sys.exit(1)

    os.environ["DB_MIGRATIONS_DONE"] = "1"

    port = os.getenv("PORT", "8080")
    host = "0.0.0.0"
    log.info("Iniciando uvicorn en %s:%s", host, port)

    os.execvp(
        "uvicorn",
        ["uvicorn", "main:app", "--host", host, "--port", str(port)],
    )


if __name__ == "__main__":
    main()
