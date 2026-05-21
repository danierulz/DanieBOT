# Despliegue y operaciones

## Google Cloud Platform

### Cloud Build (`cloudbuild.yaml`)

1. **Build** imagen Docker: `gcr.io/$PROJECT_ID/laslocaswhatsapp:$COMMIT_SHA`
2. **Push** al Container Registry
3. **Deploy** Cloud Run:
   - Servicio: `deploy-whatsapp-cloudbuild`
   - Región: `us-central1`
   - Imagen: la del paso anterior
   - `--no-allow-unauthenticated` (invocación autenticada; el webhook de Meta debe poder alcanzar la URL — revisar configuración IAM/ingress según doc Meta)
   - **VPC connector:** `whatsapp-bot-vpc-connecto` (acceso a Cloud SQL u otros recursos privados)
   - **Secrets** montados como env (Secret Manager):  
     `PYWA_VERIFY_TOKEN`, `PYWA_AUTH_TOKEN`, `PYWA_PHONE_ID`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`, `LOGIN_EMAIL`, `LOGIN_PASS` (import Las Locas)

### Cloud Run

- Puerto del contenedor: **8080** (variable `PORT` estándar también soportada por Cloud Run).
- Comando: `uvicorn main:app --host 0.0.0.0 --port 8080`
- Logs: Cloud Logging (opción `CLOUD_LOGGING_ONLY` en build).

### Meta / WhatsApp

- Configurar en la app de Meta la URL del webhook HTTPS que apunta al servicio Cloud Run (ruta `/webhook` y verificación GET).
- Mantener `PYWA_VERIFY_TOKEN` alineado con el configurado en Meta.

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
- [ ] Base alcanzable desde Cloud Run (VPC + connector)
- [ ] Secrets actualizados en Secret Manager
- [ ] URL pública del servicio registrada en Meta
- [ ] Revisar que endpoints de debug no expongan información sensible
