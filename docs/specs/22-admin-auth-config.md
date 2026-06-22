# Configuración de credenciales del admin

Guía para reemplazar `admin` / `admin123` y `supersecretkey` hardcodeados.

## Variables

| Variable | Obligatoria en prod | Descripción |
|----------|---------------------|-------------|
| `ADMIN_USERNAME` | Sí | Usuario para `/login` |
| `ADMIN_PASSWORD_HASH` | Sí | Hash bcrypt (no la contraseña en claro) |
| `JWT_SECRET_KEY` | Sí | Clave para firmar tokens JWT (string largo aleatorio) |
| `ADMIN_PASSWORD` | No | Solo dev con `APP_DEBUG=true`; evitar en prod |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default `480` (8 h) |

## Configuración local (juntos)

1. Instalar dependencia (si falta):

   ```powershell
   pip install "passlib[bcrypt]"
   ```

2. Ejecutar el asistente:

   ```powershell
   python scripts/setup_admin_auth.py
   ```

   Te pide usuario y contraseña (la contraseña no se muestra al escribir).

3. Copiar el bloque que imprime al final de tu `.env`, **o** agregar directo:

   ```powershell
   python scripts/setup_admin_auth.py --append-env
   ```

   (Crea backup `.env.bak` si ya tenías `.env`.)

4. Reiniciar el servidor:

   ```powershell
   python main.py
   ```

5. Probar en `http://localhost:8080/login` con el usuario y contraseña que elegiste.

## Verificar configuración

`GET /healt` incluye:

```json
"admin_auth": {
  "username_configured": true,
  "password_hash_configured": true,
  "jwt_secret_configured": true,
  "using_dev_defaults": false
}
```

Si `using_dev_defaults` es `true` con `APP_DEBUG=true`, todavía estás en fallback `admin/admin123`.

## Producción (Cloud Run)

1. Crear secretos en GCP Secret Manager:

   ```powershell
   echo -n "tu_usuario" | gcloud secrets create ADMIN_USERNAME --data-file=-
   echo -n "hash_bcrypt..." | gcloud secrets create ADMIN_PASSWORD_HASH --data-file=-
   echo -n "jwt_secret_largo..." | gcloud secrets create JWT_SECRET_KEY --data-file=-
   ```

2. Montarlos en `cloudbuild.yaml` (ya incluidos en `--set-secrets` del deploy):

   ```
   ADMIN_USERNAME=ADMIN_USERNAME:latest,ADMIN_PASSWORD_HASH=ADMIN_PASSWORD_HASH:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest
   ```

   La service account de Cloud Run necesita **Secret Manager Secret Accessor** en cada secreto.

3. **No** commitear `.env` con valores reales.

4. Tras cambiar `JWT_SECRET_KEY`, las sesiones anteriores quedan inválidas (hay que volver a loguearse).

## Ocultar Login / Admin en la tienda pública

Por defecto en producción (`APP_DEBUG=false`) **no** se muestra el botón «Login» en el header. El panel sigue accesible escribiendo la URL directamente.

| Variable | Default prod | Efecto |
|----------|--------------|--------|
| `ADMIN_LOGIN_NAV_VISIBLE` | `false` | Sin botón Login/Logout en el nav para visitantes |
| `ADMIN_LOGIN_PATH` | `/login` | Ruta de login (podés cambiarla por una menos obvia) |

Con sesión JWT válida en el navegador sí aparecen **Admin Panel** y **Logout**.

### Otras opciones (no implementadas en código)

| Enfoque | Pros | Contras |
|---------|------|---------|
| **URL directa** (`/login` o path custom) | Simple, ya activo | Security by obscurity; conviene contraseña fuerte |
| **Path custom** (`ADMIN_LOGIN_PATH=/acceso-jazmines`) | Menos predecible que `/login` | Hay que guardar el bookmark |
| **Cloud Run IAM** | Solo usuarios Google autorizados | Más setup; no reemplaza login del panel |
| **IP allowlist** (firewall / Cloud Armor) | Bloquea el resto del mundo | Incómodo si trabajás desde varios lugares |

Recomendación: `ADMIN_LOGIN_NAV_VISIBLE=false` + credenciales bcrypt + bookmark de `/login` (o path custom).

## Desarrollo sin configurar (temporal)

Con `APP_DEBUG=true` y sin variables admin, sigue funcionando `admin` / `admin123` con advertencia en logs. **No desplegar así.**

## Archivos

| Archivo | Rol |
|---------|-----|
| `auth/auth.py` | Verificación bcrypt + JWT desde env |
| `scripts/setup_admin_auth.py` | Generador interactivo |
| `main.py` | `POST /login` usa `authenticate_admin()` |
