/* Screener multi-símbolo de verticales de crédito, Cap. 2 del libro:
 * strike corto vendido a ≥1σ del spot y rendimiento (crédito/riesgo) de
 * al menos 12-15%. Combina la Calculadora (mismo motor de max profit/
 * max risk/PoP) con cadenas reales de opciones — solo lectura, no
 * depende de tu cuenta ni coloca nada. */
"use strict";

const ScreenerView = {
  mount(root) {
    root.innerHTML = `
      <div class="scan-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Screener de verticales</h2>
            <span class="hint">strike corto a ≥1σ · rendimiento crédito/riesgo mínimo del libro (12-15%)</span>
          </div>
          <div class="scr-controls">
            <input id="scrSymbols" class="scan-input" spellcheck="false" autocomplete="off"
                   placeholder="símbolos, coma-separados (vacío = lista por defecto)">
            <button id="scrWatchlist" class="btn" title="usa los símbolos de tus watchlists de Tradier">★ mi watchlist</button>
            <label>DTE min <input id="scrMinDays" type="number" value="25" min="1" max="365"></label>
            <label>DTE max <input id="scrMaxDays" type="number" value="45" min="1" max="365"></label>
            <label>Rendimiento min % <input id="scrMinReturn" type="number" value="12" min="1" max="200"></label>
            <label>σ mínima <input id="scrMinSigma" type="number" value="1" min="0" max="3" step="0.1"></label>
            <select id="scrSides">
              <option value="put,call" selected>Bull put + bear call</option>
              <option value="put">Solo bull put</option>
              <option value="call">Solo bear call</option>
            </select>
            <button id="scrRun" class="btn">buscar</button>
          </div>
          <div class="scan-table-wrap"><table class="scan-table">
            <thead><tr>
              <th>Símbolo</th><th>Estrategia</th><th>Spot</th><th>Corto</th><th>Largo</th>
              <th>Venc.</th><th>DTE</th><th>Crédito</th><th>Riesgo máx</th>
              <th>Rendimiento</th><th>Distancia σ</th><th>PoP</th>
            </tr></thead>
            <tbody id="scrBody"><tr><td colspan="12" class="scan-empty">pulsa "buscar"</td></tr></tbody>
          </table></div>
          <div id="scrSkipped" class="scr-skipped"></div>
        </section>
      </div>`;
    this.bodyEl = document.getElementById("scrBody");
    this.skippedEl = document.getElementById("scrSkipped");
    document.getElementById("scrRun").addEventListener("click", () => this.load());
    document.getElementById("scrWatchlist").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        document.getElementById("scrSymbols").value = await fetchTradierWatchlistSymbols();
        this.load();
      } catch (err) {
        this.bodyEl.innerHTML = `<tr><td colspan="12" class="scan-empty">${err.message}</td></tr>`;
      } finally {
        btn.disabled = false;
      }
    });
    this.load();
  },

  unmount() {},
  onData() {},

  fmt(v, digits = 2) { return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: digits }); },
  pct(v) { return v == null ? "—" : (v * 100).toFixed(1) + "%"; },

  async load() {
    this.bodyEl.innerHTML = `<tr><td colspan="12" class="scan-empty">escaneando cadenas de opciones (puede tardar)…</td></tr>`;
    this.skippedEl.innerHTML = "";
    const symbols = document.getElementById("scrSymbols").value.trim();
    const params = new URLSearchParams({
      symbols,
      min_days: document.getElementById("scrMinDays").value || "25",
      max_days: document.getElementById("scrMaxDays").value || "45",
      min_return: String((parseFloat(document.getElementById("scrMinReturn").value || "12")) / 100),
      min_sigma: document.getElementById("scrMinSigma").value || "1",
      sides: document.getElementById("scrSides").value,
    });
    try {
      const response = await fetch(`/api/screener?${params}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.render(await response.json());
    } catch (err) {
      this.bodyEl.innerHTML = `<tr><td colspan="12" class="scan-empty">${err.message}</td></tr>`;
    }
  },

  render(d) {
    if (!d.candidates.length) {
      this.bodyEl.innerHTML = `<tr><td colspan="12" class="scan-empty">ningún spread cumple ≥${d.min_sigma}σ y ≥${(d.min_return * 100).toFixed(0)}% de rendimiento en los ${d.scanned} símbolos escaneados</td></tr>`;
    } else {
      this.bodyEl.innerHTML = d.candidates.map(c => `
        <tr>
          <td class="scan-sym">${c.symbol}</td>
          <td>${c.strategy}</td>
          <td>${this.fmt(c.spot)}</td>
          <td>${this.fmt(c.short_strike)}</td>
          <td>${this.fmt(c.long_strike)}</td>
          <td>${c.expiry}</td>
          <td>${c.days}</td>
          <td class="pos">${this.fmt(c.credit, 3)}</td>
          <td>${this.fmt(c.max_risk, 3)}</td>
          <td class="pos">${this.pct(c.return_pct)}</td>
          <td>${this.fmt(c.sigma_distance)}σ</td>
          <td>${this.pct(c.pop)}</td>
        </tr>`).join("");
    }
    if (d.skipped.length) {
      this.skippedEl.innerHTML = `<span class="hint">omitidos: ${
        d.skipped.map(s => `${s.symbol} (${s.reason})`).join(" · ")
      }</span>`;
    }
  },
};
