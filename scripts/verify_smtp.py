"""Verifica configuración SMTP para avisos de pedidos al admin."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")

from config import (
    get_admin_notify_email,
    get_smtp_from,
    get_smtp_host,
    get_smtp_port,
    get_smtp_user,
    is_admin_notify_email_enabled,
)
from services.email_notify import is_email_notify_configured, send_admin_email


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificar SMTP de avisos de pedidos")
    parser.add_argument(
        "--send-test",
        action="store_true",
        help="Enviar un email de prueba al ADMIN_NOTIFY_EMAIL",
    )
    args = parser.parse_args()

    print("ADMIN_NOTIFY_EMAIL_ENABLED:", is_admin_notify_email_enabled())
    print("ADMIN_NOTIFY_EMAIL:", get_admin_notify_email() or "(vacío)")
    print("SMTP_HOST:", get_smtp_host() or "(vacío)")
    print("SMTP_PORT:", get_smtp_port())
    print("SMTP_USER:", get_smtp_user() or "(vacío)")
    print("SMTP_FROM:", get_smtp_from() or "(vacío)")
    print("Configured:", is_email_notify_configured())

    if not is_email_notify_configured():
        print("\nStatus: INCOMPLETE — completá ADMIN_NOTIFY_EMAIL y SMTP_* en .env")
        return 1

    if not args.send_test:
        print("\nStatus: OK (config completa). Usá --send-test para enviar un mail de prueba.")
        return 0

    ok = send_admin_email(
        "Prueba DanieBOT — aviso de pedidos",
        (
            "Este es un email de prueba del sistema de avisos de pedidos.\n\n"
            "Si lo recibiste, SMTP está configurado correctamente.\n\n"
            "Podés ignorar este mensaje."
        ),
    )
    if ok:
        print(f"\nStatus: OK — email de prueba enviado a {get_admin_notify_email()}")
        return 0
    print("\nStatus: FAIL — revisá credenciales SMTP y logs arriba")
    return 1


if __name__ == "__main__":
    sys.exit(main())
