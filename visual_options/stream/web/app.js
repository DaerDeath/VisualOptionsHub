/* Enrutador de la SPA: #/ inicio · #/flow/SYM · #/footprint/SYM.
 * Gestiona la barra superior, el WebSocket por símbolo y la pausa. */
"use strict";

const VIEWS = { flow: FlowView, footprint: FootprintView };
const VIEW_TITLES = { flow: "flujo de opciones", footprint: "footprint" };

const app = {
  current: HomeView,
  viewName: null,
  symbol: null,
  client: null,
  paused: false,
  pending: null,
  lastPrice: null,
};

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
  app.client = new StreamClient(symbol, onData);
  fetch(`/api/snapshot?symbol=${encodeURIComponent(symbol)}`)
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

/* Cambio de símbolo desde la barra superior. */
el("symbolInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && app.viewName) {
    const symbol = e.target.value.trim().toUpperCase();
    if (symbol) location.hash = `#/${app.viewName}/${symbol}`;
    e.target.blur();
  }
});

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
route();
