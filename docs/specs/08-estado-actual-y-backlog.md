# Estado actual y backlog

Última revisión alineada con el repositorio; actualizar al cerrar tareas.

## Lo que ya funciona (alto nivel)

- FastAPI sirve tienda, API de productos, login JWT básico, subida de fotos a GCS.
- PyWa inicializado en el mismo `app` con webhook `/webhook` — despliegue en GCP operativo según comentario del equipo.
- PostgreSQL + SQLAlchemy para productos e imágenes; Docker + compose para desarrollo.
- Carrito en front con panel lateral, `wa.me` al confirmar pedido.
- Cloud Build despliega imagen a Cloud Run con secretos y VPC.

## Huecos o deuda técnica conocida

| Ítem | Detalle |
|------|---------|
| **Router de pedidos no montado** | `routes/orders.py` no se registra con `app.include_router` en `main.py`; endpoint `POST /api/whatsapp/pedido` no está expuesto. |
| **Definición duplicada** | Misma ruta `crear_pedido` declarada dos veces en `routes/orders.py`; consolidar en una implementación. |
| **Dependencia DB** | El router usa `get_db`; en `init_db.py` solo existe `get_db_fastApi`. Corregir nombre o alias. |
| **Constante faltante** | Segunda definición retorna `BUSINESS_WHATSAPP_NUMBER` — verificar que exista en el módulo. |
| **Total en mensaje WhatsApp (JS)** | En `confirmarPedido`, el total usa `reduce` sobre `p.precio` sin multiplicar por `cantidad`; inconsistente con `renderCarrito`. Alinear con spec: total = Σ(precio × cantidad). |
| **Número WhatsApp en front** | Hardcodeado en `shoppingCart.js`; externalizar (config servidor o build-time env). |
| **Health check** | Ruta `/healt` con typo; opcional normalizar a `/health`. |
| **Endpoint `/debug`** | Lista archivos del contenedor — riesgo en producción; proteger o eliminar. |
| **Auth admin** | Credenciales y `SECRET_KEY` en código; migrar a secretos y hash de contraseña. |
| **Tailwind build** | `package.json` vacío en repo; completar scripts build CSS si usás Tailwind en pipeline. |
| **Scraper** | Trigger desde API deshabilitado; definir cómo y cuándo ejecutar ingesta. |

## Backlog sugerido (prioridad negocio)

1. **Corregir total del mensaje** y líneas del mensaje (cantidad × precio explícito).
2. **Integrar router de pedidos** y flujo opcional: confirmar en web → crear orden en DB → abrir WhatsApp con texto servidor.
3. **Mejorar UI** Tailwind: grid catálogo, detalle, carrito móvil.
4. **PyWa:** parsear mensajes de pedido o al menos notificación al admin cuando llegue texto con formato acordado.
5. **Seguridad:** secretos, desactivar `/debug` en prod, endurecer login.

## Cómo usar esta lista en el día a día

- Pasar ítems terminados a una sección **“Hecho”** con fecha o mover a changelog del proyecto.
- Si un ítem queda obsoleto, tacharlo y explicar por qué (ej. “unificamos solo checkout por wa.me sin Order en DB”).
