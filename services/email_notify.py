import logging
import smtplib
from email.message import EmailMessage

from config import (
    get_admin_notify_email,
    get_site_public_url,
    get_smtp_from,
    get_smtp_host,
    get_smtp_password,
    get_smtp_port,
    get_smtp_user,
    is_admin_notify_email_enabled,
)

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 10


def is_email_notify_configured() -> bool:
    if not is_admin_notify_email_enabled():
        return False
    return bool(
        get_admin_notify_email()
        and get_smtp_host()
        and get_smtp_user()
        and get_smtp_password()
    )


def admin_panel_link_footer() -> str:
    return f"\n\nPanel admin: {get_site_public_url()}/admin-panel"


def send_admin_email(subject: str, body: str) -> bool:
    if not is_email_notify_configured():
        logger.warning("No se pudo enviar email al admin: SMTP no configurado o desactivado")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = get_smtp_from()
    msg["To"] = get_admin_notify_email()
    msg.set_content(body)

    try:
        with smtplib.SMTP(
            get_smtp_host(), get_smtp_port(), timeout=SMTP_TIMEOUT_SECONDS
        ) as smtp:
            smtp.starttls()
            smtp.login(get_smtp_user(), get_smtp_password())
            smtp.send_message(msg)
        logger.info("Email de aviso enviado al admin (%s)", get_admin_notify_email())
        return True
    except Exception as e:
        logger.warning("Fallo envío email al admin: %s", e)
        return False
