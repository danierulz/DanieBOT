"""Utilidades para inspeccionar payloads del webhook de Meta (sin loguear PII completa)."""
import json
import logging
import os

logger = logging.getLogger(__name__)


def log_webhook_payload_summary(body: bytes) -> None:
    """Registra tipo de evento y si phone_number_id coincide con PYWA_PHONE_ID."""
    configured = (os.getenv("PYWA_PHONE_ID") or "").strip().lstrip("+")
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("WA webhook: body no es JSON válido")
        return

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            meta = value.get("metadata") or {}
            payload_phone_id = str(meta.get("phone_number_id", ""))
            display = meta.get("display_phone_number", "")

            messages = value.get("messages") or []
            statuses = value.get("statuses") or []

            if messages:
                for m in messages:
                    msg_type = m.get("type", "?")
                    sender = m.get("from", "?")
                    preview = ""
                    if msg_type == "text":
                        preview = (m.get("text") or {}).get("body", "")[:80]
                    logger.info(
                        "WA webhook mensaje: type=%s from=%s preview=%r phone_number_id=%s display=%s",
                        msg_type,
                        sender,
                        preview,
                        payload_phone_id,
                        display,
                    )
            elif statuses:
                st = statuses[0]
                logger.info(
                    "WA webhook status: %s recipient=%s phone_number_id=%s",
                    st.get("status"),
                    st.get("recipient_id"),
                    payload_phone_id,
                )
            else:
                logger.info(
                    "WA webhook otro evento: field=%s keys=%s phone_number_id=%s",
                    change.get("field"),
                    list(value.keys()),
                    payload_phone_id,
                )

            if payload_phone_id and configured and payload_phone_id != configured:
                logger.warning(
                    "WA webhook IGNORADO por PyWa (filter_updates): "
                    "phone_number_id del payload=%s pero PYWA_PHONE_ID=%s. "
                    "Actualizá el secreto PYWA_PHONE_ID en GCP con el valor del payload.",
                    payload_phone_id,
                    configured,
                )
            elif payload_phone_id and not configured:
                logger.warning("PYWA_PHONE_ID vacío; PyWa puede ignorar eventos")
