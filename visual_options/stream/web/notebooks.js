/* Notebooks (método original): el gráfico histórico + proyección de los
 * .ipynb del usuario, sin cambios — informativo. Las versiones corregidas
 * están en la vista Estadísticos. */
"use strict";

const NotebooksView = {
  panel: null,
  result: null,

  FUTURES: ["ES=F", "NQ=F", "YM=F", "GC=F"],

  mount(root) {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Notebooks · método original</h2>
            <span class="hint">tal cual tus .ipynb: 15m/7d, ARIMA+GARCH con 1 trayectoria (seed 42) o bandas GARCH · sin correcciones — la versión revisada está en STATS</span>
            <div class="stats-controls">
              <button class="srcbtn active" data-var="daily">Daily (ARIMA+GARCH)</button>
              <button class="srcbtn" data-var="meanzero">MeanZero (bandas)</button>
              <input id="nbSymbol" class="scan-input" style="min-width:90px" value="${symbol}"
                     title="símbolo (los notebooks usaban ES=F, NQ=F, YM=F, GC=F)">
              ${this.FUTURES.map(f => `<button class="qchip" data-fut="${f}">${f}</button>`).join("")}
              <button id="nbRun" class="btn btn-primary">Generar</button>
            </div>
          </div>
          <div class="nb-body">
            <canvas id="nbCanvas"></canvas>
            <div class="nb-params" id="nbParams">pulsa Generar</div>
          </div>
        </section>
      </div>`;

    this.variant = "daily";
    this.el = {
      symbol: root.querySelector("#nbSymbol"),
      params: root.querySelector("#nbParams"),
      run: root.querySelector("#nbRun"),
    };
    this.panel = new Panel(root.querySelector("#nbCanvas"), (c, w, h) => this.draw(c, w, h));

    root.querySelectorAll("[data-var]").forEach(btn => btn.addEventListener("click", () => {
      this.variant = btn.dataset.var;
      root.querySelectorAll("[data-var]").forEach(b => b.classList.toggle("active", b === btn));
    }));
    root.querySelectorAll("[data-fut]").forEach(chip =>
      chip.addEventListener("click", () => { this.el.symbol.value = chip.dataset.fut; }));
    this.el.run.addEventListener("click", () => this.generate());
    this.el.symbol.addEventListener("keydown", (e) => { if (e.key === "Enter") this.generate(); });
    this.generate();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.result = null;
    this.el = null;
  },

  onData() {},

  async generate() {
    this.el.run.disabled = true;
    this.el.run.textContent = "ajustando…";
    this.el.params.textContent = "descargando 15m/7d y ajustando el modelo original…";
    try {
      const symbol = encodeURIComponent(this.el.symbol.value.trim().toUpperCase());
      const response = await fetch(`/api/notebooks?symbol=${symbol}&variant=${this.variant}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.result = await response.json();
      const params = this.result.params;
      const fmt = (obj) => Object.entries(obj).map(([key, value]) => `${key}=${value}`).join(" · ");
      this.el.params.innerHTML =
        `<b>${this.result.label}</b><br>` +
        (params.arima ? `ARIMA: ${fmt(params.arima)}<br>` : "") +
        `GARCH: ${fmt(params.garch)}<br>` +
        `<span class="tt-dim">último precio ${this.result.last_price.toFixed(2)} · ${this.result.history.close.length} velas de ${this.result.interval} (${this.result.period}) · horizonte ${this.result.horizon} pasos</span>`;
      this.panel.draw();
    } catch (err) {
      this.el.params.textContent = "error: " + err.message;
    } finally {
      this.el.run.disabled = false;
      this.el.run.textContent = "Generar";
    }
  },

  PAD: { l: 14, r: 62, t: 14, b: 26 },

  draw(ctx, w, h) {
    const r = this.result;
    if (!r) return;
    const P = this.PAD;
    const hist = r.history.close;
    const proj = r.projection;
    const total = hist.length + proj.length;
    const all = hist.concat(proj, r.upper || [], r.lower || []);
    const hi = Math.max(...all), lo = Math.min(...all);
    const pad = (hi - lo) * 0.05 + 0.01;
    const x = (i) => P.l + (i / (total - 1)) * (w - P.l - P.r);
    const y = (v) => P.t + (1 - (v - lo + pad) / (hi - lo + 2 * pad)) * (h - P.t - P.b);

    // banda ±1σ (variante meanzero)
    if (r.upper && r.lower) {
      ctx.beginPath();
      r.upper.forEach((v, i) => i === 0 ? ctx.moveTo(x(hist.length + i), y(v))
                                        : ctx.lineTo(x(hist.length + i), y(v)));
      for (let i = r.lower.length - 1; i >= 0; i--) ctx.lineTo(x(hist.length + i), y(r.lower[i]));
      ctx.closePath();
      ctx.fillStyle = "rgba(93, 179, 217, 0.15)";
      ctx.fill();
    }

    // histórico (negro en matplotlib → blanco aquí)
    ctx.beginPath();
    hist.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
    ctx.strokeStyle = COLORS.price;
    ctx.lineWidth = 1.6;
    ctx.stroke();

    // proyección (azul, como en los notebooks)
    ctx.beginPath();
    ctx.moveTo(x(hist.length - 1), y(hist[hist.length - 1]));
    proj.forEach((v, i) => ctx.lineTo(x(hist.length + i), y(v)));
    ctx.strokeStyle = "#4d8fd9";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    // separador ahora
    ctx.strokeStyle = COLORS.border;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(x(hist.length - 1), P.t); ctx.lineTo(x(hist.length - 1), h - P.b); ctx.stroke();
    ctx.setLineDash([]);

    // ejes
    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let g = 0; g <= 4; g++) {
      const v = lo + ((hi - lo) / 4) * g;
      ctx.fillText(v.toFixed(1), w - P.r + 6, y(v) + 3);
    }
    ctx.textAlign = "center";
    const times = r.history.t;
    const step = Math.max(1, Math.floor(times.length / 6));
    for (let i = 0; i < times.length; i += step) ctx.fillText(times[i], x(i), h - 8);
    ctx.fillStyle = "#4d8fd9";
    ctx.fillText("proyección", x(hist.length + proj.length / 2), P.t + 2);
  },
};
