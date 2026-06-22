"""Autenticación JWT del panel admin."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
import bcrypt

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from config import APP_DEBUG  # noqa: E402

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

_DEFAULT_DEV_SECRET = "supersecretkey-dev-only"
_DEFAULT_DEV_USERNAME = "admin"
_DEFAULT_DEV_PASSWORD = "admin123"


def _env_bool(name: str) -> bool:
    return os.getenv(name, "false").lower() in ("1", "true", "yes", "on")


def get_jwt_secret_key() -> str:
    key = os.getenv("JWT_SECRET_KEY", "").strip()
    if key:
        return key
    if APP_DEBUG:
        logger.warning(
            "JWT_SECRET_KEY no configurada; usando clave de desarrollo insegura. "
            "Ejecutá: python scripts/setup_admin_auth.py"
        )
        return _DEFAULT_DEV_SECRET
    raise RuntimeError(
        "JWT_SECRET_KEY es obligatoria en producción. "
        "Generala con: python scripts/setup_admin_auth.py"
    )


SECRET_KEY = get_jwt_secret_key()


def get_admin_username() -> str:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    if username:
        return username
    if APP_DEBUG:
        logger.warning(
            "ADMIN_USERNAME no configurado; usando '%s' solo para desarrollo.",
            _DEFAULT_DEV_USERNAME,
        )
        return _DEFAULT_DEV_USERNAME
    raise RuntimeError(
        "ADMIN_USERNAME es obligatorio en producción. "
        "Configuralo en .env o Secret Manager."
    )


class _AdminUserView:
    """Compatibilidad con código/tests que leen ADMIN_USER['username']."""

    @property
    def username(self) -> str:
        return get_admin_username()

    @property
    def rol(self) -> str:
        return "admin"

    def __getitem__(self, key: str):
        if key == "username":
            return self.username
        if key == "rol":
            return self.rol
        raise KeyError(key)


ADMIN_USER = _AdminUserView()


def admin_auth_status() -> dict:
    """Estado de configuración (sin exponer secretos)."""
    has_jwt = bool(os.getenv("JWT_SECRET_KEY", "").strip())
    has_hash = bool(os.getenv("ADMIN_PASSWORD_HASH", "").strip())
    has_plain = bool(os.getenv("ADMIN_PASSWORD", "").strip())
    return {
        "username_configured": bool(os.getenv("ADMIN_USERNAME", "").strip()),
        "password_hash_configured": has_hash,
        "password_plain_configured": has_plain,
        "jwt_secret_configured": has_jwt,
        "using_dev_defaults": APP_DEBUG and not (has_jwt and has_hash),
    }


def authenticate_admin(username: str, password: str) -> bool:
    expected = get_admin_username()
    if username != expected:
        return False

    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    if password_hash:
        if verify_admin_password(password, password_hash):
            return True
        logger.warning("Contraseña incorrecta o hash bcrypt inválido.")
        return False

    plain = os.getenv("ADMIN_PASSWORD", "").strip()
    if plain:
        if not APP_DEBUG:
            logger.error("ADMIN_PASSWORD en texto plano solo permitido con APP_DEBUG=true")
            return False
        logger.warning("Autenticando con ADMIN_PASSWORD en texto plano (solo desarrollo).")
        return password == plain

    if APP_DEBUG:
        logger.warning(
            "Sin ADMIN_PASSWORD_HASH ni ADMIN_PASSWORD; usando credenciales de desarrollo admin/admin123."
        )
        return username == _DEFAULT_DEV_USERNAME and password == _DEFAULT_DEV_PASSWORD

    logger.error("ADMIN_PASSWORD_HASH es obligatorio en producción.")
    return False


def hash_admin_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_admin_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Tu sesión expiró. Volvé a iniciar sesión.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Sesión inválida. Volvé a iniciar sesión.")


def get_optional_user(token: str | None = Depends(oauth2_scheme_optional)):
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
