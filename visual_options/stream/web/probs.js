/* Probabilidades: cono de movimiento esperado ±1σ/±2σ sobre el precio y
 * tabla de probabilidad de expirar ITM por strike (lognormal con su IV). */
"use strict";

function erf(x) {
  // aproximación de Abramowitz-Stegun (|err| < 1.5e-7)
  const sign = x >= 0 ? 1 : -1;
  x = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * x);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
  return sign * y;
}
const normCdf = (x) => 0.5 * (1 + erf(x / Math.SQRT2));

const ProbsView = {
  data: null,
  panel: null,

  mount(root) {
    root.innerHTML = `
      <div class="probs-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Cono de movimiento esperado</h2>
            <span class="hint">±1σ = 68% de probabilidad de quedar dentro · ±2σ = 95% (según lognormal con IV ATM)</span>
          </div>
          <canvas id="probsCanvas"></canvas>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Prob. de expirar ITM por strike</h2>
            <span class="hint">con la IV propia de cada strike · vender ~16% ITM ≈ 1σ</span></div>
          <div class="scan-table-wrap"><table class="scan-table">
            <thead><tr><th>Strike</th><th>IV</th><th>P(call ITM)</th><th>P(put ITM)</th><th></th></tr></thead>
            <tbody id="probsBody"></tbody>
          </table></div>
        </section>
      </div>`;
    this.body = root.querySelector("#probsBody");
    this.panel = new Panel(root.querySelector("#probsCanvas"), (c, w, h) => this.draw(c, w, h));
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.data = null;
  },

  probItm(kind, spot, strike, iv, tYears) {
    if (tYears <= 0 || iv <= 0 || spot <= 0) return null;
    const d2 = (Math.log(spot / strike) + (0.04 - 0.5 * iv * iv) * tYears) / (iv * Math.sqrt(tYears));
    return kind === "call" ? normCdf(d2) : normCdf(-d2);
  },

  onData(payload) {
    this.data = payload.flow;
    this.renderTable();
    if (this.panel) this.panel.draw();
  },

  renderTable() {
    const d = this.data;
    if (!this.body || !d.strikes.length) return;
    const t = Math.max(d.expiry_days, 0.05) / 365;
    const rows = [...d.strikes].sort((a, b) => b.strike - a.strike);
    this.body.innerHTML = rows.map(r => {
      const iv = r.iv > 0 ? r.iv : 0.2;
      const pc = this.probItm("call", d.spot, r.strike, iv, t);
      const pp = this.probItm("put", d.spot, r.strike, iv, t);
      const atm = Math.abs(r.strike - d.spot) <= (rows[0].strike - rows[1].strike) / 2;
      const near16 = pc !== null && (Math.abs(pc - 0.16) < 0.04 || Math.abs(pp - 0.16) < 0.04);
      return `<tr class="${atm ? "tape-big" : ""}">
        <td class="scan-sym">${r.strike}</td>
        <td>${(iv * 100).toFixed(1)}%</td>
        <td class="${pc > 0.5 ? "pos" : ""}">${(pc * 100).toFixed(1)}%</td>
        <td class="${pp > 0.5 ? "neg" : ""}">${(pp * 100).toFixed(1)}%</td>
        <td>${atm ? "← ATM" : near16 ? "≈1σ" : ""}</td>
      </tr>`;
    }).join("");
  },

  PAD: { l: 14, r: 58, t: 14, b: 24 },

  draw(ctx, w, h) {
    const d = this.data;
    if (!d || d.series.length < 2) return;
    const P = this.PAD;
    const pts = d.series;
    const atm = d.strikes.length
      ? d.strikes.reduce((a, b) => Math.abs(b.strike - d.spot) < Math.abs(a.strike - d.spot) ? b : a)
      : null;
    const iv = atm && atm.iv > 0 ? atm.iv : 0.2;
    const horizon = Math.max(d.expiry_days, 0.1);
    const coneSteps = 24;
    const em = (frac) => d.spot * iv * Math.sqrt(horizon * frac / 365);

    // escala: histórico ocupa el 55% del ancho; el cono, el resto
    const histW = (w - P.l - P.r) * 0.55;
    const allPrices = pts.map(p => p.price)
      .concat([d.spot + 2 * em(1), d.spot - 2 * em(1)]);
    const pMax = Math.max(...allPrices), pMin = Math.min(...allPrices);
    const pad = (pMax - pMin) * 0.06;
    const y = (v) => P.t + (1 - (v - pMin + pad) / (pMax - pMin + 2 * pad)) * (h - P.t - P.b);
    const xHist = (i) => P.l + (i / (pts.length - 1)) * histW;
    const xCone = (frac) => P.l + histW + frac * (w - P.l - P.r - histW);

    // bandas del cono
    for (const [mult, color] of [[2, "rgba(232,184,75,0.10)"], [1, "rgba(232,184,75,0.20)"]]) {
      ctx.beginPath();
      ctx.moveTo(xCone(0), y(d.spot));
      for (let s = 1; s <= coneSteps; s++) {
        ctx.lineTo(xCone(s / coneSteps), y(d.spot + mult * em(s / coneSteps)));
      }
      for (let s = coneSteps; s >= 0; s--) {
        ctx.lineTo(xCone(s / coneSteps), y(d.spot - mult * em(s / coneSteps)));
      }
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    }

    // precio histórico
    ctx.beginPath();
    pts.forEach((p, i) => i === 0 ? ctx.moveTo(xHist(i), y(p.price)) : ctx.lineTo(xHist(i), y(p.price)));
    ctx.strokeStyle = COLORS.price;
    ctx.lineWidth = 1.8;
    ctx.stroke();
    ctx.lineWidth = 1;

    // etiquetas de los bordes del cono
    ctx.font = MONO;
    ctx.textAlign = "left";
    for (const [mult, label] of [[1, "±1σ"], [2, "±2σ"]]) {
      ctx.fillStyle = COLORS.accent;
      ctx.fillText(`${label} ${(d.spot + mult * em(1)).toFixed(2)}`, w - P.r + 4, y(d.spot + mult * em(1)) + 3);
      ctx.fillText((d.spot - mult * em(1)).toFixed(2), w - P.r + 4, y(d.spot - mult * em(1)) + 3);
    }
    ctx.fillStyle = COLORS.text;
    ctx.fillText(d.spot.toFixed(2), w - P.r + 4, y(d.spot) + 3);
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "center";
    ctx.fillText("ahora", P.l + histW, h - 8);
    ctx.fillText(`+${horizon.toFixed(1)}d (IV ${(iv * 100).toFixed(0)}%)`, xCone(0.85), h - 8);
    ctx.strokeStyle = COLORS.border;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(P.l + histW, P.t); ctx.lineTo(P.l + histW, h - P.b); ctx.stroke();
    ctx.setLineDash([]);
  },
};
