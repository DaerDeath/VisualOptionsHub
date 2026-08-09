/* Catálogo de símbolos + buscador con autocompletado.
 *
 * attachSymbolPicker(input, {onPick, onEnter}) monta un desplegable bajo
 * el input: filtra por ticker (prefijo primero) y por nombre de empresa,
 * navegable con ↑/↓ + Enter, clic para elegir, Esc cierra.
 */
"use strict";

const SYMBOL_CATALOG = [
  // índices y volatilidad
  ["SPX", "S&P 500 Index"], ["NDX", "Nasdaq 100 Index"], ["RUT", "Russell 2000 Index"],
  ["VIX", "CBOE Volatility Index"],
  // ETFs
  ["SPY", "SPDR S&P 500 ETF"], ["QQQ", "Invesco Nasdaq 100 ETF"], ["IWM", "iShares Russell 2000 ETF"],
  ["DIA", "SPDR Dow Jones ETF"], ["VTI", "Vanguard Total Market ETF"], ["VOO", "Vanguard S&P 500 ETF"],
  ["TQQQ", "ProShares UltraPro QQQ 3x"], ["SQQQ", "ProShares UltraPro Short QQQ 3x"],
  ["XLF", "Financial Select SPDR"], ["XLE", "Energy Select SPDR"], ["XLK", "Technology Select SPDR"],
  ["XLV", "Health Care Select SPDR"], ["XLI", "Industrial Select SPDR"], ["XLY", "Consumer Discretionary SPDR"],
  ["XLP", "Consumer Staples SPDR"], ["XLU", "Utilities Select SPDR"], ["XLB", "Materials Select SPDR"],
  ["XLRE", "Real Estate Select SPDR"], ["XBI", "SPDR S&P Biotech ETF"],
  ["SMH", "VanEck Semiconductor ETF"], ["SOXX", "iShares Semiconductor ETF"],
  ["SOXL", "Direxion Semis Bull 3x"], ["SOXS", "Direxion Semis Bear 3x"],
  ["ARKK", "ARK Innovation ETF"], ["TLT", "iShares 20+ Year Treasury"], ["HYG", "iShares High Yield Bond"],
  ["GLD", "SPDR Gold Shares"], ["SLV", "iShares Silver Trust"], ["USO", "United States Oil Fund"],
  ["UNG", "US Natural Gas Fund"], ["GDX", "VanEck Gold Miners ETF"], ["GDXJ", "VanEck Junior Gold Miners"],
  ["EEM", "iShares Emerging Markets"], ["EFA", "iShares EAFE"], ["FXI", "iShares China Large-Cap"],
  ["EWZ", "iShares Brazil ETF"], ["KWEB", "KraneShares China Internet"],
  ["UVXY", "ProShares Ultra VIX Futures"], ["SVXY", "ProShares Short VIX Futures"],
  ["IBIT", "iShares Bitcoin Trust"], ["BITO", "ProShares Bitcoin Strategy"],
  // mega caps / tech
  ["AAPL", "Apple"], ["MSFT", "Microsoft"], ["NVDA", "NVIDIA"], ["AMZN", "Amazon"],
  ["GOOGL", "Alphabet Class A"], ["GOOG", "Alphabet Class C"], ["META", "Meta Platforms"],
  ["TSLA", "Tesla"], ["AVGO", "Broadcom"], ["ORCL", "Oracle"], ["NFLX", "Netflix"],
  ["CRM", "Salesforce"], ["AMD", "Advanced Micro Devices"], ["ADBE", "Adobe"],
  ["QCOM", "Qualcomm"], ["TXN", "Texas Instruments"], ["INTU", "Intuit"], ["IBM", "IBM"],
  ["NOW", "ServiceNow"], ["CSCO", "Cisco Systems"], ["ACN", "Accenture"], ["INTC", "Intel"],
  ["MU", "Micron Technology"], ["LRCX", "Lam Research"], ["AMAT", "Applied Materials"],
  ["KLAC", "KLA Corporation"], ["ADI", "Analog Devices"], ["SNPS", "Synopsys"], ["CDNS", "Cadence Design"],
  ["PANW", "Palo Alto Networks"], ["CRWD", "CrowdStrike"], ["ZS", "Zscaler"], ["NET", "Cloudflare"],
  ["DDOG", "Datadog"], ["MDB", "MongoDB"], ["SNOW", "Snowflake"], ["PLTR", "Palantir"],
  ["OKTA", "Okta"], ["TEAM", "Atlassian"], ["WDAY", "Workday"], ["VEEV", "Veeva Systems"],
  ["DOCU", "DocuSign"], ["ZM", "Zoom Video"], ["SPOT", "Spotify"], ["SHOP", "Shopify"],
  ["UBER", "Uber Technologies"], ["LYFT", "Lyft"], ["ABNB", "Airbnb"], ["DASH", "DoorDash"],
  ["PINS", "Pinterest"], ["SNAP", "Snap"], ["RDDT", "Reddit"],
  ["TSM", "Taiwan Semiconductor"], ["ASML", "ASML Holding"], ["ARM", "Arm Holdings"],
  ["SMCI", "Super Micro Computer"], ["DELL", "Dell Technologies"], ["HPQ", "HP Inc"],
  ["ANET", "Arista Networks"], ["MRVL", "Marvell Technology"], ["ON", "ON Semiconductor"],
  ["NXPI", "NXP Semiconductors"], ["TER", "Teradyne"], ["MCHP", "Microchip Technology"],
  // financieras
  ["JPM", "JPMorgan Chase"], ["BAC", "Bank of America"], ["WFC", "Wells Fargo"],
  ["C", "Citigroup"], ["GS", "Goldman Sachs"], ["MS", "Morgan Stanley"],
  ["SCHW", "Charles Schwab"], ["BLK", "BlackRock"], ["AXP", "American Express"],
  ["V", "Visa"], ["MA", "Mastercard"], ["PYPL", "PayPal"], ["SQ", "Block (Square)"],
  ["COIN", "Coinbase"], ["HOOD", "Robinhood"], ["SOFI", "SoFi Technologies"],
  ["AFRM", "Affirm"], ["UPST", "Upstart"], ["CME", "CME Group"], ["ICE", "Intercontinental Exchange"],
  ["SPGI", "S&P Global"], ["MCO", "Moody's"], ["BRK.B", "Berkshire Hathaway B"],
  // salud
  ["LLY", "Eli Lilly"], ["UNH", "UnitedHealth"], ["JNJ", "Johnson & Johnson"],
  ["ABBV", "AbbVie"], ["MRK", "Merck"], ["PFE", "Pfizer"], ["TMO", "Thermo Fisher"],
  ["ABT", "Abbott Laboratories"], ["AMGN", "Amgen"], ["GILD", "Gilead Sciences"],
  ["VRTX", "Vertex Pharmaceuticals"], ["REGN", "Regeneron"], ["BMY", "Bristol-Myers Squibb"],
  ["MRNA", "Moderna"], ["BNTX", "BioNTech"], ["NVO", "Novo Nordisk"], ["ISRG", "Intuitive Surgical"],
  ["SYK", "Stryker"], ["BSX", "Boston Scientific"], ["MDT", "Medtronic"], ["ELV", "Elevance Health"],
  ["CI", "Cigna"], ["HUM", "Humana"], ["CVS", "CVS Health"], ["HIMS", "Hims & Hers Health"],
  // consumo
  ["WMT", "Walmart"], ["COST", "Costco"], ["HD", "Home Depot"], ["LOW", "Lowe's"],
  ["TGT", "Target"], ["DG", "Dollar General"], ["DLTR", "Dollar Tree"], ["KR", "Kroger"],
  ["PG", "Procter & Gamble"], ["KO", "Coca-Cola"], ["PEP", "PepsiCo"], ["MDLZ", "Mondelez"],
  ["MO", "Altria"], ["PM", "Philip Morris"], ["EL", "Estée Lauder"], ["CL", "Colgate-Palmolive"],
  ["NKE", "Nike"], ["LULU", "Lululemon"], ["ONON", "On Holding"], ["DECK", "Deckers Outdoor"],
  ["CROX", "Crocs"], ["SBUX", "Starbucks"], ["MCD", "McDonald's"], ["CMG", "Chipotle"],
  ["YUM", "Yum! Brands"], ["DPZ", "Domino's Pizza"], ["DIS", "Walt Disney"], ["CMCSA", "Comcast"],
  ["WBD", "Warner Bros Discovery"], ["PARA", "Paramount Global"], ["ROKU", "Roku"],
  // industriales / energía / defensa
  ["XOM", "Exxon Mobil"], ["CVX", "Chevron"], ["COP", "ConocoPhillips"], ["OXY", "Occidental Petroleum"],
  ["SLB", "Schlumberger"], ["HAL", "Halliburton"], ["DVN", "Devon Energy"], ["FSLR", "First Solar"],
  ["ENPH", "Enphase Energy"], ["GE", "GE Aerospace"], ["CAT", "Caterpillar"], ["DE", "Deere & Company"],
  ["HON", "Honeywell"], ["MMM", "3M"], ["ETN", "Eaton"], ["EMR", "Emerson Electric"],
  ["BA", "Boeing"], ["LMT", "Lockheed Martin"], ["NOC", "Northrop Grumman"], ["RTX", "RTX (Raytheon)"],
  ["GD", "General Dynamics"], ["UNP", "Union Pacific"], ["CSX", "CSX Corporation"],
  ["UPS", "United Parcel Service"], ["FDX", "FedEx"], ["F", "Ford Motor"], ["GM", "General Motors"],
  ["RIVN", "Rivian"], ["LCID", "Lucid Motors"], ["NIO", "NIO"], ["XPEV", "XPeng"], ["LI", "Li Auto"],
  // aerolíneas / viajes / casinos
  ["AAL", "American Airlines"], ["DAL", "Delta Air Lines"], ["UAL", "United Airlines"],
  ["LUV", "Southwest Airlines"], ["CCL", "Carnival"], ["RCL", "Royal Caribbean"],
  ["NCLH", "Norwegian Cruise Line"], ["BKNG", "Booking Holdings"], ["MAR", "Marriott"],
  ["WYNN", "Wynn Resorts"], ["LVS", "Las Vegas Sands"], ["MGM", "MGM Resorts"],
  ["CZR", "Caesars Entertainment"], ["DKNG", "DraftKings"], ["PENN", "Penn Entertainment"],
  // china / internacional
  ["BABA", "Alibaba"], ["JD", "JD.com"], ["PDD", "PDD Holdings (Temu)"], ["BIDU", "Baidu"],
  ["NTES", "NetEase"], ["TME", "Tencent Music"], ["SE", "Sea Limited"], ["MELI", "MercadoLibre"],
  // cripto-relacionadas
  ["MSTR", "MicroStrategy"], ["MARA", "Marathon Digital"], ["RIOT", "Riot Platforms"],
  ["CLSK", "CleanSpark"], ["HUT", "Hut 8 Mining"], ["BITF", "Bitfarms"],
  // otros grandes
  ["T", "AT&T"], ["VZ", "Verizon"], ["TMUS", "T-Mobile US"], ["NEE", "NextEra Energy"],
  ["DUK", "Duke Energy"], ["SO", "Southern Company"], ["LIN", "Linde"], ["APD", "Air Products"],
  ["FCX", "Freeport-McMoRan"], ["NEM", "Newmont"], ["AA", "Alcoa"], ["X", "US Steel"],
  ["CLF", "Cleveland-Cliffs"], ["NUE", "Nucor"], ["PLD", "Prologis"], ["O", "Realty Income"],
  ["ADP", "Automatic Data Processing"], ["MMC", "Marsh & McLennan"], ["CB", "Chubb"],
  ["TJX", "TJX Companies"], ["ROST", "Ross Stores"], ["GME", "GameStop"], ["AMC", "AMC Entertainment"],
  ["BYND", "Beyond Meat"], ["CHWY", "Chewy"], ["ETSY", "Etsy"], ["W", "Wayfair"],
  ["FUBO", "fuboTV"], ["OPEN", "Opendoor"], ["Z", "Zillow"], ["CVNA", "Carvana"],
];

