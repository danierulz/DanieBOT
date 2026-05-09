# Datos y scraper

## Motor y conexión

- **URL:** `postgresql+pg8000://USER:PASSWORD@HOST:PORT/DB` definida en `database/init_db.py` con variables de entorno.
- **Pool:** `pool_pre_ping=True` para reconexión ante cortes (proxy Cloud SQL, etc.).
- **Sesiones FastAPI:** `get_db_fastApi()` como dependency que cierra sesión al terminar la petición.

## Entidades principales (SQLAlchemy)

| Modelo | Rol |
|--------|-----|
| **Products** | Catálogo: título, precio, descripción, SKU/código según modelo, relación con imágenes. |
| **ProductImages** | Archivos asociados al producto: `filename`, `url`, `is_main`. |
| **Order** | Pedido: cliente, total, estado (`pendiente`, etc.), nota. |
| **OrderItem** | Líneas de pedido: producto, cantidades, precios unitarios, subtotales. |

Los campos exactos están en `database/models/`; al cambiar el modelo, actualizar este documento y migraciones si se adoptan (Alembic recomendado a futuro).

## Google Cloud Storage

- Bucket de producción referenciado en código (p. ej. `bucket_laslocas_prod` en `main.py`).
- URLs públicas típicas: `https://storage.googleapis.com/<bucket>/...` o campo `url` guardado tras subida.

**Especificación:** toda imagen nueva de producto admin debe quedar referenciada en `ProductImages` con URL estable para el front.

## Scraper “Las Locas”

**Propósito:** extraer de la web origen fotos y precios (y metadatos necesarios) para poblar/actualizar PostgreSQL.

**Herramientas:** Selenium, BeautifulSoup, `requests` (según scripts en `scraper_locas/`).

**Operación:**

- Puede ejecutarse en máquina local o job separado con acceso a DB (y opcionalmente GCS).
- El disparo automático desde la API está **comentado** en `main.py` (`/ejecutar-scraper`); definir política: manual, cron, o pipeline CI.

**Consideraciones:**

- Respetar términos de uso del sitio origen y frecuencia de requests.
- Mantener trazabilidad (`page_ficha` u otro id) para asociar imágenes en bucket con registros.

## DTOs / schemas

- `database/schemas/ProductCreate.py` y tipos en `frontend/src/types/ProductDTO.ts` pueden usarse para alinear contratos front-back cuando el front evolucione.
