# Las Locas: nuevos ingresos

Fuente preferida para detectar **novedades** de Las Locas (sin recorrer todas las categorias).

## Endpoint / URL

- Pagina de listado: [https://laslocas.com/nuevos-ingresos/](https://laslocas.com/nuevos-ingresos/)
- Es el listado de tienda (Tienda Nube) etiquetado **NUEVOS INGRESOS**: fichas nuevas o destacadas como ingreso reciente.
- Cada card apunta a una URL de producto tipo https://laslocas.com/productos/<slug>/ (mismo formato que el watch actual).

No es un webhook ni una API autenticada con token propio: es una **pagina de catalogo** publica (precios mayoristas suelen exigir sesion). Para scrape/watch hace falta la misma sesion mayorista que el resto de Locas.

## Credenciales

Solo en la laptop (nombres de variables; no pegar valores en chat ni en git):

- LOGIN_EMAIL
- LOGIN_PASS

Mismas que el bulk y la pestana **Novedades proveedores**.

## Como usarlo en DanieBOT

1. **Hoy (documentado como fuente canonica):** al mirar novedades de Las Locas, preferir esta URL frente a categorias sueltas (/productos/jean, etc.).
2. **Pestana admin** /admin-panel?tab=watch: Las Locas debe leerse desde **nuevos-ingresos** (ver [novedades-proveedores.md](./novedades-proveedores.md)). Si el codigo todavia usa una categoria default (p. ej. denim), el objetivo es migrar esa lectura a esta URL.
3. **Import:** las URLs /productos/... se clasifican en el watch; el import por ficha legacy /ficha-... puede seguir siendo un follow-up aparte.

## Ritmo y limites

- Una sola pagina de listado por pasada (mismo espiritu que el watch: tope 5-10).
- No agendar en Cloud Scheduler / Cloud Run.
- Si el sitio limita requests, pausar y reintentar mas tarde (misma politica que [scraping-cuidados.md](./scraping-cuidados.md)).

## Relacion con Instagram / avisos

Las Locas tambien anuncia ingresos en redes (#NUEVOINGRESO). Eso no reemplaza este listado web para el watch local.
