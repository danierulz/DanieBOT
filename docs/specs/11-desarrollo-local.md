# Desarrollo local (Docker + Postgres)

## Objetivo

Probar la app, pedidos, admin y migraciones **sin conectar a Cloud SQL de producción**.

| Archivo | Uso |
|---------|-----|
| `.env.dev` | Compose local: Postgres en contenedor `db`, `DB_HOST=db` |
| `.env` | Producción / secretos reales (gitignored) |
| `.env.example` | Plantilla de variables |

## Arranque rápido

```powershell
# Desde la raíz del repo (Windows)
.\scripts\dev-init.ps1
docker compose up app
```

```bash
# Linux / macOS
chmod +x scripts/dev-init.sh
./scripts/dev-init.sh
docker compose up app
```

- App: http://localhost:5000  
- Postgres en el host: `localhost:5432` (mismas credenciales que `.env.dev`)

## Servicios Compose

| Servicio | Descripción |
|----------|-------------|
| `db` | PostgreSQL 16, volumen `daniebot_pgdata` |
| `app` | FastAPI en puerto 5000 → 8080 |
| `ngrok` | Perfil `whatsapp`; túnel al webhook |

```bash
# Solo base + app
docker compose up -d db app

# Con túnel para Meta (requiere NGROK_AUTHTOKEN en .env.dev)
docker compose --profile whatsapp up
```

Panel ngrok: http://localhost:4040

## Migraciones y seeds

El script `scripts/dev-init.ps1` (o `.sh`) ejecuta:

1. `docker compose up -d db`
2. `python -m alembic upgrade head` dentro de `app`
3. `seed_reference_data()` (talles y categorías)

Manual:

```bash
docker compose run --rm app python -m alembic upgrade head
docker compose run --rm app python -c "from database.init_db import seed_reference_data; seed_reference_data()"
```

### Alembic desde el host (sin contenedor app)

Usá las mismas credenciales pero `DB_HOST=localhost`:

```powershell
$env:DB_HOST="localhost"
# cargar el resto desde .env.dev o exportar DB_USER, DB_PASSWORD, DB_NAME, DB_PORT
python -m alembic upgrade head
```

## WhatsApp / PyWa en local

1. Completar en `.env.dev`: `PYWA_*`, `APP_ID`, `APP_SECRET` (podés copiarlos de tu `.env` de prod si usás la misma app de Meta en modo dev).
2. `NGROK_AUTHTOKEN` desde el dashboard de ngrok.
3. `docker compose --profile whatsapp up`
4. En Meta, apuntar el webhook a la URL HTTPS que muestra ngrok (`/webhook`).

## Imágenes (sin GCP en local)

`.env.dev` define `STORAGE_BACKEND=local`: las fotos se guardan en `static/uploads/` y se sirven por FastAPI en URLs como:

`http://localhost:5000/static/uploads/...`

No hace falta credencial de Google para crear productos, banners ni subir fotos en el admin.

| Variable | Valor local |
|----------|-------------|
| `STORAGE_BACKEND` | `local` |
| `LOCAL_UPLOAD_DIR` | `static/uploads` |
| `SITE_PUBLIC_URL` | `http://localhost:5000` |

Los imports de proveedor que guardan URLs externas del sitio origen no usan almacenamiento local; solo los bytes descargados pasan por `upload_bytes`.

**Producción:** `STORAGE_BACKEND=gcs` (o omitir) y bucket `GCS_BUCKET_NAME` — ver Cloud Run / Secret Manager.

## Reset de la base local

```bash
docker compose down -v
.\scripts\dev-init.ps1
```

`-v` borra el volumen `daniebot_pgdata`.

## Producción

- **No** uses `env_file: .env.dev` en Cloud Run.
- Primera vez con DB ya existente: `alembic stamp head` (ver [10-alembic-migraciones.md](./10-alembic-migraciones.md)).
- Deploys siguientes: `alembic upgrade head`.
