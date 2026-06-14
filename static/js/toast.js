(function () {
  let container = null;

  function ensureContainer() {
    if (container) return container;
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed top-4 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-2 w-[min(92vw,420px)] pointer-events-none';
    document.body.appendChild(container);
    return container;
  }

  function toastClasses(type) {
    if (type === 'success') {
      return 'bg-green-50 border-green-200 text-green-800';
    }
    return 'bg-red-50 border-red-200 text-red-800';
  }

  function showToast(message, options) {
    options = options || {};
    const type = options.type === 'success' ? 'success' : 'error';
    const duration = typeof options.duration === 'number' ? options.duration : 5000;
    const text = message == null ? '' : String(message).trim();
    if (!text) return;

    const root = ensureContainer();
    const el = document.createElement('div');
    el.className =
      'pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 text-sm font-medium shadow-lg ' +
      toastClasses(type);
    el.setAttribute('role', 'alert');

    const body = document.createElement('p');
    body.className = 'flex-1 leading-snug';
    body.textContent = text;

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'shrink-0 text-lg leading-none opacity-60 hover:opacity-100';
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
})();
