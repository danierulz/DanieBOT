from typing import List, Optional

from math import ceil

from fastapi import BackgroundTasks, Depends, FastAPI, File, Request, Response, HTTPException, Form, UploadFile, Query
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from auth.auth import create_access_token, get_current_user, ADMIN_USER
from pywa import WhatsApp
from pywa.types import Message, CallbackButton, SectionRow, SectionList, Button
import os
import json
import traceback
from dataclasses import asdict
from fastapi.templating import Jinja2Templates  
from fastapi.responses import HTMLResponse  
from fastapi.staticfiles import StaticFiles      
from sqlalchemy.orm import sessionmaker, declarative_base, Session, joinedload
from sqlalchemy import create_engine, inspect
from database.init_db import Base
from database.schemas.ProductCreate import ProductCreate, ProductOut
from gcs.GCSUploader import GCSUploader
from scraper_locas.constants import BUCKET_NAME
#from scraper_locas.scraper_core import scraper_code_main
import logging

import uvicorn

from database.models.Products import Products
from database.models.ProductImages import ProductImages
from database.models.Size import Size
from database.models.ProductVariant import ProductVariant
from database.init_db import SessionLocal
from database.init_db import get_db_session, get_db_fastApi
from config import get_template_context


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
uploader = GCSUploader(bucket_name="bucket_laslocas_prod")


app = FastAPI()
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


# --- Configuración de PyWa (¡IMPORTANTE! Usa variables de entorno) ---
# Estas variables se inyectarán en Cloud Run, NO las hardcodees aquí en producción.
# Para pruebas locales, puedes definirlas directamente o usar un .env
PYWA_VERIFY_TOKEN = os.getenv("PYWA_VERIFY_TOKEN", "TU_TOKEN_DE_VERIFICACION_SECRETO")
PYWA_AUTH_TOKEN = os.getenv("PYWA_AUTH_TOKEN", "TU_TOKEN_DE_AUTENTICACION_DE_META")
# El ID del número de teléfono de WhatsApp Business
PYWA_PHONE_ID = os.getenv("PYWA_PHONE_ID", "TU_ID_DE_NUMERO_DE_TELEFONO")
APP_SECRET = os.getenv("APP_SECRET", "f173398d2e1be14ff8fbbb8b29fe16a0")
APP_ID = os.getenv("APP_ID", "26438378279080977")

if PYWA_PHONE_ID and PYWA_AUTH_TOKEN and PYWA_VERIFY_TOKEN:
    try:
        wa = WhatsApp(
            phone_id=PYWA_PHONE_ID,
            token=PYWA_AUTH_TOKEN,
            app_secret=APP_SECRET,
            app_id=APP_ID,
            server=app,
            webhook_endpoint="/webhook/",
            verify_token=PYWA_VERIFY_TOKEN
#            callback_url="/webhook" # Esta es la ruta donde WhatsApp enviará los mensajes
        )
        print("PyWa configurado correctamente")
    except Exception as e:
        print(f"Error al configurar PyWa: {e}")
else:
    print("Error: Asegúrate de definir las variables de entorno PYWA_VERIFY_TOKEN, PYWA_AUTH_TOKEN y PYWA_PHONE_ID")

# --- Rutas de FastAPI ---

