/* Vista de niveles clave: nota auto-generada (Founder's Note-like) con
 * call wall, put wall, gamma flip, imán y movimiento esperado, más una
 * escalera visual de niveles alrededor del spot. */
"use strict";

const LevelsView = {
  data: null,
  panel: null,

  mount(root) {
    root.innerHTML = `
      <div class="levels-wrap">
        <section class="panel levels-note">
          <div class="panel-head"><h2>Nota de niveles clave</h2>
            <span class="hint">generada en vivo desde GEX, OI e IV</span></div>
          <div class="note-body" id="noteBody">esperando datos…</div>
        </section>
        <section class="panel levels-ladder">
          <div class="panel-head"><h2>Escalera de niveles</h2></div>
          <canvas id="levelsCanvas"></canvas>
        </section>
      </div>`;
    this.noteEl = root.querySelector("#noteBody");
    this.panel = new Panel(root.querySelector("#levelsCanvas"), (c, w, h) => this.draw(c, w, h));
  },

  unmount() {
    if (this.panel) this.panel.destroy();
    this.panel = null;
    this.data = null;
  },

  onData(payload) {
    this.data = payload.flow;
    this.renderNote();
    if (this.panel) this.panel.draw();
  },

  computeLevels() {
    const d = this.data;
    const rows = d.strikes;
    if (!rows.length) return null;
    const callWall = rows.reduce((a, b) => (b.net_gex > a.net_gex ? b : a));
    const putWall = rows.reduce((a, b) => (b.net_gex < a.net_gex ? b : a));
    const magnet = rows.reduce((a, b) => (b.magnet > a.magnet ? b : a));
    const atm = rows.reduce((a, b) =>
      Math.abs(b.strike - d.spot) < Math.abs(a.strike - d.spot) ? b : a);
    const em = d.spot * (atm.iv || 0.2) * Math.sqrt(Math.max(d.expiry_days, 0.25) / 365);
    const totalGex = rows.reduce((acc, r) => acc + r.net_gex, 0);
    return { callWall, putWall, magnet, atm, em, totalGex };
  },

  renderNote() {
    const d = this.data;
    const L = this.computeLevels();
    if (!L) return;
    const regime = L.totalGex >= 0
      ? `<b class="pos">gamma positiva</b> (los dealers amortiguan: rangos, reversión a la media)`
      : `<b class="neg">gamma negativa</b> (los dealers aceleran: movimientos amplios, cuidado con perseguir)`;
    const flipTxt = d.gamma_flip
      ? `El <b>gamma flip</b> está en <b>${d.gamma_flip.toFixed(1)}</b> — ${d.spot > d.gamma_flip
          ? "el precio opera POR ENCIMA (régimen estable mientras aguante)"
          : "el precio opera POR DEBAJO (régimen inestable, movimientos exagerados)"}.`
      : "Sin cruce de gamma en el rango visible.";
    const dir = d.put_sell_pct - d.call_sell_pct;
    const flowTxt = dir > 3
      ? "el flujo vende puts con más agresividad que calls (presión alcista)"
      : dir < -3
        ? "el flujo vende calls con más agresividad que puts (presión bajista/techo)"
        : "el flujo está equilibrado";
    this.noteEl.innerHTML = `
      <p><b>${d.symbol}</b> a <b>${d.spot.toFixed(2)}</b> · sesión en ${regime} (Σ GEX ${L.totalGex >= 0 ? "+" : ""}${L.totalGex.toFixed(0)}M).</p>
      <p>${flipTxt}</p>
      <p>Resistencia por gamma (<b>call wall</b>): <b>${L.callWall.strike}</b> con ${L.callWall.net_gex.toFixed(0)}M.
         Soporte por gamma (<b>put wall</b>): <b>${L.putWall.strike}</b> con ${L.putWall.net_gex.toFixed(0)}M.
         Imán de OI/mariposas: <b>${L.magnet.strike}</b>.</p>
      <p>Movimiento esperado ±1σ a ${d.expiry_days.toFixed(1)} días (IV ATM ${(L.atm.iv * 100).toFixed(1)}%):
         <b>±${L.em.toFixed(2)}</b> → rango ${(d.spot - L.em).toFixed(2)} / ${(d.spot + L.em).toFixed(2)}.</p>
      <p>Lectura del flujo: ${flowTxt} (put sell ${d.put_sell_pct.toFixed(1)} · call sell ${d.call_sell_pct.toFixed(1)}).</p>`;
  },

  draw(ctx, w, h) {
    if (!this.data) return;
    const d = this.data;
    const L = this.computeLevels();
    if (!L) return;
    const levels = [
      { price: L.callWall.strike, label: "call wall", color: COLORS.bought },
      { price: d.spot + L.em, label: "+1σ", color: COLORS.dim },
      { price: L.magnet.strike, label: "imán", color: COLORS.accent },
      { price: d.spot, label: "spot", color: COLORS.price },
      ...(d.gamma_flip ? [{ price: d.gamma_flip, label: "γ-flip", color: "#c65dd9" }] : []),
      { price: d.spot - L.em, label: "−1σ", color: COLORS.dim },
      { price: L.putWall.strike, label: "put wall", color: COLORS.sold },
    ];
    const prices = levels.map(l => l.price);
    const hi = Math.max(...prices), lo = Math.min(...prices);
    const pad = (hi - lo) * 0.08 + 0.01;
    const yFor = (p) => 24 + (1 - (p - lo + pad) / (hi - lo + 2 * pad)) * (h - 48);

    // eje vertical
    ctx.strokeStyle = COLORS.border;
    ctx.beginPath(); ctx.moveTo(w * 0.32, 12); ctx.lineTo(w * 0.32, h - 12); ctx.stroke();

    ctx.font = MONO;
    [...levels].sort((a, b) => b.price - a.price).forEach(level => {
      const y = yFor(level.price);
      ctx.strokeStyle = level.color;
      ctx.setLineDash(level.label === "spot" ? [] : [5, 4]);
      ctx.beginPath(); ctx.moveTo(w * 0.32, y); ctx.lineTo(w - 14, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = level.color;
      ctx.textAlign = "right";
      ctx.fillText(level.price.toFixed(2), w * 0.32 - 8, y + 3.5);
      ctx.textAlign = "left";
      ctx.fillText(level.label, w * 0.32 + 10, y - 4);
    });
  },
};
