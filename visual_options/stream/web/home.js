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
    view: "dealer", name: "Dealer positioning", ready: true,
    desc: "Net GEX, Net DEX y Net Vanna por strike con gamma flip — lo que calcula CloutSeeker, sin Excel ni Windows.",
    art: "dealer",
  },
  {
    view: "levels", name: "Niveles clave", ready: true,
    desc: "Nota auto-generada: call/put wall, gamma flip, imán, movimiento esperado y lectura del flujo.",
    art: "levels",
  },
  {
    view: "heatmap", name: "Heatmap GEX", ready: true,
    desc: "Mapa tiempo × strike del Net GEX con el recorrido del precio — zonas que frenan o aceleran.",
    art: "heatmap",
  },
  {
    view: "hiro", name: "Impacto del flujo", ready: true,
    desc: "Índice acumulado del flujo de opciones frente al precio, para cazar divergencias (HIRO-like).",
    art: "hiro",
  },
  {
    view: "vol", name: "Volatilidad", ready: true,
    desc: "Smile de IV por strike, skew, IV ATM y bandas de movimiento esperado ±1σ/±2σ.",
    art: "vol",
  },
  {
    view: "oi", name: "Perfil de OI", ready: true,
    desc: "Open interest de calls y puts en espejo por strike con put/call ratio.",
    art: "oi",
  },
  {
    view: "tape", name: "Tape", ready: true,
    desc: "Operaciones destacadas en vivo: bloques grandes con lado, contratos y prima.",
    art: "tape",
  },
  {
    view: "scanner", name: "Scanner", ready: true,
    desc: "Señales direccionales y de volatilidad por símbolo: flujo, Σ GEX, régimen y distancia al flip.",
    art: "scanner",
  },
  {
    view: "calc", name: "Calculadora", ready: true,
    desc: "Las 23 estrategias del libro con P/L, breakevens, prob. de beneficio y griegas.",
    art: "calc",
  },
  {
    view: null, name: "Próximamente", ready: false,
    desc: "Dime qué más quieres ver aquí: ladder de DOM, perfil TPO…",
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
          <p class="home-sub">elige un subyacente y una visualización · fuente: <span id="homeMode">…</span> <span class="home-sub-hint">(cámbiala arriba a la derecha)</span></p>
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

    root.querySelector("#homeMode").textContent =
      typeof sourceLabel === "function" ? sourceLabel() : "sim";

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