@app.get("/healt")
def health_check():
    return {"status": "ok", "message": "Bot de WhatsApp funcionando en Cloud Run"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Ruta para la verificación del webhook de WhatsApp.
    Meta enviará una solicitud GET a esta URL para verificarla.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == PYWA_VERIFY_TOKEN:
        print("Webhook verificado correctamente por Meta")
        return Response(content=challenge, media_type="text/plain")
    
    print("Fallo la verificación del webhook")
    raise HTTPException(status_code=403, detail="Error de verificación")

@app.post("/webhook")
async def handle_webhook_events(request: Request):
    """
    Ruta donde WhatsApp enviará los eventos de mensajes.
    PyWa se encargará de procesarlos.
    """
    body = await request.json()
    logging.info(f"PAYLOAD RECIBIDO: {body}")
    # PyWa se encarga de procesar el JSON y disparar los handlers
    wa.handle_update(await request.json())
    return {"status": "success"}

# --- Handlers de PyWa (ejemplos) ---

@wa.on_message()
def handle_message(client: WhatsApp, message: Message):
    #logging.info(f"Escuché: {message.text}. Intentando responder...")
    print("Escuche: ", message.text)
    print("Mensaje completo: ", message)
    # Usá el método más simple posible
    try:
        print("Intentando responder a: ", message.from_user.wa_id)
#        logging.info(f"Intentando responder a: {message.from_user.wa_id}")
        # Intentá la respuesta más simple posible para probar
        message.reply_text(text="¡Te escucho!")
    except Exception:
        # Esto imprimirá el error real (Traceback) en tus logs
        logging.error(f"ERROR DETALLADO EN HANDLE_MESSAGE: \n{traceback.format_exc()}")
    try:
        logging.info(f"PAYLOAD CRUDO DE META: {message}")
        """Cuando recibes un mensaje de texto"""
        try:
            logging.info(f"DETALLES DEL MENSAJE: {json.dumps(asdict(message), indent=2, default=str)}")
        except:
            logging.info(f"DICCIONARIO DEL MENSAJE: {message.__dict__}")


        print(f"Mensaje recibido de {message.from_user.name}: {message.text}")
        client.send_message(
            to=message.from_user.wa_id,
            text=f"¡Hola {message.from_user.name}! Recibí tu mensaje: '{message.text}'. ¿Cómo puedo ayudarte con tu pedido de ropa?",
            # Puedes añadir botones aquí, por ejemplo:
            buttons=[Button(title="Ver Catálogo", callback_data="CATALOGO"), Button(title="Hablar con un asesor", callback_data="ASESOR")]
        )
    except Exception as e:
        logging.error(f"Error al manejar el mensaje de {message.from_user.name}: {e}")

@wa.on_callback_button()
def handle_button_callback(client: WhatsApp, cb: CallbackButton):
    """Cuando el usuario presiona un botón"""
    print(f"Botón presionado por {cb.from_user.name}: {cb.data}")
    if cb.data == "CATALOGO":
        client.send_message(
            to=cb.from_user.wa_id,
            text="¡Claro! Aquí tienes nuestro catálogo de ropa:",
            # Aquí podrías enviar un link a un PDF o una lista de productos
        )
    elif cb.data == "ASESOR":
        client.send_message(
            to=cb.from_user.wa_id,
            text="Un asesor se pondrá en contacto contigo a la brevedad."
        )

# Agrega más handlers según necesites (on_list_response, on_reaction, etc.)
@wa.on_message()
def handle_all_messages(client, msg):
    try:
        print(f"¡Llegó algo! De: {msg.from_user.wa_id} - Texto: {msg.text}",flush=True)
        msg.reply_text(f"Hola {msg.from_user.name}, recibí tu mensaje: {msg.text}")
        print("Respuesta enviada correctamente")
#        logging.info("Respuesta enviada correctamente")
    except Exception as e:
        print(f"Error al manejar mensaje de {msg.from_user.wa_id}: {e}", flush=True)
#        logging.error(f"Error al manejar mensaje de {msg.from_user.wa_id}: {e}", exc_info=True)



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
def obtener_producto(id: int, db: Session = Depends(get_db_fastApi)):
    print(f"Obteniendo producto con ID: {id}")
    producto = (
        db.query(Products)
        .options(
            joinedload(Products.variants).joinedload(ProductVariant.size),
            joinedload(Products.images),
        )
        .filter(Products.product_id == id)
        .first()
    )
    if not producto:
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

    return {
        "id": producto.product_id,
        "titulo": producto.item_title,
        "precio": producto.price,
        "descripcion": producto.description,
        "stock": getattr(producto, "stock", None),
        "imagenes": imagenes,
        "variantes": _variants_public_list(vars_sorted),
    }


@app.get("/api/sizes")
def listar_talles(db: Session = Depends(get_db_fastApi)):
    rows = db.query(Size).order_by(Size.sort_order.asc(), Size.code.asc()).all()
    return [{"size_id": s.size_id, "code": s.code, "label": s.label} for s in rows]


# Tu API de productos (la que consume el HTML)
@app.get("/api/productos")
def listar_productos(
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=48),
    q: Optional[str] = Query(None, max_length=200),
    size_code: Optional[str] = Query(None, max_length=32),
    disponibilidad: Optional[str] = Query(None, pattern="^(inmediata|encargo)$"),
    db: Session = Depends(get_db_fastApi),
):
    consulta = db.query(Products)
    if q and q.strip():
        consulta = consulta.filter(Products.item_title.ilike(f"%{q.strip()}%"))

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
        .options(joinedload(Products.variants).joinedload(ProductVariant.size))
        .all()
    )
    resultado = []
    for p in productos:
        imagen_principal = None
        if p.images:
            main = next((img for img in p.images if img.is_main), None)
            if main:
                imagen_principal = main.url

        resultado.append(
            {
                "id": p.product_id,
                "titulo": p.item_title,
                "precio": p.price,
                "descripcion": p.description,
                "imagen": imagen_principal,
                "variantes_resumen": _list_variant_summary(list(p.variants or [])),
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


@app.post("/api/productos", response_model=ProductOut)
def crear_producto(
    item_title: str = Form(...),
    price: int = Form(...),
    description: str = Form(...),
    variants_json: str = Form("[]"),
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    try:
        nuevo = Products(
            item_title=item_title,
            price=price,
            cod_product="cod",
            name="test",
            sku=123,
            description=description,
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)

        _guardar_imagenes_producto(db, nuevo.product_id, images)
        _sync_product_variants(db, nuevo.product_id, _parse_variants_json(variants_json))
        db.commit()
        db.refresh(nuevo)
        return nuevo

    except Exception as e:
        db.rollback()
        logging.error(f"Error al crear producto: {e}", exc_info=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al crear producto")


@app.put("/api/productos/{product_id}", response_model=ProductOut)
def actualizar_producto(
    product_id: int,
    item_title: str = Form(...),
    price: int = Form(...),
    description: str = Form(...),
    variants_json: str = Form("[]"),
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db_fastApi),
    _: dict = Depends(get_current_user),
):
    producto = db.query(Products).filter(Products.product_id == product_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    try:
        producto.item_title = item_title
        producto.price = price
        producto.description = description
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
        return producto
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
async def upload_photos(files: List[UploadFile] = File(...)):
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