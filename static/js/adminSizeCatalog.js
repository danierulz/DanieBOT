(function () {
  let catalogRows = [];

  function labels() {
    return typeof CATALOG_SIZE_LABELS !== 'undefined' ? CATALOG_SIZE_LABELS : {};
  }

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function showError(message, fallback) {
    const text = message || fallback || labels().msgError || 'Algo salió mal.';
    if (typeof showToast === 'function') showToast(text, { type: 'error' });
  }

  function showSuccess(message) {
    if (typeof showToast === 'function') showToast(message, { type: 'success' });
  }

  function groupLabel(group) {
    return group === 'numeric'
      ? labels().groupNumeric || 'Numérico'
      : labels().groupLetter || 'Letra';
  }

  function resetForm() {
    document.getElementById('catalog-size-id').value = '';
    document.getElementById('catalog-size-code').value = '';
    document.getElementById('catalog-size-label').value = '';
    document.getElementById('catalog-size-group').value = 'letter';
    document.getElementById('catalog-size-order').value = '';
    document.getElementById('catalog-size-code').disabled = false;
    const submit = document.getElementById('catalog-size-submit');
    const cancel = document.getElementById('catalog-size-cancel');
    if (submit) submit.textContent = labels().btnAdd || 'Agregar talle';
    if (cancel) cancel.classList.add('hidden');
  }

  function renderCatalogTable() {
    const tbody = document.getElementById('sizes-catalog-body');
    const status = document.getElementById('sizes-catalog-status');
    if (!tbody) return;

    if (!catalogRows.length) {
      tbody.innerHTML = '';
      if (status) status.textContent = labels().empty || 'Todavía no hay talles en el catálogo.';
      return;
    }

    if (status) status.textContent = catalogRows.length + ' talle(s)';
    tbody.innerHTML = catalogRows
      .map(
        (s) => `
        <tr class="hover:bg-gray-50">
          <td class="px-3 py-2 align-middle font-mono text-xs text-gray-900">${escapeHtml(s.code)}</td>
          <td class="px-3 py-2 align-middle font-medium text-gray-900">${escapeHtml(s.label)}</td>
          <td class="px-3 py-2 align-middle text-gray-700">${escapeHtml(groupLabel(s.size_group))}</td>
          <td class="px-3 py-2 align-middle text-gray-600">${escapeHtml(s.sort_order)}</td>
          <td class="px-3 py-2 align-middle text-right whitespace-nowrap space-x-3">
            <button type="button" class="size-catalog-edit-btn text-black font-semibold hover:underline" data-id="${s.size_id}">${escapeHtml(labels().edit || 'Editar')}</button>
            <button type="button" class="size-catalog-del-btn text-red-600 font-semibold hover:underline" data-id="${s.size_id}">${escapeHtml(labels().del || 'Eliminar')}</button>
          </td>
        </tr>`
      )
      .join('');

    tbody.querySelectorAll('.size-catalog-edit-btn').forEach((btn) => {
      btn.addEventListener('click', () => startEdit(parseInt(btn.getAttribute('data-id'), 10)));
    });
    tbody.querySelectorAll('.size-catalog-del-btn').forEach((btn) => {
      btn.addEventListener('click', () => removeSize(parseInt(btn.getAttribute('data-id'), 10)));
    });
  }

  function startEdit(sizeId) {
    const row = catalogRows.find((s) => s.size_id === sizeId);
    if (!row) return;
    document.getElementById('catalog-size-id').value = String(row.size_id);
    document.getElementById('catalog-size-code').value = row.code || '';
    document.getElementById('catalog-size-code').disabled = true;
    document.getElementById('catalog-size-label').value = row.label || '';
    document.getElementById('catalog-size-group').value = row.size_group || 'letter';
    document.getElementById('catalog-size-order').value = row.sort_order != null ? String(row.sort_order) : '';
    document.getElementById('catalog-size-submit').textContent = labels().btnUpdate || 'Guardar cambios';
    document.getElementById('catalog-size-cancel').classList.remove('hidden');
    document.getElementById('catalog-size-label').focus();
  }

  async function loadSizesCatalog() {
    const status = document.getElementById('sizes-catalog-status');
    if (status) status.textContent = labels().loading || 'Cargando…';
    try {
      const res = await authFetch('/api/admin/sizes');
      if (!res.ok) throw new Error('fail');
      catalogRows = await res.json();
      renderCatalogTable();
    } catch (e) {
      if (status) status.textContent = labels().loadErr || 'No se pudieron cargar los talles.';
    }
  }

  async function saveCatalogSize(e) {
    e.preventDefault();
    const idRaw = document.getElementById('catalog-size-id').value;
    const code = document.getElementById('catalog-size-code').value.trim();
    const label = document.getElementById('catalog-size-label').value.trim();
    const sizeGroup = document.getElementById('catalog-size-group').value;
    const orderRaw = document.getElementById('catalog-size-order').value.trim();
    const sortOrder = orderRaw === '' ? null : parseInt(orderRaw, 10);

    if (!idRaw && !code) {
      showError(labels().codeRequired || 'Escribí el código del talle.');
      return;
    }
    if (!label) {
      showError(labels().labelRequired || 'Escribí la etiqueta del talle.');
      return;
    }

    const submitBtn = document.getElementById('catalog-size-submit');
    submitBtn.disabled = true;
    try {
      const isEdit = !!idRaw;
      const payload = isEdit
        ? { label, size_group: sizeGroup, sort_order: sortOrder }
        : { code, label, size_group: sizeGroup, sort_order: sortOrder };
      const res = await authFetch(isEdit ? '/api/admin/sizes/' + idRaw : '/api/admin/sizes', {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : labels().msgError);
      }
      showSuccess(
        isEdit ? labels().msgUpdated || 'Talle actualizado.' : labels().msgAdded || 'Talle agregado.'
      );
      resetForm();
      await loadSizesCatalog();
      if (typeof window.refreshVariantsTableForCategory === 'function') {
        await window.refreshVariantsTableForCategory();
      }
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== 'function' || !isSessionRedirectScheduled()) {
        showError(err.message, labels().msgError);
      }
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function removeSize(sizeId) {
    const row = catalogRows.find((s) => s.size_id === sizeId);
    const name = row ? row.label : 'este talle';
    const confirmMsg = (labels().deleteConfirm || '¿Eliminar talle "{name}"?').replace('{name}', name);
    if (!window.confirm(confirmMsg)) return;

    try {
      const res = await authFetch('/api/admin/sizes/' + sizeId, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : labels().msgError);
      }
      showSuccess(labels().msgDeleted || 'Talle eliminado.');
      if (document.getElementById('catalog-size-id').value === String(sizeId)) {
        resetForm();
      }
      await loadSizesCatalog();
      if (typeof window.refreshVariantsTableForCategory === 'function') {
        await window.refreshVariantsTableForCategory();
      }
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== 'function' || !isSessionRedirectScheduled()) {
        showError(err.message, labels().msgError);
      }
    }
  }

  function initSizeCatalogTab() {
    const form = document.getElementById('catalog-size-form');
    if (form && !form.dataset.bound) {
      form.dataset.bound = '1';
      form.addEventListener('submit', saveCatalogSize);
    }
    const cancel = document.getElementById('catalog-size-cancel');
    if (cancel && !cancel.dataset.bound) {
      cancel.dataset.bound = '1';
      cancel.addEventListener('click', resetForm);
    }
  }

  async function loadSizeCatalogTab() {
    await loadSizesCatalog();
  }

  window.initSizeCatalogTab = initSizeCatalogTab;
  window.loadSizeCatalogTab = loadSizeCatalogTab;
})();
