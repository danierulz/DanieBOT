"""URL de conexión compartida (app, Alembic, scripts)."""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

CLOUD_SQL_SOCKET_DIR = "/cloudsql"


def _cloud_sql_unix_sock(connection_name: str) -> str:
    return f"{CLOUD_SQL_SOCKET_DIR}/{connection_name}/.s.PGSQL.5432"


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
    """
    Argumentos extra para create_engine (pg8000).

    En Cloud Run el socket Unix no va en la URL: va en connect_args['unix_sock'].
    """
    args: dict = {}
    timeout = os.getenv("DB_CONNECT_TIMEOUT", "").strip()
    if timeout:
        args["timeout"] = int(timeout)

    conn_name = _resolve_cloud_sql_connection_name()
    if conn_name:
        args["unix_sock"] = _cloud_sql_unix_sock(conn_name)
    return args


def build_database_url() -> str:
    """Construye la URL PostgreSQL desde variables de entorno."""
    override = os.getenv("DATABASE_URL")
    if override:
        return override

    user = quote_plus(os.getenv("DB_USER", ""))
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    name = os.getenv("DB_NAME", "")

    if _resolve_cloud_sql_connection_name():
        return f"postgresql+pg8000://{user}:{password}@/{name}"

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    return f"postgresql+pg8000://{user}:{password}@{host}:{port}/{name}"
