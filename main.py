from typing import List, Optional

from math import ceil

from fastapi import BackgroundTasks, Depends, FastAPI, File, Request, Response, HTTPException, Form, UploadFile, Query
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from auth.auth import create_access_token, get_current_user, get_optional_user, ADMIN_USER
import os
import json
import traceback
from dataclasses import asdict
from fastapi.templating import Jinja2Templates  
from fastapi.responses import HTMLResponse  
from fastapi.staticfiles import StaticFiles      
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker, declarative_base, Session, joinedload
from sqlalchemy import create_engine, inspect
from database.init_db import Base
from database.schemas.ProductCreate import ProductCreate, ProductOut
from gcs.storage_factory import create_uploader
from provider_importers.registry import detect_provider, fetch_product
from provider_importers.types import ImportedProduct, ProviderImportError
from scraper_locas.constants import BUCKET_NAME
#from scraper_locas.scraper_core import scraper_code_main
import logging
from urllib.parse import urlparse

import uvicorn

from database.models.Products import Products
from database.models.ProductImages import ProductImages
from database.models.Size import Size
from database.models.ProductVariant import ProductVariant
from database.models.Category import Category
from database.models.HomeBanner import HomeBanner
from sqlalchemy import or_
from database.init_db import SessionLocal
from database.init_db import get_db_session, get_db_fastApi
from config import get_template_context
from routes.orders import router as orders_router
from whatsapp.bot import init_whatsapp


DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT") # Default PostgreSQL port
DB_HOST_DOCKER = os.getenv("DB_HOST_DOCKER")  # For Docker connectivity


# 1. Configuración de la URL de conexión (vía el Proxy local)
# Formato: postgresql+pg8000://USUARIO:PASSWORD@localhost:5433/NOMBRE_DB
#DB_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 2. Crear el motor de conexión
# pool_pre_ping=True ayuda a que no se caiga la conexión si el proxy se reinicia
#print("creatE_engine main.py")
#print("DB_URL: ", DB_URL)
#inspector = inspect(engine)
#print(inspector.get_table_names())
# 3. Crear la fábrica de sesiones
#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Base para tus modelos (si vas a definirlos acá)
#Base = declarative_base()


# Configura el logging para ver todo en Cloud Run
logging.basicConfig(level=logging.INFO)
uploader = create_uploader()


app = FastAPI()
app.include_router(orders_router)
init_whatsapp(app)
# Montar la carpeta static
app.mount("/static", StaticFiles(directory="static"), name="static")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print("BASE_DIR:", BASE_DIR)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
#templates = Jinja2Templates(directory="/app/templates")


def page_context(request: Request, **extra: dict) -> dict:
    """request + textos de marca para plantillas Jinja2."""
    ctx = {"request": request, **get_template_context()}
    ctx.update(extra)
    return ctx


def _parse_variants_json(raw: Optional[str]) -> List[dict]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]
    except json.JSONDecodeError:
        return []


def _sync_product_variants(db: Session, product_id: int, items: List[dict]) -> None:
    db.query(ProductVariant).filter(ProductVariant.product_id == product_id).delete(
        synchronize_session=False
    )
    for it in items:
        code = (it.get("size_code") or "").strip().upper()
        if not code:
            continue
        size = db.query(Size).filter(Size.code == code).first()
        if not size:
            continue
        qty = int(it.get("qty_stock_local", 0) or 0)
        enc = bool(it.get("encargo_habilitado", False))
        dias_raw = it.get("dias_encargo_estimados")
        dias_i = int(dias_raw) if dias_raw not in (None, "") else None
        if qty < 0:
            qty = 0
        if qty == 0 and not enc:
            continue
        db.add(
            ProductVariant(
                product_id=product_id,
                size_id=size.size_id,
                qty_stock_local=qty,
                encargo_habilitado=enc,
                dias_encargo_estimados=dias_i,
                activo=True,
            )
        )


def _list_variant_summary(variants: List[ProductVariant]) -> dict:
    inmediato = []
    encargo = []
    for v in variants:
        if not v.activo or not v.size:
            continue
        lbl = v.size.label
        if v.qty_stock_local > 0:
            inmediato.append(lbl)
        if v.encargo_habilitado:
            encargo.append(lbl)
    return {
        "talles_retiro_inmediato": inmediato,
        "talles_encargo": encargo,
        "badge_inmediato": len(inmediato) > 0,
        "badge_encargo": len(encargo) > 0,
    }


