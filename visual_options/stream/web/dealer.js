/* Vista dealer positioning (réplica de CloutSeeker): Net GEX, Net DEX y
 * Net Vanna por strike como barras divergentes alineadas, con gamma flip,
 * spot y totales. Todo en millones de $. */
"use strict";

const DealerView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="dealer-wrap">
        <section class="panel panel-dealer">
          <div class="panel-head">
            <h2>Dealer positioning</h2>
            <span class="hint">GEX + frena / − acelera · DEX exposición direccional · Vanna sensibilidad a IV · línea ámbar = spot · magenta = gamma flip</span>
            <div class="dealer-totals" id="dealerTotals"></div>
          </div>
          <canvas id="dealerCanvas"></canvas>
        </section>
      </div>`;
    this.totalsEl = root.querySelector("#dealerTotals");
    this.panel = new Panel(root.querySelector("#dealerCanvas"), (c, w, h) => this.draw(c, w, h));
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
    this.updateTotals();
    if (this.panel) this.panel.draw();
  },

  METRICS: [
    { key: "net_gex", label: "Net GEX ($M / 1%)", split: ["call_gex", "put_gex"] },
    { key: "net_dex", label: "Net DEX ($M)", split: null },
    { key: "net_vanna", label: "Net Vanna ($M / 1% IV)", split: ["call_vanna", "put_vanna"] },
  ],
  PAD: { l: 64, r: 16, t: 30, b: 8, gap: 26 },

  fmtM(v) {
    const abs = Math.abs(v);
    const txt = abs >= 1000 ? (v / 1000).toFixed(1) + "B" : v.toFixed(abs >= 100 ? 0 : 1) + "M";
    return (v >= 0 ? "+" : "") + txt.replace("+-", "-");
  },

  updateTotals() {
    if (!this.data) return;
    const sum = (key) => this.data.strikes.reduce((acc, r) => acc + (r[key] || 0), 0);
    const flip = this.data.gamma_flip;
    const chips = [
      ["Σ GEX", sum("net_gex"), sum("net_gex") >= 0 ? "pos" : "neg"],
      ["Σ DEX", sum("net_dex"), sum("net_dex") >= 0 ? "pos" : "neg"],
      ["Σ Vanna", sum("net_vanna"), sum("net_vanna") >= 0 ? "pos" : "neg"],
    ];
    this.totalsEl.innerHTML = chips.map(([label, v, cls]) =>
      `<span class="dtotal ${cls}">${label} ${this.fmtM(v)}</span>`).join("") +
      (flip ? `<span class="dtotal flip">γ-flip ${flip.toFixed(1)}</span>` : "");
  },

  geometry(w, h) {
    const rows = [...this.data.strikes].sort((a, b) => b.strike - a.strike); // alto arriba
    const P = this.PAD;
    const rowH = (h - P.t - P.b) / rows.length;
    const colW = (w - P.l - P.r - P.gap * (this.METRICS.length - 1)) / this.METRICS.length;
    const colX = (ci) => P.l + ci * (colW + P.gap);
    return { rows, rowH, colW, colX };
  },

  draw(ctx, w, h) {
    if (!this.data || !this.data.strikes.length) return;
    const P = this.PAD;
    const g = this.geometry(w, h);
    const { rows, rowH, colW, colX } = g;

    // etiquetas de strikes (eje compartido)
    ctx.font = MONO;
    rows.forEach((r, i) => {
      const y = P.t + i * rowH + rowH / 2;
      const hot = this.hover === i;
      ctx.textAlign = "right";
      ctx.fillStyle = hot ? COLORS.accent : COLORS.dim;
      ctx.fillText(Number.isInteger(r.strike) ? String(r.strike) : r.strike.toFixed(1), P.l - 8, y + 3.5);
      if (hot) {
        ctx.fillStyle = "rgba(232, 184, 75, 0.06)";
        ctx.fillRect(P.l, y - rowH / 2, w - P.l - P.r, rowH);
      }
    });

    this.METRICS.forEach((metric, ci) => {
      const x0 = colX(ci);
      const center = x0 + colW / 2;
      const maxAbs = Math.max(1e-9, ...rows.map(r => Math.abs(r[metric.key] || 0)));
      const scale = (colW / 2 - 4) / maxAbs;

      // título y eje cero
      ctx.textAlign = "center";
      ctx.fillStyle = COLORS.text;
      ctx.font = "600 " + MONO;
      ctx.fillText(metric.label, center, P.t - 12);
      ctx.font = MONO;
      ctx.strokeStyle = COLORS.border;
      ctx.beginPath();
      ctx.moveTo(center, P.t - 4);
      ctx.lineTo(center, h - P.b);
      ctx.stroke();

      rows.forEach((r, i) => {
        const y = P.t + i * rowH;
        const v = r[metric.key] || 0;
        const bw = Math.abs(v) * scale;
        const hot = this.hover === i;
        ctx.fillStyle = v >= 0
          ? (hot ? COLORS.bought : "rgba(47,164,99,0.72)")
          : (hot ? COLORS.sold : "rgba(224,67,63,0.68)");
        if (v >= 0) ctx.fillRect(center, y + rowH * 0.14, bw, rowH * 0.72);
        else ctx.fillRect(center - bw, y + rowH * 0.14, bw, rowH * 0.72);

        // desglose call/put como muescas (si el métrico lo tiene)
        if (metric.split && rowH >= 9) {
          const half = colW / 2 - 4;
          const [callKey, putKey] = metric.split;
          const cv = clamp((r[callKey] || 0) * scale, -half, half);
          const pv = clamp((r[putKey] || 0) * scale, -half, half);
          ctx.fillStyle = "rgba(93,179,217,0.9)";
          ctx.fillRect(center + Math.min(0, cv), y + rowH * 0.14, Math.abs(cv), 2);
          ctx.fillStyle = "rgba(224,67,63,0.9)";
          ctx.fillRect(center + Math.min(0, pv), y + rowH * 0.86 - 2, Math.abs(pv), 2);
        }
      });

      // spot y gamma flip proyectados sobre cada columna
      const yFor = (level) => {
        const hi = rows[0].strike, lo = rows[rows.length - 1].strike;
        if (level < lo || level > hi) return null;
        return P.t + ((hi - level) / (hi - lo)) * (rowH * (rows.length - 1)) + rowH / 2;
      };
      const spotY = yFor(this.data.spot);
      if (spotY !== null) {
        ctx.strokeStyle = COLORS.accent;
        ctx.setLineDash([5, 4]);
        ctx.beginPath(); ctx.moveTo(x0, spotY); ctx.lineTo(x0 + colW, spotY); ctx.stroke();
        ctx.setLineDash([]);
      }
      const flipY = this.data.gamma_flip !== null ? yFor(this.data.gamma_flip) : null;
      if (flipY !== null) {
        ctx.strokeStyle = "#c65dd9";
        ctx.setLineDash([2, 3]);
        ctx.beginPath(); ctx.moveTo(x0, flipY); ctx.lineTo(x0 + colW, flipY); ctx.stroke();
        ctx.setLineDash([]);
      }
    });
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data || !this.data.strikes.length) return;
      const g = this.geometry(this.panel.w, this.panel.h);
      const i = clamp(Math.floor((e.offsetY - this.PAD.t) / g.rowH), 0, g.rows.length - 1);
      this.hover = i;
      const r = g.rows[i];
      showTooltip(
        `<div class="tt-title">Strike ${r.strike}</div>` +
        `<div>Net GEX ${this.fmtM(r.net_gex)} <span class="tt-dim">(C ${this.fmtM(r.call_gex)} · P ${this.fmtM(r.put_gex)})</span></div>` +
        `<div>Net DEX ${this.fmtM(r.net_dex)}</div>` +
        `<div>Net Vanna ${this.fmtM(r.net_vanna)} <span class="tt-dim">(C ${this.fmtM(r.call_vanna)} · P ${this.fmtM(r.put_vanna)})</span></div>` +
        `<div class="tt-dim">OI: C ${fmtK(r.call_oi)} / P ${fmtK(r.put_oi)} · IV ${(r.iv * 100).toFixed(1)}%</div>`,
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
