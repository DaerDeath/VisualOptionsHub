/* Cadena + griegas: todas las opciones del vencimiento con precio teórico
 * BSM y sus griegas completas (Δ Γ Θ V ρ) por call y put, en vivo.
 * Convenciones: Θ por día natural, Vega y ρ por 1% — como el toolkit. */
"use strict";

const ChainGreeks = (() => {
  const erfLocal = (x) => {
    const sign = x >= 0 ? 1 : -1;
    x = Math.abs(x);
    const t = 1 / (1 + 0.3275911 * x);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
      - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return sign * y;
  };
  const N = (x) => 0.5 * (1 + erfLocal(x / Math.SQRT2));
  const phi = (x) => Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);

  return function compute(spot, strike, days, iv, rate = 0.04) {
    const T = Math.max(days, 0.05) / 365;
    const sigma = iv > 0 ? iv : 0.2;
    const sqT = Math.sqrt(T);
    const d1 = (Math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * T) / (sigma * sqT);
    const d2 = d1 - sigma * sqT;
    const discount = Math.exp(-rate * T);
    const gamma = phi(d1) / (spot * sigma * sqT);
    const vega = spot * phi(d1) * sqT / 100;
    const common = -spot * phi(d1) * sigma / (2 * sqT);
    return {
      call: {
        price: spot * N(d1) - strike * discount * N(d2),
        delta: N(d1),
        theta: (common - rate * strike * discount * N(d2)) / 365,
        rho: strike * T * discount * N(d2) / 100,
      },
      put: {
        price: strike * discount * N(-d2) - spot * N(-d1),
        delta: N(d1) - 1,
        theta: (common + rate * strike * discount * N(-d2)) / 365,
        rho: -strike * T * discount * N(-d2) / 100,
      },
      gamma, vega,
    };
  };
})();

const ChainView = {
  data: null,

  mount(root) {
    root.innerHTML = `
      <div class="scan-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Cadena + griegas</h2>
            <span class="hint">BSM con la IV de cada strike · Θ por día · Vega y ρ por 1% · fila ámbar = ATM · sombreado = ITM</span>
            <div class="dealer-totals" id="chainMeta"></div>
          </div>
          <div class="scan-table-wrap"><table class="scan-table chain-table">
            <thead>
              <tr>
                <th colspan="9" class="chain-side call">CALLS</th>
                <th class="chain-strike">STRIKE</th>
                <th colspan="9" class="chain-side put">PUTS</th>
              </tr>
              <tr>
                <th>Vol</th><th>OI</th><th>IV</th><th>Prec</th><th>Δ</th><th>Γ</th><th>Θ</th><th>V</th><th>ρ</th>
                <th class="chain-strike"></th>
                <th>Δ</th><th>Γ</th><th>Θ</th><th>V</th><th>ρ</th><th>Prec</th><th>IV</th><th>OI</th><th>Vol</th>
              </tr>
            </thead>
            <tbody id="chainBody"><tr><td colspan="19" class="scan-empty">esperando datos…</td></tr></tbody>
          </table></div>
        </section>
      </div>`;
    this.body = root.querySelector("#chainBody");
    this.meta = root.querySelector("#chainMeta");
  },

  unmount() {
    this.body = null;
    this.data = null;
  },

  onData(payload) {
    this.data = payload.flow;
    this.render();
  },

  render() {
    const d = this.data;
    if (!this.body || !d || !d.strikes.length || !d.spot) return;
    const rows = [...d.strikes].sort((a, b) => b.strike - a.strike);
    const stepHalf = rows.length > 1 ? Math.abs(rows[0].strike - rows[1].strike) / 2 : 0.5;

    this.meta.innerHTML =
      `<span class="dtotal">spot ${d.spot.toFixed(2)}</span>` +
      `<span class="dtotal">${d.expiry_days.toFixed(1)}d a vencimiento</span>` +
      `<span class="dtotal">r 4%</span>`;

    const f = (v, dec) => v.toFixed(dec);
    this.body.innerHTML = rows.map(r => {
      const g = ChainGreeks(d.spot, r.strike, d.expiry_days, r.iv);
      const atm = Math.abs(r.strike - d.spot) <= stepHalf;
      const callItm = r.strike < d.spot, putItm = r.strike > d.spot;
      return `<tr class="${atm ? "tape-big" : ""}">
        <td class="${callItm ? "chain-itm" : ""}">${fmtK(r.call_volume)}</td>
        <td class="${callItm ? "chain-itm" : ""}">${fmtK(r.call_oi)}</td>
        <td class="${callItm ? "chain-itm" : ""}">${(r.iv * 100 || 20).toFixed(1)}%</td>
        <td class="${callItm ? "chain-itm" : ""}">${f(g.call.price, 2)}</td>
        <td class="${callItm ? "chain-itm" : ""} pos">${f(g.call.delta, 3)}</td>
        <td class="${callItm ? "chain-itm" : ""}">${f(g.gamma, 4)}</td>
        <td class="${callItm ? "chain-itm" : ""} neg">${f(g.call.theta, 3)}</td>
        <td class="${callItm ? "chain-itm" : ""}">${f(g.vega, 3)}</td>
        <td class="${callItm ? "chain-itm" : ""}">${f(g.call.rho, 3)}</td>
        <td class="chain-strike scan-sym">${Number.isInteger(r.strike) ? r.strike : r.strike.toFixed(1)}</td>
        <td class="${putItm ? "chain-itm" : ""} neg">${f(g.put.delta, 3)}</td>
        <td class="${putItm ? "chain-itm" : ""}">${f(g.gamma, 4)}</td>
        <td class="${putItm ? "chain-itm" : ""} neg">${f(g.put.theta, 3)}</td>
        <td class="${putItm ? "chain-itm" : ""}">${f(g.vega, 3)}</td>
        <td class="${putItm ? "chain-itm" : ""}">${f(g.put.rho, 3)}</td>
        <td class="${putItm ? "chain-itm" : ""}">${f(g.put.price, 2)}</td>
        <td class="${putItm ? "chain-itm" : ""}">${(r.iv * 100 || 20).toFixed(1)}%</td>
        <td class="${putItm ? "chain-itm" : ""}">${fmtK(r.put_oi)}</td>
        <td class="${putItm ? "chain-itm" : ""}">${fmtK(r.put_volume)}</td>
      </tr>`;
    }).join("");
  },
};
