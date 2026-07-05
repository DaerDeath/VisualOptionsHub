"""Sistema de calificación A-F (Cap. 2) y checklist de entrada (Cap. 7).

Del libro: "Cada operación empieza con una 'A' hipotética. A partir de ahí
se baja en la escala cada vez que encuentres un motivo para reducir riesgo
o no operar". El grado final determina la asignación máxima de capital.
"""

from __future__ import annotations

from dataclasses import dataclass, field

GRADES = ("A", "B", "C", "D", "F")

# Asignación máxima de cartera por grado (Cap. 2, "Grade-Level Risk Adjustments").
ALLOCATION_BY_GRADE: dict[str, tuple[float, float]] = {
    "A": (0.09, 0.10),   # hasta el 10% (o algo más); nunca >10-15% en una posición
    "B": (0.05, 0.09),
    "C": (0.02, 0.05),
    "D": (0.00, 0.02),
    "F": (0.00, 0.00),   # "no lo hagas si es posible"
}

GRADE_GUIDANCE: dict[str, str] = {
    "A": "Estrategias con más riesgo permitidas (risk reversal, double vertical…). Alta flexibilidad.",
    "B": "Verticales básicas y operaciones de riesgo limitado/alta probabilidad. Más cautela.",
    "C": "Solo bajo riesgo y alta probabilidad (verticales OTM). Salir antes de lo habitual.",
    "D": "Es un 'flier': asignación mínima, no encadenar varias seguidas.",
    "F": "No operar. Si es inevitable: asignación mínima y tomar beneficios rápido.",
}

# Criterios del checklist top-down del Cap. 2. Cada criterio NO cumplido
# reduce el grado un nivel.
CHECKLIST_CRITERIA: tuple[tuple[str, str], ...] = (
    ("market_direction", "1. La dirección del mercado (sentimiento) está en línea con la operación y no vas contra el consenso de analistas"),
    ("fund_knowledge", "2a. Conoces bien el negocio de la empresa y su sector"),
    ("fund_volume", "2b. Volumen suficiente (mínimo 750k acciones/día)"),
    ("fund_business", "2c. La dirección del negocio está en línea con la operación"),
    ("fund_top20", "2d. La acción está en el top 20% de su sector"),
    ("chart_trend", "3a. Tendencia de 6+ meses neutral o a favor"),
    ("chart_current", "3b. Últimos 30 días: sin sobreextensión (Bollinger) y medias 20/50/200 favorables"),
    ("chart_volume", "3c. El volumen favorece la tendencia deseada"),
    ("chart_macd", "3d. MACD con cruce fresco (≤3 barras) y estocásticos coherentes"),
    ("opt_volume", "4a. Volumen/open interest suficiente en las opciones (≥50 OI; ≥1000 contratos si la acción mueve >750k)"),
    ("opt_spreads", "4b. Bid-ask normales (>$0.20-0.30 de media es anormal salvo acciones >$200)"),
    ("opt_iv_fit", "4c. La IV relativa encaja con la estrategia (baja si compras prima, alta si vendes) y el mes elegido es favorable"),
    ("trade_specific", "5. Criterios específicos de la estrategia (p.ej. vertical vendida a ≥1σ y rendimiento ≥12-15%)"),
    ("timing_atr", "6a. La acción no ha movido ya más de su ATR en tu dirección hoy"),
    ("timing_event", "6b/c. No entras justo antes de un evento mayor (salvo estrategia neutral) ni en mala estación"),
    ("timing_chart", "6d. La entrada tiene sentido técnico (no hay un nivel mejor)"),
    ("timing_mental", "6e. Estado mental adecuado (sin frustración, prisa, enfado…)"),
)


@dataclass(frozen=True)
class GradeResult:
    grade: str
    failed: tuple[str, ...]
    allocation: tuple[float, float]
    guidance: str

    def summary(self) -> str:
        lo, hi = self.allocation
        lines = [
            f"Grado: {self.grade}",
            f"Asignación de cartera: {lo:.0%} – {hi:.0%}",
            f"Guía del libro: {self.guidance}",
        ]
        if self.failed:
            lines.append("Criterios no cumplidos:")
            labels = dict(CHECKLIST_CRITERIA)
            lines.extend(f"  ✗ {labels[key]}" for key in self.failed)
        else:
            lines.append("Todos los criterios cumplidos.")
        return "\n".join(lines)


def grade_trade(criteria: dict[str, bool]) -> GradeResult:
    """Aplica el sistema del Cap. 2: empieza en A y baja un nivel por fallo.

    criteria: dict clave→bool para las claves de CHECKLIST_CRITERIA. Las
    claves ausentes se consideran cumplidas (el libro permite adaptar la
    lista, pero sé estricto).
    """
    valid_keys = {key for key, _ in CHECKLIST_CRITERIA}
    unknown = set(criteria) - valid_keys
    if unknown:
        raise ValueError(f"criterios desconocidos: {sorted(unknown)}")
    failed = tuple(key for key, _ in CHECKLIST_CRITERIA if criteria.get(key, True) is False)
    level = min(len(failed), len(GRADES) - 1)
    grade = GRADES[level]
    return GradeResult(grade, failed, ALLOCATION_BY_GRADE[grade], GRADE_GUIDANCE[grade])


# Checklist previo a entrada en earnings (Cap. 7, "Checklist Before Entry").
EARNINGS_CHECKLIST: tuple[str, ...] = (
    "Convicción de analistas: ¿≥85% alcistas con objetivos ≥5-10% sobre el precio?",
    "¿Mejoras de analistas 1-2 semanas antes del informe, por encima del consenso?",
    "Objetivo de consenso ≥10% sobre el precio; ratio buys/sells ≥20% (holds cuentan según objetivo)",
    "Tendencias de industria/sector/producto: ¿vientos a favor?",
    "¿Hay grandes expectativas ya descontadas? (malo si las hay)",
    "¿Es la mejor de su sector (best in breed)?",
    "Comentario de la última llamada de resultados: ¿fuerte y sin sobrecompra frente a pares?",
    "P/E: trailing no >40% de la media del sector sin buena razón; forward <15% sobre la media",
    "Movimientos recientes: ¿fuera de bandas de Bollinger? ¿múltiplo menor que en el informe anterior?",
    "Correlación sorpresa/variación de precio: ¿cómo responde históricamente a sorpresas?",
    "HVol: ¿ha subido antes de earnings? ¿en una sola dirección? (rally previo resta recorrido)",
    "IVol/straddle: comparar straddle ATM (<10 días) como % del precio con el movimiento implícito a 1 día; "
    "si las opciones exceden en >20%, complementar con estrategia vega-corta",
    "Cobertura de analistas: preferible ≥4-5 analistas (menos sorpresas inesperadas)",
)

# Regla de breakeven para eventos (Cap. 7): sitúa tu breakeven al menos al
# 50% de la distancia del movimiento medio histórico en tu contra.
def earnings_breakeven_target(spot: float, avg_earnings_move_pct: float, bullish: bool) -> float:
    """Si la acción vale 100 y mueve de media 10%, breakeven ≤95 (alcista) o ≥105 (bajista)."""
    cushion = spot * avg_earnings_move_pct * 0.5
    return spot - cushion if bullish else spot + cushion
