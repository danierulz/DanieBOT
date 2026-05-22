"""
Rutas de compatibilidad para el webhook de Meta.

Antes del refactor (main.py) PyWa escuchaba en /webhook/ y las rutas manuales
GET/POST /webhook (sin barra) procesaban los eventos. Meta suele configurarse
con la URL sin barra final; sin estas rutas el bot deja de recibir mensajes.
"""
import logging
import os

from fastapi import FastAPI, Request, Response
from pywa import WhatsApp

from whatsapp.webhook_payload import log_webhook_payload_summary

logger = logging.getLogger(__name__)


def register_webhook_compat_routes(app: FastAPI, wa: WhatsApp) -> None:
    """Expone /webhook (sin barra) delegando en el cliente PyWa."""
    verify_token = os.getenv("PYWA_VERIFY_TOKEN", "")

    @app.get("/webhook")
    async def verify_webhook_compat(request: Request) -> Response:
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")

        if mode == "subscribe" and token == verify_token:
            logger.info("Webhook GET /webhook verificado (compat Meta)")
            return Response(content=challenge, media_type="text/plain")

        content, status_code = wa.webhook_challenge_handler(vt=token or "", ch=challenge)
        return Response(content=content, status_code=status_code, media_type="text/plain")

    @app.post("/webhook")
    async def handle_webhook_compat(request: Request) -> Response:
        body = await request.body()
        hmac_header = request.headers.get("X-Hub-Signature-256", "")
        logger.info(
            "Webhook POST /webhook (%d bytes, signature=%s)",
            len(body),
            "presente" if hmac_header else "ausente",
        )
        log_webhook_payload_summary(body)
        content, status_code = wa.webhook_update_handler(
            update=body,
            hmac_header=hmac_header,
        )
        if status_code != 200 or content != "ok":
            logger.warning(
                "Webhook POST /webhook no procesó el evento: status=%s body=%r",
                status_code,
                content,
            )
        else:
            logger.info("Webhook POST /webhook procesado OK (revisá avisos filter_updates arriba)")
        return Response(content=content, status_code=status_code, media_type="text/plain")

    logger.info("Webhook compat registrado: GET/POST /webhook (PyWa principal en /webhook/)")
