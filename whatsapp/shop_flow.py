"""
Flujo guiado «Ver tienda»: categoría (paginada) → talle → URL filtrada.
Estado en memoria por wa_id (mismo patrón que email pendiente).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

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

# Fallback para tests sin base de datos
_FALLBACK_SIZE_GROUPS: dict[str, tuple[str, ...]] = {
    "letter": ("XS", "S", "M", "L", "XL", "XXL", "UNICO"),
    "numeric": ("34", "36", "38", "40", "42"),
}
_FALLBACK_CATEGORY_GROUP: dict[str, str] = {
    "jeans": "numeric",
    "pantalones": "numeric",
}

SizeResolver = Callable[[str], list[str]]
CategoryResolver = Callable[[], list[dict]]


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
    available_sizes: tuple[str, ...] = field(default_factory=tuple)


_sessions: dict[str, ShopSession] = {}


def is_shop_callback(data: str) -> bool:
    d = (data or "").strip()
    return d.startswith("SHOP_") or d.startswith(PREFIX_CAT_PAGE) or d.startswith(PREFIX_CAT) or d.startswith(PREFIX_SIZE)


def has_active_session(wa_id: str) -> bool:
    return wa_id in _sessions


def clear_session(wa_id: str) -> None:
    _sessions.pop(wa_id, None)


def _resolve_categories(resolver: CategoryResolver | None) -> list[dict]:
    if resolver:
        cats = resolver()
        if cats:
            return cats
    return get_catalog_categories()


def _category_pages(categories: list[dict]) -> list[list[dict]]:
    pages: list[list[dict]] = []
    for i in range(0, len(categories), CATEGORIES_PER_PAGE):
        pages.append(categories[i : i + CATEGORIES_PER_PAGE])
    return pages


def _category_label(slug: str, categories: list[dict]) -> str:
    if slug == "todos":
        return "Ver todo"
    for c in categories:
        if c["slug"] == slug:
            return c["name"]
    return slug


def _fallback_sizes(category_slug: str) -> list[str]:
    if category_slug == "todos":
        group = "letter"
    else:
        group = _FALLBACK_CATEGORY_GROUP.get(category_slug, "letter")
    return list(_FALLBACK_SIZE_GROUPS.get(group, _FALLBACK_SIZE_GROUPS["letter"]))


def _resolve_sizes(category_slug: str, resolver: SizeResolver | None) -> list[str]:
    if category_slug == "todos":
        return _fallback_sizes("todos")
    if resolver:
        sizes = resolver(category_slug)
        if sizes:
            return sizes
    return _fallback_sizes(category_slug)


def _size_button_pages(codes: list[str]) -> list[list[str]]:
    if not codes:
        return [[]]
    if len(codes) <= 3:
        return [codes]
    pages: list[list[str]] = []
    i = 0
    while i < len(codes):
        rest = len(codes) - i
        if rest <= 3:
            pages.append(codes[i:])
            break
        pages.append(codes[i : i + 2])
        i += 2
    return pages


def _size_help_text(sizes: tuple[str, ...]) -> str:
    if not sizes:
        return "_Escribí *todos* para ver sin filtrar por talle._"
    if sizes[0].isdigit():
        sample = ", ".join(sizes[:4])
        return f"_Para otro talle escribí {sample} o *todos* (sin filtrar talle)._"
    extra = [s for s in sizes if s not in ("S", "M")][:3]
    sample = ", ".join(extra) if extra else ", ".join(sizes[:3])
    return f"_Para otro talle escribí {sample} o *todos* (sin filtrar talle)._"


def start_shop(*, get_categories_for_nav: CategoryResolver | None = None) -> BotReply:
    cats = _resolve_categories(get_categories_for_nav)
    return _reply_category_page(0, categories=cats)


def start_with_category(
    slug: str,
    wa_id: str | None = None,
    *,
    get_categories_for_nav: CategoryResolver | None = None,
    get_sizes_for_category: SizeResolver | None = None,
) -> BotReply:
    """Salta a elegir talle (ej. intent «jeans»)."""
    cats = _resolve_categories(get_categories_for_nav)
    name = _category_label(slug, cats)
    sizes = _resolve_sizes(slug, get_sizes_for_category)
    return _set_category_and_ask_size(slug, name, wa_id, sizes)


def _reply_category_page(
    page: int,
    wa_id: str | None = None,
    *,
    categories: list[dict],
) -> BotReply:
    pages = _category_pages(categories)
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


def _set_category_and_ask_size(
    slug: str,
    name: str,
    wa_id: str | None,
    sizes: list[str],
) -> BotReply:
    size_tuple = tuple(sizes)
    if wa_id:
        _sessions[wa_id] = ShopSession(
            step=ShopStep.SIZE,
            category_slug=slug,
            category_name=name,
            size_page=0,
            available_sizes=size_tuple,
        )
    return _reply_size_page(0, slug, name, size_tuple)


def _reply_size_page(page: int, slug: str, name: str, sizes: tuple[str, ...]) -> BotReply:
    codes = list(sizes)
    pages = _size_button_pages(codes)
    page = max(0, min(page, len(pages) - 1))
    chunk = pages[page]
    has_next = page < len(pages) - 1

    buttons: list[ButtonDef] = []
    if len(codes) <= 3:
        buttons = [ButtonDef(code, f"{PREFIX_SIZE}{code}") for code in codes[:3]]
    elif page == 0:
        buttons = [
            ButtonDef(chunk[0], f"{PREFIX_SIZE}{chunk[0]}"),
            ButtonDef(chunk[1], f"{PREFIX_SIZE}{chunk[1]}"),
            ButtonDef("Más talles", f"{CB_SHOP_SIZE_PAGE}:1"),
        ]
    else:
        for code in chunk[:3]:
            buttons.append(ButtonDef(code, f"{PREFIX_SIZE}{code}"))
        if has_next and len(buttons) == 2:
            buttons.append(ButtonDef("Más talles", f"{CB_SHOP_SIZE_PAGE}:{page + 1}"))

    cat_display = name if slug != "todos" else "todo el catálogo"
    help_txt = _size_help_text(sizes)
    if page == 0:
        intro = f"Perfecto: *{cat_display}*.\n\n¿Qué talle necesitás?\n{help_txt}"
    else:
        intro = f"Más talles para *{cat_display}*:\n{help_txt}"

    return BotReply(text=intro, buttons=buttons[:3])


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


def handle_callback(
    wa_id: str,
    data: str,
    *,
    get_categories_for_nav: CategoryResolver | None = None,
    get_sizes_for_category: SizeResolver | None = None,
) -> BotReply:
    data = (data or "").strip()
    cats = _resolve_categories(get_categories_for_nav)

    if data == CB_SHOP_START or data == CB_SHOP_AGAIN:
        _sessions[wa_id] = ShopSession(step=ShopStep.CATEGORY, category_page=0)
        return _reply_category_page(0, wa_id, categories=cats)

    if data == CB_SHOP_CANCEL:
        clear_session(wa_id)
        from whatsapp.conversation import get_welcome_reply

        return get_welcome_reply("")

    if data.startswith(PREFIX_CAT_PAGE):
        try:
            page = int(data.split(":", 1)[1])
        except (IndexError, ValueError):
            page = 0
        return _reply_category_page(page, wa_id, categories=cats)

    if data.startswith(PREFIX_CAT):
        slug = data.split(":", 1)[1].strip().lower()
        name = _category_label(slug, cats)
        sizes = _resolve_sizes(slug, get_sizes_for_category)
        return _set_category_and_ask_size(slug, name, wa_id, sizes)

    if data.startswith(CB_SHOP_SIZE_PAGE + ":"):
        session = _sessions.get(wa_id)
        if not session or session.step != ShopStep.SIZE:
            return start_shop(get_categories_for_nav=get_categories_for_nav)
        try:
            page = int(data.split(":", 1)[1])
        except (IndexError, ValueError):
            page = 1
        session.size_page = page
        return _reply_size_page(
            page,
            session.category_slug,
            session.category_name,
            session.available_sizes,
        )

    if data.startswith(PREFIX_SIZE):
        code = data.split(":", 1)[1].strip().upper()
        session = _sessions.pop(wa_id, None)
        if not session:
            return start_shop(get_categories_for_nav=get_categories_for_nav)
        return _finish_with_size(session, code if code != "ALL" else None)

    clear_session(wa_id)
    return start_shop(get_categories_for_nav=get_categories_for_nav)


def handle_text(
    wa_id: str,
    text: str,
    user_name: str = "",
    *,
    get_sizes_for_category: SizeResolver | None = None,
) -> Optional[BotReply]:
    """Si hay sesión de tienda activa, interpreta talle o cancelación."""
    del get_sizes_for_category  # sizes already stored on session
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
        allowed = set(session.available_sizes)
        if code in allowed:
            reply = _finish_with_size(session, code)
            _sessions.pop(wa_id, None)
            return reply

    hint = "Usá los botones de arriba o escribí un talle"
    if session.available_sizes and session.available_sizes[0].isdigit():
        hint += f" ({', '.join(session.available_sizes[:3])}…)"
    else:
        hint += " (S, M, L, XL…)"
    hint += ", *todos* o *cancelar*."
    return BotReply(text=hint, buttons=[])
