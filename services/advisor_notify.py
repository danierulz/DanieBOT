import logging
from typing import Optional

from config import get_whatsapp_asesor_number
from database.models import Order
from whatsapp.bot import get_wa_client

logger = logging.getLogger(__name__)

_STATUS_LABELS = {
    "borrador": "Borrador",
    "enviado_whatsapp": "Enviado por WhatsApp (pendiente de lectura)",
    "recibido": "Recibido — en revisión",
    "en_revision": "En revisión",
    "confirmado": "Confirmado",
    "cancelado": "Cancelado",
    "pendiente": "Pendiente",
}


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


def _format_lines_short(order: Order) -> str:
    parts = []
    for it in order.items:
        parts.append(f"- {it.title_snapshot} x{it.quantity} (${it.subtotal:,.0f})".replace(",", "."))
    return "\n".join(parts) if parts else "- (sin líneas)"


def _format_order_summary(order: Order) -> str:
    lines = [f"*Pedido {order.order_code}*", f"Estado: {_status_label(order.status)}", ""]
    for it in order.items:
        lines.append(f"• {it.title_snapshot} x{it.quantity} — ${it.subtotal:,.0f}".replace(",", "."))
    lines.append("")
    lines.append(f"*Total:* ${order.total:,.0f}".replace(",", "."))
    return "\n".join(lines)


def notify_advisor_new_web_order(order: Order) -> bool:
    """Avisa al asesor que se registró un pedido desde la web (antes de que la clienta envíe WA)."""
    text = (
        f"🛒 *Nuevo pedido web*\n\n"
        f"Código: *{order.order_code}*\n"
        f"Estado: {_status_label(order.status)}\n"
        f"Total: ${order.total:,.0f}\n\n"
        f"{_format_lines_short(order)}\n\n"
        "La clienta debe enviar el mensaje por WhatsApp con este código. "
        "Cuando llegue, el bot lo marcará como recibido."
    ).replace(",", ".")
    return _send_to_advisor(text)


def notify_advisor_order_received(
    order: Order,
    *,
    customer_name: Optional[str] = None,
    customer_wa_id: Optional[str] = None,
) -> bool:
    """Avisa al asesor que la clienta confirmó el pedido por WhatsApp."""
    who = customer_name or "Cliente"
    wa_line = f"\nWhatsApp: {customer_wa_id}" if customer_wa_id else ""
    summary = _format_order_summary(order)
    text = (
        f"✅ *Pedido confirmado por WhatsApp*\n\n"
        f"Cliente: {who}{wa_line}\n\n"
        f"{summary}\n\n"
        "Atendé el pedido cuando puedas (stock, envío, pago)."
    )
    return _send_to_advisor(text)


def _send_to_advisor(text: str) -> bool:
    wa = get_wa_client()
    if wa is None:
        logger.warning("No se pudo avisar al asesor: PyWa no configurado")
        return False
    to = get_whatsapp_asesor_number()
    if not to:
        logger.warning("No se pudo avisar al asesor: SITE_WA_ASESOR vacío")
        return False
    try:
        wa.send_message(to=to, text=text)
        logger.info("Aviso enviado al asesor (%s)", to)
        return True
    except Exception as e:
        logger.warning("Fallo envío WA al asesor %s: %s", to, e)
        return False
