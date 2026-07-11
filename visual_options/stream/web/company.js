/* Empresa: ficha estilo Bloomberg (DES + ERN + ANR + N) con datos de
 * Yahoo y el checklist del libro auto-evaluado. */
"use strict";

const CompanyView = {
  mount(root) {
    root.innerHTML = `
      <div class="co-wrap">
        <section class="panel co-profile">
          <div class="panel-head"><h2>Ficha</h2><span class="hint">DES</span>
            <div class="dealer-totals" id="coMeta"></div></div>
          <div class="co-body" id="coProfile"><div class="scan-empty">descargando ficha…</div></div>
        </section>
        <section class="panel co-earnings">
          <div class="panel-head"><h2>Earnings</h2><span class="hint">ERN · sorpresas EPS</span></div>
          <div class="co-body" id="coEarnings"></div>
        </section>
        <section class="panel co-analysts">
          <div class="panel-head"><h2>Analistas</h2><span class="hint">ANR · recomendaciones y objetivos</span></div>
          <div class="co-body" id="coAnalysts"></div>
        </section>
        <section class="panel co-news">
          <div class="panel-head"><h2>Noticias</h2><span class="hint">N · titulares recientes</span></div>
          <div class="co-body" id="coNews"></div>
        </section>
        <section class="panel co-check">
          <div class="panel-head"><h2>Checklist del libro</h2>
            <span class="hint">criterios del Cap. 2/7 evaluados con estos datos</span></div>
          <div class="co-body" id="coCheck"></div>
        </section>
      </div>`;
    this.el = {
      meta: root.querySelector("#coMeta"), profile: root.querySelector("#coProfile"),
      earnings: root.querySelector("#coEarnings"), analysts: root.querySelector("#coAnalysts"),
      news: root.querySelector("#coNews"), check: root.querySelector("#coCheck"),
    };
    this.load();
  },

  unmount() { this.el = null; },
  onData() {},  // ficha estática con caché de 10 min, no sigue el stream

  fmtBig(v) {
    if (v == null) return "—";
    if (v >= 1e12) return (v / 1e12).toFixed(2) + "B$";   // billones (es)
    if (v >= 1e9) return (v / 1e9).toFixed(2) + "mM$";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M$";
    return v.toLocaleString();
  },

  async load() {
    const symbol = localStorage.getItem("vo-symbol") || "QQQ";
    try {
      const response = await fetch(`/api/company?symbol=${encodeURIComponent(symbol)}`);
      if (!response.ok) throw new Error((await response.json()).detail);
      this.render(await response.json());
    } catch (err) {
      if (this.el) this.el.profile.innerHTML = `<div class="scan-empty">error: ${err.message}</div>`;
    }
  },

  render(d) {
    if (!this.el) return;
    const m = d.metrics, p = d.profile;
    this.el.meta.innerHTML =
      `<span class="dtotal">${d.symbol}</span>` +
      (m.price ? `<span class="dtotal">${m.price.toFixed(2)}</span>` : "") +
      `<span class="dtotal">${d.as_of}</span>`;

    // --- ficha DES
    const tile = (label, value, cls = "") =>
      `<div class="vtile ${cls}"><span>${label}</span><b>${value}</b></div>`;
    const pct = (v, dec = 1) => v == null ? "—" : (v * 100).toFixed(dec) + "%";
    let range52 = "—";
    if (m.low52 && m.high52) {
      const pos = Math.round((m.pos52 ?? 0) * 100);
      range52 = `<div class="co-range"><i style="left:${pos}%"></i></div>
                 <small>${m.low52.toFixed(0)} — ${m.high52.toFixed(0)} (${pos}%)</small>`;
    }
    this.el.profile.innerHTML = `
      <div class="co-name"><b>${p.name || d.symbol}</b>
        <span>${[p.sector, p.industry].filter(Boolean).join(" · ")}</span></div>
      ${p.summary ? `<p class="co-summary">${p.summary}…</p>` : ""}
      <div class="vwap-tiles co-tiles">
        ${tile("Market cap", this.fmtBig(m.market_cap))}
        ${tile("P/E ttm", m.trailing_pe ? m.trailing_pe.toFixed(1) : "—")}
        ${tile("P/E fwd", m.forward_pe ? m.forward_pe.toFixed(1) : "—")}
        ${tile("Beta", m.beta ? m.beta.toFixed(2) : "—")}
        ${tile("EPS ttm", m.eps_ttm ? m.eps_ttm.toFixed(2) : "—")}
        ${tile("Dividendo", m.dividend_yield
          ? (m.dividend_yield < 0.03 ? (m.dividend_yield * 100).toFixed(2) : m.dividend_yield.toFixed(2)) + "%"
          : "—")}
        ${tile("Short ratio", m.short_ratio ? m.short_ratio.toFixed(1) + "d" : "—")}
        ${tile("Vol. medio", m.avg_volume ? fmtK(m.avg_volume) : "—")}
      </div>
      <div class="vtile"><span>Rango 52 semanas</span>${range52}</div>`;

    // --- earnings ERN
    const e = d.earnings;
    let earnHtml = "";
    if (e.next_date) {
      const est = [];
      if (e.next_eps_est != null) est.push(`EPS est. ${e.next_eps_est.toFixed(2)}`);
      if (e.next_revenue_est != null) est.push(`revenue est. ${this.fmtBig(e.next_revenue_est)}`);
      earnHtml += `<div class="vtile pos"><span>Próximo earnings</span>
        <b>${e.next_date.slice(0, 10)} · en ${Math.round(e.days_to_next)} días</b>
        <i>${est.join(" · ") || ""}${est.length ? " — " : ""}revisa el checklist del Cap. 7 antes</i></div>`;
    } else {
      earnHtml += `<div class="vtile"><span>Próximo earnings</span><b>sin fecha</b>
        <i>índices y ETFs no reportan</i></div>`;
    }
    if (e.history.length) {
      const maxAbs = Math.max(...e.history.map(h => Math.abs(h.surprise ?? 0)), 1);
      earnHtml += `<table class="scan-table"><thead><tr>
        <th>Fecha</th><th>EPS est.</th><th>EPS real</th><th>Sorpresa</th><th></th></tr></thead><tbody>` +
        e.history.map(h => {
          const s = h.surprise;
          const bw = s == null ? 0 : Math.round(Math.abs(s) / maxAbs * 50);
          return `<tr>
            <td>${h.date}</td>
            <td>${h.estimate?.toFixed(2) ?? "—"}</td>
            <td>${h.reported?.toFixed(2) ?? "—"}</td>
            <td class="${s > 0 ? "pos" : s < 0 ? "neg" : ""}">${s == null ? "—" : (s > 0 ? "+" : "") + s.toFixed(1) + "%"}</td>
            <td><div class="co-sbar ${s >= 0 ? "pos" : "neg"}" style="width:${bw}px"></div></td>
          </tr>`;
        }).join("") + "</tbody></table>";
    }
    this.el.earnings.innerHTML = earnHtml;

    // --- analistas ANR
    const a = d.analysts;
    let anHtml = "";
    if (a.counts) {
      const order = [["strongBuy", "S.Buy", "#2fa463"], ["buy", "Buy", "#6fbf73"],
                     ["hold", "Hold", "#7c8798"], ["sell", "Sell", "#d98550"],
                     ["strongSell", "S.Sell", "#e0433f"]];
      anHtml += `<div class="co-ratings">` + order.map(([key, label, color]) => {
        const n = a.counts[key];
        const w = a.total ? (n / a.total * 100) : 0;
        return n ? `<div style="width:${w}%;background:${color}" title="${label}: ${n}">${n}</div>` : "";
      }).join("") + `</div>
      <small class="tt-dim">${a.total} analistas · ${a.bullish_pct}% alcistas</small>`;
    } else {
      anHtml += `<div class="scan-empty">sin cobertura de analistas (¿ETF/índice?)</div>`;
    }
    if (a.targets) {
      const t = a.targets, price = m.price;
      const lo = Math.min(t.low, price ?? t.low), hi = Math.max(t.high, price ?? t.high);
      const posOf = (v) => Math.round((v - lo) / Math.max(hi - lo, 1e-9) * 100);
      anHtml += `<div class="vtile" style="margin-top:.6rem"><span>Price targets</span>
        <div class="co-range co-targets">
          ${price ? `<i class="spot" style="left:${posOf(price)}%" title="precio ${price.toFixed(2)}"></i>` : ""}
          <i class="tgt" style="left:${posOf(t.mean)}%" title="objetivo medio ${t.mean.toFixed(2)}"></i>
        </div>
        <small>low ${t.low?.toFixed(2)} · medio ${t.mean?.toFixed(2)} · high ${t.high?.toFixed(2)}
        ${a.target_upside_pct != null ? `· <b class="${a.target_upside_pct >= 0 ? "pos" : "neg"}">${a.target_upside_pct > 0 ? "+" : ""}${a.target_upside_pct}% al medio</b>` : ""}</small></div>`;
    }
    this.el.analysts.innerHTML = anHtml;

    // --- noticias N
    this.el.news.innerHTML = d.news.length
      ? d.news.map(n => `
        <a class="co-newsitem" href="${n.url}" target="_blank" rel="noopener">
          <span class="co-newstitle">${n.title}</span>
          <span class="co-newsmeta">${[n.publisher, n.when].filter(Boolean).join(" · ")}</span>
        </a>`).join("")
      : `<div class="scan-empty">sin titulares</div>`;

    // --- checklist del libro
    this.el.check.innerHTML = d.book_checklist.map(c => `
      <div class="stat-card ${c.verdict}">
        <div class="st-head"><b>${c.name}</b>
          <span class="st-verdict">${c.verdict === "ok" ? "✓" : c.verdict === "warn" ? "△" : "✗"}</span></div>
        <p class="st-result">${c.value}</p>
      </div>`).join("");
  },
};
