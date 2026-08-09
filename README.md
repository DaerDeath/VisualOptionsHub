# visual-options

Toolkit de análisis de opciones basado en el libro "Visual Guide to Options" de Jared Levy.

Incluye una terminal web interactiva (34 vistas: flujo 0DTE, footprint, Wyckoff, posicionamiento de dealers con GEX/DEX/vanna, heatmaps, scanner, screener de verticales, calculadora, grading A-F, estadísticos GARCH, backtests, ficha de empresa, portafolio real, stress test y más), el toolkit completo del libro (23 estrategias, pricing Black-Scholes, griegas, probabilidades) y CLI de línea de comandos.

Con Tradier también aprovecha watchlists reales, estado exacto del mercado y streaming en vivo tick a tick — y cualquier vista se puede dividir en pantalla de 2, 3 o 4 paneles, cada uno con su propio selector de contenido.

## Empezar en 1 minuto

**Requisitos:** Python 3.11+ y [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run voptions stream
# Abre http://127.0.0.1:8000
```

## Fuentes de datos

- **Simulador** — datos sintéticos, no requiere conexión
- **Yahoo Finance** — reales, ~15 min de retraso, gratis
- **Tradier** — tiempo real con API key (incluye sandbox gratis)
- **IBKR** — en vivo desde TWS/Gateway (requiere `uv sync --extra ibkr`)

## Estructura

- `visual_options/` — toolkit: pricing, griegas, 23 estrategias, CLI
- `visual_options/stream/` — backend FastAPI para la terminal web
- `visual_options/stream/web/` — frontend canvas vanilla JS
- `tests/` — 250+ tests con cobertura 80%+

## Aviso

Herramienta educativa. No es asesoramiento financiero. Controla siempre el riesgo por posición.
