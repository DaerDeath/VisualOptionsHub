/* Guía: documentación de todos los apartados de la terminal. */
"use strict";

const GUIDE_SECTIONS = [
  ["Flujo de opciones", "flow", `
    <p>Réplica del stream 0DTE. <b>Cadena por strike</b>: calls arriba, puts abajo;
    el <b>% es la porción VENDIDA</b> de ese lado (rojo) — 16% vendido = 84% comprado = muy alcista.
    Calls muy vendidos en un strike suelen actuar de techo. El histograma blanco es el perfil de volumen
    y los chips azules el volumen por strike.</p>
    <p><b>Flujo agregado vs precio</b>: la regla del autor es literal — <i>azul (call sell %) baja → precio sube;
    roja (put sell %) baja → el precio la sigue</i>. Un call sell % hundiéndose hacia ~10% suele preceder squeezes.</p>
    <p><b>Gamma (GEX)</b>: bolsas rojas = zonas donde el precio acelera; verdes = zonas que lo frenan.
    <b>Magnet strikes</b>: concentración de OI/mariposas; actúa como imán del precio.</p>`],
  ["Setup: footprint + Wyckoff + VP", "setup", `
    <p>Tu setup completo. <b>Velas + eventos Wyckoff</b> detectados por heurística:
    <b>SPRING</b> = barre los mínimos del área de valor y recupera (giro alcista probable);
    <b>UT</b> (upthrust) = supera el área de valor y falla (giro bajista);
    <b>SOS/SOW</b> = ruptura con rango amplio y delta a favor;
    <b>ABS</b> = mucho volumen sin desplazamiento (absorción, effort vs result).</p>
    <p><b>Volume Profile</b> a la derecha: POC (ámbar) = precio con más volumen = valor aceptado;
    VAH/VAL delimitan el 70% del volumen. Precio fuera del área de valor tiende a volver (rotación)
    o a iniciar tendencia si hay aceptación fuera.</p>`],
  ["Footprint", "footprint", `
    <p>Cada barra muestra <b>vendido × comprado por nivel de precio</b>. Delta = compras − ventas.
    <b>Imbalance ≥3×</b> (borde) = agresión dominante en diagonal. POC de barra en ámbar.
    Busca: absorción en extremos (volumen alto sin avance), imbalances apilados a favor de la tendencia,
    y deltas divergentes con el precio.</p>`],
  ["Dealer positioning", "dealer", `
    <p>Lo que calcula CloutSeeker: <b>Net GEX</b> (gamma × OI): positivo = dealers frenan el precio,
    negativo = lo aceleran. <b>Net DEX</b> = exposición direccional por delta.
    <b>Net Vanna</b> = sensibilidad de la delta a la IV: con vanna alta, un cambio de IV mueve las coberturas.
    Línea magenta = <b>gamma flip</b>: por encima régimen estable, por debajo régimen explosivo.</p>`],
  ["Niveles clave", "levels", `
    <p>Nota auto-generada al estilo Founder's Note: <b>call wall</b> (strike con más GEX positivo, resistencia),
    <b>put wall</b> (más negativo, soporte), <b>imán</b> de OI, <b>gamma flip</b> y el
    <b>movimiento esperado ±1σ</b> (IV ATM × √t). Úsala como mapa antes de abrir la sesión.</p>`],
  ["Heatmap GEX", "heatmap", `
    <p>Evolución del GEX por strike en el tiempo (TRACE-like). El precio (línea blanca) suele
    <i>cabalgar</i> las bandas verdes (gamma positiva que amortigua) y acelerar al cruzar zonas rojas.
    Cambios bruscos de color = reposicionamiento de dealers.</p>`],
  ["Impacto del flujo (HIRO)", "hiro", `
    <p>Índice acumulado del flujo: sube cuando se venden puts / compran calls con agresión.
    <b>Divergencias</b>: si el precio hace máximos y el índice no (o al revés), el movimiento
    pierde gasolina. El área verde/roja indica presión neta acumulada de la sesión.</p>`],
  ["Estructura de plazos", "termstructure", `
    <p><b>TRMS</b> del libro: la IV ATM de cada vencimiento en una curva. <b>Contango</b> (sube con
    el plazo) es lo normal — el corto plazo es más barato porque hay menos incertidumbre acumulada.
    <b>Backwardation</b> (el corto plazo más caro que el largo) señala estrés inminente: earnings,
    una decisión de la Fed, o pánico ya en marcha.</p>`],
  ["Cono de volatilidad", "volcone", `
    <p><b>VC</b> del libro: en vez de comparar IV contra HV de hoy, compara la <b>vol realizada actual</b>
    contra su propio rango histórico (2 años) por ventana de tiempo. El percentil te dice si el
    régimen de volatilidad está caro (alto) o barato (bajo) en contexto — más fiable que mirar
    un solo número suelto.</p>`],
  ["Correlación", "correlation", `
    <p><b>CORR</b> del libro (aquí, contra una cesta de índices/sectores en vez de peers individuales):
    cuánto se mueve el papel en línea con SPY, QQQ, sectores, oro, bonos… Útil para saber si estás
    realmente apostando por la empresa o solo por el mercado general, y para elegir el mejor hedge.</p>`],
  ["Forward & Cost of Carry", "forward", `
    <p><b>NOVM</b> del libro (Cap. 2), el ejemplo de IBM reproducido con tus propios símbolos:
    <b>Cost of Carry</b> = interés que ganarías teniendo el capital en el activo libre de riesgo
    menos los dividendos que te pierdes hasta el vencimiento. <b>Forward Price</b> = Spot + Cost
    of Carry. Es interés <i>simple</i> (no capitalización continua) — así lo calcula el libro.
    Si el forward queda por debajo del spot, los puts ATM valen más que los calls (dividendos
    ganan la partida); si queda por encima, ganan los calls (interés gana la partida). Tasa por
    defecto: T-bill a 13 semanas real de Yahoo, editable.</p>`],
  ["Cadena + griegas", "chain", `
    <p>La cadena completa del vencimiento con precio teórico BSM y las griegas por contrato:
    <b>Δ</b> (sensibilidad al precio; también ≈ prob. de expirar ITM), <b>Γ</b> (cómo cambia la delta),
    <b>Θ</b> (lo que pierde por día), <b>V</b> (sensibilidad a 1% de IV) y <b>ρ</b> (a 1% de tipos).
    Fila ámbar = ATM. Nota: Γ y V son iguales para call y put del mismo strike — es matemática, no un error.</p>`],
  ["Volatilidad", "vol", `
    <p><b>Smile de IV</b> por strike: el skew negativo (puts OTM más caros) es lo normal en índices.
    Skew muy empinado = miedo a caídas; aplanamiento = complacencia.
    Las bandas ámbar son el movimiento esperado ±1σ/±2σ. IV alta frente a lo realizado favorece
    vender prima; IV baja, comprarla (cap. 2 y 7 del libro).</p>`],
  ["Perfil de OI", "oi", `
    <p>Open interest en espejo: puts izquierda, calls derecha. Los picos de OI actúan de
    soporte/resistencia (ahí están las coberturas). <b>PCR</b> = put OI / call OI:
    &gt;1 posicionamiento defensivo, &lt;0.7 complacencia — léelo de forma contraria en extremos.</p>`],
  ["Tape", "tape", `
    <p>Bloques grandes de volumen clasificados contra el bid-ask: <b>VENTA</b> = cruzó al bid,
    <b>COMPRA</b> = al ask. Busca secuencias del mismo lado en el mismo strike (acumulación
    institucional) y prima gorda (filas resaltadas) cerca de niveles clave.</p>`],
  ["Empresa", "company", `
    <p>Ficha Bloomberg-like con datos gratis de Yahoo: <b>DES</b> (perfil, market cap, P/E,
    beta, rango 52 semanas), <b>ERN</b> (próximo earnings con countdown y estimaciones, más el
    historial de sorpresas EPS — clave para el checklist del Cap. 7), <b>ANR</b> (recomendaciones
    apiladas y price targets con upside), <b>SIA</b> (interés en corto: % del float, días para
    cubrir y tendencia — alto + giro alcista = mecha de short squeeze) y <b>N</b> (titulares).
    Abajo, los criterios del libro evaluados automáticamente. Caché de 10 minutos.</p>`],
  ["Scanner", "scanner", `
    <p>Señales por símbolo: <b>Dirección</b> = put sell % − call sell % (positivo = presión alcista).
    <b>Régimen</b> = signo del GEX total. <b>Dist. flip</b> = colchón hasta el gamma flip (pequeño = peligro
    de aceleración). Clic en una fila para abrir su flujo. La lista de símbolos es editable.</p>`],
  ["Calculadora", "calc", `
    <p>Las 23 estrategias del libro: P/L a expiración (blanco) y valor hoy (azul discontinuo),
    breakevens, máximos y <b>probabilidad de beneficio</b> (lognormal con la IV que pongas).
    Con auto-precio, las primas se estiman con Black-Scholes — para primas reales usa
    las de tu broker. Regla del cap. 2: una vertical vendida debe rendir ≥12-15%.</p>`],
  ["Max Pain", "maxpain", `
    <p>El precio de vencimiento que minimiza lo que pagan los emisores de opciones (suma de
    valor intrínseco de calls y puts según OI). La teoría: el precio tiende a gravitar hacia
    max pain al acercarse el vencimiento. Útil como imán de referencia, no como señal única.</p>`],
  ["Delta acumulado (CVD)", "cvd", `
    <p>Suma acumulada del delta (compras − ventas) del footprint. Confirma tendencias:
    precio y CVD subiendo juntos = sano. <b>Divergencia</b> (precio sube, CVD no) = el movimiento
    lo sostienen pocos agresores — ojo al giro. Marcamos divergencias automáticamente.</p>`],
  ["Perfil TPO", "tpo", `
    <p>Market Profile clásico: cada letra = un periodo de tiempo tocando ese precio (A = apertura).
    Donde se apilan letras hay <b>aceptación</b>; colas de una letra = rechazo.
    <b>IB</b> (initial balance) = rango de los dos primeros periodos: romperlo con convicción
    define el tipo de día (tendencia vs rotación).</p>`],
  ["Probabilidades", "probs", `
    <p><b>Cono de movimiento esperado</b> ±1σ/±2σ proyectado desde el último precio con la IV ATM
    (68% / 95% de probabilidad de quedar dentro, si la lognormal se cumple).
    La tabla da la <b>probabilidad de expirar ITM</b> por strike con su propia IV — la base para
    elegir strikes de venta (ej.: vender el put con ~16% ITM ≈ 1σ).</p>`],
  ["VWAP + sesión", "vwap", `
    <p><b>VWAP</b> = precio medio ponderado por volumen de la sesión: el precio institucional de referencia.
    Por encima = compradores en control. Las bandas ±1σ/±2σ (desviación ponderada por volumen)
    marcan extensiones. Los tiles resumen la sesión: rango, volumen, delta total y % de barras alcistas.</p>`],
  ["Put/Call Ratio", "pcr", `
    <p>PCR por <b>volumen</b> (lo operado hoy: sentimiento inmediato) y por <b>OI</b> (posicionamiento).
    Lectura contraria en extremos: PCR volumen &gt;1.2 = pánico (suelo cerca), &lt;0.5 = euforia.
    El desglose por strike enseña dónde se concentra la desproporción.</p>`],
  ["Estadísticos", "stats", `
    <p>Batería de tests sobre los retornos reales del símbolo, cada uno con veredicto:
    <b>Jarque-Bera</b> (¿normales? casi nunca — por eso el MC usa bootstrap), <b>Dickey-Fuller</b>
    (¿estacionarios?), <b>Ljung-Box</b> (¿autocorrelación?), <b>efecto ARCH</b> (¿clustering de
    volatilidad? justifica el GARCH) y <b>GARCH(1,1)</b> con su persistencia. El botón
    <b>Monte Carlo</b> lanza 2.000 trayectorias con bootstrap de residuos → cono de percentiles,
    prob. de subir y VaR 95%.</p>`],
  ["Notebooks (original)", "notebooks", `
    <p>El método de tus .ipynb tal cual, como referencia: ARIMA(1,0,1)+GARCH con UNA trayectoria
    (seed 42) o la variante MeanZero con bandas ±1σ. <i>Informativo</i>: una sola ruta no es una
    proyección — compárala con el Monte Carlo de Estadísticos para ver la diferencia.</p>`],
  ["Lo que no está (y por qué)", "chain", `
    <p>Del apéndice del libro, tres pantallas se quedan fuera porque no hay fuente gratuita fiable:
    <b>WGT</b> (peso de una acción en cada índice — requiere datos de proveedores de índices, de pago),
    <b>ECO</b> (calendario macro con consenso de economistas) y <b>CEPR</b> (directorio de exchanges,
    sin utilidad práctica aquí). El resto del apéndice (32 pantallas) está cubierto por alguna vista
    de la app, aunque no lleve el mismo nombre de 4 letras — mira las tarjetas de arriba.</p>`],
  ["Grading (A-F)", "grading", `
    <p>El checklist de calificación del Cap. 2: cada operación empieza en <b>A</b> y baja un grado
    por cada criterio incumplido (A→10% de cartera máx., F→no operar). 10 de los 17 criterios se
    calculan solos con datos reales (volumen, medias móviles, Bollinger, MACD, ATR, IV vs HV,
    volumen y spreads de opciones); los otros 7 —conocer el negocio, tu estado mental, etc.— son
    subjetivos <i>por diseño</i> del libro y se marcan a mano con un clic. Clic en cualquier
    criterio automático también lo anula si no estás de acuerdo con el cálculo.</p>`],
  ["Portafolio", "portfolio", `
    <p><b>Solo lectura</b> — esta vista nunca coloca, modifica ni cancela ninguna orden, solo lee
    lo que ya tienes abierto. Con <b>IBKR</b> el P&amp;L lo calcula el propio TWS (más fiable que
    recalcularlo aquí); con <b>Tradier</b> se calcula a partir del coste base y el precio actual,
    con griegas ORATS por posición. Los totales de la cabecera son la suma de todas tus posiciones:
    tu exposición real agregada, no la de una sola estrategia suelta.</p>`],
  ["Stress Test", "stress", `
    <p>Lee tus posiciones REALES (mismo origen que Portafolio, solo lectura) y recalcula el P&amp;L
    de toda la cartera bajo una matriz de escenarios: shocks de precio del subyacente (±2.5% a ±10%)
    cruzados con shocks de IV (±15% y ±30%). Cada opción se reprecifica con el propio Black-Scholes
    del toolkit, resolviendo primero su IV implícita desde el precio de mercado reportado — no depende
    de que el bróker entregue la griega. Si falta el precio de una posición cae a un fallback lineal
    por delta, y si falta el spot del subyacente esa posición no aporta al escenario (se cuenta aparte
    en "sin modelar"). La celda 0%/0% siempre debe rondar tu P&amp;L no realizado actual — es la forma
    rápida de verificar que el modelo cuadra con la realidad.</p>`],
  ["Alertas", "alerts", `
    <p>Avisos locales del navegador: precio cruza un nivel, call/put sell % bajo un umbral
    o cruce del gamma flip. Suena un beep y sale notificación. Se revisan con cada tick
    del stream y se guardan en este navegador.</p>`],
  ["Diario", "journal", `
    <p>Notas rápidas con contexto automático (hora, símbolo, precio al escribirla).
    Apunta el porqué de cada entrada/salida y revísalo después — es la herramienta
    de mejora más barata que existe. Se guarda en este navegador.</p>`],
];

