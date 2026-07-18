"""FX cross rates from Frankfurter (ECB reference rates) - keyless.

frankfurter.dev republishes the European Central Bank's daily reference
rates as a free, keyless JSON API (the old api.frankfurter.app domain
301s to api.frankfurter.dev/v1 - use the new host directly). Rates are
official ECB fixings updated once per working day around 16:00 CET, not
live ticks - the Yahoo tape covers intraday; this powers the cross-rate
matrix.

One request fetches every rate against USD; cross rates are derived
(rate A->B = USD->B / USD->A). Decoration tier: {} on any failure.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"

# The matrix currencies: majors + the ones a US-centric terminal wants.
MATRIX_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CNY", "AUD", "CAD", "INR"]

# ECB fixes once per working day; an hour of cache is effectively free.
_CACHE_TTL_SECONDS = 3600.0

_cache: tuple[float, list, dict] = (0.0, [], {})


def get_fx_matrix(
    currencies: Optional[list[str]] = None,
    session: Optional[requests.Session] = None,
) -> dict:
    """Cross-rate matrix for the given currencies (default majors).

    Returns {"date": "YYYY-MM-DD", "currencies": [...],
    "matrix": {from: {to: rate}}} - matrix["EUR"]["JPY"] is how many JPY
    one EUR buys. {} on any failure.
    """
    global _cache
    currencies = [c.upper() for c in (currencies or MATRIX_CURRENCIES)]

    cached_at, cached_for, cached = _cache
    if cached and cached_for == currencies and (
        time.monotonic() - cached_at < _CACHE_TTL_SECONDS
    ):
        return cached

    session = session or requests.Session()
    others = [c for c in currencies if c != "USD"]
    try:
        resp = session.get(
            FRANKFURTER_URL,
            params={"base": "USD", "symbols": ",".join(others)},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return {}

    usd_rates = {"USD": 1.0}
    for currency, rate in (data.get("rates") or {}).items():
        if isinstance(rate, (int, float)) and rate > 0:
            usd_rates[currency.upper()] = float(rate)

    available = [c for c in currencies if c in usd_rates]
    if len(available) < 2:
        return {}

    matrix = {
        a: {b: usd_rates[b] / usd_rates[a] for b in available}
        for a in available
    }
    result = {
        "date": data.get("date"),
        "currencies": available,
        "matrix": matrix,
    }
    _cache = (time.monotonic(), currencies, result)
    return result
