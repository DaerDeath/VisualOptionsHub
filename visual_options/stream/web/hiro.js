/* HIRO-like: índice acumulado de impacto del flujo de opciones vs precio.
 * Incremento por punto = (put sell % − call sell %) − mediana de la sesión:
 * vender puts empuja al alza, vender calls al techo; el acumulado enseña
 * la presión neta del flujo y sus divergencias con el precio. */
"use strict";

const HiroView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Impacto del flujo (HIRO)</h2>
            <span class="hint">verde = flujo acumulado comprador · blanco = precio · divergencias = aviso</span>
          </div>
          <canvas id="hiroCanvas"></canvas>
        </section>
      </div>`;
    this.panel = new Panel(root.querySelector("#hiroCanvas"), (c, w, h) => this.draw(c, w, h));
    this.attachMouse();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.data = null;
    hideTooltip();
  },

  onData(payload) {
    this.data = payload.flow;
    if (this.panel) this.panel.draw();
  },

  PAD: { l: 46, r: 52, t: 12, b: 22 },

  series() {
    const pts = this.data.series;
    const diffs = pts.map(p => p.put_sell_pct - p.call_sell_pct);
    const sorted = [...diffs].sort((a, b) => a - b);
    const median = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0;
    let acc = 0;
    const hiro = diffs.map(d => (acc += d - median));
    return { pts, hiro };
  },

  draw(ctx, w, h) {
    if (!this.data || this.data.series.length < 2) return;
    const P = this.PAD;
    const { pts, hiro } = this.series();
    const hMax = Math.max(...hiro, 0), hMin = Math.min(...hiro, 0);
    const hPad = (hMax - hMin) * 0.08 + 1;
    const prices = pts.map(p => p.price);
    const pMax = Math.max(...prices), pMin = Math.min(...prices);
    const pPad = (pMax - pMin) * 0.08 + 0.01;
    const x = (i) => P.l + (i / (pts.length - 1)) * (w - P.l - P.r);
    const yH = (v) => P.t + (1 - (v - hMin + hPad) / (hMax - hMin + 2 * hPad)) * (h - P.t - P.b);
    const yP = (v) => P.t + (1 - (v - pMin + pPad) / (pMax - pMin + 2 * pPad)) * (h - P.t - P.b);

    // área del HIRO
    const zero = yH(0);
    ctx.beginPath();
    hiro.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), yH(v)) : ctx.lineTo(x(i), yH(v)));
    ctx.lineTo(x(pts.length - 1), zero);
    ctx.lineTo(x(0), zero);
    ctx.closePath();
    ctx.fillStyle = hiro[hiro.length - 1] >= 0 ? "rgba(47,164,99,0.18)" : "rgba(224,67,63,0.18)";
    ctx.fill();

    ctx.beginPath();
    hiro.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), yH(v)) : ctx.lineTo(x(i), yH(v)));
    ctx.strokeStyle = COLORS.bought;
    ctx.lineWidth = 1.8;
    ctx.stroke();

    ctx.beginPath();
    pts.forEach((p, i) => i === 0 ? ctx.moveTo(x(i), yP(p.price)) : ctx.lineTo(x(i), yP(p.price)));
    ctx.strokeStyle = COLORS.price;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.lineWidth = 1;

    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(P.l, zero); ctx.lineTo(w - P.r, zero); ctx.stroke();

    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let gLine = 0; gLine <= 3; gLine++) {
      const hv = hMin + ((hMax - hMin) / 3) * gLine;
      ctx.fillText(Math.round(hv).toString(), 4, yH(hv) + 3);
      const pv = pMin + ((pMax - pMin) / 3) * gLine;
      ctx.fillText(pv.toFixed(1), w - P.r + 4, yP(pv) + 3);
    }
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(pts.length / 6));
    for (let i = 0; i < pts.length; i += step) ctx.fillText(pts[i].t.slice(0, 5), x(i), h - 6);

    if (this.hover >= 0 && this.hover < pts.length) {
      const i = this.hover;
      ctx.strokeStyle = COLORS.dim;
      ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.moveTo(x(i), P.t); ctx.lineTo(x(i), h - P.b); ctx.stroke();
      ctx.setLineDash([]);
    }
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data || this.data.series.length < 2) return;
      const { pts, hiro } = this.series();
      const P = this.PAD;
      const frac = (e.offsetX - P.l) / (this.panel.w - P.l - P.r);
      const i = clamp(Math.round(frac * (pts.length - 1)), 0, pts.length - 1);
      this.hover = i;
      showTooltip(
        `<div class="tt-title">${pts[i].t}</div>` +
        `<div class="tt-call">HIRO ${Math.round(hiro[i])}</div>` +
        `<div>precio ${pts[i].price.toFixed(2)}</div>`,
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
