# Historial de trabajo — Outfit Jazmines / DanieBOT

Cuaderno cronológico de lo que se implementó, corrigió y por qué.  
Specs estructurados: [`specs/README.md`](specs/README.md).  
Notas de scraping: [`scraping-migracion-notas.md`](scraping-migracion-notas.md).

Cuando se retome el chat: leer las entradas de abajo (la más reciente primero) antes de tocar checkout, pedidos, WhatsApp, activación de prendas o import masivo.

---

## Cómo agregar una entrada

```markdown
## YYYY-MM-DD — Título corto
- **Problema / pedido:**
- **Qué se hizo:**
- **Archivos clave:**
- **Cómo verificar:**
- **Pendiente / no desplegado:**
```

No poner teléfonos, tokens ni secretos.

---

## 2026-08-23 — Pedidos web, reintentos y logs (Log Explorer)

- **Problema / pedido:** En producción la gente arma el carrito y confirma, pero muchas no mandan el WhatsApp al bot. El pedido ya existía en la web y el asesor recibía un aviso **sin saber quién era**. Cada toque de confirmar creaba **otro** pedido y **otro** aviso. También llegaba un aviso de “Remera Test” / producto que no está en la tienda. Pedían más control en Log Explorer para trackear el embudo.

- **Causa:**
  - `POST /api/whatsapp/pedido` crea el pedido en estado `enviado_whatsapp` y avisa al asesor **antes** de que la clienta escriba.
  - Nombre y WhatsApp solo aparecen cuando el bot ve el código (`link_order_to_whatsapp`).
  - El front no recordaba el pedido: cada tap = nuevo `POST`.
  - “Remera Test” es el título de los **tests automáticos**. Con WhatsApp configurado en `.env`, correr tests en la PC **mandaba el aviso de verdad** al asesor.

- **Qué se hizo:**
  - Mismo carrito (mismas prendas/cantidades, ventana 45 min, estado `enviado_whatsapp`) **reutiliza el código** y **no vuelve a avisar** al asesor. Evento `order.retry_same_cart` / `web_retry`.
  - El carrito guarda el pedido pendiente en `sessionStorage` (`oj_pending_wa_order`). El botón pasa a “Reabrir WhatsApp (mismo pedido)”. Si cambia el carrito, se limpia.
  - Aviso 1 (web): *pendiente de WhatsApp, todavía no sabemos quién es*. Aviso 2 (cuando escriben al bot): nombre + número.
  - En **Pedidos**: cliente “Pendiente de WhatsApp”, conteo de reintentos, talle/color en el detalle.
  - Logs JSON para Cloud Logging (`services/app_log.py`). En Cloud Run (`K_SERVICE`) se imprime JSON crudo → `jsonPayload.event`.
  - Tests de pedidos ya **no** llaman al WhatsApp real.

- **Archivos clave:**
  - `services/order_service.py`, `services/advisor_notify.py`, `services/app_log.py`
  - `routes/orders.py`, `whatsapp/handlers.py`
  - `static/js/shoppingCart.js`, `templates/partials/header.html`
  - `templates/admin-panel.html`, `templates/admin-help.html`, `config.py`
  - Tests: `tests/test_orders_endpoint.py`, `tests/test_email_notify.py`, `tests/test_colors_and_orders.py`, `tests/test_orders_price_validation.py`

- **Cómo verificar:**
  1. Confirmar carrito → se abre `wa.me` y aparece un pedido *Enviado WA* sin nombre.
  2. Confirmar de nuevo el mismo carrito → mismo `order_code`, un solo aviso al asesor, botón “Reabrir WhatsApp”.
  3. Enviar el mensaje al bot con el código → pasa a *Recibido* y llega el segundo aviso con la persona.
  4. En Log Explorer (después del deploy), filtros:

  | Qué pasó | Filtro |
  |---|---|
  | Confirmaron el carrito | `jsonPayload.event="order.created_web"` |
  | Reintento mismo carrito | `jsonPayload.event="order.retry_same_cart"` |
  | Checkout rechazado (producto inexistente, stock, precio) | `jsonPayload.event="order.create_rejected"` |
  | Llegó un WhatsApp al bot | `jsonPayload.event="wa.inbound"` |
  | Se vinculó el código al WhatsApp | `jsonPayload.event="order.wa_linked"` |
  | Código que no existe en DB | `jsonPayload.event="order.wa_code_unknown"` |
  | Aviso al asesor | `jsonPayload.event="advisor.notify"` (`kind`: `new_web` o `received`) |

  Pedido puntual: `jsonPayload.order_code="OJ-YYYYMMDD-XXXX"`.

  Lectura: `created_web` sin `wa_linked` = no mandaron el mensaje. Varios `retry_same_cart` = reintentos, no clientas distintas.

- **Pendiente / no desplegado:** hay que **desplegar a Cloud Run** para que rija en la tienda. En **Mis productos** buscar “Remera Test” y desactivar/borrar si quedó en prod.

