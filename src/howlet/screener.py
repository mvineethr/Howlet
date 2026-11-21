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
`build_consensus_universe` builds that last one for you: every ticker
the tracked 13F managers hold, from their latest filings.

Results are cached to disk per (ticker, calendar day) - fundamentals
change quarterly and price daily, so re-screening the same day is fast.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .cache import CACHE_VERSION, FilingCache
from .client import EdgarClient
from .consensus import fetch_latest_portfolios
from .fundamentals import (
    FundamentalsClient,
    extract_annual_metrics,
    extract_shares_outstanding,
)
from .market import YahooMarketClient
from .presets import FAMOUS_INVESTORS
from .tickers import CusipTickerResolver, default_cache_dir

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
    price: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    eps_diluted: float | None = None
    revenue: float | None = None
    revenue_growth_pct: float | None = None
    net_margin_pct: float | None = None
    change_pct: float | None = None


class ScreenerCache:
    """Ticker -> {day: row_dict}, so a same-day re-screen skips network.

    Rows are held in memory and written to disk once by `save()` (called
    by `screen()` at the end of a run) instead of rewriting the whole
    JSON file per symbol - a 45-symbol screen used to be O(n^2) file I/O.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.path = (Path(cache_dir) if cache_dir else default_cache_dir()) / "screener_cache.json"
        self._data: dict | None = None  # lazily loaded from disk
        self._dirty = False  # True once put() has changed _data

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
                return {}
            data = raw.get("data")
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _ensure_loaded(self) -> None:
        if self._data is None:
            self._data = self._load()

    def get(self, symbol: str, day: str) -> dict | None:
        self._ensure_loaded()
        return self._data.get(symbol, {}).get(day)

    def put(self, symbol: str, day: str, row: dict) -> None:
        # In-memory only; the file is written once by save().
        self._ensure_loaded()
        self._data.setdefault(symbol, {})[day] = row
        self._dirty = True

    def save(self) -> None:
        """Flush in-memory rows to disk. No-op when nothing changed."""
        if not self._dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"version": CACHE_VERSION, "data": self._data}, f)
            self._dirty = False
        except OSError:
            pass


def build_consensus_universe(
    client: EdgarClient,
    cache: FilingCache | None = None,
    resolver: CusipTickerResolver | None = None,
) -> list[str]:
    """Every ticker the tracked 13F managers hold, sorted, deduplicated.

    The universe the screener was missing: instead of a hardcoded list
    that rots, screen what smart money actually owns. Pulls every
    tracked manager's latest 13F (disk-cached after the first run),
    unions the CUSIPs, and maps them to tickers via the OpenFIGI disk
    cache (same resolver the dashboard's holders view uses). CUSIPs
    with no ticker are skipped, not failed - a fund, a foreign listing,
    or an unmapped CUSIP just doesn't screen. Returns [] when no
    manager portfolio loads (all feeds down), so callers can fall back
    to DEFAULT_UNIVERSE.
    """
    portfolios = fetch_latest_portfolios(client, FAMOUS_INVESTORS, cache=cache)
    cusips = sorted({c for p in portfolios for c in p.positions})
    if not cusips:
        return []
    tickers = (resolver or CusipTickerResolver()).resolve(cusips)
    return sorted({t for t in tickers.values() if t})


def screen(
    market: YahooMarketClient,
    fundamentals: FundamentalsClient,
    universe: list[str] | None = None,
    cache: ScreenerCache | None = None,
    filters: dict[str, tuple[float | None, float | None]] | None = None,
) -> list[ScreenRow]:
    """Compute screen rows for `universe` (default: DEFAULT_UNIVERSE).

    `filters` maps field name -> (min, max) (either bound may be None).
    e.g. {"pe_ratio": (0, 25), "market_cap": (1e11, None)}.
    """
    universe = universe or DEFAULT_UNIVERSE
    today = date.today().isoformat()
    rows = []
    for symbol in universe:
        try:
            rows.append(_screen_one(symbol, market, fundamentals, cache, today))
        except Exception:
            continue  # one broken symbol must not kill the screen
    rows = [r for r in rows if r is not None]
    if filters:
        rows = [r for r in rows if _passes_filters(r, filters)]
    if cache is not None:
        cache.save()  # one file write for the whole run (see B3)
    return rows


def _screen_one(
    symbol: str,
    market: YahooMarketClient,
    fundamentals: FundamentalsClient,
    cache: ScreenerCache | None,
    today: str,
) -> ScreenRow | None:
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
        try:
            facts = fundamentals.get_company_facts(cik)
        except Exception:
            return None  # SEC hiccup on one symbol: skip it, like a quote failure
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
