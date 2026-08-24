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
| **Email marketing** | Consent en DB; integración SendGrid/Resend pendiente (ver `09-marketing-email-compliance.md`). |
| **Aviso asesor WA** | Requiere que el asesor haya escrito al número del negocio en las últimas 24h (reglas Meta); si falla, ver logs Cloud Run. |
| **Alembic en prod** | Si la base existía antes de Alembic: `python -m alembic stamp head` una sola vez (ver [10-alembic-migraciones.md](./10-alembic-migraciones.md)). |
| **CI migrate** | Migraciones en el **arranque del contenedor** (`docker-entrypoint.sh`), no en Cloud Build (VPC de Cloud Run). |
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

- El diario de lo que se fue haciendo está en [`docs/historial-trabajo.md`](../historial-trabajo.md).
- Pasar ítems terminados a una sección **“Hecho”** con fecha o mover a changelog del proyecto.
- Si un ítem queda obsoleto, tacharlo y explicar por qué (ej. “unificamos solo checkout por wa.me sin Order en DB”).
