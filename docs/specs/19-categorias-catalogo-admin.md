# Categorías — catálogo admin unificado

> **Referencia viva.** Consultar antes de tocar categorías en admin, menú web, filtros `?cat=` o bot WhatsApp.

## Resumen en una frase

Las categorías viven en la tabla `categories`; admin, menú web y WhatsApp leen categorías **activas** desde la DB vía [`services/categories.py`](../../services/categories.py). Colores, talles y categorías se gestionan en una sola pestaña **Catálogo** del panel admin.

---

## Modelo `categories`

| Campo | Uso |
|-------|-----|
| `slug` | Identificador URL (`/?cat=jeans`). **Inmutable** tras crear. |
| `name` | Etiqueta visible en menú, admin y WhatsApp. |
| `sort_order` | Orden en nav, WhatsApp y listados admin. |
| `size_group` | `letter` \| `numeric` — qué talles ofrece la categoría (ver spec 16). |
| `activo` | `false` oculta del menú, WhatsApp y select de productos; productos existentes conservan FK. |

---

## Reglas de negocio

1. **Slug inmutable** al editar (como `code` de talles/colores).
2. **Eliminar** bloqueado si hay productos en la categoría (HTTP 409); preferir desactivar.
3. **Slug duplicado** al crear → HTTP 409.
4. **`activo=false`**: no aparece en `GET /api/categories`, nav web ni flujo WhatsApp.

---

## Fuente de verdad en código

| Qué | Dónde |
|-----|-------|
| Lógica categorías | [`services/categories.py`](../../services/categories.py) |
| API HTTP | [`main.py`](../../main.py) — `/api/categories`, `/api/admin/categories` |
| Nav web | `page_context()` → `list_categories_for_nav` + `build_nav_links()` |
| Admin UI | [`templates/partials/admin_catalog_tab.html`](../../templates/partials/admin_catalog_tab.html), [`static/js/adminCategoryCatalog.js`](../../static/js/adminCategoryCatalog.js) |
| WhatsApp | [`whatsapp/handlers.py`](../../whatsapp/handlers.py) → `_shop_categories_resolver()` |
| Fallback tests | `get_catalog_categories()` en [`config.py`](../../config.py) |

### Qué ya NO usar

- ~~`_NAV_CATEGORIES` en `config.py`~~ — eliminado
- ~~Editar `config.py` para agregar categoría al menú~~ — usar admin Catálogo → Categorías

Endpoints deprecated (compatibilidad): `GET/PUT /api/admin/categories/size-groups` — usar CRUD de categorías.

---

## API admin

| Método | Ruta | Body |
|--------|------|------|
| GET | `/api/admin/categories` | Lista completa (incluye inactivas + `product_count`) |
| POST | `/api/admin/categories` | `{ name, slug?, size_group?, sort_order?, activo? }` |
| PUT | `/api/admin/categories/{id}` | `{ name?, size_group?, sort_order?, activo? }` |
| DELETE | `/api/admin/categories/{id}` | Bloqueo si hay productos |

Público: `GET /api/categories` — solo activas, ordenadas.

---

## Pestaña Catálogo unificada

Ruta: `/admin-panel?tab=catalog`

Sub-secciones (misma pestaña):

| Sección | Hash | Contenido |
|---------|------|-----------|
| Categorías | `#categorias` | CRUD categorías + tipo de talle |
| Talles | `#talles` | Catálogo de talles (`size_group` por fila) |
| Colores | `#colores` | Catálogo de colores |

Compatibilidad: `?tab=colors` → `?tab=catalog#colores`; `?tab=sizes` → `?tab=catalog#talles`.

Links «Gestionar colores/talles →» en formulario producto apuntan a `#colores` / `#talles`.

---

## Checklist al agregar categoría

- [ ] Crear en admin **Catálogo → Categorías** (nombre, slug, tipo de talle, orden).
- [ ] Verificar menú web y bot WhatsApp (categoría activa).
- [ ] Asignar productos desde Nuevo producto / Editar.
- [ ] **No** editar `config.py` para el dropdown Productos.

Tests:

```bash
python -m unittest tests.test_categories_admin tests.test_sizes_admin tests.test_shop_flow -v
```

Ver también: [`16-talles-catalogo-y-whatsapp.md`](16-talles-catalogo-y-whatsapp.md), [`13-colores-catalogo-y-checkout.md`](13-colores-catalogo-y-checkout.md).
