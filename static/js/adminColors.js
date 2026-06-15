(function () {
  let catalogColors = [];
  let selectedIds = new Set();

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
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
        if (typeof refreshVariantsTableForColors === 'function') {
          refreshVariantsTableForColors();
        }
      });
    });
  }

  async function loadCatalog() {
    const r = await fetch('/api/colors');
    if (!r.ok) throw new Error('load fail');
    catalogColors = await r.json();
    renderCheckboxes();
  }

  async function initColorsUi(options) {
    options = options || {};
    if (options.selectedIds) {
      selectedIds = new Set(options.selectedIds.map((id) => parseInt(id, 10)).filter((id) => !isNaN(id)));
    }
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
    if (typeof refreshVariantsTableForColors === 'function') {
      refreshVariantsTableForColors();
    }
  }

  function resetProductColors() {
    selectedIds.clear();
    renderCheckboxes();
  }

  async function refreshProductColorCheckboxes() {
    const status = document.getElementById('product-colors-status');
    if (!document.getElementById('product-colors-picker')) return;
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

  window.initColorsUi = initColorsUi;
  window.collectProductColorIds = collectProductColorIds;
  window.setSelectedProductColorIds = setSelectedProductColorIds;
  window.resetProductColors = resetProductColors;
  window.refreshProductColorCheckboxes = refreshProductColorCheckboxes;
  window.getProductColorCatalog = function () {
    return catalogColors.slice();
  };
})();
