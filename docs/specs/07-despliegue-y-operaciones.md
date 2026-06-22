# Despliegue y operaciones

## Google Cloud Platform

### Cloud Build (`cloudbuild.yaml`)

1. **Build** imagen Docker: `gcr.io/$PROJECT_ID/laslocaswhatsapp:$COMMIT_SHA`
2. **Push** al Container Registry
3. **Deploy** Cloud Run:
   - Servicio: `deploy-whatsapp-cloudbuild`
   - Región: `us-central1`
   - Imagen: la del paso anterior
   - `--allow-unauthenticated` (tienda pública y webhook Meta; admin protegido con JWT)
   - **Secrets** montados como env (Secret Manager):  
     `PYWA_VERIFY_TOKEN`, `PYWA_AUTH_TOKEN`, `PYWA_PHONE_ID`, `DATABASE_URL`, `LOGIN_EMAIL`, `LOGIN_PASS`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_SECRET_KEY`
   - **Env vars** en deploy: `APP_DEBUG=false`, `ADMIN_LOGIN_NAV_VISIBLE=false`, `STORAGE_BACKEND=gcs`, `GCS_BUCKET_NAME`, `SITE_PUBLIC_URL`, `GOOGLE_CLOUD_PROJECT`

   **Email SMTP (avisos de pedidos):** opcional. Por defecto `ADMIN_NOTIFY_EMAIL_ENABLED=false` en Cloud Build; no se montan secretos SMTP. El deploy no depende de Zoho. Para activar después: [20-email-dominio-propio.md](./20-email-dominio-propio.md) → sección «Activar email después del deploy».

   `APP_ID` y `APP_SECRET` están hoy como **variables de entorno literales** en Cloud Run (no Secret Manager). No incluirlos en `--set-secrets` del deploy: gcloud falla si cambiás el tipo. Para migrarlos a secretos: borrar esas env vars en la consola y agregarlas a `--set-secrets`.

### Cloud Run

- Puerto del contenedor: **8080** (variable `PORT` estándar también soportada por Cloud Run).
- Comando: `uvicorn main:app --host 0.0.0.0 --port 8080`
- Logs: Cloud Logging (opción `CLOUD_LOGGING_ONLY` en build).

### Meta / WhatsApp

- Configurar en la app de Meta la URL del webhook HTTPS que apunta al servicio Cloud Run.
- **Callback URL:** `https://<tu-dominio>/webhook` (sin barra final; es la ruta que usaba el proyecto antes del refactor).
- PyWa también registra `/webhook/`; ambas rutas están soportadas vía `whatsapp/webhook_routes.py`.
- `PYWA_PHONE_ID` debe ser el **Phone number ID** numérico de Meta (API Setup), **no** el número de teléfono con `+54`.
- Mantener `PYWA_VERIFY_TOKEN` alineado con el configurado en Meta.
- Tras deploy, `GET /healt` incluye `whatsapp.configured`, `webhook_paths` y `signature_validation`.
- **`APP_SECRET`** debe coincidir con el *App Secret* de Meta (Basic settings). Si no coincide, el webhook responde `200` con `Unmatching signature` y **el bot ignora el mensaje** sin error visible para Meta.

## Docker local

- `Dockerfile`: `WORKDIR /DANIEBOT`, copia `requirements.txt`, instala deps, copia código.
- **Importante:** rutas que asumen `/DANIEBOT` en disco deben ser coherentes con el despliegue (p. ej. endpoint `/debug`).

## docker-compose (desarrollo)

- **`env_file: .env.dev`** — Postgres local en el servicio `db`; no usar el `.env` de producción con compose por defecto.
- Servicio `db`: PostgreSQL 16, puerto `5432`, datos en volumen `daniebot_pgdata`.
- Servicio `app`: puerto host `5000` → `8080`, depende de `db` (healthcheck).
- Servicio `ngrok` (perfil `whatsapp`): túnel hacia `app:8080`, puerto `4040`.

Guía paso a paso: [11-desarrollo-local.md](./11-desarrollo-local.md).

```powershell
.\scripts\dev-init.ps1    # migraciones + seeds
docker compose up app
```

## Variables de entorno (referencia)

| Variable | Uso |
|----------|-----|
| `DB_*` | Conexión PostgreSQL |
| `PYWA_*` | Tokens e ID de teléfono WhatsApp |
| `APP_ID`, `APP_SECRET` | Meta / PyWa |
| `GOOGLE_CLOUD_PROJECT` | Integraciones GCP (compose/local) |
| `LOGIN_EMAIL`, `LOGIN_PASS` | Login mayorista Las Locas (import por URL) |

No commitear valores reales de producción; usar `.env` (gitignored) o Secret Manager en GCP. Desarrollo Docker: `.env.dev` (credenciales de Postgres solo local).

## Migraciones de base de datos (Alembic)

Antes o durante un deploy que cambie modelos en `database/models/`:

```bash
python -m alembic upgrade head
```

Si la base de producción **ya tiene** el esquema completo y es la primera vez con Alembic:

```bash
python -m alembic stamp head
```

Detalle: [10-alembic-migraciones.md](./10-alembic-migraciones.md).

## Checklist pre-deploy

- [ ] Tests manuales webhook GET/POST
- [ ] Base alcanzable desde Cloud Run (Cloud SQL instance + rol `Cloud SQL Client` en la SA de Run)
- [ ] Secrets actualizados en Secret Manager
- [ ] URL pública del servicio registrada en Meta
- [ ] Revisar que endpoints de debug no expongan información sensible
