/* Novedades de proveedores: primera página del listado, solo en la PC.
   No recorre el catálogo ni publica a Meta. Importar es opcional y deja inactivo. */
(function () {
  var started = false;
  var busy = false;
  var lastItems = [];
  var delayByProvider = {};

  function panel() {
    return document.getElementById("panel-watch");
  }

  function setStatus(message) {
    var node = document.getElementById("watch-status");
    if (node) node.textContent = message || "";
  }

  function selectedProviders() {
    return Array.prototype.map.call(
      document.querySelectorAll(".watch-provider:checked"),
      function (input) { return input.value; }
    );
  }

  function limitValue() {
    var select = document.getElementById("watch-limit");
    var value = select ? parseInt(select.value, 10) : 5;
    return value === 10 ? 10 : 5;
  }

  function categoryValue() {
    var select = document.getElementById("watch-laslocas-category");
    return select && select.value ? select.value : "denim";
  }

  function money(price) {
    if (price === null || price === undefined || price === "") return "—";
    try {
      return new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 }).format(price);
    } catch (err) {
      return String(price);
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render(data) {
    var body = document.getElementById("watch-table-body");
    var errors = document.getElementById("watch-errors");
    var cli = document.getElementById("watch-cli");
    var root = panel();
    if (!body || !root) return;
    lastItems = (data && data.items) || [];
    delayByProvider = {};
    (data.providers || []).forEach(function (row) {
      delayByProvider[row.id] = row.delay_ms || 1500;
    });
    errors.innerHTML = "";
    (data.providers || []).forEach(function (row) {
      if (!row.error) return;
      var p = document.createElement("p");
      p.textContent = row.display_name + ": " + row.error;
      errors.appendChild(p);
    });
    cli.textContent = (data.providers || []).map(function (row) {
      return row.cli_dry_run || "";
    }).filter(Boolean).join("\n");

    if (!lastItems.length) {
      body.innerHTML = "<tr><td colspan=\"5\" class=\"px-3 py-4 text-gray-500\">" +
        escapeHtml(root.dataset.empty || "") + "</td></tr>";
      return;
    }
    body.innerHTML = lastItems.map(function (item, index) {
      var isNew = item.status === "nuevo";
      var title = item.title || item.url;
      var hint = item.match_label ? "<span class=\"block text-xs text-gray-500\">" + escapeHtml(item.match_label) + "</span>" : "";
      var check = isNew
        ? "<input type=\"checkbox\" class=\"watch-pick w-4 h-4 accent-black\" data-index=\"" + index + "\">"
        : "";
      var badge = isNew
        ? "bg-emerald-100 text-emerald-900"
        : "bg-amber-100 text-amber-950";
      return "<tr class=\"border-t border-gray-100 align-top\" data-status=\"" + escapeHtml(item.status) + "\">" +
        "<td class=\"px-2 py-2\">" + check + "</td>" +
        "<td class=\"px-2 py-2 whitespace-nowrap\">" + escapeHtml(item.provider_name || item.provider) + "</td>" +
        "<td class=\"px-2 py-2\"><a class=\"font-medium text-gray-900 hover:underline break-all\" target=\"_blank\" rel=\"noopener\" href=\"" +
          escapeHtml(item.url) + "\">" + escapeHtml(title) + "</a>" +
          "<span class=\"block text-xs text-gray-500 break-all\">" + escapeHtml(item.url) + "</span></td>" +
        "<td class=\"px-2 py-2 whitespace-nowrap\">" + escapeHtml(money(item.price)) + "</td>" +
        "<td class=\"px-2 py-2\"><span class=\"inline-block rounded px-2 py-0.5 text-xs font-semibold " + badge + "\">" +
          escapeHtml(item.status_label || item.status) + "</span>" + hint + "</td></tr>";
    }).join("");
  }

  function pickedIndexes() {
    return Array.prototype.map.call(
      document.querySelectorAll(".watch-pick:checked"),
      function (input) { return parseInt(input.getAttribute("data-index"), 10); }
    ).filter(function (index) { return !isNaN(index); });
  }

  async function runScan() {
    if (busy) return;
    var root = panel();
    if (!root) return;
    var providers = selectedProviders();
    if (!providers.length) {
      setStatus("Elegí al menos un proveedor.");
      return;
    }
    busy = true;
    var button = document.getElementById("watch-scan-btn");
    if (button) button.disabled = true;
    setStatus(root.dataset.scanning || "Leyendo…");
    try {
      var response = await authFetch("/api/proveedores/novedades", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          providers: providers,
          limit: limitValue(),
          laslocas_category: categoryValue(),
        }),
      });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        var detail = data.detail || response.statusText;
        setStatus(typeof detail === "string" ? detail : "No se pudo leer el listado.");
        return;
      }
      render(data);
      var nuevos = lastItems.filter(function (item) { return item.status === "nuevo"; }).length;
      var dups = lastItems.length - nuevos;
      setStatus(nuevos + " nuevo" + (nuevos === 1 ? "" : "s") + " · " + dups + " posible duplicado" + (dups === 1 ? "" : "s") + ". " + (data.notice || root.dataset.notice || ""));
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== "function" || !isSessionRedirectScheduled()) {
        setStatus(err && err.message ? err.message : "No se pudo leer el listado.");
      }
    } finally {
      busy = false;
      if (button) button.disabled = false;
    }
  }

  function urlsToCopy() {
    var picked = pickedIndexes();
    var rows = picked.length
      ? picked.map(function (index) { return lastItems[index]; })
      : lastItems.filter(function (item) { return item.status === "nuevo"; });
    return rows.map(function (item) { return item && item.url; }).filter(Boolean);
  }

  async function copyUrls() {
    var root = panel();
    var urls = urlsToCopy();
    if (!urls.length) {
      setStatus("No hay URLs nuevas para copiar.");
      return;
    }
    var payload = urls.join("\n");
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(payload);
      } else {
        var area = document.createElement("textarea");
        area.value = payload;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setStatus((root && root.dataset.copied) || "URLs copiadas.");
    } catch (err) {
      setStatus(payload);
    }
  }

  function delayFor(provider) {
    var ms = delayByProvider[provider] || 1500;
    if (provider === "sochic") return Math.max(ms, 5000);
    return Math.max(ms, 1500);
  }

  function wait(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  async function importSelected() {
    var root = panel();
    var indexes = pickedIndexes().filter(function (index) {
      return lastItems[index] && lastItems[index].status === "nuevo";
    });
    if (!indexes.length) {
      setStatus("Marcá fichas en estado nuevo. Los posibles duplicados no se importan.");
      return;
    }
    var confirmText = (root && root.dataset.importConfirm) || "";
    if (confirmText && !window.confirm(confirmText)) return;
    var button = document.getElementById("watch-import-btn");
    if (button) button.disabled = true;
    var done = 0;
    try {
      for (var i = 0; i < indexes.length; i += 1) {
        var item = lastItems[indexes[i]];
        setStatus("Importando " + (i + 1) + "/" + indexes.length + " (queda inactiva)…");
        var response = await authFetch("/api/proveedores/importar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: item.url, status: false }),
        });
        var data = await response.json().catch(function () { return {}; });
        if (!response.ok || data.ok === false) {
          var detail = data.error || data.detail || response.statusText;
          setStatus("Se frenó en " + item.url + ". " + (typeof detail === "string" ? detail : ""));
          return;
        }
        done += 1;
        var row = document.querySelectorAll("#watch-table-body tr")[indexes[i]];
        if (row) {
          var cell = row.lastElementChild;
          if (cell) {
            cell.textContent = data.created === false ? "ya estaba" : "importado, inactivo";
          }
        }
        if (i < indexes.length - 1) await wait(delayFor(item.provider));
      }
      setStatus(done + " ficha(s) procesadas. Quedan inactivas. No se publicó a Meta.");
    } catch (err) {
      if (typeof isSessionRedirectScheduled !== "function" || !isSessionRedirectScheduled()) {
        setStatus(err && err.message ? err.message : "No se pudo importar.");
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  function bind() {
    var scan = document.getElementById("watch-scan-btn");
    var copy = document.getElementById("watch-copy-btn");
    var importBtn = document.getElementById("watch-import-btn");
    var selectAll = document.getElementById("watch-select-new");
    if (scan) scan.addEventListener("click", runScan);
    if (copy) copy.addEventListener("click", copyUrls);
    if (importBtn) importBtn.addEventListener("click", importSelected);
    if (selectAll) {
      selectAll.addEventListener("change", function () {
        document.querySelectorAll(".watch-pick").forEach(function (input) {
          input.checked = selectAll.checked;
        });
      });
    }
  }

  window.onAdminWatchTab = function () {
    if (!started) {
      started = true;
      runScan();
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
