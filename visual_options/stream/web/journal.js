/* Diario de trading: notas rápidas con hora, símbolo y precio capturados
 * automáticamente. Se guarda en localStorage de este navegador. */
"use strict";

const JournalView = {
  flow: null,

  mount(root) {
    root.innerHTML = `
      <div class="journal-wrap">
        <section class="panel">
          <div class="panel-head"><h2>Nueva nota</h2>
            <span class="hint">la hora, el símbolo y el precio se guardan solos · Ctrl+Enter para guardar</span></div>
          <div class="journal-form">
            <textarea id="jText" rows="4" placeholder="¿Por qué entras/sales? ¿Qué ves en el flujo, el footprint, los niveles…?"></textarea>
            <div class="journal-actions">
              <span class="tt-dim" id="jCtx"></span>
              <button id="jSave" class="btn btn-primary">Guardar nota</button>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Notas</h2>
            <button id="jExport" class="btn" style="margin-left:auto" title="copiar todo al portapapeles">copiar</button>
            <button id="jClear" class="btn" title="borrar todas">borrar todo</button></div>
          <div class="journal-list" id="jList"></div>
        </section>
      </div>`;
    this.el = {
      text: root.querySelector("#jText"), ctx: root.querySelector("#jCtx"),
      list: root.querySelector("#jList"),
    };
    root.querySelector("#jSave").addEventListener("click", () => this.save());
    root.querySelector("#jClear").addEventListener("click", () => {
      if (confirm("¿Borrar todas las notas del diario?")) {
        localStorage.removeItem("vo-journal");
        this.render();
      }
    });
    root.querySelector("#jExport").addEventListener("click", () => {
      const text = this.load().map(n =>
        `[${n.date} ${n.t}] ${n.symbol} @ ${n.spot} — ${n.text}`).join("\n");
      navigator.clipboard.writeText(text);
    });
    this.el.text.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) this.save();
    });
    this.render();
    this.el.text.focus();
  },

  unmount() { this.el = null; },

  onData(payload) {
    this.flow = payload.flow;
    if (this.el) {
      this.el.ctx.textContent =
        `${this.flow.symbol} @ ${this.flow.spot.toFixed(2)} · ${this.flow.timestamp}`;
    }
  },

  load() { return JSON.parse(localStorage.getItem("vo-journal") || "[]"); },

  save() {
    const text = this.el.text.value.trim();
    if (!text) return;
    const notes = this.load();
    notes.unshift({
      date: new Date().toLocaleDateString("es"),
      t: this.flow ? this.flow.timestamp : new Date().toLocaleTimeString("es"),
      symbol: this.flow ? this.flow.symbol : (localStorage.getItem("vo-symbol") || "—"),
      spot: this.flow ? this.flow.spot.toFixed(2) : "—",
      text,
    });
    localStorage.setItem("vo-journal", JSON.stringify(notes.slice(0, 500)));
    this.el.text.value = "";
    this.render();
  },

  render() {
    if (!this.el) return;
    const notes = this.load();
    this.el.list.innerHTML = notes.map((n, i) => `
      <div class="journal-note">
        <div class="jn-head">
          <b>${n.symbol}</b><span>@ ${n.spot}</span><i>${n.date} ${n.t}</i>
          <button class="btn" data-del="${i}" title="borrar">✕</button>
        </div>
        <p>${n.text.replace(/</g, "&lt;").replace(/\n/g, "<br>")}</p>
      </div>`).join("") || `<div class="scan-empty">sin notas — escribe la primera arriba</div>`;
    this.el.list.querySelectorAll("[data-del]").forEach(btn =>
      btn.addEventListener("click", () => {
        const notes = this.load();
        notes.splice(Number(btn.dataset.del), 1);
        localStorage.setItem("vo-journal", JSON.stringify(notes));
        this.render();
      }));
  },
};
