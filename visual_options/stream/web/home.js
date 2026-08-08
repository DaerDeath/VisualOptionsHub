/* Vista de inicio: elegir símbolo y tipo de visualización. */
"use strict";

const QUICK_SYMBOLS = ["QQQ", "SPY", "SPX", "IWM", "DIA", "VIX", "NVDA", "TSLA", "AAPL", "MSFT",
                       "META", "AMZN", "GOOGL", "AMD", "NFLX", "COIN", "PLTR", "SMCI"];

const VIEW_CARDS = [
  {
    view: "flow", name: "Flujo de opciones", ready: true,
    desc: "Premium / volume profile por strike, put-call sell % contra el precio, GEX y magnet strikes.",
    art: "flow",
  },
  {
    view: "setup", name: "Setup: footprint + Wyckoff + VP", ready: true,
    desc: "El setup completo en un apartado: velas con eventos Wyckoff (spring, UT, SOS/SOW, absorción), Volume Profile con POC/VAH/VAL y footprint.",
    art: "setup",
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
    view: "chain", name: "Cadena + griegas", ready: true,
    desc: "Todas las opciones del vencimiento con precio teórico y griegas completas (Δ Γ Θ V ρ) por call y put, en vivo.",
    art: "chainart",
  },
  {
    view: "vol", name: "Volatilidad", ready: true,
    desc: "Smile de IV por strike, skew, IV ATM y bandas de movimiento esperado ±1σ/±2σ.",
    art: "vol",
  },
  {
    view: "termstructure", name: "Estructura de plazos", ready: true,
    desc: "IV ATM por vencimiento (TRMS): contango o backwardation en la curva de volatilidad.",
    art: "tsart",
  },
  {
    view: "volcone", name: "Cono de volatilidad", ready: true,
    desc: "Rango histórico de la vol realizada por ventana (VC): ¿la IV de hoy está cara o barata?",
    art: "vcart",
  },
  {
    view: "forward", name: "Forward & Cost of Carry", ready: true,
    desc: "Fórmula del libro paso a paso (NOVM): interés simple menos dividendos = Cost of Carry; Spot + Cost of Carry = Forward Price.",
    art: "fwart",
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
    view: "company", name: "Empresa", ready: true,
    desc: "Ficha Bloomberg-like: fundamentales, próximo earnings con historial de sorpresas EPS, analistas con price targets, noticias y el checklist del libro auto-evaluado.",
    art: "coart",
  },
  {
    view: "correlation", name: "Correlación", ready: true,
    desc: "Sensibilidad de los retornos frente a índices y sectores (CORR): de qué depende realmente el papel.",
    art: "crart",
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
    view: "maxpain", name: "Max Pain", ready: true,
    desc: "El precio de vencimiento que minimiza el pago a los compradores de opciones — el imán teórico del expiry.",
    art: "maxpain",
  },
  {
    view: "cvd", name: "Delta acumulado (CVD)", ready: true,
    desc: "Agresión compradora − vendedora acumulada vs precio, con divergencias marcadas automáticamente.",
    art: "hiro",
  },
  {
    view: "tpo", name: "Perfil TPO", ready: true,
    desc: "Market Profile con letras por periodo, initial balance y POC — aceptación vs rechazo de precios.",
    art: "tpo",
  },
  {
    view: "probs", name: "Probabilidades", ready: true,
    desc: "Cono de movimiento esperado ±1σ/±2σ y probabilidad de expirar ITM por strike.",
    art: "probs",
  },
  {
    view: "vwap", name: "VWAP + sesión", ready: true,
    desc: "Velas con VWAP y bandas ±1σ/±2σ más el resumen estadístico de la sesión.",
    art: "vwapart",
  },
  {
    view: "pcr", name: "Put/Call Ratio", ready: true,
    desc: "PCR por volumen y por open interest con lectura contraria y desglose por strike.",
    art: "oi",
  },
  {
    view: "stats", name: "Estadísticos", ready: true,
    desc: "Tus notebooks ARIMA+GARCH corregidos: cada test con su explicación y veredicto, y Monte Carlo de 2.000 rutas con un botón.",
    art: "statsart",
  },
  {
    view: "backtest", name: "Backtest de rangos", ready: true,
    desc: "¿Cómo habría ido vender strangles ±X% cada semana? Win rate, drawdown y equity con históricos reales.",
    art: "btart",
  },
  {
    view: "notebooks", name: "Notebooks (original)", ready: true,
    desc: "Tu gráfico histórico + proyección ARIMA+GARCH tal cual los .ipynb, sin cambios — informativo.",
    art: "nbart",
  },
  {
    view: "alerts", name: "Alertas", ready: true,
    desc: "Avisos locales: precio cruza nivel, call sell % bajo (squeeze), cruce del gamma flip. Beep + notificación.",
    art: "alertsart",
  },
  {
    view: "journal", name: "Diario", ready: true,
    desc: "Notas de trading con hora, símbolo y precio capturados automáticamente.",
    art: "journalart",
  },
  {
    view: "guide", name: "Guía", ready: true,
    desc: "Cómo leer cada apartado de la terminal: reglas, conceptos y trucos, en cristiano.",
    art: "guideart",
  },
  {
    view: null, name: "Próximamente", ready: false,
    desc: "Dime qué más quieres ver aquí y lo añado.",
    art: "plus",
  },
];

const HomeView = {
  renderSections() {
    const byView = new Map(VIEW_CARDS.filter(c => c.view).map(c => [c.view, c]));
    const used = new Set();
    const cardHtml = (c) => `
      <button class="card ${c.ready ? "" : "card-disabled"}" data-view="${c.view ?? ""}">
        <span class="card-art art-${c.art}" aria-hidden="true"></span>
        <span class="card-name">${c.name}</span>
        <span class="card-desc">${c.desc}</span>
      </button>`;
    let html = NAV_GROUPS.map(([group, views]) => {
      const cards = views.map(v => { used.add(v); return byView.get(v); }).filter(Boolean);
      if (!cards.length) return "";
      return `<section class="home-sec">
        <h2 class="home-sec-title">${group}</h2>
        <div class="cards">${cards.map(cardHtml).join("")}</div>
      </section>`;
    }).join("");
    const rest = VIEW_CARDS.filter(c => !c.view || !used.has(c.view));
    if (rest.length) {
      html += `<section class="home-sec"><div class="cards">${rest.map(cardHtml).join("")}</div></section>`;
    }
    return html;
  },

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
        ${this.renderSections()}
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

    attachSymbolPicker(input, {
      onPick: (symbol) => localStorage.setItem("vo-symbol", symbol),
      onEnter: (symbol) => {
        localStorage.setItem("vo-symbol", symbol || "QQQ");
        location.hash = `#/flow/${symbol || "QQQ"}`;
      },
    });
    input.focus();
    input.select();
  },
  unmount() {},
  onData() {},
};
