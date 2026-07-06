/* Estadísticos: batería de tests sobre los retornos reales del símbolo
 * (qué hace cada uno + veredicto) y Monte Carlo GARCH con un botón.
 * Versión corregida de los notebooks ARIMA+GARCH del usuario. */
"use strict";

const StatsView = {
  panel: null,
  mc: null,
  interval: localStorage.getItem("vo-stats-interval") || "15m",

  INTERVALS: [["5m", "5m · 5d"], ["15m", "15m · 7d"], ["1h", "1h · 1mes"], ["1d", "diario · 1año"]],

  mount(root) {
    root.innerHTML = `
      <div class="stats-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Estadísticos</h2>
            <span class="hint">batería sobre retornos log reales (Yahoo) · veredicto por test · los notebooks originales proyectaban 1 sola trayectoria: aquí Monte Carlo de verdad</span>
            <div class="stats-controls">
              ${this.INTERVALS.map(([value, label]) =>
                `<button class="srcbtn ${value === this.interval ? "active" : ""}" data-int="${value}">${label}</button>`).join("")}
              <button id="stRun" class="btn">Analizar</button>
              <button id="stMc" class="btn btn-primary">▶ Monte Carlo</button>
            </div>
          </div>
          <div class="stats-body">
            <div id="stCards" class="stats-cards"><div class="scan-empty">pulsa Analizar o Monte Carlo</div></div>
            <div class="stats-mc" id="stMcWrap" hidden>
              <div class="vwap-tiles" id="stMcTiles"></div>
              <canvas id="stMcCanvas"></canvas>
            </div>
          </div>
        </section>
      </div>`;

    this.el = {
      cards: root.querySelector("#stCards"),
      mcWrap: root.querySelector("#stMcWrap"),
      mcTiles: root.querySelector("#stMcTiles"),
      run: root.querySelector("#stRun"),
      mcBtn: root.querySelector("#stMc"),
    };
    this.panel = new Panel(root.querySelector("#stMcCanvas"), (c, w, h) => this.drawMc(c, w, h));

    root.querySelectorAll("[data-int]").forEach(btn => btn.addEventListener("click", () => {
      this.interval = btn.dataset.int;
      localStorage.setItem("vo-stats-interval", this.interval);
      root.querySelectorAll("[data-int]").forEach(b => b.classList.toggle("active", b === btn));
    }));
    this.el.run.addEventListener("click", () => this.analyze());
    this.el.mcBtn.addEventListener("click", () => this.runMonteCarlo());
    this.analyze();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.mc = null;
    this.el = null;
  },

  onData() {},  // trabaja con históricos, no con el stream

  symbol() { return localStorage.getItem("vo-symbol") || "QQQ"; },

  async analyze() {
    this.el.cards.innerHTML = `<div class="scan-empty">descargando ${this.symbol()} (${this.interval}) y calculando…</div>`;
    try {
      const response = await fetch(`/api/stats?symbol=${this.symbol()}&interval=${this.interval}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      const data = await response.json();
      this.el.cards.innerHTML = data.cards.map(card => `
        <div class="stat-card ${card.verdict}">
          <div class="st-head">
            <b>${card.name}</b>
            <span class="st-verdict">${card.verdict === "ok" ? "✓ bien" : card.verdict === "warn" ? "△ aviso" : "✗ mal"}</span>
          </div>
          <p class="st-does">${card.does}</p>
          <p class="st-result">${card.result}</p>
          <p class="st-note">${card.note}</p>
        </div>`).join("") +
        `<div class="stat-card meta"><div class="st-head"><b>${data.symbol} · ${this.interval} (${data.period})</b></div>
         <p class="st-does">último precio ${data.last_price.toFixed(2)} · datos reales de Yahoo con ~15 min de retraso</p></div>`;
    } catch (err) {
      this.el.cards.innerHTML = `<div class="scan-empty">error: ${err.message}</div>`;
    }
  },

  async runMonteCarlo() {
    this.el.mcBtn.disabled = true;
    this.el.mcBtn.textContent = "simulando…";
    try {
      const response = await fetch(
        `/api/stats/montecarlo?symbol=${this.symbol()}&interval=${this.interval}&paths=2000&horizon=96`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.mc = await response.json();
      this.el.mcWrap.hidden = false;
      const mc = this.mc;
      const pct = (v) => (v * 100).toFixed(1) + "%";
      const tile = (label, value, cls = "") =>
        `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`;
      this.el.mcTiles.innerHTML =
        tile("Prob. de subir", pct(mc.prob_up), mc.prob_up >= 0.5 ? "pos" : "neg") +
        tile("Mediana final", mc.expected.toFixed(2)) +
        tile("Rango 90%", `${mc.range90[0].toFixed(2)} – ${mc.range90[1].toFixed(2)}`) +
        tile("VaR 95%", "−" + mc.var95.toFixed(2), "neg") +
        tile("Rutas", `${mc.paths} · bootstrap`) +
        tile("GARCH α+β", mc.garch.persistence.toFixed(3), mc.garch.converged ? "pos" : "neg");
      this.panel.resize();
      this.panel.draw();
    } catch (err) {
      this.el.mcTiles.innerHTML = `<div class="scan-empty">error: ${err.message}</div>`;
      this.el.mcWrap.hidden = false;
    } finally {
      this.el.mcBtn.disabled = false;
      this.el.mcBtn.textContent = "▶ Monte Carlo";
    }
  },

  PAD: { l: 12, r: 66, t: 16, b: 24 },

  drawMc(ctx, w, h) {
    const mc = this.mc;
    if (!mc) return;
    const P = this.PAD;
    const bands = mc.bands;  // horizon × [p5,p25,p50,p75,p95]
    const all = bands.flat().concat([mc.last_price]);
    const hi = Math.max(...all), lo = Math.min(...all);
    const pad = (hi - lo) * 0.05 + 0.01;
    const x = (t) => P.l + ((t + 1) / bands.length) * (w - P.l - P.r);
    const y = (v) => P.t + (1 - (v - lo + pad) / (hi - lo + 2 * pad)) * (h - P.t - P.b);

    const drawBand = (idxLow, idxHigh, color) => {
      ctx.beginPath();
      ctx.moveTo(P.l, y(mc.last_price));
      bands.forEach((row, t) => ctx.lineTo(x(t), y(row[idxHigh])));
      for (let t = bands.length - 1; t >= 0; t--) ctx.lineTo(x(t), y(bands[t][idxLow]));
      ctx.lineTo(P.l, y(mc.last_price));
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    };
    drawBand(0, 4, "rgba(93, 179, 217, 0.12)");   // P5–P95
    drawBand(1, 3, "rgba(93, 179, 217, 0.22)");   // P25–P75

    // mediana
    ctx.beginPath();
    ctx.moveTo(P.l, y(mc.last_price));
    bands.forEach((row, t) => ctx.lineTo(x(t), y(row[2])));
    ctx.strokeStyle = COLORS.price;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    // nivel actual
    ctx.strokeStyle = COLORS.accent;
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(P.l, y(mc.last_price)); ctx.lineTo(w - P.r, y(mc.last_price)); ctx.stroke();
    ctx.setLineDash([]);

    // etiquetas
    ctx.font = MONO;
    ctx.textAlign = "left";
    const last = bands[bands.length - 1];
    const labels = [["P95", last[4], COLORS.bought], ["P75", last[3], COLORS.dim],
                    ["P50", last[2], COLORS.price], ["P25", last[1], COLORS.dim],
                    ["P5", last[0], COLORS.sold]];
    labels.forEach(([tag, value, color]) => {
      ctx.fillStyle = color;
      ctx.fillText(`${tag} ${value.toFixed(2)}`, w - P.r + 5, y(value) + 3);
    });
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "center";
    ctx.fillText("ahora", P.l + 18, h - 8);
    ctx.fillText(`+${mc.horizon} barras (${this.interval})`, w - P.r - 60, h - 8);
  },
};
