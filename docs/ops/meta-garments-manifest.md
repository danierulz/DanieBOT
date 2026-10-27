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
```

`--exclude-id` se puede repetir (o separar por comas). Acepta el slug del manifiesto (`sochic-300`, `denim-292`), el `product_id` o el `cod_product`. `--exclude-file` es la misma lista en un archivo: un id por línea (`#` comenta), comas, o un array JSON.

Cuando el resumen cierra, sacar `--dry-run` para escribir el JSON (UTF-8, sin BOM). El archivo lleva títulos, precios y URLs del catálogo: no hace falta commitearlo.

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
