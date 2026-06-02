"""URL de conexión compartida (app, Alembic, scripts)."""
import os

from dotenv import load_dotenv
from sqlalchemy.engine.url import URL

load_dotenv()

CLOUD_SQL_SOCKET_DIR = "/cloudsql"


def _resolve_cloud_sql_connection_name() -> str | None:
    """Nombre de instancia project:region:instance para socket en Cloud Run."""
    explicit = os.getenv("CLOUD_SQL_CONNECTION_NAME", "").strip()
    if explicit:
        return explicit

    host = os.getenv("DB_HOST", "").strip()
    if host.startswith(f"{CLOUD_SQL_SOCKET_DIR}/"):
        return host.removeprefix(f"{CLOUD_SQL_SOCKET_DIR}/").split("/")[0]

    if host.count(":") == 2 and "." not in host and not host.startswith("/"):
        return host

    return None


def get_sqlalchemy_connect_args() -> dict:
    """Argumentos extra para create_engine (psycopg2)."""
    args: dict = {}
    timeout = os.getenv("DB_CONNECT_TIMEOUT", "").strip()
    if timeout:
        args["connect_timeout"] = int(timeout)
    return args


def _normalize_database_url(url: str) -> str:
    """Asegura driver psycopg2 y SSL para Neon."""
    u = url.strip()
    if u.startswith("postgresql://"):
        u = "postgresql+psycopg2://" + u[len("postgresql://") :]
    if "neon.tech" in u and "sslmode=" not in u:
        u += "&sslmode=require" if "?" in u else "?sslmode=require"
    return u


def build_database_url() -> str:
    """Construye la URL PostgreSQL desde variables de entorno."""
    override = os.getenv("DATABASE_URL", "").strip()
    if override:
        return _normalize_database_url(override)

    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", "")

    conn_name = _resolve_cloud_sql_connection_name()
    if conn_name:
        # Formato recomendado por Google Cloud Run + Cloud SQL (libpq host = socket dir)
        return URL.create(
            drivername="postgresql+psycopg2",
            username=user,
            password=password,
            database=name,
            query={"host": f"{CLOUD_SQL_SOCKET_DIR}/{conn_name}"},
        ).render_as_string(hide_password=False)

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    return URL.create(
        drivername="postgresql+psycopg2",
        username=user,
        password=password,
        host=host,
        port=port,
        database=name,
    ).render_as_string(hide_password=False)
