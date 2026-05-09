"""
Textos y marca del sitio web. Override marca: variable de entorno SITE_BRAND_NAME.
"""
import os
from datetime import datetime

_BRAND = os.getenv("SITE_BRAND_NAME", "Outfit Jazmines")
_PROMO_BANNER = os.getenv(
    "SITE_PROMO_BANNER",
    "Compra mínima $100.000 · Envío a todo el país",
)


def get_template_context() -> dict:
    """Contexto compartido para todas las plantillas Jinja2."""
    year = datetime.now().year
    return {
        "brand_name": _BRAND,
        "page_title_catalog": f"{_BRAND} - Catálogo",
        "page_title_product": "Detalle de producto",
        "page_title_admin": "Panel Admin",
        "page_title_login": "Login Admin",
        "promo_banner_text": _PROMO_BANNER,
        "hero_headline": "Colección destacada",
        "hero_subtitle": "Envíos y stock actualizados en tiempo real",
        "footer_copyright": f"© {year} {_BRAND}",
        "btn_add_to_cart": "Agregar",
        "placeholder_no_image": "Sin imagen",
        "cart_title": "Tu carrito",
        "cart_total_label": "Total",
        "cart_btn_whatsapp": "Confirmar y enviar por WhatsApp",
        "nav_login": "Login",
        "nav_logout": "Logout",
        "nav_admin": "Admin Panel",
        "btn_add_cart_detail": "Agregar al carrito",
        "btn_buy_now": "Comprar ahora",
        "label_stock_prefix": "Stock disponible:",
        "label_no_description": "Sin descripción",
        "admin_panel_heading": "Panel de Administración",
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
        "label_title": "Título",
        "label_price": "Precio",
        "label_description": "Descripción",
        "admin_btn_upload": "Subir fotos",
        "login_heading": "Login Admin",
        "label_username": "Usuario",
        "label_password": "Contraseña",
        "btn_sign_in": "Ingresar",
    }
