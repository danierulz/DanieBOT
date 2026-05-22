import logging

from pywa import WhatsApp, filters, types

from config import get_order_confirmation_reply
from database.init_db import SessionLocal
from services.customer_service import get_or_create_customer_by_wa_id, save_customer_email
from services.order_code import extract_order_code
from services.order_service import (
    format_order_summary_for_bot,
    get_order_by_code,
    link_order_to_whatsapp,
    status_label,
)
from whatsapp.conversation import (
    CB_EMAIL_CONSENT_NO,
    CB_EMAIL_CONSENT_SI,
    CB_EMAIL_NO,
    CB_EMAIL_SI,
    reply_for_callback,
    route_text_message,
    reply_to_pywa_buttons,
)
from whatsapp import email_flow
from whatsapp.shop_flow import handle_callback as shop_handle_callback
from whatsapp.shop_flow import handle_text as shop_handle_text
from whatsapp.shop_flow import is_shop_callback

logger = logging.getLogger(__name__)


def _send_reply(msg_or_cb, reply) -> None:
    buttons = reply_to_pywa_buttons(reply.buttons)
    kwargs = {"text": reply.text}
    if buttons:
        kwargs["buttons"] = buttons
    msg_or_cb.reply_text(**kwargs)


def register_handlers(client) -> None:
    def _on_email_timeout(wa_id: str) -> None:
        try:
            client.send_message(
                to=wa_id,
                text="Tardaste mucho en responder. Podés escribir tu email cuando quieras.",
            )
        except Exception:
            logger.exception("No se pudo enviar timeout de email a %s", wa_id)

    email_flow.set_timeout_callback(_on_email_timeout)

    @client.on_callback_button()
    def on_button(_: WhatsApp, cb: types.CallbackButton):
        if email_flow.is_callback_duplicate(cb.id):
            logger.info("Callback duplicado ignorado: %s", cb.id)
            return

        data = (cb.data or "").strip()
        if data in (CB_EMAIL_SI, CB_EMAIL_NO, CB_EMAIL_CONSENT_SI, CB_EMAIL_CONSENT_NO):
            wa_id = cb.from_user.wa_id
            if data == CB_EMAIL_SI:
                if email_flow.start_email_collection(wa_id):
                    cb.reply_text("Escribí tu email:")
            elif data == CB_EMAIL_NO:
                email_flow.clear_email_flow(wa_id)
                cb.reply_text("¡Perfecto! Cualquier consulta, escribinos por acá.")
            elif data == CB_EMAIL_CONSENT_SI:
                _save_email_from_context(cb, marketing_consent=True)
            elif data == CB_EMAIL_CONSENT_NO:
                _save_email_from_context(cb, marketing_consent=False)
            return
        wa_id = cb.from_user.wa_id
        if is_shop_callback(data):
            _send_reply(cb, shop_handle_callback(wa_id, data))
            return
        _send_reply(cb, reply_for_callback(data))

    @client.on_message(filters.text)
    def on_text(_: WhatsApp, msg: types.Message):
        text = (msg.text or "").strip()
        if not text:
            return

        logger.info(
            "WA mensaje texto de %s (%s): %s",
            msg.from_user.wa_id,
            msg.from_user.name or "?",
            text[:120],
        )
        try:
            wa_id = msg.from_user.wa_id

            email_result = email_flow.handle_email_text(wa_id, text)
            if email_result is not None:
                reply_text, ask_consent = email_result
                if reply_text:
                    msg.reply_text(reply_text)
                elif ask_consent:
                    msg.reply_text(
                        "¿Aceptás recibir novedades y promociones por email?",
                        buttons=[
                            types.Button(title="Sí, acepto", callback_data=CB_EMAIL_CONSENT_SI),
                            types.Button(title="Solo seguimiento", callback_data=CB_EMAIL_CONSENT_NO),
                        ],
                    )
                return

            if email_flow.is_awaiting_consent(wa_id):
                msg.reply_text("Elegí una opción con los botones de arriba.")
                return

            order_code = extract_order_code(text)
            if order_code:
                _handle_order_message(msg, order_code)
                return

            lower = text.lower()
            if lower.startswith("estado"):
                code = extract_order_code(text[6:]) or extract_order_code(text)
                if code:
                    _handle_status_query(msg, code)
                    return

            name = msg.from_user.name or ""
            shop_reply = shop_handle_text(wa_id, text, name)
            if shop_reply is not None:
                _send_reply(msg, shop_reply)
                return

            _send_reply(msg, route_text_message(text, name, wa_id))
        except Exception:
            logger.exception("Error respondiendo mensaje WA de %s", msg.from_user.wa_id)
            try:
                msg.reply_text(
                    "Hubo un problema al procesar tu mensaje. Intentá de nuevo en un momento."
                )
            except Exception:
                logger.exception("No se pudo enviar mensaje de error al usuario %s", msg.from_user.wa_id)


def _handle_order_message(msg: types.Message, order_code: str):
    db = SessionLocal()
    try:
        order = get_order_by_code(db, order_code)
        if not order:
            msg.reply_text(
                f"No encontramos el pedido *{order_code}*. "
                "Si acabás de confirmar en la web, esperá unos segundos e intentá de nuevo."
            )
            return

        customer = get_or_create_customer_by_wa_id(
            db,
            msg.from_user.wa_id,
            display_name=msg.from_user.name,
        )
        link_order_to_whatsapp(db, order, customer, msg.from_user.wa_id)
        summary = format_order_summary_for_bot(order)
        msg.reply_text(get_order_confirmation_reply(msg.from_user.name, summary))
        email_flow.clear_email_flow(msg.from_user.wa_id)
        msg.reply_text(
            "¿Querés dejarnos tu email para novedades y seguimiento?",
            buttons=[
                types.Button(title="Sí", callback_data=CB_EMAIL_SI),
                types.Button(title="No, gracias", callback_data=CB_EMAIL_NO),
            ],
        )
    except Exception:
        logger.exception("Error procesando pedido %s", order_code)
        msg.reply_text("Hubo un problema al registrar tu pedido. Escribinos de nuevo en un momento.")
    finally:
        db.close()


def _handle_status_query(msg: types.Message, order_code: str):
    db = SessionLocal()
    try:
        order = get_order_by_code(db, order_code)
        if not order:
            msg.reply_text(f"No encontramos el pedido *{order_code}*.")
            return
        msg.reply_text(
            f"*Pedido {order.order_code}*\nEstado: {status_label(order.status)}\n\n"
            + format_order_summary_for_bot(order)
        )
    finally:
        db.close()


def _save_email_from_context(cb: types.CallbackButton, *, marketing_consent: bool):
    email = email_flow.pop_pending_email(cb.from_user.wa_id)
    if not email:
        cb.reply_text("No tengo tu email guardado. Tocá «Sí» y escribilo en un mensaje.")
        return
    db = SessionLocal()
    try:
        customer = get_or_create_customer_by_wa_id(
            db, cb.from_user.wa_id, display_name=cb.from_user.name
        )
        save_customer_email(db, customer, email, marketing_consent=marketing_consent)
        if marketing_consent:
            cb.reply_text("¡Gracias! Guardamos tu email para novedades y seguimiento.")
        else:
            cb.reply_text("¡Gracias! Guardamos tu email solo para seguimiento del pedido.")
    finally:
        db.close()
