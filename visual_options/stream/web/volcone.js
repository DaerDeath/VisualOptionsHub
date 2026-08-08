/* Cono de volatilidad (VC): rango histórico (min/p25/mediana/p75/max) de
 * la vol realizada por ventana, con el valor actual marcado — ¿la IV de
 * hoy está cara o barata frente a su propio historial? */
"use strict";

const VolConeView = {
  panel: null,
  result: null,
  hover: -1,

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Cono de volatilidad</h2>
            <span class="hint">caja = rango histórico p25–p75 · barra = min–max · punto ámbar = vol realizada actual · percentil sobre 2 años</span>
            <div class="dealer-totals" id="vcTotals"></div>
          </div>
          <canvas id="vcCanvas"></canvas>
        </section>
      </div>`;
    this.totalsEl = root.querySelector("#vcTotals");
    this.panel = new Panel(root.querySelector("#vcCanvas"), (c, w, h) => this.draw(c, w, h));
    this.attachMouse();
    this.load();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.result = null;
  },

  onData() {},

  async load() {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    this.totalsEl.innerHTML = `<span class="dtotal">cargando ${symbol}…</span>`;
    try {
      const response = await fetch(`/api/vol-cone?symbol=${encodeURIComponent(symbol)}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.result = await response.json();
      const last = this.result.cones[this.result.cones.length - 1];
      this.totalsEl.innerHTML =
        `<span class="dtotal">${this.result.symbol}</span>` +
        `<span class="dtotal ${last.percentile >= 50 ? "neg" : "pos"}">${last.window}d: percentil ${last.percentile}</span>`;
      this.panel.draw();
    } catch (err) {
      this.totalsEl.innerHTML = `<span class="dtotal neg">error: ${err.message}</span>`;
    }
  },

  PAD: { l: 54, r: 16, t: 16, b: 34 },

  draw(ctx, w, h) {
    const r = this.result;
    if (!r || !r.cones.length) return;
    const P = this.PAD;
    const cones = r.cones;
    const vMax = Math.max(...cones.map(c => c.max)) * 1.08;
    const vMin = Math.min(...cones.map(c => c.min)) * 0.9;
    const colW = (w - P.l - P.r) / cones.length;
    const y = (v) => P.t + (1 - (v - vMin) / (vMax - vMin)) * (h - P.t - P.b);

    ctx.font = MONO;
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = "left";
    for (let g = 0; g <= 4; g++) {
      const v = vMin + ((vMax - vMin) / 4) * g;
      const yy = y(v);
      ctx.strokeStyle = COLORS.border;
      ctx.globalAlpha = 0.4;
      ctx.beginPath(); ctx.moveTo(P.l, yy); ctx.lineTo(w - P.r, yy); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText((v * 100).toFixed(0) + "%", 4, yy + 3);
    }

    cones.forEach((c, i) => {
      const cx = P.l + i * colW + colW / 2;
      const hot = this.hover === i;
      const boxW = colW * 0.4;

      ctx.strokeStyle = COLORS.dim;
      ctx.beginPath(); ctx.moveTo(cx, y(c.max)); ctx.lineTo(cx, y(c.min)); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx - boxW * 0.25, y(c.max)); ctx.lineTo(cx + boxW * 0.25, y(c.max)); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx - boxW * 0.25, y(c.min)); ctx.lineTo(cx + boxW * 0.25, y(c.min)); ctx.stroke();

      ctx.fillStyle = hot ? "rgba(93,179,217,0.35)" : "rgba(93,179,217,0.18)";
      ctx.fillRect(cx - boxW / 2, y(c.p75), boxW, y(c.p25) - y(c.p75));
      ctx.strokeStyle = COLORS.call;
      ctx.strokeRect(cx - boxW / 2, y(c.p75), boxW, y(c.p25) - y(c.p75));

      ctx.strokeStyle = COLORS.text;
      ctx.beginPath(); ctx.moveTo(cx - boxW / 2, y(c.median)); ctx.lineTo(cx + boxW / 2, y(c.median)); ctx.stroke();

      ctx.beginPath();
      ctx.arc(cx, y(c.current), hot ? 6 : 4.2, 0, Math.PI * 2);
      ctx.fillStyle = c.percentile >= 50 ? COLORS.sold : COLORS.bought;
      ctx.fill();
      ctx.strokeStyle = COLORS.accent;
      ctx.lineWidth = hot ? 2 : 1;
      ctx.stroke();
      ctx.lineWidth = 1;

      ctx.textAlign = "center";
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(`${c.window}d`, cx, h - P.b + 16);
      ctx.fillText(`p${c.percentile}`, cx, h - P.b + 28);
    });
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.result) return;
      const cones = this.result.cones;
      const P = this.PAD;
      const colW = (this.panel.w - P.l - P.r) / cones.length;
      const i = clamp(Math.floor((e.offsetX - P.l) / colW), 0, cones.length - 1);
      this.hover = i;
      const c = cones[i];
      showTooltip(
        `<div class="tt-title">Ventana ${c.window}d</div>` +
        `<div>actual ${(c.current * 100).toFixed(2)}% (percentil ${c.percentile})</div>` +
        `<div class="tt-dim">p25 ${(c.p25 * 100).toFixed(1)}% · mediana ${(c.median * 100).toFixed(1)}% · p75 ${(c.p75 * 100).toFixed(1)}%</div>` +
        `<div class="tt-dim">min ${(c.min * 100).toFixed(1)}% · max ${(c.max * 100).toFixed(1)}%</div>`,
        e.clientX, e.clientY);
      this.panel.draw();
    });
    canvas.addEventListener("pointerleave", () => {
      this.hover = -1;
      hideTooltip();
      this.panel.draw();
    });
  },
};
