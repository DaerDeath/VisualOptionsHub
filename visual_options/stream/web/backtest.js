/* Backtest de venta de rangos (short strangle ±X% OTM cada N sesiones)
 * sobre históricos reales de Yahoo. Primas BSM con vol realizada —
 * aproximación declarada, para comparar parámetros, no para prometer. */
"use strict";

const BacktestView = {
  panel: null,
  result: null,

  mount(root) {
    root.innerHTML = `
      <div class="vwap-wrap">
        <section class="panel" style="flex:0 0 auto">
          <div class="panel-head">
            <h2>Backtest de rangos</h2>
            <span class="hint">vende un strangle ±OTM% cada DTE sesiones y lo lleva a expiración · primas BSM con vol realizada 21d · sin comisiones</span>
            <div class="stats-controls">
              <label class="bt-lbl">OTM % <input id="btOtm" type="number" step="0.5" value="3" style="width:70px"></label>
              <label class="bt-lbl">DTE
                <select id="btDte">
                  <option value="5" selected>5 (semanal)</option>
                  <option value="10">10</option>
                  <option value="21">21 (mensual)</option>
                </select></label>
              <label class="bt-lbl">Años
                <select id="btYears"><option>1</option><option selected>2</option><option>5</option></select></label>
              <button id="btRun" class="btn btn-primary">Ejecutar</button>
            </div>
          </div>
          <div class="vwap-tiles" id="btTiles" style="padding:0.7rem"></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Equity (% acumulado del subyacente)</h2></div>
          <canvas id="btCanvas"></canvas>
        </section>
      </div>`;
    this.el = {
      otm: root.querySelector("#btOtm"), dte: root.querySelector("#btDte"),
      years: root.querySelector("#btYears"), run: root.querySelector("#btRun"),
      tiles: root.querySelector("#btTiles"),
    };
    this.panel = new Panel(root.querySelector("#btCanvas"), (c, w, h) => this.draw(c, w, h));
    this.el.run.addEventListener("click", () => this.run());
    this.run();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.result = null;
    this.el = null;
  },

  onData() {},

  async run() {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    this.el.run.disabled = true;
    this.el.run.textContent = "corriendo…";
    this.el.tiles.innerHTML = `<div class="scan-empty">descargando ${symbol} y simulando…</div>`;
    try {
      const query = `symbol=${symbol}&otm_pct=${this.el.otm.value}&dte=${this.el.dte.value}&years=${this.el.years.value}`;
      const response = await fetch(`/api/backtest?${query}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.result = await response.json();
      const r = this.result;
      const tile = (label, value, cls = "") =>
        `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`;
      this.el.tiles.innerHTML =
        tile("Operaciones", r.n) +
        tile("Win rate", r.win_rate + "%", r.win_rate >= 60 ? "pos" : "") +
        tile("Total", (r.total_pct >= 0 ? "+" : "") + r.total_pct + "%", r.total_pct >= 0 ? "pos" : "neg") +
        tile("Media gana / pierde", `+${r.avg_win}% / ${r.avg_loss}%`) +
        tile("Peor operación", r.worst + "%", "neg") +
        tile("Max drawdown", "−" + r.max_drawdown + "%", "neg") +
        `<div class="vtile" style="grid-column:1/-1"><span>Nota</span><i>${r.note}</i></div>`;
      this.panel.resize();
      this.panel.draw();
    } catch (err) {
      this.el.tiles.innerHTML = `<div class="scan-empty">error: ${err.message}</div>`;
    } finally {
      this.el.run.disabled = false;
      this.el.run.textContent = "Ejecutar";
    }
  },

  PAD: { l: 52, r: 14, t: 12, b: 24 },

  draw(ctx, w, h) {
    const r = this.result;
    if (!r || !r.curve.length) return;
    const P = this.PAD;
    const values = r.curve.map(p => p.equity);
    const hi = Math.max(...values, 0), lo = Math.min(...values, 0);
    const pad = (hi - lo) * 0.08 + 0.1;
    const x = (i) => P.l + (i / (r.curve.length - 1)) * (w - P.l - P.r);
    const y = (v) => P.t + (1 - (v - lo + pad) / (hi - lo + 2 * pad)) * (h - P.t - P.b);

    const zero = y(0);
    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(P.l, zero); ctx.lineTo(w - P.r, zero); ctx.stroke();

    ctx.beginPath();
    values.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
    ctx.lineTo(x(values.length - 1), zero);
    ctx.lineTo(x(0), zero);
    ctx.closePath();
    ctx.fillStyle = values[values.length - 1] >= 0 ? "rgba(47,164,99,0.15)" : "rgba(224,67,63,0.15)";
    ctx.fill();
    ctx.beginPath();
    values.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
    ctx.strokeStyle = values[values.length - 1] >= 0 ? COLORS.bought : COLORS.sold;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let g = 0; g <= 4; g++) {
      const v = lo + ((hi - lo) / 4) * g;
      ctx.fillText(v.toFixed(1) + "%", 4, y(v) + 3);
    }
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(r.curve.length / 6));
    for (let i = 0; i < r.curve.length; i += step) {
      ctx.fillText(r.curve[i].date.slice(2), x(i), h - 7);
    }
  },
};
