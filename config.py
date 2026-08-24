"""
Textos, marca, redes y contactos del sitio.
Override por variable de entorno cuando aplica.
"""
import os
from datetime import datetime

_BRAND = os.getenv("SITE_BRAND_NAME", "Outfit Jazmines")
_BRAND_LOGO_ANIMATED = os.getenv("SITE_BRAND_LOGO_ANIMATED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
APP_DEBUG = os.getenv("APP_DEBUG", "false").lower() in ("1", "true", "yes", "on")
ADMIN_LOGIN_NAV_VISIBLE = os.getenv(
    "ADMIN_LOGIN_NAV_VISIBLE",
    "true" if APP_DEBUG else "false",
).lower() in ("1", "true", "yes", "on")
ADMIN_LOGIN_PATH = os.getenv("ADMIN_LOGIN_PATH", "/login").strip() or "/login"
# Paleta del logo (alineada al PNG: letras negras + jazmín a color)
_BRAND_LOGO_COLORS = {
    "letter": os.getenv("SITE_BRAND_LOGO_LETTER", "#111111"),
    "stem": os.getenv("SITE_BRAND_LOGO_STEM", "#3D6B4F"),
    "leaf": os.getenv("SITE_BRAND_LOGO_LEAF", "#2F5A40"),
    "petal": os.getenv("SITE_BRAND_LOGO_PETAL", "#FAFAF8"),
    "petal_center": os.getenv("SITE_BRAND_LOGO_PETAL_CENTER", "#E8C547"),
    "bud": os.getenv("SITE_BRAND_LOGO_BUD", "#F5F5F0"),
}
_PROMO_BANNER = os.getenv(
    "SITE_PROMO_BANNER",
    "Compra mínima $100.000 · Envío a todo el país",
)


def get_default_promo_banner_text() -> str:
    return _PROMO_BANNER

# Redes
_SOCIAL_FACEBOOK = os.getenv(
    "SITE_FACEBOOK_URL",
    "https://www.facebook.com/jazmines.jazmines.56",
)
_SOCIAL_INSTAGRAM = os.getenv(
    "SITE_INSTAGRAM_URL",
    "https://www.instagram.com/outfit_jazmines",
)

# Contactos (números en formato internacional sin signos para wa.me)
_WHATSAPP_BOT = os.getenv("SITE_WA_BOT", "5491125298412")
_WHATSAPP_ASESOR = os.getenv("SITE_WA_ASESOR", "5491126295590")
_SITE_PUBLIC_URL = os.getenv("SITE_PUBLIC_URL", "https://outfitjazmines.com.ar")


def get_whatsapp_bot_number() -> str:
    return _WHATSAPP_BOT


def get_whatsapp_asesor_number() -> str:
    return _WHATSAPP_ASESOR


def get_site_public_url() -> str:
    return _SITE_PUBLIC_URL.rstrip("/")


# Notificación admin por email (SMTP)
_ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL", "").strip()
_SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
_SMTP_USER = os.getenv("SMTP_USER", "").strip()
_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
_SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
_ADMIN_NOTIFY_EMAIL_ENABLED = os.getenv("ADMIN_NOTIFY_EMAIL_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def get_admin_notify_email() -> str:
    return _ADMIN_NOTIFY_EMAIL


def is_admin_notify_email_enabled() -> bool:
    return _ADMIN_NOTIFY_EMAIL_ENABLED


def get_smtp_host() -> str:
    return _SMTP_HOST


def get_smtp_port() -> int:
    return _SMTP_PORT


def get_smtp_user() -> str:
    return _SMTP_USER


def get_smtp_password() -> str:
    return _SMTP_PASSWORD


def get_smtp_from() -> str:
    return _SMTP_FROM or _SMTP_USER


# Fallback para tests de WhatsApp sin base de datos
_FALLBACK_CATALOG_CATEGORIES = [
    {"name": "Jeans", "slug": "jeans"},
    {"name": "Pantalones", "slug": "pantalones"},
    {"name": "Remeras", "slug": "remeras"},
]


def get_catalog_categories() -> list[dict]:
    """Deprecated: usar list_categories_for_nav(db). Fallback para tests."""
    return list(_FALLBACK_CATALOG_CATEGORIES)


def build_nav_links(categories: list[dict]) -> list[dict]:
    """Arma nav_links con dropdown Productos desde categorías activas en DB."""
    children = [{"label": "Ver todo", "href": "/?cat=todos"}]
    children.extend(
        {"label": c["name"], "href": f"/?cat={c['slug']}"}
        for c in categories
    )
    return [
        {"label": "Inicio", "href": "/"},
        {
            "label": "Productos",
            "href": "/?cat=todos",
            "dropdown": True,
            "children": children,
        },
        {"label": "Sale", "href": "/sale", "highlight": True},
        {"label": "Contacto", "href": "/contacto"},
        {"label": "Puntos de venta", "href": "/puntos-de-venta"},
    ]


def get_bot_welcome_text(user_name: str) -> str:
    return (
        f"¡Hola {user_name}! Soy el asistente de *{_BRAND}* 👖\n\n"
        f"{_PROMO_BANNER}\n\n"
        "Te ayudo con *jeans*, talles, envíos y retiro en sucursal. "
        "Elegí en la web y, al confirmar, enviá acá el mensaje con tu *código de pedido*.\n\n"
        "Usá los botones o escribí *jeans*, *talles*, *envío* o *asesor*."
    )


def get_order_confirmation_reply(user_name: str | None, order_summary: str) -> str:
    """Respuesta del bot cuando la clienta envía el pedido por WhatsApp."""
    who = (user_name or "").strip() or "Gracias"
    greeting = f"¡{who}, gracias por comprar en *{_BRAND}*!" if user_name else f"¡Gracias por comprar en *{_BRAND}*!"
    return (
        f"{greeting} 🛍️\n\n"
        "Recibimos tu pedido y *ya lo estamos preparando*.\n\n"
        f"{order_summary}\n\n"
        "Un asesor te va a confirmar stock, envío y forma de pago a la brevedad."
    )

# Sucursales (puntos de venta con retiro confirmado)
_STORES = [
    {
        "name": "José C. Paz",
        "address": "Coronel Arias 585, José C. Paz, Buenos Aires",
        "hours": "Lunes a sábado · 9:00 a 16:00",
        "note": "Coordinar el horario de retiro con confirmación previa.",
        "maps_url": "https://www.google.com/maps/search/?api=1&q=Coronel+Arias+585,+Jose+C.+Paz,+Buenos+Aires",
    },
]

# Menú principal (Productos se completa en page_context desde DB)
_NAV_LINKS = build_nav_links([])

# Talles: catálogo y grupos por categoría viven en DB (sizes.size_group, categories.size_group).
DEFAULT_SIZE_GROUP = "letter"

_NUMERIC_SIZE_SEED = [
    ("34", "34", 75),
    ("36", "36", 76),
    ("38", "38", 77),
    ("40", "40", 78),
    ("42", "42", 79),
]


def get_numeric_size_seed() -> list[tuple[str, str, int]]:
    return list(_NUMERIC_SIZE_SEED)


PRODUCT_ITEM_TITLE_MAX_LEN = 255
PRODUCT_DESCRIPTION_MAX_LEN = 1024


def get_template_context() -> dict:
    """Contexto compartido para todas las plantillas Jinja2."""
    year = datetime.now().year
    return {
        "brand_name": _BRAND,
        "brand_logo_animated": _BRAND_LOGO_ANIMATED,
        "brand_logo_colors": _BRAND_LOGO_COLORS,
        "app_debug": APP_DEBUG,
        "admin_login_nav_visible": ADMIN_LOGIN_NAV_VISIBLE,
        "admin_login_path": ADMIN_LOGIN_PATH,
        "page_title_catalog": f"{_BRAND} - Catálogo",
        "page_title_product": "Detalle de producto",
        "page_title_admin": "Panel Admin",
        "page_title_admin_edit": "Editar producto",
        "page_title_admin_help": "Ayuda Admin",
        "admin_help_link": "Ayuda",
        "admin_help_heading": "Manual de la administradora",
        "admin_help_lead": "Cómo cargar prendas, talles, colores, stock y pedidos desde el panel.",
        "admin_help_back": "← Volver al panel",
        "page_title_login": "Login Admin",
        "product_item_title_max_len": PRODUCT_ITEM_TITLE_MAX_LEN,
        "product_description_max_len": PRODUCT_DESCRIPTION_MAX_LEN,
        "page_title_sale": f"{_BRAND} - Sale",
        "page_title_contact": f"{_BRAND} - Contacto",
        "page_title_stores": f"{_BRAND} - Puntos de venta",
        "promo_banner_text": _PROMO_BANNER,
        "promo_banner_visible": True,
        "hero_headline": "Colección destacada",
        "hero_subtitle": "Stock para retiro inmediato + opción a encargo",
        "footer_copyright": f"© {year} {_BRAND}",
        "footer_follow": "Seguinos",
        "footer_help": "Atención al cliente",
        "footer_pickup": "Retiro y atención",
        "footer_pickup_hint": "Lunes a sábado · 9:00 a 16:00 (coordinar)",
        "btn_add_to_cart": "Agregar",
        "placeholder_no_image": "Sin imagen",
        "cart_title": "Tu carrito",
        "cart_total_label": "Total",
        "cart_btn_whatsapp": "Confirmar y enviar por WhatsApp",
        "cart_btn_whatsapp_retry": "Reabrir WhatsApp (mismo pedido)",
        "cart_empty": "Tu carrito está vacío",
        "cart_subtotal_immediate": "Subtotal en stock",
        "cart_subtotal_encargo": "Subtotal por encargo",
        "cart_savings": "Ahorrás",
        "nav_login": "Login",
        "nav_logout": "Logout",
        "nav_admin": "Admin Panel",
        "nav_search_placeholder": "Buscar prendas…",
        "nav_search_aria": "Buscar productos",
        "nav_links": _NAV_LINKS,
        "nav_categories": [],
        "nav_categories_label": "Productos",
        "nav_productos_ver_todo": "Ver todo",
        "admin_tab_banners": "Banners inicio",
        "admin_banners_heading": "Banners de la página de inicio",
        "admin_banners_help": "Arriba: la franja negra de compra mínima / envío. Abajo: banners de imagen o video (~⅓ de pantalla en móvil). 1 banner = ancho completo; 2 = mitad cada uno; 3+ = carrusel. Preferí WebP/JPEG o MP4 corto (sin audio); evitá GIF pesados.",
        "admin_promo_heading": "Franja negra superior",
        "admin_promo_help": "Texto que se ve en la home (barra negra), en Sale y en el pie. Si la desactivás o dejás el texto vacío, no se muestra.",
        "admin_promo_label_text": "Texto de la franja",
        "admin_promo_label_active": "Visible",
        "admin_promo_btn_save": "Guardar franja",
        "admin_promo_msg_saved": "Franja actualizada.",
        "admin_promo_text_max": 200,
        "admin_banners_media_heading": "Banners de imagen o video",
        "admin_banners_col_image": "Vista previa",
        "admin_banners_col_type": "Tipo",
        "admin_banners_col_title": "Título",
        "admin_banners_col_link": "Enlace",
        "admin_banners_col_order": "Orden",
        "admin_banners_col_active": "Activo",
        "admin_banners_col_actions": "Acciones",
        "admin_banners_label_image_url": "URL de imagen o video",
        "admin_banners_label_upload": "O subir archivo (JPG, PNG, WebP, GIF, MP4, WebM)",
        "admin_banners_type_image": "Imagen",
        "admin_banners_type_video": "Video",
        "admin_banners_label_title": "Título (opcional)",
        "admin_banners_label_subtitle": "Subtítulo (opcional)",
        "admin_banners_label_link": "Enlace al hacer clic",
        "admin_banners_label_order": "Orden",
        "admin_banners_label_active": "Visible en inicio",
        "admin_banners_btn_save": "Guardar banner",
        "admin_banners_btn_update": "Actualizar banner",
        "admin_banners_btn_cancel": "Cancelar",
        "admin_banners_list_empty": "Todavía no hay banners.",
        "admin_banners_msg_saved": "Banner guardado.",
        "admin_banners_msg_updated": "Banner actualizado.",
        "admin_banners_msg_deleted": "Banner eliminado.",
        "admin_banners_delete_confirm": "¿Eliminar este banner?",
        "btn_add_cart_detail": "Agregar al carrito",
        "btn_add_cart_immediate": "Agregar – En stock para retiro",
        "btn_add_cart_encargo_days": "Encargar – llega en aprox. {days} días",
        "btn_add_cart_encargo_no_days": "Encargar – consultar días por WhatsApp",
        "btn_buy_now": "Comprar ahora",
        "label_stock_prefix": "Stock disponible:",
        "label_no_description": "Sin descripción",
        "admin_panel_heading": "Panel de Administración",
        "admin_edit_heading": "Editar producto",
        "admin_btn_back_list": "← Volver a Mis productos",
        "admin_detail_open_hint": "Ver en la tienda (abre en nueva pestaña)",
        "admin_edit_saved_back": "Cambios guardados.",
        "admin_btn_save_return_list": "Guardar y volver al listado",
        "admin_btn_save_continue_here": "Guardar y seguir aquí",
        "admin_tab_new": "Nuevo producto",
        "admin_tab_bulk_import": "Importación masiva",
        "admin_tab_list": "Mis productos",
        "admin_tab_orders": "Pedidos",
        "admin_tab_catalog": "Catálogo",
        "admin_catalog_tab_heading": "Catálogo de la tienda",
        "admin_catalog_tab_help": "Gestioná categorías, talles y colores. Los cambios se reflejan en el menú web, WhatsApp y formularios de producto.",
        "admin_catalog_sub_categories": "Categorías",
        "admin_catalog_sub_sizes": "Talles",
        "admin_catalog_sub_colors": "Colores",
        "admin_categories_tab_heading": "Categorías",
        "admin_categories_tab_help": "Creá categorías, definí el tipo de talle y el orden del menú. El slug queda fijo al crear (se usa en URLs y filtros).",
        "admin_categories_new_name": "Nombre",
        "admin_categories_new_name_placeholder": "Ej. Enteritos",
        "admin_categories_new_slug": "Slug (URL)",
        "admin_categories_new_slug_placeholder": "enteritos",
        "admin_categories_slug_help": "Opcional al crear. Si lo dejás vacío, se genera del nombre. No se puede cambiar después.",
        "admin_categories_col_name": "Nombre",
        "admin_categories_col_slug": "Slug",
        "admin_categories_col_group": "Tipo de talle",
        "admin_categories_col_order": "Orden",
        "admin_categories_col_active": "Activa",
        "admin_categories_col_products": "Productos",
        "admin_categories_col_actions": "Acciones",
        "admin_categories_btn_add": "Agregar categoría",
        "admin_categories_btn_cancel": "Cancelar",
        "admin_categories_btn_update": "Guardar cambios",
        "admin_categories_loading": "Cargando categorías…",
        "admin_categories_empty": "Todavía no hay categorías.",
        "admin_categories_load_err": "No se pudieron cargar las categorías.",
        "admin_categories_msg_added": "Categoría creada.",
        "admin_categories_msg_updated": "Categoría actualizada.",
        "admin_categories_msg_deleted": "Categoría eliminada.",
        "admin_categories_delete_confirm": "¿Eliminar categoría \"{name}\"?",
        "admin_categories_name_required": "Escribí el nombre de la categoría.",
        "admin_categories_active_label": "Visible en menú y tienda",
        "admin_orders_heading": "Pedidos de la tienda",
        "admin_orders_help": "Al confirmar el carrito se crea el pedido y se avisa al asesor (aún sin saber quién es). El nombre aparece cuando la clienta envía el WhatsApp con el código. Si reabre el mismo carrito, se reutiliza el código y no se vuelve a avisar.",
        "admin_orders_col_code": "Código",
        "admin_orders_col_date": "Fecha",
        "admin_orders_col_customer": "Cliente",
        "admin_orders_col_status": "Estado",
        "admin_orders_col_total": "Total",
        "admin_orders_col_actions": "Acciones",
        "admin_orders_filter_all": "Todos los estados",
        "admin_orders_status_enviado": "Enviado WA",
        "admin_orders_status_recibido": "Recibido",
        "admin_orders_status_en_revision": "En revisión",
        "admin_orders_status_confirmado": "Confirmado",
        "admin_orders_status_cancelado": "Cancelado",
        "admin_orders_btn_confirm": "Confirmar",
        "admin_orders_btn_review": "En revisión",
        "admin_orders_btn_cancel": "Cancelar",
        "admin_orders_empty": "No hay pedidos todavía.",
        "admin_orders_load_error": "No se pudieron cargar los pedidos.",
        "admin_orders_msg_updated": "Estado del pedido actualizado.",
        "admin_orders_lines": "Detalle",
        "admin_orders_pending_wa": "Pendiente de WhatsApp",
        "admin_orders_retries": "{n} reintento(s) del mismo carrito",
        "admin_list_heading": "Catálogo cargado",
        "admin_search_label": "Buscar por nombre",
        "admin_search_placeholder": "Nombre del artículo…",
        "admin_search_aria": "Buscar producto por nombre",
        "admin_list_no_results": "No hay productos que coincidan con la búsqueda.",
        "admin_btn_save": "Guardar producto",
        "admin_btn_update": "Actualizar producto",
        "admin_btn_cancel_edit": "Cancelar edición",
        "admin_col_photo": "Foto",
        "admin_col_title": "Producto",
        "admin_col_price": "Precio",
        "admin_col_actions": "Acciones",
        "admin_edit": "Editar",
        "admin_delete": "Eliminar",
        "admin_list_empty": "Todavía no hay productos.",
        "admin_list_load_error": "No se pudo cargar la lista.",
        "admin_delete_confirm_title": "¿Eliminar producto?",
        "admin_delete_confirm_hint": "Esta acción no se puede deshacer.",
        "admin_delete_confirm_btn": "Eliminar",
        "admin_delete_cancel_btn": "Cancelar",
        "admin_msg_saved": "El producto se dio de alta correctamente.",
        "admin_msg_updated": "Producto actualizado.",
        "admin_msg_deleted": "Producto eliminado.",
        "admin_msg_error": "Algo salió mal. Revisá tu sesión o intentá de nuevo.",
        "admin_provider_heading": "Importar desde proveedor",
        "admin_provider_help": "Pegá un link de So Chic, Las Locas, Nissie Denim o HOLIC. El producto se carga desactivado; activalo y ajustá el precio cuando quieras publicarlo.",
        "admin_provider_url_label": "Link del producto",
        "admin_provider_url_placeholder": "https://sochic.com.ar/product/... o https://laslocas.com/ficha-... o https://nissiedenim.com.ar/productos/...",
        "admin_provider_btn": "Importar producto",
        "admin_provider_importing": "Importando producto...",
        "admin_provider_created": "Producto importado correctamente (desactivado).",
        "admin_provider_created_active": "Producto importado y publicado como activo.",
        "admin_provider_exists": "Ese producto ya estaba cargado.",
        "admin_provider_status_label": "Publicar activo al importar",
        "admin_provider_status_help": "Si no lo marcás, el producto queda desactivado hasta activarlo en edición.",
        "admin_nissie_bulk_heading": "Importación masiva Nissie Denim",
        "admin_nissie_bulk_help": "Importa todo el catálogo de Nissie. Solo se agregan productos nuevos; los existentes no se modifican. Todo queda desactivado para que revises precio y lo actives.",
        "admin_nissie_bulk_btn": "Importar catálogo Nissie",
        "admin_nissie_bulk_confirm": "¿Importar el catálogo completo de Nissie? Solo se agregarán productos nuevos, todos desactivados.",
        "admin_nissie_bulk_running": "Importación en curso…",
        "admin_nissie_bulk_done": "Importación finalizada:",
        "admin_nissie_bulk_created": "creados",
        "admin_nissie_bulk_skipped": "omitidos",
        "admin_nissie_bulk_failed": "con error",
        "admin_nissie_bulk_errors_heading": "Productos con error",
        "admin_nissie_bulk_view_pending": "Ver pendientes de revisión (Nissie inactivos)",
        "admin_nissie_bulk_already_running": "Ya hay una importación masiva en curso.",
        "admin_bulk_tab_heading": "Importación masiva por proveedor",
        "admin_bulk_tab_help": "Importación automática desde proveedores: una ficha por URL o catálogos completos (Nissie, HOLIC, Las Locas). Solo se agregan productos nuevos; todo queda desactivado para revisar precio antes de publicar.",
        "admin_holic_bulk_heading": "Importación masiva HOLIC",
        "admin_holic_bulk_help": "Importa todo el catálogo de HOLIC. Solo se agregan productos nuevos; los existentes no se modifican. Todo queda desactivado para que revises precio y lo actives.",
        "admin_holic_bulk_btn": "Importar catálogo HOLIC",
        "admin_holic_bulk_confirm": "¿Importar el catálogo completo de HOLIC? Solo se agregarán productos nuevos, todos desactivados.",
        "admin_holic_bulk_running": "Importación HOLIC en curso…",
        "admin_holic_bulk_done": "Importación HOLIC finalizada:",
        "admin_holic_bulk_created": "creados",
        "admin_holic_bulk_skipped": "omitidos",
        "admin_holic_bulk_failed": "con error",
        "admin_holic_bulk_errors_heading": "Productos HOLIC con error",
        "admin_holic_bulk_view_pending": "Ver pendientes de revisión (HOLIC inactivos)",
        "admin_holic_bulk_already_running": "Ya hay una importación masiva de HOLIC en curso.",
        "admin_laslocas_bulk_heading": "Importación masiva Las Locas",
        "admin_laslocas_bulk_help": "Importa fichas de Las Locas por categoría del mayorista. Requiere LOGIN_EMAIL y LOGIN_PASS en el servidor. Solo productos nuevos, todos desactivados.",
        "admin_laslocas_bulk_category_label": "Categoría Las Locas",
        "admin_laslocas_bulk_all_categories": "Todas las categorías",
        "admin_laslocas_bulk_max_pages_label": "Máx. páginas por categoría",
        "admin_laslocas_bulk_max_pages_help": "0 = sin límite (recorre todo el listado).",
        "admin_laslocas_bulk_btn": "Importar Las Locas",
        "admin_laslocas_bulk_confirm": "¿Iniciar importación masiva de Las Locas? Solo se agregarán productos nuevos, todos desactivados.",
        "admin_laslocas_bulk_running": "Importación Las Locas en curso…",
        "admin_laslocas_bulk_done": "Importación Las Locas finalizada:",
        "admin_laslocas_bulk_created": "creados",
        "admin_laslocas_bulk_skipped": "omitidos",
        "admin_laslocas_bulk_failed": "con error",
        "admin_laslocas_bulk_errors_heading": "Productos Las Locas con error",
        "admin_laslocas_bulk_view_pending": "Ver pendientes de revisión (Las Locas inactivos)",
        "admin_laslocas_bulk_already_running": "Ya hay una importación masiva de Las Locas en curso.",
        "admin_bulk_phase_discover": "Explorando catálogo…",
        "admin_bulk_phase_import": "Importando",
        "admin_bulk_elapsed": "Tiempo transcurrido",
        "admin_bulk_stale_warning": "Posible importación interrumpida (sin actividad reciente).",
        "admin_bulk_cancel_btn": "Marcar como fallida",
        "admin_bulk_cancel_confirm": "¿Marcar esta importación como fallida? No se revertirán productos ya creados.",
        "admin_bulk_progress_detail": "Detalle",
        "admin_list_provider_filter_label": "Origen",
        "admin_list_provider_all": "Todos los orígenes",
        "admin_list_provider_nissie": "Nissie Denim",
        "admin_list_provider_sochic": "So Chic",
        "admin_list_provider_laslocas": "Las Locas",
        "admin_list_provider_holic": "HOLIC",
        "admin_col_provider": "Origen",
        "admin_list_status_filter_label": "Estado",
        "admin_list_status_all": "Todos",
        "admin_list_status_active": "Solo activos",
        "admin_list_status_inactive": "Solo inactivos",
        "admin_col_status": "Estado",
        "admin_status_active": "Activo",
        "admin_status_inactive": "Inactivo",
        "admin_product_active_label": "Producto activo (visible en la tienda)",
        "admin_product_active_help": "Para activarlo hace falta categoría y al menos un talle con stock o encargo. Desmarcá para ocultarlo.",
        "admin_publish_need_category": "Elegí una categoría.",
        "admin_publish_need_price": "Indicá un precio mayor a 0.",
        "admin_publish_need_stock": "Cargá al menos un talle con unidades en local o por encargo.",
        "admin_publish_blocked": "No se puede activar:",
        "admin_edit_mode_hint": "Estás editando un producto. Podés cambiar datos y, si querés, nuevas fotos.",
        "label_images_optional": "Imágenes (opcional; en edición solo se suben si querés reemplazar todas)",
        "admin_variants_heading": "Talles y disponibilidad",
        "admin_variants_help": "Indicá stock por talle. Si el producto tiene colores, completá cada combinación talle + color (0 sin encargo = sin stock, se muestra tachado en la tienda).",
        "admin_variants_col_size": "Talle",
        "admin_variants_col_color": "Color",
        "admin_variants_col_stock": "Uds. en local",
        "admin_variants_col_encargo": "Por encargo",
        "admin_variants_col_days": "Días (estimado)",
        "admin_colors_heading": "Colores disponibles",
        "admin_colors_help": "Marcá los colores en los que se puede pedir esta prenda. La clienta deberá elegir uno al comprar.",
        "admin_colors_select_help": "Marcá los colores disponibles para esta prenda. Para crear o corregir colores, usá la pestaña Catálogo.",
        "admin_colors_manage_link": "Gestionar colores",
        "admin_colors_new_label": "Color nuevo",
        "admin_colors_new_placeholder": "Ej. Verde musgo",
        "admin_colors_btn_add": "Agregar color",
        "admin_colors_pick_label": "Tono del color",
        "admin_colors_presets_label": "Tonos rápidos",
        "admin_colors_loading": "Cargando colores…",
        "admin_colors_empty_catalog": "Todavía no hay colores en el catálogo.",
        "admin_colors_msg_added": "Color agregado al catálogo.",
        "admin_colors_tab_heading": "Catálogo de colores",
        "admin_colors_tab_help": "Creá y editá los colores del catálogo. En Prendas ves si está en uso y a qué ficha está asignado. Solo se puede borrar un color sin prendas.",
        "admin_colors_col_swatch": "Muestra",
        "admin_colors_col_name": "Nombre",
        "admin_colors_col_hex": "Hex",
        "admin_colors_col_products": "Prendas",
        "admin_colors_unused": "Sin uso",
        "admin_colors_inactive_badge": "inactiva",
        "admin_colors_col_actions": "Acciones",
        "admin_colors_btn_cancel": "Cancelar",
        "admin_colors_btn_update": "Guardar cambios",
        "admin_colors_msg_updated": "Color actualizado.",
        "admin_colors_msg_deleted": "Color eliminado.",
        "admin_colors_delete_confirm": "¿Eliminar \"{name}\"?",
        "admin_colors_name_required": "Escribí el nombre del color.",
        "admin_colors_hex_required": "Elegí un tono de color válido.",
        "admin_colors_load_err": "No se pudieron cargar los colores.",
        "admin_sizes_tab_heading": "Catálogo de talles",
        "admin_sizes_tab_help": "Creá y editá los talles del catálogo. El tipo de talle por categoría se configura en la sección Categorías.",
        "admin_sizes_new_code": "Código",
        "admin_sizes_new_code_placeholder": "Ej. M o 38",
        "admin_sizes_new_label": "Etiqueta",
        "admin_sizes_new_label_placeholder": "Ej. M o 38",
        "admin_sizes_group_label": "Tipo",
        "admin_sizes_group_letter": "Letra (S, M, L…)",
        "admin_sizes_group_numeric": "Numérico (34, 36, 38…)",
        "admin_sizes_btn_add": "Agregar talle",
        "admin_sizes_btn_cancel": "Cancelar",
        "admin_sizes_btn_update": "Guardar cambios",
        "admin_sizes_col_code": "Código",
        "admin_sizes_col_label": "Etiqueta",
        "admin_sizes_col_group": "Tipo",
        "admin_sizes_col_order": "Orden",
        "admin_sizes_col_actions": "Acciones",
        "admin_sizes_loading": "Cargando talles…",
        "admin_sizes_empty_catalog": "Todavía no hay talles en el catálogo.",
        "admin_sizes_load_err": "No se pudieron cargar los talles.",
        "admin_sizes_msg_added": "Talle agregado al catálogo.",
        "admin_sizes_msg_updated": "Talle actualizado.",
        "admin_sizes_msg_deleted": "Talle eliminado.",
        "admin_sizes_delete_confirm": "¿Eliminar talle \"{name}\"?",
        "admin_sizes_code_required": "Escribí el código del talle.",
        "admin_sizes_label_required": "Escribí la etiqueta del talle.",
        "admin_sizes_categories_heading": "Tipo de talle por categoría",
        "admin_sizes_categories_help": "Elegí si cada categoría usa talles con letra o numéricos en la tienda y en WhatsApp.",
        "admin_sizes_categories_col_name": "Categoría",
        "admin_sizes_categories_col_group": "Tipo de talle",
        "admin_sizes_categories_msg_updated": "Categoría actualizada.",
        "admin_sizes_manage_link": "Gestionar talles",
        "admin_sizes_select_help": "Completá stock por talle según la categoría del producto. Para crear o corregir talles, usá la pestaña Catálogo.",
        "detail_select_color": "Elegí un color",
        "detail_add_requires_color": "Seleccioná un color antes de agregar al carrito.",
        "admin_label_category": "Categoría",
        "admin_label_category_none": "(sin categoría)",
        "admin_sale_heading": "Promoción / Sale",
        "admin_sale_toggle": "Marcar este producto como Sale",
        "admin_sale_discount_label": "Descuento (%)",
        "admin_sale_help": "Si marcás Sale y cargás un % de descuento, el precio final se calcula automáticamente.",
        "label_catalog_cta": "Ver producto",
        "label_badge_inmediato": "Retiro ya",
        "label_badge_encargo": "Encargo",
        "label_badge_sale": "SALE",
        "detail_select_size": "Elegí un talle",
        "detail_availability": "Disponibilidad",
        "detail_summary_colors": "Colores",
        "detail_summary_sizes": "Talles",
        "detail_unavailable_in_color": "No disponible en este color",
        "detail_unavailable_in_size": "No disponible en este talle",
        "detail_immediate": "Retiro en el local",
        "detail_encargo": "Pedido / próximos días",
        "detail_add_requires_size": "Seleccioná un talle antes de agregar al carrito.",
        "detail_cannot_buy": "Esta prenda no se puede pedir por la web ahora. Escribinos por WhatsApp.",
        "detail_price_was": "Antes",
        "detail_price_now": "Ahora",
        "label_title": "Título",
        "label_price": "Precio",
        "label_description": "Descripción",
        "admin_description_limit_help": "Máximo 1024 caracteres.",
        "admin_btn_upload": "Subir fotos",
        "login_heading": "Login Admin",
        "label_username": "Usuario",
        "label_password": "Contraseña",
        "btn_sign_in": "Ingresar",
        # Redes
        "social_facebook_url": _SOCIAL_FACEBOOK,
        "social_instagram_url": _SOCIAL_INSTAGRAM,
        # Contactos: dos canales aclarados
        "contact_bot_number": _WHATSAPP_BOT,
        "checkout_whatsapp_number": _WHATSAPP_BOT,
        "site_public_url": _SITE_PUBLIC_URL,
        "contact_bot_label": "Bot WhatsApp",
        "contact_bot_url": f"https://wa.me/{_WHATSAPP_BOT}",
        "contact_asesor_number": _WHATSAPP_ASESOR,
        "contact_asesor_label": "Asesor comercial",
        "contact_asesor_url": f"https://wa.me/{_WHATSAPP_ASESOR}",
        # Sucursales
        "stores": _STORES,
        # Página contacto
        "contact_title": "Contacto",
        "contact_subtitle": "Atención por WhatsApp y redes",
        "contact_intro": "Escribinos, te respondemos durante el horario de atención (lunes a sábado de 9:00 a 16:00).",
        "contact_choose_help": "Elegí el canal según tu consulta:",
        "contact_open_in_whatsapp": "Abrir en WhatsApp",
        "contact_bot_desc": "Consultas rápidas, catálogo y disponibilidad.",
        "contact_asesor_desc": "Hablar con una persona del local para asesoramiento personalizado.",
        # Página puntos de venta
        "stores_title": "Puntos de venta",
        "stores_subtitle": "Retirá tu pedido en cualquiera de nuestras direcciones",
        "stores_hours_label": "Horario",
        "stores_address_label": "Dirección",
        "stores_open_maps": "Cómo llegar",
        "stores_call_to_arrange": "Coordinar retiro por WhatsApp",
    }
