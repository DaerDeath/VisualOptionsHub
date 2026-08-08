/* Portafolio real — SOLO LECTURA. Lee posiciones, P&L y griegas de tu
 * cuenta de verdad (IBKR o Tradier); nunca coloca ni modifica órdenes. */
"use strict";

const PortfolioView = {
  timer: null,
  source: "ibkr",

  mount(root) {
    root.innerHTML = `
      <div class="scan-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Portafolio</h2>
            <span class="hint">solo lectura — nunca coloca ni modifica órdenes · P&amp;L calculado por el propio broker</span>
            <div class="stats-controls">
              <button class="srcbtn active" data-src="ibkr">IBKR</button>
              <button class="srcbtn" data-src="tradier">Tradier</button>
              <button id="pfRefresh" class="btn">↻ actualizar</button>
            </div>
          </div>
          <div class="vwap-tiles" id="pfTiles" style="padding:0.7rem"></div>
          <div class="scan-table-wrap"><table class="scan-table">
            <thead><tr>
              <th>Símbolo</th><th>Tipo</th><th>Strike</th><th>Venc.</th><th>Cant.</th>
              <th>Coste medio</th><th>Precio</th><th>Valor</th><th>P&amp;L</th><th>P&amp;L %</th>
              <th>Δ</th><th>Γ</th><th>Θ</th><th>V</th>
            </tr></thead>
            <tbody id="pfBody"><tr><td colspan="14" class="scan-empty">cargando…</td></tr></tbody>
          </table></div>
        </section>
      </div>`;
    this.tilesEl = document.getElementById("pfTiles");
    this.bodyEl = document.getElementById("pfBody");
    document.querySelectorAll("[data-src]").forEach(btn => btn.addEventListener("click", () => {
      this.source = btn.dataset.src;
      document.querySelectorAll("[data-src]").forEach(b => b.classList.toggle("active", b === btn));
      this.load();
    }));
    document.getElementById("pfRefresh").addEventListener("click", () => this.load());
    this.load();
    this.timer = setInterval(() => this.load(), 20000);
  },

  unmount() {
    clearInterval(this.timer);
    this.timer = null;
  },

  onData() {},  // vista de cuenta, no sigue el stream de mercado

  fmt(v) { return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 }); },

  async load() {
    this.bodyEl.innerHTML = `<tr><td colspan="14" class="scan-empty">cargando…</td></tr>`;
    try {
      const response = await fetch(`/api/portfolio?source=${this.source}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.render(await response.json());
    } catch (err) {
      this.bodyEl.innerHTML = `<tr><td colspan="14" class="scan-empty">${err.message}</td></tr>`;
      this.tilesEl.innerHTML = "";
    }
  },

  render(d) {
    const t = d.totals;
    const tile = (label, value, cls = "") => `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`;
    this.tilesEl.innerHTML =
      tile("Cuenta", d.account || "—") +
      tile("Net Liquidation", d.net_liquidation != null ? "$" + this.fmt(d.net_liquidation) : "—") +
      tile("Buying Power", d.buying_power != null ? "$" + this.fmt(d.buying_power) : "—") +
      tile("Valor posiciones", "$" + this.fmt(t.market_value)) +
      tile("P&L no realizado", (t.unrealized_pnl >= 0 ? "+$" : "-$") + this.fmt(Math.abs(t.unrealized_pnl)),
           t.unrealized_pnl >= 0 ? "pos" : "neg") +
      tile("Σ Delta", this.fmt(t.delta)) +
      tile("Σ Gamma", this.fmt(t.gamma)) +
      tile("Σ Theta/día", this.fmt(t.theta)) +
      tile("Σ Vega/1%", this.fmt(t.vega));

    if (!d.positions.length) {
      this.bodyEl.innerHTML = `<tr><td colspan="14" class="scan-empty">sin posiciones abiertas en esta cuenta</td></tr>`;
      return;
    }
    this.bodyEl.innerHTML = d.positions.map(p => `
      <tr>
        <td class="scan-sym">${p.symbol}</td>
        <td class="${p.kind === "call" ? "pos" : p.kind === "put" ? "neg" : ""}">${p.kind}</td>
        <td>${p.strike ?? "—"}</td>
        <td>${p.expiry ?? "—"}</td>
        <td class="${p.qty >= 0 ? "pos" : "neg"}">${p.qty}</td>
        <td>${this.fmt(p.avg_cost)}</td>
        <td>${this.fmt(p.price)}</td>
        <td>$${this.fmt(p.market_value)}</td>
        <td class="${p.unrealized_pnl >= 0 ? "pos" : "neg"}">${p.unrealized_pnl >= 0 ? "+" : ""}$${this.fmt(p.unrealized_pnl)}</td>
        <td class="${(p.unrealized_pnl_pct ?? 0) >= 0 ? "pos" : "neg"}">${p.unrealized_pnl_pct != null ? p.unrealized_pnl_pct.toFixed(1) + "%" : "—"}</td>
        <td>${this.fmt(p.delta)}</td><td>${this.fmt(p.gamma)}</td>
        <td>${this.fmt(p.theta)}</td><td>${this.fmt(p.vega)}</td>
      </tr>`).join("");
  },
};
