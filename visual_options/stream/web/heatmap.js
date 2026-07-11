/* Heatmap GEX (TRACE-like): tiempo × strike con color por Net GEX
 * (verde amortigua, rojo acelera) y el recorrido del spot superpuesto. */
"use strict";

const HeatmapView = {
  data: null,
  panel: null,
  hover: { col: -1, row: -1 },

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Heatmap GEX</h2>
            <span class="hint">tiempo × strike · verde frena · rojo acelera · blanca = spot · ${ZOOM_HINT}</span>
          </div>
          <canvas id="hmCanvas"></canvas>
        </section>
      </div>`;
    this.panel = new Panel(root.querySelector("#hmCanvas"), (c, w, h) => this.draw(c, w, h));
    this.vp = new BarViewport(() => this.panel && this.panel.draw());
    this.vp.attach(this.panel.canvas, {
      total: () => (this.data ? this.data.gex_history.length : 0),
      defaultCount: () => (this.data ? this.data.gex_history.length : 1),
      plot: () => [this.PAD.l, this.panel.w - this.PAD.l - this.PAD.r],
    });
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

  PAD: { l: 8, r: 58, t: 10, b: 24 },

  geometry(w, h) {
    const all = this.data.gex_history;
    const strikes = this.data.strikes.map(r => r.strike); // ascendente
    if (!all.length || !strikes.length) return null;
    const range = this.vp ? this.vp.view(all.length, all.length)
                          : { start: 0, end: all.length };
    const history = all.slice(range.start, range.end);
    if (!history.length) return null;
    const P = this.PAD;
    const colW = (w - P.l - P.r) / history.length;
    const rowH = (h - P.t - P.b) / strikes.length;
    const maxAbs = Math.max(1e-9, ...history.flatMap(col => col.gex.map(Math.abs)));
    return { history, strikes, colW, rowH, maxAbs };
  },

  draw(ctx, w, h) {
    if (!this.data) return;
    const g = this.geometry(w, h);
    if (!g) return;
    const P = this.PAD;
    const { history, strikes, colW, rowH, maxAbs } = g;
    const n = strikes.length;

    history.forEach((col, ci) => {
      const x = P.l + ci * colW;
      col.gex.forEach((value, si) => {
        if (si >= n) return;
        const y = P.t + (n - 1 - si) * rowH;  // strike alto arriba
        const intensity = Math.pow(Math.abs(value) / maxAbs, 0.55);
        ctx.fillStyle = value >= 0
          ? `rgba(47, 164, 99, ${0.06 + intensity * 0.85})`
          : `rgba(224, 67, 63, ${0.06 + intensity * 0.85})`;
        ctx.fillRect(x, y, colW + 0.6, rowH + 0.6);
      });
    });

    // recorrido del spot
    const hi = strikes[n - 1], lo = strikes[0];
    ctx.beginPath();
    let started = false;
    history.forEach((col, ci) => {
      if (col.spot < lo || col.spot > hi) return;
      const x = P.l + ci * colW + colW / 2;
      const y = P.t + ((hi - col.spot) / (hi - lo)) * (rowH * (n - 1)) + rowH / 2;
      started ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      started = true;
    });
    ctx.strokeStyle = COLORS.price;
    ctx.lineWidth = 1.8;
    ctx.stroke();
    ctx.lineWidth = 1;

    // gamma flip actual
    if (this.data.gamma_flip !== null && this.data.gamma_flip >= lo && this.data.gamma_flip <= hi) {
      const y = P.t + ((hi - this.data.gamma_flip) / (hi - lo)) * (rowH * (n - 1)) + rowH / 2;
      ctx.strokeStyle = "#c65dd9";
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(P.l, y); ctx.lineTo(w - P.r, y); ctx.stroke();
      ctx.setLineDash([]);
    }

    // ejes
    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    const rowStep = Math.ceil(n / Math.max(1, Math.floor((h - P.t - P.b) / 20)));
    for (let si = 0; si < n; si += rowStep) {
      const y = P.t + (n - 1 - si) * rowH + rowH / 2;
      ctx.fillText(String(strikes[si]), w - P.r + 6, y + 3);
    }
    ctx.textAlign = "center";
    const colStep = Math.max(1, Math.floor(history.length / 7));
    for (let ci = 0; ci < history.length; ci += colStep) {
      ctx.fillText(history[ci].t.slice(0, 5), P.l + ci * colW + colW / 2, h - 8);
    }

    if (this.hover.col >= 0 && this.hover.row >= 0) {
      ctx.strokeStyle = COLORS.accent;
      ctx.strokeRect(P.l + this.hover.col * colW, P.t + this.hover.row * rowH, colW, rowH);
    }
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data) return;
      if (this.vp && this.vp.dragging) { hideTooltip(); return; }
      const g = this.geometry(this.panel.w, this.panel.h);
      if (!g) return;
      const P = this.PAD;
      const col = clamp(Math.floor((e.offsetX - P.l) / g.colW), 0, g.history.length - 1);
      const row = clamp(Math.floor((e.offsetY - P.t) / g.rowH), 0, g.strikes.length - 1);
      this.hover = { col, row };
      const strikeIdx = g.strikes.length - 1 - row;
      const entry = g.history[col];
      const value = entry.gex[strikeIdx];
      showTooltip(
        `<div class="tt-title">${entry.t} · strike ${g.strikes[strikeIdx]}</div>` +
        `<div class="${value >= 0 ? "tt-call" : "tt-put"}">Net GEX ${value >= 0 ? "+" : ""}${value?.toFixed(1)} M$</div>` +
        `<div class="tt-dim">spot ${entry.spot.toFixed(2)}</div>`,
        e.clientX, e.clientY);
      this.panel.draw();
    });
    canvas.addEventListener("pointerleave", () => {
      this.hover = { col: -1, row: -1 };
      hideTooltip();
      this.panel.draw();
    });
  },
};
