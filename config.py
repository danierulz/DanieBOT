"""
Textos y marca del sitio web. Override marca: variable de entorno SITE_BRAND_NAME.
"""
import os
from datetime import datetime

_BRAND = os.getenv("SITE_BRAND_NAME", "Outfit Jazmines")


def get_template_context() -> dict:
    """Contexto compartido para todas las plantillas Jinja2."""
    year = datetime.now().year
    return {
        "brand_name": _BRAND,
        "page_title_catalog": f"{_BRAND} - Catálogo",
        "page_title_product": "Detalle de producto",
        "page_title_admin": "Panel Admin",
        "page_title_login": "Login Admin",
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
        "label_title": "Título",
        "label_price": "Precio",
        "label_description": "Descripción",
        "admin_btn_upload": "Subir fotos",
        "login_heading": "Login Admin",
        "label_username": "Usuario",
        "label_password": "Contraseña",
        "btn_sign_in": "Ingresar",
    }
