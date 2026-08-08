/* Grading: el checklist A-F del Cap. 2, con 10 de los 17 criterios
 * calculados solos desde datos reales; los 7 subjetivos (conocimiento
 * del negocio, estado mental…) se marcan a mano — así lo pide el libro. */
"use strict";

const GradingView = {
  result: null,
  manualFail: new Set(),

  mount(root) {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    root.innerHTML = `
      <div class="fwd-wrap">
        <section class="panel fwd-form">
          <div class="panel-head"><h2>Grading</h2>
            <span class="hint">Cap. 2 · empieza en A, baja un grado por cada criterio incumplido</span></div>
          <div class="calc-controls">
            <label>Símbolo <input id="grSymbol" value="${symbol}" style="text-transform:uppercase"></label>
            <label>Sesgo
              <select id="grBias">
                <option value="bullish">alcista</option>
                <option value="bearish">bajista</option>
                <option value="neutral" selected>neutral (straddle/condor…)</option>
              </select></label>
            <label>Lado
              <select id="grSide">
                <option value="buy">comprador de prima</option>
                <option value="sell">vendedor de prima</option>
              </select></label>
            <button id="grRun" class="btn btn-primary">Calificar</button>
          </div>
          <div class="grade-badge-wrap" id="grBadge"></div>
        </section>
        <section class="panel fwd-steps">
          <div class="panel-head"><h2>Checklist</h2>
            <span class="hint">△ auto — desmarca los criterios subjetivos que no se cumplan</span></div>
          <div class="co-body" id="grItems"><div class="scan-empty">pulsa Calificar</div></div>
        </section>
      </div>`;

    this.el = {
      symbol: root.querySelector("#grSymbol"), bias: root.querySelector("#grBias"),
      side: root.querySelector("#grSide"), run: root.querySelector("#grRun"),
      badge: root.querySelector("#grBadge"), items: root.querySelector("#grItems"),
    };
    this.el.run.addEventListener("click", () => { this.manualFail.clear(); this.run(); });
    this.run();
  },

  unmount() { this.el = null; this.result = null; },
  onData() {},

  async run() {
    this.el.run.disabled = true;
    this.el.items.innerHTML = `<div class="scan-empty">descargando y calculando…</div>`;
    try {
      const symbol = this.el.symbol.value.trim().toUpperCase() || "QQQ";
      const params = new URLSearchParams({
        symbol, bias: this.el.bias.value, side: this.el.side.value,
        manual_fail: [...this.manualFail].join(","),
      });
      const response = await fetch(`/api/grading?${params}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.result = await response.json();
      this.render();
    } catch (err) {
      this.el.items.innerHTML = `<div class="scan-empty">error: ${err.message}</div>`;
      this.el.badge.innerHTML = "";
    } finally {
      this.el.run.disabled = false;
    }
  },

  toggle(key) {
    if (this.manualFail.has(key)) this.manualFail.delete(key);
    else this.manualFail.add(key);
    this.run();
  },

  render() {
    const r = this.result;
    const gradeClass = { A: "pos", B: "pos", C: "", D: "neg", F: "neg" }[r.grade] || "";
    this.el.badge.innerHTML = `
      <div class="grade-big ${gradeClass}">${r.grade}</div>
      <div class="grade-info">
        <div><b>${r.symbol}</b> a $${r.price} · sesgo ${r.bias} · ${r.side === "buy" ? "comprador" : "vendedor"} de prima</div>
        <div>Asignación de cartera: <b>${(r.allocation[0] * 100).toFixed(0)}% – ${(r.allocation[1] * 100).toFixed(0)}%</b></div>
        <div class="tt-dim">${r.guidance}</div>
      </div>`;

    this.el.items.innerHTML = r.items.map(item => {
      const isManualable = item.group === "manual" ||
        (item.value !== null && this.manualFail.has(item.key)) || item.group === "auto";
      const checked = item.value !== false;
      const icon = item.value === null ? "?" : item.value ? "✓" : "✗";
      const cls = item.value === null ? "" : item.value ? "ok" : "fail";
      const toggleTitle = item.group === "manual"
        ? "criterio subjetivo: clic para marcar/desmarcar"
        : "criterio automático: clic para anular si no estás de acuerdo";
      return `
        <div class="grade-item ${cls}" data-key="${item.key}" title="${toggleTitle}">
          <span class="grade-item-icon">${icon}</span>
          <div class="grade-item-body">
            <div class="grade-item-label">${item.label} ${item.group === "auto" ? '<i class="grade-auto-tag">auto</i>' : ""}</div>
            <div class="grade-item-detail">${item.detail}</div>
          </div>
        </div>`;
    }).join("");

    this.el.items.querySelectorAll("[data-key]").forEach(el =>
      el.addEventListener("click", () => this.toggle(el.dataset.key)));
  },
};
