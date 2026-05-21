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

function agregarAlCarrito(producto) {
  if (!producto.variant_id) {
    if (typeof window.detailShowSizeWarning === 'function') {
      window.detailShowSizeWarning();
    } else {
      alert('Elegí un talle antes de agregar al carrito.');
    }
    return;
  }
  const precioUnit = Number(producto.precio_final ?? producto.precio) || 0;
  const precioOrig = Number(producto.precio_original ?? producto.precio) || precioUnit;
  const idx = carrito.findIndex(
    (x) => x.id === producto.id && x.variant_id === producto.variant_id
  );
  if (idx >= 0) {
    carrito[idx].cantidad += 1;
  } else {
    carrito.push({
      id: producto.id,
      titulo: producto.titulo,
      imagen: producto.imagen || (producto.imagenes && producto.imagenes[0] && producto.imagenes[0].url) || null,
      precio: precioUnit,
      precio_original: precioOrig,
      is_sale: !!producto.is_sale,
      descuento_porcentaje: producto.descuento_porcentaje || 0,
      variant_id: producto.variant_id,
      talle_label: producto.talle_label || producto.size_label || '',
      size_code: producto.size_code || '',
      modo_entrega: producto.modo_entrega || '',
      dias_encargo_estimados: producto.dias_encargo_estimados || null,
      cantidad: 1,
    });
  }
  persistCart();
  renderCarrito();
}

function persistCart() {
  try { localStorage.setItem('carrito_v1', JSON.stringify(carrito)); } catch (e) {}
}

function modoLabel(p) {
  if (p.modo_entrega === 'inmediato') return 'Retiro ya';
  if (p.modo_entrega === 'encargo') {
    return p.dias_encargo_estimados ? 'Encargo · ~' + p.dias_encargo_estimados + ' días' : 'Encargo';
  }
  return '';
}

function modoBadgeClass(p) {
  if (p.modo_entrega === 'inmediato') return 'bg-green-100 text-green-800';
  if (p.modo_entrega === 'encargo') return 'bg-amber-100 text-amber-800';
  return 'bg-gray-100 text-gray-700';
}

