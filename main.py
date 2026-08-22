from contextlib import asynccontextmanager
from typing import List, Optional

from math import ceil

from fastapi import BackgroundTasks, Depends, FastAPI, File, Request, Response, HTTPException, Form, UploadFile, Query
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from auth.auth import (
    ADMIN_USER,
    admin_auth_status,
    authenticate_admin,
    create_access_token,
    get_current_user,
    get_optional_user,
)
import os
import json
import traceback
from dataclasses import asdict
from fastapi.templating import Jinja2Templates  
from fastapi.responses import HTMLResponse, FileResponse  
from fastapi.staticfiles import StaticFiles      
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker, declarative_base, Session, joinedload
from sqlalchemy import create_engine, inspect
from database.init_db import Base
from database.schemas.ProductCreate import ProductCreate, ProductOut
from gcs.storage_factory import create_uploader
from provider_importers.registry import detect_provider, fetch_product
from provider_importers.types import ImportedProduct, ProviderImportError
from services.product_variants import sync_product_variants
from services.provider_import import (
    ProviderImportPayload,
    persist_imported_product,
    product_is_active,
    provider_description,
    image_filename_from_url,
    page_ficha_from_url,
    truncate as _truncate,
    match_import_color_ids,
)
from services.nissie_bulk_import import (
    BulkImportConflictError,
    create_bulk_run,
    run_nissie_bulk_import,
)
from services.holic_bulk_import import (
    BulkImportConflictError as HolicBulkImportConflictError,
    create_bulk_run as create_holic_bulk_run,
    run_holic_bulk_import,
)
from services.provider_import_runs import cancel_run, get_active_run, serialize_run
from services import laslocas_bulk_import as laslocas_bulk
from database.models.ProviderImportRun import ProviderImportRun
from scraper_locas.constants import BUCKET_NAME
#from scraper_locas.scraper_core import scraper_code_main
import logging
from urllib.parse import urlparse

import uvicorn

from database.models.Products import Products
from database.models.ProductImages import ProductImages
from database.models.Size import Size
from database.models.ProductVariant import ProductVariant
from database.models.ProductColor import ProductColor
from database.models.Color import Color
from database.models.Category import Category
from database.models.HomeBanner import HomeBanner
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from database.init_db import SessionLocal
from database.init_db import get_db_session, get_db_fastApi
from config import get_template_context, PRODUCT_DESCRIPTION_MAX_LEN, PRODUCT_ITEM_TITLE_MAX_LEN, APP_DEBUG, build_nav_links
from provider_importers.bulk.laslocas_catalog import load_laslocas_categories
from services.colors import (
    color_to_public,
    create_color,
    get_or_create_color,
    update_color,
    delete_color,
    list_colors_public,
    normalize_color_code,
    parse_colors_json,
    sync_product_colors,
)
from services.sizes import (
    create_size,
    delete_size,
    get_or_create_size_code,
    list_all_sizes_admin,
    list_sizes_public,
    size_to_public,
    update_size,
)
from services.categories import (
    category_to_public,
    create_category,
    delete_category,
    list_categories_admin,
    list_categories_for_nav,
    list_categories_public,
    update_category,
)
from routes.orders import router as orders_router
from whatsapp.bot import get_wa_client, init_whatsapp
from services.email_notify import is_email_notify_configured


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


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    """Migraciones solo si no corrieron en docker_entrypoint (uvicorn local)."""
    if not os.getenv("DB_MIGRATIONS_DONE"):
        from database.run_migrations import apply_migrations_and_seed

        apply_migrations_and_seed()
    yield


