#!/usr/bin/env python3
"""Genera JWT_SECRET_KEY, ADMIN_USERNAME y ADMIN_PASSWORD_HASH para .env / Secret Manager."""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.auth import hash_admin_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Configurar credenciales del admin.")
    parser.add_argument(
        "--username",
        help="Usuario admin (si no se pasa, pregunta interactivo)",
    )
    parser.add_argument(
        "--append-env",
        action="store_true",
        help="Agregar líneas al final de .env (crea backup .env.bak si existe)",
    )
    args = parser.parse_args()

    username = (args.username or input("Usuario admin: ").strip()) or "admin"
    password = getpass.getpass("Contraseña nueva: ")
    confirm = getpass.getpass("Repetir contraseña: ")
    if not password:
        print("La contraseña no puede estar vacía.", file=sys.stderr)
        return 1
    if password != confirm:
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 1
    if len(password) < 10:
        print("Advertencia: conviene al menos 10 caracteres.", file=sys.stderr)

    jwt_secret = secrets.token_urlsafe(48)
    password_hash = hash_admin_password(password)

    lines = [
        "",
        "# --- Admin panel (generado con scripts/setup_admin_auth.py) ---",
        f"ADMIN_USERNAME={username}",
        f"ADMIN_PASSWORD_HASH={password_hash}",
        f"JWT_SECRET_KEY={jwt_secret}",
        "# ADMIN_PASSWORD=  # no usar en producción; solo dev temporal",
    ]
    block = "\n".join(lines)

    print("\nAgregá esto a tu .env (o a Secret Manager en Cloud Run):\n")
    print(block)
    print("\nLuego reiniciá el servidor. Login en /login con el usuario y contraseña que elegiste.")

    if args.append_env:
        env_path = ROOT / ".env"
        if env_path.exists():
            backup = ROOT / ".env.bak"
            backup.write_text(env_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"\nBackup guardado en {backup}")
        with env_path.open("a", encoding="utf-8") as fh:
            fh.write(block + "\n")
        print(f"Variables agregadas a {env_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
