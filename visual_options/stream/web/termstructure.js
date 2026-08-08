/* Estructura de plazos (TRMS): IV ATM por vencimiento — contango o
 * backwardation. Datos estáticos por símbolo (no sigue el stream). */
"use strict";

const TermStructureView = {
  panel: null,
  result: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Estructura de plazos de IV</h2>
            <span class="hint">IV ATM por vencimiento · contango (sube con el plazo) = normal · backwardation (baja) = estrés a corto plazo</span>
            <div class="dealer-totals" id="tsTotals"></div>
          </div>
          <canvas id="tsCanvas"></canvas>
        </section>
      </div>`;
    this.totalsEl = root.querySelector("#tsTotals");
    this.panel = new Panel(root.querySelector("#tsCanvas"), (c, w, h) => this.draw(c, w, h));
    this.attachMouse();
    this.load();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.result = null;
  },

  onData() {},

  async load() {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    this.totalsEl.innerHTML = `<span class="dtotal">cargando ${symbol}…</span>`;
    try {
      const response = await fetch(`/api/term-structure?symbol=${encodeURIComponent(symbol)}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.result = await response.json();
      const r = this.result;
      this.totalsEl.innerHTML =
        `<span class="dtotal">${r.symbol} spot ${r.spot.toFixed(2)}</span>` +
        `<span class="dtotal ${r.contango >= 0 ? "pos" : "neg"}">${r.shape} (${r.contango >= 0 ? "+" : ""}${(r.contango * 100).toFixed(2)}pt)</span>`;
      this.panel.draw();
    } catch (err) {
      this.totalsEl.innerHTML = `<span class="dtotal neg">error: ${err.message}</span>`;
    }
  },

  PAD: { l: 54, r: 16, t: 16, b: 26 },

  draw(ctx, w, h) {
    const r = this.result;
    if (!r || !r.points.length) return;
    const P = this.PAD;
    const pts = r.points;
    const ivMax = Math.max(...pts.map(p => p.iv)) * 1.08;
    const ivMin = Math.min(...pts.map(p => p.iv)) * 0.92;
    const x = (i) => P.l + (i / Math.max(1, pts.length - 1)) * (w - P.l - P.r);
    const y = (v) => P.t + (1 - (v - ivMin) / (ivMax - ivMin)) * (h - P.t - P.b);

    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let g = 0; g <= 4; g++) {
      const v = ivMin + ((ivMax - ivMin) / 4) * g;
      const yy = y(v);
      ctx.strokeStyle = COLORS.border;
      ctx.globalAlpha = 0.4;
      ctx.beginPath(); ctx.moveTo(P.l, yy); ctx.lineTo(w - P.r, yy); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText((v * 100).toFixed(1) + "%", 4, yy + 3);
    }

    ctx.beginPath();
    pts.forEach((p, i) => i === 0 ? ctx.moveTo(x(i), y(p.iv)) : ctx.lineTo(x(i), y(p.iv)));
    ctx.strokeStyle = COLORS.call;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    ctx.textAlign = "center";
    pts.forEach((p, i) => {
      const hot = this.hover === i;
      ctx.beginPath();
      ctx.arc(x(i), y(p.iv), hot ? 5.5 : 3.2, 0, Math.PI * 2);
      ctx.fillStyle = hot ? COLORS.accent : COLORS.call;
      ctx.fill();
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(`${p.days}d`, x(i), h - 8);
    });
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.result) return;
      const pts = this.result.points;
      const P = this.PAD;
      const i = clamp(Math.round((e.offsetX - P.l) / (this.panel.w - P.l - P.r) * (pts.length - 1)),
                      0, pts.length - 1);
      this.hover = i;
      const p = pts[i];
      showTooltip(
        `<div class="tt-title">${p.expiry}</div>` +
        `<div>${p.days} días · IV ${(p.iv * 100).toFixed(2)}%</div>`,
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
