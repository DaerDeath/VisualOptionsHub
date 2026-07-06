/* Put/Call Ratio: medidores por volumen (sentimiento de hoy) y por OI
 * (posicionamiento), y ratio por strike. Lectura contraria en extremos. */
"use strict";

const PcrView = {
  data: null,
  panel: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="pcr-wrap">
        <div class="vwap-tiles" id="pcrTiles"></div>
        <section class="panel">
          <div class="panel-head">
            <h2>Put/Call por strike</h2>
            <span class="hint">barra hacia la izquierda = dominan puts, derecha = calls · arriba: volumen (hoy) · abajo: open interest (posicionamiento)</span>
          </div>
          <canvas id="pcrCanvas"></canvas>
        </section>
      </div>`;
    this.tilesEl = root.querySelector("#pcrTiles");
    this.panel = new Panel(root.querySelector("#pcrCanvas"), (c, w, h) => this.draw(c, w, h));
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
    this.renderTiles();
    if (this.panel) this.panel.draw();
  },

  verdict(pcr) {
    if (pcr > 1.2) return ["pánico → contrario alcista", "pos"];
    if (pcr > 0.9) return ["defensivo", ""];
    if (pcr > 0.7) return ["neutral", ""];
    if (pcr > 0.5) return ["optimista", ""];
    return ["euforia → contrario bajista", "neg"];
  },

  renderTiles() {
    const rows = this.data.strikes;
    if (!this.tilesEl || !rows.length) return;
    const volC = rows.reduce((a, r) => a + r.call_volume, 0);
    const volP = rows.reduce((a, r) => a + r.put_volume, 0);
    const oiC = rows.reduce((a, r) => a + r.call_oi, 0);
    const oiP = rows.reduce((a, r) => a + r.put_oi, 0);
    const pcrVol = volC ? volP / volC : 0;
    const pcrOI = oiC ? oiP / oiC : 0;
    const [vVol, cVol] = this.verdict(pcrVol);
    const [vOI, cOI] = this.verdict(pcrOI);
    const tile = (label, value, sub, cls = "") =>
      `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b><i>${sub}</i></div>`;
    this.tilesEl.innerHTML =
      tile("PCR volumen", pcrVol.toFixed(2), vVol, cVol) +
      tile("PCR open interest", pcrOI.toFixed(2), vOI, cOI) +
      tile("Vol puts / calls", `${fmtK(volP)} / ${fmtK(volC)}`, "operado hoy") +
      tile("OI puts / calls", `${fmtK(oiP)} / ${fmtK(oiC)}`, "posiciones abiertas");
  },

  PAD: { l: 64, r: 16, t: 26, b: 8, gap: 26 },

  draw(ctx, w, h) {
    if (!this.data || !this.data.strikes.length) return;
    const P = this.PAD;
    const rows = [...this.data.strikes].sort((a, b) => b.strike - a.strike);
    const rowH = (h - P.t - P.b) / rows.length;
    const colW = (w - P.l - P.r - P.gap) / 2;

    const drawColumn = (x0, title, getPut, getCall) => {
      const center = x0 + colW / 2;
      const maxSide = Math.max(1, ...rows.flatMap(r => [getPut(r), getCall(r)]));
      ctx.font = "600 " + MONO;
      ctx.textAlign = "center";
      ctx.fillStyle = COLORS.text;
      ctx.fillText(title, center, P.t - 10);
      ctx.font = MONO;
      ctx.strokeStyle = COLORS.border;
      ctx.beginPath(); ctx.moveTo(center, P.t); ctx.lineTo(center, h - P.b); ctx.stroke();
      rows.forEach((r, i) => {
        const y = P.t + i * rowH;
        const hot = this.hover === i;
        const pw = (colW / 2 - 3) * getPut(r) / maxSide;
        const cw = (colW / 2 - 3) * getCall(r) / maxSide;
        ctx.fillStyle = hot ? COLORS.sold : "rgba(224,67,63,0.62)";
        ctx.fillRect(center - pw, y + rowH * 0.16, pw, rowH * 0.68);
        ctx.fillStyle = hot ? COLORS.call : "rgba(93,179,217,0.62)";
        ctx.fillRect(center, y + rowH * 0.16, cw, rowH * 0.68);
      });
    };

    ctx.font = MONO;
    rows.forEach((r, i) => {
      const y = P.t + i * rowH + rowH / 2;
      ctx.textAlign = "right";
      ctx.fillStyle = this.hover === i ? COLORS.accent : COLORS.dim;
      ctx.fillText(Number.isInteger(r.strike) ? String(r.strike) : r.strike.toFixed(1), P.l - 8, y + 3.5);
    });

    drawColumn(P.l, "VOLUMEN (hoy)", r => r.put_volume, r => r.call_volume);
    drawColumn(P.l + colW + P.gap, "OPEN INTEREST", r => r.put_oi, r => r.call_oi);

    // spot
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
      if (!this.data || !this.data.strikes.length) return;
      const P = this.PAD;
      const rows = [...this.data.strikes].sort((a, b) => b.strike - a.strike);
      const rowH = (this.panel.h - P.t - P.b) / rows.length;
      const i = clamp(Math.floor((e.offsetY - P.t) / rowH), 0, rows.length - 1);
      this.hover = i;
      const r = rows[i];
      const pcrVol = r.call_volume ? (r.put_volume / r.call_volume) : 0;
      const pcrOI = r.call_oi ? (r.put_oi / r.call_oi) : 0;
      showTooltip(
        `<div class="tt-title">Strike ${r.strike}</div>` +
        `<div>vol: P ${fmtK(r.put_volume)} / C ${fmtK(r.call_volume)} → PCR ${pcrVol.toFixed(2)}</div>` +
        `<div>OI: P ${fmtK(r.put_oi)} / C ${fmtK(r.call_oi)} → PCR ${pcrOI.toFixed(2)}</div>`,
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
