import logging
import os
from typing import Optional

from fastapi import FastAPI
from pywa import WhatsApp

logger = logging.getLogger(__name__)

_wa: Optional[WhatsApp] = None


def init_whatsapp(app: FastAPI) -> Optional[WhatsApp]:
    global _wa
    phone_id = os.getenv("PYWA_PHONE_ID")
    token = os.getenv("PYWA_AUTH_TOKEN")
    verify_token = os.getenv("PYWA_VERIFY_TOKEN")
    app_secret = os.getenv("APP_SECRET")
    app_id = os.getenv("APP_ID")

    if not (phone_id and token and verify_token):
        logger.warning("PyWa no configurado: faltan PYWA_PHONE_ID, PYWA_AUTH_TOKEN o PYWA_VERIFY_TOKEN")
        return None

    try:
        kwargs = {
            "phone_id": phone_id,
            "token": token,
            "app_secret": app_secret,
            "verify_token": verify_token,
            "server": app,
            "webhook_endpoint": "/webhook",
        }
        if app_id:
            kwargs["app_id"] = int(app_id)
        _wa = WhatsApp(**kwargs)
        logger.info("PyWa configurado (webhook /webhook)")
        from whatsapp.handlers import register_handlers

        register_handlers(_wa)
        return _wa
    except Exception as e:
        logger.error("Error al configurar PyWa: %s", e)
        return None


def get_wa_client() -> Optional[WhatsApp]:
    return _wa
