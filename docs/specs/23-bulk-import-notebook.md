# Alta masiva en el notebook

Comandos para correr el runner en la PC. La política (no agendar en Cloud Scheduler / Cloud Run / GitHub Actions) está en [17-scraping-masivo-proveedores.md](./17-scraping-masivo-proveedores.md). Identidad y `cod_product`: [18-import-proveedores-patrones.md](./18-import-proveedores-patrones.md). Pestaña admin: [21-admin-importacion-masiva.md](./21-admin-importacion-masiva.md).

## Antes de correr

`.env` local (no se commitea). El CLI no imprime secretos.

| Variable | Para qué |
|----------|----------|
| `DATABASE_URL` o `DB_*` | Neon o Postgres local. Apuntar a producción inserta filas reales (inactivas salvo `--status-active`) |
| `LOGIN_EMAIL` / `LOGIN_PASS` | Solo Las Locas |
| `STORAGE_BACKEND` | `local` o `gcs`. Las Locas sube bytes; Nissie, HOLIC y So Chic guardan la URL de la foto |

```bash
python -m provider_importers.bulk.runner --list-brands
```

Marcas: `provider_importers/bulk/brands.json`.

## Comandos

Siempre `--dry-run` primero. `--skip-existing` ya viene activo: no scrapea URLs que la base ya conoce. `--limit` acota fichas **nuevas**. Detalle de reanudación, hueco de URLs viejas y `--no-skip-existing` en el spec 17.

```bash
python -m provider_importers.bulk.runner --provider laslocas --category denim --max-pages 1 --limit 5 --dry-run

python -m provider_importers.bulk.runner --provider laslocas --category denim --max-pages 1 --limit 5 --tracked-run

python -m provider_importers.bulk.runner --provider nissie --limit 10 --dry-run

python -m provider_importers.bulk.runner --provider holic --limit 10 --dry-run

python -m provider_importers.bulk.runner --provider sochic --max-pages 1 --limit 5 --dry-run

python -m provider_importers.bulk.runner --provider sochic --category camperas --max-pages 1 --limit 5 --dry-run

python -m provider_importers.bulk.runner --provider sochic --limit 5 --no-skip-existing --dry-run
```

El JSON de dry-run trae `discovered`, `would_skip_existing` y `would_fetch`.
