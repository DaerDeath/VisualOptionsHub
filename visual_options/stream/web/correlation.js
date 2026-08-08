/* Correlación (CORR): sensibilidad de los retornos diarios frente a una
 * cesta de índices/sectores/factores — de qué depende realmente el papel. */
"use strict";

const CorrelationView = {
  panel: null,
  result: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Correlación de mercado</h2>
            <span class="hint">retornos diarios de los últimos 90 días vs una cesta de índices/sectores · +1 = se mueve igual, −1 = inverso</span>
            <div class="dealer-totals" id="crTotals"></div>
          </div>
          <canvas id="crCanvas"></canvas>
        </section>
      </div>`;
    this.totalsEl = root.querySelector("#crTotals");
    this.panel = new Panel(root.querySelector("#crCanvas"), (c, w, h) => this.draw(c, w, h));
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
      const response = await fetch(`/api/correlation?symbol=${encodeURIComponent(symbol)}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.result = await response.json();
      const top = this.result.rows[0];
      this.totalsEl.innerHTML =
        `<span class="dtotal">${this.result.symbol}</span>` +
        `<span class="dtotal">${this.result.days} sesiones</span>` +
        `<span class="dtotal pos">más ligado: ${top.peer} (${top.correlation.toFixed(2)})</span>`;
      this.panel.draw();
    } catch (err) {
      this.totalsEl.innerHTML = `<span class="dtotal neg">error: ${err.message}</span>`;
    }
  },

  PAD: { l: 60, r: 50, t: 12, b: 8 },

  draw(ctx, w, h) {
    const r = this.result;
    if (!r || !r.rows.length) return;
    const P = this.PAD;
    const rows = r.rows;
    const rowH = (h - P.t - P.b) / rows.length;
    const center = P.l + (w - P.l - P.r) / 2;
    const half = (w - P.l - P.r) / 2 - 6;

    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(center, P.t); ctx.lineTo(center, h - P.b); ctx.stroke();

    ctx.font = MONO;
    rows.forEach((row, i) => {
      const y = P.t + i * rowH;
      const hot = this.hover === i;
      const bw = half * Math.abs(row.correlation);
      ctx.fillStyle = row.correlation >= 0
        ? (hot ? COLORS.bought : "rgba(47,164,99,0.65)")
        : (hot ? COLORS.sold : "rgba(224,67,63,0.65)");
      if (row.correlation >= 0) ctx.fillRect(center, y + rowH * 0.18, bw, rowH * 0.64);
      else ctx.fillRect(center - bw, y + rowH * 0.18, bw, rowH * 0.64);

      ctx.textAlign = "right";
      ctx.fillStyle = hot ? COLORS.accent : COLORS.text;
      ctx.fillText(row.peer, P.l - 8, y + rowH / 2 + 4);
      ctx.textAlign = "left";
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(row.correlation.toFixed(2), w - P.r + 6, y + rowH / 2 + 4);
    });
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.result) return;
      const rows = this.result.rows;
      const P = this.PAD;
      const rowH = (this.panel.h - P.t - P.b) / rows.length;
      const i = clamp(Math.floor((e.offsetY - P.t) / rowH), 0, rows.length - 1);
      this.hover = i;
      const row = rows[i];
      showTooltip(`<div class="tt-title">${row.peer}</div><div>correlación ${row.correlation.toFixed(3)}</div>`,
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
