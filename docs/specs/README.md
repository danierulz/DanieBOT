# Especificaciones — DanieBOT / Outfit Jazmines

Documentación viva del producto y del sistema. **Versión inicial** generada a partir del código y los objetivos acordados; conviene revisarla al cerrar cada milestone.

## Índice

| Documento | Contenido |
|-----------|-----------|
| [01-producto-y-alcance.md](./01-producto-y-alcance.md) | Visión, objetivos, alcance, fuera de alcance |
| [02-flujos-de-usuario.md](./02-flujos-de-usuario.md) | Recorridos: vitrina, carrito, checkout por WhatsApp |
| [03-arquitectura-y-stack.md](./03-arquitectura-y-stack.md) | Componentes, tecnologías, diagrama lógico |
| [04-api-y-contratos.md](./04-api-y-contratos.md) | Rutas HTTP relevantes, payloads, integraciones |
| [05-datos-y-scraper.md](./05-datos-y-scraper.md) | Modelo de datos, scraping “Las Locas”, GCS |
| [06-frontend-y-checkout-whatsapp.md](./06-frontend-y-checkout-whatsapp.md) | Tailwind, carrito, mensaje `wa.me`, formato del pedido |
| [07-despliegue-y-operaciones.md](./07-despliegue-y-operaciones.md) | GCP, Cloud Run, Cloud Build, secretos, local |
| [08-estado-actual-y-backlog.md](./08-estado-actual-y-backlog.md) | Qué está hecho, huecos conocidos, mejoras |
| [10-alembic-migraciones.md](./10-alembic-migraciones.md) | Migraciones de esquema con Alembic (`upgrade`, `stamp` en prod) |
| [11-desarrollo-local.md](./11-desarrollo-local.md) | Docker Compose, Postgres local, `.env.dev`, ngrok |
| [12-bot-whatsapp-conversacion.md](./12-bot-whatsapp-conversacion.md) | Intents, copy del bot, tests sin Meta |
| [13-colores-catalogo-y-checkout.md](./13-colores-catalogo-y-checkout.md) | Catálogo de colores, admin, tienda, pedido y WhatsApp |

## Cómo mantener estos specs

1. Tratar cada archivo como **fuente de verdad** hasta que el código lo contradiga; entonces actualizar el doc o el código y anotar la decisión.
2. Para nuevas features: añadir una línea en **alcance** o **backlog**, luego detallar en **flujos** / **API** si afecta contratos.
3. Los números de teléfono, URLs y secretos **no** deben vivir en estos archivos en producción; usar placeholders (`TU_NUMERO`, variables de entorno).
