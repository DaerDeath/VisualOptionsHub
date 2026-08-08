/* Enrutador de la SPA: #/ inicio · #/flow/SYM · #/footprint/SYM.
 * Gestiona la barra superior, el WebSocket por símbolo y la pausa. */
"use strict";

const VIEWS = {
  flow: FlowView, setup: SetupView, footprint: FootprintView, dealer: DealerView,
  levels: LevelsView, heatmap: HeatmapView, hiro: HiroView,
  vol: VolView, oi: OIView, tape: TapeView,
  scanner: ScannerView, calc: CalcView,
  maxpain: MaxPainView, cvd: CvdView, tpo: TpoView, probs: ProbsView,
  vwap: VwapView, pcr: PcrView, chain: ChainView, company: CompanyView,
  termstructure: TermStructureView, volcone: VolConeView, correlation: CorrelationView,
  forward: ForwardView,
  stats: StatsView, backtest: BacktestView, notebooks: NotebooksView, portfolio: PortfolioView,
  grading: GradingView, stress: StressView,
  alerts: AlertsView, journal: JournalView,
  guide: GuideView,
};
const VIEW_TITLES = {
  flow: "flujo de opciones", setup: "setup: footprint + wyckoff + vp",
  footprint: "footprint", dealer: "dealer positioning",
  levels: "niveles clave", heatmap: "heatmap GEX", hiro: "impacto del flujo",
  vol: "volatilidad", oi: "perfil de OI", tape: "tape",
  scanner: "scanner", calc: "calculadora",
  maxpain: "max pain", cvd: "delta acumulado", tpo: "perfil TPO",
  probs: "probabilidades", vwap: "vwap + sesión", pcr: "put/call ratio",
  chain: "cadena + griegas", company: "empresa",
  termstructure: "estructura de plazos", volcone: "cono de volatilidad", correlation: "correlación",
  forward: "forward y cost of carry",
  stats: "estadísticos", backtest: "backtest", notebooks: "notebooks (original)", portfolio: "portafolio",
  grading: "grading (checklist A-F)", stress: "stress test",
  alerts: "alertas", journal: "diario", guide: "guía",
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
  expiry: 0,
  split: null,       // id de la vista secundaria en pantalla dividida
  sideView: null,    // objeto de la vista secundaria montada
};

/* ----------------------------------------------- selector de vencimiento */
async function loadExpirations() {
  const select = el("expirySel");
  try {
    const list = await fetch(
      `/api/expirations?symbol=${encodeURIComponent(app.symbol)}&source=${encodeURIComponent(app.source)}`
    ).then(r => r.json());
    if (app.expiry >= list.length) app.expiry = 0;
    select.innerHTML = list.map(e =>
      `<option value="${e.index}" ${e.index === app.expiry ? "selected" : ""}>${e.label}</option>`).join("");
  } catch (_) {
    select.innerHTML = `<option value="0">próximo</option>`;
    app.expiry = 0;
  }
}

function reconnectStream() {
  if (!app.viewName) return;
  if (typeof replay !== "undefined" && replay.active) return;  // en replay no hay directo
  if (app.client) app.client.close();
  app.lastPrice = null;
  app.client = new StreamClient(app.symbol, onData, app.source, app.expiry);
  fetch(`/api/snapshot?symbol=${encodeURIComponent(app.symbol)}&source=${encodeURIComponent(app.source)}&expiry=${app.expiry}`)
    .then(r => r.json())
    .then(onData)
    .catch(() => {});
}

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
    loadExpirations();  // el calendario puede diferir entre fuentes
    reconnectStream();
  }
}

function sourceLabel() {
  const entry = app.sourcesCatalog.find(s => s.id === app.source);
  return entry ? entry.label : app.source;
}

const el = (id) => document.getElementById(id);

