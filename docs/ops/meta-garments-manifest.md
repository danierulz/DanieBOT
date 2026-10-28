# Manifiesto de prendas para robotRZ

Exporta productos de DanieBOT (fila + fotos) a un JSON que consumen los scripts de robotRZ `meta_page_garments.py` y `meta_ig_garments.py`.

Este comando **no publica** en Meta, no llama a Graph, no scrapea Sochic y no guarda tokens. La pausa entre publicaciones de Graph queda afuera: la maneja quien opera robotRZ.

Corre solo en el notebook, con el `.env` local. No crear Cloud Scheduler, Cloud Run Job ni un cron de GitHub Actions.

## Antes de correr

El CLI no imprime la URL de la base. Si no puede conectar, avisa que revises el `.env` y corta.

| Variable | Para qué |
|----------|----------|
| `DATABASE_URL` o `DB_*` | Misma base que el admin y el import masivo |

Los productos inactivos (`status` false) **entran** en el export. No hay `--status-active`.

## Dry-run primero

```bash
python -m services.meta_manifest --provider sochic --limit 5 --output exports/sochic-meta.json --dry-run
```

El dry-run lee la base y imprime ids, títulos, cantidad de imágenes HTTPS y la ruta. No escribe el archivo y no necesita Graph.

Otros filtros, los más nuevos primero (`product_id` descendente):

```bash
python -m services.meta_manifest --product-id 300 --product-id 292 --output exports/lote.json --dry-run

python -m services.meta_manifest --provider sochic --limit 20 --exclude-id sochic-300 --exclude-file exports/ya-publicados.txt --output exports/sochic-meta.json --dry-run

python -m services.meta_manifest --provider sochic --channel ig --exclude-file exports/ya-publicados.txt --output exports/sochic-meta-ig.json --dry-run
```

`--exclude-id` se puede repetir (o separar por comas). Acepta el slug del manifiesto (`sochic-300`, `denim-292`), el `product_id` o el `cod_product`, con o sin canal (`sochic-292:page`). `--exclude-file` es la misma lista en un archivo: un id por línea (`#` comenta), comas, o un array JSON (un manifiesto anterior también sirve: lee el campo `id` de cada objeto).

## Saltar lo ya publicado (Page e IG por separado)

Después de publicar en Graph, el ledger anota cada id con el canal que ya salió. El archivo no se commitea. **Un solo archivo, sin sidecar:** se evoluciona `exports/ya-publicados.txt`, el mismo path que robotRZ puede usar en `MARKET_OPS_EXCLUDE_FILE`. El exclude de DanieBOT y el de robotRZ leen esas mismas líneas.

El formato es el de `tmp/ops-console/publicados.txt` en robotRZ (ledger `#21`):

| Línea | Significado |
|-------|-------------|
| `sochic-300` | Publicado en Page **y** en IG. Un id pelado = los dos canales. |
| `sochic-292:page` | Page ok. IG pendiente. |
| `denim-288:ig` | IG ok. Page pendiente. |
| `sochic-280:page` y `sochic-280:ig` | Las dos líneas juntas equivalen a un id pelado. |

El id puede ser el slug del manifiesto (`sochic-300`), el `product_id` (`3515:page`) o el `cod_product`. Mayúsculas no importan. Un sufijo que no sea `page` o `ig` corta el comando con error, sin leer la base y sin llamar a Graph. Este export **no** consulta Graph ni reescribe el ledger: robotRZ anota `:page` / `:ig` después de publicar, y ese txt (o una copia) es `exports/ya-publicados.txt`.

`exports/ya-publicados.txt`:

```text
# mismo formato que robotRZ tmp/ops-console/publicados.txt
# id pelado = Page e IG
sochic-300
# Page ok, IG pendiente
sochic-292:page
denim-288:ig
3515:page
```

### Ola solo de IG (Page ok, IG pendiente)

`--channel ig` omite los ids pelados y los `id:ig`. Los `id:page` entran al JSON. El resumen lista esos ids como `ya en page, pendientes de ig`.

```bash
python -m services.meta_manifest --provider sochic --channel ig --exclude-file exports/ya-publicados.txt --output exports/sochic-meta-ig.json --dry-run
```

Ola solo de Page: `--channel page` (omite pelados y `:page`; deja pasar `:ig`).

