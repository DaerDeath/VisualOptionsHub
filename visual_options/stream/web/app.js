/* Dashboard de flujo de opciones — render en canvas sin dependencias.
 *
 * Lectura (según el vídeo "how to read the stream's data"):
 *  - % en cada strike = porción VENDIDA de ese lado (rojo); el resto, comprada (verde).
 *  - Histograma blanco = perfil visual del volumen.
 *  - Panel de series: azul (call sell %) baja → precio sube; roja (put sell %) baja → precio la sigue.
 *  - Magnet strikes = OI de mariposas / volumen: actúa como imán del precio.
 */
"use strict";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const COLORS = {
  sold: css("--sold"), soldDim: css("--sold-dim"),
  bought: css("--bought"), boughtDim: css("--bought-dim"),
  call: css("--call-line"), put: css("--put-line"), price: css("--price-line"),
  accent: css("--accent"), text: css("--text"), dim: css("--text-dim"),
  border: css("--border"), surface2: css("--surface-2"),
};
const MONO = "11px " + css("--mono");

const state = {
  data: null,
  paused: false,
  pending: null,
  hover: { panel: null, index: -1, x: 0, y: 0 },
  pinnedStrike: null,
  lastPrice: null,
};

/* ------------------------------------------------------------- canvases */
class Panel {
  constructor(id, drawFn) {
    this.canvas = document.getElementById(id);
    this.ctx = this.canvas.getContext("2d");
    this.drawFn = drawFn;
    new ResizeObserver(() => this.resize()).observe(this.canvas);
    this.resize();
  }
  resize() {
    const dpr = window.devicePixelRatio || 1;
    const { clientWidth: w, clientHeight: h } = this.canvas;
    if (w === 0 || h === 0) return;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = w; this.h = h;
    render();
  }
  draw() {
    if (!state.data || !this.w) return;
    this.ctx.clearRect(0, 0, this.w, this.h);
    this.drawFn(this.ctx, this.w, this.h);
  }
}

const fmtK = (n) => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : String(n);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/* ------------------------------------------ panel 1: perfil por strike */
const PROFILE = { top: 30, axisH: 22, bottom: 30, chipH: 16 };

function profileLayout(w) {
  const rows = state.data.strikes;
  const colW = w / rows.length;
  return { rows, colW };
}