---

## 2026-08-23 — Import masivo Las Locas roto

- **Problema / pedido:** “No funciona el import masivo desde ningún sitio.” En vivo: Nissie / HOLIC / So Chic **por URL** parseaban bien. So Chic **no tiene** masivo. Las Locas login OK, pero el listing ya no trae fichas (infinite scroll). Las fichas cargan con `?page=N&ajax=1`. Cambiaron paths de categoría; URLs viejas de ficha pueden 404.

- **Qué se hizo:**
  - Actualizar `provider_importers/bulk/laslocas_categories.json` (ej. `denim` → `/productos/jean`, chupin, invierno, verano-2026).
  - Discovery con `listing_url_for_category(..., ajax=True)` y loop de páginas ajax hasta vacío.
  - Check en vivo: 48 fichas en Chupin página 1.

- **Archivos clave:** `provider_importers/bulk/laslocas_catalog.py`, `laslocas_categories.json`, `tests/test_laslocas_bulk_catalog.py`

- **Pendiente:** el masivo usa `BackgroundTasks` de FastAPI. En Cloud Run la instancia puede morir **después** de devolver el HTTP 200: el job queda a medias. No se migró a un runner persistente.

---

## 2026-08-23 — Uso de colores en el catálogo admin

- **Problema / pedido:** ver qué colores no se usan y en qué prendas está cada uno, para poder borrar los huérfanos.

- **Qué se hizo:** `GET /api/admin/colors` via `list_colors_admin()` (conteo, títulos, `activo`). Columna **Prendas** en Catálogo → Colores: “Sin uso” o links a `/admin-panel/edit/{id}`. Delete 409 nombra las prendas.

- **Archivos clave:** `services/colors.py`, `static/js/adminColorCatalog.js`, `templates/partials/admin_catalog_colors_section.html`, `tests/test_colors_and_orders.py`

---

## 2026-08-23 — Activo solo si se puede comprar

- **Problema / pedido:** prenda sin categoría y solo un color mostraba “no hay talles” y CTAs muertos. Querían **Activo** solo si se puede comprar. Duda: ¿rompe los imports Las Locas / So Chic / Nissie / HOLIC?

- **Qué se hizo:**
  - `services/product_activation.py`: para pasar a Activo hace falta categoría, precio > 0 y al menos una variante vendible (stock > 0 o encargo).
  - Se aplica **solo** en `PUT /api/productos/{id}` (edición). No en create ni en persist de import.
  - Checklist en `templates/admin-edit-product.html`.
  - **Imports no se bloquean:** el masivo sigue creando con `status=False`. Import por URL “Publicar activo” sigue pudiendo saltear este check. El import crea UNICO + encargo, qty 0.

- **Archivos clave:** `services/product_activation.py`, `main.py`, `tests/test_product_activation.py`, `tests/test_product_status.py`

---

## 2026-08-23 — Bug talles en ficha (móvil)

- **Problema / pedido:** al guardar talle + color, en móvil se veía gris y S/M/L tachados. La lista completa de talles solo aparecía al tocar el color.

- **Causa:** `renderSizeChips()` corría **antes** de autoseleccionar el único color. Usaba `availableSizes()` (S/M/L) hasta el tap, y después `productSizes()` (matriz real).

- **Qué se hizo:** `applyDefaultColorSelection()` primero; init `applyDefaultColorSelection → renderColorChips → renderSizeChips`; siempre mostrar `productSizes()`. Si no se puede comprar, se ocultan los CTAs (`detail_cannot_buy`).

- **Archivos clave:** `templates/tiredimages.html`

---

## 2026-08-23 — Manual de la administradora

- **Problema / pedido:** explicar cómo funcionan prendas, stock, talles, colores y pedidos para quien carga la tienda.

- **Qué se hizo:** `GET /admin-panel/ayuda` → `templates/admin-help.html`. Link **Ayuda** en el panel y en editar producto. Textos en `config.py` (`page_title_admin_help`, etc.). Más tarde se actualizó la sección Pedidos (reintentos / pendiente WA).

- **Archivos clave:** `templates/admin-help.html`, `config.py`, `tests/test_admin_panel.py`

---

## Lectura rápida del embudo checkout (después del 2026-08-23)

```
Clienta confirma carrito
        ↓
POST /api/whatsapp/pedido
        ↓
¿Mismo carrito reciente? ──sí──► reusa código, log order.retry_same_cart, NO avisa asesor
        │ no
        ↓
Crea Order (enviado_whatsapp) + order.created_web + aviso asesor (kind=new_web, sin nombre)
        ↓
Se abre wa.me con el texto (la clienta puede no enviar)
        ↓
Si escribe al bot con el código → order.wa_linked + aviso asesor (kind=received, con persona)
```

Estados útiles en **Pedidos**: *Enviado WA* = pendiente de mensaje; *Recibido* = ya escribió.