const GuideView = {
  mount(root) {
    root.innerHTML = `
      <div class="guide-wrap">
        <section class="panel guide-panel">
          <div class="panel-head"><h2>Guía de la terminal</h2>
            <span class="hint">clic en un título para abrir esa vista con el símbolo actual</span></div>
          <div class="guide-body">
            ${GUIDE_SECTIONS.map(([title, view, html]) => `
              <article class="guide-sec">
                <h3><a href="#/${view}/${localStorage.getItem("vo-symbol") || "QQQ"}">${title}</a></h3>
                ${html}
              </article>`).join("")}
            <article class="guide-sec guide-foot">
              <h3>Fuentes de datos</h3>
              <p><b>Simulación</b>: sesión sintética con la dinámica del stream (siempre disponible).
              <b>Yahoo</b>: datos reales gratis con ~15 min de retraso, sin token.
              <b>Tradier 15m</b>: sandbox gratis con token (griegas ORATS).
              <b>Tradier / IBKR</b>: tiempo real con cuenta. El % comprado/vendido siempre es una
              aproximación por clasificación contra el bid-ask.</p>
              <p class="tt-dim">Nada de esto es asesoramiento financiero: son herramientas de lectura.</p>
            </article>
          </div>
        </section>
      </div>`;
  },
  unmount() {},
  onData() {},
};
