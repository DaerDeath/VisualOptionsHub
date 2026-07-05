/* Vista de inicio: elegir símbolo y tipo de visualización. */
"use strict";

const QUICK_SYMBOLS = ["QQQ", "SPY", "SPX", "IWM", "NVDA", "TSLA", "AAPL", "MSFT", "META", "AMZN"];

const VIEW_CARDS = [
  {
    view: "flow", name: "Flujo de opciones", ready: true,
    desc: "Premium / volume profile por strike, put-call sell % contra el precio, GEX y magnet strikes.",
    art: "flow",
  },
  {
    view: "footprint", name: "Footprint", ready: true,
    desc: "Velas con volumen comprador y vendedor por nivel de precio, delta por barra, POC e imbalances.",
    art: "footprint",
  },
  {
    view: null, name: "Próximamente", ready: false,
    desc: "Dime qué más quieres ver aquí: heatmap de open interest, ladder de DOM, perfil TPO…",
    art: "plus",
  },
];

const HomeView = {
  mount(root) {
    const saved = localStorage.getItem("vo-symbol") || "QQQ";
    root.innerHTML = `
      <div class="home">
        <section class="home-hero">
          <h1>¿Qué quieres ver?</h1>
          <p class="home-sub">elige un subyacente y una visualización · fuente: <span id="homeMode">…</span></p>
          <div class="home-symbol">
            <input id="homeSymbol" value="${saved}" spellcheck="false" autocomplete="off"
                   placeholder="símbolo" maxlength="6">
            <div class="quick-chips">
              ${QUICK_SYMBOLS.map(s => `<button class="qchip" data-sym="${s}">${s}</button>`).join("")}
            </div>
          </div>
        </section>
        <section class="cards">
          ${VIEW_CARDS.map(c => `
            <button class="card ${c.ready ? "" : "card-disabled"}" data-view="${c.view ?? ""}">
              <span class="card-art art-${c.art}" aria-hidden="true"></span>
              <span class="card-name">${c.name}</span>
              <span class="card-desc">${c.desc}</span>
            </button>`).join("")}
        </section>
      </div>`;

    fetch("/api/config").then(r => r.json())
      .then(cfg => { root.querySelector("#homeMode").textContent = cfg.mode; });

    const input = root.querySelector("#homeSymbol");
    const currentSymbol = () => (input.value.trim().toUpperCase() || "QQQ");

    root.querySelectorAll(".qchip").forEach(chip =>
      chip.addEventListener("click", () => { input.value = chip.dataset.sym; }));

    root.querySelectorAll(".card:not(.card-disabled)").forEach(card =>
      card.addEventListener("click", () => {
        const symbol = currentSymbol();
        localStorage.setItem("vo-symbol", symbol);
        location.hash = `#/${card.dataset.view}/${symbol}`;
      }));

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        localStorage.setItem("vo-symbol", currentSymbol());
        location.hash = `#/flow/${currentSymbol()}`;
      }
    });
    input.focus();
    input.select();
  },
  unmount() {},
  onData() {},
};
