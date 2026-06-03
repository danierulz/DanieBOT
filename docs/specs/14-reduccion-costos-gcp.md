# Reducción de costos GCP (tienda + bot)

## Estado actual (Jun 2026)

| Recurso | Estado | Costo aprox. |
|---------|--------|--------------|
| **Cloud SQL** `laslocas-dbng` | **Eliminado** (0 instancias) | ~USD 0 |
| **VPC connector** `whatsapp-bot-vpc-connecto` | **Eliminado** | ~USD 0 (antes ~3–7/mes) |
| **Base de datos** | **Neon** (`DATABASE_URL` en Secret Manager) | Factura en Neon, no en GCP |
| **Cloud Run** `deploy-whatsapp-cloudbuild` | `us-central1`, escala a 0, max 5 instancias | Pay-per-use |
| **GCR** `laslocaswhatsapp` | Muchas tags históricas | Centavos–USD 1/mes según tags |

La app **no usa** `DB_HOST` / `DB_*` en Cloud Run (se quitan en deploy). Podés archivar esos secretos viejos en Secret Manager si querés orden (costo por secreto: centavos).

---

## Qué ya está optimizado en `cloudbuild.yaml`

- `--clear-vpc-connector` — sin conector Serverless VPC
- `--no-cpu-boost` — sin CPU extra al arrancar (ahorro en cold starts)
- `--max-instances=5` — tope ante picos o abuso
- `--memory=512Mi` / `--cpu=1` — tamaño fijo razonable para FastAPI + migraciones
- Solo secretos necesarios: `DATABASE_URL`, WhatsApp, login admin

---

## Acciones manuales recomendadas (consola o CLI)

### 1. Limpiar imágenes Docker viejas (GCR)

Cada deploy sube una tag nueva. Las viejas ocupan disco.

```powershell
cd C:\Projects\DanieBOT
.\scripts\gcp_prune_images.ps1 -Keep 8
```

Conserva las 8 más recientes; borra el resto.

### 2. Desactivar APIs que ya no usás

Si no volvés a Cloud SQL ni VPC connector:

```bash
gcloud services disable sqladmin.googleapis.com --project laslocaswhatsapp
gcloud services disable vpcaccess.googleapis.com --project laslocaswhatsapp
```

No baja la factura si no hay recursos, pero reduce superficie y confusiones.

### 3. Presupuesto y alertas

Billing → **Budgets & alerts** → crear presupuesto mensual (ej. USD 15) con alerta al 50 % y 90 %.

### 4. Revisar factura por SKU

Billing → **Reports** → filtrar:

- **Cloud Run** — compute + egress
- **Networking** → **Network egress** — tráfico a usuarios, Meta API y Neon
- **Cloud Build** — minutos de build (free tier mensual)
- **Artifact Registry / GCR** — almacenamiento de imágenes

### 5. Neon (fuera de GCP)

El costo de Postgres migró a Neon. Revisá en [console.neon.tech](https://console.neon.tech): plan free/autoscale, suspender compute inactivo si aplica.

---

## Networking / egress (lo que suele aparecer en billing)

- **Entrada** al sitio y webhooks de Meta: gratis.
- **Salida** (egress): HTML, JS, llamadas a Graph API, queries a Neon → se factura por GB (volumen bajo en tienda chica).
- **Región `us-central1`**: no es “global”; es Iowa. Cambiar a `southamerica-east1` mejora latencia a AR pero Neon suele estar en US igual; el ahorro de egress es marginal salvo mucho tráfico.

---

## Qué NO hacer sin migrar de nuevo

- Volver a encender Cloud SQL 24/7 “por las dudas” — era el mayor costo fijo.
- Recrear el VPC connector sin necesidad — ~USD 3–7/mes mínimo aunque no lo uses mucho.

---

## Checklist rápido post-deploy

1. Tienda carga (home + producto).
2. Admin login y listado.
3. WhatsApp webhook (mensaje de prueba).
4. Cloud Run → **Registros** sin errores de `DATABASE_URL`.
5. Ejecutar `gcp_prune_images.ps1` una vez al mes si deployás seguido.
