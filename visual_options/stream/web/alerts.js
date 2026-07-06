/* Alertas locales: precio cruza nivel, call/put sell % bajo umbral o
 * cruce del gamma flip. Beep + notificación del navegador. Persisten en
 * localStorage y se evalúan con cada tick del stream (en cualquier vista
 * NO — solo mientras la vista de alertas esté abierta o el stream activo
 * en esta pestaña, ya que el chequeo vive en onData del router). */
"use strict";

const AlertsEngine = {
  load() { return JSON.parse(localStorage.getItem("vo-alerts") || "[]"); },
  save(alerts) { localStorage.setItem("vo-alerts", JSON.stringify(alerts)); },
  log() { return JSON.parse(localStorage.getItem("vo-alerts-log") || "[]"); },

  beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
      osc.start(); osc.stop(ctx.currentTime + 0.4);
    } catch (_) { /* sin audio */ }
  },

  fire(alert, flow) {
    const entry = { t: flow.timestamp, symbol: flow.symbol, spot: flow.spot,
                    text: this.describe(alert) };
    const log = this.log();
    log.unshift(entry);
    localStorage.setItem("vo-alerts-log", JSON.stringify(log.slice(0, 50)));
    this.beep();
    if (Notification.permission === "granted") {
      new Notification(`⚡ ${flow.symbol}: ${entry.text}`, { body: `spot ${flow.spot.toFixed(2)} · ${flow.timestamp}` });
    }
    if (typeof AlertsView !== "undefined" && AlertsView.renderLists) AlertsView.renderLists();
  },

  describe(alert) {
    if (alert.type === "price_above") return `precio cruza ↑ ${alert.value}`;
    if (alert.type === "price_below") return `precio cruza ↓ ${alert.value}`;
    if (alert.type === "call_sell_below") return `call sell % < ${alert.value} (posible squeeze)`;
    if (alert.type === "put_sell_below") return `put sell % < ${alert.value}`;
    if (alert.type === "gamma_flip") return `precio cruza el gamma flip`;
    return alert.type;
  },

  check(flow) {
    if (!flow || !flow.spot) return;
    const alerts = this.load();
    let changed = false;
    alerts.forEach(alert => {
      if (alert.done || alert.symbol !== flow.symbol) return;
      const previous = alert.last;
      let hit = false;
      if (alert.type === "price_above") hit = previous !== undefined && previous < alert.value && flow.spot >= alert.value;
      if (alert.type === "price_below") hit = previous !== undefined && previous > alert.value && flow.spot <= alert.value;
      if (alert.type === "call_sell_below") hit = flow.call_sell_pct < alert.value;
      if (alert.type === "put_sell_below") hit = flow.put_sell_pct < alert.value;
      if (alert.type === "gamma_flip" && flow.gamma_flip) {
        hit = previous !== undefined && Math.sign(previous - flow.gamma_flip) !== Math.sign(flow.spot - flow.gamma_flip);
      }
      alert.last = flow.spot;
      changed = true;
      if (hit) { alert.done = true; this.fire(alert, flow); }
    });
    if (changed) this.save(alerts);
  },
};

const AlertsView = {
  mount(root) {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    root.innerHTML = `
      <div class="alerts-wrap">
        <section class="panel">
          <div class="panel-head"><h2>Nueva alerta</h2>
            <span class="hint">se evalúan con cada tick mientras la pestaña esté abierta · beep + notificación</span></div>
          <div class="calc-controls">
            <label>Símbolo <input id="alSymbol" value="${symbol}" style="text-transform:uppercase"></label>
            <label>Condición
              <select id="alType">
                <option value="price_above">precio cruza hacia arriba</option>
                <option value="price_below">precio cruza hacia abajo</option>
                <option value="call_sell_below">call sell % por debajo de…</option>
                <option value="put_sell_below">put sell % por debajo de…</option>
                <option value="gamma_flip">precio cruza el gamma flip</option>
              </select>
            </label>
            <label id="alValueWrap">Valor <input id="alValue" type="number" step="0.01"></label>
            <button id="alAdd" class="btn btn-primary">Añadir alerta</button>
            <div class="tt-dim" id="alPerm"></div>
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
    root.querySelector("#alClearLog").addEventListener("click", () => {
      localStorage.removeItem("vo-alerts-log");
      this.renderLists();
    });
    if (Notification.permission === "default") {
      Notification.requestPermission().then(() => this.renderPermission());
    }
    this.renderPermission();
    this.renderLists();
  },

  unmount() { this.el = null; },
  onData() {},  // el chequeo global lo hace el router en cada tick

  renderPermission() {
    if (!this.el) return;
    this.el.perm.textContent = Notification.permission === "granted"
      ? "notificaciones del navegador activadas"
      : "notificaciones bloqueadas: solo beep + historial";
  },

  add() {
    const type = this.el.type.value;
    const value = parseFloat(this.el.value.value);
    if (type !== "gamma_flip" && !isFinite(value)) return;
    const alerts = AlertsEngine.load();
    alerts.push({ id: Date.now(), symbol: this.el.symbol.value.trim().toUpperCase() || "QQQ",
                  type, value, done: false });
    AlertsEngine.save(alerts);
    this.el.value.value = "";
    this.renderLists();
  },

  renderLists() {
    if (!this.el) return;
    const alerts = AlertsEngine.load();
    this.el.active.innerHTML = alerts.filter(a => !a.done).map(a => `
      <div class="alert-item">
        <b>${a.symbol}</b><span>${AlertsEngine.describe(a)}</span>
        <button class="btn" data-del="${a.id}">✕</button>
      </div>`).join("") || `<div class="scan-empty">sin alertas activas</div>`;
    this.el.active.querySelectorAll("[data-del]").forEach(btn =>
      btn.addEventListener("click", () => {
        AlertsEngine.save(AlertsEngine.load().filter(a => a.id !== Number(btn.dataset.del)));
        this.renderLists();
      }));
    this.el.log.innerHTML = AlertsEngine.log().map(entry => `
      <div class="alert-item fired">
        <b>${entry.symbol}</b><span>${entry.text} · spot ${entry.spot.toFixed(2)}</span>
        <i>${entry.t}</i>
      </div>`).join("") || `<div class="scan-empty">nada disparado todavía</div>`;
  },
};
