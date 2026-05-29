#!/usr/bin/env python3
"""Arranque Cloud Run: migraciones DB y luego Uvicorn en PORT."""
from __future__ import annotations

import logging
import os
import sys


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("entrypoint")

    log.info("Aplicando migraciones y seeds de referencia...")
    os.environ["DB_MIGRATIONS_DONE"] = "1"

    try:
        from database.run_migrations import apply_migrations_and_seed

        apply_migrations_and_seed()
    except Exception:
        log.exception("Fallo al migrar la base de datos; no se inicia el servidor.")
        sys.exit(1)

    port = os.getenv("PORT", "8080")
    host = "0.0.0.0"
    log.info("Iniciando uvicorn en %s:%s", host, port)

    os.execvp(
        "uvicorn",
        ["uvicorn", "main:app", "--host", host, "--port", str(port)],
    )


if __name__ == "__main__":
    main()