/* Navegación agrupada (compartida con el home). */
const NAV_GROUPS = [
  ["Mercado", ["flow", "dealer", "levels", "heatmap", "hiro", "oi", "tape"]],
  ["Precio", ["setup", "footprint", "vwap", "cvd", "tpo"]],
  ["Opciones", ["chain", "vol", "termstructure", "volcone", "forward", "probs", "maxpain", "pcr", "calc"]],
  ["Análisis", ["company", "correlation", "scanner", "stats", "backtest", "notebooks"]],
  ["Cuenta", ["portfolio", "stress"]],
  ["Herramientas", ["grading", "alerts", "journal", "guide"]],
];
const NAV_SHORT = {
  flow: "Flujo", dealer: "Dealer", levels: "Niveles", heatmap: "Heatmap GEX",
  hiro: "HIRO", oi: "Perfil OI", tape: "Tape",
  setup: "Setup FP+Wyckoff+VP", footprint: "Footprint", vwap: "VWAP", cvd: "CVD", tpo: "TPO",
  chain: "Cadena + griegas",
  vol: "Volatilidad", termstructure: "Estructura de plazos", volcone: "Cono de volatilidad",
  forward: "Forward & Carry", probs: "Probabilidades", maxpain: "Max Pain", pcr: "Put/Call", calc: "Calculadora",
  company: "Empresa", correlation: "Correlación", scanner: "Scanner", stats: "Estadísticos",
  backtest: "Backtest", notebooks: "Notebooks", portfolio: "Portafolio", stress: "Stress Test",
  grading: "Grading", alerts: "Alertas", journal: "Diario", guide: "Guía",
};

function renderNav(activeView, symbol) {
  const nav = el("viewNav");
  nav.innerHTML = NAV_GROUPS.map(([group, views]) => {
    const isActiveGroup = views.includes(activeView);
    const label = isActiveGroup ? NAV_SHORT[activeView] : group;
    return `<div class="navgroup ${isActiveGroup ? "active" : ""}">
      <button class="navgroup-btn">${label} <span class="caret">▾</span></button>
      <div class="navgroup-menu">
        ${views.map(view => `<a href="#/${view}/${symbol}" class="${view === activeView ? "active" : ""}">${NAV_SHORT[view]}</a>`).join("")}
      </div>
    </div>`;
  }).join("");
}

function parseHash() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts.length >= 1 && VIEWS[parts[0]]) {
    return { view: parts[0], symbol: (parts[1] || localStorage.getItem("vo-symbol") || "QQQ").toUpperCase() };
  }
  return { view: null, symbol: null };
}

function route() {
  const { view, symbol } = parseHash();
  if (typeof replay !== "undefined" && replay.active) closeReplay(false);
  app.current.unmount();
  if (app.sideView) { app.sideView.unmount(); app.sideView = null; }
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
  el("replayBtn").hidden = !inView;
  el("shotBtn").hidden = !inView;
  el("splitSel").hidden = !inView;
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

  const symbolChanged = app.symbol !== symbol;
  app.viewName = view;
  app.symbol = symbol;
  localStorage.setItem("vo-symbol", symbol);
  el("symbolInput").value = symbol;
  renderNav(view, symbol);
  if (symbolChanged) loadExpirations();

  // pantalla dividida: opciones del selector (todas menos la vista actual)
  const splitSel = el("splitSel");
  if (app.split === view) app.split = null;
  splitSel.innerHTML = `<option value="">— dividir —</option>` +
    Object.keys(VIEWS).filter(v => v !== view)
      .map(v => `<option value="${v}" ${v === app.split ? "selected" : ""}>◫ ${NAV_SHORT[v]}</option>`).join("");

  app.current = VIEWS[view];
  root.classList.toggle("split", !!app.split);
  if (app.split) {
    root.innerHTML = `<div class="split-pane" id="viewMain"></div><div class="split-pane" id="viewSide"></div>`;
    app.current.mount(root.querySelector("#viewMain"));
    app.sideView = VIEWS[app.split];
    app.sideView.mount(root.querySelector("#viewSide"));
  } else {
    app.current.mount(root);
  }
  reconnectStream();
}

