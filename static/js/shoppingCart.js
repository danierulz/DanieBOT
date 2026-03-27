let carrito = [];
console.log("shoppingCart.js cargado, carrito inicial:", carrito);
function toggleCarrito() {
  const panel = document.getElementById('carrito-panel');
  if (panel.classList.contains('translate-x-full')) {
    panel.classList.remove('translate-x-full');
    panel.classList.add('translate-x-0');
  } else {
    panel.classList.remove('translate-x-0');
    panel.classList.add('translate-x-full');
  }
}

function agregarAlCarrito(producto) {
  const idx = carrito.findIndex(x => x.id === producto.id);
  if (idx >= 0) carrito[idx].cantidad += 1;
  else carrito.push({ ...producto, cantidad: 1 });
  renderCarrito();
}

function renderCarrito() {
  const cont = document.getElementById('carrito-items');
  const btnConfirmar = document.getElementById('btn-confirmar');


  if (carrito.length === 0) {
    cont.innerHTML = '<p class="text-gray-500 p-4">Tu carrito está vacío</p>';
  } else {
    cont.innerHTML = carrito.map((p, i) => `
          <div class="flex items-center justify-between mb-3">
            <div>
              <div class="font-semibold">${p.titulo}</div>
              <div class="text-xs text-gray-500">Unit: $${p.precio}</div>
              <div class="text-xs text-gray-500">Stock: ${p.stock ?? 'N/D'}</div>
            </div>
            <div class="text-right">
              <div class="flex items-center gap-2">
                <button onclick="cambiarCantidad(${p.id}, -1)" class="px-2 py-1 bg-gray-100 rounded">-</button>
                <span>${p.cantidad}</span>
                <button onclick="cambiarCantidad(${p.id}, 1)" class="px-2 py-1 bg-gray-100 rounded">+</button>
              </div>
              <div class="mt-2 font-semibold">$${p.precio * p.cantidad}</div>
            </div>
   <button onclick="eliminarDelCarrito(${i})" 
        class="p-2 bg-red-100 rounded hover:bg-red-200">
  <svg xmlns="http://www.w3.org/2000/svg" 
       class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5-4h4m-4 0a1 1 0 00-1 1v1h6V4a1 1 0 00-1-1m-4 0h4" />
  </svg>
</button>       </div>
        `).join('');
            if (btnConfirmar) btnConfirmar.disabled = false;

  }
 
  // Actualizar contador y total
  const count = document.getElementById('carrito-count');
  if (count) count.textContent = carrito.length;

  const total = carrito.reduce((acc, p) => acc + p.precio * p.cantidad, 0);
  const totalEl = document.getElementById('carrito-total');
  if (totalEl) totalEl.textContent = total;
}

function cambiarCantidad(id, delta) {
  const idx = carrito.findIndex(x => x.id === id);
  if (idx < 0) return;
  carrito[idx].cantidad = Math.max(1, carrito[idx].cantidad + delta);
  renderCarrito();
}

function eliminarDelCarrito(index) {
  carrito.splice(index, 1); // elimina el producto en esa posición
  localStorage.setItem('carrito_v1', JSON.stringify(carrito));
  renderCarrito();
}

function confirmarPedido() {
  // Tomar datos del carrito
  let mensaje = "🛒 Pedido:\n";
  carrito.forEach((p, i) => {
    mensaje += `${i + 1}. ${p.titulo} - $${p.precio}\n`;
  });

  // Total
  const total = carrito.reduce((acc, p) => acc + p.precio, 0);
  mensaje += `\nTotal: $${total}\n`;

  // Datos del cliente
  //  const nombre = document.getElementById("customer_name").value;
  // const telefono = document.getElementById("customer_phone").value;
  //const nota = document.getElementById("order_note").value;

  //  if (nombre) mensaje += `\nCliente: ${nombre}`;
  // if (telefono) mensaje += `\nTel: ${telefono}`;
  //if (nota) mensaje += `\nNota: ${nota}`;

  // Codificar mensaje para URL
  const mensajeCodificado = encodeURIComponent(mensaje);

  // Número de destino (ejemplo: tu número de WhatsApp)
  const numeroDestino = "5491125298412"; // <-- reemplazá con tu número real

  // Abrir WhatsApp Web
  window.open(`https://wa.me/${numeroDestino}?text=${mensajeCodificado}`, "_blank");
}
// Inicializar carrito desde localStorage (opcional)
window.addEventListener('load', () => {
  const saved = localStorage.getItem('carrito_v1');
  if (saved) {
    try { carrito = JSON.parse(saved); renderCarrito(); } catch (e) { carrito = []; }
  }
});
window.addEventListener('beforeunload', () => {
  localStorage.setItem('carrito_v1', JSON.stringify(carrito));
});
