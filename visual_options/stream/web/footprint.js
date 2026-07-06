/* Vista footprint: velas con volumen comprador/vendedor por nivel de precio.
 * Cada barra: celdas "vendido × comprado", delta y volumen abajo, POC en
 * ámbar e imbalances diagonales (≥3x) subrayados. */
"use strict";

const FootprintView = {
  data: null,
  panel: null,
  hover: { bar: -1, level: null },

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel panel-fp">
          <div class="panel-head">
            <h2>Footprint</h2>
            <span class="hint">vendido × comprado por nivel · ámbar = POC · borde = imbalance ≥3× · ${ZOOM_HINT}</span>
          </div>
          <canvas id="fpCanvas"></canvas>
        </section>
      </div>`;
    this.panel = new Panel(root.querySelector("#fpCanvas"), (c, w, h) => this.draw(c, w, h));
    this.vp = new BarViewport(() => this.panel && this.panel.draw());
    this.vp.attach(this.panel.canvas, {
      total: () => (this.data ? this.data.bars.length : 0),
      defaultCount: () => Math.max(3, Math.floor((this.panel.w - this.PAD.l - this.PAD.r) / 110)),
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
    this.data = payload.footprint;
    if (this.panel) this.panel.draw();
  },

  PAD: { l: 8, r: 64, t: 10, b: 44 },
  MIN_ROW_H: 13,

  geometry(w, h) {
    const P = this.PAD;
    const bars = this.data.bars;
    const defaultCount = Math.max(3, Math.floor((w - P.l - P.r) / 110));
    const range = this.vp ? this.vp.view(bars.length, defaultCount)
                          : { start: Math.max(0, bars.length - defaultCount), end: bars.length, count: Math.min(bars.length, defaultCount) };
    const visible = bars.slice(range.start, range.end);
    const colW = (w - P.l - P.r) / Math.max(1, visible.length);
    const tick = this.data.tick;
    let hi = -Infinity, lo = Infinity;
    visible.forEach(b => { hi = Math.max(hi, b.high); lo = Math.min(lo, b.low); });
    if (!isFinite(hi)) return null;
    hi = Math.ceil(hi / tick) * tick;
    lo = Math.floor(lo / tick) * tick;
    const levels = Math.max(1, Math.round((hi - lo) / tick) + 1);
    const plotH = h - P.t - P.b;
    const rowH = Math.max(this.MIN_ROW_H, Math.min(30, plotH / levels));
    const yOffset = P.t + Math.max(0, (plotH - rowH * levels) / 2);
    const yFor = (price) => yOffset + (hi - price) / tick * rowH + rowH / 2;
    return { visible, colW, tick, hi, lo, levels, rowH, yFor, yOffset };
  },

  draw(ctx, w, h) {
    if (!this.data || !this.data.bars.length) return;
    const P = this.PAD;
    const g = this.geometry(w, h);
    if (!g) return;
    const { visible, colW, tick, rowH, yFor } = g;
    const showText = rowH >= 12 && colW >= 54;
    const maxCell = Math.max(1, ...visible.flatMap(b => b.cells.map(c => c.buy + c.sell)));

    // eje de precios a la derecha
    ctx.font = MONO;
    ctx.textAlign = "left";
    for (let price = g.hi; price >= g.lo - 1e-9; price -= tick * Math.ceil(g.levels / Math.max(1, Math.floor((h - P.t - P.b) / 18)))) {
      const y = yFor(price);
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(price.toFixed(tick < 1 ? 2 : 0), w - P.r + 8, y + 3);
      ctx.strokeStyle = COLORS.border;
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(P.l, y); ctx.lineTo(w - P.r, y); ctx.stroke();
      ctx.globalAlpha = 1;
    }

    visible.forEach((bar, bi) => {
      const x = P.l + bi * colW;
      const cellsByPrice = new Map(bar.cells.map(c => [c.price, c]));

      // esqueleto de vela detrás de las celdas
      const bodyTop = yFor(Math.max(bar.open, bar.close));
      const bodyBot = yFor(Math.min(bar.open, bar.close));
      ctx.strokeStyle = bar.close >= bar.open ? COLORS.bought : COLORS.sold;
      ctx.globalAlpha = 0.55;
      ctx.beginPath();
      ctx.moveTo(x + colW / 2, yFor(bar.high) - rowH / 2);
      ctx.lineTo(x + colW / 2, yFor(bar.low) + rowH / 2);
      ctx.stroke();
      ctx.strokeRect(x + 3, bodyTop - rowH / 2, colW - 6, Math.max(2, bodyBot - bodyTop + rowH));
      ctx.globalAlpha = 1;

      bar.cells.forEach(cell => {
        const y = yFor(cell.price);
        const total = cell.buy + cell.sell;
        const heat = Math.pow(total / maxCell, 0.6);
        const isPoc = bar.poc !== null && Math.abs(cell.price - bar.poc) < tick / 2;
        const hot = this.hover.bar === bi && this.hover.level !== null &&
                    Math.abs(this.hover.level - cell.price) < tick / 2;

        // mitades: vendido izquierda (rojo), comprado derecha (verde)
        ctx.fillStyle = `rgba(224, 67, 63, ${0.10 + 0.45 * heat * (cell.sell / Math.max(1, total))})`;
        ctx.fillRect(x + 2, y - rowH / 2 + 1, colW / 2 - 2, rowH - 2);
        ctx.fillStyle = `rgba(47, 164, 99, ${0.10 + 0.45 * heat * (cell.buy / Math.max(1, total))})`;
        ctx.fillRect(x + colW / 2, y - rowH / 2 + 1, colW / 2 - 2, rowH - 2);

        // imbalances diagonales ≥3x
        const below = cellsByPrice.get(Math.round((cell.price - tick) / tick) * tick);
        const above = cellsByPrice.get(Math.round((cell.price + tick) / tick) * tick);
        const ratio = this.data.imbalance_ratio;
        if (below && cell.sell >= ratio * Math.max(1, below.buy) && cell.sell > 10) {
          ctx.strokeStyle = COLORS.sold;
          ctx.strokeRect(x + 2, y - rowH / 2 + 1, colW / 2 - 2, rowH - 2);
        }
        if (above && cell.buy >= ratio * Math.max(1, above.sell) && cell.buy > 10) {
          ctx.strokeStyle = COLORS.bought;
          ctx.strokeRect(x + colW / 2, y - rowH / 2 + 1, colW / 2 - 2, rowH - 2);
        }
        if (isPoc) {
          ctx.strokeStyle = COLORS.accent;
          ctx.strokeRect(x + 1, y - rowH / 2, colW - 2, rowH);
        }
        if (hot) {
          ctx.strokeStyle = COLORS.price;
          ctx.strokeRect(x + 1, y - rowH / 2, colW - 2, rowH);
        }

        if (showText) {
          ctx.textAlign = "right";
          ctx.fillStyle = cell.sell > cell.buy ? COLORS.sold : COLORS.dim;
          ctx.fillText(fmtK(cell.sell), x + colW / 2 - 5, y + 3.5);
          ctx.textAlign = "left";
          ctx.fillStyle = cell.buy > cell.sell ? COLORS.bought : COLORS.dim;
          ctx.fillText(fmtK(cell.buy), x + colW / 2 + 5, y + 3.5);
        }
      });

      // pie: hora, delta y volumen
      ctx.textAlign = "center";
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(bar.t, x + colW / 2, h - 30);
      ctx.fillStyle = bar.delta >= 0 ? COLORS.bought : COLORS.sold;
      ctx.font = "600 " + MONO;
      ctx.fillText((bar.delta >= 0 ? "+" : "") + fmtK(bar.delta), x + colW / 2, h - 17);
      ctx.font = MONO;
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(fmtK(bar.volume), x + colW / 2, h - 5);
    });
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data || !this.data.bars.length) return;
      if (this.vp && this.vp.dragging) { hideTooltip(); return; }
      const g = this.geometry(this.panel.w, this.panel.h);
      if (!g) return;
      const bi = clamp(Math.floor((e.offsetX - this.PAD.l) / g.colW), 0, g.visible.length - 1);
      const price = g.hi - Math.round((e.offsetY - g.yOffset - g.rowH / 2) / g.rowH) * g.tick;
      const bar = g.visible[bi];
      const cell = bar.cells.find(c => Math.abs(c.price - price) < g.tick / 2);
      this.hover = { bar: bi, level: cell ? cell.price : null };
      if (cell) {
        const total = cell.buy + cell.sell;
        showTooltip(
          `<div class="tt-title">${bar.t} · ${cell.price.toFixed(2)}</div>` +
          `<div class="tt-put">vendido ${fmtK(cell.sell)}</div>` +
          `<div class="tt-call">comprado ${fmtK(cell.buy)}</div>` +
          `<div>total ${fmtK(total)} · delta ${(cell.buy - cell.sell) >= 0 ? "+" : ""}${fmtK(cell.buy - cell.sell)}</div>` +
          `<div class="tt-dim">barra: Δ ${fmtK(bar.delta)} · vol ${fmtK(bar.volume)} · POC ${bar.poc?.toFixed(2) ?? "—"}</div>`,
          e.clientX, e.clientY);
      } else {
        hideTooltip();
      }
      this.panel.draw();
    });
    canvas.addEventListener("pointerleave", () => {
      this.hover = { bar: -1, level: null };
      hideTooltip();
      this.panel.draw();
    });
  },
};
