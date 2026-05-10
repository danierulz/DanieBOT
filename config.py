"""
Textos, marca, redes y contactos del sitio.
Override por variable de entorno cuando aplica.
"""
import os
from datetime import datetime

_BRAND = os.getenv("SITE_BRAND_NAME", "Outfit Jazmines")
_PROMO_BANNER = os.getenv(
    "SITE_PROMO_BANNER",
    "Compra mínima $100.000 · Envío a todo el país",
)

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

# Sucursales (puntos de venta con retiro confirmado)
_STORES = [
    {
        "name": "José C. Paz",
        "address": "Coronel Arias 585, José C. Paz, Buenos Aires",
        "hours": "Lunes a sábado · 9:00 a 16:00",
        "note": "Coordinar el horario de retiro con confirmación previa.",
        "maps_url": "https://www.google.com/maps/search/?api=1&q=Coronel+Arias+585,+Jose+C.+Paz,+Buenos+Aires",
    },
    {
        "name": "Ingeniero Pablo Nogués",
        "address": "Boulogne Sur Mer 2779, Ingeniero Pablo Nogués, Buenos Aires",
        "hours": "Lunes a sábado · 9:00 a 16:00",
        "note": "Coordinar el horario de retiro con confirmación previa.",
        "maps_url": "https://www.google.com/maps/search/?api=1&q=Boulogne+Sur+Mer+2779,+Ingeniero+Pablo+Nogues,+Buenos+Aires",
    },
]

# Menú principal
_NAV_LINKS = [
    {"label": "Inicio", "href": "/"},
    {"label": "Productos", "href": "/?cat=todos"},
    {"label": "Sale", "href": "/sale", "highlight": True},
    {"label": "Contacto", "href": "/contacto"},
    {"label": "Puntos de venta", "href": "/puntos-de-venta"},
]


def get_template_context() -> dict:
    """Contexto compartido para todas las plantillas Jinja2."""
    year = datetime.now().year
    return {
        "brand_name": _BRAND,
        "page_title_catalog": f"{_BRAND} - Catálogo",
        "page_title_product": "Detalle de producto",
        "page_title_admin": "Panel Admin",
        "page_title_admin_edit": "Editar producto",
        "page_title_login": "Login Admin",
        "page_title_sale": f"{_BRAND} - Sale",
        "page_title_contact": f"{_BRAND} - Contacto",
        "page_title_stores": f"{_BRAND} - Puntos de venta",
        "promo_banner_text": _PROMO_BANNER,
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
        "nav_categories_label": "Productos",
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
        "admin_tab_list": "Mis productos",
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
        "admin_edit_mode_hint": "Estás editando un producto. Podés cambiar datos y, si querés, nuevas fotos.",
        "label_images_optional": "Imágenes (opcional; en edición solo se suben si querés reemplazar todas)",
        "admin_variants_heading": "Talles y disponibilidad",
        "admin_variants_help": "Indicá unidades en local (retiro inmediato) y/o marcá “Por encargo” si se puede pedir aunque no haya stock. Dejá en 0 y sin encargo para no ofrecer ese talle.",
        "admin_variants_col_size": "Talle",
        "admin_variants_col_stock": "Uds. en local",
        "admin_variants_col_encargo": "Por encargo",
        "admin_variants_col_days": "Días (estimado)",
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
        "detail_immediate": "Retiro en el local",
        "detail_encargo": "Pedido / próximos días",
        "detail_add_requires_size": "Seleccioná un talle antes de agregar al carrito.",
        "detail_price_was": "Antes",
        "detail_price_now": "Ahora",
        "label_title": "Título",
        "label_price": "Precio",
        "label_description": "Descripción",
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
