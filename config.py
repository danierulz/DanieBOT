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
_SITE_PUBLIC_URL = os.getenv("SITE_PUBLIC_URL", "https://outfitjazmines.com.ar")


def get_whatsapp_bot_number() -> str:
    return _WHATSAPP_BOT


def get_whatsapp_asesor_number() -> str:
    return _WHATSAPP_ASESOR


def get_site_public_url() -> str:
    return _SITE_PUBLIC_URL.rstrip("/")


def get_catalog_categories() -> list[dict]:
    """Categorías del catálogo (slug + name) para menú web y bot WhatsApp."""
    return list(_NAV_CATEGORIES)


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

# Categorías del menú Productos (slugs alineados con seed en init_db)
_NAV_CATEGORIES = [
    {"name": "Jeans", "slug": "jeans"},
    {"name": "Pantalones", "slug": "pantalones"},
    {"name": "Remeras", "slug": "remeras"},
    {"name": "Camisas", "slug": "camisas"},
    {"name": "Blusas", "slug": "blusas"},
    {"name": "Camperas", "slug": "camperas"},
    {"name": "Vestidos", "slug": "vestidos"},
    {"name": "Polleras", "slug": "polleras"},
    {"name": "Buzos", "slug": "buzos"},
    {"name": "Accesorios", "slug": "accesorios"},
]

_NAV_PRODUCTOS_CHILDREN = [
    {"label": "Ver todo", "href": "/?cat=todos"},
    *[
        {"label": c["name"], "href": f"/?cat={c['slug']}"}
        for c in _NAV_CATEGORIES
    ],
]

# Menú principal
_NAV_LINKS = [
    {"label": "Inicio", "href": "/"},
    {
        "label": "Productos",
        "href": "/?cat=todos",
        "dropdown": True,
        "children": _NAV_PRODUCTOS_CHILDREN,
    },
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
        "nav_categories": _NAV_CATEGORIES,
        "nav_categories_label": "Productos",
        "nav_productos_ver_todo": "Ver todo",
        "admin_tab_banners": "Banners inicio",
        "admin_banners_heading": "Banners de la página de inicio",
        "admin_banners_help": "Banners en la home (~⅓ de pantalla en móvil). 1 banner = ancho completo; 2 = mitad cada uno; 3+ = carrusel. Preferí WebP/JPEG o MP4 corto (sin audio); evitá GIF pesados.",
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
        "admin_tab_list": "Mis productos",
        "admin_tab_orders": "Pedidos",
        "admin_tab_colors": "Colores",
        "admin_orders_heading": "Pedidos de la tienda",
        "admin_orders_help": "Pedidos creados desde la web y confirmados por WhatsApp. El asesor recibe aviso por WhatsApp al registrarse y al confirmar la clienta.",
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
        "admin_provider_help": "Pegá un link de So Chic o Las Locas. El producto se carga desactivado; activalo y ajustá el precio cuando quieras publicarlo.",
        "admin_provider_url_label": "Link del producto",
        "admin_provider_url_placeholder": "https://sochic.com.ar/product/... o https://laslocas.com/ficha-...",
        "admin_provider_btn": "Importar producto",
        "admin_provider_importing": "Importando producto...",
        "admin_provider_created": "Producto importado correctamente (desactivado).",
        "admin_provider_created_active": "Producto importado y publicado como activo.",
        "admin_provider_exists": "Ese producto ya estaba cargado.",
        "admin_provider_status_label": "Publicar activo al importar",
        "admin_provider_status_help": "Si no lo marcás, el producto queda desactivado hasta activarlo en edición.",
        "admin_list_status_filter_label": "Estado",
        "admin_list_status_all": "Todos",
        "admin_list_status_active": "Solo activos",
        "admin_list_status_inactive": "Solo inactivos",
        "admin_col_status": "Estado",
        "admin_status_active": "Activo",
        "admin_status_inactive": "Inactivo",
        "admin_product_active_label": "Producto activo (visible en la tienda)",
        "admin_product_active_help": "Desmarcá para ocultar el producto del catálogo público.",
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
        "admin_colors_select_help": "Marcá los colores disponibles para esta prenda. Para crear o corregir colores, usá la pestaña Colores.",
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
        "admin_colors_tab_help": "Creá y editá los colores del catálogo. Después asignalos a cada producto desde Nuevo producto o Editar.",
        "admin_colors_col_swatch": "Muestra",
        "admin_colors_col_name": "Nombre",
        "admin_colors_col_hex": "Hex",
        "admin_colors_col_actions": "Acciones",
        "admin_colors_btn_cancel": "Cancelar",
        "admin_colors_btn_update": "Guardar cambios",
        "admin_colors_msg_updated": "Color actualizado.",
        "admin_colors_msg_deleted": "Color eliminado.",
        "admin_colors_delete_confirm": "¿Eliminar \"{name}\"?",
        "admin_colors_name_required": "Escribí el nombre del color.",
        "admin_colors_hex_required": "Elegí un tono de color válido.",
        "admin_colors_load_err": "No se pudieron cargar los colores.",
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
        "detail_immediate": "Retiro en el local",
        "detail_encargo": "Pedido / próximos días",
        "detail_add_requires_size": "Seleccioná un talle antes de agregar al carrito.",
        "detail_price_was": "Antes",
        "detail_price_now": "Ahora",
        "label_title": "Título",
        "label_price": "Precio",
        "label_description": "Descripción",
        "admin_description_limit_help": "Máximo 255 caracteres.",
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
