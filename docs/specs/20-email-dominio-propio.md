# Email con dominio propio (NIC Argentina + DanieBOT)

Guía operativa para avisos de pedidos con `@outfitjazmines.com.ar`.

## Resumen

| Componente | Rol |
|------------|-----|
| **NIC Argentina** | Registro del dominio y panel DNS (MX, TXT, CNAME) |
| **Zoho Mail** (recomendado) | Buzón + SMTP gratuito |
| **DanieBOT** | Envía mail al crear/confirmar pedido vía [`services/email_notify.py`](../../services/email_notify.py) |

NIC **no incluye** correo. Hay que contratar un proveedor y apuntar DNS.

**Estado por defecto:** email **desactivado** en producción (`ADMIN_NOTIFY_EMAIL_ENABLED=false`). Podés deployar todos los demás cambios sin Zoho; los pedidos y WhatsApp al asesor siguen funcionando.

## Activar email después del deploy

Cuando tengas buzón y SMTP listos (Zoho u otro proveedor):

1. Zoho + DNS en NIC (pasos 1–2 abajo).
2. `.\scripts\setup_smtp_secrets.ps1 -ProjectId laslocaswhatsapp`
3. `python scripts/verify_smtp.py --send-test`
4. En [`cloudbuild.yaml`](../../cloudbuild.yaml):
   - `--set-env-vars` → `ADMIN_NOTIFY_EMAIL_ENABLED=true`
   - Añadir a `--set-secrets`: `ADMIN_NOTIFY_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
   - Quitar `--remove-secrets` de los secretos SMTP (o eliminar esa línea)
5. Redeploy vía Cloud Build.

Hasta entonces, `GET /healt` debe mostrar `admin_email.enabled: false`.

## Paso 1 — Zoho Mail (proveedor recomendado)

1. Crear cuenta en [Zoho Mail](https://www.zoho.com/mail/) → **Add existing domain** → `outfitjazmines.com.ar`.
2. Elegir plan **Forever Free** (1 usuario, 5 GB).
3. Crear buzón: `pedidos@outfitjazmines.com.ar` (o `admin@...`).
4. **Security → App passwords** → generar contraseña para SMTP (no usar la contraseña de login web).

Host SMTP según región (ver panel Zoho):

| Región cuenta | Host |
|---------------|------|
| Global (.com) | `smtp.zoho.com` |
| Europa | `smtp.zoho.eu` |
| India | `smtp.zoho.in` |

Puerto: **587** (STARTTLS).

## Paso 2 — DNS en NIC Argentina

1. Entrar a [nic.ar](https://nic.ar) → **Mis dominios** → `outfitjazmines.com.ar` → **Administración de DNS**.
2. Agregar los registros que indique Zoho (copiar exacto desde su asistente de verificación):

| Tipo | Uso típico |
|------|------------|
| **MX** | `mx.zoho.com` (prioridad 10), `mx2.zoho.com` (20), `mx3.zoho.com` (50) |
| **TXT** | Verificación de dominio (`zoho-verification=...`) |
| **TXT** | SPF: `v=spf1 include:zoho.com ~all` |
| **TXT/CNAME** | DKIM (selector que asigne Zoho) |

3. Esperar propagación (minutos a 24 h). Verificar en Zoho que el dominio quede **Verified**.

**Nota:** Los registros del sitio web (A/CNAME hacia Cloud Run) **no interfieren** con MX del correo.

## Paso 3 — Variables locales (`.env`)

Copiar de [`.env.example`](../../.env.example):

```env
ADMIN_NOTIFY_EMAIL_ENABLED=true
ADMIN_NOTIFY_EMAIL=pedidos@outfitjazmines.com.ar
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USER=pedidos@outfitjazmines.com.ar
SMTP_PASSWORD=<app_password_zoho>
SMTP_FROM=pedidos@outfitjazmines.com.ar
```

Verificar sin enviar mail:

```powershell
python scripts/verify_smtp.py
```

Enviar mail de prueba:

```powershell
python scripts/verify_smtp.py --send-test
```

## Paso 4 — Producción (Cloud Run + Secret Manager)

Solo cuando quieras activar email (ver sección «Activar email después del deploy» arriba).

Crear secretos en GCP:

```powershell
.\scripts\setup_smtp_secrets.ps1 -ProjectId laslocaswhatsapp
```

El script pide los valores (o `-FromEnv` si ya están en `.env`). Tras ajustar `cloudbuild.yaml` (ENABLED=true + secretos SMTP), el deploy monta:

- `ADMIN_NOTIFY_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `ADMIN_NOTIFY_EMAIL_ENABLED=true` como env var no secreta

Actualizar un secreto existente:

```powershell
echo -n "nueva_app_password" | gcloud secrets versions add SMTP_PASSWORD --data-file=-
```

## Paso 5 — Prueba end-to-end

1. Confirmar pedido en la web → mail **Nuevo pedido web OJ-…**
2. Enviar código `OJ-…` al bot WhatsApp → mail **Pedido confirmado por WhatsApp OJ-…**
3. Revisar bandeja `pedidos@...` (y carpeta spam la primera vez).

Health check: `GET /healt` incluye `admin_email.configured`.

## Alternativas

| Proveedor | Cuándo usarlo |
|-----------|----------------|
| **Google Workspace** | Gmail con dominio (~USD 6/usuario/mes); SMTP `smtp.gmail.com` + app password |
| **Hosting (DonWeb, etc.)** | Si ya incluye casillas con el plan |
| **Resend / SendGrid** | Solo envío transaccional; verificar dominio en NIC con TXT/CNAME |

Migrar de proveedor = cambiar MX en NIC + actualizar `SMTP_*` en secretos. Sin cambios de código.

## Errores frecuentes

- **SMTP auth failed:** usar app password de Zoho, no la contraseña web.
- **Mail en spam:** completar SPF y DKIM en NIC.
- **Deploy Cloud Run falla por SMTP:** no hace falta Zoho para deployar; email viene desactivado por defecto. Si activaste SMTP en `cloudbuild.yaml`, creá secretos con `setup_smtp_secrets.ps1` antes del build.
- **Pedido OK pero sin mail:** revisar logs Cloud Run (`Fallo envío email al admin`); verificar `GET /healt`.
