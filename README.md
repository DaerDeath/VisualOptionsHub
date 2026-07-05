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
```

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
