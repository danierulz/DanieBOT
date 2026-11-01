# HOLIC: New In (novedades)

Fuente preferida para detectar **novedades** de HOLIC sin recorrer toda la tienda.

## Endpoint / URL

- Categoria WooCommerce: [https://holiclothing.com.ar/product-category/new-in/](https://holiclothing.com.ar/product-category/new-in/)
- Es el listado **New In**: fichas que el proveedor marca como ingreso reciente.
- Cada card apunta a https://holiclothing.com.ar/product/<slug>/ (mismo formato que el import HOLIC).

No es un webhook: es una **pagina de catalogo** publica. No requiere login.

## Como usarlo en DanieBOT

1. **Hoy (documentado como fuente canonica):** al mirar novedades de HOLIC, preferir esta URL frente al catalogo general /tienda/.
2. **Pestana admin** /admin-panel?tab=watch: HOLIC (opcional en el UI) deberia leerse desde **new-in** (ver [novedades-proveedores.md](./novedades-proveedores.md)). Si el codigo todavia usa HOLIC_CATALOG_URL (/tienda/), el objetivo es migrar esa lectura a esta URL.
3. Las Locas usan [nuevos-ingresos](./laslocas-nuevos-ingresos.md); Nissie y So Chic siguen con su listado de tienda.

## Ritmo y limites

- Una sola pagina de listado por pasada (tope 5-10 en el watch).
- No agendar en Cloud Scheduler / Cloud Run.
- Si el sitio limita requests (429), pausar y reintentar (ver [scraping-cuidados.md](./scraping-cuidados.md)).
