# API y contratos

Convención base: JSON salvo donde se indique `multipart/form-data` o HTML.

## Salud y utilidades

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/healt` | Health check (typo intencional en código actual; considerar renombrar a `/health`). |
| GET | `/debug` | Lista archivos bajo `/DANIEBOT` — **solo desarrollo**, no exponer en producción sin protección. |

## WhatsApp / Meta

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/webhook` | Verificación Meta (`hub.mode`, `hub.verify_token`, `hub.challenge`). |
| POST | `/webhook` | Eventos entrantes; el cuerpo se delega a PyWa (`wa.handle_update`). |

**Variables de entorno:** `PYWA_VERIFY_TOKEN`, `PYWA_AUTH_TOKEN`, `PYWA_PHONE_ID`, más `APP_SECRET` y `APP_ID` según configuración PyWa.

## Web (HTML)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Home tienda (`index.html`). |
| GET | `/login` | Página login (HTML plano desde archivo). |
| POST | `/login` | OAuth2 password → JWT (`access_token`, `token_type`). |
| GET | `/admin-panel` | Panel admin (Jinja). |
| GET | `/api/detalle/{product_id}` | Vista detalle producto (`tiredimages.html`). |

## API catálogo

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/productos` | Lista productos. **Público:** solo `status=true`. **Admin (JWT):** query `status_filter=activos\|inactivos\|todos`. Cada ítem incluye `activo`. |
| GET | `/api/producto/{id}` | Detalle. **Público:** 404 si inactivo. **Admin (JWT):** permite inactivos; incluye `activo`. |
| POST | `/api/productos` | Alta producto: `Form` (título, precio, descripción) + `File` imágenes opcionales; sube a GCS y crea filas `ProductImages`. |
| PUT | `/api/productos/{id}` | Actualiza producto; `Form` incluye `status` (`1`/`0`) para activar/desactivar en tienda. Requiere JWT admin. |
| POST | `/api/proveedores/importar` | Body JSON `{ "url": "...", "status": false }` (`status` opcional, default `false`). Auto-detecta proveedor. Respuesta incluye `activo`. Requiere JWT admin. |
| POST | `/api/proveedores/sochic/importar` | Alias de `/api/proveedores/importar` (compatibilidad). |
| POST | `/upload-photos` | Sube fotos y devuelve URLs (`uploaded_urls`). |

## Pedidos (código en `routes/orders.py` — ver backlog)

**Objetivo:** persistir pedido y líneas, validar stock, devolver mensaje formateado para WhatsApp.

| Método | Ruta | Body (JSON) | Respuesta esperada |
|--------|------|-------------|----------------------|
| POST | `/api/whatsapp/pedido` | `PedidoIn`: `items[]` con `{ id, titulo, precio, cantidad }`, opcional `customer_name`, `customer_phone`, `note` | `status`, `order_id`, `mensaje`, (opcional) `whatsapp_number` |

**Estado:** el router **no está incluido** en `main.py`; además el archivo define la misma ruta **dos veces** y referencia dependencias a revisar (`get_db`, `BUSINESS_WHATSAPP_NUMBER`). Tratar como **especificación objetivo** hasta integrar y limpiar.

## Autenticación

- **Admin API:** header `Authorization: Bearer <JWT>` usando `get_current_user` donde se protejan rutas (ampliar según necesidad).
- **JWT:** emitido en `POST /login`; clave y usuario admin deben endurecerse para producción.

## Errores HTTP típicos

| Código | Caso |
|--------|------|
| 400 | Carrito vacío, stock insuficiente |
| 401 | Credenciales / token inválido |
| 404 | Producto no encontrado |
| 403 | Verificación webhook fallida |
| 500 | Error servidor / DB / GCS |
