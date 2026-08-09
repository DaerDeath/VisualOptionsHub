/* Stress Test del portafolio real: P&L agregado bajo shocks de precio e
 * IV, recalculado con BSM propio (IV resuelta desde el precio reportado
 * de cada posición) — solo lectura, sobre las posiciones que ya tienes. */
"use strict";

const StressView = {
  result: null,
  source: "ibkr",

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Stress Test</h2>
            <span class="hint">P&amp;L de TODO tu portafolio real bajo shocks de precio e IV · BSM propio, IV resuelta desde el precio de cada posición</span>
            <div class="stats-controls">
              <button class="srcbtn active" data-src="ibkr">IBKR</button>
              <button class="srcbtn" data-src="tradier">Tradier</button>
              <button id="stRefresh" class="btn">↻ recalcular</button>
            </div>
          </div>
          <div class="vwap-tiles" id="stTiles" style="padding:0.7rem"></div>
          <div class="co-body" id="stMatrix" style="flex:1"></div>
        </section>
      </div>`;
    this.tilesEl = root.querySelector("#stTiles");
    this.matrixEl = root.querySelector("#stMatrix");
    // scopeado a `root`: el header global también tiene botones con
    // data-src (fuente de mercado) que no deben pisar este estado.
    root.querySelectorAll("[data-src]").forEach(btn => btn.addEventListener("click", () => {
      this.source = btn.dataset.src;
      root.querySelectorAll("[data-src]").forEach(b => b.classList.toggle("active", b === btn));
      this.load();
    }));
    root.querySelector("#stRefresh").addEventListener("click", () => this.load());
    this.load();
  },

  unmount() { this.result = null; },
  onData() {},

  fmt(v) { return v.toLocaleString(undefined, { maximumFractionDigits: 0 }); },

  async load() {
    this.matrixEl.innerHTML = `<div class="scan-empty">leyendo posiciones y calculando escenarios (puede tardar unos segundos)…</div>`;
    this.tilesEl.innerHTML = "";
    try {
      const response = await fetch(`/api/stress?source=${this.source}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.render(await response.json());
    } catch (err) {
      this.matrixEl.innerHTML = `<div class="scan-empty">${err.message}</div>`;
    }
  },

  render(d) {
    const tile = (label, value, cls = "") => `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`;
    this.tilesEl.innerHTML =
      tile("Cuenta", d.account || "—") +
      tile("Posiciones", d.n_positions) +
      tile("Modeladas con BSM", d.modeled_bsm) +
      tile("Modeladas por delta", d.modeled_linear) +
      tile("Sin modelar", d.unmodeled, d.unmodeled > 0 ? "neg" : "") +
      tile("Valor actual", "$" + this.fmt(d.base_market_value));

    if (!d.n_positions) {
      this.matrixEl.innerHTML = `<div class="scan-empty">sin posiciones abiertas — nada que estresar</div>`;
      return;
    }

    const allValues = d.matrix.flatMap(r => r.pnl);
    const maxAbs = Math.max(1, ...allValues.map(Math.abs));
    const cellColor = (v) => {
      const intensity = Math.min(1, Math.abs(v) / maxAbs);
      return v >= 0 ? `rgba(47,164,99,${0.12 + intensity * 0.6})` : `rgba(224,67,63,${0.12 + intensity * 0.6})`;
    };

    let html = `<table class="scan-table stress-table"><thead><tr><th>IV \\ Spot</th>`;
    d.spot_shocks.forEach(s => { html += `<th>${s >= 0 ? "+" : ""}${(s * 100).toFixed(1)}%</th>`; });
    html += `</tr></thead><tbody>`;
    d.matrix.forEach(row => {
      html += `<tr><td class="scan-sym">${row.iv_shock >= 0 ? "+" : ""}${(row.iv_shock * 100).toFixed(0)}%</td>`;
      row.pnl.forEach((v, i) => {
        const isZero = d.spot_shocks[i] === 0 && row.iv_shock === 0;
        html += `<td style="background:${cellColor(v)}" class="${isZero ? "stress-zero" : ""}">${v >= 0 ? "+" : ""}$${this.fmt(v)}</td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table>`;
    this.matrixEl.innerHTML = html;
  },
};