function searchSymbols(query, limit = 12) {
  query = query.trim().toUpperCase();
  if (!query) return SYMBOL_CATALOG.slice(0, limit);
  const starts = [], contains = [], byName = [];
  for (const entry of SYMBOL_CATALOG) {
    const [ticker, name] = entry;
    if (ticker === query) starts.unshift(entry);          // exacto primero
    else if (ticker.startsWith(query)) starts.push(entry);
    else if (ticker.includes(query)) contains.push(entry);
    else if (name.toUpperCase().includes(query)) byName.push(entry);
  }
  return [...starts, ...contains, ...byName].slice(0, limit);
}

function attachSymbolPicker(input, { onPick, onEnter } = {}) {
  const dropdown = document.createElement("div");
  dropdown.className = "sym-dd";
  dropdown.hidden = true;
  document.body.appendChild(dropdown);

  let items = [];
  let highlighted = -1;

  const position = () => {
    const rect = input.getBoundingClientRect();
    dropdown.style.left = Math.min(rect.left, innerWidth - 290) + "px";
    dropdown.style.top = rect.bottom + 4 + "px";
    dropdown.style.minWidth = Math.max(rect.width, 260) + "px";
  };

  const close = () => { dropdown.hidden = true; highlighted = -1; };

  /* Redibuja el dropdown desde `items` (sin volver a buscar) — para
   * navegación con flechas o para pintar resultados remotos ya llegados. */
  const renderDropdown = () => {
    if (!items.length) { close(); return; }
    highlighted = Math.min(highlighted, items.length - 1);
    dropdown.innerHTML = items.map(([ticker, name], i) =>
      `<div class="sym-item ${i === highlighted ? "hl" : ""}" data-i="${i}">
         <b>${ticker}</b><span>${name}</span></div>`).join("");
    dropdown.querySelectorAll(".sym-item").forEach(item => {
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();  // no robar el foco antes del click
        pick(Number(item.dataset.i));
      });
      item.addEventListener("mousemove", () => {
        highlighted = Number(item.dataset.i);
        dropdown.querySelectorAll(".sym-item").forEach((other, i) =>
          other.classList.toggle("hl", i === highlighted));
      });
    });
    position();
    dropdown.hidden = false;
  };

  /* Búsqueda local instantánea + enriquecimiento con /api/symbolsearch
   * (Tradier, miles de tickers reales) cuando llega — sin token o sin
   * red, se queda con la lista local de siempre, sin romper nada. */
  let searchToken = 0;
  const render = () => {
    const query = input.value.trim();
    items = searchSymbols(query);
    renderDropdown();
    if (!query) return;
    const token = ++searchToken;
    fetch(`/api/symbolsearch?q=${encodeURIComponent(query)}`)
      .then(r => r.ok ? r.json() : [])
      .then(remote => {
        if (token !== searchToken || !remote.length) return;  // el input ya cambió, o nada nuevo
        const seen = new Set(items.map(([ticker]) => ticker));
        const extra = remote.filter(r => !seen.has(r.symbol)).map(r => [r.symbol, r.name || ""]);
        if (!extra.length) return;
        items = [...items, ...extra].slice(0, 12);
        renderDropdown();
      })
      .catch(() => {});  // sin Tradier, se queda con la búsqueda local
  };

  const pick = (index) => {
    const entry = items[index];
    if (!entry) return;
    input.value = entry[0];
    close();
    if (onPick) onPick(entry[0]);
  };

  input.addEventListener("focus", () => { input.select(); render(); });
  input.addEventListener("click", () => { if (dropdown.hidden) render(); });
  input.addEventListener("input", () => { highlighted = 0; render(); });
  input.addEventListener("blur", () => setTimeout(close, 120));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && !dropdown.hidden) {
      e.preventDefault();
      highlighted = (highlighted + 1) % items.length;
      renderDropdown();
    } else if (e.key === "ArrowUp" && !dropdown.hidden) {
      e.preventDefault();
      highlighted = (highlighted - 1 + items.length) % items.length;
      renderDropdown();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (!dropdown.hidden && highlighted >= 0) pick(highlighted);
      else if (!dropdown.hidden && items.length) pick(0);
      else if (onEnter) onEnter(input.value.trim().toUpperCase());
      input.blur();
    } else if (e.key === "Escape") {
      close();
    }
  });
  addEventListener("resize", () => { if (!dropdown.hidden) position(); });
}
