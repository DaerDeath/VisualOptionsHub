/* Enrutador de la SPA: #/ inicio · #/flow/SYM · #/footprint/SYM.
 * Gestiona la barra superior, el WebSocket por símbolo y la pausa. */
"use strict";

const VIEWS = {
  flow: FlowView, setup: SetupView, footprint: FootprintView, dealer: DealerView,
  levels: LevelsView, heatmap: HeatmapView, hiro: HiroView,
  vol: VolView, oi: OIView, tape: TapeView,
  scanner: ScannerView, calc: CalcView,
};
const VIEW_TITLES = {
  flow: "flujo de opciones", setup: "setup: footprint + wyckoff + vp",
  footprint: "footprint", dealer: "dealer positioning",
  levels: "niveles clave", heatmap: "heatmap GEX", hiro: "impacto del flujo",
  vol: "volatilidad", oi: "perfil de OI", tape: "tape",
  scanner: "scanner", calc: "calculadora",
};

const app = {
  current: HomeView,
  viewName: null,
  symbol: null,
  client: null,
  paused: false,
  pending: null,
  lastPrice: null,
  source: "sim",
  sourcesCatalog: [],
};

/* ------------------------------------------------ selector de proveedor */
async function initSources() {
  try {
    const cfg = await fetch("/api/config").then(r => r.json());
    app.sourcesCatalog = cfg.sources;
    const available = new Set(cfg.sources.filter(s => s.available).map(s => s.id));
    const saved = localStorage.getItem("vo-source");
    app.source = available.has(saved) ? saved : cfg.default;
  } catch (_) {
    app.sourcesCatalog = [{ id: "sim", label: "Simulación", available: true, reason: "" }];
    app.source = "sim";
  }
  renderSourceNav();
}

function renderSourceNav() {
  const nav = el("srcNav");
  nav.innerHTML = app.sourcesCatalog.map(s => {
    const active = s.id === app.source ? "active" : "";
    const disabled = s.available ? "" : "disabled";
    const title = s.available ? (s.reason || s.label) : s.reason;
    return `<button class="srcbtn ${active}" data-src="${s.id}" ${disabled} title="${title}">${s.label}</button>`;
  }).join("");
  nav.querySelectorAll(".srcbtn:not([disabled])").forEach(btn =>
    btn.addEventListener("click", () => setSource(btn.dataset.src)));
}

function setSource(source) {
  if (source === app.source) return;
  app.source = source;
  localStorage.setItem("vo-source", source);
  renderSourceNav();
  const homeMode = document.getElementById("homeMode");
  if (homeMode) homeMode.textContent = sourceLabel();
  if (app.viewName) {
    // reconecta la vista actual con el nuevo proveedor
    if (app.client) { app.client.close(); }
    app.lastPrice = null;
    app.client = new StreamClient(app.symbol, onData, source);
    fetch(`/api/snapshot?symbol=${encodeURIComponent(app.symbol)}&source=${encodeURIComponent(source)}`)
      .then(r => r.json())
      .then(onData)
      .catch(() => {});
  }
}

function sourceLabel() {
  const entry = app.sourcesCatalog.find(s => s.id === app.source);
  return entry ? entry.label : app.source;
}

const el = (id) => document.getElementById(id);

function parseHash() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts.length >= 1 && VIEWS[parts[0]]) {
    return { view: parts[0], symbol: (parts[1] || localStorage.getItem("vo-symbol") || "QQQ").toUpperCase() };
  }
  return { view: null, symbol: null };
}

function route() {
  const { view, symbol } = parseHash();
  app.current.unmount();
  if (app.client) { app.client.close(); app.client = null; }
  app.paused = false;
  app.pending = null;
  app.lastPrice = null;
  el("pauseBtn").textContent = "⏸";
  el("pauseBtn").classList.remove("active");

  const root = el("view");
  const inView = view !== null;
  el("quoteBox").hidden = !inView;
  el("aggBox").hidden = !inView;
  el("viewNav").hidden = !inView;
  el("pauseBtn").hidden = !inView;
  el("viewTitle").textContent = inView ? VIEW_TITLES[view] : "terminal";

  if (!inView) {
    app.current = HomeView;
    app.viewName = null;
    app.symbol = null;
    el("status").className = "status ok";
    el("clock").textContent = "";
    HomeView.mount(root);
    return;
  }

  app.viewName = view;
  app.symbol = symbol;
  localStorage.setItem("vo-symbol", symbol);
  el("symbolInput").value = symbol;
  document.querySelectorAll("#viewNav a").forEach(a => {
    a.classList.toggle("active", a.dataset.view === view);
    a.href = `#/${a.dataset.view}/${symbol}`;
  });

  app.current = VIEWS[view];
  app.current.mount(root);
  app.client = new StreamClient(symbol, onData, app.source);
  fetch(`/api/snapshot?symbol=${encodeURIComponent(symbol)}&source=${encodeURIComponent(app.source)}`)
    .then(r => r.json())
    .then(onData)
    .catch(() => {});
}

function onData(payload) {
  if (app.paused) { app.pending = payload; return; }
  updateHeader(payload.flow);
  app.current.onData(payload);
}

function updateHeader(flow) {
  if (!flow) return;
  const priceEl = el("price");
  priceEl.textContent = flow.spot ? flow.spot.toFixed(2) : "—";
  if (app.lastPrice !== null && flow.spot !== app.lastPrice) {
    priceEl.classList.toggle("up", flow.spot > app.lastPrice);
    priceEl.classList.toggle("down", flow.spot < app.lastPrice);
  }
  app.lastPrice = flow.spot;
  el("putSell").textContent = flow.put_sell_pct.toFixed(2);
  el("callSell").textContent = flow.call_sell_pct.toFixed(2);
  el("clock").textContent = flow.timestamp || "";
  const status = el("status");
  status.className = "status " + (flow.connected ? (flow.source === "sim" ? "sim" : "ok") : "");
  status.title = flow.source === "sim" ? "simulador" : (flow.connected ? flow.source + " conectado" : "desconectado");
}

/* Cambio de símbolo desde la barra superior (con autocompletado). */
function gotoSymbol(symbol) {
  if (symbol && app.viewName) location.hash = `#/${app.viewName}/${symbol}`;
}
attachSymbolPicker(el("symbolInput"), { onPick: gotoSymbol, onEnter: gotoSymbol });

/* Pausa. */
function togglePause() {
  if (!app.viewName) return;
  app.paused = !app.paused;
  const btn = el("pauseBtn");
  btn.textContent = app.paused ? "▶" : "⏸";
  btn.classList.toggle("active", app.paused);
  if (!app.paused && app.pending) {
    const payload = app.pending;
    app.pending = null;
    onData(payload);
  }
}
el("pauseBtn").addEventListener("click", togglePause);
addEventListener("keydown", (e) => {
  if (e.code === "Space" && e.target === document.body) { e.preventDefault(); togglePause(); }
});

addEventListener("hashchange", route);
initSources().then(route);
