"""
Aplica migraciones Alembic al arrancar el contenedor (Cloud Run / Docker).

Usa un advisory lock de PostgreSQL para que varias instancias en frío no
corran upgrade en paralelo. Idempotente: si ya está en head, no hace nada.
"""
from __future__ import annotations

import logging
import os
import sys

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from database.db_url import build_database_url

logger = logging.getLogger(__name__)

# Lock estable para migraciones (evitar colisiones entre réplicas Cloud Run)
_MIGRATION_LOCK_ID = 73482901


def _migrations_disabled() -> bool:
    if os.getenv("SKIP_DB_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        return True
    # Tests unitarios usan SQLite en memoria; no aplicar Alembic contra Postgres ficticio
    if "unittest" in sys.modules and not os.getenv("FORCE_DB_MIGRATIONS"):
        return True
    return False


def _current_revision(connection) -> str | None:
    context = MigrationContext.configure(connection)
    return context.get_current_revision()


def apply_pending_migrations() -> None:
    """Ejecuta `alembic upgrade head` si hace falta. Seguro llamar en cada deploy."""
    if _migrations_disabled():
        logger.info("SKIP_DB_MIGRATIONS activo — no se aplican migraciones.")
        return

    url = build_database_url()
    if not url or "://" not in url:
        logger.warning("Sin DATABASE_URL / DB_* — se omiten migraciones.")
        return

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()

    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            current = _current_revision(conn)
            if current == head:
                logger.info("Base de datos ya en revisión Alembic %s (head).", head)
                return

            logger.info(
                "Migrando base de datos: %s → %s",
                current or "(sin alembic_version)",
                head,
            )
            # Bloqueo: si varias instancias arrancan a la vez, una migra y el resto espera
            conn.execute(
                text("SELECT pg_advisory_lock(:id)"),
                {"id": _MIGRATION_LOCK_ID},
            )
            conn.commit()
            try:
                command.upgrade(cfg, "head")
                logger.info("Migraciones Alembic aplicadas correctamente (head=%s).", head)
            finally:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:id)"),
                    {"id": _MIGRATION_LOCK_ID},
                )
                conn.commit()
    finally:
        engine.dispose()


def apply_migrations_and_seed() -> None:
    """Migraciones + datos de referencia (talles, colores, categorías) si faltan."""
    apply_pending_migrations()
    try:
        from database.init_db import seed_reference_data

        seed_reference_data()
    except Exception as e:
        logger.warning("Seed de referencia no completado (no crítico): %s", e)
