/* Vista de flujo de opciones: los 4 paneles del stream.
 * Lectura (vídeo "how to read the stream's data"): % = porción VENDIDA del
 * strike; azul (call sell %) baja → precio sube; roja baja → precio la sigue. */
"use strict";

const FlowView = {
  data: null,
  panels: [],
  hover: { panel: null, index: -1 },
  pinnedStrike: null,

  mount(root) {
    root.innerHTML = `
      <div class="flow-grid">
        <section class="panel panel-profile">
          <div class="panel-head">
            <h2>Cadena · volumen y % vendido por strike</h2>
            <span class="hint">calls arriba · puts abajo · rojo = vendido, verde = comprado · blanco = perfil de volumen</span>
            <div class="dealer-totals" id="flowStats"></div>
          </div>
          <canvas id="profileCanvas"></canvas>
        </section>
        <section class="panel panel-series">
          <div class="panel-head">
            <h2>Flujo agregado vs precio</h2>
            <span class="hint">azul baja → precio sube · roja baja → el precio la sigue · naranja = IV</span>
          </div>
          <canvas id="seriesCanvas"></canvas>
        </section>
        <section class="panel panel-gamma">
          <div class="panel-head"><h2>Gamma (GEX) por strike</h2></div>
          <canvas id="gammaCanvas"></canvas>
        </section>
        <section class="panel panel-magnet">
          <div class="panel-head"><h2>Magnet strikes <span class="hint">OI / volumen</span></h2></div>
          <canvas id="magnetCanvas"></canvas>
        </section>
      </div>`;

    this.statsEl = root.querySelector("#flowStats");
    const profile = new Panel(root.querySelector("#profileCanvas"), (c, w, h) => this.drawProfile(c, w, h));
    const series = new Panel(root.querySelector("#seriesCanvas"), (c, w, h) => this.drawSeries(c, w, h));
    const gamma = new Panel(root.querySelector("#gammaCanvas"), (c, w, h) => this.drawGamma(c, w, h));
    const magnet = new Panel(root.querySelector("#magnetCanvas"), (c, w, h) => this.drawMagnet(c, w, h));
    this.panels = [profile, series, gamma, magnet];
    this.attachMouse(profile, series, gamma, magnet);
  },

  unmount() {
    this.panels.forEach(p => p.destroy());
    this.panels = [];
    this.data = null;
    hideTooltip();
  },

  onData(payload) {
    this.data = payload.flow;
    this.renderStats();
    this.render();
  },

  /* fila de métricas del stream: IV · Gamma per 1% · EMtop/EMbot */
  renderStats() {
    const d = this.data;
    if (!this.statsEl || !d.strikes.length) return;
    const last = d.series[d.series.length - 1];
    const iv = last && last.iv > 0 ? last.iv : 0.2;
    const totalGex = d.strikes.reduce((acc, r) => acc + r.net_gex, 0);
    const em = d.spot * iv * Math.sqrt(Math.max(d.expiry_days, 0.25) / 365);
    this.statsEl.innerHTML =
      `<span class="dtotal">IV ${(iv * 100).toFixed(2)}%</span>` +
      `<span class="dtotal ${totalGex >= 0 ? "pos" : "neg"}" title="Σ Net GEX por 1% de movimiento">Γ/1% ${totalGex >= 0 ? "+" : ""}${totalGex.toFixed(1)}M</span>` +
      `<span class="dtotal pos" title="movimiento esperado +1σ">EMtop ${(d.spot + em).toFixed(2)}</span>` +
      `<span class="dtotal neg" title="movimiento esperado −1σ">EMbot ${(d.spot - em).toFixed(2)}</span>`;
  },

  render() {
    if (!this.data) return;
    this.panels.forEach(p => p.draw());
  },

  /* ---------------------------------------------------- perfil por strike */
  PROFILE: { top: 30, axisH: 22, bottom: 30, chipH: 16 },

  layout(w) {
    const rows = this.data.strikes;
    return { rows, colW: w / rows.length };
  },

  strikeLabel(strike) {
    return Number.isInteger(strike) ? String(strike) : strike.toFixed(1);
  },

  drawProfile(ctx, w, h) {
    if (!this.data) return;
    const P = this.PROFILE;
    const { rows, colW } = this.layout(w);
    const axisY = h / 2;
    const halfH = axisY - P.top - P.axisH / 2 - P.chipH;
    const maxCall = Math.max(1, ...rows.map(r => r.call_volume));
    const maxPut = Math.max(1, ...rows.map(r => r.put_volume));

    rows.forEach((r, i) => {
      const x = i * colW + colW * 0.14;
      const bw = colW * 0.72;
      const hot = (this.hover.panel === "profile" && this.hover.index === i) || this.pinnedStrike === r.strike;

      const cSold = halfH * r.call_sold_pct / 100;
      const yTopCall = axisY - P.axisH / 2;
      ctx.fillStyle = hot ? COLORS.sold : COLORS.soldDim;
      ctx.fillRect(x, yTopCall - cSold, bw, cSold);
      ctx.fillStyle = hot ? COLORS.bought : COLORS.boughtDim;
      ctx.fillRect(x, yTopCall - halfH, bw, halfH - cSold);

      const pSold = halfH * r.put_sold_pct / 100;
      const yBotPut = axisY + P.axisH / 2;
      ctx.fillStyle = hot ? COLORS.sold : COLORS.soldDim;
      ctx.fillRect(x, yBotPut, bw, pSold);
      ctx.fillStyle = hot ? COLORS.bought : COLORS.boughtDim;
      ctx.fillRect(x, yBotPut + pSold, bw, halfH - pSold);

      ctx.font = MONO;
      ctx.textAlign = "center";
      ctx.fillStyle = "#fff";
      ctx.fillText(Math.round(r.call_sold_pct) + "%", x + bw / 2, yTopCall - 5);
      ctx.fillText(Math.round(r.put_sold_pct) + "%", x + bw / 2, yBotPut + 13);

      ctx.fillStyle = COLORS.surface2;
      ctx.fillRect(x, P.top - P.chipH + 2, bw, P.chipH - 4);
      ctx.fillRect(x, h - P.bottom + 2, bw, P.chipH - 4);
      ctx.fillStyle = "#9fc2e8";
      ctx.fillText(fmtK(r.call_volume), x + bw / 2, P.top - 6);
      ctx.fillText(fmtK(r.put_volume), x + bw / 2, h - P.bottom + 13);
    });

    const volPath = (getVol, maxVol, sign) => {
      ctx.beginPath();
      ctx.moveTo(0, axisY - sign * P.axisH / 2);
      rows.forEach((r, i) => {
        const vh = halfH * getVol(r) / maxVol;
        ctx.lineTo(i * colW + colW / 2, axisY - sign * (P.axisH / 2 + vh));
      });
      ctx.lineTo(w, axisY - sign * P.axisH / 2);
      ctx.closePath();
      ctx.fillStyle = "rgba(240, 245, 250, 0.16)";
      ctx.fill();
    };
    volPath(r => r.call_volume, maxCall, 1);
    volPath(r => r.put_volume, maxPut, -1);

    ctx.fillStyle = "#000";
    ctx.fillRect(0, axisY - P.axisH / 2, w, P.axisH);
    ctx.strokeStyle = COLORS.border;
    ctx.strokeRect(0, axisY - P.axisH / 2, w, P.axisH);
    ctx.font = "600 " + MONO;
    rows.forEach((r, i) => {
      ctx.fillStyle = this.pinnedStrike === r.strike ? COLORS.accent : COLORS.text;
      ctx.fillText(this.strikeLabel(r.strike), i * colW + colW / 2, axisY + 4);
    });

    const spotX = this.spotToX(this.data.spot, rows, colW);
    if (spotX !== null) {
      ctx.strokeStyle = COLORS.accent;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(spotX, P.top);
      ctx.lineTo(spotX, h - P.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = COLORS.accent;
      ctx.fillText(this.data.spot.toFixed(2), spotX, P.top - 18);
    }
  },

  spotToX(spot, rows, colW) {
    const first = rows[0].strike, last = rows[rows.length - 1].strike;
    if (spot < first || spot > last) return null;
    return ((spot - first) / (last - first)) * (colW * (rows.length - 1)) + colW / 2;
  },

  /* --------------------------------------------------- series temporales */
  SPAD: { l: 34, r: 52, t: 10, b: 22 },

  seriesScales(w, h) {
    const pts = this.data.series;
    const S = this.SPAD;
    const pctMax = Math.max(20, ...pts.map(p =>
      Math.max(p.put_sell_pct, p.call_sell_pct, (p.iv || 0) * 100))) * 1.1;
    const prices = pts.map(p => p.price);
    const pMin = Math.min(...prices), pMax = Math.max(...prices);
    const pad = Math.max(0.4, (pMax - pMin) * 0.08);
    return {
      pts, pctMax, pMin: pMin - pad, pMax: pMax + pad,
      x: (i) => S.l + (i / Math.max(1, pts.length - 1)) * (w - S.l - S.r),
      yPct: (v) => h - S.b - (v / pctMax) * (h - S.t - S.b),
      yPrice: (v) => h - S.b - ((v - (pMin - pad)) / ((pMax + pad) - (pMin - pad))) * (h - S.t - S.b),
    };
  },

  drawSeries(ctx, w, h) {
    if (!this.data || this.data.series.length < 2) return;
    const S = this.SPAD;
    const s = this.seriesScales(w, h);

    ctx.strokeStyle = COLORS.border;
    ctx.fillStyle = COLORS.dim;
    ctx.font = MONO;
    ctx.textAlign = "left";
    for (let g = 0; g <= 4; g++) {
      const v = (s.pctMax / 4) * g;
      const y = s.yPct(v);
      ctx.globalAlpha = 0.5;
      ctx.beginPath(); ctx.moveTo(S.l, y); ctx.lineTo(w - S.r, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(Math.round(v) + "%", 2, y + 3);
      const price = s.pMin + ((s.pMax - s.pMin) / 4) * g;
      ctx.fillText(price.toFixed(1), w - S.r + 4, s.yPrice(price) + 3);
    }

    const line = (getV, yScale, color, width) => {
      ctx.beginPath();
      s.pts.forEach((p, i) => {
        const px = s.x(i), py = yScale(getV(p));
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      });
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
      ctx.lineWidth = 1;
    };
    line(p => p.put_sell_pct, s.yPct, COLORS.put, 1.4);
    line(p => p.call_sell_pct, s.yPct, COLORS.call, 1.4);
    if (s.pts.some(p => p.iv > 0)) {
      line(p => p.iv * 100, s.yPct, "#e0954b", 1.3);  // IV en naranja, eje %
    }
    line(p => p.price, s.yPrice, COLORS.price, 1.8);

    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(s.pts.length / 6));
    for (let i = 0; i < s.pts.length; i += step) {
      ctx.fillText(s.pts[i].t.slice(0, 5), s.x(i), h - 6);
    }

    if (this.hover.panel === "series" && this.hover.index >= 0 && this.hover.index < s.pts.length) {
      const i = this.hover.index, p = s.pts[i], px = s.x(i);
      ctx.strokeStyle = COLORS.dim;
      ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.moveTo(px, S.t); ctx.lineTo(px, h - S.b); ctx.stroke();
      ctx.setLineDash([]);
      [[s.yPrice(p.price), COLORS.price], [s.yPct(p.put_sell_pct), COLORS.put], [s.yPct(p.call_sell_pct), COLORS.call]]
        .forEach(([y, c]) => {
          ctx.beginPath(); ctx.arc(px, y, 3.4, 0, Math.PI * 2);
          ctx.fillStyle = c; ctx.fill();
        });
    }
  },

  /* ------------------------------------------------------------- gamma */
  GPAD: { l: 8, r: 8, t: 14, b: 22 },

  drawGamma(ctx, w, h) {
    if (!this.data) return;
    const G = this.GPAD;
    const rows = this.data.strikes;
    const colW = (w - G.l - G.r) / rows.length;
    const maxAbs = Math.max(1e-6, ...rows.map(r => Math.abs(r.gamma_exposure)));
    const zeroY = G.t + (h - G.t - G.b) / 2;
    const scale = (h - G.t - G.b) / 2 / maxAbs;

    rows.forEach((r, i) => {
      const x = G.l + i * colW + colW * 0.18;
      const bw = colW * 0.64;
      const v = r.gamma_exposure * scale;
      const hot = this.hover.panel === "gamma" && this.hover.index === i;
      ctx.fillStyle = r.gamma_exposure >= 0
        ? (hot ? COLORS.bought : "rgba(47,164,99,0.75)")
        : (hot ? COLORS.sold : "rgba(224,67,63,0.7)");
      if (v >= 0) ctx.fillRect(x, zeroY - v, bw, v);
      else ctx.fillRect(x, zeroY, bw, -v);
    });

    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(G.l, zeroY); ctx.lineTo(w - G.r, zeroY); ctx.stroke();

    ctx.font = MONO; ctx.fillStyle = COLORS.dim; ctx.textAlign = "center";
    const step = Math.ceil(rows.length / 8);
    rows.forEach((r, i) => {
      if (i % step === 0) ctx.fillText(this.strikeLabel(r.strike), G.l + i * colW + colW / 2, h - 6);
    });

    const spotX = this.spotToX(this.data.spot, rows, colW);
    if (spotX !== null) {
      ctx.strokeStyle = COLORS.accent;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(G.l + spotX, G.t);
      ctx.lineTo(G.l + spotX, h - G.b);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  },

  /* ---------------------------------------------------- magnet strikes */
  MPAD: { l: 48, r: 12, t: 8, b: 8 },

  drawMagnet(ctx, w, h) {
    if (!this.data) return;
    const M = this.MPAD;
    const rows = [...this.data.strikes].reverse();
    const rowH = (h - M.t - M.b) / rows.length;
    const maxV = Math.max(1e-6, ...rows.map(r => r.magnet));

    rows.forEach((r, i) => {
      const y = M.t + i * rowH;
      const bw = (w - M.l - M.r) * (r.magnet / maxV);
      const hot = this.hover.panel === "magnet" && this.hover.index === i;
      const intensity = r.magnet / maxV;
      ctx.fillStyle = hot ? COLORS.accent : `rgba(232, 184, 75, ${0.25 + intensity * 0.6})`;
      ctx.fillRect(M.l, y + rowH * 0.15, bw, rowH * 0.7);
      ctx.font = MONO;
      ctx.textAlign = "right";
      ctx.fillStyle = hot ? COLORS.accent : COLORS.dim;
      ctx.fillText(this.strikeLabel(r.strike), M.l - 5, y + rowH / 2 + 4);
    });

    const first = rows[rows.length - 1].strike, last = rows[0].strike;
    if (this.data.spot >= first && this.data.spot <= last) {
      const y = M.t + ((last - this.data.spot) / (last - first)) * (rowH * (rows.length - 1)) + rowH / 2;
      ctx.strokeStyle = COLORS.price;
      ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(M.l, y); ctx.lineTo(w - M.r, y); ctx.stroke();
      ctx.setLineDash([]);
    }
  },

  /* ------------------------------------------------------------- ratón */
  strikeTooltip(r) {
    const cb = (100 - r.call_sold_pct).toFixed(0), pb = (100 - r.put_sold_pct).toFixed(0);
    return `<div class="tt-title">Strike ${this.strikeLabel(r.strike)}</div>` +
      `<div class="tt-call">Calls ${fmtK(r.call_volume)} · ${r.call_sold_pct.toFixed(0)}% vendido / ${cb}% comprado</div>` +
      `<div class="tt-put">Puts&nbsp; ${fmtK(r.put_volume)} · ${r.put_sold_pct.toFixed(0)}% vendido / ${pb}% comprado</div>` +
      `<div>GEX ${r.gamma_exposure.toFixed(1)} M$ · magnet ${r.magnet.toFixed(2)}</div>` +
      `<div class="tt-dim">clic para fijar/soltar el strike</div>`;
  },

  attachMouse(profile, series, gamma, magnet) {
    const hoverStrike = (panelName, indexFn, reversed = false) => (panel) => {
      panel.canvas.addEventListener("pointermove", (e) => {
        if (!this.data) return;
        const rows = this.data.strikes;
        const i = clamp(indexFn(e, panel, rows), 0, rows.length - 1);
        this.hover = { panel: panelName, index: i };
        const r = reversed ? [...rows].reverse()[i] : rows[i];
        showTooltip(this.strikeTooltip(r), e.clientX, e.clientY);
        this.render();
      });
      panel.canvas.addEventListener("pointerleave", () => {
        this.hover = { panel: null, index: -1 };
        hideTooltip();
        this.render();
      });
    };

    hoverStrike("profile", (e, p, rows) => Math.floor(e.offsetX / (p.w / rows.length)))(profile);
    profile.canvas.addEventListener("click", (e) => {
      if (!this.data) return;
      const rows = this.data.strikes;
      const strike = rows[clamp(Math.floor(e.offsetX / (profile.w / rows.length)), 0, rows.length - 1)].strike;
      this.pinnedStrike = this.pinnedStrike === strike ? null : strike;
      this.render();
    });

    hoverStrike("gamma", (e, p, rows) =>
      Math.floor((e.offsetX - this.GPAD.l) / ((p.w - this.GPAD.l - this.GPAD.r) / rows.length)))(gamma);
    hoverStrike("magnet", (e, p, rows) =>
      Math.floor((e.offsetY - this.MPAD.t) / ((p.h - this.MPAD.t - this.MPAD.b) / rows.length)), true)(magnet);

    series.canvas.addEventListener("pointermove", (e) => {
      if (!this.data || this.data.series.length < 2) return;
      const s = this.seriesScales(series.w, series.h);
      const frac = (e.offsetX - this.SPAD.l) / (series.w - this.SPAD.l - this.SPAD.r);
      const i = clamp(Math.round(frac * (s.pts.length - 1)), 0, s.pts.length - 1);
      this.hover = { panel: "series", index: i };
      const p = s.pts[i];
      showTooltip(
        `<div class="tt-title">${p.t}</div>` +
        `<div>precio ${p.price.toFixed(2)}</div>` +
        `<div class="tt-put">put sell ${p.put_sell_pct.toFixed(1)}%</div>` +
        `<div class="tt-call">call sell ${p.call_sell_pct.toFixed(1)}%</div>` +
        (p.iv > 0 ? `<div style="color:#e0954b">IV ${(p.iv * 100).toFixed(2)}%</div>` : ""),
        e.clientX, e.clientY);
      this.render();
    });
    series.canvas.addEventListener("pointerleave", () => {
      this.hover = { panel: null, index: -1 };
      hideTooltip();
      this.render();
    });
  },
};
