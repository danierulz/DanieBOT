(function () {
  let container = null;

  function ensureContainer() {
    if (container) return container;
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className =
      'fixed top-4 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-2 w-[min(92vw,420px)] pointer-events-none';
    document.body.appendChild(container);
    return container;
  }

  function toastClasses(type) {
    if (type === 'success') {
      return 'bg-green-50 border-green-200 text-green-800';
    }
    return 'bg-red-50 border-red-200 text-red-800';
  }

  function formatApiMessage(detail) {
    if (detail == null || detail === '') return '';
    if (typeof detail === 'string') return detail.trim();
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item.msg === 'string') return item.msg;
          return String(item);
        })
        .filter(Boolean)
        .join('. ');
    }
    if (typeof detail === 'object' && typeof detail.message === 'string') {
      return detail.message.trim();
    }
    return String(detail).trim();
  }

  function showToast(message, options) {
    options = options || {};
    const type = options.type === 'success' ? 'success' : 'error';
    const defaultDuration = type === 'success' ? 5000 : 0;
    const duration =
      typeof options.duration === 'number' ? options.duration : defaultDuration;
    const text = formatApiMessage(message);
    if (!text) return;

    const root = ensureContainer();
    const el = document.createElement('div');
    el.className =
      'pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 text-sm font-medium shadow-lg ' +
      toastClasses(type);
    el.setAttribute('role', 'alert');

    const body = document.createElement('p');
    body.className = 'flex-1 leading-snug whitespace-pre-wrap break-words';
    body.textContent = text;

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className =
      'shrink-0 min-w-[28px] min-h-[28px] flex items-center justify-center rounded-md text-xl leading-none text-red-900/70 hover:text-red-900 hover:bg-red-100/80';
    closeBtn.setAttribute('aria-label', 'Cerrar');
    closeBtn.textContent = '×';

    let timer = null;
    const remove = () => {
      if (timer) clearTimeout(timer);
      el.remove();
    };

    closeBtn.addEventListener('click', remove);
    el.appendChild(body);
    el.appendChild(closeBtn);
    root.appendChild(el);

    if (duration > 0) {
      timer = setTimeout(remove, duration);
    }
  }

  window.showToast = showToast;
  window.formatApiMessage = formatApiMessage;
})();
