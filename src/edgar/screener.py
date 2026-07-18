"""Security screener over a ticker universe.

Deliberately built ONLY from data sources this project already trusts:
SEC XBRL fundamentals (`fundamentals.py`) for EPS/shares/revenue, and the
Yahoo chart endpoint (`market.py`) for price - not Yahoo's `v7/finance/quote`
batch endpoint, which is now walled off behind the crumb auth (see
`yahoo_auth.py`) and would make a "quick screen 40 tickers" feature
fragile in exactly the wrong way.

This is NOT a full S&P 500 screener - there's no free, reliable, no-key
source for that index's live membership list that this project wants to
depend on. `DEFAULT_UNIVERSE` is a hand-picked set of large, liquid,
well-known names across sectors; pass your own `universe` (e.g. a
watchlist, or the union of tracked managers' holdings) for anything else.

Results are cached to disk per (ticker, calendar day) - fundamentals
change quarterly and price daily, so re-screening the same day is fast.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .fundamentals import (
    FundamentalsClient,
    extract_annual_metrics,
    extract_shares_outstanding,
)
from .market import YahooMarketClient
from .tickers import default_cache_dir

DEFAULT_UNIVERSE = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AVGO", "ORCL", "CRM",
    "ADBE", "AMD", "INTC", "CSCO", "IBM",
    # Financials
    "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS",
    # Healthcare
    "UNH", "JNJ", "MRK", "ABBV", "PFE", "TMO", "ABT",
    # Consumer
    "WMT", "PG", "HD", "COST", "KO", "PEP", "MCD", "NKE", "DIS", "NFLX",
    # Energy / Industrials
    "XOM", "CVX", "CAT", "BA", "LIN",
    # Telecom
    "T", "VZ",
]


@dataclass
class ScreenRow:
    symbol: str
    price: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps_diluted: Optional[float] = None
    revenue: Optional[float] = None
    revenue_growth_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None
    change_pct: Optional[float] = None


class ScreenerCache:
    """Ticker -> {day: row_dict}, so a same-day re-screen skips network."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.path = (Path(cache_dir) if cache_dir else default_cache_dir()) / "screener_cache.json"

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def get(self, symbol: str, day: str) -> Optional[dict]:
        return self._load().get(symbol, {}).get(day)

    def put(self, symbol: str, day: str, row: dict) -> None:
        try:
            data = self._load()
            data.setdefault(symbol, {})[day] = row
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass


def screen(
    market: YahooMarketClient,
    fundamentals: FundamentalsClient,
    universe: Optional[list[str]] = None,
    cache: Optional[ScreenerCache] = None,
    filters: Optional[dict[str, tuple[Optional[float], Optional[float]]]] = None,
) -> list[ScreenRow]:
    """Compute screen rows for `universe` (default: DEFAULT_UNIVERSE).

    `filters` maps field name -> (min, max) (either bound may be None).
    e.g. {"pe_ratio": (0, 25), "market_cap": (1e11, None)}.
    """
    universe = universe or DEFAULT_UNIVERSE
    today = date.today().isoformat()
    rows = [
        _screen_one(symbol, market, fundamentals, cache, today) for symbol in universe
    ]
    rows = [r for r in rows if r is not None]
    if filters:
        rows = [r for r in rows if _passes_filters(r, filters)]
    return rows


def _screen_one(
    symbol: str,
    market: YahooMarketClient,
    fundamentals: FundamentalsClient,
    cache: Optional[ScreenerCache],
    today: str,
) -> Optional[ScreenRow]:
    if cache is not None:
        cached = cache.get(symbol, today)
        if cached is not None:
            return ScreenRow(**cached)

    quote = market.get_quote(symbol, range_="5d", interval="1d")
    if quote is None:
        return None

    # One companyfacts fetch per symbol (it's a multi-MB payload) serves
    # both the annual metrics and the shares-outstanding figure.
    years: list = []
    shares = None
    cik = fundamentals.ticker_to_cik(symbol)
    if cik is not None:
        facts = fundamentals.get_company_facts(cik)
        years = extract_annual_metrics(facts, years=2)
        shares = extract_shares_outstanding(facts)
    row = _build_row(symbol, quote.price, quote.change_pct, shares, years)

    if cache is not None:
        cache.put(symbol, today, asdict(row))
    return row


def _build_row(symbol, price, change_pct, shares, years) -> ScreenRow:
    latest = years[0] if years else None
    prior = years[1] if len(years) > 1 else None

    eps = latest.eps_diluted if latest else None
    pe = price / eps if (eps and eps > 0) else None
    market_cap = price * shares if shares else None
    revenue = latest.revenue if latest else None
    net_margin = (
        latest.net_income / latest.revenue * 100.0
        if latest and latest.revenue and latest.net_income is not None
        else None
    )
    rev_growth = (
        (latest.revenue - prior.revenue) / prior.revenue * 100.0
        if latest and prior and prior.revenue and latest.revenue is not None
        else None
    )
    return ScreenRow(
        symbol=symbol,
        price=price,
        market_cap=market_cap,
        pe_ratio=pe,
        eps_diluted=eps,
        revenue=revenue,
        revenue_growth_pct=rev_growth,
        net_margin_pct=net_margin,
        change_pct=change_pct,
    )


def _passes_filters(row: ScreenRow, filters: dict) -> bool:
    for field, (lo, hi) in filters.items():
        value = getattr(row, field, None)
        if value is None:
            return False
        if lo is not None and value < lo:
            return False
        if hi is not None and value > hi:
            return False
    return True
