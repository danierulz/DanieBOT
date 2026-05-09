# Frontend y checkout por WhatsApp

## Stack UI

- **Templates:** Jinja2 (`templates/index.html`, `admin-panel.html`, `tiredimages.html`, etc.).
- **Estáticos:** `static/` (JS, CSS generado).
- **Tailwind:** configuración en `tailwind.config.js`; entrada en `static/src/input.css`. El CSS definitivo debe compilarse en el build (ajustar pipeline npm cuando `package.json` esté completo).
- **Estado actual:** UI hecha con rapidez; **mejora visual y responsive** es prioridad de roadmap.

## Catálogo

- Los productos se cargan vía `GET /api/productos` desde el HTML/JS.
- Cada tarjeta debe incluir al menos: `id`, `titulo`, `precio`, `imagen` (URL principal), y si está disponible `stock` en detalle.

## Carrito (`static/js/shoppingCart.js`)

**Comportamiento especificado:**

1. Estructura en memoria: array de objetos `{ ...producto, cantidad }`.
2. Operaciones: agregar (incrementa duplicados), cambiar cantidad, eliminar línea.
3. Persistencia opcional: `localStorage` clave `carrito_v1`.
4. Total mostrado en UI: **suma de `precio * cantidad` por línea** (coherente con el mensaje de WhatsApp).

**Checkout:**

- Función `confirmarPedido()` construye un texto multilínea y abre:
  - `https://wa.me/<NUMERO_NEGOCIO>?text=<encodeURIComponent(mensaje)>`
- El número de destino debe ser **configurable** (hoy hardcodeado en JS — mover a variable de entorno inyectada en plantilla o endpoint de config).

### Formato del mensaje WhatsApp (objetivo)

El mensaje que recibe el negocio debe permitir atender el pedido sin ambigüedad:

- Identificación de cada línea: nombre/título de prenda, **cantidad**, **precio unitario** o subtotal por línea.
- **Total general** al final.
- Opcional: notas, nombre o teléfono si el front los solicita más adelante.

**Nota de implementación:** en el código actual, el bucle de `confirmarPedido` lista precios por ítem y el “Total” usa una reducción que **debe alinearse** con cantidades (ver backlog: bug de total vs cantidad).

## Integración futura API pedidos

Cuando `POST /api/whatsapp/pedido` esté activo, el flujo puede ser:

1. Usuario confirma en web → backend crea `Order` y devuelve `mensaje` + `order_id`.
2. Front abre `wa.me` con el **mensaje oficial** generado por servidor (precios validados contra DB).

Esto reduce discrepancias entre lo que ve la cliente y lo que guarda el sistema.

## Accesibilidad y UX (deseable)

- Contraste y tamaños táctiles en botones del carrito.
- Estados vacíos claros (“Tu carrito está vacío”).
- Indicador de carga si el catálogo es lento.
