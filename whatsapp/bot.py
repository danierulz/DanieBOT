import logging
import os
import re
from typing import Optional

from fastapi import FastAPI
from pywa import WhatsApp

logger = logging.getLogger(__name__)

_wa: Optional[WhatsApp] = None

# Meta Phone Number ID: solo dígitos, ~12–16 chars. E.164 AR suele empezar en 54911…
_PHONE_ID_RE = re.compile(r"^\d{10,20}$")
_E164_LIKE_RE = re.compile(r"^54\d{9,12}$")


def normalize_phone_id(raw: str | None) -> str | None:
    """Quita +, espacios y guiones del valor de PYWA_PHONE_ID."""
    if not raw:
        return None
    cleaned = raw.strip().lstrip("+").replace(" ", "").replace("-", "")
    return cleaned or None


def validate_phone_id(phone_id: str | None) -> list[str]:
    """Devuelve advertencias de configuración (no bloquea el arranque)."""
    warnings: list[str] = []
    if not phone_id:
        warnings.append("PYWA_PHONE_ID vacío")
        return warnings
    if not _PHONE_ID_RE.match(phone_id):
        warnings.append(
            f"PYWA_PHONE_ID '{phone_id}' no parece un ID numérico de Meta "
            "(esperado: solo dígitos, sin +)"
        )
    if _E164_LIKE_RE.match(phone_id):
        warnings.append(
            f"PYWA_PHONE_ID '{phone_id}' parece un número de teléfono (+54…), "
            "no el Phone number ID de Meta Developer → WhatsApp → API Setup"
        )
    return warnings


def init_whatsapp(app: FastAPI) -> Optional[WhatsApp]:
    global _wa
    phone_id = normalize_phone_id(os.getenv("PYWA_PHONE_ID"))
    token = os.getenv("PYWA_AUTH_TOKEN")
    verify_token = os.getenv("PYWA_VERIFY_TOKEN")
    app_secret = os.getenv("APP_SECRET")
    app_id = os.getenv("APP_ID")

    if not (phone_id and token and verify_token):
        logger.warning("PyWa no configurado: faltan PYWA_PHONE_ID, PYWA_AUTH_TOKEN o PYWA_VERIFY_TOKEN")
        return None

    for warn in validate_phone_id(phone_id):
        logger.warning("PYWA_PHONE_ID: %s", warn)

    try:
        kwargs = {
            "phone_id": phone_id,
            "token": token,
            "app_secret": app_secret,
            "verify_token": verify_token,
            "server": app,
            # Path original del proyecto antes del refactor a whatsapp/bot.py
            "webhook_endpoint": "/webhook/",
        }
        if app_id:
            kwargs["app_id"] = int(app_id)
        _wa = WhatsApp(**kwargs)
        logger.info(
            "PyWa configurado (webhook /webhook/ + compat /webhook, "
            "APP_SECRET=%s, APP_ID=%s)",
            "set" if app_secret else "missing",
            app_id or "missing",
        )
        if not app_secret:
            logger.warning(
                "APP_SECRET no configurado: validación de firma del webhook desactivada"
            )
        elif not app_id:
            logger.warning("APP_ID no configurado en el entorno de Cloud Run")

        from whatsapp.handlers import register_handlers
        from whatsapp.webhook_routes import register_webhook_compat_routes

        register_handlers(_wa)
        register_webhook_compat_routes(app, _wa)
        return _wa
    except Exception as e:
        logger.error("Error al configurar PyWa: %s", e)
        return None


def get_wa_client() -> Optional[WhatsApp]:
    return _wa
