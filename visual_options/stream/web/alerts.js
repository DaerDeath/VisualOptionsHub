/* Alertas server-side: viven en el servidor y disparan notificación de
 * escritorio (notify-send) aunque el navegador esté cerrado — solo hace
 * falta que el servidor corra y la sesión del símbolo esté activa. */
"use strict";

const ALERT_LABELS = {
  price_above: "precio cruza hacia arriba",
  price_below: "precio cruza hacia abajo",
  call_sell_below: "call sell % por debajo de…",
  put_sell_below: "put sell % por debajo de…",
  gamma_flip: "precio cruza el gamma flip",
};

function describeAlert(a) {
  if (a.type === "price_above") return `precio cruza ↑ ${a.value}`;
  if (a.type === "price_below") return `precio cruza ↓ ${a.value}`;
  if (a.type === "call_sell_below") return `call sell % < ${a.value} (posible squeeze)`;
  if (a.type === "put_sell_below") return `put sell % < ${a.value}`;
  if (a.type === "gamma_flip") return "precio cruza el gamma flip";
  return a.type;
}

const AlertsView = {
  timer: null,

  mount(root) {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    root.innerHTML = `
      <div class="alerts-wrap">
        <section class="panel">
          <div class="panel-head"><h2>Nueva alerta</h2>
            <span class="hint">se evalúan EN EL SERVIDOR con cada tick — disparan aunque cierres el navegador</span></div>
          <div class="calc-controls">
            <label>Símbolo <input id="alSymbol" value="${symbol}" style="text-transform:uppercase"></label>
            <label>Condición
              <select id="alType">
                ${Object.entries(ALERT_LABELS).map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}
              </select>
            </label>
            <label id="alValueWrap">Valor <input id="alValue" type="number" step="0.01"></label>
            <button id="alAdd" class="btn btn-primary">Añadir alerta</button>
            <div class="tt-dim" id="alPerm"></div>
            <div class="tt-dim">ojo: la alerta necesita que la sesión de su símbolo esté viva
            (alguna pestaña la ha abierto, o el scanner la mantiene).</div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Activas</h2></div>
          <div class="alerts-list" id="alActive"></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Historial de disparos</h2>
            <button id="alClearLog" class="btn" style="margin-left:auto">limpiar</button></div>
          <div class="alerts-list" id="alLog"></div>
        </section>
      </div>`;

    this.el = {
      symbol: root.querySelector("#alSymbol"), type: root.querySelector("#alType"),
      value: root.querySelector("#alValue"), valueWrap: root.querySelector("#alValueWrap"),
      active: root.querySelector("#alActive"), log: root.querySelector("#alLog"),
      perm: root.querySelector("#alPerm"),
    };
    this.el.type.addEventListener("change", () => {
      this.el.valueWrap.style.display = this.el.type.value === "gamma_flip" ? "none" : "";
    });
    root.querySelector("#alAdd").addEventListener("click", () => this.add());
    root.querySelector("#alClearLog").addEventListener("click", async () => {
      await fetch("/api/alerts/log", { method: "DELETE" });
      this.refresh();
    });
    this.refresh();
    this.timer = setInterval(() => this.refresh(), 4000);
  },

  unmount() {
    clearInterval(this.timer);
    this.timer = null;
    this.el = null;
  },

  onData() {},  // el chequeo vive en el servidor

  async add() {
    const type = this.el.type.value;
    const value = parseFloat(this.el.value.value);
    if (type !== "gamma_flip" && !isFinite(value)) return;
    await fetch("/api/alerts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: this.el.symbol.value.trim().toUpperCase() || "QQQ",
        type, value: isFinite(value) ? value : null,
      }),
    });
    this.el.value.value = "";
    this.refresh();
  },

  async refresh() {
    if (!this.el) return;
    try {
      const data = await fetch("/api/alerts").then(r => r.json());
      this.el.perm.textContent = data.desktop
        ? "notificaciones de escritorio activas (notify-send)"
        : "notify-send no disponible: solo historial";
      this.el.active.innerHTML = data.active.map(a => `
        <div class="alert-item">
          <b>${a.symbol}</b><span>${describeAlert(a)}</span>
          <button class="btn" data-del="${a.id}">✕</button>
        </div>`).join("") || `<div class="scan-empty">sin alertas activas</div>`;
      this.el.active.querySelectorAll("[data-del]").forEach(btn =>
        btn.addEventListener("click", async () => {
          await fetch(`/api/alerts/${btn.dataset.del}`, { method: "DELETE" });
          this.refresh();
        }));
      this.el.log.innerHTML = data.log.map(entry => `
        <div class="alert-item fired">
          <b>${entry.symbol}</b><span>${entry.text} · spot ${entry.spot.toFixed(2)}</span>
          <i>${entry.ts}</i>
        </div>`).join("") || `<div class="scan-empty">nada disparado todavía</div>`;
    } catch (_) { /* siguiente ciclo */ }
  },
};