def _compute_pricing(price: Optional[int], is_sale: bool, discount_percent: Optional[int]) -> dict:
    from services.pricing import compute_pricing

    return compute_pricing(price, is_sale, discount_percent)


def _category_public(cat: Optional[Category]) -> Optional[dict]:
    if not cat:
        return None
    return {"category_id": cat.category_id, "slug": cat.slug, "name": cat.name}


def _variants_public_list(variants: List[ProductVariant]) -> List[dict]:
    out = []
    for v in variants:
        if not v.activo or not v.size:
            continue
        disp = []
        if v.qty_stock_local > 0:
            disp.append("inmediato")
        if v.encargo_habilitado:
            disp.append("encargo")
        if not disp:
            continue
        out.append(
            {
                "variant_id": v.variant_id,
                "size_code": v.size.code,
                "size_label": v.size.label,
                "qty_stock_local": v.qty_stock_local,
                "encargo_habilitado": v.encargo_habilitado,
                "dias_encargo_estimados": v.dias_encargo_estimados,
                "disponibilidad": disp,
            }
        )
    out.sort(key=lambda x: (x["size_label"], x["size_code"]))
    return out


# --- Rutas de FastAPI ---

@app.get("/healt")
def health_check():
    return {"status": "ok", "message": "Bot de WhatsApp funcionando en Cloud Run"}


@app.get("/debug")
async def debug_dir():
    # Lista todo el contenido de /app
    files = []
    for root, dirs, filenames in os.walk("/DANIEBOT"):
        for name in filenames:
            files.append(os.path.join(root, name))
    return {"archivos": files}

# Ruta para ver la página web
@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
#    print("Archivos en /app/templates:", os.listdir("/templates"))
    print("Contexto:", {"request": request})
    # Esto busca el archivo 'index.html' dentro de la carpeta 'templates'
    return templates.TemplateResponse("index.html", page_context(request))


@app.get("/sale", response_class=HTMLResponse)
async def page_sale(request: Request):
    return templates.TemplateResponse("sale.html", page_context(request))


@app.get("/contacto", response_class=HTMLResponse)
async def page_contacto(request: Request):
    return templates.TemplateResponse("contacto.html", page_context(request))


@app.get("/puntos-de-venta", response_class=HTMLResponse)
async def page_stores(request: Request):
    return templates.TemplateResponse("puntos-venta.html", page_context(request))



@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == ADMIN_USER["username"] and form_data.password == ADMIN_USER["password"]:
        token = create_access_token({"sub": ADMIN_USER["username"], "rol": ADMIN_USER["rol"]})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Credenciales inválidas")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", page_context(request))
    '''
    Opcion de endpoint sin jinja2 (si no querés usar plantillas para el login)
@app.get("/admin-panel", response_class=HTMLResponse)
def admin_panel():
    with open("templates/admin-panel.html") as f:
        return f.read()
    
    '''
    
@app.get("/admin-panel", response_class=HTMLResponse)
def admin_panel(request: Request):
    return templates.TemplateResponse("admin-panel.html", page_context(request))


@app.get("/admin-panel/edit/{product_id}", response_class=HTMLResponse)
def admin_edit_product(request: Request, product_id: int):
    return templates.TemplateResponse(
        "admin-edit-product.html",
        page_context(request, edit_product_id=product_id),
    )


# Utilizado en tireadimages.html para mostrar el detalle del producto. Recibe el ID por URL y lo pasa a la plantilla
@app.get("/api/detalle/{product_id}", response_class=HTMLResponse)
async def read_item(request: Request, product_id: int):
    print("ID recibido en detalle: ", product_id)
    print("Request recibido en detalle: ", request)
    # Esto busca el archivo 'index.html' dentro de la carpeta 'templates'
    return templates.TemplateResponse(
        "tiredimages.html",
        page_context(request, product_id=product_id),
    )

