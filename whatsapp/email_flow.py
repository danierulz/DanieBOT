"""
Flujo de captura de email post-pedido (sin wait_for_reply bloqueante).
Estado en memoria por wa_id, mismo patrón que shop_flow.
"""
from __future__ import annotations

import re
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
TIMEOUT_SECONDS = 300

_processed_callback_ids: deque[str] = deque(maxlen=2000)


class EmailStep(str, Enum):
    AWAITING_EMAIL = "awaiting_email"
    AWAITING_CONSENT = "awaiting_consent"


@dataclass
class EmailSession:
    step: EmailStep = EmailStep.AWAITING_EMAIL
    pending_email: str = ""


_sessions: dict[str, EmailSession] = {}
_timers: dict[str, threading.Timer] = {}
_on_timeout: Optional[Callable[[str], None]] = None


def set_timeout_callback(fn: Callable[[str], None]) -> None:
    global _on_timeout
    _on_timeout = fn


def is_callback_duplicate(message_id: str) -> bool:
    """True si este callback de botón ya fue procesado (reintentos de Meta)."""
    if not message_id:
        return False
    if message_id in _processed_callback_ids:
        return True
    _processed_callback_ids.append(message_id)
    return False


def is_collecting_email(wa_id: str) -> bool:
    return wa_id in _sessions


def is_awaiting_email(wa_id: str) -> bool:
    session = _sessions.get(wa_id)
    return session is not None and session.step == EmailStep.AWAITING_EMAIL


def is_awaiting_consent(wa_id: str) -> bool:
    session = _sessions.get(wa_id)
    return session is not None and session.step == EmailStep.AWAITING_CONSENT


def start_email_collection(wa_id: str) -> bool:
    """
    Inicia la espera de email. Devuelve True si hay que enviar el prompt
    (False si ya estaba en curso).
    """
    if wa_id in _sessions:
        return False
    _sessions[wa_id] = EmailSession()
    _arm_timeout(wa_id)
    return True


def clear_email_flow(wa_id: str) -> None:
    _cancel_timeout(wa_id)
    _sessions.pop(wa_id, None)


def handle_email_text(wa_id: str, text: str) -> Optional[tuple[Optional[str], bool]]:
    """
    Procesa texto cuando el usuario está escribiendo su email.

    Returns:
        None — no está en el flujo de email.
        (mensaje, False) — email inválido.
        (None, True) — email válido; hay que pedir consentimiento.
    """
    session = _sessions.get(wa_id)
    if not session or session.step != EmailStep.AWAITING_EMAIL:
        return None

    email = text.strip()
    if not _EMAIL_RE.match(email):
        return ("El email no parece válido. Podés escribirlo de nuevo cuando quieras.", False)

    session.pending_email = email
    session.step = EmailStep.AWAITING_CONSENT
    _cancel_timeout(wa_id)
    return (None, True)


def pop_pending_email(wa_id: str) -> Optional[str]:
    session = _sessions.pop(wa_id, None)
    _cancel_timeout(wa_id)
    if session and session.pending_email:
        return session.pending_email
    return None


def _arm_timeout(wa_id: str) -> None:
    _cancel_timeout(wa_id)
    timer = threading.Timer(TIMEOUT_SECONDS, _fire_timeout, args=(wa_id,))
    timer.daemon = True
    _timers[wa_id] = timer
    timer.start()


def _cancel_timeout(wa_id: str) -> None:
    timer = _timers.pop(wa_id, None)
    if timer is not None:
        timer.cancel()


def _fire_timeout(wa_id: str) -> None:
    _timers.pop(wa_id, None)
    session = _sessions.get(wa_id)
    if session is None or session.step != EmailStep.AWAITING_EMAIL:
        return
    if _on_timeout:
        _on_timeout(wa_id)
