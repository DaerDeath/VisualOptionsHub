/* Utilidades compartidas: tokens de color, canvas con DPR, tooltip y WebSocket. */
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

const fmtK = (n) => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : String(n);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/* Canvas con escala DPR y redibujado al redimensionar. */
class Panel {
  constructor(canvas, drawFn) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.drawFn = drawFn;
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(canvas);
    this.resize();
  }
  resize() {
    const dpr = window.devicePixelRatio || 1;
    const { clientWidth: w, clientHeight: h } = this.canvas;
    if (!w || !h) return;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = w; this.h = h;
    this.draw();
  }
  draw() {
    if (!this.w) return;
    this.ctx.clearRect(0, 0, this.w, this.h);
    this.drawFn(this.ctx, this.w, this.h);
  }
  destroy() { this.observer.disconnect(); }
}

/* Tooltip flotante global. */
const tooltipEl = document.getElementById("tooltip");
function showTooltip(html, clientX, clientY) {
  tooltipEl.innerHTML = html;
  tooltipEl.hidden = false;
  const pad = 14;
  const rect = tooltipEl.getBoundingClientRect();
  let x = clientX + pad, y = clientY + pad;
  if (x + rect.width > innerWidth - 8) x = clientX - rect.width - pad;
  if (y + rect.height > innerHeight - 8) y = clientY - rect.height - pad;
  tooltipEl.style.left = x + "px";
  tooltipEl.style.top = y + "px";
}
function hideTooltip() { tooltipEl.hidden = true; }

/* Viewport de barras con pan + zoom para gráficos temporales.
 * rueda = zoom anclado al cursor · arrastrar = pan · doble clic = reset. */
class BarViewport {
  constructor(redraw) {
    this.start = null;   // null = pegado al final (siguiendo el directo)
    this.count = null;   // null = nº de barras por defecto
    this.redraw = redraw;
    this.dragging = false;
  }
  view(total, defaultCount) {
    let count = Math.round(clamp(this.count ?? Math.min(total, defaultCount), 3, Math.max(3, total)));
    let start = this.start ?? (total - count);
    start = Math.round(clamp(start, 0, Math.max(0, total - count)));
    return { start, count, end: start + count };
  }
  zoom(factor, anchorFrac, total, defaultCount) {
    const v = this.view(total, defaultCount);
    const anchorBar = v.start + anchorFrac * v.count;
    this.count = clamp(v.count * factor, 3, total);
    this.start = anchorBar - anchorFrac * this.count;
    this.redraw();
  }
  pan(deltaBars, total, defaultCount) {
    const v = this.view(total, defaultCount);
    this.start = clamp(v.start + deltaBars, 0, Math.max(0, total - v.count));
    this.count = v.count;
    this.redraw();
  }
  reset() {
    this.start = null;
    this.count = null;
    this.redraw();
  }
  /* opts: { total(), defaultCount(), plot() → [xIzq, ancho] } */
  attach(canvas, opts) {
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const [left, width] = opts.plot();
      const frac = clamp((e.offsetX - left) / Math.max(1, width), 0, 1);
      this.zoom(e.deltaY > 0 ? 1.18 : 1 / 1.18, frac, opts.total(), opts.defaultCount());
    }, { passive: false });

    let lastX = null, accum = 0;
    canvas.addEventListener("pointerdown", (e) => {
      lastX = e.clientX;
      accum = 0;
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointermove", (e) => {
      if (lastX === null) return;
      const [, width] = opts.plot();
      const v = this.view(opts.total(), opts.defaultCount());
      accum += Math.abs(e.clientX - lastX);
      if (accum > 4) this.dragging = true;   // distinguir clic de arrastre
      this.pan(-(e.clientX - lastX) * v.count / Math.max(1, width), opts.total(), opts.defaultCount());
      lastX = e.clientX;
    });
    const stop = () => { lastX = null; setTimeout(() => { this.dragging = false; }, 0); };
    canvas.addEventListener("pointerup", stop);
    canvas.addEventListener("pointercancel", stop);
    canvas.addEventListener("dblclick", () => this.reset());
  }
}

const ZOOM_HINT = "rueda = zoom · arrastra = mover · doble clic = reset";

/* Cliente WebSocket por símbolo + fuente de datos, con reconexión. */
class StreamClient {
  constructor(symbol, onData, source, expiry) {
    this.symbol = symbol;
    this.source = source || "";
    this.expiry = expiry || 0;
    this.onData = onData;
    this.closed = false;
    this.connect();
  }
  connect() {
    if (this.closed) return;
    const src = this.source ? `&source=${encodeURIComponent(this.source)}` : "";
    this.ws = new WebSocket(`ws://${location.host}/ws?symbol=${encodeURIComponent(this.symbol)}${src}&expiry=${this.expiry}`);
    this.ws.onmessage = (ev) => this.onData(JSON.parse(ev.data));
    this.ws.onclose = () => { if (!this.closed) setTimeout(() => this.connect(), 2000); };
  }
  close() {
    this.closed = true;
    try { this.ws.close(); } catch (_) { /* ya cerrado */ }
  }
}

/* Símbolos de las watchlists reales de Tradier, unidas y sin duplicados —
 * para que Screener/Scanner puedan partir de lo que el usuario ya sigue
 * en su broker en vez de una lista genérica. Lanza si no hay watchlists
 * o si falla la llamada (sin token, cuenta sin watchlists, etc.). */
async function fetchTradierWatchlistSymbols() {
  const response = await fetch("/api/watchlists?source=tradier");
  if (!response.ok) throw new Error((await response.json()).detail);
  const data = await response.json();
  if (!data.symbols.length) throw new Error("no hay símbolos en tus watchlists de Tradier");
  return data.symbols.join(",");
}
