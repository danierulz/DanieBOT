(function () {
  let catalogSizes = [];
  let savedVariants = [];

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function getCategorySlugFromForm() {
    const sel = document.getElementById('category_id');
    if (!sel || !sel.value) return '';
    const opt = sel.options[sel.selectedIndex];
    return opt ? opt.getAttribute('data-slug') || '' : '';
  }

  function getSelectedProductColors() {
    if (typeof collectProductColorIds === 'function') {
      const ids = collectProductColorIds();
      if (ids.length) return ids;
    }
    return [];
  }

  function getColorMeta(colorId) {
    if (typeof getProductColorCatalog === 'function') {
      const c = getProductColorCatalog().find((x) => x.color_id === colorId);
      if (c) return c;
    }
    return { color_id: colorId, label: 'Color ' + colorId, hex: '#888888' };
  }

  function readCurrentRows() {
    const out = [];
    document.querySelectorAll('#variants-table-body tr[data-size-code]').forEach((row) => {
      const code = row.getAttribute('data-size-code');
      const colorRaw = row.getAttribute('data-color-id');
      const colorId = colorRaw != null && colorRaw !== '' ? parseInt(colorRaw, 10) : null;
      const q = row.querySelector('.pv-qty');
      const e = row.querySelector('.pv-encargo');
      const d = row.querySelector('.pv-dias');
      out.push({
        size_code: code,
        color_id: isNaN(colorId) ? null : colorId,
        qty_stock_local: q ? parseInt(q.value, 10) || 0 : 0,
        encargo_habilitado: e ? e.checked : false,
        dias_encargo_estimados: d && d.value.trim() ? parseInt(d.value, 10) : null,
      });
    });
    return out;
  }

  function variantKey(sizeCode, colorId) {
    return sizeCode + '|' + (colorId == null ? '' : String(colorId));
  }

  function buildLookup(rows) {
    const map = {};
    (rows || []).forEach((v) => {
      map[variantKey(v.size_code, v.color_id ?? null)] = v;
    });
    return map;
  }

  function renderTableHead(hasColors) {
    const thead = document.querySelector('#variants-table-body')?.closest('table')?.querySelector('thead tr');
    if (!thead) return;
    const colSize =
      (typeof VARIANT_LABELS !== 'undefined' && VARIANT_LABELS.colSize) || 'Talle';
    const colColor =
      (typeof VARIANT_LABELS !== 'undefined' && VARIANT_LABELS.colColor) || 'Color';
    const colStock =
      (typeof VARIANT_LABELS !== 'undefined' && VARIANT_LABELS.colStock) || 'Uds. en local';
    const colEncargo =
      (typeof VARIANT_LABELS !== 'undefined' && VARIANT_LABELS.colEncargo) || 'Por encargo';
    const colDays =
      (typeof VARIANT_LABELS !== 'undefined' && VARIANT_LABELS.colDays) || 'Días (estimado)';
    thead.innerHTML = hasColors
      ? `<th class="px-2 py-2 font-semibold text-gray-700">${escapeHtml(colSize)}</th>
         <th class="px-2 py-2 font-semibold text-gray-700">${escapeHtml(colColor)}</th>
         <th class="px-2 py-2 font-semibold text-gray-700 whitespace-nowrap">${escapeHtml(colStock)}</th>
         <th class="px-2 py-2 font-semibold text-gray-700 text-center">${escapeHtml(colEncargo)}</th>
         <th class="px-2 py-2 font-semibold text-gray-700 whitespace-nowrap">${escapeHtml(colDays)}</th>`
      : `<th class="px-2 py-2 font-semibold text-gray-700">${escapeHtml(colSize)}</th>
         <th class="px-2 py-2 font-semibold text-gray-700 whitespace-nowrap">${escapeHtml(colStock)}</th>
         <th class="px-2 py-2 font-semibold text-gray-700 text-center">${escapeHtml(colEncargo)}</th>
         <th class="px-2 py-2 font-semibold text-gray-700 whitespace-nowrap">${escapeHtml(colDays)}</th>`;
  }

  function renderVariantRows(preserveRows) {
    const tbody = document.getElementById('variants-table-body');
    if (!tbody || !catalogSizes.length) return;

    const colorIds = getSelectedProductColors();
    const hasColors = colorIds.length > 0;
    const preserved = buildLookup(preserveRows || readCurrentRows());
    const fromSaved = buildLookup(savedVariants);

    renderTableHead(hasColors);

    const rows = [];
    catalogSizes.forEach((s) => {
      if (hasColors) {
        colorIds.forEach((cid) => {
          rows.push({ size: s, colorId: cid });
        });
      } else {
        rows.push({ size: s, colorId: null });
      }
    });

    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="5" class="px-2 py-3 text-gray-500 text-sm">Seleccioná al menos un color o cargá talles.</td></tr>';
      return;
    }

    tbody.innerHTML = rows
      .map(({ size, colorId }) => {
        const key = variantKey(size.code, colorId);
        const legacyKey = variantKey(size.code, null);
        const v =
          preserved[key] ||
          fromSaved[key] ||
          (colorId != null ? preserved[legacyKey] || fromSaved[legacyKey] : null) ||
          {};
        const qty = v.qty_stock_local ?? 0;
        const enc = !!v.encargo_habilitado;
        const dias = v.dias_encargo_estimados != null ? String(v.dias_encargo_estimados) : '';
        const colorAttr = colorId != null ? ` data-color-id="${colorId}"` : '';
        const colorCell = hasColors
          ? (() => {
              const c = getColorMeta(colorId);
              return `<td class="px-2 py-2">
                <span class="inline-flex items-center gap-1.5 text-sm">
                  <span class="w-4 h-4 rounded-full border border-gray-300 shrink-0" style="background:${escapeHtml(
                    c.hex || '#888888'
                  )}"></span>
                  ${escapeHtml(c.label)}
                </span>
              </td>`;
            })()
          : '';
        return `<tr data-size-code="${escapeHtml(size.code)}"${colorAttr} class="border-t border-gray-100">
          <td class="px-2 py-2 font-medium">${escapeHtml(size.label)} <span class="text-gray-400 text-xs">(${escapeHtml(
            size.code
          )})</span></td>
          ${colorCell}
          <td class="px-2 py-2"><input type="number" min="0" step="1" value="${qty}" class="pv-qty w-20 px-2 py-1 border rounded-md" aria-label="Stock ${escapeHtml(
            size.code
          )}"></td>
          <td class="px-2 py-2 text-center"><input type="checkbox" class="pv-encargo w-4 h-4 accent-black" ${
            enc ? 'checked' : ''
          } aria-label="Encargo ${escapeHtml(size.code)}"></td>
          <td class="px-2 py-2"><input type="number" min="1" step="1" placeholder="—" value="${escapeHtml(
            dias
          )}" class="pv-dias w-16 px-2 py-1 border rounded-md"></td>
        </tr>`;
      })
      .join('');
  }

  async function loadCatalogSizes(categorySlug) {
    const slug = (categorySlug || '').trim();
    const url = slug ? '/api/sizes?category_slug=' + encodeURIComponent(slug) : '/api/sizes';
    const r = await fetch(url);
    if (!r.ok) throw new Error('fail');
    catalogSizes = await r.json();
  }

  async function initVariantsTable() {
    const tbody = document.getElementById('variants-table-body');
    if (!tbody) return;
    tbody.innerHTML =
      '<tr><td colspan="5" class="px-2 py-3 text-gray-500 text-sm">Cargando talles…</td></tr>';
    try {
      await loadCatalogSizes(getCategorySlugFromForm());
      renderVariantRows();
    } catch (e) {
      const msg =
        (typeof VARIANT_LABELS !== 'undefined' && VARIANT_LABELS.loadError) ||
        'No se pudieron cargar los talles. Recargá la página.';
      tbody.innerHTML = `<tr><td colspan="5" class="text-red-600 px-2 py-2 text-sm">${escapeHtml(
        msg
      )}</td></tr>`;
    }
  }

  function resetVariantRows() {
    savedVariants = [];
    document.querySelectorAll('#variants-table-body tr[data-size-code]').forEach((row) => {
      const q = row.querySelector('.pv-qty');
      const e = row.querySelector('.pv-encargo');
      const d = row.querySelector('.pv-dias');
      if (q) q.value = '0';
      if (e) e.checked = false;
      if (d) d.value = '';
    });
  }

  function collectVariants() {
    const out = [];
    const hasColors = getSelectedProductColors().length > 0;
    readCurrentRows().forEach((row) => {
      const qty = row.qty_stock_local || 0;
      const enc = row.encargo_habilitado;
      if (!hasColors && qty === 0 && !enc) return;
      const o = {
        size_code: row.size_code,
        qty_stock_local: qty,
        encargo_habilitado: enc,
      };
      if (row.color_id != null) o.color_id = row.color_id;
      if (row.dias_encargo_estimados != null && !isNaN(row.dias_encargo_estimados)) {
        o.dias_encargo_estimados = row.dias_encargo_estimados;
      }
      if (hasColors || qty > 0 || enc) out.push(o);
    });
    return JSON.stringify(out);
  }

  function fillVariantsFromProduct(p) {
    savedVariants = (p && p.variantes) || [];
    renderVariantRows();
  }

  function refreshVariantsTableForColors() {
    if (!catalogSizes.length) return;
    const preserved = readCurrentRows();
    renderVariantRows(preserved);
  }

  async function refreshVariantsTableForCategory() {
    const preserved = readCurrentRows();
    try {
      await loadCatalogSizes(getCategorySlugFromForm());
      renderVariantRows(preserved);
    } catch (e) {
      /* keep current table on transient errors */
    }
  }

  function bindCategoryForVariants() {
    const sel = document.getElementById('category_id');
    if (!sel || sel.dataset.variantsBound === '1') return;
    sel.dataset.variantsBound = '1';
    sel.addEventListener('change', () => {
      refreshVariantsTableForCategory();
    });
  }

  window.initVariantsTable = initVariantsTable;
  window.resetVariantRows = resetVariantRows;
  window.collectVariants = collectVariants;
  window.fillVariantsFromProduct = fillVariantsFromProduct;
  window.refreshVariantsTableForColors = refreshVariantsTableForColors;
  window.refreshVariantsTableForCategory = refreshVariantsTableForCategory;
  window.bindCategoryForVariants = bindCategoryForVariants;
})();