app = FastAPI(lifespan=_app_lifespan)
app.include_router(orders_router)
init_whatsapp(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(
        os.path.join(BASE_DIR, "static", "favicon.svg"),
        media_type="image/svg+xml",
    )


# Montar la carpeta static
app.mount("/static", StaticFiles(directory="static"), name="static")

print("BASE_DIR:", BASE_DIR)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
#templates = Jinja2Templates(directory="/app/templates")


def page_context(request: Request, **extra: dict) -> dict:
    """request + textos de marca para plantillas Jinja2."""
    ctx = {"request": request, **get_template_context()}
    db = SessionLocal()
    try:
        nav_cats = list_categories_for_nav(db)
        ctx["nav_categories"] = nav_cats
        ctx["nav_links"] = build_nav_links(nav_cats)
    finally:
        db.close()
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
    sync_product_variants(db, product_id, items)


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
        out.append(
            {
                "variant_id": v.variant_id,
                "size_code": v.size.code,
                "size_label": v.size.label,
                "color_id": v.color_id,
                "color_label": v.color.label if v.color else None,
                "color_hex": v.color.hex if v.color else None,
                "qty_stock_local": v.qty_stock_local,
                "encargo_habilitado": v.encargo_habilitado,
                "dias_encargo_estimados": v.dias_encargo_estimados,
                "disponibilidad": disp,
                "disponible": len(disp) > 0,
            }
        )
    return out


# --- Rutas de FastAPI ---

@app.get("/healt")
def health_check():
    wa = get_wa_client()
    app_secret = os.getenv("APP_SECRET")
    return {
        "status": "ok",
        "message": "Bot de WhatsApp funcionando en Cloud Run",
        "whatsapp": {
            "configured": wa is not None,
            "webhook_paths": ["/webhook", "/webhook/"],
            "signature_validation": bool(app_secret),
            "app_id_set": bool(os.getenv("APP_ID")),
        },
        "admin_email": {
            "configured": is_email_notify_configured(),
            "enabled": os.getenv("ADMIN_NOTIFY_EMAIL_ENABLED", "false").lower()
            in ("1", "true", "yes", "on"),
        },
        "admin_auth": admin_auth_status(),
    }


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


@app.get("/dev/brand-logo", response_class=HTMLResponse)
async def dev_brand_logo_preview(request: Request):
    if not APP_DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    ctx = {"request": request, **get_template_context()}
    return templates.TemplateResponse("dev-brand-logo.html", ctx)


class LogoCalibrationPayload(BaseModel):
    letters: dict
    jasmine: dict


@app.post("/dev/brand-logo/calibration")
async def save_logo_calibration(payload: LogoCalibrationPayload):
    if not APP_DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    calibration_path = os.path.join("static", "brand", "logo-calibration.json")
    data = {"letters": payload.letters, "jasmine": payload.jasmine}
    with open(calibration_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    return {"ok": True, "path": "/static/brand/logo-calibration.json"}


@app.get("/contacto", response_class=HTMLResponse)
async def page_contacto(request: Request):
    return templates.TemplateResponse("contacto.html", page_context(request))


@app.get("/puntos-de-venta", response_class=HTMLResponse)
async def page_stores(request: Request):
    return templates.TemplateResponse("puntos-venta.html", page_context(request))



@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if authenticate_admin(form_data.username, form_data.password):
        token = create_access_token({"sub": form_data.username, "rol": "admin"})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Credenciales inválidas")


@app.post("/api/auth/refresh")
def refresh_token(user: dict = Depends(get_current_user)):
    token = create_access_token({"sub": user["sub"], "rol": user.get("rol", "admin")})
    return {"access_token": token, "token_type": "bearer"}

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
    return templates.TemplateResponse(
        "admin-panel.html",
        page_context(request, laslocas_bulk_categories=load_laslocas_categories()),
    )


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
            joinedload(Products.variants).joinedload(ProductVariant.color),
            joinedload(Products.product_colors).joinedload(ProductColor.color),
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
        "colores": [
            color_to_public(pc.color)
            for pc in (producto.product_colors or [])
            if pc.activo and pc.color
        ],
        "categoria": _category_public(producto.category),
    }


@app.get("/api/sizes")
def listar_talles(
    category_slug: Optional[str] = Query(None),
    db: Session = Depends(get_db_fastApi),
):
    return list_sizes_public(db, category_slug)


@app.get("/api/colors")
def listar_colores(db: Session = Depends(get_db_fastApi)):
    return list_colors_public(db)


class ColorCreateIn(BaseModel):
    label: str
    hex: str


class ColorUpdateIn(BaseModel):
    label: Optional[str] = None
    hex: Optional[str] = None


@app.post("/api/admin/colors")
def admin_crear_color(
    body: ColorCreateIn,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    row = create_color(db, label=body.label, hex_value=body.hex)
    db.commit()
    db.refresh(row)
    return {"ok": True, "color": color_to_public(row), "created": True}


@app.put("/api/admin/colors/{color_id}")
def admin_actualizar_color(
    color_id: int,
    body: ColorUpdateIn,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    if body.label is None and body.hex is None:
        raise HTTPException(status_code=400, detail="Indicá el nombre o el tono a actualizar.")
    row = update_color(db, color_id, label=body.label, hex_value=body.hex)
    db.commit()
    db.refresh(row)
    return {"ok": True, "color": color_to_public(row)}


@app.delete("/api/admin/colors/{color_id}")
def admin_eliminar_color(
    color_id: int,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    delete_color(db, color_id)
    db.commit()
    return {"ok": True, "deleted": True}


class SizeCreateIn(BaseModel):
    code: str
    label: str
    size_group: str
    sort_order: Optional[int] = None


class SizeUpdateIn(BaseModel):
    label: Optional[str] = None
    size_group: Optional[str] = None
    sort_order: Optional[int] = None


class CategorySizeGroupIn(BaseModel):
    size_group: str


class CategoryCreateIn(BaseModel):
    name: str
    slug: Optional[str] = None
    size_group: str = "letter"
    sort_order: Optional[int] = None
    activo: bool = True


class CategoryUpdateIn(BaseModel):
    name: Optional[str] = None
    size_group: Optional[str] = None
    sort_order: Optional[int] = None
    activo: Optional[bool] = None


@app.get("/api/admin/sizes")
def admin_listar_talles(
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    return list_all_sizes_admin(db)


@app.post("/api/admin/sizes")
def admin_crear_talle(
    body: SizeCreateIn,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    row = create_size(
        db,
        code=body.code,
        label=body.label,
        size_group=body.size_group,
        sort_order=body.sort_order,
    )
    db.commit()
    db.refresh(row)
    return {"ok": True, "size": size_to_public(row), "created": True}


@app.put("/api/admin/sizes/{size_id}")
def admin_actualizar_talle(
    size_id: int,
    body: SizeUpdateIn,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    if body.label is None and body.size_group is None and body.sort_order is None:
        raise HTTPException(status_code=400, detail="Indicá al menos un campo a actualizar.")
    row = update_size(
        db,
        size_id,
        label=body.label,
        size_group=body.size_group,
        sort_order=body.sort_order,
    )
    db.commit()
    db.refresh(row)
    return {"ok": True, "size": size_to_public(row)}


@app.delete("/api/admin/sizes/{size_id}")
def admin_eliminar_talle(
    size_id: int,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    delete_size(db, size_id)
    db.commit()
    return {"ok": True, "deleted": True}


@app.get("/api/admin/categories")
def admin_listar_categorias(
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    return list_categories_admin(db)


@app.post("/api/admin/categories")
def admin_crear_categoria(
    body: CategoryCreateIn,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    row = create_category(
        db,
        name=body.name,
        slug=body.slug,
        size_group=body.size_group,
        sort_order=body.sort_order,
        activo=body.activo,
    )
    db.commit()
    db.refresh(row)
    return {"ok": True, "category": category_to_public(row, product_count=0), "created": True}


@app.put("/api/admin/categories/{category_id}")
def admin_actualizar_categoria(
    category_id: int,
    body: CategoryUpdateIn,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    if body.name is None and body.size_group is None and body.sort_order is None and body.activo is None:
        raise HTTPException(status_code=400, detail="Indicá al menos un campo a actualizar.")
    row = update_category(
        db,
        category_id,
        name=body.name,
        size_group=body.size_group,
        sort_order=body.sort_order,
        activo=body.activo,
    )
    db.commit()
    db.refresh(row)
    usage = db.query(Products).filter(Products.category_id == category_id).count()
    return {"ok": True, "category": category_to_public(row, product_count=usage)}


@app.delete("/api/admin/categories/{category_id}")
def admin_eliminar_categoria(
    category_id: int,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    delete_category(db, category_id)
    db.commit()
    return {"ok": True, "deleted": True}


@app.get("/api/admin/categories/size-groups")
def admin_listar_grupos_categoria(
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    """Deprecated: usar GET /api/admin/categories."""
    rows = list_categories_admin(db)
    return [
        {
            "category_id": r["category_id"],
            "slug": r["slug"],
            "name": r["name"],
            "size_group": r["size_group"],
        }
        for r in rows
        if r.get("activo", True)
    ]


@app.put("/api/admin/categories/{category_id}/size-group")
def admin_actualizar_grupo_categoria(
    category_id: int,
    body: CategorySizeGroupIn,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    """Deprecated: usar PUT /api/admin/categories/{id}."""
    row = update_category(db, category_id, size_group=body.size_group)
    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "category": category_to_public(row),
    }


def _match_import_color_ids(db: Session, color_names: List[str]) -> List[int]:
    return match_import_color_ids(db, color_names)

@app.get("/api/categories")
def listar_categorias(db: Session = Depends(get_db_fastApi)):
    return list_categories_public(db)


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
    provider: Optional[str] = Query(
        None, pattern="^(nissie|sochic|laslocas|holic)$"
    ),
    db: Session = Depends(get_db_fastApi),
    user: Optional[dict] = Depends(get_optional_user),
):
    consulta = db.query(Products)
    consulta = _apply_products_status_filter(consulta, status_filter, bool(user))
    if provider and user:
        consulta = consulta.filter(Products.provider == provider)
    elif provider and not user:
        raise HTTPException(
            status_code=403,
            detail="Se requiere autenticación admin para filtrar por proveedor.",
        )
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
                "provider": p.provider,
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


class LasLocasBulkImportRequest(BaseModel):
    category_id: Optional[str] = None
    all_categories: bool = False
    max_pages: int = 0



def _validate_product_form_fields(*, item_title: str, description: str) -> None:
    title = item_title or ""
    desc = description or ""
    if len(title) > PRODUCT_ITEM_TITLE_MAX_LEN:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El título supera el máximo de {PRODUCT_ITEM_TITLE_MAX_LEN} caracteres "
                f"(ingresaste {len(title)})."
            ),
        )
    if len(desc) > PRODUCT_DESCRIPTION_MAX_LEN:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La descripción supera el máximo de {PRODUCT_DESCRIPTION_MAX_LEN} caracteres "
                f"(ingresaste {len(desc)})."
            ),
        )


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
    return get_or_create_size_code(db, size_code)


def _provider_description(product: ImportedProduct) -> str:
    return provider_description(product)


def _image_filename_from_url(image_url: str, idx: int, provider: str = "sochic") -> str:
    return image_filename_from_url(image_url, idx, provider)


def _product_is_active(product: Products) -> bool:
    return product_is_active(product)


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
    import_payload = ProviderImportPayload(
        url=payload.url,
        category_id=payload.category_id,
        size_code=payload.size_code,
        encargo_habilitado=payload.encargo_habilitado,
        dias_encargo_estimados=payload.dias_encargo_estimados,
        status=payload.status,
    )
    return persist_imported_product(
        db,
        imported,
        import_payload,
        uploader,
        sync_variants_fn=sync_product_variants,
        match_color_ids_fn=match_import_color_ids,
    )


def _page_ficha_from_url(url: str) -> str:
    return page_ficha_from_url(url)


def _log_provider_import_failure(provider: str, url: str, error: ProviderImportError) -> None:
    logging.warning(
        json.dumps(
            {
                "event": "provider_import_failed",
                "provider": provider,
                "url": url,
                "error_code": error.code,
                "detail": str(error),
            },
            ensure_ascii=False,
        )
    )


def _import_product_from_url(
    payload: ProviderUrlImportRequest,
    db: Session,
) -> dict:
    provider = detect_provider(payload.url)
    try:
        imported = fetch_product(payload.url)
    except ProviderImportError as e:
        _log_provider_import_failure(provider, payload.url, e)
        return {
            "ok": False,
            "error": str(e),
            "error_code": e.code,
            "provider": provider,
        }

    try:
        return _persist_imported_product(db, imported, payload)
    except Exception as e:
        db.rollback()
        logging.error(
            json.dumps(
                {
                    "event": "provider_import_persist_failed",
                    "provider": provider,
                    "url": payload.url,
                    "detail": str(e),
                },
                ensure_ascii=False,
            ),
            exc_info=True,
        )
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


def _nissie_bulk_import_task(run_id: int) -> None:
    db = SessionLocal()
    try:
        bulk_uploader = create_uploader()
        run_nissie_bulk_import(
            db,
            run_id,
            bulk_uploader,
            sync_variants_fn=sync_product_variants,
            match_color_ids_fn=match_import_color_ids,
        )
    finally:
        db.close()


def _holic_bulk_import_task(run_id: int) -> None:
    db = SessionLocal()
    try:
        bulk_uploader = create_uploader()
        run_holic_bulk_import(
            db,
            run_id,
            bulk_uploader,
            sync_variants_fn=sync_product_variants,
            match_color_ids_fn=match_import_color_ids,
        )
    finally:
        db.close()


def _laslocas_bulk_import_task(
    run_id: int,
    *,
    category_id: str | None,
    all_categories: bool,
    max_pages: int,
) -> None:
    db = SessionLocal()
    try:
        bulk_uploader = create_uploader()
        laslocas_bulk.run_laslocas_bulk_import(
            db,
            run_id,
            bulk_uploader,
            sync_variants_fn=sync_product_variants,
            match_color_ids_fn=match_import_color_ids,
            category_id=category_id,
            all_categories=all_categories,
            max_pages=max_pages,
        )
    finally:
        db.close()


@app.post("/api/proveedores/nissie/importar-masivo")
def importar_catalogo_nissie_masivo(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_fastApi),
    user: dict = Depends(get_current_user),
):
    try:
        run = create_bulk_run(db, triggered_by=str(user.get("sub") or "admin"))
    except BulkImportConflictError as exc:
        active = get_active_run(db, "nissie")
        return {
            "ok": False,
            "error": str(exc),
            "run_id": active.run_id if active else None,
            "status": active.status if active else None,
        }
    background_tasks.add_task(_nissie_bulk_import_task, run.run_id)
    return {
        "ok": True,
        "run_id": run.run_id,
        "status": run.status,
        "provider": run.provider,
    }


@app.post("/api/proveedores/holic/importar-masivo")
def importar_catalogo_holic_masivo(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_fastApi),
    user: dict = Depends(get_current_user),
):
    try:
        run = create_holic_bulk_run(db, triggered_by=str(user.get("sub") or "admin"))
    except HolicBulkImportConflictError as exc:
        active = get_active_run(db, "holic")
        return {
            "ok": False,
            "error": str(exc),
            "run_id": active.run_id if active else None,
            "status": active.status if active else None,
        }
    background_tasks.add_task(_holic_bulk_import_task, run.run_id)
    return {
        "ok": True,
        "run_id": run.run_id,
        "status": run.status,
        "provider": run.provider,
    }


@app.post("/api/proveedores/laslocas/importar-masivo")
def importar_catalogo_laslocas_masivo(
    payload: LasLocasBulkImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_fastApi),
    user: dict = Depends(get_current_user),
):
    try:
        run = laslocas_bulk.create_bulk_run(db, triggered_by=str(user.get("sub") or "admin"))
    except laslocas_bulk.BulkImportConflictError as exc:
        active = get_active_run(db, "laslocas")
        return {
            "ok": False,
            "error": str(exc),
            "run_id": active.run_id if active else None,
            "status": active.status if active else None,
        }
    background_tasks.add_task(
        _laslocas_bulk_import_task,
        run.run_id,
        category_id=payload.category_id,
        all_categories=payload.all_categories,
        max_pages=payload.max_pages,
    )
    return {
        "ok": True,
        "run_id": run.run_id,
        "status": run.status,
        "provider": run.provider,
    }


@app.get("/api/proveedores/importaciones/{run_id}")
def obtener_importacion_proveedor(
    run_id: int,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    run = db.query(ProviderImportRun).filter(ProviderImportRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Importación no encontrada")
    return serialize_run(db, run)


@app.get("/api/proveedores/importaciones/ultima")
def obtener_ultima_importacion_proveedor(
    provider: str = Query("nissie", pattern="^(nissie|sochic|laslocas|holic)$"),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    run = (
        db.query(ProviderImportRun)
        .filter(ProviderImportRun.provider == provider)
        .order_by(ProviderImportRun.run_id.desc())
        .first()
    )
    if not run:
        return {"ok": True, "run": None}
    return {"ok": True, "run": serialize_run(db, run)}


@app.post("/api/proveedores/importaciones/{run_id}/cancelar")
def cancelar_importacion_proveedor(
    run_id: int,
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    run = db.query(ProviderImportRun).filter(ProviderImportRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Importación no encontrada")
    if run.status != "running":
        raise HTTPException(status_code=400, detail="La importación no está en curso")
    cancel_run(db, run)
    return {"ok": True, "run": serialize_run(db, run)}


@app.post("/api/productos")
def crear_producto(
    item_title: str = Form(...),
    price: int = Form(...),
    description: str = Form(...),
    variants_json: str = Form("[]"),
    colors_json: str = Form("[]"),
    category_id: Optional[str] = Form(None),
    is_sale: Optional[str] = Form(None),
    discount_percent: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    _validate_product_form_fields(item_title=item_title, description=description)
    try:
        is_sale_b = str(is_sale).lower() in ("1", "true", "on", "yes")
        nuevo = Products(
            item_title=item_title,
            price=price,
            name=_truncate(item_title, 80),
            description=description,
            category_id=_resolve_category_id(db, category_id),
            is_sale=is_sale_b,
            discount_percent=_normalize_discount(is_sale_b, discount_percent),
        )
        db.add(nuevo)
        db.flush()
        nuevo.cod_product = f"P{nuevo.product_id}"

        _guardar_imagenes_producto(db, nuevo.product_id, images)
        sync_product_colors(db, nuevo.product_id, parse_colors_json(colors_json))
        db.flush()
        _sync_product_variants(db, nuevo.product_id, _parse_variants_json(variants_json))
        db.commit()
        db.refresh(nuevo)
        return {"ok": True, "id": nuevo.product_id}

    except IntegrityError as e:
        db.rollback()
        logging.error(f"Error al crear producto: {e}", exc_info=True)
        orig = str(getattr(e, "orig", e))
        if "ix_products_cod_product" in orig or "cod_product" in orig:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un producto con ese código",
            )
        raise HTTPException(status_code=500, detail="Error al crear producto")
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
    colors_json: str = Form("[]"),
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
    _validate_product_form_fields(item_title=item_title, description=description)
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
        sync_product_colors(db, product_id, parse_colors_json(colors_json))
        db.flush()
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
        db.query(ProductColor).filter(ProductColor.product_id == product_id).delete(
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