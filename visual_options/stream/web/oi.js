/* Vista de perfil de open interest (Equity Hub-like): OI de calls y puts
 * en espejo por strike, put/call ratio y OI total. */
"use strict";

const OIView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="dealer-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Perfil de open interest</h2>
            <span class="hint">puts a la izquierda · calls a la derecha · ámbar = spot</span>
            <div class="dealer-totals" id="oiTotals"></div>
          </div>
          <canvas id="oiCanvas"></canvas>
        </section>
      </div>`;
    this.totalsEl = root.querySelector("#oiTotals");
    this.panel = new Panel(root.querySelector("#oiCanvas"), (c, w, h) => this.draw(c, w, h));
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
    const rows = this.data.strikes;
    const callTotal = rows.reduce((a, r) => a + r.call_oi, 0);
    const putTotal = rows.reduce((a, r) => a + r.put_oi, 0);
    const pcr = callTotal ? putTotal / callTotal : 0;
    this.totalsEl.innerHTML =
      `<span class="dtotal"><span style="color:var(--call-line)">C ${fmtK(callTotal)}</span></span>` +
      `<span class="dtotal"><span style="color:var(--put-line)">P ${fmtK(putTotal)}</span></span>` +
      `<span class="dtotal ${pcr > 1 ? "neg" : "pos"}">PCR ${pcr.toFixed(2)}</span>`;
    if (this.panel) this.panel.draw();
  },

  PAD: { l: 60, r: 16, t: 12, b: 8 },

  geometry(w, h) {
    const rows = [...this.data.strikes].sort((a, b) => b.strike - a.strike);
    const P = this.PAD;
    const rowH = (h - P.t - P.b) / rows.length;
    const center = P.l + (w - P.l - P.r) / 2;
    const half = (w - P.l - P.r) / 2 - 6;
    const maxOI = Math.max(1, ...rows.map(r => Math.max(r.call_oi, r.put_oi)));
    return { rows, rowH, center, half, maxOI };
  },

  draw(ctx, w, h) {
    if (!this.data || !this.data.strikes.length) return;
    const P = this.PAD;
    const { rows, rowH, center, half, maxOI } = this.geometry(w, h);

    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(center, P.t); ctx.lineTo(center, h - P.b); ctx.stroke();

    ctx.font = MONO;
    rows.forEach((r, i) => {
      const y = P.t + i * rowH;
      const hot = this.hover === i;
      const putW = half * r.put_oi / maxOI;
      const callW = half * r.call_oi / maxOI;
      ctx.fillStyle = hot ? COLORS.sold : "rgba(224,67,63,0.62)";
      ctx.fillRect(center - putW, y + rowH * 0.14, putW, rowH * 0.72);
      ctx.fillStyle = hot ? COLORS.call : "rgba(93,179,217,0.62)";
      ctx.fillRect(center, y + rowH * 0.14, callW, rowH * 0.72);
      ctx.textAlign = "right";
      ctx.fillStyle = hot ? COLORS.accent : COLORS.dim;
      ctx.fillText(Number.isInteger(r.strike) ? String(r.strike) : r.strike.toFixed(1), P.l - 8, y + rowH / 2 + 3.5);
      if (rowH >= 12) {
        ctx.fillStyle = COLORS.dim;
        ctx.fillText(fmtK(r.put_oi), center - putW - 4, y + rowH / 2 + 3.5);
        ctx.textAlign = "left";
        ctx.fillText(fmtK(r.call_oi), center + callW + 4, y + rowH / 2 + 3.5);
      }
    });

    const hi = rows[0].strike, lo = rows[rows.length - 1].strike;
    if (this.data.spot >= lo && this.data.spot <= hi) {
      const y = P.t + ((hi - this.data.spot) / (hi - lo)) * (rowH * (rows.length - 1)) + rowH / 2;
      ctx.strokeStyle = COLORS.accent;
      ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(P.l, y); ctx.lineTo(w - P.r, y); ctx.stroke();
      ctx.setLineDash([]);
    }
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data) return;
      const g = this.geometry(this.panel.w, this.panel.h);
      const i = clamp(Math.floor((e.offsetY - this.PAD.t) / g.rowH), 0, g.rows.length - 1);
      this.hover = i;
      const r = g.rows[i];
      showTooltip(
        `<div class="tt-title">Strike ${r.strike}</div>` +
        `<div class="tt-call">Call OI ${fmtK(r.call_oi)}</div>` +
        `<div class="tt-put">Put OI ${fmtK(r.put_oi)}</div>` +
        `<div class="tt-dim">IV ${(r.iv * 100).toFixed(1)}% · vol C ${fmtK(r.call_volume)} / P ${fmtK(r.put_volume)}</div>`,
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
