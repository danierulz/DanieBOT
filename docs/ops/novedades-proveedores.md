# Novedades de proveedores (solo la PC)

Mirá si Las Locas, Nissie o So Chic publicaron fichas nuevas, sin bajar el catálogo y sin publicar a Meta.

La política de no agendar el scrape está en el [spec 17](../specs/17-scraping-masivo-proveedores.md). Los comandos largos siguen en el [spec 23](../specs/23-bulk-import-notebook.md). Pausas y 429: [scraping-cuidados.md](./scraping-cuidados.md).

## Cómo abrirlo

Con la app corriendo en la laptop (por ejemplo `http://localhost:5000`):

1. Entrá al admin e iniciá sesión.
2. Abrí **Novedades proveedores**, o directo `/admin-panel?tab=watch`.
3. Al abrir la pestaña se lee **una** página de listado por proveedor. El botón **Buscar novedades** repite esa lectura.

No hace falta Cloud Scheduler, Cloud Run Job ni un cron. Si el admin está servido por Cloud Run, la consulta responde que solo corre en la PC.


## Las Locas: de dónde salen

Las Locas **no** se priorizan por categoría denim suelta para novedades. La fuente a usar es el listado **Nuevos ingresos**:

- URL: https://laslocas.com/nuevos-ingresos/
- Detalle operativo: [laslocas-nuevos-ingresos.md](./laslocas-nuevos-ingresos.md)

Ahí aparecen las fichas que el proveedor marca como ingreso reciente. Nissie y So Chic siguen con su listado de tienda (/productos/, /shop/).

## Qué muestra

| Control | Efecto |
|---------|--------|
| Proveedores | Las Locas, Nissie y So Chic vienen marcados. HOLIC es opcional. |
| Máximo | 5 (default) o 10 fichas de la **primera** página. No sigue paginando. |
| Las Locas | Listado [nuevos-ingresos](https://laslocas.com/nuevos-ingresos/) (ver [laslocas-nuevos-ingresos.md](./laslocas-nuevos-ingresos.md)). No recorre todas las categorías. |

Cada fila trae proveedor, título, URL, precio si el listado lo trae, y estado:

- **nuevo** — la URL no está en `products.provider_source_url` ni en una corrida `created`/`skipped` cuyo `cod_product` sigue existiendo, y el código visible del listado tampoco está en `products.cod_product`.
- **posible duplicado** — coincide alguna de esas claves (las mismas que `--skip-existing`).

Las Locas necesita `LOGIN_EMAIL` y `LOGIN_PASS` en el `.env` local. La pantalla lista los nombres de las variables si faltan y **no muestra los valores**.

So Chic espera al menos 5 segundos entre proveedores (`default_delay_ms` de `brands.json`). La búsqueda lee solo el listado: no pide la ficha de cada producto. Un 429 en ese listado frena esa marca, avisa cuántos minutos esperar y no sigue con fichas. Si igual importás filas marcadas y So Chic responde 429, se corta ahí: las que faltaban no se piden.

## Qué no hace

- No importa el catálogo al abrir la pestaña.
- No publica a Meta.
- No agenda nada.
- No activa productos.

**Importar seleccionados** es opcional: manda de a una las filas **nuevo** a `POST /api/proveedores/importar` con `status: false` (quedan inactivas) y espera la pausa del proveedor entre una y otra. **Copiar URLs nuevas** y el comando `--dry-run` de abajo sirven si preferís el CLI.

## Uso diario

Una vez por día, en la PC: abrí la pestaña, mirá las filas **nuevo** y, si hace falta, importá unas pocas o corré el dry-run que muestra la pantalla antes de una corrida que escribe.
