(function () {
  const DEFAULT_HEX = '#2563EB';
  let catalogRows = [];

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function labels() {
    return typeof CATALOG_COLOR_LABELS !== 'undefined' ? CATALOG_COLOR_LABELS : {};
  }

  function showError(message, fallback) {
    const text = message || fallback || labels().msgError || 'Algo salió mal.';
    if (typeof showToast === 'function') showToast(text, { type: 'error' });
  }

  function showSuccess(message) {
    if (typeof showToast === 'function') showToast(message, { type: 'success' });
  }

  function normalizeHex(value) {
    const raw = (value || '').trim();
    if (!raw) return null;
    const withHash = raw.startsWith('#') ? raw : '#' + raw;
    return /^#[0-9A-Fa-f]{6}$/.test(withHash) ? withHash.toUpperCase() : null;
  }

  function syncPicker(hex) {
    const input = document.getElementById('catalog-color-hex');
    const preview = document.getElementById('catalog-color-preview');
    const clean = normalizeHex(hex) || DEFAULT_HEX;
    if (input) input.value = clean;
    if (preview) preview.style.background = clean;
  }

  function resetForm() {
    document.getElementById('catalog-color-id').value = '';
    document.getElementById('catalog-color-label').value = '';
    syncPicker(DEFAULT_HEX);
    const submit = document.getElementById('catalog-color-submit');
    const cancel = document.getElementById('catalog-color-cancel');
    if (submit) submit.textContent = labels().btnAdd || 'Agregar color';
    if (cancel) cancel.classList.add('hidden');
  }

  function bindPickerUi() {
    const input = document.getElementById('catalog-color-hex');
    if (input && !input.dataset.bound) {
      input.dataset.bound = '1';
      input.addEventListener('input', () => syncPicker(input.value));
    }
    document.querySelectorAll('.catalog-preset-btn').forEach((btn) => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', () => syncPicker(btn.getAttribute('data-hex')));
    });
    syncPicker(input ? input.value : DEFAULT_HEX);
  }

  function renderTable() {
    const tbody = document.getElementById('colors-catalog-body');
    const status = document.getElementById('colors-catalog-status');
    if (!tbody) return;

    if (!catalogRows.length) {
      tbody.innerHTML = '';
      if (status) status.textContent = labels().empty || 'Todavía no hay colores en el catálogo.';
      return;
    }

    if (status) status.textContent = catalogRows.length + ' color(es)';
    tbody.innerHTML = catalogRows
      .map((c) => {
        const hex = c.hex || '#888888';
        return `
        <tr class="hover:bg-gray-50">
          <td class="px-3 py-2 align-middle">
            <span class="inline-block w-8 h-8 rounded-full border border-gray-300" style="background:${escapeHtml(hex)}"></span>
          </td>
          <td class="px-3 py-2 align-middle font-medium text-gray-900">${escapeHtml(c.label)}</td>
          <td class="px-3 py-2 align-middle font-mono text-xs text-gray-600">${escapeHtml(hex)}</td>
          <td class="px-3 py-2 align-middle text-right whitespace-nowrap space-x-3">
            <button type="button" class="catalog-edit-btn text-black font-semibold hover:underline" data-id="${c.color_id}">${escapeHtml(labels().edit || 'Editar')}</button>
            <button type="button" class="catalog-del-btn text-red-600 font-semibold hover:underline" data-id="${c.color_id}">${escapeHtml(labels().del || 'Eliminar')}</button>
          </td>
        </tr>`;
      })
      .join('');

    tbody.querySelectorAll('.catalog-edit-btn').forEach((btn) => {
      btn.addEventListener('click', () => startEdit(parseInt(btn.getAttribute('data-id'), 10)));
    });
    tbody.querySelectorAll('.catalog-del-btn').forEach((btn) => {
      btn.addEventListener('click', () => removeColor(parseInt(btn.getAttribute('data-id'), 10)));
    });
  }

  function startEdit(colorId) {
    const row = catalogRows.find((c) => c.color_id === colorId);
    if (!row) return;
    document.getElementById('catalog-color-id').value = String(row.color_id);
    document.getElementById('catalog-color-label').value = row.label || '';
    syncPicker(row.hex || DEFAULT_HEX);
    document.getElementById('catalog-color-submit').textContent = labels().btnUpdate || 'Guardar cambios';
    document.getElementById('catalog-color-cancel').classList.remove('hidden');
    document.getElementById('catalog-color-label').focus();
  }

  async function loadColorsCatalog() {
    const status = document.getElementById('colors-catalog-status');
    if (status) status.textContent = labels().loading || 'Cargando…';
    try {
      const res = await fetch('/api/colors');
      if (!res.ok) throw new Error('fail');
      catalogRows = await res.json();
      renderTable();
    } catch (e) {
      if (status) status.textContent = labels().loadErr || 'No se pudieron cargar los colores.';
    }
  }

  async function saveCatalogColor(e) {
    e.preventDefault();
    const idRaw = document.getElementById('catalog-color-id').value;
    const label = document.getElementById('catalog-color-label').value.trim();
    const hex = normalizeHex(document.getElementById('catalog-color-hex').value);
    if (!label) {
      showError(labels().nameRequired || 'Escribí el nombre del color.');
      return;
    }
    if (!hex) {
      showError(labels().hexRequired || 'Elegí un tono de color válido.');
      return;
    }

    const submitBtn = document.getElementById('catalog-color-submit');
    submitBtn.disabled = true;
    try {
      const isEdit = !!idRaw;
      const res = await authFetch(isEdit ? '/api/admin/colors/' + idRaw : '/api/admin/colors', {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label, hex }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : labels().msgError);
      }
      showSuccess(isEdit ? labels().msgUpdated || 'Color actualizado.' : labels().msgAdded || 'Color agregado.');
      resetForm();
      await loadColorsCatalog();
      if (typeof window.refreshProductColorCheckboxes === 'function') {
        window.refreshProductColorCheckboxes();
      }
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== 'function' || !isSessionRedirectScheduled()) {
        showError(err.message, labels().msgError);
      }
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function removeColor(colorId) {
    const row = catalogRows.find((c) => c.color_id === colorId);
    const name = row ? row.label : 'este color';
    const confirmMsg = (labels().deleteConfirm || '¿Eliminar "{name}"?').replace('{name}', name);
    if (!window.confirm(confirmMsg)) return;

    try {
      const res = await authFetch('/api/admin/colors/' + colorId, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : labels().msgError);
      }
      showSuccess(labels().msgDeleted || 'Color eliminado.');
      if (document.getElementById('catalog-color-id').value === String(colorId)) {
        resetForm();
      }
      await loadColorsCatalog();
      if (typeof window.refreshProductColorCheckboxes === 'function') {
        window.refreshProductColorCheckboxes();
      }
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== 'function' || !isSessionRedirectScheduled()) {
        showError(err.message, labels().msgError);
      }
    }
  }

  function initColorCatalogTab() {
    bindPickerUi();
    const form = document.getElementById('catalog-color-form');
    if (form && !form.dataset.bound) {
      form.dataset.bound = '1';
      form.addEventListener('submit', saveCatalogColor);
    }
    const cancel = document.getElementById('catalog-color-cancel');
    if (cancel && !cancel.dataset.bound) {
      cancel.dataset.bound = '1';
      cancel.addEventListener('click', resetForm);
    }
  }

  window.initColorCatalogTab = initColorCatalogTab;
  window.loadColorsCatalog = loadColorsCatalog;
})();
