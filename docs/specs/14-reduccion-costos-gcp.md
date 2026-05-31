# Reducción de costos GCP (tienda + bot)

Instancia Cloud SQL: `laslocaswhatsapp:us-central1:laslocas-dbng`

## Qué hace el código (automático al mergear y desplegar)

- `cloudbuild.yaml` deja de usar el conector VPC `whatsapp-bot-vpc-connecto`.
- Cloud Run monta el socket de Cloud SQL y define `CLOUD_SQL_CONNECTION_NAME`.
- `database/db_url.py` conecta por socket Unix (no hace falta IP privada en `DB_HOST` si está la env de conexión).

## Qué tenés que hacer vos (tablet, pocos pasos)

### 1. Aprobar el PR y dejar que Cloud Build despliegue

- En GitHub: **Merge** del PR.
- Si el trigger de Cloud Build está en `main`, el deploy corre solo.
- Si no: en la consola GCP → **Cloud Build** → **Historial** → **Ejecutar** el último commit de `main`.

### 2. Permiso Cloud SQL (obligatorio si el deploy falla al arrancar)

Si Cloud Build termina con *"container failed to start"* o *"listen on PORT=8080"*, casi siempre es la **base de datos** en el arranque (migraciones), no el puerto.

En los logs del contenedor buscá:
- `Socket Cloud SQL ausente` → falta `--add-cloudsql-instances` o permiso IAM.
- `Fallo al migrar` → credenciales `DB_*` o instancia SQL apagada.

Cloud Run → servicio `deploy-whatsapp-cloudbuild` → pestaña **Seguridad** → copiá el **correo de la cuenta de servicio** (termina en `@...gserviceaccount.com`).

IAM → **Conceder acceso** → principal = esa cuenta → rol **Cloud SQL Client** → Guardar.

Volvé a ejecutar el build o redeploy.

### 3. Probar (2 minutos)

- Abrí la URL pública de la tienda (home y un producto).
- Entrá al admin y listá productos.
- Mandá un mensaje de prueba al bot de WhatsApp.

Si algo falla: Cloud Run → **Registros**; buscá errores de conexión a la base.

### 4. Opcional: borrar el conector VPC (ahorro ~$3–7/mes)

Solo cuando la tienda y el bot funcionen bien:

GCP → **VPC network** → **Serverless VPC access** → eliminá `whatsapp-bot-vpc-connecto`.

### 5. Opcional: achicar Cloud SQL

SQL → `laslocas-dbng` → **Editar** → tier **db-f1-micro**, disco mínimo, **sin** alta disponibilidad.

---

## Secret `DB_HOST`

No es obligatorio cambiarlo: con `CLOUD_SQL_CONNECTION_NAME` en el deploy, la app ignora la IP privada antigua.

Si querés ordenar Secret Manager, podés poner en `DB_HOST` el valor  
`laslocaswhatsapp:us-central1:laslocas-dbng` (mismo formato que la instancia).
