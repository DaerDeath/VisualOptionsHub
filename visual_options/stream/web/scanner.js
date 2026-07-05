/* Scanner multi-símbolo (Compass-like): señales direccionales y de
 * volatilidad por símbolo, ordenables; clic → vista de flujo. */
"use strict";

const ScannerView = {
  timer: null,
  rows: [],
  sortKey: "direction_score",
  sortDesc: true,

  COLUMNS: [
    ["symbol", "Símbolo"],
    ["spot", "Precio"],
    ["direction_score", "Dirección"],
    ["put_sell_pct", "Put sell %"],
    ["call_sell_pct", "Call sell %"],
    ["total_gex", "Σ GEX (M$)"],
    ["regime", "Régimen"],
    ["gamma_flip", "γ-flip"],
    ["flip_distance_pct", "Dist. flip %"],
    ["atm_iv", "IV ATM"],
  ],

  mount(root) {
    const saved = localStorage.getItem("vo-scan") || "QQQ,SPY,SPX,IWM,NVDA,TSLA,AAPL,MSFT";
    root.innerHTML = `
      <div class="scan-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Scanner</h2>
            <span class="hint">dirección = put sell − call sell (＋alcista / −bajista) · clic en fila → flujo</span>
            <input id="scanSymbols" class="scan-input" value="${saved}" spellcheck="false"
                   title="símbolos separados por comas (Enter para escanear)">
          </div>
          <div class="scan-table-wrap"><table class="scan-table">
            <thead><tr>${this.COLUMNS.map(([key, label]) =>
              `<th data-key="${key}">${label}</th>`).join("")}</tr></thead>
            <tbody id="scanBody"><tr><td colspan="10" class="scan-empty">escaneando…</td></tr></tbody>
          </table></div>
        </section>
      </div>`;
    this.body = root.querySelector("#scanBody");
    this.input = root.querySelector("#scanSymbols");
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { localStorage.setItem("vo-scan", this.input.value); this.refresh(); }
    });
    root.querySelectorAll("th").forEach(th => th.addEventListener("click", () => {
      const key = th.dataset.key;
      this.sortDesc = this.sortKey === key ? !this.sortDesc : true;
      this.sortKey = key;
      this.render();
    }));
    this.refresh();
    this.timer = setInterval(() => this.refresh(), 5000);
  },

  unmount() {
    clearInterval(this.timer);
    this.timer = null;
  },

  onData() {},  // el scanner consulta su propio endpoint

  async refresh() {
    try {
      const symbols = encodeURIComponent(this.input.value);
      const source = encodeURIComponent(app.source);
      this.rows = await fetch(`/api/scan?symbols=${symbols}&source=${source}`).then(r => r.json());
      this.render();
    } catch (_) { /* siguiente ciclo */ }
  },

  render() {
    if (!this.body) return;
    const key = this.sortKey;
    const rows = [...this.rows].sort((a, b) => {
      const va = a[key] ?? -Infinity, vb = b[key] ?? -Infinity;
      const cmp = typeof va === "string" ? va.localeCompare(vb) : va - vb;
      return this.sortDesc ? -cmp : cmp;
    });
    const cls = (v) => v > 0 ? "pos" : v < 0 ? "neg" : "";
    this.body.innerHTML = rows.map(r => `
      <tr data-sym="${r.symbol}">
        <td class="scan-sym">${r.symbol}</td>
        <td>${r.spot?.toFixed(2) ?? "—"}</td>
        <td class="${cls(r.direction_score)}">${r.direction_score > 0 ? "+" : ""}${r.direction_score?.toFixed(1)}</td>
        <td>${r.put_sell_pct?.toFixed(1)}</td>
        <td>${r.call_sell_pct?.toFixed(1)}</td>
        <td class="${cls(r.total_gex)}">${r.total_gex?.toFixed(0)}</td>
        <td class="${r.regime === "amortiguador" ? "pos" : "neg"}">${r.regime}</td>
        <td>${r.gamma_flip ? r.gamma_flip.toFixed(1) : "—"}</td>
        <td class="${cls(r.flip_distance_pct)}">${r.flip_distance_pct !== null ? r.flip_distance_pct.toFixed(2) : "—"}</td>
        <td>${r.atm_iv !== null ? (r.atm_iv * 100).toFixed(1) + "%" : "—"}</td>
      </tr>`).join("") || `<tr><td colspan="10" class="scan-empty">sin resultados</td></tr>`;
    this.body.querySelectorAll("tr[data-sym]").forEach(tr =>
      tr.addEventListener("click", () => { location.hash = `#/flow/${tr.dataset.sym}`; }));
  },
};
