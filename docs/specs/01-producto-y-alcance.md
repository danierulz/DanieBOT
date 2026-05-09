# Producto y alcance

## Visión

**DanieBOT** es una aplicación que combina:

- Una **vitrina web** de indumentaria femenina (jeans y otras prendas), donde la cliente arma un **carrito simple**.
- Un cierre de compra que **derivará el pedido a WhatsApp**: la usuaria envía el **resumen del pedido** (cantidades, precios, descripción por ítem, total) al número del negocio.
- Un **bot en WhatsApp** integrado con **Meta Cloud API**, implementado con **PyWa** sobre **FastAPI**, desplegado en **Google Cloud Run**, para recibir y responder mensajes (hoy con respuestas automáticas básicas; evolución prevista según roadmap).

Los datos de catálogo (fotos, precios) se obtienen mediante **scraping** del sitio de referencia comercial (“Las Locas”) y se persisten en **PostgreSQL** vía **SQLAlchemy**. Las imágenes pueden almacenarse en **Google Cloud Storage**.

## Objetivos de negocio

1. Mostrar catálogo actualizado de ropa de mujer con buena experiencia visual (mejora continua del front con **Tailwind**).
2. Permitir armar carrito sin fricción excesiva (cantidades, líneas, total coherente).
3. Canalizar el cierre de compra por **WhatsApp**, donde el negocio ya opera con clientes.
4. Mantener inventario y pedidos alineados con la base de datos cuando se implementen flujos servidor ↔ WhatsApp completos.

## Usuarios / actores

| Actor | Rol |
|-------|-----|
| **Cliente (web)** | Navega catálogo, suma prendas al carrito, confirma y abre WhatsApp con mensaje prearmado. |
| **Cliente (WhatsApp)** | Envía mensajes al número del negocio; el bot responde (catálogo, asesor, etc., según implementación). |
| **Administrador** | Gestiona productos (UI admin existente / futura), posiblemente dispara scraper o revisa pedidos. |
| **Sistema** | FastAPI, PostgreSQL, GCS, Meta API, jobs de scraping. |

## Alcance actual (implícito en el código)

- Servidor **FastAPI** único: API REST, plantillas Jinja, estáticos, webhook WhatsApp.
- Catálogo servido desde PostgreSQL; creación manual de productos e imágenes vía API/formulario y subida a GCS.
- Scraping con **Selenium** y **BeautifulSoup** como pipeline de ingesta hacia la base (complementario al admin).

## Fuera de alcance (por ahora)

- Pasarela de pago online obligatoria (el cobro se coordina fuera o por WhatsApp).
- App móvil nativa.
- Multi-tenant o varias marcas en una sola instancia (salvo que se defina explícitamente después).

## Glosario

| Término | Significado |
|---------|-------------|
| **Las Locas** | Sitio origen del scraping de referencia para fotos/precios. |
| **PyWa** | Librería Python para WhatsApp Cloud API sobre FastAPI. |
| **Carrito** | Lista en memoria del navegador (y opcionalmente `localStorage`) hasta confirmar. |
