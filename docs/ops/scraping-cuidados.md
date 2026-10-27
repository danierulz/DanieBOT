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

So Chic (WooCommerce) responde HTTP 429, o una página que dice «limitó las consultas» / too many requests, si el listado o las fichas salen rápido. El CLI **no** reintenta en un loop cerrado.

Esto corre en `python -m provider_importers.bulk.runner` **sin** `--tracked-run` (So Chic no tiene tracked). No crea Cloud Scheduler, Cloud Run Job ni un cron: el cooldown es un aviso para relanzar a mano.

Qué hace el runner:

1. Frena esa URL. No manda otro pedido enseguida.
2. Espera con backoff escalonado y vuelve a intentar **la misma** URL. La primera espera es `--rate-limit-backoff-seconds` (default 15). Después se duplica (30, 60, …) hasta `--rate-limit-max-backoff-seconds` (default 120). Si la respuesta trae `Retry-After` en segundos y pide más, se usa esa espera, con tope en el mayor entre el tope de backoff y el cooldown.
3. `--rate-limit-retries` (default 3) es cuántas veces reintenta después del primer 429. `--rate-limit-retries 0` y `--rate-limit-hard-stop` cortan en el primer 429, sin espera.
4. Si se agotan los reintentos (o hay hard stop), **no sigue con el resto de la corrida**. Lo ya persistido queda en la base (cada alta hace commit). El proceso imprime el JSON y sale con código 1.

El listado de So Chic usa la misma política. Si el listado queda limitado, esa corrida **no** pide fichas (ni las que ya había descubierto). `stopped_during` sale `listing`.

Campos del JSON cuando corta:

| Campo | Significado |
|-------|-------------|
| `rate_limited` | `true` |
| `cooldown_hint_seconds` | Segundos a esperar antes de relanzar. Default 600 (`--rate-limit-cooldown-seconds`). No los duerme el proceso. |
| `stopped_during` | `listing` o `product` |
| `aborted_remaining` | Fichas que no se pidieron después del corte |
| `rate_limit_attempts` | Intentos de la URL (o página) que cortó la corrida |
| `created` | Altas que ya quedaron guardadas |

```json
{
  "rate_limited": true,
  "cooldown_hint_seconds": 600,
  "stopped_during": "product",
  "aborted_remaining": 3,
  "rate_limit_attempts": 4,
  "created": 2,
  "failed": 1
}
```

Qué hacer después:

1. No relanzar el catálogo enseguida. Esperar al menos `cooldown_hint_seconds`.
2. Si el 429 fue con la pausa default, subir `--delay-ms`.
3. Volver a lanzar el mismo comando. Lo ya guardado no se vuelve a scrapear (`--skip-existing`, spec 17). Lo que no llegó a persistirse se reintenta.

`--delay-ms` sigue siendo la pausa entre fichas que respondieron. El backoff es aparte y solo corre después de un 429.

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

python -m provider_importers.bulk.runner --provider sochic --max-pages 1 --limit 5 --delay-ms 8000 --rate-limit-retries 3 --price-markup-percent 30

python -m provider_importers.bulk.runner --provider sochic --max-pages 1 --limit 5 --rate-limit-hard-stop --dry-run

python -m provider_importers.bulk.runner --provider laslocas --category denim --max-pages 1 --limit 5 --price-markup-percent 15 --dry-run
```

La línea de So Chic con `--delay-ms 8000` y sin `--dry-run` escribe. Confirmá el dry-run antes.
