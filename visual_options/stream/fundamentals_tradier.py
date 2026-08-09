"""Perfil de empresa vía la API beta de fundamentals de Tradier —
complementa (no reemplaza) la ficha de Empresa que ya sale de Yahoo en
fundamentals.py. Es la parte MENOS segura de todo lo que se integró de
Tradier en este toolkit: es una beta, no todos los planes la incluyen,
y la forma exacta del JSON no está tan documentada como el resto de la
API. Por eso la extracción es deliberadamente defensiva — busca las
claves esperadas en la estructura típica (`results[].tables.*`) y, si
no aparecen ahí, escanea el resto del payload por si la beta cambió de
forma; mejor devolver algunos campos vacíos que reventar. Si tu plan no
incluye el endpoint (403/404), devuelve {} sin más.
"""

from __future__ import annotations

TRADIER_URLS = {"sandbox": "https://sandbox.tradier.com/v1", "prod": "https://api.tradier.com/v1"}

_PROFILE_KEYS = ("sector", "industry", "long_business_summary", "description",
                 "website", "total_employee_number", "employees")


def _deep_find(payload: object, keys: tuple[str, ...]) -> dict:
    """Recorre el payload (dicts y listas anidadas) buscando cualquiera
    de `keys`; se queda con la primera ocurrencia no vacía de cada una."""
    found: dict = {}
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key in keys:
                if key not in found and node.get(key):
                    found[key] = node[key]
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


async def company_profile(symbol: str, token: str, env: str = "prod", client=None) -> dict:
    """`client` inyectable para tests. Nunca levanta por un plan sin
    acceso o un símbolo sin ficha — es un complemento opcional, no algo
    de lo que el resto de la vista dependa."""
    import httpx
    base = TRADIER_URLS.get(env, TRADIER_URLS["prod"])
    owns_client = client is None
    client = client or httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15.0)
    try:
        response = await client.get(f"{base}/beta/markets/fundamentals/company",
                                    params={"symbols": symbol.upper()})
        if response.status_code in (403, 404):
            return {}
        response.raise_for_status()
        found = _deep_find(response.json(), _PROFILE_KEYS)
        if not found:
            return {}
        summary = found.get("long_business_summary") or found.get("description") or ""
        return {
            "sector": found.get("sector"),
            "industry": found.get("industry"),
            "summary": summary[:420] or None,
            "website": found.get("website"),
            "employees": found.get("total_employee_number") or found.get("employees"),
        }
    finally:
        if owns_client:
            await client.aclose()
