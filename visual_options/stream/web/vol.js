/* Vista de volatilidad: smile de IV por strike, skew, IV ATM y movimiento
 * esperado ±1σ / ±2σ (Volatility Dashboard-like). */
"use strict";

const VolView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="dealer-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Volatilidad</h2>
            <span class="hint">smile de IV por strike · ámbar = spot · bandas = movimiento esperado</span>
            <div class="dealer-totals" id="volTotals"></div>
          </div>
          <canvas id="volCanvas"></canvas>
        </section>
      </div>`;
    this.totalsEl = root.querySelector("#volTotals");
    this.panel = new Panel(root.querySelector("#volCanvas"), (c, w, h) => this.draw(c, w, h));
    this.attachMouse();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.data = null;
    hideTooltip();
  },

  stats() {
    const d = this.data;
    const rows = d.strikes.filter(r => r.iv > 0);
    if (!rows.length) return null;
    const atm = rows.reduce((a, b) =>
      Math.abs(b.strike - d.spot) < Math.abs(a.strike - d.spot) ? b : a);
    const low = rows[0], high = rows[rows.length - 1];
    const skew = (low.iv - high.iv) * 100;  // skew put-call en puntos de IV
    const em1 = d.spot * atm.iv * Math.sqrt(Math.max(d.expiry_days, 0.25) / 365);
    return { rows, atm, skew, em1 };
  },

  onData(payload) {
    this.data = payload.flow;
    const s = this.stats();
    if (s) {
      this.totalsEl.innerHTML =
        `<span class="dtotal">IV ATM ${(s.atm.iv * 100).toFixed(1)}%</span>` +
        `<span class="dtotal ${s.skew >= 0 ? "neg" : "pos"}">skew ${s.skew >= 0 ? "+" : ""}${s.skew.toFixed(1)}pt</span>` +
        `<span class="dtotal">±1σ ${s.em1.toFixed(2)} (${(s.em1 / this.data.spot * 100).toFixed(2)}%)</span>` +
        `<span class="dtotal">${this.data.expiry_days.toFixed(1)}d</span>`;
    }
    if (this.panel) this.panel.draw();
  },

  PAD: { l: 50, r: 14, t: 16, b: 26 },

  draw(ctx, w, h) {
    if (!this.data) return;
    const s = this.stats();
    if (!s) return;
    const P = this.PAD;
    const d = this.data;
    const { rows } = s;
    const ivs = rows.map(r => r.iv * 100);
    const vMax = Math.max(...ivs) * 1.06, vMin = Math.min(...ivs) * 0.94;
    const first = rows[0].strike, last = rows[rows.length - 1].strike;
    const x = (strike) => P.l + ((strike - first) / (last - first)) * (w - P.l - P.r);
    const y = (iv) => P.t + (1 - (iv - vMin) / (vMax - vMin)) * (h - P.t - P.b);

    // bandas de movimiento esperado ±1σ / ±2σ
    for (const [mult, alpha] of [[2, 0.05], [1, 0.09]]) {
      const from = Math.max(first, d.spot - s.em1 * mult);
      const to = Math.min(last, d.spot + s.em1 * mult);
      ctx.fillStyle = `rgba(232, 184, 75, ${alpha})`;
      ctx.fillRect(x(from), P.t, x(to) - x(from), h - P.t - P.b);
    }

    // rejilla y ejes
    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let gLine = 0; gLine <= 4; gLine++) {
      const value = vMin + ((vMax - vMin) / 4) * gLine;
      const yy = y(value);
      ctx.strokeStyle = COLORS.border;
      ctx.globalAlpha = 0.4;
      ctx.beginPath(); ctx.moveTo(P.l, yy); ctx.lineTo(w - P.r, yy); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(value.toFixed(1) + "%", 4, yy + 3);
    }
    ctx.textAlign = "center";
    rows.forEach((r, i) => {
      if (i % Math.ceil(rows.length / 10) === 0) {
        ctx.fillText(String(r.strike), x(r.strike), h - 8);
      }
    });

    // smile
    ctx.beginPath();
    rows.forEach((r, i) => {
      const px = x(r.strike), py = y(r.iv * 100);
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    });
    ctx.strokeStyle = COLORS.call;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;
    rows.forEach((r, i) => {
      ctx.beginPath();
      ctx.arc(x(r.strike), y(r.iv * 100), this.hover === i ? 4.5 : 2.6, 0, Math.PI * 2);
      ctx.fillStyle = this.hover === i ? COLORS.accent : COLORS.call;
      ctx.fill();
    });

    // spot
    ctx.strokeStyle = COLORS.accent;
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(x(d.spot), P.t); ctx.lineTo(x(d.spot), h - P.b); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = COLORS.accent;
    ctx.fillText(d.spot.toFixed(2), x(d.spot), P.t - 4);
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data) return;
      const s = this.stats();
      if (!s) return;
      const P = this.PAD;
      const first = s.rows[0].strike, last = s.rows[s.rows.length - 1].strike;
      const strike = first + ((e.offsetX - P.l) / (this.panel.w - P.l - P.r)) * (last - first);
      const i = s.rows.reduce((best, r, idx) =>
        Math.abs(r.strike - strike) < Math.abs(s.rows[best].strike - strike) ? idx : best, 0);
      this.hover = i;
      const r = s.rows[i];
      showTooltip(
        `<div class="tt-title">Strike ${r.strike}</div>` +
        `<div class="tt-call">IV ${(r.iv * 100).toFixed(2)}%</div>` +
        `<div class="tt-dim">OI C ${fmtK(r.call_oi)} / P ${fmtK(r.put_oi)}</div>`,
        e.clientX, e.clientY);
      this.panel.draw();
    });
    canvas.addEventListener("pointerleave", () => {
      this.hover = -1;
      hideTooltip();
      this.panel.draw();
    });
  },
};
