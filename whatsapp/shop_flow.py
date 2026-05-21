"""
Flujo guiado «Ver tienda»: categoría (paginada) → talle → URL filtrada.
Estado en memoria por wa_id (mismo patrón que email pendiente).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from config import get_catalog_categories
from services.catalog_urls import build_catalog_url
from whatsapp.conversation import (
    BotReply,
    ButtonDef,
    CB_ASESOR,
    CB_ESTADO_PEDIDO,
)

# Callbacks del flujo tienda
CB_SHOP_START = "SHOP_START"
CB_SHOP_AGAIN = "SHOP_AGAIN"
CB_SHOP_CANCEL = "SHOP_CANCEL"
CB_SHOP_SIZE_PAGE = "SHOP_SIZE_PAGE"  # SHOP_SIZE_PAGE:1

PREFIX_CAT_PAGE = "SHOP_CAT_PAGE:"
PREFIX_CAT = "SHOP_CAT:"
PREFIX_SIZE = "SHOP_SIZE:"

# 2 categorías + «Siguiente» en páginas intermedias (máx. 3 botones WhatsApp)
CATEGORIES_PER_PAGE = 2
_SIZE_PRIMARY = ("S", "M", "L")
_SIZE_EXTRA = ("XS", "XL", "XXL")
_ALL_SIZE_CODES = frozenset({"XS", "S", "M", "L", "XL", "XXL", "UNICO", "ALL"})


class ShopStep(str, Enum):
    CATEGORY = "category"
    SIZE = "size"


@dataclass
class ShopSession:
    step: ShopStep = ShopStep.CATEGORY
    category_slug: str = ""
    category_name: str = ""
    category_page: int = 0
    size_page: int = 0


_sessions: dict[str, ShopSession] = {}


def is_shop_callback(data: str) -> bool:
    d = (data or "").strip()
    return d.startswith("SHOP_") or d.startswith(PREFIX_CAT_PAGE) or d.startswith(PREFIX_CAT) or d.startswith(PREFIX_SIZE)


def has_active_session(wa_id: str) -> bool:
    return wa_id in _sessions


def clear_session(wa_id: str) -> None:
    _sessions.pop(wa_id, None)


def _category_pages() -> list[list[dict]]:
    cats = get_catalog_categories()
    pages: list[list[dict]] = []
    for i in range(0, len(cats), CATEGORIES_PER_PAGE):
        pages.append(cats[i : i + CATEGORIES_PER_PAGE])
    return pages


def _category_label(slug: str) -> str:
    if slug == "todos":
        return "Ver todo"
    for c in get_catalog_categories():
        if c["slug"] == slug:
            return c["name"]
    return slug


def start_shop() -> BotReply:
    return _reply_category_page(0)


def start_with_category(slug: str, wa_id: str | None = None) -> BotReply:
    """Salta a elegir talle (ej. intent «jeans»)."""
    name = _category_label(slug)
    return _set_category_and_ask_size(slug, name, wa_id)


def _reply_category_page(page: int, wa_id: str | None = None) -> BotReply:
    pages = _category_pages()
    if not pages:
        return BotReply(text="No hay categorías configuradas.")
    page = max(0, min(page, len(pages) - 1))
    if wa_id:
        _sessions[wa_id] = ShopSession(step=ShopStep.CATEGORY, category_page=page)

    chunk = pages[page]
    is_last = page >= len(pages) - 1
    has_next = page < len(pages) - 1

    buttons: list[ButtonDef] = [
        ButtonDef(c["name"], f"{PREFIX_CAT}{c['slug']}") for c in chunk[:CATEGORIES_PER_PAGE]
    ]

    if is_last and len(buttons) < 3:
        buttons.append(ButtonDef("Ver todo", f"{PREFIX_CAT}todos"))
    if has_next and len(buttons) < 3:
        buttons.append(ButtonDef("Siguiente ▶", f"{PREFIX_CAT_PAGE}{page + 1}"))

    nav = f" (pág. {page + 1}/{len(pages)})" if len(pages) > 1 else ""
    return BotReply(
        text=f"🛍️ ¿Qué categoría buscás?{nav}\n\nElegí una opción:",
        buttons=buttons[:3],
    )


def _set_category_and_ask_size(slug: str, name: str, wa_id: str | None = None) -> BotReply:
    if wa_id:
        _sessions[wa_id] = ShopSession(
            step=ShopStep.SIZE,
            category_slug=slug,
            category_name=name,
            size_page=0,
        )
    cat_display = name if slug != "todos" else "todo el catálogo"
    return BotReply(
        text=(
            f"Perfecto: *{cat_display}*.\n\n"
            "¿Qué talle necesitás?\n"
            "_Para otro talle escribí XS, XL, XXL o *todos* (sin filtrar talle)._"
        ),
        buttons=[
            ButtonDef("S", f"{PREFIX_SIZE}S"),
            ButtonDef("M", f"{PREFIX_SIZE}M"),
            ButtonDef("Más talles", f"{CB_SHOP_SIZE_PAGE}:1"),
        ],
    )


def _reply_size_page(page: int, session: ShopSession) -> BotReply:
    if page <= 0:
        return BotReply(
            text=(
                f"Talle para *{session.category_name}*:\n"
                "Elegí S, M o L, o tocá *Más talles*."
            ),
            buttons=[
                ButtonDef("S", f"{PREFIX_SIZE}S"),
                ButtonDef("M", f"{PREFIX_SIZE}M"),
                ButtonDef("Más talles", f"{CB_SHOP_SIZE_PAGE}:1"),
            ],
        )
    return BotReply(
        text=(
            f"Más talles para *{session.category_name}*:\n"
            "_Escribí *todos* para ver sin filtrar por talle._"
        ),
        buttons=[
            ButtonDef("L", f"{PREFIX_SIZE}L"),
            ButtonDef("XS", f"{PREFIX_SIZE}XS"),
            ButtonDef("XL", f"{PREFIX_SIZE}XL"),
        ],
    )


def _finish_with_size(session: ShopSession, size_code: str | None) -> BotReply:
    slug = session.category_slug or "todos"
    name = session.category_name or "Catálogo"
    url = build_catalog_url(slug if slug else None, size_code)

    if size_code and size_code != "ALL":
        talle_txt = f" talle *{size_code}*"
    else:
        talle_txt = ""

    cat_txt = name if slug != "todos" else "todo el catálogo"
    return BotReply(
        text=(
            f"Listo 👖 Esto es lo que tenemos en *{cat_txt}*{talle_txt}:\n\n"
            f"{url}\n\n"
            "Elegí en la web y, al confirmar, enviá tu *código de pedido* por acá."
        ),
        buttons=[
            ButtonDef("Ver otra categoría", CB_SHOP_AGAIN),
            ButtonDef("Mi pedido", CB_ESTADO_PEDIDO),
            ButtonDef("Asesor", CB_ASESOR),
        ],
    )


def handle_callback(wa_id: str, data: str) -> BotReply:
    data = (data or "").strip()

    if data == CB_SHOP_START or data == CB_SHOP_AGAIN:
        _sessions[wa_id] = ShopSession(step=ShopStep.CATEGORY, category_page=0)
        return _reply_category_page(0, wa_id)

    if data == CB_SHOP_CANCEL:
        clear_session(wa_id)
        from whatsapp.conversation import get_welcome_reply

        return get_welcome_reply("")

    if data.startswith(PREFIX_CAT_PAGE):
        try:
            page = int(data.split(":", 1)[1])
        except (IndexError, ValueError):
            page = 0
        return _reply_category_page(page, wa_id)

    if data.startswith(PREFIX_CAT):
        slug = data.split(":", 1)[1].strip().lower()
        name = _category_label(slug)
        return _set_category_and_ask_size(slug, name, wa_id)

    if data.startswith(CB_SHOP_SIZE_PAGE + ":"):
        session = _sessions.get(wa_id)
        if not session or session.step != ShopStep.SIZE:
            return start_shop()
        try:
            page = int(data.split(":", 1)[1])
        except (IndexError, ValueError):
            page = 1
        session.size_page = page
        return _reply_size_page(page, session)

    if data.startswith(PREFIX_SIZE):
        code = data.split(":", 1)[1].strip().upper()
        session = _sessions.pop(wa_id, None)
        if not session:
            return start_shop()
        return _finish_with_size(session, code if code != "ALL" else None)

    clear_session(wa_id)
    return start_shop()


def handle_text(wa_id: str, text: str, user_name: str = "") -> Optional[BotReply]:
    """Si hay sesión de tienda activa, interpreta talle o cancelación."""
    session = _sessions.get(wa_id)
    if not session:
        return None

    t = text.lower().strip()
    if t in ("cancelar", "salir", "menu", "menú", "volver"):
        clear_session(wa_id)
        from whatsapp.conversation import get_welcome_reply

        return get_welcome_reply(user_name or "ahí")

    if session.step == ShopStep.SIZE:
        code = text.strip().upper()
        if code == "TODOS" or code == "ALL":
            reply = _finish_with_size(session, None)
            _sessions.pop(wa_id, None)
            return reply
        if code in _ALL_SIZE_CODES and code != "ALL":
            reply = _finish_with_size(session, code)
            _sessions.pop(wa_id, None)
            return reply

    return BotReply(
        text="Usá los botones de arriba o escribí un talle (S, M, L, XL…), *todos* o *cancelar*.",
        buttons=[],
    )


