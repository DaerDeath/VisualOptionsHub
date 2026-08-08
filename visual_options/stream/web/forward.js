/* Forward Price & Cost of Carry (NOVM): el método exacto del Cap. 2 del
 * libro, paso a paso con números reales — interés simple, no
 * capitalización continua. Editable: días y tasa libre de riesgo. */
"use strict";

const ForwardView = {
  result: null,

  mount(root) {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    root.innerHTML = `
      <div class="fwd-wrap">
        <section class="panel fwd-form">
          <div class="panel-head"><h2>Forward &amp; Cost of Carry</h2>
            <span class="hint">NOVM · método del libro (interés simple)</span></div>
          <div class="calc-controls">
            <label>Símbolo <input id="fwSymbol" value="${symbol}" style="text-transform:uppercase"></label>
            <label>Días a vencimiento <input id="fwDays" type="number" placeholder="auto (próximo vencimiento)"></label>
            <label>Tasa libre de riesgo % <input id="fwRate" type="number" step="0.01" placeholder="auto (T-bill 13 sem.)"></label>
            <button id="fwRun" class="btn btn-primary">Calcular</button>
            <div class="tt-dim" id="fwMeta"></div>
          </div>
          <div class="fwd-formulas">
            <p><b>Cost of Carry</b> = (Spot × tasa × días/365) − Dividendos hasta el vencimiento</p>
            <p><b>Forward Price</b> = Spot + Cost of Carry</p>
            <p class="tt-dim">Si el forward &lt; spot (dividendos &gt; interés), los puts ATM valen más que los calls;
            si el forward &gt; spot (interés &gt; dividendos), los calls valen más — es la base del put-call parity.</p>
          </div>
        </section>
        <section class="panel fwd-steps">
          <div class="panel-head"><h2>Desglose paso a paso</h2>
            <span class="hint">como el ejemplo de IBM del libro</span></div>
          <div class="co-body" id="fwSteps"><div class="scan-empty">pulsa Calcular</div></div>
        </section>
      </div>`;

    this.el = {
      symbol: root.querySelector("#fwSymbol"), days: root.querySelector("#fwDays"),
      rate: root.querySelector("#fwRate"), run: root.querySelector("#fwRun"),
      meta: root.querySelector("#fwMeta"), steps: root.querySelector("#fwSteps"),
    };
    this.el.run.addEventListener("click", () => this.run());
    this.run();
  },

  unmount() { this.el = null; this.result = null; },
  onData() {},

  async run() {
    this.el.run.disabled = true;
    this.el.run.textContent = "calculando…";
    this.el.steps.innerHTML = `<div class="scan-empty">descargando datos…</div>`;
    try {
      const symbol = this.el.symbol.value.trim().toUpperCase() || "QQQ";
      const params = new URLSearchParams({ symbol });
      if (this.el.days.value) params.set("days", this.el.days.value);
      if (this.el.rate.value) params.set("rate", (parseFloat(this.el.rate.value) / 100).toString());
      const response = await fetch(`/api/forward?${params}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.result = await response.json();
      this.render();
    } catch (err) {
      this.el.steps.innerHTML = `<div class="scan-empty">error: ${err.message}</div>`;
    } finally {
      this.el.run.disabled = false;
      this.el.run.textContent = "Calcular";
    }
  },

  render() {
    const r = this.result;
    this.el.days.placeholder = `${r.days} (auto)`;
    this.el.rate.placeholder = `${(r.rate * 100).toFixed(3)} (auto)`;
    this.el.meta.textContent = `tasa: ${r.rate_source} · dividendo anual estimado $${r.annual_dividend.toFixed(2)}`;

    const stepsHtml = r.steps.map((s, i) => `
      <div class="fwd-step">
        <div class="fwd-step-n">${i + 1}</div>
        <div class="fwd-step-body">
          <div class="fwd-step-label">${s.label}</div>
          <div class="fwd-step-formula">${s.formula}${s.detail ? ` = ${s.detail}` : ""}</div>
        </div>
        <div class="fwd-step-value">${s.value.toFixed(4)}</div>
      </div>`).join("");

    const tile = (label, value, cls = "") =>
      `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`;

    this.el.steps.innerHTML = `
      <div class="fwd-steps-list">${stepsHtml}</div>
      <div class="vwap-tiles" style="margin-top:0.9rem">
        ${tile("Forward (interés simple)", r.forward_simple.toFixed(4), "pos")}
        ${tile("Forward (capitalización continua)", r.forward_continuous.toFixed(4))}
        ${tile("Spot actual", r.spot.toFixed(4))}
        ${tile("Put ATM − Call ATM (aprox.)", (r.put_over_call_atm >= 0 ? "+" : "") + r.put_over_call_atm.toFixed(4),
               r.put_over_call_atm >= 0 ? "neg" : "pos")}
      </div>
      <p class="co-summary">${r.carry_direction}.</p>`;
  },
};
