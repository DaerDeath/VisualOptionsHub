/* Delta acumulado (CVD): suma del delta del footprint vs precio,
 * con detección simple de divergencias. */
"use strict";

const CvdView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Delta acumulado (CVD)</h2>
            <span class="hint">verde = agresión compradora acumulada · blanco = precio · ⚠ = divergencia (precio y CVD en desacuerdo)</span>
          </div>
          <canvas id="cvdCanvas"></canvas>
        </section>
      </div>`;
    this.panel = new Panel(root.querySelector("#cvdCanvas"), (c, w, h) => this.draw(c, w, h));
    this.attachMouse();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.data = null;
    hideTooltip();
  },

  onData(payload) {
    this.data = payload.footprint;
    if (this.panel) this.panel.draw();
  },

  series() {
    const bars = this.data.bars;
    let acc = 0;
    const cvd = bars.map(b => (acc += b.delta));
    // divergencia: en ventanas de 6 barras, precio sube y CVD baja (o al revés)
    const divergences = bars.map((bar, i) => {
      if (i < 6) return false;
      const dPrice = bar.close - bars[i - 6].close;
      const dCvd = cvd[i] - cvd[i - 6];
      const priceMove = Math.abs(dPrice) > (bar.high - bar.low) * 0.8;
      return priceMove && Math.sign(dPrice) !== Math.sign(dCvd) && dCvd !== 0;
    });
    return { bars, cvd, divergences };
  },

  PAD: { l: 56, r: 56, t: 14, b: 24 },

  draw(ctx, w, h) {
    if (!this.data || this.data.bars.length < 2) return;
    const P = this.PAD;
    const { bars, cvd, divergences } = this.series();
    const cMax = Math.max(...cvd, 0), cMin = Math.min(...cvd, 0);
    const cPad = (cMax - cMin) * 0.1 + 1;
    const prices = bars.map(b => b.close);
    const pMax = Math.max(...prices), pMin = Math.min(...prices);
    const pPad = (pMax - pMin) * 0.1 + 0.01;
    const x = (i) => P.l + (i / (bars.length - 1)) * (w - P.l - P.r);
    const yC = (v) => P.t + (1 - (v - cMin + cPad) / (cMax - cMin + 2 * cPad)) * (h - P.t - P.b);
    const yP = (v) => P.t + (1 - (v - pMin + pPad) / (pMax - pMin + 2 * pPad)) * (h - P.t - P.b);

    // área CVD
    const zero = yC(0);
    ctx.beginPath();
    cvd.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), yC(v)) : ctx.lineTo(x(i), yC(v)));
    ctx.lineTo(x(bars.length - 1), zero);
    ctx.lineTo(x(0), zero);
    ctx.closePath();
    ctx.fillStyle = cvd[cvd.length - 1] >= 0 ? "rgba(47,164,99,0.16)" : "rgba(224,67,63,0.16)";
    ctx.fill();
    ctx.beginPath();
    cvd.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), yC(v)) : ctx.lineTo(x(i), yC(v)));
    ctx.strokeStyle = COLORS.bought;
    ctx.lineWidth = 1.9;
    ctx.stroke();

    // precio
    ctx.beginPath();
    bars.forEach((b, i) => i === 0 ? ctx.moveTo(x(i), yP(b.close)) : ctx.lineTo(x(i), yP(b.close)));
    ctx.strokeStyle = COLORS.price;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.lineWidth = 1;

    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(P.l, zero); ctx.lineTo(w - P.r, zero); ctx.stroke();

    // divergencias
    ctx.font = "700 " + MONO;
    ctx.textAlign = "center";
    divergences.forEach((isDiv, i) => {
      if (!isDiv) return;
      ctx.fillStyle = COLORS.accent;
      ctx.fillText("⚠", x(i), yP(bars[i].close) - 10);
    });
    ctx.font = MONO;

    // ejes
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let g = 0; g <= 3; g++) {
      const cv = cMin + ((cMax - cMin) / 3) * g;
      ctx.fillText(fmtK(Math.round(cv)), 4, yC(cv) + 3);
      const pv = pMin + ((pMax - pMin) / 3) * g;
      ctx.fillText(pv.toFixed(2), w - P.r + 6, yP(pv) + 3);
    }
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(bars.length / 8));
    for (let i = 0; i < bars.length; i += step) ctx.fillText(bars[i].t, x(i), h - 7);

    if (this.hover >= 0 && this.hover < bars.length) {
      ctx.strokeStyle = COLORS.dim;
      ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.moveTo(x(this.hover), P.t); ctx.lineTo(x(this.hover), h - P.b); ctx.stroke();
      ctx.setLineDash([]);
    }
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data || this.data.bars.length < 2) return;
      const { bars, cvd, divergences } = this.series();
      const P = this.PAD;
      const i = clamp(Math.round((e.offsetX - P.l) / (this.panel.w - P.l - P.r) * (bars.length - 1)),
                      0, bars.length - 1);
      this.hover = i;
      showTooltip(
        `<div class="tt-title">${bars[i].t}${divergences[i] ? " · ⚠ divergencia" : ""}</div>` +
        `<div>precio ${bars[i].close.toFixed(2)}</div>` +
        `<div class="${cvd[i] >= 0 ? "tt-call" : "tt-put"}">CVD ${fmtK(cvd[i])}</div>` +
        `<div class="tt-dim">Δ barra ${fmtK(bars[i].delta)} · vol ${fmtK(bars[i].volume)}</div>`,
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
