# visual-options

Toolkit de análisis de opciones basado en el libro "Visual Guide to Options" de Jared Levy.

Incluye una terminal web interactiva (~25 vistas: flujo 0DTE, footprint, Wyckoff, posicionamiento de dealers con GEX/DEX/vanna, heatmaps, scanner, calculadora, estadísticos GARCH y backtests), el toolkit completo del libro (23 estrategias, pricing Black-Scholes, griegas, probabilidades) y CLI de línea de comandos.

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
- `tests/` — 180+ tests con cobertura 80%+

## Aviso

Herramienta educativa. No es asesoramiento financiero. Controla siempre el riesgo por posición.
