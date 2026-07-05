# visual-options

Toolkit de análisis de opciones que implementa el contenido de **Visual Guide to
Options** de Jared Levy (Bloomberg Financial, 2013), capítulo a capítulo:

| Capítulo | Contenido | Módulo |
|---|---|---|
| 1. The World of Options | moneyness, valor intrínseco/extrínseco, payoffs | `contracts.py` |
| 2. Tools & Knowledge | pricing BSM, IV, prob. ITM, movimiento esperado 1σ, sistema de calificación A-F | `pricing.py`, `grading.py` |
| 3. Visualizing the Greeks | delta, gamma, theta, vega, rho por pata y por posición | `greeks.py` |
| 4. Basic Strategies | long/short call/put, covered call, protective put, collar | `builders.py` |
| 5. Vertical Spreads | bull/bear call/put spreads (débito y crédito) | `builders.py` |
| 6. Butterflies, Condors & Complex | mariposas, cóndores e iron (largos y cortos) | `builders.py` |
| 7. Managing Your Risk | HV/IV, straddles/strangles, checklist de earnings, regla de breakeven | `volatility.py`, `grading.py` |

Cada estrategia lleva incrustadas las fórmulas literales del libro (max profit,
max risk, breakeven) y los tests verifican que la matemática las reproduce.

## Instalación

```bash
cd visual-options
uv sync                 # entorno + dependencias
uv run pytest           # verificar
# con datos de IBKR (requiere TWS/IB Gateway):
uv sync --extra ibkr
```

## Uso

```bash
# Listar las 23 estrategias del libro y sus parámetros
uv run voptions list

# Analizar un bull put spread (ejemplo del Cap. 5) con gráfico P/L
uv run voptions analyze bull_put_spread \
    short_strike=190 short_premium=5 long_strike=180 long_premium=2.5 \
    --spot 195 --iv 0.28 --days 30 --plot charts/bull_put.png --greeks-plot charts/bull_put_greeks.png

# ¿No conoces las primas? Estímalas con Black-Scholes
uv run voptions analyze long_straddle strike=100 \
    --auto-price --spot 100 --iv 0.35 --days 21 --plot charts/straddle.png

# Precio, griegas y probabilidad ITM de una opción suelta
uv run voptions price call --spot 150 --strike 155 --days 45 --iv 0.30

# Volatilidad histórica desde un fichero de cierres (uno por línea)
uv run voptions vol cierres.txt --window 30 --iv 0.45 --days 30

# Sistema de calificación A-F del Cap. 2
uv run voptions grade --show-criteria
uv run voptions grade --fail chart_macd,opt_spreads --account 25000

# Checklist de earnings del Cap. 7 + regla de breakeven
uv run voptions earnings --spot 100 --avg-move 0.10

# Cadena de opciones en vivo desde IBKR (TWS paper en 7497)
uv run voptions chain AAPL --port 7497

# Terminal web multi-vista (flujo de opciones, footprint…)
uv run voptions stream                          # simulador en http://127.0.0.1:8000
TRADIER_TOKEN=xxx uv run voptions stream --mode tradier   # API Tradier (gratis, ~15 min retraso)
uv run voptions stream --mode ibkr              # datos en vivo desde TWS/Gateway
```

## Terminal web (`voptions stream`)

Al abrir el navegador aparece un **selector**: eliges el subyacente (QQQ,
SPY, SPX, NVDA… o el que escribas) y la visualización. Desde cualquier
vista puedes cambiar de símbolo (input de la barra superior + Enter) o
saltar entre vistas sin recargar. Cada símbolo mantiene su propia sesión
de datos en el servidor.

Vistas disponibles:

1. **Flujo de opciones** — el dashboard estilo stream 0DTE (abajo).
2. **Footprint** — velas con volumen comprador × vendedor por nivel de
   precio, delta y volumen por barra, POC (ámbar) e imbalances diagonales
   ≥3× (borde rojo/verde).
3. **Dealer positioning** — réplica de la hoja CloutSeeker (liquidose)
   sin Excel/Windows/ThinkorSwim: Net GEX, Net DEX y Net Vanna por strike
   calculados con nuestro propio BSM desde OI + IV (`stream/dealer.py`),
   con desglose call/put, totales, spot y nivel de gamma flip.
4. Huecos para las siguientes (heatmap de OI, DOM, TPO…): pídelas.

**Proveedor de datos**: se elige desde la propia web con el selector de la
barra superior — `Simulación`, `Tradier` (tiempo real, cuenta de broker),
`Tradier 15m` (sandbox gratis con retraso) e `IBKR` (TWS/Gateway). Cada
fuente aparece deshabilitada si le falta su requisito (token de Tradier en
`TRADIER_TOKEN` o `--tradier-token`; `uv sync --extra ibkr` para IBKR).
`--mode` solo fija la fuente por defecto al arrancar; el cambio es por
sesión y sin reiniciar el servidor.

## Vista de flujo

Replica el "Options Premium / Volume Profile" de los streams 0DTE, con la
lectura que explica el vídeo *how to read the stream's data*:

- **Cadena por strike** (panel superior): calls arriba, puts abajo. El **%
  es la porción VENDIDA** de ese lado (rojo); el resto es comprada (verde).
  16% vendido = 84% comprado = muy alcista. El histograma blanco es el
  perfil visual del volumen y los chips azules el volumen por strike.
- **Flujo agregado vs precio** (abajo izquierda): la regla del autor es
  literal — *azul (call sell %) baja → precio sube; roja (put sell %) baja
  → el precio la sigue*. Call sell % hundiéndose hacia ~10% = squeeze.
- **Gamma (GEX) por strike**: bolsas negativas = zonas donde el precio
  acelera; positivas = zonas que lo frenan.
- **Magnet strikes**: OI de mariposas / volumen; funciona como imán del
  precio y su sesgo indica hacia dónde gravita la sesión.

Interacción: hover en cualquier panel para el detalle del strike o del
minuto, clic en la cadena para fijar un strike, espacio o ⏸ para pausar.
El modo `sim` genera una sesión sintética con esa misma dinámica de flujo;
el modo `ibkr` clasifica cada incremento de volumen como comprado/vendido
comparando el último precio con el punto medio bid-ask (aproximación
Lee-Ready con datos de nivel 1).

## Uso como librería

```python
from visual_options.builders import short_iron_condor

s = short_iron_condor(85, 0.8, 90, 2.0, 110, 2.2, 115, 0.9)
print(s.summary(spot=100, iv=0.30, days=30))
print(s.probability_of_profit(spot=100, iv=0.30, days=30))
```

## Aviso

Herramienta educativa. Nada de esto es asesoramiento financiero; el propio
libro insiste: haz tus deberes y controla el riesgo por posición (nunca más
del 10-15% de la cartera en una sola operación).
