(function () {
  let catalogColors = [];
  let selectedIds = new Set();
  let addButtonBound = false;
  const DEFAULT_HEX = '#2563EB';

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function normalizeHex(value) {
    const raw = (value || '').trim();
    if (!raw) return null;
    const withHash = raw.startsWith('#') ? raw : '#' + raw;
    return /^#[0-9A-Fa-f]{6}$/.test(withHash) ? withHash.toUpperCase() : null;
  }

  function syncColorPicker(hex) {
    const input = document.getElementById('new-color-hex');
    const preview = document.getElementById('new-color-preview');
    const clean = normalizeHex(hex) || DEFAULT_HEX;
    if (input) input.value = clean;
    if (preview) preview.style.background = clean;
  }

  function bindColorPickerUi() {
    const input = document.getElementById('new-color-hex');
    if (input && !input.dataset.bound) {
      input.dataset.bound = '1';
      input.addEventListener('input', () => syncColorPicker(input.value));
    }

    document.querySelectorAll('.color-preset-btn').forEach((btn) => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', () => {
        syncColorPicker(btn.getAttribute('data-hex'));
      });
    });

    syncColorPicker(input ? input.value : DEFAULT_HEX);
  }

  function showColorError(message) {
    if (typeof showToast === 'function') {
      showToast(message, { type: 'error' });
      return;
    }
    const msg = document.getElementById('msg');
    if (msg) msg.textContent = message;
  }

  function renderCheckboxes() {
    const picker = document.getElementById('product-colors-picker');
    if (!picker) return;

    if (!catalogColors.length) {
      const emptyMsg =
        (typeof COLOR_LABELS !== 'undefined' && COLOR_LABELS.empty) ||
        'Todavía no hay colores en el catálogo.';
      picker.innerHTML = `<p class="text-xs text-gray-500">${escapeHtml(emptyMsg)}</p>`;
      return;
    }

    picker.innerHTML = catalogColors
      .map(
        (c) => `
      <label class="inline-flex items-center gap-2 mr-3 mb-2 text-sm cursor-pointer">
        <input type="checkbox" class="pc-color-cb w-4 h-4 accent-black" value="${c.color_id}" ${
          selectedIds.has(c.color_id) ? 'checked' : ''
        }>
        <span class="inline-flex items-center gap-1.5">
          <span class="w-4 h-4 rounded-full border border-gray-300 shrink-0" style="background:${escapeHtml(
            c.hex || '#888888'
          )}"></span>
          ${escapeHtml(c.label)}
        </span>
      </label>`
      )
      .join('');

    picker.querySelectorAll('.pc-color-cb').forEach((cb) => {
      cb.addEventListener('change', () => {
        const id = parseInt(cb.value, 10);
        if (cb.checked) selectedIds.add(id);
        else selectedIds.delete(id);
      });
    });
  }

  async function loadCatalog() {
    const r = await fetch('/api/colors');
    if (!r.ok) throw new Error('load fail');
    catalogColors = await r.json();
    renderCheckboxes();
  }

  function bindAddColorButton() {
    if (addButtonBound) return;
    const btn = document.getElementById('btn-add-color');
    if (!btn) return;
    addButtonBound = true;

    btn.addEventListener('click', async () => {
      const labelInput = document.getElementById('new-color-label');
      const hexInput = document.getElementById('new-color-hex');
      const label = labelInput && labelInput.value.trim();
      const hex = normalizeHex(hexInput && hexInput.value);
      const msg = document.getElementById('msg');

      if (!label) {
        showColorError('Escribí el nombre del color.');
        return;
      }
      if (!hex) {
        showColorError('Elegí un color válido con la paleta.');
        return;
      }
      if (typeof ensureValidSession === 'function' && !ensureValidSession()) {
        return;
      }

      btn.disabled = true;
      try {
        const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
        const options = {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label, hex }),
        };
        if (fetchFn === fetch) {
          const token = localStorage.getItem('token');
          if (!token) {
            window.location.href = '/login';
            return;
          }
          options.headers.Authorization = 'Bearer ' + token;
        }

        const r = await fetchFn('/api/admin/colors', options);
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
          const detail = data.detail;
          throw new Error(
            typeof detail === 'string' ? detail : 'No se pudo agregar el color.'
          );
        }
        const c = data.color;
        if (c) {
          const idx = catalogColors.findIndex((x) => x.color_id === c.color_id);
          if (idx >= 0) catalogColors[idx] = c;
          else catalogColors.push(c);
          selectedIds.add(c.color_id);
          renderCheckboxes();
        }
        if (labelInput) labelInput.value = '';
        syncColorPicker(DEFAULT_HEX);
        if (msg && typeof COLOR_LABELS !== 'undefined' && COLOR_LABELS.msgAdded) {
          msg.textContent = COLOR_LABELS.msgAdded;
        }
        if (typeof showToast === 'function') {
          showToast(
            (typeof COLOR_LABELS !== 'undefined' && COLOR_LABELS.msgAdded) ||
              'Color agregado al catálogo.',
            { type: 'success' }
          );
        }
      } catch (e) {
        if (typeof isSessionRedirectScheduled === 'function' && isSessionRedirectScheduled()) {
          return;
        }
        showColorError(e.message || 'No se pudo agregar el color.');
      } finally {
        btn.disabled = false;
      }
    });
  }

  async function initColorsUi(options) {
    options = options || {};
    if (options.selectedIds) {
      selectedIds = new Set(options.selectedIds.map((id) => parseInt(id, 10)).filter((id) => !isNaN(id)));
    }
    bindColorPickerUi();
    bindAddColorButton();
    const status = document.getElementById('product-colors-status');
    try {
      await loadCatalog();
      if (status) status.classList.add('hidden');
    } catch (e) {
      if (status) {
        status.textContent = 'No se pudieron cargar los colores. Recargá la página.';
        status.classList.remove('hidden');
      }
    }
  }

  function collectProductColorIds() {
    return Array.from(document.querySelectorAll('.pc-color-cb:checked'))
      .map((cb) => parseInt(cb.value, 10))
      .filter((id) => !isNaN(id));
  }

  function setSelectedProductColorIds(ids) {
    selectedIds = new Set((ids || []).map((id) => parseInt(id, 10)).filter((id) => !isNaN(id)));
    renderCheckboxes();
  }

  function resetProductColors() {
    selectedIds.clear();
    renderCheckboxes();
    const input = document.getElementById('new-color-label');
    if (input) input.value = '';
    syncColorPicker(DEFAULT_HEX);
  }

  window.initColorsUi = initColorsUi;
  window.collectProductColorIds = collectProductColorIds;
  window.setSelectedProductColorIds = setSelectedProductColorIds;
  window.resetProductColors = resetProductColors;
})();
