/* Calculadora de estrategias (Options Calculator): las 23 estrategias del
 * libro con P/L a expiración + T+0, breakevens, prob. de beneficio y
 * griegas. Las primas se escriben o se estiman con BSM (auto-precio). */
"use strict";

const CalcView = {
  data: null,
  panel: null,
  catalog: [],
  result: null,

  mount(root) {
    root.innerHTML = `
      <div class="calc-wrap">
        <section class="panel calc-form">
          <div class="panel-head"><h2>Calculadora</h2>
            <span class="hint">estrategias del libro Visual Guide to Options</span></div>
          <div class="calc-controls">
            <label>Estrategia
              <select id="calcStrategy"></select>
            </label>
            <div id="calcParams" class="calc-params"></div>
            <div class="calc-ctx">
              <label>Spot <input id="calcSpot" type="number" step="0.01"></label>
              <label>IV <input id="calcIV" type="number" step="0.01" value="0.30"></label>
              <label>Días <input id="calcDays" type="number" step="1" value="30"></label>
              <label class="calc-check"><input id="calcAuto" type="checkbox" checked> auto-precio BSM</label>
            </div>
            <button id="calcRun" class="btn btn-primary">Calcular</button>
            <div id="calcError" class="calc-error" hidden></div>
            <div id="calcMetrics" class="calc-metrics"></div>
          </div>
        </section>
        <section class="panel calc-chart">
          <div class="panel-head"><h2 id="calcTitle">P/L</h2></div>
          <canvas id="calcCanvas"></canvas>
        </section>
      </div>`;

    this.el = {
      strategy: root.querySelector("#calcStrategy"),
      params: root.querySelector("#calcParams"),
      spot: root.querySelector("#calcSpot"),
      iv: root.querySelector("#calcIV"),
      days: root.querySelector("#calcDays"),
      auto: root.querySelector("#calcAuto"),
      run: root.querySelector("#calcRun"),
      error: root.querySelector("#calcError"),
      metrics: root.querySelector("#calcMetrics"),
      title: root.querySelector("#calcTitle"),
    };
    this.panel = new Panel(root.querySelector("#calcCanvas"), (c, w, h) => this.draw(c, w, h));

    fetch("/api/calculator/strategies").then(r => r.json()).then(catalog => {
      this.catalog = catalog;
      this.el.strategy.innerHTML = catalog.map(s =>
        `<option value="${s.id}">${s.id.replaceAll("_", " ")}</option>`).join("");
      this.el.strategy.value = "bull_put_spread";
      this.renderParams();
    });

    this.el.strategy.addEventListener("change", () => this.renderParams());
    this.el.auto.addEventListener("change", () => this.renderParams());
    this.el.run.addEventListener("click", () => this.calculate());
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.result = null;
  },

  onData(payload) {
    this.data = payload.flow;
    // precarga el spot del símbolo activo si el campo está vacío
    if (this.el && !this.el.spot.value && this.data.spot) {
      this.el.spot.value = this.data.spot.toFixed(2);
      const atm = this.data.strikes.reduce((a, b) =>
        Math.abs(b.strike - this.data.spot) < Math.abs(a.strike - this.data.spot) ? b : a,
        this.data.strikes[0]);
      if (atm && atm.iv) this.el.iv.value = atm.iv.toFixed(2);
      this.prefillStrikes();
      if (!this.result) this.calculate();  // primer cálculo automático
    }
  },

  entry(id) { return this.catalog.find(s => s.id === id); },

  renderParams() {
    const entry = this.entry(this.el.strategy.value);
    if (!entry) return;
    const auto = this.el.auto.checked;
    this.el.params.innerHTML = entry.params.map(p => {
      const isPremium = p.endsWith("premium") || /^p\d+$/.test(p);
      if (isPremium && auto) return "";
      const type = p === "kind"
        ? `<select data-param="kind"><option value="call">call</option><option value="put">put</option></select>`
        : `<input data-param="${p}" type="number" step="0.01">`;
      return `<label>${p.replaceAll("_", " ")} ${type}</label>`;
    }).join("");
    this.prefillStrikes();
  },

  // offsets de prefill (en pasos de strike respecto al ATM) por estrategia,
  // respetando el orden que exige cada builder
  PRESETS: {
    long_call: { strike: 0 }, short_call: { strike: 2 },
    long_put: { strike: 0 }, short_put: { strike: -2 },
    covered_call: { stock_cost: "spot", call_strike: 2 },
    protective_put: { stock_cost: "spot", put_strike: -2 },
    collar: { stock_cost: "spot", put_strike: -2, call_strike: 2 },
    bull_call_spread: { long_strike: 0, short_strike: 2 },
    bear_call_spread: { short_strike: 1, long_strike: 3 },
    bull_put_spread: { short_strike: -1, long_strike: -3 },
    bear_put_spread: { long_strike: 0, short_strike: -2 },
    long_straddle: { strike: 0 }, short_straddle: { strike: 0 },
    long_strangle: { put_strike: -2, call_strike: 2 },
    short_strangle: { put_strike: -2, call_strike: 2 },
    long_butterfly: { lower_strike: -2, center_strike: 0, upper_strike: 2 },
    short_butterfly: { lower_strike: -2, center_strike: 0, upper_strike: 2 },
    long_condor: { s1: -3, s2: -1, s3: 1, s4: 3 },
    short_condor: { s1: -3, s2: -1, s3: 1, s4: 3 },
    short_iron_butterfly: { center_strike: 0, wing_put_strike: -3, wing_call_strike: 3 },
    long_iron_butterfly: { center_strike: 0, wing_put_strike: -3, wing_call_strike: 3 },
    short_iron_condor: { put_wing_strike: -4, short_put_strike: -2, short_call_strike: 2, call_wing_strike: 4 },
    long_iron_condor: { put_wing_strike: -4, long_put_strike: -2, long_call_strike: 2, call_wing_strike: 4 },
  },

  prefillStrikes() {
    if (!this.data || !this.data.spot) return;
    const spot = this.data.spot;
    const preset = this.PRESETS[this.el.strategy.value] || {};
    const step = Math.max(1, Math.round(spot * 0.01));
    this.el.params.querySelectorAll("input[data-param]").forEach(input => {
      const offset = preset[input.dataset.param];
      if (input.value !== "" || offset === undefined) return;
      input.value = offset === "spot" ? spot.toFixed(2) : String(Math.round(spot) + offset * step);
    });
  },

  async calculate() {
    const entry = this.entry(this.el.strategy.value);
    const pairs = [];
    this.el.params.querySelectorAll("[data-param]").forEach(field => {
      if (field.value !== "") pairs.push(`${field.dataset.param}=${field.value}`);
    });
    const query = new URLSearchParams({
      strategy: entry.id,
      params: pairs.join(","),
      auto_price: this.el.auto.checked,
    });
    for (const [key, field] of [["spot", this.el.spot], ["iv", this.el.iv], ["days", this.el.days]]) {
      if (field.value !== "") query.set(key, field.value);
    }
    const response = await fetch(`/api/calculator?${query}`);
    if (!response.ok) {
      const detail = (await response.json()).detail || "error";
      this.el.error.textContent = detail;
      this.el.error.hidden = false;
      return;
    }
    this.el.error.hidden = true;
    this.result = await response.json();
    this.renderMetrics();
    this.panel.draw();
  },

  renderMetrics() {
    const r = this.result;
    this.el.title.textContent = `${r.name} · ${r.sentiment}`;
    const chip = (label, value, cls = "") =>
      `<div class="metric ${cls}"><span>${label}</span><b>${value}</b></div>`;
    const money = (v) => v === null ? "ilimitado" : `$${v.toLocaleString()}`;
    let html =
      chip("Prima neta", `${Math.abs(r.net_premium).toFixed(2)} ${r.net_premium >= 0 ? "débito" : "crédito"}`) +
      chip("Max profit", money(r.max_profit), "pos") +
      chip("Max riesgo", money(r.max_loss), "neg") +
      chip("Breakevens", r.breakevens.map(b => b.toFixed(2)).join(" / ") || "—");
    if (r.pop !== undefined) html += chip("Prob. beneficio", (r.pop * 100).toFixed(1) + "%");
    if (r.greeks) html += chip("Griegas",
      `Δ${r.greeks.delta.toFixed(2)} Γ${r.greeks.gamma.toFixed(3)} Θ${r.greeks.theta.toFixed(3)} V${r.greeks.vega.toFixed(3)}`);
    html += `<div class="metric metric-legs"><span>Patas</span><b>${r.legs.map(l =>
      l.kind === "stock" ? `${l.quantity > 0 ? "+" : ""}${l.quantity} acc @${l.cost_basis}`
        : `${l.quantity > 0 ? "+" : ""}${l.quantity} ${l.kind} ${l.strike} @${l.premium.toFixed(2)}`
    ).join(" · ")}</b></div>`;
    if (r.notes) html += `<div class="metric metric-note"><span>Libro</span><b>${r.notes}</b></div>`;
    this.el.metrics.innerHTML = html;
  },

  PAD: { l: 54, r: 14, t: 14, b: 26 },

  draw(ctx, w, h) {
    const r = this.result;
    if (!r) {
      ctx.fillStyle = COLORS.dim;
      ctx.font = MONO;
      ctx.textAlign = "center";
      ctx.fillText("configura la estrategia y pulsa Calcular", w / 2, h / 2);
      return;
    }
    const P = this.PAD;
    const { spots, payoff, t0 } = r.curve;
    const all = t0 ? payoff.concat(t0) : payoff;
    const vMax = Math.max(...all, 0), vMin = Math.min(...all, 0);
    const pad = (vMax - vMin) * 0.08 + 1;
    const x = (i) => P.l + (i / (spots.length - 1)) * (w - P.l - P.r);
    const y = (v) => P.t + (1 - (v - vMin + pad) / (vMax - vMin + 2 * pad)) * (h - P.t - P.b);

    const zeroY = y(0);
    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(P.l, zeroY); ctx.lineTo(w - P.r, zeroY); ctx.stroke();

    // sombreado beneficio/pérdida a expiración
    ctx.beginPath();
    payoff.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
    ctx.lineTo(x(spots.length - 1), zeroY);
    ctx.lineTo(x(0), zeroY);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, P.t, 0, h - P.b);
    grad.addColorStop(0, "rgba(47,164,99,0.22)");
    grad.addColorStop(Math.max(0.01, Math.min(0.99, (zeroY - P.t) / (h - P.t - P.b))), "rgba(47,164,99,0.05)");
    grad.addColorStop(1, "rgba(224,67,63,0.20)");
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    payoff.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
    ctx.strokeStyle = COLORS.price;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    if (t0) {
      ctx.beginPath();
      t0.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
      ctx.strokeStyle = COLORS.call;
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let gLine = 0; gLine <= 4; gLine++) {
      const value = vMin + ((vMax - vMin) / 4) * gLine;
      ctx.fillText("$" + Math.round(value).toLocaleString(), 4, y(value) + 3);
    }
    ctx.textAlign = "center";
    for (let i = 0; i < spots.length; i += Math.floor(spots.length / 6)) {
      ctx.fillText(spots[i].toFixed(0), x(i), h - 8);
    }
    r.breakevens.forEach(be => {
      const idx = spots.findIndex(s => s >= be);
      if (idx < 0) return;
      ctx.strokeStyle = COLORS.accent;
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x(idx), P.t); ctx.lineTo(x(idx), h - P.b); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = COLORS.accent;
      ctx.fillText(`BE ${be.toFixed(1)}`, x(idx), P.t - 3);
    });
  },
};