function onData(payload) {
  if (app.paused) { app.pending = payload; return; }
  updateHeader(payload.flow);
  app.current.onData(payload);
  if (app.sideView) app.sideView.onData(payload);
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

el("expirySel").addEventListener("change", (e) => {
  app.expiry = parseInt(e.target.value, 10) || 0;
  reconnectStream();
});

el("splitSel").addEventListener("change", (e) => {
  app.split = e.target.value || null;
  route();  // remonta con/sin panel secundario
});

/* ------------------------------------------------------ replay de sesión */
const replay = { active: false, sessions: [], current: null, total: 0, timer: null };

async function openReplay() {
  const bar = el("replayBar");
  replay.sessions = await fetch(`/api/replay/days?symbol=${encodeURIComponent(app.symbol)}`)
    .then(r => r.json()).catch(() => []);
  const select = el("rpSession");
  if (!replay.sessions.length) {
    select.innerHTML = `<option>sin sesiones grabadas de ${app.symbol}</option>`;
    bar.hidden = false;
    return;
  }
  select.innerHTML = replay.sessions.map((s, i) =>
    `<option value="${i}">${s.day} · ${s.source} · exp${s.expiry} · ${s.count} snaps (${s.from}–${s.to})</option>`).join("");
  bar.hidden = false;
  replay.active = true;
  if (app.client) { app.client.close(); app.client = null; }
  await selectReplaySession(0);
}

async function selectReplaySession(index) {
  replay.current = replay.sessions[index];
  stopReplayTimer();
  await loadReplayIndex(0);
}

async function loadReplayIndex(index) {
  const s = replay.current;
  if (!s) return;
  const query = `symbol=${encodeURIComponent(app.symbol)}&day=${s.day}&source=${s.source}&expiry=${s.expiry}&i=${index}`;
  try {
    const data = await fetch(`/api/replay?${query}`).then(r => r.json());
    replay.total = data.total;
    const slider = el("rpSlider");
    slider.max = data.total - 1;
    slider.value = data.index;
    el("rpTs").textContent = data.ts;
    onData(data.payload);
    if (data.index >= data.total - 1) stopReplayTimer();
  } catch (_) { stopReplayTimer(); }
}

function stopReplayTimer() {
  clearInterval(replay.timer);
  replay.timer = null;
  el("rpPlay").textContent = "▶";
}

function closeReplay(reconnect = true) {
  stopReplayTimer();
  replay.active = false;
  el("replayBar").hidden = true;
  if (reconnect) reconnectStream();
}

/* ------------------------------------------------- exportar vista a PNG */
el("shotBtn").addEventListener("click", () => {
  const canvases = [...document.querySelectorAll("#view canvas")]
    .filter(c => c.width > 0 && c.height > 0);
  if (!canvases.length) return;
  const gap = 14, header = 34;
  const width = Math.max(...canvases.map(c => c.width));
  const height = header + canvases.reduce((acc, c) => acc + c.height + gap, 0);
  const out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const ctx = out.getContext("2d");
  ctx.fillStyle = css("--bg") || "#0a0d12";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = css("--accent");
  ctx.font = "700 18px " + css("--mono");
  const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
  ctx.fillText(`${app.symbol} · ${VIEW_TITLES[app.viewName] || app.viewName} · ${stamp} · visual-options`, 12, 24);
  let y = header;
  canvases.forEach(c => {
    ctx.drawImage(c, 0, y);
    y += c.height + gap;
  });
  const link = document.createElement("a");
  link.download = `${app.symbol}_${app.viewName}_${stamp.replace(/[: ]/g, "-")}.png`;
  link.href = out.toDataURL("image/png");
  link.click();
});

el("replayBtn").addEventListener("click", () => {
  replay.active ? closeReplay() : openReplay();
});
el("rpClose").addEventListener("click", () => closeReplay());
el("rpSession").addEventListener("change", (e) => selectReplaySession(Number(e.target.value)));
el("rpSlider").addEventListener("input", (e) => loadReplayIndex(Number(e.target.value)));
el("rpPlay").addEventListener("click", () => {
  if (replay.timer) { stopReplayTimer(); return; }
  el("rpPlay").textContent = "⏸";
  const step = () => {
    const next = Number(el("rpSlider").value) + 1;
    if (next >= replay.total) { stopReplayTimer(); return; }
    loadReplayIndex(next);
  };
  replay.timer = setInterval(step, 1000 / Number(el("rpSpeed").value));
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
initSources().then(route);
