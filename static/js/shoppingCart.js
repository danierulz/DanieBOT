let carrito = [];
console.log("shoppingCart.js cargado, carrito inicial:", carrito);
function toggleCarrito() {
  const panel = document.getElementById('carrito-panel');
  panel.style.right = panel.style.right === '0px' ? '-100%' : '0px';
}

function agregarAlCarrito(producto) {
  const idx = carrito.findIndex(x => x.id === producto.id);
  if (idx >= 0) carrito[idx].cantidad += 1;
  else carrito.push({ ...producto, cantidad: 1 });
  renderCarrito();
}

function renderCarrito() {
  const cont = document.getElementById('carrito-items');
  if (carrito.length === 0) {
    cont.innerHTML = '<p class="text-gray-500 p-4">Tu carrito está vacío</p>';
  } else {
    cont.innerHTML = carrito.map(p => `
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
          </div>
        `).join('');
  }
  const total = carrito.reduce((s, i) => s + (i.precio * i.cantidad), 0);
  document.getElementById('carrito-total').textContent = total.toFixed(2);
  document.getElementById('carrito-count').textContent = carrito.reduce((s, i) => s + i.cantidad, 0);
}

function cambiarCantidad(id, delta) {
  const idx = carrito.findIndex(x => x.id === id);
  if (idx < 0) return;
  carrito[idx].cantidad = Math.max(1, carrito[idx].cantidad + delta);
  renderCarrito();
}

function confirmarPedido() {
  // Tomar datos del carrito
  let mensaje = "🛒 Pedido:\n";
  carrito.forEach((p, i) => {
    mensaje += `${i+1}. ${p.titulo} - $${p.precio}\n`;
  });

  // Total
  const total = carrito.reduce((acc, p) => acc + p.precio, 0);
  mensaje += `\nTotal: $${total}\n`;

  // Datos del cliente
  const nombre = document.getElementById("customer_name").value;
  const telefono = document.getElementById("customer_phone").value;
  const nota = document.getElementById("order_note").value;

  if (nombre) mensaje += `\nCliente: ${nombre}`;
  if (telefono) mensaje += `\nTel: ${telefono}`;
  if (nota) mensaje += `\nNota: ${nota}`;

  // Codificar mensaje para URL
  const mensajeCodificado = encodeURIComponent(mensaje);

  // Número de destino (ejemplo: tu número de WhatsApp)
  const numeroDestino = "5491160267215"; // <-- reemplazá con tu número real

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
