/* Vista Setup: footprint + Wyckoff + Volume Profile en un solo apartado.
 *
 * Arriba: velas de la sesión con eventos Wyckoff detectados por heurística
 * (spring, upthrust, SOS, SOW, absorción effort-vs-result) y el Volume
 * Profile en el margen derecho compartiendo eje de precio (POC ámbar,
 * área de valor 70% sombreada, VAH/VAL punteados).
 * Abajo: el footprint completo (reutiliza el render de FootprintView).
 */
"use strict";

const SetupView = {
  data: null,
  chart: null,
  fp: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="setup-wrap">
        <section class="panel setup-chart">
          <div class="panel-head">
            <h2>Wyckoff + Volume Profile</h2>
            <span class="hint">SC/BC clímax · AR reacción · ST retest · SPRING/UT · SOS/SOW · ABS absorción · POC ámbar · ${ZOOM_HINT}</span>
          </div>
          <canvas id="setupChart"></canvas>
        </section>
        <section class="panel setup-fp">
          <div class="panel-head"><h2>Footprint</h2>
            <span class="hint">vendido × comprado por nivel · ámbar = POC · borde = imbalance ≥3×</span></div>
          <canvas id="setupFp"></canvas>
        </section>
      </div>`;

    this.chart = new Panel(root.querySelector("#setupChart"), (c, w, h) => this.drawChart(c, w, h));
    this.vp = new BarViewport(() => this.chart && this.chart.draw());
    this.vp.attach(this.chart.canvas, {
      total: () => (this.data ? this.data.bars.length : 0),
      defaultCount: () => (this.data ? this.data.bars.length : 1),
      plot: () => [this.PAD.l, this.chart.w - this.PAD.l - this.PAD.r],
    });
    // footprint embebido: delega en FootprintView vía prototipo
    this.fp = Object.create(FootprintView);
    this.fp.data = null;
    this.fp.hover = { bar: -1, level: null };
    this.fp.panel = new Panel(root.querySelector("#setupFp"), (c, w, h) => this.fp.draw(c, w, h));
    this.fp.vp = new BarViewport(() => this.fp.panel && this.fp.panel.draw());
    this.fp.vp.attach(this.fp.panel.canvas, {
      total: () => (this.fp.data ? this.fp.data.bars.length : 0),
      defaultCount: () => Math.max(3, Math.floor((this.fp.panel.w - this.fp.PAD.l - this.fp.PAD.r) / 110)),
      plot: () => [this.fp.PAD.l, this.fp.panel.w - this.fp.PAD.l - this.fp.PAD.r],
    });
    this.fp.attachMouse();
    this.attachMouse();
  },

  unmount() {
    if (this.chart) this.chart.destroy();
    if (this.fp && this.fp.panel) this.fp.panel.destroy();
    this.chart = null;
    this.fp = null;
    this.data = null;
    hideTooltip();
  },

  onData(payload) {
    this.data = payload.footprint;
    if (this.fp) {
      this.fp.data = payload.footprint;
      this.fp.panel.draw();
    }
    if (this.chart) this.chart.draw();
  },

  /* ------------------------------------------------------ volume profile */

  profile() {
    const totals = new Map();
    this.data.bars.forEach(bar => bar.cells.forEach(cell => {
      totals.set(cell.price, (totals.get(cell.price) || 0) + cell.buy + cell.sell);
    }));
    const levels = [...totals.entries()].sort((a, b) => a[0] - b[0]); // ascendente
    if (!levels.length) return null;
    const grand = levels.reduce((acc, [, v]) => acc + v, 0);
    let pocIdx = 0;
    levels.forEach(([, v], i) => { if (v > levels[pocIdx][1]) pocIdx = i; });

    // área de valor 70%: expandir desde el POC hacia el vecino con más volumen
    let lo = pocIdx, hi = pocIdx, acc = levels[pocIdx][1];
    while (acc < grand * 0.7 && (lo > 0 || hi < levels.length - 1)) {
      const below = lo > 0 ? levels[lo - 1][1] : -1;
      const above = hi < levels.length - 1 ? levels[hi + 1][1] : -1;
      if (above >= below) { hi += 1; acc += levels[hi][1]; }
      else { lo -= 1; acc += levels[lo][1]; }
    }
    return {
      levels, maxVol: levels[pocIdx][1],
      poc: levels[pocIdx][0], val: levels[lo][0], vah: levels[hi][0],
    };
  },

  /* ---------------------------------------------------- eventos wyckoff */

  /* Clímax y estructura: SC/BC (rango y volumen extremos con cierre en el
   * extremo y nuevo mínimo/máximo), AR (reacción automática: el swing
   * opuesto en las 6 barras siguientes), ST (retest del clímax con menos
   * volumen). Devuelve mapa índice→evento; pisa a las señales por barra. */
  structuralEvents(bars, quantile) {
    const events = {};
    const ranges = bars.map(b => b.high - b.low);
    const volumes = bars.map(b => b.volume);
    const rangeP85 = quantile(ranges, 0.85);
    const volP85 = quantile(volumes, 0.85);
    let runLow = Infinity, runHigh = -Infinity;
    let sc = null, bc = null;
    bars.forEach((bar, i) => {
      const range = Math.max(bar.high - bar.low, 1e-9);
      const pos = (bar.close - bar.low) / range;
      if (sc === null && range >= rangeP85 && bar.volume >= volP85 &&
          pos < 0.35 && bar.low <= runLow) {
        sc = i;
      }
      if (bc === null && range >= rangeP85 && bar.volume >= volP85 &&
          pos > 0.65 && bar.high >= runHigh) {
        bc = i;
      }
      runLow = Math.min(runLow, bar.low);
      runHigh = Math.max(runHigh, bar.high);
    });

    const chain = (climaxIdx, isSelling) => {
      const climax = bars[climaxIdx];
      events[climaxIdx] = {
        tag: isSelling ? "SC" : "BC", side: isSelling ? "below" : "above",
        color: COLORS.accent,
        note: isSelling ? "selling climax: pánico con rango y volumen extremos — posible suelo"
                        : "buying climax: euforia con rango y volumen extremos — posible techo",
      };
      // AR: el swing opuesto en las 6 barras siguientes
      let ar = null, best = isSelling ? -Infinity : Infinity;
      for (let j = climaxIdx + 1; j < Math.min(bars.length, climaxIdx + 7); j++) {
        const v = isSelling ? bars[j].high : bars[j].low;
        if (isSelling ? v > best : v < best) { best = v; ar = j; }
      }
      if (ar === null || ar === climaxIdx) return;
      events[ar] = events[ar] || {
        tag: "AR", side: isSelling ? "above" : "below", color: COLORS.call,
        note: "automatic rally/reaction: el rebote que define el rango de trading",
      };
      // ST: retest del clímax con menos volumen, pasado el AR
      const span = Math.abs(best - (isSelling ? climax.low : climax.high));
      for (let j = ar + 1; j < bars.length; j++) {
        const near = isSelling
          ? bars[j].low <= climax.low + span * 0.25
          : bars[j].high >= climax.high - span * 0.25;
        if (near && bars[j].volume < climax.volume) {
          events[j] = events[j] || {
            tag: "ST", side: isSelling ? "below" : "above", color: COLORS.dim,
            note: "secondary test: retest del clímax con menos volumen — confirma el extremo",
          };
          break;
        }
      }
    };
    if (sc !== null) chain(sc, true);
    if (bc !== null) chain(bc, false);
    return events;
  },

  wyckoffEvents(bars, vp) {
    const quantile = (values, q) => {
      const sorted = [...values].sort((a, b) => a - b);
      return sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
    };
    const structural = this.structuralEvents(bars, quantile);
    const ranges = bars.map(b => b.high - b.low);
    const volumes = bars.map(b => b.volume);
    const wideRange = quantile(ranges, 0.6);
    const highVol = quantile(volumes, 0.75);
    const narrowRange = quantile(ranges, 0.3);

    return bars.map((bar, i) => {
      if (structural[i]) return structural[i];
      if (i === 0) return null;
      // spring / upthrust contra el área de valor
      if (bar.low < vp.val && bar.close > vp.val) {
        return { tag: "SPRING", side: "below", color: COLORS.bought,
                 note: "barrió mínimos del área de valor y recuperó — posible giro alcista" };
      }
      if (bar.high > vp.vah && bar.close < vp.vah) {
        return { tag: "UT", side: "above", color: COLORS.sold,
                 note: "upthrust: superó el área de valor y falló — posible giro bajista" };
      }
      // SOS / SOW: ruptura con rango amplio y delta a favor
      const prevHigh = Math.max(...bars.slice(Math.max(0, i - 3), i).map(b => b.high));
      const prevLow = Math.min(...bars.slice(Math.max(0, i - 3), i).map(b => b.low));
      const range = bar.high - bar.low;
      if (bar.close > prevHigh && bar.delta > 0 && range >= wideRange) {
        return { tag: "SOS", side: "above", color: COLORS.bought,
                 note: "sign of strength: ruptura con rango amplio y delta comprador" };
      }
      if (bar.close < prevLow && bar.delta < 0 && range >= wideRange) {
        return { tag: "SOW", side: "below", color: COLORS.sold,
                 note: "sign of weakness: ruptura bajista con rango amplio y delta vendedor" };
      }
      // absorción: mucho esfuerzo (volumen), poco resultado (rango)
      if (bar.volume >= highVol && range <= narrowRange) {
        return { tag: "ABS", side: bar.delta >= 0 ? "below" : "above", color: COLORS.accent,
                 note: "effort vs result: volumen alto sin desplazamiento — absorción" };
      }
      return null;
    });
  },

  /* --------------------------------------------------------------- dibujo */

  PAD: { l: 10, r: 218, t: 16, b: 12, volH: 54, vpGap: 8 },

  geometry(w, h) {
    if (!this.data || !this.data.bars.length) return null;
    const vp = this.profile();
    if (!vp) return null;
    const P = this.PAD;
    const all = this.data.bars;
    const range = this.vp ? this.vp.view(all.length, all.length)
                          : { start: 0, end: all.length };
    const bars = all.slice(range.start, range.end);
    if (!bars.length) return null;
    const colW = (w - P.l - P.r) / bars.length;
    let hi = Math.max(...bars.map(b => b.high));
    let lo = Math.min(...bars.map(b => b.low));
    const pad = (hi - lo) * 0.06 + this.data.tick;
    hi += pad; lo -= pad;
    const plotH = h - P.t - P.b - P.volH;
    const y = (price) => P.t + (1 - (price - lo) / (hi - lo)) * plotH;
    const x = (i) => P.l + i * colW + colW / 2;
    return { bars, vp, colW, hi, lo, y, x, plotH };
  },

  drawChart(ctx, w, h) {
    const g = this.geometry(w, h);
    if (!g) return;
    const P = this.PAD;
    const { bars, vp, colW, y, x } = g;
    const events = this.wyckoffEvents(bars, vp);
    const vpX0 = w - P.r + P.vpGap + 46;
    const vpW = P.r - P.vpGap - 56;

    // sombreado del área de valor a lo ancho del gráfico
    ctx.fillStyle = "rgba(232, 184, 75, 0.055)";
    ctx.fillRect(P.l, y(vp.vah), w - P.l - P.r, y(vp.val) - y(vp.vah));
    for (const [level, style] of [[vp.vah, COLORS.dim], [vp.val, COLORS.dim]]) {
      ctx.strokeStyle = style;
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(P.l, y(level)); ctx.lineTo(w - P.r + P.vpGap + vpW + 46, y(level)); ctx.stroke();
      ctx.setLineDash([]);
    }
    // POC
    ctx.strokeStyle = COLORS.accent;
    ctx.setLineDash([6, 3]);
    ctx.beginPath(); ctx.moveTo(P.l, y(vp.poc)); ctx.lineTo(w - P.r + P.vpGap + vpW + 46, y(vp.poc)); ctx.stroke();
    ctx.setLineDash([]);

    // volume profile en el margen derecho (comparte eje de precio)
    const levelSpan = vp.levels.length > 1
      ? Math.abs(y(vp.levels[0][0]) - y(vp.levels[1][0]))
      : 14;
    const rowH = clamp(levelSpan * 0.85, 2, 14);
    vp.levels.forEach(([price, volume]) => {
      const bw = vpW * volume / vp.maxVol;
      const inVA = price >= vp.val - 1e-9 && price <= vp.vah + 1e-9;
      const isPoc = Math.abs(price - vp.poc) < this.data.tick / 2;
      ctx.fillStyle = isPoc ? COLORS.accent
        : inVA ? "rgba(93, 179, 217, 0.55)" : "rgba(124, 135, 152, 0.35)";
      ctx.fillRect(vpX0, y(price) - rowH / 2, bw, rowH);
    });
    ctx.font = MONO;
    ctx.fillStyle = COLORS.accent;
    ctx.textAlign = "left";
    ctx.fillText("POC " + vp.poc.toFixed(2), vpX0, y(vp.poc) - 6);
    ctx.fillStyle = COLORS.dim;
    ctx.fillText("VAH " + vp.vah.toFixed(2), vpX0, y(vp.vah) - 4);
    ctx.fillText("VAL " + vp.val.toFixed(2), vpX0, y(vp.val) + 12);

    // eje de precios entre gráfico y perfil
    ctx.textAlign = "right";
    const steps = Math.max(3, Math.floor(g.plotH / 46));
    for (let s = 0; s <= steps; s++) {
      const price = g.lo + ((g.hi - g.lo) / steps) * s;
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(price.toFixed(2), vpX0 - 8, y(price) + 3);
    }

    // velas + volumen + eventos
    const maxVol = Math.max(1, ...bars.map(b => b.volume));
    const volY0 = h - P.b;
    bars.forEach((bar, i) => {
      const cx = x(i);
      const bull = bar.close >= bar.open;
      const color = bull ? COLORS.bought : COLORS.sold;
      const hot = this.hover === i;

      ctx.strokeStyle = color;
      ctx.lineWidth = hot ? 2 : 1;
      ctx.beginPath(); ctx.moveTo(cx, y(bar.high)); ctx.lineTo(cx, y(bar.low)); ctx.stroke();
      ctx.lineWidth = 1;
      const bodyTop = y(Math.max(bar.open, bar.close));
      const bodyH = Math.max(1.5, y(Math.min(bar.open, bar.close)) - bodyTop);
      ctx.fillStyle = hot ? color : (bull ? "rgba(47,164,99,0.85)" : "rgba(224,67,63,0.85)");
      ctx.fillRect(cx - colW * 0.3, bodyTop, colW * 0.6, bodyH);

      // volumen coloreado por delta
      const vh = (P.volH - 16) * bar.volume / maxVol;
      ctx.fillStyle = bar.delta >= 0 ? "rgba(47,164,99,0.55)" : "rgba(224,67,63,0.55)";
      ctx.fillRect(cx - colW * 0.3, volY0 - vh, colW * 0.6, vh);

      const event = events[i];
      if (event) {
        ctx.font = "700 " + MONO;
        ctx.textAlign = "center";
        ctx.fillStyle = event.color;
        if (event.side === "above") {
          ctx.fillText("▼", cx, y(bar.high) - 16);
          ctx.fillText(event.tag, cx, y(bar.high) - 26);
        } else {
          ctx.fillText("▲", cx, y(bar.low) + 22);
          ctx.fillText(event.tag, cx, y(bar.low) + 34);
        }
        ctx.font = MONO;
      }
      if (i % Math.ceil(bars.length / 8) === 0) {
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.dim;
        ctx.fillText(bar.t, cx, volY0 + 10);
      }
    });
  },

  attachMouse() {
    const canvas = this.chart.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (this.vp && this.vp.dragging) { hideTooltip(); return; }
      const g = this.geometry(this.chart.w, this.chart.h);
      if (!g) return;
      if (e.offsetX > this.chart.w - this.PAD.r) { this.hover = -1; hideTooltip(); this.chart.draw(); return; }
      const i = clamp(Math.floor((e.offsetX - this.PAD.l) / g.colW), 0, g.bars.length - 1);
      this.hover = i;
      const bar = g.bars[i];
      const event = this.wyckoffEvents(g.bars, g.vp)[i];
      showTooltip(
        `<div class="tt-title">${bar.t}${event ? " · " + event.tag : ""}</div>` +
        `<div>O ${bar.open.toFixed(2)} H ${bar.high.toFixed(2)} L ${bar.low.toFixed(2)} C ${bar.close.toFixed(2)}</div>` +
        `<div class="${bar.delta >= 0 ? "tt-call" : "tt-put"}">Δ ${fmtK(bar.delta)} · vol ${fmtK(bar.volume)}</div>` +
        (event ? `<div class="tt-dim">${event.note}</div>` : ""),
        e.clientX, e.clientY);
      this.chart.draw();
    });
    canvas.addEventListener("pointerleave", () => {
      this.hover = -1;
      hideTooltip();
      this.chart.draw();
    });
  },
};
