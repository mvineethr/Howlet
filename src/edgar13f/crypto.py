"""Crypto market data: CoinGecko keyless tier, Coinpaprika fallback.

Both are free JSON APIs with no signup. CoinGecko's keyless tier allows
roughly 10-30 requests/minute and returns richer fields (24h high/low),
so it's primary; Coinpaprika (no key, generous limits) covers the same
core fields and is the automatic fallback when CoinGecko rate-limits or
breaks. A short in-memory TTL cache keeps the terminal well under both
limits no matter how often the screen refreshes.

Decoration tier: every failure degrades to an empty list, never raises.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINPAPRIKA_URL = "https://api.coinpaprika.com/v1/tickers"

# One fetch per minute is plenty for a market-cap table and stays far
# inside CoinGecko's keyless budget.
_CACHE_TTL_SECONDS = 60.0


class CryptoClient:
    """Top coins by market cap, normalized across both providers."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self._cache: tuple[float, str, list[dict]] = (0.0, "", [])

    def get_markets(self, limit: int = 50) -> tuple[str, list[dict]]:
        """(source, rows) for the top `limit` coins; ("", []) if all fail.

        Rows: {"rank", "symbol", "name", "price", "change_pct_24h",
        "market_cap", "volume_24h", "high_24h", "low_24h"} - the last two
        are None from the Coinpaprika fallback (it doesn't report them).
        """
        limit = min(limit, 100)
        cached_at, source, rows = self._cache
        if rows and time.monotonic() - cached_at < _CACHE_TTL_SECONDS:
            return source, rows[:limit]

        for source, fetch in (
            ("coingecko", self._from_coingecko),
            ("coinpaprika", self._from_coinpaprika),
        ):
            try:
                rows = fetch(limit)
            except (requests.RequestException, ValueError, KeyError, TypeError):
                continue
            if rows:
                self._cache = (time.monotonic(), source, rows)
                return source, rows
        return "", []

    def _from_coingecko(self, limit: int) -> list[dict]:
        resp = self.session.get(
            COINGECKO_URL,
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": str(limit),
                "page": "1",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [
            {
                "rank": c.get("market_cap_rank"),
                "symbol": (c.get("symbol") or "").upper(),
                "name": c.get("name"),
                "price": c.get("current_price"),
                "change_pct_24h": c.get("price_change_percentage_24h"),
                "market_cap": c.get("market_cap"),
                "volume_24h": c.get("total_volume"),
                "high_24h": c.get("high_24h"),
                "low_24h": c.get("low_24h"),
            }
            for c in resp.json()
            if isinstance(c, dict) and c.get("symbol")
        ]

    def _from_coinpaprika(self, limit: int) -> list[dict]:
        resp = self.session.get(
            COINPAPRIKA_URL, params={"limit": str(limit)}, timeout=15
        )
        resp.raise_for_status()
        rows = []
        for c in resp.json():
            if not isinstance(c, dict) or not c.get("symbol"):
                continue
            usd = (c.get("quotes") or {}).get("USD") or {}
            rows.append(
                {
                    "rank": c.get("rank"),
                    "symbol": c.get("symbol"),
                    "name": c.get("name"),
                    "price": usd.get("price"),
                    "change_pct_24h": usd.get("percent_change_24h"),
                    "market_cap": usd.get("market_cap"),
                    "volume_24h": usd.get("volume_24h"),
                    "high_24h": None,
                    "low_24h": None,
                }
            )
        rows.sort(key=lambda r: r["rank"] if r["rank"] is not None else 10**9)
        return rows
