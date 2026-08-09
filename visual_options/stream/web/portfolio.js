/* Portafolio real — SOLO LECTURA. Lee posiciones, órdenes y P&L (abierto
 * y ya realizado) de tu cuenta de verdad (IBKR o Tradier); nunca coloca
 * ni modifica ninguna orden. Órdenes e histórico de P&L solo existen con
 * Tradier (Brokerage API); IBKR aquí solo cubre posiciones. */
"use strict";

const PortfolioView = {
  timer: null,
  source: "ibkr",
  tab: "positions",

  TABS: [["positions", "Posiciones"], ["orders", "Órdenes"], ["gainloss", "Histórico P&L"]],

  mount(root) {
    root.innerHTML = `
      <div class="scan-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Portafolio</h2>
            <span class="hint">solo lectura — nunca coloca ni modifica órdenes</span>
            <div class="stats-controls">
              <button class="srcbtn active" data-src="ibkr">IBKR</button>
              <button class="srcbtn" data-src="tradier">Tradier</button>
              <button id="pfRefresh" class="btn">↻ actualizar</button>
            </div>
          </div>
          <div class="pf-tabs">
            ${this.TABS.map(([id, label]) =>
              `<button class="pf-tab ${id === this.tab ? "active" : ""}" data-tab="${id}">${label}</button>`).join("")}
          </div>
          <div class="vwap-tiles" id="pfTiles" style="padding:0.7rem"></div>
          <div class="scan-table-wrap"><table class="scan-table" id="pfTable">
            <thead id="pfHead"></thead>
            <tbody id="pfBody"><tr><td class="scan-empty">cargando…</td></tr></tbody>
          </table></div>
        </section>
      </div>`;
    this.tilesEl = root.querySelector("#pfTiles");
    this.headEl = root.querySelector("#pfHead");
    this.bodyEl = root.querySelector("#pfBody");
    // ojo: scopeado a `root` — el header global también tiene botones
    // con data-src (fuente de mercado), sin scopear pisarían este estado.
    root.querySelectorAll("[data-src]").forEach(btn => btn.addEventListener("click", () => {
      this.source = btn.dataset.src;
      root.querySelectorAll("[data-src]").forEach(b => b.classList.toggle("active", b === btn));
      this.load();
    }));
    root.querySelectorAll(".pf-tab").forEach(btn => btn.addEventListener("click", () => {
      this.tab = btn.dataset.tab;
      root.querySelectorAll(".pf-tab").forEach(b => b.classList.toggle("active", b === btn));
      this.load();
    }));
    root.querySelector("#pfRefresh").addEventListener("click", () => this.load());
    this.load();
    this.timer = setInterval(() => this.load(), 20000);
  },

  unmount() {
    clearInterval(this.timer);
    this.timer = null;
  },

  onData() {},  // vista de cuenta, no sigue el stream de mercado

  fmt(v) { return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 }); },
  colspan() { return this.tab === "positions" ? 14 : this.tab === "orders" ? 8 : 6; },

  async load() {
    this.bodyEl.innerHTML = `<tr><td colspan="${this.colspan()}" class="scan-empty">cargando…</td></tr>`;
    if (this.tab !== "positions" && this.source !== "tradier") {
      this.tilesEl.innerHTML = "";
      this.headEl.innerHTML = "";
      this.bodyEl.innerHTML = `<tr><td colspan="${this.colspan()}" class="scan-empty">
        ${this.TABS.find(([id]) => id === this.tab)[1]} solo está disponible con Tradier (Brokerage API) — cambia de fuente arriba</td></tr>`;
      return;
    }
    const endpoint = this.tab === "positions" ? "portfolio" : this.tab;
    try {
      const response = await fetch(`/api/${endpoint}?source=${this.source}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      const data = await response.json();
      if (this.tab === "positions") this.renderPositions(data);
      else if (this.tab === "orders") this.renderOrders(data);
      else this.renderGainloss(data);
    } catch (err) {
      this.bodyEl.innerHTML = `<tr><td colspan="${this.colspan()}" class="scan-empty">${err.message}</td></tr>`;
      this.tilesEl.innerHTML = "";
    }
  },

  tile(label, value, cls = "") { return `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`; },

  renderPositions(d) {
    const t = d.totals;
    this.tilesEl.innerHTML =
      this.tile("Cuenta", d.account || "—") +
      this.tile("Net Liquidation", d.net_liquidation != null ? "$" + this.fmt(d.net_liquidation) : "—") +
      this.tile("Buying Power", d.buying_power != null ? "$" + this.fmt(d.buying_power) : "—") +
      this.tile("Valor posiciones", "$" + this.fmt(t.market_value)) +
      this.tile("P&L no realizado", (t.unrealized_pnl >= 0 ? "+$" : "-$") + this.fmt(Math.abs(t.unrealized_pnl)),
           t.unrealized_pnl >= 0 ? "pos" : "neg") +
      this.tile("Σ Delta", this.fmt(t.delta)) +
      this.tile("Σ Gamma", this.fmt(t.gamma)) +
      this.tile("Σ Theta/día", this.fmt(t.theta)) +
      this.tile("Σ Vega/1%", this.fmt(t.vega));

    this.headEl.innerHTML = `<tr>
      <th>Símbolo</th><th>Tipo</th><th>Strike</th><th>Venc.</th><th>Cant.</th>
      <th>Coste medio</th><th>Precio</th><th>Valor</th><th>P&amp;L</th><th>P&amp;L %</th>
      <th>Δ</th><th>Γ</th><th>Θ</th><th>V</th>
    </tr>`;
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

  renderOrders(d) {
    this.tilesEl.innerHTML =
      this.tile("Cuenta", d.account || "—") +
      this.tile("Órdenes", d.orders.length);
    this.headEl.innerHTML = `<tr>
      <th>Símbolo</th><th>Lado</th><th>Cant.</th><th>Tipo</th><th>Estado</th>
      <th>Precio</th><th>Ejecutado a</th><th>Creada</th>
    </tr>`;
    if (!d.orders.length) {
      this.bodyEl.innerHTML = `<tr><td colspan="8" class="scan-empty">sin órdenes en esta cuenta</td></tr>`;
      return;
    }
    const statusCls = (s) => s === "filled" ? "pos" : s === "canceled" || s === "rejected" ? "neg" : "";
    this.bodyEl.innerHTML = d.orders.map(o => `
      <tr>
        <td class="scan-sym">${o.symbol}${o.option_symbol ? ` <span class="hint">${o.option_symbol}</span>` : ""}</td>
        <td class="${(o.side || "").includes("buy") ? "pos" : "neg"}">${o.side ?? "—"}</td>
        <td>${this.fmt(o.qty)}</td>
        <td>${o.type ?? "—"}</td>
        <td class="${statusCls(o.status)}">${o.status ?? "—"}</td>
        <td>${this.fmt(o.price)}</td>
        <td>${this.fmt(o.avg_fill_price)}</td>
        <td>${o.created_at ? o.created_at.replace("T", " ").slice(0, 16) : "—"}</td>
      </tr>`).join("");
  },

  renderGainloss(d) {
    const s = d.summary;
    this.tilesEl.innerHTML =
      this.tile("Cuenta", d.account || "—") +
      this.tile("Operaciones cerradas", s.n_trades) +
      this.tile("Win rate", s.win_rate != null ? s.win_rate.toFixed(1) + "%" : "—") +
      this.tile("P&L total realizado", (s.total_pnl >= 0 ? "+$" : "-$") + this.fmt(Math.abs(s.total_pnl)),
           s.total_pnl >= 0 ? "pos" : "neg") +
      this.tile("Ganancia media", s.avg_win != null ? "+$" + this.fmt(s.avg_win) : "—", "pos") +
      this.tile("Pérdida media", s.avg_loss != null ? "-$" + this.fmt(Math.abs(s.avg_loss)) : "—", "neg");

    this.headEl.innerHTML = `<tr>
      <th>Símbolo</th><th>Abierta</th><th>Cerrada</th><th>Cant.</th>
      <th>Coste base</th><th>P&amp;L</th>
    </tr>`;
    if (!d.closed.length) {
      this.bodyEl.innerHTML = `<tr><td colspan="6" class="scan-empty">sin operaciones cerradas todavía</td></tr>`;
      return;
    }
    this.bodyEl.innerHTML = d.closed.map(c => `
      <tr>
        <td class="scan-sym">${c.symbol}</td>
        <td>${c.open_date ?? "—"}</td>
        <td>${c.close_date ?? "—"}</td>
        <td>${this.fmt(c.qty)}</td>
        <td>$${this.fmt(c.cost_basis)}</td>
        <td class="${c.gain_loss >= 0 ? "pos" : "neg"}">${c.gain_loss >= 0 ? "+" : ""}$${this.fmt(c.gain_loss)}
          (${c.gain_loss_pct >= 0 ? "+" : ""}${c.gain_loss_pct.toFixed(1)}%)</td>
      </tr>`).join("");
  },
};
