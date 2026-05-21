from contextlib import contextmanager
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from database.db_url import build_database_url  # noqa: E402

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_HOST_DOCKER = os.getenv("DB_HOST_DOCKER")

DATABASE_URL = build_database_url()
# echo SQL solo en desarrollo explícito (evita logs enormes en Cloud Run)
_engine_echo = os.getenv("DB_ECHO", "").lower() in ("1", "true", "yes")
engine = create_engine(DATABASE_URL, echo=_engine_echo, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    """
    Datos de referencia (talles, categorías). El esquema lo gestiona Alembic:
      python -m alembic upgrade head

    En producción con DB ya existente (sin alembic_version):
      python -m alembic stamp head
    """
    print(f"DEBUG: Conectando base init_db: {DATABASE_URL}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        import database.models  # noqa: F401

        run_schema = os.getenv("RUN_DB_CREATE_ALL", "").lower() in ("1", "true", "yes")
        if run_schema:
            print(
                "AVISO: RUN_DB_CREATE_ALL activo — create_all omitido; usá Alembic. "
                "Solo se ejecutan seeds."
            )
        seed_reference_data()
    except Exception as e:
        print(f"Error initializing database: {e}")


def seed_reference_data() -> None:
    """Talles y categorías base (idempotente). No altera el esquema."""
    _seed_sizes_if_empty()
    _seed_categories_if_empty()


def _seed_sizes_if_empty() -> None:
    from database.models.Size import Size

    session = SessionLocal()
    try:
        if session.query(Size).count() > 0:
            return
        defaults = [
            ("XS", "XS", 10),
            ("S", "S", 20),
            ("M", "M", 30),
            ("L", "L", 40),
            ("XL", "XL", 50),
            ("XXL", "XXL", 60),
            ("UNICO", "Único", 70),
        ]
        for code, label, order in defaults:
            session.add(Size(code=code, label=label, sort_order=order))
        session.commit()
        print("Talles base insertados (sizes).")
    except Exception as e:
        session.rollback()
        print(f"No se pudieron insertar talles base: {e}")
    finally:
        session.close()


def _seed_categories_if_empty() -> None:
    from database.models.Category import Category

    session = SessionLocal()
    try:
        if session.query(Category).count() > 0:
            return
        defaults = [
            ("jeans", "Jeans", 10),
            ("pantalones", "Pantalones", 20),
            ("remeras", "Remeras", 30),
            ("camisas", "Camisas", 40),
            ("blusas", "Blusas", 50),
            ("camperas", "Camperas", 60),
            ("vestidos", "Vestidos", 70),
            ("polleras", "Polleras", 80),
            ("buzos", "Buzos", 90),
            ("accesorios", "Accesorios", 100),
        ]
        for slug, name, order in defaults:
            session.add(Category(slug=slug, name=name, sort_order=order, activo=True))
        session.commit()
        print("Categorías base insertadas (categories).")
    except Exception as e:
        session.rollback()
        print(f"No se pudieron insertar categorías base: {e}")
    finally:
        session.close()


@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error en la DB get_db_session: {e}")
        raise
    finally:
        session.close()


def get_db_fastApi():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


if __name__ == "__main__":
    initialize_database()
