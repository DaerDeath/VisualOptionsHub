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
    apiladas y price targets con upside) y <b>N</b> (titulares). Abajo, los criterios del libro
    que se pueden evaluar automáticamente con estos datos. Caché de 10 minutos.</p>`],
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
