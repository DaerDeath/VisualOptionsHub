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

/* Cliente WebSocket por símbolo con reconexión. */
class StreamClient {
  constructor(symbol, onData) {
    this.symbol = symbol;
    this.onData = onData;
    this.closed = false;
    this.connect();
  }
  connect() {
    if (this.closed) return;
    this.ws = new WebSocket(`ws://${location.host}/ws?symbol=${encodeURIComponent(this.symbol)}`);
    this.ws.onmessage = (ev) => this.onData(JSON.parse(ev.data));
    this.ws.onclose = () => { if (!this.closed) setTimeout(() => this.connect(), 2000); };
  }
  close() {
    this.closed = true;
    try { this.ws.close(); } catch (_) { /* ya cerrado */ }
  }
}