#Utilizado en tiredimages.html para mostrar el detalle del producto
@app.get("/api/producto/{id}")
def obtener_producto(
    id: int,
    db: Session = Depends(get_db_fastApi),
    user: Optional[dict] = Depends(get_optional_user),
):
    print(f"Obteniendo producto con ID: {id}")
    producto = (
        db.query(Products)
        .options(
            joinedload(Products.variants).joinedload(ProductVariant.size),
            joinedload(Products.images),
            joinedload(Products.category),
        )
        .filter(Products.product_id == id)
        .first()
    )
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not _product_is_active(producto) and not user:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    imagenes = []
    page_ficha = getattr(producto, "page_ficha", None)
    if producto.images:
        for img in producto.images:
            if img.url:
                url = img.url
            elif page_ficha:
                url = f"https://storage.googleapis.com/{BUCKET_NAME}/images/{page_ficha}/{img.filename}"
            else:
                url = ""
            if url:
                imagenes.append({"url": url, "is_main": img.is_main})

    vars_sorted = sorted(
        producto.variants or [],
        key=lambda v: (v.size.sort_order if v.size else 0, v.size.code if v.size else ""),
    )

    pricing = _compute_pricing(producto.price, bool(producto.is_sale), producto.discount_percent)

    return {
        "id": producto.product_id,
        "titulo": producto.item_title,
        "precio": pricing["precio_final"],
        "precio_original": pricing["precio_original"],
        "precio_final": pricing["precio_final"],
        "descuento_porcentaje": pricing["descuento_porcentaje"],
        "is_sale": pricing["is_sale"],
        "activo": _product_is_active(producto),
        "descripcion": producto.description,
        "stock": getattr(producto, "stock", None),
        "imagenes": imagenes,
        "variantes": _variants_public_list(vars_sorted),
        "categoria": _category_public(producto.category),
    }


@app.get("/api/sizes")
def listar_talles(db: Session = Depends(get_db_fastApi)):
    rows = db.query(Size).order_by(Size.sort_order.asc(), Size.code.asc()).all()
    return [{"size_id": s.size_id, "code": s.code, "label": s.label} for s in rows]


@app.get("/api/categories")
def listar_categorias(db: Session = Depends(get_db_fastApi)):
    rows = (
        db.query(Category)
        .filter(Category.activo.is_(True))
        .order_by(Category.sort_order.asc(), Category.name.asc())
        .all()
    )
    return [
        {"category_id": c.category_id, "slug": c.slug, "name": c.name}
        for c in rows
    ]


_BANNER_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
_BANNER_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
_BANNER_ALLOWED_EXTENSIONS = _BANNER_VIDEO_EXTENSIONS | _BANNER_IMAGE_EXTENSIONS


def _banner_media_type_from_name(name: str) -> str:
    lower = (name or "").split("?")[0].lower()
    for ext in _BANNER_VIDEO_EXTENSIONS:
        if lower.endswith(ext):
            return "video"
    return "image"


def _validate_banner_upload(filename: str) -> None:
    lower = (filename or "").lower()
    if not any(lower.endswith(ext) for ext in _BANNER_ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Formato no permitido. Usá imagen (JPG, PNG, WebP, GIF) o video (MP4, WebM).",
        )


def _resolve_banner_media(url: str, filename: Optional[str] = None) -> str:
    if filename:
        return _banner_media_type_from_name(filename)
    return _banner_media_type_from_name(url)


def _banner_public(b: HomeBanner) -> dict:
    media = getattr(b, "media_type", None) or _banner_media_type_from_name(b.image_url)
    return {
        "banner_id": b.banner_id,
        "image_url": b.image_url,
        "media_type": media,
        "title": b.title,
        "subtitle": b.subtitle,
        "link_href": b.link_href,
        "sort_order": b.sort_order,
    }


def _banner_admin(b: HomeBanner) -> dict:
    d = _banner_public(b)
    d["activo"] = b.activo
    return d


@app.get("/api/home-banners")
def listar_home_banners_publicos(db: Session = Depends(get_db_fastApi)):
    rows = (
        db.query(HomeBanner)
        .filter(HomeBanner.activo.is_(True))
        .order_by(HomeBanner.sort_order.asc(), HomeBanner.banner_id.asc())
        .all()
    )
    return [_banner_public(b) for b in rows]