function drawProfile(ctx, w, h) {
  const { rows, colW } = profileLayout(w);
  const axisY = h / 2;
  const halfH = axisY - PROFILE.top - PROFILE.axisH / 2 - PROFILE.chipH;
  const maxCall = Math.max(1, ...rows.map(r => r.call_volume));
  const maxPut = Math.max(1, ...rows.map(r => r.put_volume));

  rows.forEach((r, i) => {
    const x = i * colW + colW * 0.14;
    const bw = colW * 0.72;
    const hovered = state.hover.panel === "profile" && state.hover.index === i;
    const pinned = state.pinnedStrike === r.strike;

    // mitad de calls (hacia arriba): vendido (rojo) pegado al eje, comprado encima
    const cSold = halfH * r.call_sold_pct / 100;
    const yTopCall = axisY - PROFILE.axisH / 2;
    ctx.fillStyle = hovered || pinned ? COLORS.sold : COLORS.soldDim;
    ctx.fillRect(x, yTopCall - cSold, bw, cSold);
    ctx.fillStyle = hovered || pinned ? COLORS.bought : COLORS.boughtDim;
    ctx.fillRect(x, yTopCall - halfH, bw, halfH - cSold);

    // mitad de puts (hacia abajo)
    const pSold = halfH * r.put_sold_pct / 100;
    const yBotPut = axisY + PROFILE.axisH / 2;
    ctx.fillStyle = hovered || pinned ? COLORS.sold : COLORS.soldDim;
    ctx.fillRect(x, yBotPut, bw, pSold);
    ctx.fillStyle = hovered || pinned ? COLORS.bought : COLORS.boughtDim;
    ctx.fillRect(x, yBotPut + pSold, bw, halfH - pSold);

    // etiquetas de % vendido junto al eje
    ctx.font = MONO;
    ctx.textAlign = "center";
    ctx.fillStyle = "#fff";
    ctx.fillText(Math.round(r.call_sold_pct) + "%", x + bw / 2, yTopCall - 5);
    ctx.fillText(Math.round(r.put_sold_pct) + "%", x + bw / 2, yBotPut + 13);

    // chips de volumen en los bordes
    ctx.fillStyle = COLORS.surface2;
    ctx.fillRect(x, PROFILE.top - PROFILE.chipH + 2, bw, PROFILE.chipH - 4);
    ctx.fillRect(x, h - PROFILE.bottom + 2, bw, PROFILE.chipH - 4);
    ctx.fillStyle = "#9fc2e8";
    ctx.fillText(fmtK(r.call_volume), x + bw / 2, PROFILE.top - 6);
    ctx.fillText(fmtK(r.put_volume), x + bw / 2, h - PROFILE.bottom + 13);
  });

  // histograma blanco translúcido: perfil de volumen (calls arriba, puts abajo)
  const volPath = (getVol, maxVol, sign) => {
    ctx.beginPath();
    ctx.moveTo(0, axisY - sign * PROFILE.axisH / 2);
    rows.forEach((r, i) => {
      const vh = halfH * getVol(r) / maxVol;
      ctx.lineTo(i * colW + colW / 2, axisY - sign * (PROFILE.axisH / 2 + vh));
    });
    ctx.lineTo(w, axisY - sign * PROFILE.axisH / 2);
    ctx.closePath();
    ctx.fillStyle = "rgba(240, 245, 250, 0.16)";
    ctx.fill();
  };
  volPath(r => r.call_volume, maxCall, 1);
  volPath(r => r.put_volume, maxPut, -1);

  // eje central con strikes
  ctx.fillStyle = "#000";
  ctx.fillRect(0, axisY - PROFILE.axisH / 2, w, PROFILE.axisH);
  ctx.strokeStyle = COLORS.border;
  ctx.strokeRect(0, axisY - PROFILE.axisH / 2, w, PROFILE.axisH);
  ctx.font = "600 " + MONO;
  rows.forEach((r, i) => {
    ctx.fillStyle = state.pinnedStrike === r.strike ? COLORS.accent : COLORS.text;
    ctx.fillText(String(Math.round(r.strike)), i * colW + colW / 2, axisY + 4);
  });

  // marcador del spot
  const spotX = spotToX(state.data.spot, rows, colW);
  if (spotX !== null) {
    ctx.strokeStyle = COLORS.accent;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(spotX, PROFILE.top);
    ctx.lineTo(spotX, h - PROFILE.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = COLORS.accent;
    ctx.font = "600 " + MONO;
    ctx.fillText(state.data.spot.toFixed(2), spotX, PROFILE.top - 18);
  }
}

function spotToX(spot, rows, colW) {
  const first = rows[0].strike, last = rows[rows.length - 1].strike;
  if (spot < first || spot > last) return null;
  return ((spot - first) / (last - first)) * (colW * (rows.length - 1)) + colW / 2;
}

/* ------------------------------------------- panel 2: series temporales */
const SERIES_PAD = { l: 34, r: 48, t: 10, b: 22 };

function seriesScales(w, h) {
  const pts = state.data.series;
  const pctMax = Math.max(20, ...pts.map(p => Math.max(p.put_sell_pct, p.call_sell_pct))) * 1.1;
  const prices = pts.map(p => p.price);
  const pMin = Math.min(...prices), pMax = Math.max(...prices);
  const pad = Math.max(0.4, (pMax - pMin) * 0.08);
  const x = (i) => SERIES_PAD.l + (i / Math.max(1, pts.length - 1)) * (w - SERIES_PAD.l - SERIES_PAD.r);
  const yPct = (v) => h - SERIES_PAD.b - (v / pctMax) * (h - SERIES_PAD.t - SERIES_PAD.b);
  const yPrice = (v) => h - SERIES_PAD.b - ((v - (pMin - pad)) / ((pMax + pad) - (pMin - pad))) * (h - SERIES_PAD.t - SERIES_PAD.b);
  return { pts, pctMax, pMin: pMin - pad, pMax: pMax + pad, x, yPct, yPrice };
}

function drawSeries(ctx, w, h) {
  const s = seriesScales(w, h);
  if (s.pts.length < 2) return;

  // rejilla y ejes
  ctx.strokeStyle = COLORS.border;
  ctx.fillStyle = COLORS.dim;
  ctx.font = MONO;
  ctx.textAlign = "left";
  for (let g = 0; g <= 4; g++) {
    const v = (s.pctMax / 4) * g;
    const y = s.yPct(v);
    ctx.globalAlpha = 0.5;
    ctx.beginPath(); ctx.moveTo(SERIES_PAD.l, y); ctx.lineTo(w - SERIES_PAD.r, y); ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.fillText(Math.round(v) + "%", 2, y + 3);
    const price = s.pMin + ((s.pMax - s.pMin) / 4) * g;
    ctx.fillText(price.toFixed(1), w - SERIES_PAD.r + 4, s.yPrice(price) + 3);
  }

  const line = (getV, yScale, color, width) => {
    ctx.beginPath();
    s.pts.forEach((p, i) => {
      const px = s.x(i), py = yScale(getV(p));
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.lineWidth = 1;
  };
  line(p => p.put_sell_pct, s.yPct, COLORS.put, 1.4);
  line(p => p.call_sell_pct, s.yPct, COLORS.call, 1.4);
  line(p => p.price, s.yPrice, COLORS.price, 1.8);

  // etiquetas de tiempo
  ctx.fillStyle = COLORS.dim;
  ctx.textAlign = "center";
  const step = Math.max(1, Math.floor(s.pts.length / 6));
  for (let i = 0; i < s.pts.length; i += step) {
    ctx.fillText(s.pts[i].t.slice(0, 5), s.x(i), h - 6);
  }

  // crosshair interactivo
  if (state.hover.panel === "series" && state.hover.index >= 0) {
    const i = state.hover.index, p = s.pts[i], px = s.x(i);
    ctx.strokeStyle = COLORS.dim;
    ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(px, SERIES_PAD.t); ctx.lineTo(px, h - SERIES_PAD.b); ctx.stroke();
    ctx.setLineDash([]);
    [[s.yPrice(p.price), COLORS.price], [s.yPct(p.put_sell_pct), COLORS.put], [s.yPct(p.call_sell_pct), COLORS.call]]
      .forEach(([y, c]) => {
        ctx.beginPath(); ctx.arc(px, y, 3.4, 0, Math.PI * 2);
        ctx.fillStyle = c; ctx.fill();
      });
  }
}

/* -------------------------------------------------- panel 3: gamma GEX */
const GAMMA_PAD = { l: 8, r: 8, t: 14, b: 22 };

function drawGamma(ctx, w, h) {
  const rows = state.data.strikes;
  const colW = (w - GAMMA_PAD.l - GAMMA_PAD.r) / rows.length;
  const maxAbs = Math.max(1e-6, ...rows.map(r => Math.abs(r.gamma_exposure)));
  const zeroY = GAMMA_PAD.t + (h - GAMMA_PAD.t - GAMMA_PAD.b) / 2;
  const scale = (h - GAMMA_PAD.t - GAMMA_PAD.b) / 2 / maxAbs;

  rows.forEach((r, i) => {
    const x = GAMMA_PAD.l + i * colW + colW * 0.18;
    const bw = colW * 0.64;
    const v = r.gamma_exposure * scale;
    const hovered = state.hover.panel === "gamma" && state.hover.index === i;
    ctx.fillStyle = r.gamma_exposure >= 0
      ? (hovered ? COLORS.bought : "rgba(47,164,99,0.75)")
      : (hovered ? COLORS.sold : "rgba(224,67,63,0.7)");
    if (v >= 0) ctx.fillRect(x, zeroY - v, bw, v);
    else ctx.fillRect(x, zeroY, bw, -v);
  });

  ctx.strokeStyle = COLORS.border;
  ctx.beginPath(); ctx.moveTo(GAMMA_PAD.l, zeroY); ctx.lineTo(w - GAMMA_PAD.r, zeroY); ctx.stroke();

  ctx.font = MONO; ctx.fillStyle = COLORS.dim; ctx.textAlign = "center";
  const step = Math.ceil(rows.length / 8);
  rows.forEach((r, i) => {
    if (i % step === 0) ctx.fillText(String(Math.round(r.strike)), GAMMA_PAD.l + i * colW + colW / 2, h - 6);
  });

  const spotX = spotToX(state.data.spot, rows, colW);
  if (spotX !== null) {
    ctx.strokeStyle = COLORS.accent;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(GAMMA_PAD.l + spotX, GAMMA_PAD.t);
    ctx.lineTo(GAMMA_PAD.l + spotX, h - GAMMA_PAD.b);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

/* -------------------------------------------- panel 4: magnet strikes */
const MAGNET_PAD = { l: 44, r: 12, t: 8, b: 8 };

function drawMagnet(ctx, w, h) {
  const rows = [...state.data.strikes].reverse();  // strike alto arriba
  const rowH = (h - MAGNET_PAD.t - MAGNET_PAD.b) / rows.length;
  const maxV = Math.max(1e-6, ...rows.map(r => r.magnet));

  rows.forEach((r, i) => {
    const y = MAGNET_PAD.t + i * rowH;
    const bw = (w - MAGNET_PAD.l - MAGNET_PAD.r) * (r.magnet / maxV);
    const hovered = state.hover.panel === "magnet" && state.hover.index === i;
    const intensity = r.magnet / maxV;
    ctx.fillStyle = hovered ? COLORS.accent : `rgba(232, 184, 75, ${0.25 + intensity * 0.6})`;
    ctx.fillRect(MAGNET_PAD.l, y + rowH * 0.15, bw, rowH * 0.7);
    ctx.font = MONO;
    ctx.textAlign = "right";
    ctx.fillStyle = hovered ? COLORS.accent : COLORS.dim;
    ctx.fillText(String(Math.round(r.strike)), MAGNET_PAD.l - 5, y + rowH / 2 + 4);
  });

  // línea del spot
  const first = rows[rows.length - 1].strike, last = rows[0].strike;
  if (state.data.spot >= first && state.data.spot <= last) {
    const y = MAGNET_PAD.t + ((last - state.data.spot) / (last - first)) * (rowH * (rows.length - 1)) + rowH / 2;
    ctx.strokeStyle = COLORS.price;
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(MAGNET_PAD.l, y); ctx.lineTo(w - MAGNET_PAD.r, y); ctx.stroke();
    ctx.setLineDash([]);
  }
}

/* --------------------------------------------------- tooltips y ratón */
const tooltip = document.getElementById("tooltip");

function showTooltip(html, clientX, clientY) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  const pad = 14;
  const rect = tooltip.getBoundingClientRect();
  let x = clientX + pad, y = clientY + pad;
  if (x + rect.width > innerWidth - 8) x = clientX - rect.width - pad;
  if (y + rect.height > innerHeight - 8) y = clientY - rect.height - pad;
  tooltip.style.left = x + "px";
  tooltip.style.top = y + "px";
}

function hideTooltip() { tooltip.hidden = true; }

function strikeTooltip(r) {
  const cb = (100 - r.call_sold_pct).toFixed(0), pb = (100 - r.put_sold_pct).toFixed(0);
  return `<div class="tt-title">Strike ${Math.round(r.strike)}</div>` +
    `<div class="tt-call">Calls ${fmtK(r.call_volume)} · ${r.call_sold_pct.toFixed(0)}% vendido / ${cb}% comprado</div>` +
    `<div class="tt-put">Puts&nbsp; ${fmtK(r.put_volume)} · ${r.put_sold_pct.toFixed(0)}% vendido / ${pb}% comprado</div>` +
    `<div>GEX ${r.gamma_exposure.toFixed(1)} M$ · magnet ${r.magnet.toFixed(2)}</div>` +
    `<div class="tt-dim">clic para fijar/soltar el strike</div>`;
}

function attachProfileMouse(panel) {
  panel.canvas.addEventListener("pointermove", (e) => {
    if (!state.data) return;
    const { colW, rows } = profileLayout(panel.w);
    const i = clamp(Math.floor(e.offsetX / colW), 0, rows.length - 1);
    state.hover = { panel: "profile", index: i };
    showTooltip(strikeTooltip(rows[i]), e.clientX, e.clientY);
    render();
  });
  panel.canvas.addEventListener("pointerleave", () => { state.hover = { panel: null, index: -1 }; hideTooltip(); render(); });
  panel.canvas.addEventListener("click", (e) => {
    const { colW, rows } = profileLayout(panel.w);
    const strike = rows[clamp(Math.floor(e.offsetX / colW), 0, rows.length - 1)].strike;
    state.pinnedStrike = state.pinnedStrike === strike ? null : strike;
    render();
  });
}

function attachSeriesMouse(panel) {
  panel.canvas.addEventListener("pointermove", (e) => {
    if (!state.data || state.data.series.length < 2) return;
    const s = seriesScales(panel.w, panel.h);
    const frac = (e.offsetX - SERIES_PAD.l) / (panel.w - SERIES_PAD.l - SERIES_PAD.r);
    const i = clamp(Math.round(frac * (s.pts.length - 1)), 0, s.pts.length - 1);
    state.hover = { panel: "series", index: i };
    const p = s.pts[i];
    showTooltip(
      `<div class="tt-title">${p.t}</div>` +
      `<div>precio ${p.price.toFixed(2)}</div>` +
      `<div class="tt-put">put sell ${p.put_sell_pct.toFixed(1)}%</div>` +
      `<div class="tt-call">call sell ${p.call_sell_pct.toFixed(1)}%</div>`,
      e.clientX, e.clientY);
    render();
  });
  panel.canvas.addEventListener("pointerleave", () => { state.hover = { panel: null, index: -1 }; hideTooltip(); render(); });
}

function attachBarsMouse(panel, panelName, reversed) {
  panel.canvas.addEventListener("pointermove", (e) => {
    if (!state.data) return;
    const rows = state.data.strikes;
    let i;
    if (panelName === "magnet") {
      const rowH = (panel.h - MAGNET_PAD.t - MAGNET_PAD.b) / rows.length;
      i = clamp(Math.floor((e.offsetY - MAGNET_PAD.t) / rowH), 0, rows.length - 1);
    } else {
      const colW = (panel.w - GAMMA_PAD.l - GAMMA_PAD.r) / rows.length;
      i = clamp(Math.floor((e.offsetX - GAMMA_PAD.l) / colW), 0, rows.length - 1);
    }
    state.hover = { panel: panelName, index: i };
    const r = reversed ? [...rows].reverse()[i] : rows[i];
    showTooltip(strikeTooltip(r), e.clientX, e.clientY);
    render();
  });
  panel.canvas.addEventListener("pointerleave", () => { state.hover = { panel: null, index: -1 }; hideTooltip(); render(); });
}

/* ------------------------------------------------------ cabecera y ws */
function updateHeader() {
  const d = state.data;
  document.getElementById("symbol").textContent = d.symbol;
  const priceEl = document.getElementById("price");
  priceEl.textContent = d.spot.toFixed(2);
  if (state.lastPrice !== null && d.spot !== state.lastPrice) {
    priceEl.classList.toggle("up", d.spot > state.lastPrice);
    priceEl.classList.toggle("down", d.spot < state.lastPrice);
  }
  state.lastPrice = d.spot;
  document.getElementById("putSell").textContent = d.put_sell_pct.toFixed(4);
  document.getElementById("callSell").textContent = d.call_sell_pct.toFixed(4);
  document.getElementById("clock").textContent = d.timestamp || "--:--:--";
  const status = document.getElementById("status");
  status.className = "status " + (d.connected ? (d.source === "sim" ? "sim" : "ok") : "");
  status.title = d.source === "sim" ? "simulador" : (d.connected ? "IBKR conectado" : "desconectado");
}

let panels = [];
function render() {
  if (!state.data) return;
  updateHeader();
  panels.forEach(p => p.draw());
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (state.paused) { state.pending = data; return; }
    state.data = data;
    render();
  };
  ws.onclose = () => {
    if (state.data) { state.data.connected = false; render(); }
    setTimeout(connect, 2000);
  };
}

const pauseBtn = document.getElementById("pauseBtn");
function togglePause() {
  state.paused = !state.paused;
  pauseBtn.textContent = state.paused ? "▶" : "⏸";
  pauseBtn.classList.toggle("active", state.paused);
  if (!state.paused && state.pending) {
    state.data = state.pending;
    state.pending = null;
    render();
  }
}
pauseBtn.addEventListener("click", togglePause);
addEventListener("keydown", (e) => {
  if (e.code === "Space" && e.target === document.body) { e.preventDefault(); togglePause(); }
});

/* ------------------------------------------------------------- arranque */
const profilePanel = new Panel("profileCanvas", drawProfile);
const seriesPanel = new Panel("seriesCanvas", drawSeries);
const gammaPanel = new Panel("gammaCanvas", drawGamma);
const magnetPanel = new Panel("magnetCanvas", drawMagnet);
panels = [profilePanel, seriesPanel, gammaPanel, magnetPanel];

attachProfileMouse(profilePanel);
attachSeriesMouse(seriesPanel);
attachBarsMouse(gammaPanel, "gamma", false);
attachBarsMouse(magnetPanel, "magnet", true);

fetch("/api/snapshot").then(r => r.json()).then(d => { state.data = d; render(); });
connect();
