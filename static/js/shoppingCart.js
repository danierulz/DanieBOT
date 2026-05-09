let carrito = [];

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

function lineKeyLinea(linea) {
  const vid = linea.variant_id != null ? String(linea.variant_id) : '';
  return String(linea.id) + '_' + vid;
}

function agregarAlCarrito(producto) {
  if (!producto.variant_id) {
    if (typeof window.detailShowSizeWarning === 'function') {
      window.detailShowSizeWarning();
    } else {
      alert('Elegí un talle antes de agregar al carrito.');
    }
    return;
  }
  const idx = carrito.findIndex(
    (x) => x.id === producto.id && x.variant_id === producto.variant_id
  );
  if (idx >= 0) carrito[idx].cantidad += 1;
  else carrito.push({ ...producto, cantidad: 1 });
  renderCarrito();
}

function renderCarrito() {
  const cont = document.getElementById('carrito-items');
  const btnConfirmar = document.getElementById('btn-confirmar');

  if (carrito.length === 0) {
    cont.innerHTML = '<p class="text-gray-500 p-4">Tu carrito está vacío</p>';
    if (btnConfirmar) btnConfirmar.disabled = true;
  } else {
    cont.innerHTML = carrito.map((p, i) => {
      const talle =
        p.talle_label || p.size_label || (p.variant_id ? 'Talle' : '');
      const modo =
        p.modo_entrega === 'inmediato'
          ? 'Retiro ya'
          : p.modo_entrega === 'encargo'
            ? 'Encargo'
            : '';
      const sub = (Number(p.precio) || 0) * (p.cantidad || 1);
      return `
          <div class="flex items-start justify-between gap-2 mb-4 pb-4 border-b border-gray-100">
            <div class="min-w-0 flex-1">
              <div class="font-semibold text-gray-900">${escapeCartHtml(p.titulo)}</div>
              <div class="text-xs text-gray-600 mt-1">${escapeCartHtml(talle)}${modo ? ' · ' + escapeCartHtml(modo) : ''}</div>
              <div class="text-xs text-gray-500 mt-0.5">$${formatMoney(p.precio)} c/u</div>
            </div>
            <div class="text-right shrink-0">
              <div class="flex items-center gap-2 justify-end">
                <button type="button" onclick="cambiarCantidad(${p.id}, ${p.variant_id != null ? p.variant_id : 'null'}, -1)" class="px-2 py-1 bg-gray-100 rounded touch-manipulation">-</button>
                <span class="tabular-nums min-w-[1.5rem] text-center">${p.cantidad}</span>
                <button type="button" onclick="cambiarCantidad(${p.id}, ${p.variant_id != null ? p.variant_id : 'null'}, 1)" class="px-2 py-1 bg-gray-100 rounded touch-manipulation">+</button>
              </div>
              <div class="mt-2 font-semibold tabular-nums">$${formatMoney(sub)}</div>
              <button type="button" onclick="eliminarDelCarrito(${i})" class="mt-2 p-2 bg-red-100 rounded hover:bg-red-200 inline-flex" aria-label="Quitar">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5-4h4m-4 0a1 1 0 00-1 1v1h6V4a1 1 0 00-1-1m-4 0h4" /></svg>
              </button>
            </div>
          </div>`;
    }).join('');
    if (btnConfirmar) btnConfirmar.disabled = false;
  }

  const count = document.getElementById('carrito-count');
  if (count) count.textContent = carrito.reduce((a, p) => a + (p.cantidad || 0), 0);

  const total = carrito.reduce(
    (acc, p) => acc + (Number(p.precio) || 0) * (p.cantidad || 1),
    0
  );
  const totalEl = document.getElementById('carrito-total');
  if (totalEl) totalEl.textContent = formatMoney(total);
}

function escapeCartHtml(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

function formatMoney(n) {
  return new Intl.NumberFormat('es-AR', { maximumFractionDigits: 0 }).format(
    Number(n) || 0
  );
}

function cambiarCantidad(id, variantId, delta) {
  const idx = carrito.findIndex(
    (x) =>
      x.id === id &&
      (variantId == null ? x.variant_id == null : x.variant_id === variantId)
  );
  if (idx < 0) return;
  carrito[idx].cantidad = Math.max(1, carrito[idx].cantidad + delta);
  renderCarrito();
}

function eliminarDelCarrito(index) {
  carrito.splice(index, 1);
  localStorage.setItem('carrito_v1', JSON.stringify(carrito));
  renderCarrito();
}

function confirmarPedido() {
  let mensaje = '🛒 Pedido:\n';
  carrito.forEach((p, i) => {
    const talle = p.talle_label || p.size_label || '';
    const modo =
      p.modo_entrega === 'inmediato'
        ? 'Retiro ya'
        : p.modo_entrega === 'encargo'
          ? 'Encargo'
          : '';
    mensaje += `${i + 1}. ${p.titulo}`;
    if (talle) mensaje += ` — Talle: ${talle}`;
    if (modo) mensaje += ` (${modo})`;
    mensaje += ` — $${formatMoney(p.precio)} x ${p.cantidad}\n`;
  });

  const total = carrito.reduce(
    (acc, p) => acc + (Number(p.precio) || 0) * (p.cantidad || 1),
    0
  );
  mensaje += `\nTotal: $${formatMoney(total)}\n`;

  const mensajeCodificado = encodeURIComponent(mensaje);
  const numeroDestino = '5491125298412';

  window.open(`https://wa.me/${numeroDestino}?text=${mensajeCodificado}`, '_blank');
}

window.addEventListener('load', () => {
  const saved = localStorage.getItem('carrito_v1');
  if (saved) {
    try {
      carrito = JSON.parse(saved);
      renderCarrito();
    } catch (e) {
      carrito = [];
    }
  }
});
window.addEventListener('beforeunload', () => {
  localStorage.setItem('carrito_v1', JSON.stringify(carrito));
});
