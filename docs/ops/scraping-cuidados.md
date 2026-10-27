# Cuidados al scrapear catálogos

Procedimiento para una corrida masiva en la PC. Las reglas de fondo están en los specs; este archivo no las repite.

- Política, skip y reanudación: [17-scraping-masivo-proveedores.md](../specs/17-scraping-masivo-proveedores.md)
- Identidad, `cod_product` y qué se persiste: [18-import-proveedores-patrones.md](../specs/18-import-proveedores-patrones.md)
- Pestaña admin (no es el lugar de un barrido largo): [21-admin-importacion-masiva.md](../specs/21-admin-importacion-masiva.md)
- Comandos cortos y variables de entorno: [23-bulk-import-notebook.md](../specs/23-bulk-import-notebook.md)

## Solo el notebook

El comando es `python -m provider_importers.bulk.runner`, en la PC del desarrollador.

No crear Cloud Scheduler, Cloud Run Jobs ni un cron de GitHub Actions. El motivo (costo y corridas que mueren a mitad) está en el spec 17.

El CLI no imprime secretos. Nombres de variables (sin valores): spec 23.

## Checklist

- [ ] `.env` local. Confirmar a qué base apunta antes de una corrida que escribe.
- [ ] `--dry-run` primero. Leer `would_fetch` y `would_skip_existing` en el JSON.
- [ ] Dejar `--skip-existing` (viene activo). `--no-skip-existing` vuelve a pegarle a la red.
- [ ] `--limit` chico en la primera corrida que escribe.
- [ ] Sin `--status-active`, salvo que se quiera publicar. El default deja la prenda inactiva (spec 17).
- [ ] Pausa suficiente. So Chic es el caso delicado: ver abajo.
- [ ] Si hace falta recargo, `--price-markup-percent` en el dry-run y en la corrida que escribe. No va con `--tracked-run`.

## Rate limit y 429

So Chic (WooCommerce) responde 429 si las fichas salen rápido. El síntoma en el JSON es `failed` con un error que menciona 429 o "too many".

Qué hacer:

1. Parar. No relanzar el catálogo entero enseguida.
2. Subir `--delay-ms`.
3. Volver a lanzar el mismo comando. Lo ya guardado no se vuelve a scrapear (`--skip-existing`, spec 17). Lo que falló no tiene fila y se reintenta.

Pausas sugeridas entre fichas (`--delay-ms`; si se omite, sale de `brands.json`):

| Proveedor | Pausa |
|-----------|--------|
| So Chic | 5000 ms (default). 8000–10000 ms si hubo 429 |
| Las Locas, Nissie, HOLIC | 1500 ms (default). Subir si el sitio se queja |

La pausa del listado es otra (`LISTING_PAGE_DELAY_SECONDS`, spec 17). `--delay-ms` corre entre fichas del CLI sin `--tracked-run`.

## Recargo de precio

`--price-markup-percent` (float, default `0`) multiplica `price` y, si viene, `original_price` por `1 + percent/100` después del fetch y antes de persistir. Redondea al entero; un empate en `.5` va hacia arriba. `discount_percent` no se toca.

| Percent | Precio scrapeado | Precio que se persiste |
|---------|------------------|------------------------|
| 0 | 10000 | 10000 |
| 10 | 10000 | 11000 |
| 30 | 10000 | 13000 |

El valor sale en el JSON como `price_markup_percent`, también en el dry-run (ahí no se fetchea ni se aplica).

Un número negativo baja el precio. `0` no cambia nada.

No actualiza filas que ya existen: si el `cod_product` está, el runner salta y no pisa el precio (spec 17 y spec 18). El recargo entra solo en altas nuevas.

No combina con `--tracked-run`. Esa corrida no pasa por este recargo y el CLI corta si el porcentaje no es 0. Para marcar precios, corré sin `--tracked-run` (la alta igual persiste; no queda fila en `provider_import_runs`).

## Ejemplos

```bash
python -m provider_importers.bulk.runner --list-brands

python -m provider_importers.bulk.runner --provider sochic --max-pages 1 --limit 5 --dry-run

python -m provider_importers.bulk.runner --provider sochic --max-pages 1 --limit 5 --price-markup-percent 30 --dry-run

python -m provider_importers.bulk.runner --provider sochic --max-pages 1 --limit 5 --delay-ms 8000 --price-markup-percent 30

python -m provider_importers.bulk.runner --provider laslocas --category denim --max-pages 1 --limit 5 --price-markup-percent 15 --dry-run
```

La línea de So Chic con `--delay-ms 8000` y sin `--dry-run` escribe. Confirmá el dry-run antes.
