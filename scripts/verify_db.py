"""Verifica conexión y estado Alembic (sin imprimir contraseñas)."""
from __future__ import annotations

import re
import sys

from sqlalchemy import create_engine, text

from database.db_url import build_database_url, get_sqlalchemy_connect_args


def _mask_url(url: str) -> str:
    base, _, qs = url.partition("?")
    masked = re.sub(r":([^:@/]+)@", ":***@", base)
    return f"{masked}?{qs}" if qs else masked


def main() -> int:
    url = build_database_url()
    print("URL:", _mask_url(url))
    print("Neon:", "neon.tech" in url)
    print("Host mode:", "cloudsql" in url or "host.docker.internal" in url or "localhost" in url)

    try:
        args = {**get_sqlalchemy_connect_args(), "connect_timeout": 15}
        engine = create_engine(url, pool_pre_ping=True, connect_args=args)
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version()")).scalar() or ""
            print("Status: OK")
            print("PostgreSQL:", ver[:80])
            try:
                rev = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
                print("Alembic revision:", rev or "(sin fila)")
            except Exception:
                print("Alembic revision: (tabla alembic_version no existe)")
            n = conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).scalar()
            print("Tablas public:", n)
    except Exception as exc:
        print("Status: FAIL")
        print("Error:", type(exc).__name__, str(exc)[:240])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
