# Colores en catálogo y checkout

## Objetivo

Permitir que la administradora defina **qué colores** ofrece cada prenda, que la clienta **elija color** en el detalle (junto con el talle) y que el **color figure en el pedido**, en el mensaje de WhatsApp y en el panel de pedidos — con los mismos datos en todos lados.

## Modelo de datos

| Tabla / campo | Rol |
|---------------|-----|
| `colors` | Catálogo global (`code`, `label`, `sort_order`, `hex` opcional) |
| `product_colors` | Colores habilitados por producto (`product_id`, `color_id`, `activo`) |
| `order_items.color_id` | Color elegido (FK) |
| `order_items.color_label_snapshot` | Texto histórico en el pedido |
| `order_items.size_label_snapshot` | Talle histórico (complementa `variant_id`) |

El stock y el encargo siguen en `product_variants` (solo por **talle**). No hay stock por color en v1.

## API

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/colors` | Público | Lista de colores |
| POST | `/api/admin/colors` | Admin JWT | Alta de color (`label`, `hex` opcional). Si el código ya existe, devuelve el existente |
| GET | `/api/producto/{id}` | Público / admin | Incluye `colores[]` |
| POST/PUT | `/api/productos` | Admin | Form field `colors_json`: array de `color_id` |
| POST | `/api/whatsapp/pedido` | Público | `items[].color_id` obligatorio si el producto tiene colores |

## Flujo administración

1. Cargar checkboxes desde `GET /api/colors`.
2. Marcar colores del producto al guardar.
3. Si falta un color: campo «Color nuevo» + **Agregar color** → `POST /api/admin/colors` → se agrega al catálogo y queda disponible para marcar.

Import So Chic: los nombres scrapeados se mapean a colores del catálogo (creando filas si no existen) y se pre-asignan al producto importado.

## Flujo tienda

1. Detalle: chips de talle (como antes) + chips de color si `colores.length > 0`.
2. Un solo color disponible: se preselecciona.
3. Carrito: badges «Talle …» y «Color …».
4. Checkout: `color_id` en cada ítem; servidor valida y guarda snapshots.

## Mensaje WhatsApp (formato de línea)

```text
1. Jean wide — Talle M — Color Celeste — $45.000 ($45.000 x 1)
```

Si el producto no tiene colores configurados, se omite el segmento de color.

## Criterios de aceptación

- Admin: marcar colores y crear colores nuevos desde el panel.
- Tienda: no agregar al carrito sin color cuando el producto lo exige.
- Pedido: `order_items` con `color_id` y snapshots.
- WhatsApp y panel admin pedidos muestran talle y color por línea.
- Productos sin `product_colors` se comportan como antes.

## Fuera de alcance v1

- Stock por color.
- Variante `(talle × color)` en `product_variants`.
- Filtro de catálogo por color en URL.
- Elección de color en el bot WhatsApp (solo web).
