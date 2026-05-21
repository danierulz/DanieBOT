"""URL de conexión compartida (app, Alembic, scripts)."""
import os

from dotenv import load_dotenv

load_dotenv()


def build_database_url() -> str:
    """Construye la URL PostgreSQL desde variables de entorno."""
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "")
    override = os.getenv("DATABASE_URL")
    if override:
        return override
    return f"postgresql+pg8000://{user}:{password}@{host}:{port}/{name}"
