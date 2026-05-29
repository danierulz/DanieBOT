"""
Aplica migraciones Alembic al arrancar el contenedor (Cloud Run / Docker).

Idempotente: si ya está en head, sale en segundos. Timeouts cortos para no
bloquear el arranque de Cloud Run.
"""
from __future__ import annotations

import logging
import os
import sys
import time

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from database.db_url import build_database_url

logger = logging.getLogger(__name__)

_MIGRATION_LOCK_ID = 73482901
_LOCK_WAIT_SECONDS = 120
_CONNECT_TIMEOUT = 30


def _migrations_disabled() -> bool:
    if os.getenv("SKIP_DB_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        return True
    if "unittest" in sys.modules and not os.getenv("FORCE_DB_MIGRATIONS"):
        return True
    return False


def _current_revision(connection) -> str | None:
    context = MigrationContext.configure(connection)
    return context.get_current_revision()


def _acquire_migration_lock(connection) -> bool:
    """Intenta tomar el lock con reintentos (varias instancias en frío en deploy)."""
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    while time.monotonic() < deadline:
        got = connection.execute(
            text("SELECT pg_try_advisory_lock(:id)"),
            {"id": _MIGRATION_LOCK_ID},
        ).scalar()
        if got:
            return True
        logger.info("Esperando lock de migración (otra instancia migrando)...")
        time.sleep(2)
    return False


def apply_pending_migrations() -> None:
    """Ejecuta `alembic upgrade head` si hace falta."""
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

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"timeout": _CONNECT_TIMEOUT},
    )
    locked = False
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

            locked = _acquire_migration_lock(conn)
            if not locked:
                raise RuntimeError(
                    f"No se pudo obtener el lock de migración en {_LOCK_WAIT_SECONDS}s"
                )

            try:
                command.upgrade(cfg, "head")
                logger.info("Migraciones Alembic aplicadas (head=%s).", head)
            finally:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:id)"),
                    {"id": _MIGRATION_LOCK_ID},
                )
                locked = False
    finally:
        if locked:
            try:
                with engine.connect() as conn:
                    conn.execute(
                        text("SELECT pg_advisory_unlock(:id)"),
                        {"id": _MIGRATION_LOCK_ID},
                    )
            except Exception as e:
                logger.warning("No se pudo liberar lock de migración: %s", e)
        engine.dispose()


def apply_migrations_and_seed() -> None:
    """Migraciones + datos de referencia (talles, colores, categorías) si faltan."""
    apply_pending_migrations()
    try:
        from database.init_db import seed_reference_data

        seed_reference_data()
    except Exception as e:
        logger.warning("Seed de referencia no completado (no crítico): %s", e)
