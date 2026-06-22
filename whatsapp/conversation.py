"""
Lógica de mensajes del bot (sin PyWa). Los handlers solo envían BotReply al cliente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from config import (
    _PROMO_BANNER,
    _STORES,
    get_bot_welcome_text,
    get_site_public_url,
)

# Callback data (máx. 3 botones por mensaje en WhatsApp)
CB_JEANS = "JEANS"
CB_TALLES = "TALLES"
CB_MENU = "MENU"
CB_CATALOGO = "CATALOGO"
CB_ESTADO_PEDIDO = "ESTADO_PEDIDO"
CB_ASESOR = "ASESOR"
CB_ENVIO = "ENVIO"
CB_TIENDAS = "TIENDAS"
CB_EMAIL_SI = "EMAIL_SI"
CB_EMAIL_NO = "EMAIL_NO"
CB_EMAIL_CONSENT_SI = "EMAIL_CONSENT_SI"
CB_EMAIL_CONSENT_NO = "EMAIL_CONSENT_NO"


class Intent(str, Enum):
    GREETING = "greeting"
    JEANS = "jeans"
    SIZES = "sizes"
    SHIPPING = "shipping"
    MIN_ORDER = "min_order"
    STORES = "stores"
    CATALOG = "catalog"
    ORDER_HELP = "order_help"
    ADVISOR = "advisor"
    HELP = "help"


@dataclass(frozen=True)
class ButtonDef:
    title: str
    callback_data: str


@dataclass
class BotReply:
    text: str
    buttons: list[ButtonDef] = field(default_factory=list)


def get_jeans_catalog_url() -> str:
    return f"{get_site_public_url()}/?cat=jeans"


def get_welcome_reply(user_name: str) -> BotReply:
    from whatsapp.shop_flow import CB_SHOP_START

    return BotReply(
        text=get_bot_welcome_text(user_name),
        buttons=[
            ButtonDef("Ver tienda", CB_SHOP_START),
            ButtonDef("Mi pedido", CB_ESTADO_PEDIDO),
            ButtonDef("Asesor", CB_ASESOR),
        ],
    )


def detect_intent(text: str) -> Intent:
    """Clasifica mensaje de texto (sin código de pedido)."""
    t = text.lower().strip()
    if not t:
        return Intent.GREETING

    if any(w in t for w in ("asesor", "humano", "persona", "vendedor", "atencion", "atención")):
        return Intent.ADVISOR
    if any(w in t for w in ("jean", "jeans", "denim", "pantalón", "pantalon")):
        return Intent.JEANS
    if any(w in t for w in ("talle", "talles", "medida", "medidas", "size", "tamaño", "tamano")):
        return Intent.SIZES
    if any(w in t for w in ("envio", "envío", "enviar", "delivery", "correo", "paquete")):
        return Intent.SHIPPING
    if any(
        w in t
        for w in (
            "minimo",
            "mínimo",
            "minima",
            "mínima",
            "cuanto es el minimo",
            "compra minima",
            "compra mínima",
        )
    ):
        return Intent.MIN_ORDER
    if any(w in t for w in ("tienda", "sucursal", "retiro", "local", "puntos de venta", "donde estan")):
        return Intent.STORES
    if any(w in t for w in ("catalogo", "catálogo", "ver todo", "comprar", "web", "pagina", "página")):
        return Intent.CATALOG
    if any(w in t for w in ("pedido", "codigo", "código", "orden", "compra web", "estado")):
        return Intent.ORDER_HELP
    if any(w in t for w in ("hola", "buenas", "buen dia", "buenos dias", "menu", "menú", "ayuda", "info")):
        return Intent.GREETING
    return Intent.HELP


def reply_for_intent(intent: Intent, user_name: str = "") -> BotReply:
    name = user_name.strip() or "ahí"
    base = get_site_public_url()
    jeans_url = get_jeans_catalog_url()

    if intent == Intent.JEANS:
        from whatsapp.shop_flow import start_with_category

        return start_with_category("jeans", None)

    if intent == Intent.SIZES:
        return BotReply(
            text=(
                "📏 *Guía de talles*\n\n"
                "• *Remeras, camperas, buzos*, etc.: talles *XS, S, M, L, XL y XXL*.\n"
                "• *Jeans y pantalones*: talles *numéricos* (34, 36, 38, 40, 42…).\n\n"
                "Tip: si estás entre dos talles, consultanos el calce del jean que te interesa. "
                "Podés combinar varios talles en el mismo pedido.\n\n"
                f"Catálogo de jeans: {jeans_url}"
            ),
            buttons=[
                ButtonDef("Ver jeans", CB_JEANS),
                ButtonDef("Envío", CB_ENVIO),
                ButtonDef("Asesor", CB_ASESOR),
            ],
        )

    if intent == Intent.SHIPPING or intent == Intent.MIN_ORDER:
        return BotReply(
            text=(
                "🚚 *Envíos y compra mínima*\n\n"
                f"{_PROMO_BANNER}\n\n"
                "Después de confirmar en la web, enviá el mensaje con tu *código de pedido* "
                "y un asesor te confirma costo de envío, medios de pago y tiempos."
            ),
            buttons=[
                ButtonDef("Ver jeans", CB_JEANS),
                ButtonDef("Estado de pedido", CB_ESTADO_PEDIDO),
                ButtonDef("Asesor", CB_ASESOR),
            ],
        )

    if intent == Intent.STORES:
        lines = ["🏪 *Puntos de retiro*\n"]
        for s in _STORES:
            lines.append(
                f"\n*{s['name']}*\n{s['address']}\n{s['hours']}\n_{s['note']}_"
            )
        lines.append("\n\nCoordiná retiro por acá después de confirmar tu pedido en la web.")
        return BotReply(text="".join(lines), buttons=_menu_buttons())

    if intent == Intent.CATALOG:
        from whatsapp.shop_flow import start_shop

        return start_shop()

    if intent == Intent.ORDER_HELP:
        return reply_for_callback(CB_ESTADO_PEDIDO)

    if intent == Intent.ADVISOR:
        return reply_for_callback(CB_ASESOR)

    if intent == Intent.GREETING:
        return get_welcome_reply(name)

    # HELP — no entendió; ofrece menú
    return BotReply(
        text=(
            "No estoy seguro de haber entendido 😊\n\n"
            "Podés escribir, por ejemplo:\n"
            "• *jeans* — ver modelos\n"
            "• *talles* — guía de medidas\n"
            "• *envío* — mínimo y envíos\n"
            "• *tiendas* — puntos de retiro\n"
            "• tu *código de pedido* (ej. OJ-20260519-8K4Q) si ya compraste en la web"
        ),
        buttons=[
            ButtonDef("Ver tienda", "SHOP_START"),
            ButtonDef("Talles", CB_TALLES),
            ButtonDef("Mi pedido", CB_ESTADO_PEDIDO),
        ],
    )


def route_text_message(
    text: str,
    user_name: str = "",
    wa_id: str | None = None,
    *,
    get_categories_for_nav=None,
    get_sizes_for_category=None,
) -> BotReply:
    """Respuesta para texto libre (sin código de pedido)."""
    intent = detect_intent(text)
    if wa_id and intent == Intent.JEANS:
        from whatsapp.shop_flow import start_with_category

        return start_with_category(
            "jeans",
            wa_id,
            get_categories_for_nav=get_categories_for_nav,
            get_sizes_for_category=get_sizes_for_category,
        )
    if wa_id and intent == Intent.CATALOG:
        from whatsapp.shop_flow import CB_SHOP_START, handle_callback

        return handle_callback(
            wa_id,
            CB_SHOP_START,
            get_categories_for_nav=get_categories_for_nav,
            get_sizes_for_category=get_sizes_for_category,
        )
    return reply_for_intent(intent, user_name)


def reply_for_callback(data: str) -> BotReply:
    data = (data or "").strip()
    base = get_site_public_url()
    jeans_url = get_jeans_catalog_url()

    if data == CB_JEANS:
        return BotReply(
            text=f"Jeans en la web:\n{jeans_url}\n\nCuando elijas, confirmá el pedido y enviá el código por acá.",
            buttons=[
                ButtonDef("Talles", CB_TALLES),
                ButtonDef("Envío", CB_ENVIO),
                ButtonDef("Asesor", CB_ASESOR),
            ],
        )

    if data == CB_TALLES:
        return reply_for_intent(Intent.SIZES)

    if data == CB_ENVIO:
        return reply_for_intent(Intent.SHIPPING)

    if data == CB_TIENDAS:
        return reply_for_intent(Intent.STORES)

    if data == CB_CATALOGO:
        return BotReply(
            text=f"Catálogo completo:\n{base}/?cat=todos",
            buttons=[
                ButtonDef("Ver jeans", CB_JEANS),
                ButtonDef("Talles", CB_TALLES),
                ButtonDef("Mi pedido", CB_ESTADO_PEDIDO),
            ],
        )

    if data == CB_MENU:
        return BotReply(
            text=(
                f"🛍️ *Catálogo:* {base}/?cat=todos\n"
                f"👖 *Jeans:* {jeans_url}\n\n"
                "*Pedido web:* confirmá en la tienda y enviá acá el mensaje con tu código.\n"
                "Escribí *estado* + código para consultar.\n\n"
                "También podés escribir: *envío*, *tiendas*, *asesor*."
            ),
            buttons=[
                ButtonDef("Estado pedido", CB_ESTADO_PEDIDO),
                ButtonDef("Envío", CB_ENVIO),
                ButtonDef("Asesor", CB_ASESOR),
            ],
        )

    if data == CB_ESTADO_PEDIDO:
        return BotReply(
            text=(
                "📦 *Tu pedido*\n\n"
                "Si ya confirmaste en la web, *reenviá el mensaje* con tu código "
                "(ej. OJ-20260519-8K4Q) y lo registramos.\n\n"
                "Para consultar estado, escribí: *estado OJ-...*"
            ),
        )

    if data == CB_ASESOR:
        return BotReply(
            text=(
                "👤 Un asesor de Outfit Jazmines te va a responder en breve.\n\n"
                "Si ya tenés pedido, incluí el *código* y el jean/talle que te interesa "
                "para agilizar la atención."
            ),
        )

    return reply_for_intent(Intent.HELP)


def _menu_buttons() -> list[ButtonDef]:
    return [
        ButtonDef("Ver jeans", CB_JEANS),
        ButtonDef("Catálogo", CB_CATALOGO),
        ButtonDef("Asesor", CB_ASESOR),
    ]


def reply_to_pywa_buttons(buttons: list[ButtonDef]) -> Optional[list]:
    """Convierte ButtonDef a tipos PyWa (import lazy en handlers)."""
    if not buttons:
        return None
    from pywa import types

    return [types.Button(title=b.title, callback_data=b.callback_data) for b in buttons[:3]]
