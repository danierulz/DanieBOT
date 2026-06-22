(function () {
  const limits = typeof window.PRODUCT_FIELD_LIMITS !== 'undefined' ? window.PRODUCT_FIELD_LIMITS : {};
  const TITLE_MAX = limits.titleMax || 255;
  const DESC_MAX = limits.descMax || 1024;

  function updateCounter(field, counterEl, max) {
    if (!field || !counterEl) return;
    const len = (field.value || '').length;
    counterEl.textContent = len + ' / ' + max;
    counterEl.classList.toggle('text-red-600', len > max);
    counterEl.classList.toggle('font-semibold', len > max);
    counterEl.classList.toggle('text-gray-500', len <= max);
  }

  function bindCounter(fieldId, counterId, max) {
    const field = document.getElementById(fieldId);
    const counter = document.getElementById(counterId);
    if (!field || !counter) return;
    const sync = () => updateCounter(field, counter, max);
    field.addEventListener('input', sync);
    sync();
  }

  function validateProductFieldLimits() {
    const titleEl = document.getElementById('item_title');
    const descEl = document.getElementById('description');
    const title = titleEl ? titleEl.value : '';
    const desc = descEl ? descEl.value : '';

    if (title.length > TITLE_MAX) {
      const msg =
        'El título supera el máximo de ' +
        TITLE_MAX +
        ' caracteres (ingresaste ' +
        title.length +
        ').';
      if (typeof showToast === 'function') showToast(msg, { type: 'error' });
      titleEl && titleEl.focus();
      return false;
    }
    if (desc.length > DESC_MAX) {
      const msg =
        'La descripción supera el máximo de ' +
        DESC_MAX +
        ' caracteres (ingresaste ' +
        desc.length +
        ').';
      if (typeof showToast === 'function') showToast(msg, { type: 'error' });
      descEl && descEl.focus();
      return false;
    }
    return true;
  }

  window.bindProductFieldLimits = function () {
    bindCounter('item_title', 'item-title-count', TITLE_MAX);
    bindCounter('description', 'description-count', DESC_MAX);
  };

  window.validateProductFieldLimits = validateProductFieldLimits;
})();
