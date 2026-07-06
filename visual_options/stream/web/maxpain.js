/* Max Pain: precio de vencimiento que minimiza el pago total a los
 * compradores de opciones (valor intrínseco × OI de toda la cadena). */
"use strict";

const MaxPainView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Max Pain</h2>
            <span class="hint">curva = $ que pagarían los emisores si el precio expira en cada strike · mínimo = max pain · teoría: el precio gravita hacia él cerca del vencimiento</span>
            <div class="dealer-totals" id="mpTotals"></div>
          </div>
          <canvas id="mpCanvas"></canvas>
        </section>
      </div>`;
    this.totalsEl = root.querySelector("#mpTotals");
    this.panel = new Panel(root.querySelector("#mpCanvas"), (c, w, h) => this.draw(c, w, h));
    this.attachMouse();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.data = null;
    hideTooltip();
  },

  compute() {
    const rows = this.data.strikes;
    if (!rows.length) return null;
    const payouts = rows.map(candidate => {
      let total = 0;
      rows.forEach(r => {
        total += r.call_oi * Math.max(0, candidate.strike - r.strike) * 100;
        total += r.put_oi * Math.max(0, r.strike - candidate.strike) * 100;
      });
      return { strike: candidate.strike, payout: total };
    });
    const best = payouts.reduce((a, b) => (b.payout < a.payout ? b : a));
    return { payouts, maxPain: best.strike, minPayout: best.payout };
  },

  onData(payload) {
    this.data = payload.flow;
    const c = this.compute();
    if (c) {
      const dist = (this.data.spot - c.maxPain) / this.data.spot * 100;
      this.totalsEl.innerHTML =
        `<span class="dtotal flip">max pain ${c.maxPain}</span>` +
        `<span class="dtotal">spot ${this.data.spot.toFixed(2)}</span>` +
        `<span class="dtotal ${dist >= 0 ? "neg" : "pos"}">distancia ${dist >= 0 ? "+" : ""}${dist.toFixed(2)}%</span>`;
    }
    if (this.panel) this.panel.draw();
  },

  PAD: { l: 66, r: 16, t: 18, b: 26 },

  draw(ctx, w, h) {
    if (!this.data) return;
    const c = this.compute();
    if (!c) return;
    const P = this.PAD;
    const { payouts } = c;
    const maxPay = Math.max(...payouts.map(p => p.payout));
    const x = (i) => P.l + (i / (payouts.length - 1)) * (w - P.l - P.r);
    const y = (v) => P.t + (1 - v / (maxPay || 1)) * (h - P.t - P.b);

    // área + línea de la curva de pago
    ctx.beginPath();
    payouts.forEach((p, i) => i === 0 ? ctx.moveTo(x(i), y(p.payout)) : ctx.lineTo(x(i), y(p.payout)));
    ctx.lineTo(x(payouts.length - 1), h - P.b);
    ctx.lineTo(x(0), h - P.b);
    ctx.closePath();
    ctx.fillStyle = "rgba(93, 179, 217, 0.12)";
    ctx.fill();
    ctx.beginPath();
    payouts.forEach((p, i) => i === 0 ? ctx.moveTo(x(i), y(p.payout)) : ctx.lineTo(x(i), y(p.payout)));
    ctx.strokeStyle = COLORS.call;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    ctx.font = MONO;
    payouts.forEach((p, i) => {
      const hot = this.hover === i;
      const isPain = p.strike === c.maxPain;
      ctx.beginPath();
      ctx.arc(x(i), y(p.payout), hot || isPain ? 5 : 2.6, 0, Math.PI * 2);
      ctx.fillStyle = isPain ? "#c65dd9" : hot ? COLORS.accent : COLORS.call;
      ctx.fill();
      if (i % Math.ceil(payouts.length / 12) === 0 || isPain) {
        ctx.textAlign = "center";
        ctx.fillStyle = isPain ? "#c65dd9" : COLORS.dim;
        ctx.fillText(String(p.strike), x(i), h - 8);
      }
    });

    // marcador de max pain y spot
    const painIdx = payouts.findIndex(p => p.strike === c.maxPain);
    ctx.strokeStyle = "#c65dd9";
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(x(painIdx), P.t); ctx.lineTo(x(painIdx), h - P.b); ctx.stroke();
    const first = payouts[0].strike, last = payouts[payouts.length - 1].strike;
    if (this.data.spot >= first && this.data.spot <= last) {
      const spotX = P.l + ((this.data.spot - first) / (last - first)) * (w - P.l - P.r);
      ctx.strokeStyle = COLORS.accent;
      ctx.beginPath(); ctx.moveTo(spotX, P.t); ctx.lineTo(spotX, h - P.b); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = COLORS.accent;
      ctx.textAlign = "center";
      ctx.fillText("spot", spotX, P.t - 5);
    }
    ctx.setLineDash([]);

    // eje Y en millones
    ctx.textAlign = "left";
    ctx.fillStyle = COLORS.dim;
    for (let g = 0; g <= 3; g++) {
      const v = (maxPay / 3) * g;
      ctx.fillText("$" + fmtK(Math.round(v)), 4, y(v) + 3);
    }
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data) return;
      const c = this.compute();
      if (!c) return;
      const P = this.PAD;
      const i = clamp(Math.round((e.offsetX - P.l) / (this.panel.w - P.l - P.r) * (c.payouts.length - 1)),
                      0, c.payouts.length - 1);
      this.hover = i;
      const p = c.payouts[i];
      showTooltip(
        `<div class="tt-title">Expiración en ${p.strike}</div>` +
        `<div>pago a compradores: $${fmtK(Math.round(p.payout))}</div>` +
        (p.strike === c.maxPain ? `<div class="tt-dim">← max pain (mínimo pago)</div>` : ""),
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