Sin `--channel`, cualquier id que aparezca en el archivo se omite, tenga o no sufijo. Una línea `id:page` **no** vuelve a salir hasta que pases el canal. Para filtrar a mano una lista pelada (herramientas que no leen `:page` / `:ig`), dejá solo lo ya hecho en el canal destino. Un id pelado cuenta para los dos:

```bash
python - <<'PY'
from pathlib import Path
from services.meta_manifest import ids_published_on, parse_exclude_tokens

text = Path("exports/ya-publicados.txt").read_text(encoding="utf-8")
done = ids_published_on(parse_exclude_tokens(text), "ig")
Path("exports/ya-publicados-ig.txt").write_text("\n".join(done) + ("\n" if done else ""), encoding="utf-8")
PY

python -m services.meta_manifest --provider sochic --exclude-file exports/ya-publicados-ig.txt --output exports/sochic-meta-ig.json --dry-run
```

Esa lista plana es solo para esta ola. No la pongas en `MARKET_OPS_EXCLUDE_FILE`: ahí un id pelado vuelve a significar los dos canales. El archivo compartido sigue siendo `exports/ya-publicados.txt` con los sufijos.

Si una prenda quedó anotada como id pelado pero en realidad solo está en la página, cambiala a `id:page` antes de la ola de IG. Si no, `--channel ig` la sigue omitiendo (id pelado = los dos canales, igual que robotRZ).

Sacar una lista pelada de un manifiesto que ya se publicó en los dos canales:

```bash
python - <<'PY'
import json
from pathlib import Path
src = Path("exports/sochic-meta.json")
items = json.loads(src.read_text(encoding="utf-8"))
ids = [str(item["id"]) for item in items if item.get("id")]
Path("exports/ya-publicados.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
PY

python -m services.meta_manifest --provider sochic --exclude-file exports/ya-publicados.txt --output exports/sochic-meta-nuevos.json --dry-run
```

Esas líneas peladas significan Page e IG. Si el JSON se publicó solo en la página, escribí `id:page` en cada línea (o pasá el JSON solo en una ola con `--channel page`). El mismo corte se puede hacer pasando el JSON anterior directo, sin el txt: cada `id` del array se lee como los dos canales.

```bash
python -m services.meta_manifest --provider sochic --exclude-file exports/sochic-meta.json --output exports/sochic-meta-nuevos.json --dry-run
```

Cuando el resumen cierra, sacar `--dry-run` para escribir el JSON (UTF-8, sin BOM). El archivo lleva títulos, precios y URLs del catálogo: no hace falta commitearlo. El comando no llama a Graph.

## Qué lleva cada ítem

Array JSON. Campos en snake_case:

| Campo | Contenido |
|-------|-----------|
| `id` | Slug estable: `{provider}-{product_id}` si hay proveedor (`sochic-300`). Si no, `{categoría}-{product_id}` (`denim-292`). Si no hay ninguno, `producto-{id}`. |
| `title` | `item_title` sin un sufijo de proveedor al final (` - Sochic`, ` - So Chic`, ` - Las Locas`, ` - Nissie`, ` - HOLIC`). |
| `caption` y `message` | El mismo texto: título, precio `$28.500` (miles con punto), talles si hay, y una descripción corta si aporta. |
| `price` | Entero en pesos. Si la prenda está en sale, es el precio final de la tienda. |
| `images` | URLs `https://` solamente, la principal primero, máximo 10. `http://` y rutas locales no entran. |

Ejemplo:

```json
[
  {
    "id": "sochic-300",
    "title": "Campera friza",
    "caption": "Campera friza\n$28.500\nTalles: S, M\nFriza con cierre.",
    "message": "Campera friza\n$28.500\nTalles: S, M\nFriza con cierre.",
    "price": 28500,
    "images": [
      "https://cdn.example.com/campera-1.jpg"
    ]
  }
]
```

## Después del archivo

Pasar ese JSON a robotRZ (`meta_page_garments.py` / `meta_ig_garments.py`) como el manifiesto que esos scripts ya leen. El ritmo de Graph (esperas, reintentos, topes) no lo define este export.

Cuando robotRZ publica, anota `id:page` o `id:ig` en `tmp/ops-console/publicados.txt` (un id pelado si salieron los dos). Copiá esas líneas a `exports/ya-publicados.txt`, o apuntá `MARKET_OPS_EXCLUDE_FILE` a ese archivo. La próxima ola de DanieBOT con `--channel` salta solo el canal que ya está hecho.
