"""Estadísticos de series de retornos + Monte Carlo GARCH.

Versión revisada y corregida de los notebooks del usuario (SP500-Daily,
*-MeanZero, etc.), que ajustaban ARIMA+GARCH y proyectaban UNA sola
trayectoria aleatoria. Mejoras aplicadas:
  - validación de supuestos con veredicto: Jarque-Bera (normalidad),
    Dickey-Fuller (estacionariedad), Ljung-Box (autocorrelación) y
    efecto ARCH (Ljung-Box sobre r²)
  - GARCH(1,1) de media cero por MLE propia (scipy), sin dependencias
    extra, con chequeo de persistencia α+β < 1
  - Monte Carlo de verdad: miles de trayectorias con la recursión GARCH
    y shocks por bootstrap de los residuos estandarizados (las colas
    gordas reales, no la normal) → cono de percentiles y probabilidades
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps
from scipy.optimize import minimize

GARCH_SCALE = 1000.0  # los retornos se escalan para estabilidad numérica (como en arch)

# barras por año para anualizar según intervalo
BARS_PER_YEAR = {"5m": 252 * 78, "15m": 252 * 26, "1h": 252 * 7, "1d": 252}
PERIOD_FOR_INTERVAL = {"5m": "5d", "15m": "7d", "1h": "1mo", "1d": "1y"}


def fetch_log_returns(symbol: str, interval: str = "15m") -> tuple[np.ndarray, float]:
    """Descarga cierres con yfinance y devuelve (retornos log, último precio)."""
    import yfinance as yf
    period = PERIOD_FOR_INTERVAL.get(interval, "7d")
    ticker = yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)
    history = ticker.history(period=period, interval=interval)
    closes = history["Close"].dropna().to_numpy(dtype=float)
    if len(closes) < 60:
        raise ValueError(f"solo {len(closes)} cierres para {symbol} en {interval}; se necesitan ≥60")
    returns = np.diff(np.log(closes))
    return returns, float(closes[-1])


# ------------------------------------------------------------------ tests

def describe(returns: np.ndarray, interval: str) -> dict:
    per_year = BARS_PER_YEAR.get(interval, 252)
    return {
        "n": int(len(returns)),
        "mean": float(returns.mean()),
        "sigma_bar": float(returns.std(ddof=1)),
        "sigma_annual": float(returns.std(ddof=1) * math.sqrt(per_year)),
        "skew": float(sps.skew(returns)),
        "kurtosis": float(sps.kurtosis(returns)),  # exceso (normal = 0)
    }


def jarque_bera(returns: np.ndarray) -> dict:
    stat, p = sps.jarque_bera(returns)
    return {"stat": float(stat), "p": float(p), "normal": bool(p >= 0.05)}


def ljung_box(series: np.ndarray, lags: int = 10) -> dict:
    """Q de Ljung-Box: ¿hay autocorrelación hasta `lags`?"""
    x = np.asarray(series, dtype=float)
    x = x - x.mean()
    n = len(x)
    denominator = float(np.dot(x, x))
    q = 0.0
    for k in range(1, lags + 1):
        rho_k = float(np.dot(x[k:], x[:-k])) / denominator
        q += rho_k * rho_k / (n - k)
    q *= n * (n + 2)
    p = float(sps.chi2.sf(q, lags))
    return {"stat": float(q), "p": p, "independent": bool(p >= 0.05), "lags": lags}


def adf_test(returns: np.ndarray) -> dict:
    """Dickey-Fuller aumentado (1 rezago, con constante) hecho a mano.

    Δy_t = a + b·y_{t-1} + c·Δy_{t-1} + ε ; H0: b = 0 (raíz unitaria).
    Valores críticos asintóticos con constante: 1% −3.43, 5% −2.86, 10% −2.57.
    """
    y = np.asarray(returns, dtype=float)
    dy = np.diff(y)
    y_lag = y[1:-1]
    dy_lag = dy[:-1]
    dy_t = dy[1:]
    X = np.column_stack([np.ones_like(y_lag), y_lag, dy_lag])
    beta, _, _, _ = np.linalg.lstsq(X, dy_t, rcond=None)
    residuals = dy_t - X @ beta
    dof = len(dy_t) - X.shape[1]
    sigma2 = float(residuals @ residuals) / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    t_stat = float(beta[1] / math.sqrt(cov[1, 1]))
    critical = {"1%": -3.43, "5%": -2.86, "10%": -2.57}
    return {"stat": t_stat, "critical": critical, "stationary": bool(t_stat < critical["5%"])}


def ar1_fit(returns: np.ndarray) -> dict:
    """AR(1) por OLS: r_t = c + φ·r_{t-1}. Sustituto honesto del ARIMA(1,0,1)."""
    y = returns[1:]
    x = returns[:-1]
    X = np.column_stack([np.ones_like(x), x])
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ beta
    dof = len(y) - 2
    sigma2 = float(residuals @ residuals) / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    phi = float(beta[1])
    t_phi = phi / math.sqrt(cov[1, 1])
    p = float(2 * sps.t.sf(abs(t_phi), dof))
    return {"phi": phi, "t": float(t_phi), "p": p, "significant": bool(p < 0.05)}


def garch11_fit(returns: np.ndarray) -> dict:
    """GARCH(1,1) de media cero por máxima verosimilitud (Nelder-Mead)."""
    r = np.asarray(returns, dtype=float) * GARCH_SCALE
    var_uncond = float(r.var())

    def sigma2_path(omega: float, alpha: float, beta: float) -> np.ndarray:
        sigma2 = np.empty_like(r)
        sigma2[0] = var_uncond
        for t in range(1, len(r)):
            sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
        return sigma2

    def neg_loglik(params: np.ndarray) -> float:
        omega, alpha, beta = params
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 0.9995:
            return 1e12
        sigma2 = sigma2_path(omega, alpha, beta)
        return float(0.5 * np.sum(np.log(2 * np.pi * sigma2) + r ** 2 / sigma2))

    result = minimize(neg_loglik, x0=np.array([var_uncond * 0.05, 0.08, 0.88]),
                      method="Nelder-Mead",
                      options={"maxiter": 3000, "xatol": 1e-8, "fatol": 1e-8})
    omega, alpha, beta = (float(v) for v in result.x)
    sigma2 = sigma2_path(omega, alpha, beta)
    std_residuals = r / np.sqrt(sigma2)
    persistence = alpha + beta
    return {
        "omega": omega, "alpha": alpha, "beta": beta,
        "persistence": float(persistence),
        "converged": bool(result.success and 0 < persistence < 1),
        "last_sigma2": float(sigma2[-1]),
        "last_r": float(r[-1]),
        "std_residuals": std_residuals,
        "sigma_bar": float(np.sqrt(sigma2[-1]) / GARCH_SCALE),
    }


# ------------------------------------------------------------ monte carlo

def monte_carlo(returns: np.ndarray, last_price: float, horizon: int = 96,
                paths: int = 2000, seed: int | None = None,
                bootstrap: bool = True) -> dict:
    """Simulación GARCH(1,1) con múltiples trayectorias.

    Mejora sobre los notebooks (una sola ruta con shocks normales):
    `paths` rutas y shocks por bootstrap de los residuos estandarizados
    reales — conserva colas gordas y asimetría.
    """
    fit = garch11_fit(returns)
    rng = np.random.default_rng(seed)
    omega, alpha, beta = fit["omega"], fit["alpha"], fit["beta"]

    sigma2 = np.full(paths, fit["last_sigma2"])
    r_prev = np.full(paths, fit["last_r"])
    log_price = np.full(paths, math.log(last_price))
    residual_pool = fit["std_residuals"]

    percentile_levels = [5, 25, 50, 75, 95]
    bands = np.empty((horizon, len(percentile_levels)))
    for t in range(horizon):
        shocks = (rng.choice(residual_pool, size=paths, replace=True) if bootstrap
                  else rng.standard_normal(paths))
        sigma2 = omega + alpha * r_prev ** 2 + beta * sigma2
        r_t = np.sqrt(sigma2) * shocks
        r_prev = r_t
        log_price += r_t / GARCH_SCALE
        bands[t] = np.percentile(np.exp(log_price), percentile_levels)

    final_prices = np.exp(log_price)
    return {
        "horizon": horizon,
        "paths": paths,
        "bootstrap": bootstrap,
        "last_price": last_price,
        "percentiles": percentile_levels,
        "bands": [[round(float(v), 4) for v in row] for row in bands],
        "prob_up": float(np.mean(final_prices > last_price)),
        "expected": float(np.median(final_prices)),
        "var95": float(last_price - np.percentile(final_prices, 5)),
        "range90": [float(np.percentile(final_prices, 5)),
                    float(np.percentile(final_prices, 95))],
        "garch": {"alpha": fit["alpha"], "beta": fit["beta"],
                  "persistence": fit["persistence"], "converged": fit["converged"]},
    }


# --------------------------------------------------------------- resumen

def analyze(symbol: str, interval: str = "15m") -> dict:
    """Batería completa con explicación y veredicto por estadístico."""
    returns, last_price = fetch_log_returns(symbol, interval)
    desc = describe(returns, interval)
    jb = jarque_bera(returns)
    lb_r = ljung_box(returns)
    lb_r2 = ljung_box(returns ** 2)
    adf = adf_test(returns)
    ar1 = ar1_fit(returns)
    garch = garch11_fit(returns)

    def card(id_, name, does, result, verdict, note):
        return {"id": id_, "name": name, "does": does, "result": result,
                "verdict": verdict, "note": note}

    cards = [
        card("desc", "Descripción de retornos",
             "Media, volatilidad, asimetría y curtosis de los retornos log.",
             f"n={desc['n']} · σ anual {desc['sigma_annual']:.1%} · skew {desc['skew']:+.2f} · curtosis {desc['kurtosis']:+.2f}",
             "ok" if desc["n"] >= 200 else "warn",
             "Curtosis > 0 = colas más gordas que la normal (lo habitual en mercados)."),
        card("jb", "Jarque-Bera (normalidad)",
             "Contrasta si los retornos siguen una distribución normal (H0: sí).",
             f"JB={jb['stat']:.1f} · p={jb['p']:.4f} → {'normales' if jb['normal'] else 'NO normales'}",
             "ok" if jb["normal"] else "warn",
             "Que falle es lo esperado: por eso el Monte Carlo usa bootstrap de residuos "
             "reales en vez de la normal (los notebooks usaban shocks normales)."),
        card("adf", "Dickey-Fuller (estacionariedad)",
             "¿Los retornos son estacionarios? Requisito para modelarlos (H0: raíz unitaria).",
             f"t={adf['stat']:.2f} vs crítico 5% {adf['critical']['5%']} → {'estacionarios' if adf['stationary'] else 'NO estacionarios'}",
             "ok" if adf["stationary"] else "fail",
             "Los retornos casi siempre lo son; si falla, desconfía del resto."),
        card("lb", "Ljung-Box sobre retornos",
             "¿Hay autocorrelación aprovechable en los retornos? (H0: independientes)",
             f"Q({lb_r['lags']})={lb_r['stat']:.1f} · p={lb_r['p']:.4f} → {'independientes' if lb_r['independent'] else 'autocorrelacionados'}",
             "ok" if lb_r["independent"] else "warn",
             "Si hay autocorrelación, un término AR aporta algo; si no, la parte ARIMA "
             "de los notebooks apenas pinta nada."),
        card("arch", "Efecto ARCH (Ljung-Box sobre r²)",
             "¿La volatilidad se agrupa en rachas? Es lo que justifica usar GARCH.",
             f"Q={lb_r2['stat']:.1f} · p={lb_r2['p']:.4f} → {'hay clustering' if not lb_r2['independent'] else 'sin clustering'}",
             "ok" if not lb_r2["independent"] else "warn",
             "Con clustering, el GARCH está justificado; sin él, bastaría σ constante."),
        card("ar1", "AR(1) sobre retornos",
             "Versión honesta del ARIMA(1,0,1) de los notebooks: ¿φ es significativo?",
             f"φ={ar1['phi']:+.3f} · p={ar1['p']:.4f} → {'significativo' if ar1['significant'] else 'no significativo'}",
             "ok" if ar1["significant"] else "warn",
             "Si no es significativo, la media prevista ≈ 0 y la proyección depende "
             "solo de la volatilidad (como debe ser)."),
        card("garch", "GARCH(1,1) media cero",
             "Modela la volatilidad condicional: σ²ₜ = ω + α·r²ₜ₋₁ + β·σ²ₜ₋₁ (MLE propia).",
             f"α={garch['alpha']:.3f} · β={garch['beta']:.3f} · persistencia {garch['persistence']:.3f} · σ̂ próxima barra {garch['sigma_bar']:.3%}",
             "ok" if garch["converged"] else "fail",
             "Persistencia < 1 y convergencia = modelo utilizable. Cerca de 1 = "
             "shocks de volatilidad muy duraderos."),
    ]
    return {"symbol": symbol, "interval": interval,
            "period": PERIOD_FOR_INTERVAL.get(interval, "7d"),
            "last_price": last_price, "cards": cards}