function renderCarrito() {
  const cont = document.getElementById('carrito-items');
  const btnConfirmar = document.getElementById('btn-confirmar');

  if (!carrito.length) {
    cont.innerHTML = '<p class="text-gray-500 p-4 text-sm">Tu carrito está vacío</p>';
    if (btnConfirmar) btnConfirmar.disabled = true;
  } else {
    cont.innerHTML = carrito.map((p, i) => {
      const talle = p.talle_label || p.size_label || '';
      const modo = modoLabel(p);
      const sub = (Number(p.precio) || 0) * (p.cantidad || 1);
      const subOrig = (Number(p.precio_original) || Number(p.precio) || 0) * (p.cantidad || 1);
      const showOrig = p.is_sale && subOrig > sub;
      const img = p.imagen || 'https://via.placeholder.com/120x160?text=%20';
      return `
        <div class="flex items-start gap-3 mb-4 pb-4 border-b border-gray-100">
          <div class="w-16 h-20 sm:w-20 sm:h-24 shrink-0 rounded-lg overflow-hidden bg-gray-50 border border-gray-100 flex items-center justify-center">
            <img src="${escapeAttr(img)}" alt="" class="w-full h-full object-contain">
          </div>
          <div class="min-w-0 flex-1">
            <div class="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">${escapeCartHtml(p.titulo)}</div>
            <div class="mt-1 flex flex-wrap gap-1">
              ${talle ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-700">Talle ${escapeCartHtml(talle)}</span>` : ''}
              ${modo ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${modoBadgeClass(p)}">${escapeCartHtml(modo)}</span>` : ''}
              ${p.is_sale ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-600 text-white">SALE${p.descuento_porcentaje ? ' -' + p.descuento_porcentaje + '%' : ''}</span>` : ''}
            </div>
            <div class="mt-1 text-xs text-gray-600">
              <span class="${p.is_sale ? 'text-green-700 font-semibold' : ''}">$${formatMoney(p.precio)} c/u</span>
              ${showOrig ? `<span class="ml-1 text-gray-400 line-through">$${formatMoney(p.precio_original)}</span>` : ''}
            </div>
            <div class="mt-2 flex items-center gap-2">
              <button type="button" onclick="cambiarCantidadIdx(${i}, -1)" class="w-8 h-8 inline-flex items-center justify-center bg-gray-100 rounded-full touch-manipulation">−</button>
              <span class="tabular-nums min-w-[1.5rem] text-center text-sm">${p.cantidad}</span>
              <button type="button" onclick="cambiarCantidadIdx(${i}, 1)" class="w-8 h-8 inline-flex items-center justify-center bg-gray-100 rounded-full touch-manipulation">+</button>
              <div class="ml-auto text-right">
                <div class="text-sm font-semibold tabular-nums ${p.is_sale ? 'text-green-700' : ''}">$${formatMoney(sub)}</div>
                ${showOrig ? `<div class="text-[11px] text-gray-400 line-through tabular-nums">$${formatMoney(subOrig)}</div>` : ''}
              </div>
              <button type="button" onclick="eliminarDelCarrito(${i})" class="ml-1 p-1.5 bg-red-50 hover:bg-red-100 rounded-full inline-flex" aria-label="Quitar">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5-4h4m-4 0a1 1 0 00-1 1v1h6V4a1 1 0 00-1-1m-4 0h4" /></svg>
              </button>
            </div>
          </div>
        </div>`;
    }).join('');
    if (btnConfirmar) btnConfirmar.disabled = false;
  }

  const count = document.getElementById('carrito-count');
  if (count) count.textContent = carrito.reduce((a, p) => a + (p.cantidad || 0), 0);

  const total = carrito.reduce((acc, p) => acc + (Number(p.precio) || 0) * (p.cantidad || 1), 0);
  const totalOrig = carrito.reduce((acc, p) => acc + (Number(p.precio_original) || Number(p.precio) || 0) * (p.cantidad || 1), 0);
  const ahorro = Math.max(0, totalOrig - total);
  const totalEl = document.getElementById('carrito-total');
  if (totalEl) totalEl.textContent = formatMoney(total);
  const savBox = document.getElementById('carrito-savings');
  const savAmt = document.getElementById('carrito-savings-amount');
  if (savBox && savAmt) {
    if (ahorro > 0) { savBox.classList.remove('hidden'); savAmt.textContent = formatMoney(ahorro); }
    else { savBox.classList.add('hidden'); }
  }
}

function escapeCartHtml(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
function escapeAttr(s) {
  return String(s == null ? '' : s).replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function formatMoney(n) {
  return new Intl.NumberFormat('es-AR', { maximumFractionDigits: 0 }).format(Number(n) || 0);
}

function cambiarCantidadIdx(index, delta) {
  if (!carrito[index]) return;
  carrito[index].cantidad = Math.max(1, (carrito[index].cantidad || 1) + delta);
  persistCart();
  renderCarrito();
}

function eliminarDelCarrito(index) {
  carrito.splice(index, 1);
  persistCart();
  renderCarrito();
}

async function confirmarPedido() {
  if (!carrito.length) return;
  const btn = document.getElementById('btn-confirmar');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Preparando pedido…';
  }

  const payload = {
    items: carrito.map((p) => ({
      id: p.id,
      titulo: p.titulo,
      precio: Number(p.precio) || 0,
      cantidad: p.cantidad || 1,
      variant_id: p.variant_id || null,
    })),
    cart_snapshot: carrito,
  };

  try {
    const res = await fetch('/api/whatsapp/pedido', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || 'No se pudo registrar el pedido. Intentá de nuevo.');
      return;
    }
    const numero =
      data.whatsapp_number ||
      (typeof CHECKOUT_WHATSAPP_NUMBER !== 'undefined' ? CHECKOUT_WHATSAPP_NUMBER : '');
    const mensaje = data.mensaje || '';
    if (!numero || !mensaje) {
      alert('Pedido registrado pero falta configuración de WhatsApp.');
      return;
    }
    window.open(`https://wa.me/${numero}?text=${encodeURIComponent(mensaje)}`, '_blank');
  } catch (e) {
    alert('Error de conexión. Revisá tu internet e intentá de nuevo.');
  } finally {
    if (btn) {
      btn.disabled = !carrito.length;
      btn.textContent = btn.dataset.label || 'Confirmar y enviar por WhatsApp';
    }
  }
}

window.addEventListener('load', () => {
  const saved = localStorage.getItem('carrito_v1');
  if (saved) {
    try { carrito = JSON.parse(saved) || []; renderCarrito(); }
    catch (e) { carrito = []; }
  } else {
    renderCarrito();
  }
});
window.addEventListener('beforeunload', persistCart);
