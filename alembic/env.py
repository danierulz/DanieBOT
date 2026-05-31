"""
Entorno Alembic: usa los mismos modelos SQLAlchemy que la app.
"""
from logging.config import fileConfig
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Raíz del proyecto en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db_url import build_database_url, get_sqlalchemy_connect_args
from database.init_db import Base

# Registrar todos los modelos en Base.metadata
import database.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", build_database_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        build_database_url(),
        poolclass=pool.NullPool,
        connect_args=get_sqlalchemy_connect_args(),
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
