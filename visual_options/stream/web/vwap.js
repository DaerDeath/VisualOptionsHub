/* VWAP + resumen de sesión: velas con VWAP y bandas ±1σ/±2σ ponderadas
 * por volumen, más tiles con las estadísticas de la sesión. */
"use strict";

const VwapView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="vwap-wrap">
        <div class="vwap-tiles" id="vwapTiles"></div>
        <section class="panel">
          <div class="panel-head">
            <h2>VWAP + bandas</h2>
            <span class="hint">ámbar = VWAP · bandas ±1σ/±2σ ponderadas por volumen · ${ZOOM_HINT}</span>
          </div>
          <canvas id="vwapCanvas"></canvas>
        </section>
      </div>`;
    this.tilesEl = root.querySelector("#vwapTiles");
    this.panel = new Panel(root.querySelector("#vwapCanvas"), (c, w, h) => this.draw(c, w, h));
    this.vp = new BarViewport(() => this.panel && this.panel.draw());
    this.vp.attach(this.panel.canvas, {
      total: () => (this.data ? this.data.bars.length : 0),
      defaultCount: () => (this.data ? this.data.bars.length : 1),
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

  series() {
    const bars = this.data.bars;
    let sumPV = 0, sumV = 0, sumP2V = 0;
    return bars.map(bar => {
      const typical = (bar.high + bar.low + bar.close) / 3;
      sumPV += typical * bar.volume;
      sumP2V += typical * typical * bar.volume;
      sumV += bar.volume;
      const vwap = sumV ? sumPV / sumV : typical;
      const variance = sumV ? Math.max(0, sumP2V / sumV - vwap * vwap) : 0;
      return { vwap, sd: Math.sqrt(variance) };
    });
  },

  onData(payload) {
    this.data = payload.footprint;
    this.renderTiles();
    if (this.panel) this.panel.draw();
  },

  renderTiles() {
    const bars = this.data.bars;
    if (!this.tilesEl || !bars.length) return;
    const first = bars[0], last = bars[bars.length - 1];
    const hi = Math.max(...bars.map(b => b.high));
    const lo = Math.min(...bars.map(b => b.low));
    const totalVol = bars.reduce((a, b) => a + b.volume, 0);
    const totalDelta = bars.reduce((a, b) => a + b.delta, 0);
    const bullPct = 100 * bars.filter(b => b.close >= b.open).length / bars.length;
    const change = last.close - first.open;
    const vwapNow = this.series()[bars.length - 1].vwap;
    const tile = (label, value, cls = "") =>
      `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`;
    this.tilesEl.innerHTML =
      tile("Cambio", `${change >= 0 ? "+" : ""}${change.toFixed(2)}`, change >= 0 ? "pos" : "neg") +
      tile("Rango", `${lo.toFixed(2)} – ${hi.toFixed(2)} (${(hi - lo).toFixed(2)})`) +
      tile("Volumen", fmtK(totalVol)) +
      tile("Δ total", (totalDelta >= 0 ? "+" : "") + fmtK(totalDelta), totalDelta >= 0 ? "pos" : "neg") +
      tile("Barras alcistas", bullPct.toFixed(0) + "%") +
      tile("VWAP", vwapNow.toFixed(2), last.close >= vwapNow ? "pos" : "neg") +
      tile("vs VWAP", `${last.close >= vwapNow ? "encima" : "debajo"} (${(last.close - vwapNow).toFixed(2)})`,
           last.close >= vwapNow ? "pos" : "neg");
  },

  PAD: { l: 12, r: 58, t: 14, b: 24 },

  visibleRange(w) {
    const all = this.data.bars;
    return this.vp ? this.vp.view(all.length, all.length) : { start: 0, end: all.length };
  },

  draw(ctx, w, h) {
    if (!this.data || this.data.bars.length < 2) return;
    const P = this.PAD;
    const range = this.visibleRange(w);
    const bars = this.data.bars.slice(range.start, range.end);
    const vwaps = this.series().slice(range.start, range.end);
    if (bars.length < 2) return;
    const allValues = bars.flatMap(b => [b.high, b.low])
      .concat(vwaps.flatMap(v => [v.vwap + 2 * v.sd, v.vwap - 2 * v.sd]));
    const hi = Math.max(...allValues), lo = Math.min(...allValues);
    const pad = (hi - lo) * 0.05 + 0.01;
    const colW = (w - P.l - P.r) / bars.length;
    const x = (i) => P.l + i * colW + colW / 2;
    const y = (v) => P.t + (1 - (v - lo + pad) / (hi - lo + 2 * pad)) * (h - P.t - P.b);

    // bandas
    for (const [mult, color] of [[2, "rgba(232,184,75,0.07)"], [1, "rgba(232,184,75,0.13)"]]) {
      ctx.beginPath();
      vwaps.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v.vwap + mult * v.sd))
                                      : ctx.lineTo(x(i), y(v.vwap + mult * v.sd)));
      for (let i = vwaps.length - 1; i >= 0; i--) ctx.lineTo(x(i), y(vwaps[i].vwap - mult * vwaps[i].sd));
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    }

    // velas
    bars.forEach((bar, i) => {
      const bull = bar.close >= bar.open;
      const color = bull ? COLORS.bought : COLORS.sold;
      const hot = this.hover === i;
      ctx.strokeStyle = color;
      ctx.lineWidth = hot ? 2 : 1;
      ctx.beginPath(); ctx.moveTo(x(i), y(bar.high)); ctx.lineTo(x(i), y(bar.low)); ctx.stroke();
      ctx.lineWidth = 1;
      const top = y(Math.max(bar.open, bar.close));
      const bodyH = Math.max(1.5, y(Math.min(bar.open, bar.close)) - top);
      ctx.fillStyle = bull ? "rgba(47,164,99,0.85)" : "rgba(224,67,63,0.85)";
      ctx.fillRect(x(i) - colW * 0.28, top, colW * 0.56, bodyH);
    });

    // VWAP
    ctx.beginPath();
    vwaps.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v.vwap)) : ctx.lineTo(x(i), y(v.vwap)));
    ctx.strokeStyle = COLORS.accent;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    // ejes
    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let g = 0; g <= 4; g++) {
      const v = lo + ((hi - lo) / 4) * g;
      ctx.fillText(v.toFixed(2), w - P.r + 6, y(v) + 3);
    }
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(bars.length / 8));
    for (let i = 0; i < bars.length; i += step) ctx.fillText(bars[i].t, x(i), h - 7);
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data || this.data.bars.length < 2) return;
      if (this.vp && this.vp.dragging) { hideTooltip(); return; }
      const P = this.PAD;
      const range = this.visibleRange(this.panel.w);
      const bars = this.data.bars.slice(range.start, range.end);
      if (!bars.length) return;
      const colW = (this.panel.w - P.l - P.r) / bars.length;
      const i = clamp(Math.floor((e.offsetX - P.l) / colW), 0, bars.length - 1);
      this.hover = i;
      const v = this.series()[range.start + i];
      const bar = bars[i];
      showTooltip(
        `<div class="tt-title">${bar.t}</div>` +
        `<div>O ${bar.open.toFixed(2)} H ${bar.high.toFixed(2)} L ${bar.low.toFixed(2)} C ${bar.close.toFixed(2)}</div>` +
        `<div class="tt-call">VWAP ${v.vwap.toFixed(2)} · σ ${v.sd.toFixed(2)}</div>` +
        `<div class="tt-dim">${bar.close >= v.vwap ? "encima" : "debajo"} del VWAP · Δ ${fmtK(bar.delta)}</div>`,
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
