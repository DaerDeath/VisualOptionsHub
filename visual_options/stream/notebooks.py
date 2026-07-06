"""Método ORIGINAL de los notebooks del usuario, portado sin cambios.

Reproduce fielmente las celdas de SP500-Daily.ipynb y SP500-MeanZero.ipynb
(y sus variantes NAS/Dow/XAU): mismos modelos, mismos parámetros, misma
semilla y mismo horizonte. Es la vista informativa "tal cual estaba":
las correcciones viven en stream/stats.py (vista Estadísticos).

  daily    → ARIMA(1,0,1) sobre retornos log + GARCH(1,1) media cero;
             UNA trayectoria simulada con np.random.seed(42) (sic)
  meanzero → GARCH(1,1) con mean='Constant' (sic, pese al nombre);
             precio esperado + bandas ±1σ acumuladas

Datos: intervalo 15m, periodo 7d — es lo que descargan TODOS los
notebooks aunque se llamen Daily u 8H.
"""

from __future__ import annotations

import numpy as np

HORIZON = 96          # pasos de 15m, como en los notebooks
INTERVAL = "15m"
PERIOD = "7d"
GARCH_SCALE = 1000.0  # los notebooks escalan ×1000 antes del GARCH

# los notebooks originales usaban estos futuros
NOTEBOOK_TICKERS = {"ES=F": "E-mini S&P 500", "NQ=F": "E-mini Nasdaq 100",
                    "YM=F": "Mini Dow Jones", "GC=F": "Oro (futuro)"}


def fetch_closes(symbol: str) -> tuple[list[str], np.ndarray]:
    """Descarga como los notebooks: yf.download(interval='15m', period='7d')."""
    import yfinance as yf
    ticker = f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol
    data = yf.download(ticker, interval=INTERVAL, period=PERIOD, progress=False,
                       auto_adjust=True)
    if data is None or data.empty:
        raise ValueError("No se descargaron datos. Verifica conexión o que el mercado esté abierto.")
    closes = data["Close"].dropna()
    if hasattr(closes, "columns"):  # MultiIndex de yfinance moderno
        closes = closes.iloc[:, 0]
    times = [ts.strftime("%d %H:%M") for ts in closes.index]
    return times, closes.to_numpy(dtype=float)


def _named_params(params, names) -> dict:
    """Serie de pandas o ndarray → dict nombre→valor redondeado."""
    if hasattr(params, "items"):
        return {str(k): round(float(v), 6) for k, v in params.items()}
    values = np.asarray(params, dtype=float)
    names = list(names) if names else [f"p{i}" for i in range(len(values))]
    return {str(n): round(float(v), 6) for n, v in zip(names, values)}


def original_projection(symbol: str, variant: str = "daily",
                        closes: np.ndarray | None = None,
                        times: list[str] | None = None) -> dict:
    """Proyección con el método original. `closes` inyectable para tests."""
    if closes is None:
        times, closes = fetch_closes(symbol)
    times = times or [str(i) for i in range(len(closes))]
    log_returns = np.diff(np.log(closes))
    returns = log_returns[~np.isnan(log_returns)]
    if len(returns) < 50:
        raise ValueError(f"solo {len(returns)} retornos; insuficientes para ajustar")

    last_price = float(closes[-1])
    scaled = returns * GARCH_SCALE

    result = {
        "symbol": symbol,
        "variant": variant,
        "interval": INTERVAL,
        "period": PERIOD,
        "horizon": HORIZON,
        "history": {"t": times, "close": [round(float(c), 4) for c in closes]},
        "last_price": last_price,
    }

    if variant == "daily":
        # === celda original de SP500-Daily.ipynb ===
        from statsmodels.tsa.arima.model import ARIMA

        from arch import arch_model
        arima_fit = ARIMA(returns, order=(1, 0, 1)).fit()
        mu_forecast = np.asarray(arima_fit.forecast(steps=HORIZON), dtype=float)

        garch_fit = arch_model(scaled, vol="GARCH", p=1, q=1, mean="Zero").fit(disp="off")
        vol_forecast = np.sqrt(garch_fit.forecast(horizon=HORIZON).variance.iloc[-1].values) / GARCH_SCALE

        np.random.seed(42)  # sic: una sola trayectoria con semilla fija
        shocks = np.random.normal(0, 1, size=HORIZON)
        sim_log_returns = mu_forecast + vol_forecast * shocks
        sim_prices = np.exp(np.cumsum(sim_log_returns) + np.log(last_price))

        result["projection"] = [round(float(p), 4) for p in sim_prices]
        result["params"] = {
            "arima": _named_params(arima_fit.params,
                                   getattr(arima_fit, "param_names", None)),
            "garch": _named_params(garch_fit.params, None),
        }
        result["label"] = "Proyección ARIMA(1,0,1) + GARCH(1,1) — 1 trayectoria (seed 42)"

    elif variant == "meanzero":
        # === celda original de SP500-MeanZero.ipynb ===
        from arch import arch_model
        garch_fit = arch_model(scaled, vol="GARCH", p=1, q=1, mean="Constant").fit(disp="off")
        forecast = garch_fit.forecast(horizon=HORIZON)
        mean_forecast = forecast.mean.iloc[-1].values / GARCH_SCALE
        vol_forecast = np.sqrt(forecast.variance.iloc[-1].values) / GARCH_SCALE

        cum_mean = np.cumsum(mean_forecast)
        cum_std = np.sqrt(np.cumsum(vol_forecast ** 2))

        result["projection"] = [round(float(p), 4) for p in last_price * np.exp(cum_mean)]
        result["upper"] = [round(float(p), 4) for p in last_price * np.exp(cum_mean + cum_std)]
        result["lower"] = [round(float(p), 4) for p in last_price * np.exp(cum_mean - cum_std)]
        result["params"] = {"garch": _named_params(garch_fit.params, None)}
        result["label"] = "Proyección GARCH(1,1) mean='Constant' ± 1σ acumulada"

    else:
        raise ValueError(f"variante desconocida: {variant!r} (usa 'daily' o 'meanzero')")

    return result
