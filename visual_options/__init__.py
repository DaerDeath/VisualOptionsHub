"""visual-options: toolkit de opciones basado en Visual Guide to Options (Jared Levy).

Capítulos del libro → módulos:
  Cap. 1-2  fundamentos y herramientas  → pricing, volatility, grading
  Cap. 3    griegas                     → greeks
  Cap. 4-6  estrategias                 → strategies
  Cap. 7    riesgo y volatilidad        → grading (checklist), volatility
"""

from visual_options.contracts import OptionLeg, StockLeg
from visual_options.strategies import STRATEGY_BUILDERS, Strategy
from visual_options import builders as _builders  # puebla STRATEGY_BUILDERS

__all__ = ["OptionLeg", "StockLeg", "Strategy", "STRATEGY_BUILDERS"]
__version__ = "0.1.0"
