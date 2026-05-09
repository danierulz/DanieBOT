# Arquitectura y stack

## Vista lógica

```text
                    ┌─────────────────────────────────────┐
                    │           Cloud Run                 │
                    │  FastAPI (main.py) + Uvicorn :8080  │
                    │  ├─ Jinja templates + /static       │
                    │  ├─ REST /api/*                     │
                    │  └─ PyWa webhook /webhook           │
                    └───────────┬─────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
   PostgreSQL              GCS bucket            Meta WhatsApp
   (Cloud SQL via          (imágenes)            Cloud API
    VPC connector)

   Scraping (local/batch) ──► PostgreSQL + GCS
   Selenium + BeautifulSoup
```

## Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Runtime | Python 3.10 (Dockerfile), FastAPI, Uvicorn |
| WhatsApp | PyWa, Meta Cloud API (variables `PYWA_*`, `APP_ID`, `APP_SECRET`) |
| Base de datos | PostgreSQL, SQLAlchemy, driver pg8000 en URL de conexión |
| Object storage | `google-cloud-storage` (`GCSUploader`) |
| Scraping | Selenium, BeautifulSoup, requests |
| Web cliente | HTML + Jinja2, Tailwind (CSS compilado en `static/`), JS vanilla (`shoppingCart.js`) |
| Auth admin | JWT (`python-jose`), OAuth2 password |

## Archivos y módulos relevantes

| Ruta | Rol |
|------|-----|
| `main.py` | App FastAPI central: webhook WhatsApp, rutas web, API productos, uploads. |
| `database/` | `init_db.py` (engine, sesiones), modelos SQLAlchemy, schemas Pydantic. |
| `auth/auth.py` | JWT, usuario admin (ajustar secretos y hash en producción). |
| `gcs/GCSUploader.py` | Subida de archivos al bucket. |
| `scraper_locas/` | Scraping “Las Locas”. |
| `routes/orders.py` | Lógica de creación de pedidos vía API (ver estado en backlog). |
| `templates/`, `static/` | UI tienda y admin. |
| `Dockerfile` | Imagen para Cloud Run (`WORKDIR /DANIEBOT`). |
| `cloudbuild.yaml` | Build Docker → push GCR → deploy Cloud Run + secrets. |
| `docker-compose.yml` | App local + ngrok para webhooks. |

## Principios de diseño (objetivo)

1. **Separación progresiva:** mover rutas grandes de `main.py` a routers (`APIRouter`) manteniendo un solo deploy.
2. **Una fuente de verdad de precios:** el total mostrado en web debe coincidir con DB y con el mensaje de WhatsApp.
3. **Secretos fuera del código:** tokens Meta, credenciales DB y claves JWT vía Secret Manager / env.
