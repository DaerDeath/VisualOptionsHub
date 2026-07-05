/* Tape de opciones (TAPE-like): operaciones destacadas en vivo con
 * filtros por tipo y lado; lo más nuevo arriba. */
"use strict";

const TapeView = {
  data: null,
  filter: "all",

  mount(root) {
    root.innerHTML = `
      <div class="scan-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Tape · operaciones destacadas</h2>
            <span class="hint">bloques grandes de volumen; con datos retrasados el reloj va ~15 min detrás</span>
            <div class="tape-filters">
              ${["all|todo", "call|calls", "put|puts", "buy|compras", "sell|ventas"].map(pair => {
                const [key, label] = pair.split("|");
                return `<button class="srcbtn ${key === "all" ? "active" : ""}" data-f="${key}">${label}</button>`;
              }).join("")}
            </div>
          </div>
          <div class="scan-table-wrap"><table class="scan-table">
            <thead><tr><th>Hora</th><th>Strike</th><th>Tipo</th><th>Lado</th>
              <th>Contratos</th><th>Prima</th></tr></thead>
            <tbody id="tapeBody"><tr><td colspan="6" class="scan-empty">esperando operaciones…</td></tr></tbody>
          </table></div>
        </section>
      </div>`;
    this.body = root.querySelector("#tapeBody");
    root.querySelectorAll("[data-f]").forEach(btn => btn.addEventListener("click", () => {
      this.filter = btn.dataset.f;
      root.querySelectorAll("[data-f]").forEach(b => b.classList.toggle("active", b === btn));
      this.render();
    }));
  },

  unmount() {
    this.data = null;
    this.body = null;
  },

  onData(payload) {
    this.data = payload.flow;
    this.render();
  },

  render() {
    if (!this.body || !this.data) return;
    let events = [...this.data.tape].reverse();  // lo más nuevo arriba
    if (this.filter === "call" || this.filter === "put") {
      events = events.filter(ev => ev.kind === this.filter);
    } else if (this.filter === "buy" || this.filter === "sell") {
      events = events.filter(ev => ev.side === this.filter);
    }
    if (!events.length) {
      this.body.innerHTML = `<tr><td colspan="6" class="scan-empty">sin operaciones para este filtro</td></tr>`;
      return;
    }
    const maxPremium = Math.max(...events.map(ev => ev.premium));
    this.body.innerHTML = events.slice(0, 60).map(ev => {
      const sideCls = ev.side === "buy" ? "pos" : "neg";
      const sideTxt = ev.side === "buy" ? "COMPRA" : "VENTA";
      const big = ev.premium >= maxPremium * 0.5 ? " tape-big" : "";
      return `<tr class="${big}">
        <td>${ev.t}</td>
        <td class="scan-sym">${ev.strike}</td>
        <td class="${ev.kind === "call" ? "pos" : "neg"}">${ev.kind.toUpperCase()}</td>
        <td class="${sideCls}">${sideTxt}</td>
        <td>${fmtK(ev.size)}</td>
        <td>$${Math.round(ev.premium).toLocaleString()}</td>
      </tr>`;
    }).join("");
  },
};
