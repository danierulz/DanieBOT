# Admin — importación masiva (pestaña dedicada)

Documento de referencia para la UI de importación masiva en el panel de administración.

Relacionado: [17-scraping-masivo-proveedores.md](./17-scraping-masivo-proveedores.md), [18-import-proveedores-patrones.md](./18-import-proveedores-patrones.md).

## Separación de responsabilidades

El panel admin distingue dos flujos de alta de productos:

| Pestaña | Uso | Alcance |
|---------|-----|---------|
| **Nuevo producto** | Alta **manual** | Formulario: título, precio, fotos, variantes, colores |
| **Importación masiva** | Import **automático** desde proveedores | Una ficha por URL + catálogos completos (Nissie, HOLIC, Las Locas) |

**Motivo:** el formulario manual no debe mezclarse con scrapers ni importaciones automáticas.

## Ubicación en la UI

- Ruta: `/admin-panel?tab=bulk`
- Plantilla: [`templates/admin-panel.html`](../../templates/admin-panel.html) — panel `#panel-bulk`
- Pestaña: `admin_tab_bulk_import` en [`config.py`](../../config.py)

La pestaña **Nuevo producto** conserva solo el formulario manual (título, precio, variantes, imágenes, etc.).

La pestaña **Importación masiva** incluye:

- Import unitario por URL (`POST /api/proveedores/importar`)
- Import masivo por proveedor (Nissie, HOLIC, Las Locas)

## Proveedores en importación masiva

Cada proveedor tiene su bloque con barra de progreso, fases y contadores:

| Proveedor | Endpoint | Opciones extra |
|-----------|----------|----------------|
| Nissie | `POST /api/proveedores/nissie/importar-masivo` | Catálogo completo |
| HOLIC | `POST /api/proveedores/holic/importar-masivo` | Catálogo completo |
| Las Locas | `POST /api/proveedores/laslocas/importar-masivo` | Categoría, todas las categorías, máx. páginas |

## Progreso visible

Polling cada 2 s contra `GET /api/proveedores/importaciones/{run_id}`.

| Fase (`phase`) | UI |
|----------------|-----|
| `discovering` | Barra indeterminada + «Explorando catálogo…» + detalle por página/categoría |
| `importing` | Barra `processed/discovered` + creados / omitidos / errores |
| `completed` / `failed` | Resumen final + listado de URLs con error |

Campos relevantes del run: `phase`, `progress_detail`, `discovered`, `processed`, `is_stale`.

Si un run lleva más de 2 h en `running`, la UI muestra aviso y botón **Marcar como fallida** (`POST /api/proveedores/importaciones/{id}/cancelar`).

## Enlaces útiles desde la pestaña

Cada bloque incluye «Ver pendientes de revisión» → abre **Mis productos** filtrado por proveedor e inactivos.

## Archivos principales

| Archivo | Rol |
|---------|-----|
| `templates/admin-panel.html` | Pestaña, paneles, JS `renderBulkRun` |
| `config.py` | Textos de pestaña y mensajes de progreso |
| `services/provider_import_runs.py` | `serialize_run`, heartbeat, cancelación |
| `services/*_bulk_import.py` | Orquestación por proveedor |
| `provider_importers/*_catalog.py` | Discovery con callback de progreso |

## CLI en el notebook

Los catálogos largos se corren en la PC, no como job de Cloud Run ni Cloud Scheduler. La pestaña admin sigue usando `BackgroundTasks` en el request: en Cloud Run esa corrida puede morir a mitad. Para un barrido completo usá el CLI y leé la política en [17-scraping-masivo-proveedores.md](./17-scraping-masivo-proveedores.md). Comandos: [23-bulk-import-notebook.md](./23-bulk-import-notebook.md). Patrones de `cod_product`: [18-import-proveedores-patrones.md](./18-import-proveedores-patrones.md).

```bash
python -m provider_importers.bulk.runner --provider laslocas --category denim --max-pages 1 --limit 5 --dry-run
```
