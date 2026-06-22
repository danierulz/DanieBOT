(function () {
  let catalogRows = [];

  function labels() {
    return typeof CATALOG_CATEGORY_LABELS !== 'undefined' ? CATALOG_CATEGORY_LABELS : {};
  }

  function sizeLabels() {
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
      ? sizeLabels().groupNumeric || 'Numérico'
      : sizeLabels().groupLetter || 'Letra';
  }

  function resetForm() {
    document.getElementById('catalog-category-id').value = '';
    document.getElementById('catalog-category-name').value = '';
    document.getElementById('catalog-category-slug').value = '';
    document.getElementById('catalog-category-slug').disabled = false;
    document.getElementById('catalog-category-group').value = 'letter';
    document.getElementById('catalog-category-order').value = '';
    document.getElementById('catalog-category-active').checked = true;
    const submit = document.getElementById('catalog-category-submit');
    const cancel = document.getElementById('catalog-category-cancel');
    if (submit) submit.textContent = labels().btnAdd || 'Agregar categoría';
    if (cancel) cancel.classList.add('hidden');
  }

  function renderTable() {
    const tbody = document.getElementById('categories-catalog-body');
    const status = document.getElementById('categories-catalog-status');
    if (!tbody) return;

    if (!catalogRows.length) {
      tbody.innerHTML = '';
      if (status) status.textContent = labels().empty || 'Todavía no hay categorías.';
      return;
    }

    if (status) status.textContent = catalogRows.length + ' categoría(s)';
    tbody.innerHTML = catalogRows
      .map(
        (c) => `
        <tr class="hover:bg-gray-50">
          <td class="px-3 py-2 align-middle font-medium text-gray-900">${escapeHtml(c.name)}</td>
          <td class="px-3 py-2 align-middle font-mono text-xs text-gray-600">${escapeHtml(c.slug)}</td>
          <td class="px-3 py-2 align-middle text-gray-700">${escapeHtml(groupLabel(c.size_group))}</td>
          <td class="px-3 py-2 align-middle text-gray-600">${escapeHtml(c.sort_order)}</td>
          <td class="px-3 py-2 align-middle text-center">${c.activo ? '✓' : '—'}</td>
          <td class="px-3 py-2 align-middle text-gray-600">${escapeHtml(c.product_count != null ? c.product_count : 0)}</td>
          <td class="px-3 py-2 align-middle text-right whitespace-nowrap space-x-3">
            <button type="button" class="category-catalog-edit-btn text-black font-semibold hover:underline" data-id="${c.category_id}">${escapeHtml(labels().edit || 'Editar')}</button>
            <button type="button" class="category-catalog-del-btn text-red-600 font-semibold hover:underline" data-id="${c.category_id}">${escapeHtml(labels().del || 'Eliminar')}</button>
          </td>
        </tr>`
      )
      .join('');

    tbody.querySelectorAll('.category-catalog-edit-btn').forEach((btn) => {
      btn.addEventListener('click', () => startEdit(parseInt(btn.getAttribute('data-id'), 10)));
    });
    tbody.querySelectorAll('.category-catalog-del-btn').forEach((btn) => {
      btn.addEventListener('click', () => removeCategory(parseInt(btn.getAttribute('data-id'), 10)));
    });
  }

  function startEdit(categoryId) {
    const row = catalogRows.find((c) => c.category_id === categoryId);
    if (!row) return;
    document.getElementById('catalog-category-id').value = String(row.category_id);
    document.getElementById('catalog-category-name').value = row.name || '';
    document.getElementById('catalog-category-slug').value = row.slug || '';
    document.getElementById('catalog-category-slug').disabled = true;
    document.getElementById('catalog-category-group').value = row.size_group || 'letter';
    document.getElementById('catalog-category-order').value =
      row.sort_order != null ? String(row.sort_order) : '';
    document.getElementById('catalog-category-active').checked = !!row.activo;
    document.getElementById('catalog-category-submit').textContent =
      labels().btnUpdate || 'Guardar cambios';
    document.getElementById('catalog-category-cancel').classList.remove('hidden');
    document.getElementById('catalog-category-name').focus();
  }

  async function loadCategoriesCatalog() {
    const status = document.getElementById('categories-catalog-status');
    if (status) status.textContent = labels().loading || 'Cargando…';
    try {
      const res = await authFetch('/api/admin/categories');
      if (!res.ok) throw new Error('fail');
      catalogRows = await res.json();
      renderTable();
    } catch (e) {
      if (status) status.textContent = labels().loadErr || 'No se pudieron cargar las categorías.';
    }
  }

  async function saveCatalogCategory(e) {
    e.preventDefault();
    const idRaw = document.getElementById('catalog-category-id').value;
    const name = document.getElementById('catalog-category-name').value.trim();
    const slugRaw = document.getElementById('catalog-category-slug').value.trim();
    const sizeGroup = document.getElementById('catalog-category-group').value;
    const orderRaw = document.getElementById('catalog-category-order').value.trim();
    const sortOrder = orderRaw === '' ? null : parseInt(orderRaw, 10);
    const activo = document.getElementById('catalog-category-active').checked;

    if (!name) {
      showError(labels().nameRequired || 'Escribí el nombre de la categoría.');
      return;
    }

    const submitBtn = document.getElementById('catalog-category-submit');
    submitBtn.disabled = true;
    try {
      const isEdit = !!idRaw;
      const payload = isEdit
        ? { name, size_group: sizeGroup, sort_order: sortOrder, activo }
        : {
            name,
            slug: slugRaw || null,
            size_group: sizeGroup,
            sort_order: sortOrder,
            activo,
          };
      const res = await authFetch(
        isEdit ? '/api/admin/categories/' + idRaw : '/api/admin/categories',
        {
          method: isEdit ? 'PUT' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : labels().msgError);
      }
      showSuccess(
        isEdit ? labels().msgUpdated || 'Categoría actualizada.' : labels().msgAdded || 'Categoría creada.'
      );
      resetForm();
      await loadCategoriesCatalog();
      if (typeof loadCategoriesSelect === 'function') {
        await loadCategoriesSelect('category_id');
      }
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== 'function' || !isSessionRedirectScheduled()) {
        showError(err.message, labels().msgError);
      }
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function removeCategory(categoryId) {
    const row = catalogRows.find((c) => c.category_id === categoryId);
    const name = row ? row.name : 'esta categoría';
    const confirmMsg = (labels().deleteConfirm || '¿Eliminar "{name}"?').replace('{name}', name);
    if (!window.confirm(confirmMsg)) return;

    try {
      const res = await authFetch('/api/admin/categories/' + categoryId, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : labels().msgError);
      }
      showSuccess(labels().msgDeleted || 'Categoría eliminada.');
      if (document.getElementById('catalog-category-id').value === String(categoryId)) {
        resetForm();
      }
      await loadCategoriesCatalog();
      if (typeof loadCategoriesSelect === 'function') {
        await loadCategoriesSelect('category_id');
      }
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== 'function' || !isSessionRedirectScheduled()) {
        showError(err.message, labels().msgError);
      }
    }
  }

  function initCategoryCatalogTab() {
    const form = document.getElementById('catalog-category-form');
    if (form && !form.dataset.bound) {
      form.dataset.bound = '1';
      form.addEventListener('submit', saveCatalogCategory);
    }
    const cancel = document.getElementById('catalog-category-cancel');
    if (cancel && !cancel.dataset.bound) {
      cancel.dataset.bound = '1';
      cancel.addEventListener('click', resetForm);
    }
  }

  window.initCategoryCatalogTab = initCategoryCatalogTab;
  window.loadCategoriesCatalog = loadCategoriesCatalog;
})();
