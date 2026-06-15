(function () {
  const TOKEN_KEY = 'token';
  const REFRESH_THRESHOLD_SEC = 15 * 60;
  let sessionRedirectScheduled = false;
  let refreshInFlight = null;

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function decodeTokenPayload(token) {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    try {
      const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
      return JSON.parse(atob(padded));
    } catch (e) {
      return null;
    }
  }

  function tokenExpiresInSec(token) {
    const payload = decodeTokenPayload(token);
    if (!payload || typeof payload.exp !== 'number') return null;
    return payload.exp - Math.floor(Date.now() / 1000);
  }

  function isTokenExpired(token) {
    const remaining = tokenExpiresInSec(token);
    if (remaining == null) return true;
    return remaining <= 0;
  }

  function handleSessionExpired(message) {
    if (sessionRedirectScheduled) return false;
    sessionRedirectScheduled = true;
    localStorage.removeItem(TOKEN_KEY);
    const msg =
      message ||
      'Tu sesión expiró. Te redirigimos al login para que vuelvas a iniciar sesión.';
    if (typeof window.showToast === 'function') {
      window.showToast(msg, { type: 'error' });
    }
    setTimeout(() => {
      window.location.href = '/login';
    }, 2000);
    return false;
  }

  function ensureValidSession() {
    const token = getToken();
    if (!token) {
      window.location.href = '/login';
      return false;
    }
    if (isTokenExpired(token)) {
      return handleSessionExpired();
    }
    return true;
  }

  async function maybeRefreshToken() {
    const token = getToken();
    if (!token || isTokenExpired(token)) return false;

    const remaining = tokenExpiresInSec(token);
    if (remaining == null || remaining > REFRESH_THRESHOLD_SEC) return true;

    if (refreshInFlight) return refreshInFlight;

    refreshInFlight = (async () => {
      try {
        const res = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + token },
        });
        if (res.status === 401 || res.status === 403) {
          handleSessionExpired();
          return false;
        }
        if (!res.ok) return true;
        const data = await res.json().catch(() => ({}));
        if (data.access_token) {
          localStorage.setItem(TOKEN_KEY, data.access_token);
        }
        return true;
      } catch (e) {
        return true;
      } finally {
        refreshInFlight = null;
      }
    })();

    return refreshInFlight;
  }

  async function authFetch(url, options) {
    options = options || {};
    const token = getToken();
    if (!token) {
      handleSessionExpired();
      throw new Error('Sesión no iniciada');
    }
    if (isTokenExpired(token)) {
      handleSessionExpired();
      throw new Error('Sesión expirada');
    }

    await maybeRefreshToken();

    const headers = Object.assign({}, options.headers || {});
    const currentToken = getToken();
    if (currentToken) {
      headers.Authorization = 'Bearer ' + currentToken;
    }

    const res = await fetch(url, Object.assign({}, options, { headers }));

    if (res.status === 401 || res.status === 403) {
      let detail = '';
      try {
        const data = await res.clone().json();
        detail = typeof data.detail === 'string' ? data.detail : '';
      } catch (e) {
        detail = '';
      }
      handleSessionExpired(detail || undefined);
      throw new Error(detail || 'Sesión expirada');
    }

    return res;
  }

  window.getToken = getToken;
  window.isTokenExpired = isTokenExpired;
  window.isSessionRedirectScheduled = function () {
    return sessionRedirectScheduled;
  };
  window.handleSessionExpired = handleSessionExpired;
  window.ensureValidSession = ensureValidSession;
  window.maybeRefreshToken = maybeRefreshToken;
  window.authFetch = authFetch;
})();