@app.get("/api/admin/banners")
def listar_banners_admin(
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    rows = (
        db.query(HomeBanner)
        .order_by(HomeBanner.sort_order.asc(), HomeBanner.banner_id.asc())
        .all()
    )
    return [_banner_admin(b) for b in rows]


@app.post("/api/admin/banners")
def crear_banner(
    title: Optional[str] = Form(None),
    subtitle: Optional[str] = Form(None),
    link_href: str = Form("/"),
    sort_order: int = Form(0),
    activo: Optional[str] = Form("1"),
    image_url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    url = (image_url or "").strip()
    upload_name: Optional[str] = None
    if image and image.filename:
        _validate_banner_upload(image.filename)
        upload_name = image.filename
        url = uploader.upload_file(image.file, image.filename)
    if not url:
        raise HTTPException(status_code=400, detail="Se requiere URL de imagen/video o archivo")
    media_type = _resolve_banner_media(url, upload_name)
    activo_b = str(activo).lower() in ("1", "true", "on", "yes")
    banner = HomeBanner(
        image_url=url,
        media_type=media_type,
        title=(title or "").strip() or None,
        subtitle=(subtitle or "").strip() or None,
        link_href=(link_href or "/").strip() or "/",
        sort_order=sort_order,
        activo=activo_b,
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return {"ok": True, "banner": _banner_admin(banner)}


@app.put("/api/admin/banners/{banner_id}")
def actualizar_banner(
    banner_id: int,
    title: Optional[str] = Form(None),
    subtitle: Optional[str] = Form(None),
    link_href: str = Form("/"),
    sort_order: int = Form(0),
    activo: Optional[str] = Form("1"),
    image_url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    banner = db.query(HomeBanner).filter(HomeBanner.banner_id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    if image and image.filename:
        _validate_banner_upload(image.filename)
        banner.image_url = uploader.upload_file(image.file, image.filename)
        banner.media_type = _resolve_banner_media(banner.image_url, image.filename)
    elif image_url and image_url.strip():
        banner.image_url = image_url.strip()
        banner.media_type = _resolve_banner_media(banner.image_url)
    banner.title = (title or "").strip() or None
    banner.subtitle = (subtitle or "").strip() or None
    banner.link_href = (link_href or "/").strip() or "/"
    banner.sort_order = sort_order
    banner.activo = str(activo).lower() in ("1", "true", "on", "yes")
    db.commit()
    db.refresh(banner)
    return {"ok": True, "banner": _banner_admin(banner)}


@app.delete("/api/admin/banners/{banner_id}")
def eliminar_banner(
    banner_id: int,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    banner = db.query(HomeBanner).filter(HomeBanner.banner_id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    db.delete(banner)
    db.commit()
    return {"ok": True, "id": banner_id}


# Tu API de productos (la que consume el HTML)
@app.get("/api/productos")
def listar_productos(
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=48),
    q: Optional[str] = Query(None, max_length=200),
    size_code: Optional[str] = Query(None, max_length=32),
    disponibilidad: Optional[str] = Query(None, pattern="^(inmediata|encargo)$"),
    cat: Optional[str] = Query(None, max_length=64),
    sale: Optional[int] = Query(None, ge=0, le=1),
    status_filter: Optional[str] = Query(
        None, pattern="^(activos|inactivos|todos)$"
    ),
    db: Session = Depends(get_db_fastApi),
    user: Optional[dict] = Depends(get_optional_user),
):
    consulta = db.query(Products)
    consulta = _apply_products_status_filter(consulta, status_filter, bool(user))
    if q and q.strip():
        like = f"%{q.strip()}%"
        consulta = consulta.outerjoin(Category, Products.category_id == Category.category_id).filter(
            or_(
                Products.item_title.ilike(like),
                Products.description.ilike(like),
                Category.name.ilike(like),
            )
        )

    if cat and cat.strip() and cat.strip().lower() != "todos":
        consulta = consulta.join(Category, Products.category_id == Category.category_id).filter(
            Category.slug == cat.strip().lower()
        )

    if sale == 1:
        consulta = consulta.filter(Products.is_sale.is_(True))

    if size_code or disponibilidad:
        pv_q = db.query(ProductVariant.product_id).join(Size)
        if size_code and size_code.strip():
            pv_q = pv_q.filter(Size.code == size_code.strip().upper())
        if disponibilidad == "inmediata":
            pv_q = pv_q.filter(
                ProductVariant.qty_stock_local > 0,
                ProductVariant.activo.is_(True),
            )
        elif disponibilidad == "encargo":
            pv_q = pv_q.filter(
                ProductVariant.encargo_habilitado.is_(True),
                ProductVariant.activo.is_(True),
            )
        ids_match = [r[0] for r in pv_q.distinct().all()]
        if not ids_match:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0,
            }
        consulta = consulta.filter(Products.product_id.in_(ids_match))

    total = consulta.count()
    productos = (
        consulta.order_by(Products.product_id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .options(
            joinedload(Products.variants).joinedload(ProductVariant.size),
            joinedload(Products.category),
        )
        .all()
    )
    resultado = []
    for p in productos:
        imagen_principal = None
        if p.images:
            main = next((img for img in p.images if img.is_main), None)
            if main:
                imagen_principal = main.url

        pricing = _compute_pricing(p.price, bool(p.is_sale), p.discount_percent)
        resultado.append(
            {
                "id": p.product_id,
                "titulo": p.item_title,
                "precio": pricing["precio_final"],
                "precio_original": pricing["precio_original"],
                "precio_final": pricing["precio_final"],
                "descuento_porcentaje": pricing["descuento_porcentaje"],
                "is_sale": pricing["is_sale"],
                "descripcion": p.description,
                "imagen": imagen_principal,
                "categoria": _category_public(p.category),
                "variantes_resumen": _list_variant_summary(list(p.variants or [])),
                "activo": _product_is_active(p),
            }
        )
    total_pages = ceil(total / per_page) if total else 0
    return {
        "items": resultado,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


def _guardar_imagenes_producto(
    db: Session,
    product_id: int,
    images: Optional[List[UploadFile]],
) -> None:
    is_main_set = False
    if not images:
        return
    for img in images:
        if not img.filename:
            continue
        url = uploader.upload_file(img.file, img.filename)
        if not is_main_set:
            is_main_set = True
            db.add(
                ProductImages(
                    product_id=product_id,
                    filename=img.filename,
                    url=url,
                    is_main=True,
                )
            )
        else:
            db.add(
                ProductImages(
                    product_id=product_id,
                    filename=img.filename,
                    url=url,
                    is_main=False,
                )
            )


def _resolve_category_id(db: Session, category_id_raw: Optional[str]) -> Optional[int]:
    if not category_id_raw:
        return None
    raw = str(category_id_raw).strip()
    if not raw:
        return None
    try:
        cid = int(raw)
    except ValueError:
        return None
    if cid <= 0:
        return None
    exists = db.query(Category.category_id).filter(Category.category_id == cid).first()
    return cid if exists else None


def _normalize_discount(is_sale: bool, discount_percent_raw: Optional[str]) -> Optional[int]:
    if not is_sale:
        return None
    if discount_percent_raw is None or str(discount_percent_raw).strip() == "":
        return None
    try:
        pct = int(str(discount_percent_raw).strip())
    except ValueError:
        return None
    if pct < 1:
        return None
    if pct > 95:
        pct = 95
    return pct


class ProviderUrlImportRequest(BaseModel):
    url: str
    category_id: Optional[int] = None
    size_code: str = "UNICO"
    encargo_habilitado: bool = True
    dias_encargo_estimados: Optional[int] = None
    status: bool = False


def _truncate(value: Optional[str], max_len: int) -> str:
    clean = " ".join(str(value or "").split())
    return clean[:max_len].rstrip()


def _resolve_category_slug(db: Session, slug: Optional[str]) -> Optional[int]:
    if not slug:
        return None
    row = (
        db.query(Category.category_id)
        .filter(Category.slug == slug.strip().lower(), Category.activo.is_(True))
        .first()
    )
    return row[0] if row else None


def _ensure_size_code(db: Session, size_code: str) -> str:
    code = (size_code or "UNICO").strip().upper()[:32] or "UNICO"
    size = db.query(Size).filter(Size.code == code).first()
    if not size:
        db.add(
            Size(
                code=code,
                label="Unico" if code == "UNICO" else code,
                sort_order=70 if code == "UNICO" else 999,
            )
        )
        db.flush()
    return code


def _provider_description(product: ImportedProduct) -> str:
    parts = []
    if product.description:
        parts.append(product.description)
    if product.colors:
        parts.append("Colores proveedor: " + ", ".join(product.colors))
    default = {
        "sochic": "Producto importado desde So Chic.",
        "laslocas": "Producto importado desde Las Locas.",
    }
    return _truncate(" | ".join(parts) or default.get(product.provider, "Producto importado."), 255)


def _image_filename_from_url(image_url: str, idx: int, provider: str = "sochic") -> str:
    filename = os.path.basename(urlparse(image_url).path)
    return _truncate(filename or f"{provider}-{idx + 1}.jpg", 255)


def _product_is_active(product: Products) -> bool:
    return bool(product.status)


def _parse_form_bool(value: Optional[str]) -> bool:
    return str(value or "").lower() in ("1", "true", "on", "yes")


def _apply_products_status_filter(consulta, status_filter: Optional[str], is_admin: bool):
    if status_filter:
        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Se requiere autenticación admin para filtrar por estado.",
            )
        if status_filter == "activos":
            return consulta.filter(Products.status.is_(True))
        if status_filter == "inactivos":
            return consulta.filter(or_(Products.status.is_(False), Products.status.is_(None)))
        return consulta
    return consulta.filter(Products.status.is_(True))


def _persist_imported_product(
    db: Session,
    imported: ImportedProduct,
    payload: ProviderUrlImportRequest,
) -> dict:
    existing = db.query(Products).filter(Products.cod_product == imported.cod_product).first()
    if existing:
        return {
            "ok": True,
            "created": False,
            "id": existing.product_id,
            "provider": imported.provider,
            "cod_product": existing.cod_product,
            "activo": _product_is_active(existing),
        }

    is_sale = imported.is_sale or bool(imported.discount_percent and imported.original_price)
    base_price = imported.original_price if is_sale else imported.price
    category_id = (
        _resolve_category_id(db, str(payload.category_id))
        if payload.category_id
        else _resolve_category_slug(db, imported.category_slug)
    )
    nuevo = Products(
        item_title=_truncate(imported.title, 255),
        price=base_price,
        cod_product=imported.cod_product,
        name=_truncate(imported.title, 80),
        sku=imported.sku,
        description=_provider_description(imported),
        category_id=category_id,
        status=bool(payload.status),
        is_sale=is_sale,
        discount_percent=imported.discount_percent if is_sale else None,
    )
    db.add(nuevo)
    db.flush()

    image_count = 0
    page_ficha = imported.page_ficha or _page_ficha_from_url(imported.source_url)

    for idx, image_url in enumerate(imported.image_urls):
        db.add(
            ProductImages(
                product_id=nuevo.product_id,
                filename=_image_filename_from_url(image_url, idx, imported.provider),
                url=image_url,
                is_main=(image_count == 0),
            )
        )
        image_count += 1

    for filename, data in imported.image_assets:
        blob_path = f"images/{page_ficha}/{filename}"
        public_url = uploader.upload_bytes(blob_path, data)
        db.add(
            ProductImages(
                product_id=nuevo.product_id,
                filename=_truncate(filename, 255),
                url=public_url,
                is_main=(image_count == 0),
            )
        )
        image_count += 1

    size_code = _ensure_size_code(db, payload.size_code)
    _sync_product_variants(
        db,
        nuevo.product_id,
        [
            {
                "size_code": size_code,
                "qty_stock_local": 0,
                "encargo_habilitado": payload.encargo_habilitado,
                "dias_encargo_estimados": payload.dias_encargo_estimados,
            }
        ],
    )
    db.commit()
    db.refresh(nuevo)
    return {
        "ok": True,
        "created": True,
        "id": nuevo.product_id,
        "provider": imported.provider,
        "cod_product": nuevo.cod_product,
        "imagenes": image_count,
        "colores": imported.colors,
        "activo": _product_is_active(nuevo),
    }


def _page_ficha_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.replace("/", "") or "ficha"


def _import_product_from_url(
    payload: ProviderUrlImportRequest,
    db: Session,
) -> dict:
    try:
        imported = fetch_product(payload.url)
    except ProviderImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        return _persist_imported_product(db, imported, payload)
    except Exception as e:
        db.rollback()
        logging.error(f"Error al importar producto ({detect_provider(payload.url)}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al importar producto desde proveedor")


@app.post("/api/proveedores/importar")
def importar_producto_proveedor(
    payload: ProviderUrlImportRequest,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    return _import_product_from_url(payload, db)


@app.post("/api/proveedores/sochic/importar")
def importar_producto_sochic(
    payload: ProviderUrlImportRequest,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    return _import_product_from_url(payload, db)


@app.post("/api/productos")
def crear_producto(
    item_title: str = Form(...),
    price: int = Form(...),
    description: str = Form(...),
    variants_json: str = Form("[]"),
    category_id: Optional[str] = Form(None),
    is_sale: Optional[str] = Form(None),
    discount_percent: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    try:
        is_sale_b = str(is_sale).lower() in ("1", "true", "on", "yes")
        nuevo = Products(
            item_title=item_title,
            price=price,
            cod_product="cod",
            name="test",
            sku=123,
            description=description,
            category_id=_resolve_category_id(db, category_id),
            is_sale=is_sale_b,
            discount_percent=_normalize_discount(is_sale_b, discount_percent),
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)

        _guardar_imagenes_producto(db, nuevo.product_id, images)
        _sync_product_variants(db, nuevo.product_id, _parse_variants_json(variants_json))
        db.commit()
        db.refresh(nuevo)
        return {"ok": True, "id": nuevo.product_id}

    except Exception as e:
        db.rollback()
        logging.error(f"Error al crear producto: {e}", exc_info=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al crear producto")


@app.put("/api/productos/{product_id}")
def actualizar_producto(
    product_id: int,
    item_title: str = Form(...),
    price: int = Form(...),
    description: str = Form(...),
    variants_json: str = Form("[]"),
    category_id: Optional[str] = Form(None),
    is_sale: Optional[str] = Form(None),
    discount_percent: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    producto = db.query(Products).filter(Products.product_id == product_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    try:
        is_sale_b = str(is_sale).lower() in ("1", "true", "on", "yes")
        producto.item_title = item_title
        producto.price = price
        producto.description = description
        producto.category_id = _resolve_category_id(db, category_id)
        producto.is_sale = is_sale_b
        producto.discount_percent = _normalize_discount(is_sale_b, discount_percent)
        if status is not None:
            producto.status = _parse_form_bool(status)

        has_new_images = bool(
            images and any(getattr(img, "filename", None) for img in images)
        )
        if has_new_images:
            db.query(ProductImages).filter(ProductImages.product_id == product_id).delete(
                synchronize_session=False
            )
            _guardar_imagenes_producto(db, product_id, images)
        _sync_product_variants(db, product_id, _parse_variants_json(variants_json))
        db.commit()
        db.refresh(producto)
        return {"ok": True, "id": producto.product_id}
    except Exception as e:
        db.rollback()
        logging.error(f"Error al actualizar producto: {e}", exc_info=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al actualizar producto")


@app.delete("/api/productos/{product_id}")
def eliminar_producto(
    product_id: int,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    producto = db.query(Products).filter(Products.product_id == product_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    try:
        db.query(ProductImages).filter(ProductImages.product_id == product_id).delete(
            synchronize_session=False
        )
        db.query(ProductVariant).filter(ProductVariant.product_id == product_id).delete(
            synchronize_session=False
        )
        db.delete(producto)
        db.commit()
        return {"ok": True, "id": product_id}
    except Exception as e:
        db.rollback()
        logging.error(f"Error al eliminar producto: {e}", exc_info=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al eliminar producto")

@app.post("/upload-photos")
async def upload_photos(
    files: List[UploadFile] = File(...),
    _: dict = Depends(get_current_user),
):
    urls = uploader.upload_multiple(files)

    # Guardar en PostgreSQL
    #conn = psycopg2.connect("dbname=... user=... password=... host=...")
    #cur = conn.cursor()
    #for url in urls:
    #    cur.execute("INSERT INTO fotos (url) VALUES (%s)", (url,))
    #conn.commit()
    #cur.close()
    #conn.close()

    return {"uploaded_urls": urls}



#  EL SCRAPER (Lo disparás cuando quieras)
#@app.get("/ejecutar-scraper")
#async def trigger_scraper(background_tasks: BackgroundTasks):
#    # Esto le dice a Python: "Corré el scraper de fondo y no trabes la web"
#    background_tasks.add_task(scraper_code_main)
#    return {"status": "Scraper iniciado en segundo plano"}

# 4. Esto permite correrlo dándole al "Play" en VS Code
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)