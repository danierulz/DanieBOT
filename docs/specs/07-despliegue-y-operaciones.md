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

- Servicio `app`: puerto host `5000` → `8080` del contenedor, `env_file: .env`.
- Servicio `ngrok`: túnel HTTP hacia `app:8080`, puerto `4040` para inspeccionar requests (útil para webhook WhatsApp en local).

## Variables de entorno (referencia)

| Variable | Uso |
|----------|-----|
| `DB_*` | Conexión PostgreSQL |
| `PYWA_*` | Tokens e ID de teléfono WhatsApp |
| `APP_ID`, `APP_SECRET` | Meta / PyWa |
| `GOOGLE_CLOUD_PROJECT` | Integraciones GCP (compose/local) |
| `LOGIN_EMAIL`, `LOGIN_PASS` | Login mayorista Las Locas (import por URL) |

No commitear valores reales; usar `.env` local y Secret Manager en GCP.

## Checklist pre-deploy

- [ ] Tests manuales webhook GET/POST
- [ ] Base alcanzable desde Cloud Run (VPC + connector)
- [ ] Secrets actualizados en Secret Manager
- [ ] URL pública del servicio registrada en Meta
- [ ] Revisar que endpoints de debug no expongan información sensible
