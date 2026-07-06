/* Perfil TPO (Market Profile): cada letra = un periodo tocando ese nivel.
 * A = primer periodo. IB = rango de los dos primeros (initial balance). */
"use strict";

const TpoView = {
  data: null,
  panel: null,
  hoverLevel: null,

  mount(root) {
    root.innerHTML = `
      <div class="fp-wrap">
        <section class="panel">
          <div class="panel-head">
            <h2>Perfil TPO</h2>
            <span class="hint">letras apiladas = aceptación · colas de una letra = rechazo · caja azul = initial balance (2 primeros periodos) · POC ámbar</span>
          </div>
          <canvas id="tpoCanvas"></canvas>
        </section>
      </div>`;
    this.panel = new Panel(root.querySelector("#tpoCanvas"), (c, w, h) => this.draw(c, w, h));
    this.attachMouse();
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.data = null;
    hideTooltip();
  },

  onData(payload) {
    this.data = payload.footprint;
    if (this.panel) this.panel.draw();
  },

  LETTERS: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",

  profile() {
    const bars = this.data.bars;
    const tick = this.data.tick;
    if (!bars.length) return null;
    const levels = new Map();  // nivel → [letras]
    bars.forEach((bar, i) => {
      const letter = this.LETTERS[i % this.LETTERS.length];
      const from = Math.round(bar.low / tick) * tick;
      const to = Math.round(bar.high / tick) * tick;
      for (let level = from; level <= to + 1e-9; level += tick) {
        const key = Math.round(level / tick) * tick;
        const arr = levels.get(key) || [];
        arr.push(letter);
        levels.set(key, arr);
      }
    });
    const sorted = [...levels.entries()].sort((a, b) => b[0] - a[0]); // alto arriba
    let poc = sorted[0][0];
    sorted.forEach(([lvl, letters]) => {
      if (letters.length > levels.get(poc).length) poc = lvl;
    });
    const ibBars = bars.slice(0, Math.min(2, bars.length));
    const ib = { hi: Math.max(...ibBars.map(b => b.high)), lo: Math.min(...ibBars.map(b => b.low)) };
    return { sorted, poc, ib, tick, maxLen: Math.max(...sorted.map(([, l]) => l.length)) };
  },

  PAD: { l: 74, r: 16, t: 14, b: 10 },

  rowGeometry(h, levels) {
    const P = this.PAD;
    const rowH = clamp((h - P.t - P.b) / levels, 8, 34);
    const offset = P.t + Math.max(0, (h - P.t - P.b - rowH * levels) / 2);
    return { rowH, offset };
  },

  draw(ctx, w, h) {
    if (!this.data || !this.data.bars.length) return;
    const p = this.profile();
    if (!p) return;
    const P = this.PAD;
    const { rowH, offset } = this.rowGeometry(h, p.sorted.length);
    const charW = clamp((w - P.l - P.r) / p.maxLen, 7, 22);
    const fontSize = Math.min(rowH - 3, charW + 2, 16);
    const yFor = (i) => offset + i * rowH + rowH / 2;

    // initial balance
    const idxOf = (price) => p.sorted.findIndex(([lvl]) => Math.abs(lvl - price) < p.tick / 2);
    const ibTop = idxOf(Math.round(p.ib.hi / p.tick) * p.tick);
    const ibBot = idxOf(Math.round(p.ib.lo / p.tick) * p.tick);
    if (ibTop >= 0 && ibBot >= 0) {
      ctx.fillStyle = "rgba(93, 179, 217, 0.07)";
      ctx.strokeStyle = "rgba(93, 179, 217, 0.5)";
      const y0 = yFor(ibTop) - rowH / 2, y1 = yFor(ibBot) + rowH / 2;
      ctx.fillRect(P.l - 4, y0, w - P.l - P.r + 8, y1 - y0);
      ctx.strokeRect(P.l - 4, y0, w - P.l - P.r + 8, y1 - y0);
      ctx.font = MONO;
      ctx.fillStyle = "rgba(93, 179, 217, 0.8)";
      ctx.textAlign = "right";
      ctx.fillText("IB", w - P.r, y0 + 12);
    }

    ctx.textAlign = "left";
    p.sorted.forEach(([level, letters], i) => {
      const y = yFor(i);
      const isPoc = Math.abs(level - p.poc) < p.tick / 2;
      const hot = this.hoverLevel !== null && Math.abs(level - this.hoverLevel) < p.tick / 2;
      ctx.font = MONO;
      ctx.textAlign = "right";
      ctx.fillStyle = isPoc ? COLORS.accent : hot ? COLORS.text : COLORS.dim;
      ctx.fillText(level.toFixed(p.tick < 1 ? 2 : 0), P.l - 8, y + 3.5);
      ctx.textAlign = "left";
      ctx.font = `${isPoc || hot ? "700 " : ""}${fontSize}px ` + css("--mono");
      letters.forEach((letter, li) => {
        // color por tercio de la sesión: apertura fría → cierre cálido
        const phase = this.LETTERS.indexOf(letter) / Math.max(1, this.data.bars.length - 1);
        ctx.fillStyle = isPoc ? COLORS.accent
          : phase < 0.34 ? "rgba(93,179,217,0.9)"
          : phase < 0.67 ? "rgba(215,222,232,0.75)"
          : "rgba(232,184,75,0.85)";
        ctx.fillText(letter, P.l + li * charW, y + fontSize / 2 - 1);
      });
    });
  },

  attachMouse() {
    const canvas = this.panel.canvas;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.data || !this.data.bars.length) return;
      const p = this.profile();
      if (!p) return;
      const { rowH, offset } = this.rowGeometry(this.panel.h, p.sorted.length);
      const i = clamp(Math.floor((e.offsetY - offset) / rowH), 0, p.sorted.length - 1);
      const [level, letters] = p.sorted[i];
      this.hoverLevel = level;
      const firstBar = this.data.bars[this.LETTERS.indexOf(letters[0])];
      showTooltip(
        `<div class="tt-title">${level.toFixed(2)}</div>` +
        `<div>${letters.length} periodos: ${letters.join("")}</div>` +
        `<div class="tt-dim">primer toque ${firstBar ? firstBar.t : "—"}` +
        (Math.abs(level - p.poc) < p.tick / 2 ? " · POC" : "") + `</div>`,
        e.clientX, e.clientY);
      this.panel.draw();
    });
    canvas.addEventListener("pointerleave", () => {
      this.hoverLevel = null;
      hideTooltip();
      this.panel.draw();
    });
  },
};
