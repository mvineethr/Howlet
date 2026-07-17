"""Shared, JSON-ready view builders for the dashboard and the MCP server.

Both frontends (the Flask web terminal and the `edgar13f mcp` AI tool
server) call these functions, so a browser user and an AI agent always
see the same numbers. Everything returns plain dicts/lists.

Functions raise LookupError for "no such manager/ticker" so callers can
map that to a 404 / tool error without parsing messages.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

from .cache import (
    FilingCache,
    Form4Cache,
    cached_form4_transactions,
    cached_information_table,
)
from .client import EdgarClient
from .consensus import build_consensus_rows, fetch_latest_portfolios
from .crypto import CryptoClient
from .diff import STATUS_ORDER, diff_holdings
from .events import CorporateEventsClient, get_fed_events, get_shareholder_meetings
from .form4 import TRANSACTION_CODE_LABELS, list_form4_filings
from .fundamentals import FundamentalsClient
from .indicators import (
    bollinger_bands,
    ema,
    macd,
    opening_range_breakout,
    rsi,
    sma,
)
from .market import Quote, YahooMarketClient
from .news import NewsClient
from .options import OptionsClient
from .presets import FAMOUS_INVESTORS
from .risk import analyze_portfolio
from .screener import DEFAULT_UNIVERSE, ScreenerCache, screen
from .tickers import CusipTickerResolver
from .yahoo_auth import YahooAuthSession

# The "world tape": broad indices, vol, rates, energy, metals, crypto, FX.
TAPE_SYMBOLS = [
    ("^GSPC", "S&P 500"),
    ("^IXIC", "NASDAQ"),
    ("^DJI", "DOW"),
    ("^RUT", "RUSSELL 2K"),
    ("^VIX", "VIX"),
    ("^TNX", "US 10Y"),
    ("CL=F", "WTI CRUDE"),
    ("GC=F", "GOLD"),
    ("BTC-USD", "BITCOIN"),
    ("EURUSD=X", "EUR/USD"),
]

# The MKTS screen: world equity indices, FX, commodities, crypto.
MARKET_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("AMERICAS", [
        ("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ COMP"), ("^DJI", "DOW JONES"),
        ("^RUT", "RUSSELL 2000"), ("^VIX", "VIX"), ("^GSPTSE", "TSX (CANADA)"),
        ("^BVSP", "BOVESPA (BRAZIL)"), ("^MXX", "IPC (MEXICO)"),
    ]),
    ("EMEA", [
        ("^FTSE", "FTSE 100"), ("^GDAXI", "DAX"), ("^FCHI", "CAC 40"),
        ("^STOXX50E", "EURO STOXX 50"), ("^IBEX", "IBEX 35"),
        ("FTSEMIB.MI", "FTSE MIB"), ("^SSMI", "SMI (SWISS)"),
    ]),
    ("ASIA/PACIFIC", [
        ("^N225", "NIKKEI 225"), ("^HSI", "HANG SENG"),
        ("000001.SS", "SHANGHAI COMP"), ("^KS11", "KOSPI"),
        ("^AXJO", "ASX 200"), ("^BSESN", "SENSEX"), ("^TWII", "TAIEX"),
    ]),
    ("FX", [
        ("EURUSD=X", "EUR/USD"), ("GBPUSD=X", "GBP/USD"), ("USDJPY=X", "USD/JPY"),
        ("USDCNY=X", "USD/CNY"), ("USDINR=X", "USD/INR"), ("AUDUSD=X", "AUD/USD"),
        ("DX-Y.NYB", "DOLLAR INDEX"),
    ]),
    ("COMMODITIES & RATES", [
        ("CL=F", "WTI CRUDE"), ("BZ=F", "BRENT"), ("NG=F", "NAT GAS"),
        ("GC=F", "GOLD"), ("SI=F", "SILVER"), ("HG=F", "COPPER"),
        ("ZW=F", "WHEAT"), ("^TNX", "US 10Y YLD"), ("^FVX", "US 5Y YLD"),
    ]),
]
# (Crypto is deliberately NOT a section here: the MKTS screen has a
# STOCKS/CRYPTO toggle and crypto_view below serves the CRYPTO side with
# real market-cap data instead of a handful of hardcoded Yahoo symbols.)


class Services:
    """Shared clients + a lock that serializes EDGAR access."""

    def __init__(self, user_agent: str, cache_dir: Optional[Path] = None):
        self.edgar = EdgarClient(user_agent)
        self.market = YahooMarketClient()
        self.news = NewsClient()
        self.resolver = CusipTickerResolver(cache_dir=cache_dir)
        self.cache = FilingCache(cache_dir=cache_dir)
        self.form4_cache = Form4Cache(cache_dir=cache_dir)
        self.fundamentals = FundamentalsClient(self.edgar)
        self.edgar_lock = threading.Lock()

        # events + options share one crumb/cookie session (one crumb
        # fetch instead of two) since both hit Yahoo's walled endpoints.
        yahoo_auth = YahooAuthSession()
        self.events = CorporateEventsClient(auth=yahoo_auth)
        self.options = OptionsClient(auth=yahoo_auth)
        self.screener_cache = ScreenerCache(cache_dir=cache_dir)
        self.crypto = CryptoClient()


def resolve_cik(identifier: str) -> str:
    key = identifier.strip().lower()
    return FAMOUS_INVESTORS.get(key, identifier.strip())


def _quote_dict(q: Quote, with_history: bool = False) -> dict:
    d = {
        "symbol": q.symbol,
        "name": q.long_name,
        "exchange": q.exchange,
        "instrument_type": q.instrument_type,
        "currency": q.currency,
        "price": q.price,
        "change": q.change,
        "change_pct": q.change_pct,
        "previous_close": q.previous_close,
        "day_low": q.day_low,
        "day_high": q.day_high,
        "week52_low": q.week52_low,
        "week52_high": q.week52_high,
        "volume": q.volume,
    }
    if with_history:
        d["history_ts"] = q.history_ts
        d["history_close"] = q.sparkline
        d["history_open"] = q.history_open
        d["history_high"] = q.history_high
        d["history_low"] = q.history_low
        d["history_volume"] = q.history_volume
    return d


def _apply_name_fallback(
    svc: Services, tickers: dict, unresolved: dict[str, str]
) -> None:
    """Fill tickers OpenFIGI couldn't map by matching issuer names
    against SEC's company_tickers.json (keyless; e.g. Chubb's H1467J104).
    Successful matches are written back to the resolver's disk cache so
    the fallback runs at most once per CUSIP per machine."""
    if not unresolved:
        return
    with svc.edgar_lock:
        for cusip, issuer in unresolved.items():
            ticker = svc.fundamentals.name_to_ticker(issuer)
            if ticker:
                tickers[cusip] = ticker
                svc.resolver.learn(cusip, ticker)


# ---------------------------------------------------------------------- #
# 13F views
# ---------------------------------------------------------------------- #

def managers_view() -> list[dict]:
    seen: set[str] = set()
    result = []
    for label, cik in FAMOUS_INVESTORS.items():
        if cik in seen:
            continue
        seen.add(cik)
        result.append({"label": label, "cik": cik})
    return result


def portfolio_view(svc: Services, identifier: str, top: int = 25) -> dict:
    """A manager's latest 13F, aggregated by CUSIP and joined with quotes."""
    top = min(top, 100)
    cik = resolve_cik(identifier)

    with svc.edgar_lock:
        filings = svc.edgar.list_13f_filings(cik, limit=1)
        if not filings:
            raise LookupError(f"No 13F-HR filings for '{identifier}'")
        filing = filings[0]
        holdings = cached_information_table(svc.edgar, svc.cache, filing)

    # One row per CUSIP (filers often split a security across entries).
    agg: dict[str, dict] = {}
    for h in holdings:
        entry = agg.setdefault(
            h.cusip,
            {
                "issuer": h.name_of_issuer,
                "cusip": h.cusip,
                "value_usd": 0,
                "shares": 0,
                "share_type": h.share_type,
            },
        )
        entry["value_usd"] += h.value_usd
        entry["shares"] += h.shares

    rows = sorted(agg.values(), key=lambda r: r["value_usd"], reverse=True)
    total = sum(r["value_usd"] for r in rows)
    for r in rows:
        r["weight_pct"] = r["value_usd"] / total * 100.0 if total else 0.0

    top_rows = rows[:top]
    # Only equity-type positions get ticker/quote decoration.
    cusips = [r["cusip"] for r in top_rows if r["share_type"] != "PRN"]
    tickers = svc.resolver.resolve(cusips)
    _apply_name_fallback(
        svc,
        tickers,
        {
            r["cusip"]: r["issuer"]
            for r in top_rows
            if r["share_type"] != "PRN" and not tickers.get(r["cusip"])
        },
    )
    symbols = sorted({t for t in tickers.values() if t})
    quotes = svc.market.get_quotes(symbols)

    for r in top_rows:
        ticker = tickers.get(r["cusip"])
        r["ticker"] = ticker
        q = quotes.get(ticker) if ticker else None
        r["price"] = q.price if q else None
        r["change_pct"] = q.change_pct if q else None
        r["currency"] = q.currency if q else None
        r["sparkline"] = q.sparkline if q else []

    return {
        "identifier": identifier,
        "cik": filing.cik,
        "period_of_report": (
            filing.period_of_report.isoformat() if filing.period_of_report else None
        ),
        "filing_date": filing.filing_date.isoformat(),
        "accession_number": filing.accession_number,
        "total_value_usd": total,
        "position_count": len(rows),
        "positions": top_rows,
    }


def diff_view(svc: Services, identifier: str) -> dict:
    """What changed between a manager's two most recent filings."""
    cik = resolve_cik(identifier)
    with svc.edgar_lock:
        filings = svc.edgar.list_13f_filings(cik, limit=2)
        if len(filings) < 2:
            raise LookupError(
                f"Need 2 filings to diff; found {len(filings)} for '{identifier}'"
            )
        current_f, prior_f = filings[0], filings[1]
        prior = cached_information_table(svc.edgar, svc.cache, prior_f)
        current = cached_information_table(svc.edgar, svc.cache, current_f)

    changes = [c for c in diff_holdings(prior, current) if c.status != "UNCHANGED"]
    changes.sort(key=lambda c: (STATUS_ORDER[c.status], -abs(c.value_change_usd)))
    return {
        "prior_period": (
            prior_f.period_of_report.isoformat() if prior_f.period_of_report else None
        ),
        "current_period": (
            current_f.period_of_report.isoformat()
            if current_f.period_of_report
            else None
        ),
        "changes": [
            {
                "issuer": c.name_of_issuer,
                "cusip": c.cusip,
                "status": c.status,
                "value_change_usd": c.value_change_usd,
                "shares_change": c.shares_change,
                "current_value_usd": c.current_value_usd,
            }
            for c in changes
        ],
    }


def consensus_view(svc: Services, min_managers: int = 2, limit: int = 20) -> dict:
    """Cross-manager holdings overlap across the tracked presets."""
    with svc.edgar_lock:
        portfolios = fetch_latest_portfolios(
            svc.edgar, FAMOUS_INVESTORS, cache=svc.cache
        )
    rows = build_consensus_rows(portfolios, min_managers=min_managers)[:limit]
    return {
        "managers": [
            {"label": p.label, "period_of_report": p.period_of_report}
            for p in portfolios
        ],
        "rows": [
            {
                "issuer": r.name_of_issuer,
                "cusip": r.cusip,
                "manager_count": r.manager_count,
                "total_value_usd": r.total_value_usd,
                "combined_weight_pct": r.combined_weight_pct,
                "weights_pct": r.weights_pct,
            }
            for r in rows
        ],
    }


def holders_view(svc: Services, symbol: str) -> dict:
    """Bloomberg HDS-style: which tracked managers hold this ticker.

    Resolves every CUSIP across the tracked managers' latest filings
    (answers are disk-cached forever, so this is slow exactly once).
    """
    symbol_u = symbol.upper()
    with svc.edgar_lock:
        portfolios = fetch_latest_portfolios(
            svc.edgar, FAMOUS_INVESTORS, cache=svc.cache
        )

    all_cusips = sorted({c for p in portfolios for c in p.positions})
    tickers = svc.resolver.resolve(all_cusips)
    _apply_name_fallback(
        svc,
        tickers,
        {
            c: p.positions[c]["name_of_issuer"]
            for p in portfolios
            for c in p.positions
            if not tickers.get(c)
        },
    )
    matching = {c for c, t in tickers.items() if t and t.upper() == symbol_u}

    holders = []
    for p in portfolios:
        total = p.total_value_usd
        for cusip in matching:
            pos = p.positions.get(cusip)
            if not pos:
                continue
            holders.append(
                {
                    "manager": p.label,
                    "period_of_report": p.period_of_report,
                    "cusip": cusip,
                    "issuer": pos["name_of_issuer"],
                    "shares": pos["shares"],
                    "value_usd": pos["value_usd"],
                    "weight_pct": (
                        pos["value_usd"] / total * 100.0 if total else 0.0
                    ),
                }
            )
    holders.sort(key=lambda h: h["value_usd"], reverse=True)
    return {
        "symbol": symbol_u,
        "tracked_managers": [p.label for p in portfolios],
        "holders": holders,
    }


def position_history_view(
    svc: Services, identifier: str, query: str, quarters: int = 8
) -> dict:
    """One manager's stake in one security across N quarters of 13Fs.

    `query` is a ticker (resolved against the manager's own CUSIPs, so
    no extra OpenFIGI lookups beyond what the portfolio views already
    cache), a raw 9-char CUSIP, or an issuer-name substring fallback.
    Rows are chronological (oldest first) for charting; quarters where
    the manager didn't report the name have shares=0 and held=false.
    """
    quarters = min(quarters, 40)
    cik = resolve_cik(identifier)
    query_u = query.strip().upper()

    with svc.edgar_lock:
        filings = svc.edgar.list_13f_filings(cik, limit=quarters)
        if not filings:
            raise LookupError(f"No 13F-HR filings for '{identifier}'")
        per_filing: list[tuple] = []  # (filing, {cusip: agg}, total)
        for f in filings:
            holdings = cached_information_table(svc.edgar, svc.cache, f)
            agg: dict[str, dict] = {}
            for h in holdings:
                entry = agg.setdefault(
                    h.cusip,
                    {"issuer": h.name_of_issuer, "value_usd": 0, "shares": 0},
                )
                entry["value_usd"] += h.value_usd
                entry["shares"] += h.shares
            per_filing.append((f, agg, sum(e["value_usd"] for e in agg.values())))

    # Which CUSIP(s) is the user asking about?
    all_cusips = sorted({c for _, agg, _ in per_filing for c in agg})
    if query_u in all_cusips:
        matching = {query_u}
    else:
        tickers = svc.resolver.resolve(all_cusips)
        matching = {c for c, t in tickers.items() if t and t.upper() == query_u}
        if not matching:
            # Name fallback: free, no extra requests (e.g. "chubb").
            matching = {
                c
                for _, agg, _ in per_filing
                for c, e in agg.items()
                if query_u in e["issuer"].upper()
            }
    if not matching:
        raise LookupError(
            f"'{identifier}' didn't report anything matching '{query}' "
            f"in the last {len(filings)} 13F filings"
        )

    issuer = next(
        e["issuer"]
        for _, agg, _ in per_filing
        for c, e in agg.items()
        if c in matching
    )
    rows = []
    for f, agg, total in reversed(per_filing):  # oldest first
        shares = sum(agg[c]["shares"] for c in matching if c in agg)
        value = sum(agg[c]["value_usd"] for c in matching if c in agg)
        rows.append(
            {
                "period_of_report": (
                    f.period_of_report.isoformat() if f.period_of_report else None
                ),
                "filing_date": f.filing_date.isoformat(),
                "shares": shares,
                "value_usd": value,
                "weight_pct": value / total * 100.0 if total else 0.0,
                "held": any(c in agg for c in matching),
            }
        )
    return {
        "identifier": identifier,
        "cik": svc.edgar.pad_cik(cik),
        "query": query,
        "issuer": issuer,
        "cusips": sorted(matching),
        "quarters": rows,
    }


def insiders_view(svc: Services, symbol: str, filings: int = 15) -> dict:
    """Form 4 insider transactions for a company (Bloomberg-style GP/II).

    `filings` is how many recent Form 4 filings to scan (each is one SEC
    request on a cache miss, cached forever afterwards). Only
    non-derivative rows are returned; the open-market signal is
    transaction codes P (purchase) and S (sale) - everything else is
    mostly compensation mechanics (grants, RSU vests, tax withholding).
    """
    filings = min(filings, 40)
    with svc.edgar_lock:
        cik = svc.fundamentals.ticker_to_cik(symbol)
        if cik is None:
            raise LookupError(
                f"SEC has no filer for ticker '{symbol}' (foreign or non-equity?)"
            )
        company = svc.fundamentals.company_name(symbol)
        form4s = list_form4_filings(svc.edgar, cik, limit=filings)
        transactions = []
        for f in form4s:
            transactions.extend(
                cached_form4_transactions(svc.edgar, svc.form4_cache, f)
            )

    transactions.sort(
        key=lambda t: (t.transaction_date or "", t.filing_date), reverse=True
    )
    purchases = [t for t in transactions if t.transaction_code == "P"]
    sales = [t for t in transactions if t.transaction_code == "S"]
    return {
        "symbol": symbol.upper(),
        "cik": cik,
        "company": company,
        "filings_scanned": len(form4s),
        "summary": {
            "open_market_purchases": len(purchases),
            "purchase_shares": sum(t.shares for t in purchases),
            "purchase_value_usd": sum(t.value_usd or 0 for t in purchases),
            "open_market_sales": len(sales),
            "sale_shares": sum(t.shares for t in sales),
            "sale_value_usd": sum(t.value_usd or 0 for t in sales),
        },
        "transactions": [
            {
                "insider": t.insider_name,
                "relationship": t.relationship,
                "date": t.transaction_date,
                "code": t.transaction_code,
                "code_label": TRANSACTION_CODE_LABELS.get(
                    t.transaction_code, t.transaction_code
                ),
                "acquired_disposed": t.acquired_disposed,
                "shares": t.shares,
                "price_per_share": t.price_per_share,
                "value_usd": t.value_usd,
                "shares_owned_after": t.shares_owned_after,
                "security_title": t.security_title,
                "direct_or_indirect": t.direct_or_indirect,
                "filing_date": t.filing_date,
                "accession_number": t.accession_number,
            }
            for t in transactions
        ],
    }


# ---------------------------------------------------------------------- #
# market views
# ---------------------------------------------------------------------- #

def tape_view(svc: Services) -> list[dict]:
    quotes = svc.market.get_quotes([s for s, _ in TAPE_SYMBOLS], range_="5d")
    rows = []
    for symbol, label in TAPE_SYMBOLS:
        q = quotes.get(symbol)
        if q is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "label": label,
                "price": q.price,
                "change": q.change,
                "change_pct": q.change_pct,
            }
        )
    return rows


def security_view(svc: Services, symbol: str, range_: str = "6mo") -> dict:
    """Bloomberg DES/GP-style: full quote detail + chartable history.

    The chart uses the requested range; price/change stats come from a
    separate daily-bar quote so "CHANGE" is always the day move, never
    the drift over whatever chart range happens to be selected.
    """
    q = svc.market.get_security(symbol, range_=range_)
    if q is None:
        raise LookupError(f"No market data for symbol '{symbol}'")
    d = _quote_dict(q, with_history=True)
    d["range"] = range_
    if len(q.sparkline) >= 2 and q.sparkline[0]:
        d["range_change_pct"] = (
            (q.sparkline[-1] - q.sparkline[0]) / q.sparkline[0] * 100.0
        )
    else:
        d["range_change_pct"] = None

    daily = svc.market.get_quote(symbol, range_="5d", interval="1d")
    if daily is not None:
        d["price"] = daily.price
        d["previous_close"] = daily.previous_close
        d["change"] = daily.change
        d["change_pct"] = daily.change_pct
        d["volume"] = daily.volume or d["volume"]

    d["studies"] = _studies_dict(q.sparkline)
    d["orb"] = _orb_dict(svc, symbol)
    return d


def _studies_dict(closes: list[float]) -> dict:
    """Latest value of each study (chart series aren't sent - the caller
    already has close history and can recompute if it wants a full line)."""
    if len(closes) < 2:
        return {}
    macd_result = macd(closes)
    bb = bollinger_bands(closes)

    def last(series):
        return next((v for v in reversed(series) if v is not None), None)

    return {
        "sma20": last(sma(closes, 20)),
        "sma50": last(sma(closes, 50)),
        "ema12": last(ema(closes, 12)),
        "ema26": last(ema(closes, 26)),
        "rsi14": last(rsi(closes, 14)),
        "macd": last(macd_result.macd),
        "macd_signal": last(macd_result.signal),
        "macd_histogram": last(macd_result.histogram),
        "bollinger_upper": last(bb.upper),
        "bollinger_mid": last(bb.mid),
        "bollinger_lower": last(bb.lower),
    }


def _orb_dict(svc: Services, symbol: str, opening_bars: int = 6) -> Optional[dict]:
    """Opening-range breakout needs today's own intraday bars (5-min), not
    the daily-bar history the main chart uses - a fresh, separate fetch."""
    intraday = svc.market.get_quote(symbol, range_="1d", interval="5m")
    if intraday is None:
        return None
    orb = opening_range_breakout(
        intraday.history_high, intraday.history_low, intraday.sparkline,
        opening_bars=opening_bars,
    )
    if orb is None:
        return None
    return {
        "range_high": orb.range_high,
        "range_low": orb.range_low,
        "last_price": orb.last_price,
        "status": orb.status,
        "breakout_pct": orb.breakout_pct,
    }


def quotes_view(svc: Services, symbols: list[str]) -> list[dict]:
    quotes = svc.market.get_quotes(symbols, range_="5d")
    return [
        _quote_dict(quotes[s]) | {"sparkline": quotes[s].sparkline}
        for s in symbols
        if s in quotes
    ]


def markets_view(svc: Services) -> list[dict]:
    """The MKTS screen: world indices / FX / commodities / crypto."""
    all_symbols = [s for _, pairs in MARKET_SECTIONS for s, _ in pairs]
    quotes = svc.market.get_quotes(all_symbols, range_="5d")
    sections = []
    for section, pairs in MARKET_SECTIONS:
        rows = []
        for symbol, label in pairs:
            q = quotes.get(symbol)
            if q is None:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "label": label,
                    "price": q.price,
                    "change_pct": q.change_pct,
                    "sparkline": q.sparkline,
                }
            )
        sections.append({"section": section, "rows": rows})
    return sections


def crypto_view(svc: Services, limit: int = 50) -> dict:
    """The CRYPTO side of the MKTS screen: top coins by market cap from
    CoinGecko's keyless tier (Coinpaprika fallback). Rows may be empty
    if both providers are unreachable - the UI shows "unavailable"."""
    source, rows = svc.crypto.get_markets(limit=limit)
    return {"source": source, "rows": rows}


def regulatory_view(limit: int = 20) -> list[dict]:
    """Newest SEC rulemaking/notices from the Federal Register (keyless
    official source). Empty list when the API is unreachable."""
    from . import regulatory

    return regulatory.get_sec_documents(limit=limit)


def facts_view(svc: Services, symbol: str, years: int = 5) -> dict:
    """Bloomberg FA-style: annual headline financials from SEC XBRL."""
    with svc.edgar_lock:
        cik = svc.fundamentals.ticker_to_cik(symbol)
        if cik is None:
            raise LookupError(
                f"SEC has no filer for ticker '{symbol}' (foreign or non-equity?)"
            )
        name = svc.fundamentals.company_name(symbol)
        rows = svc.fundamentals.annual_metrics(symbol, years=years)
    return {
        "symbol": symbol.upper(),
        "cik": cik,
        "company": name,
        "fiscal_years": [
            {
                "fiscal_year": r.fiscal_year,
                "end_date": r.end_date,
                "revenue": r.revenue,
                "net_income": r.net_income,
                "eps_diluted": r.eps_diluted,
                "total_assets": r.total_assets,
                "total_liabilities": r.total_liabilities,
                "stockholders_equity": r.stockholders_equity,
                "operating_cash_flow": r.operating_cash_flow,
            }
            for r in rows
        ],
    }


def events_view(svc: Services, symbol: str) -> dict:
    """Bloomberg-style corporate calendar: earnings date, analyst
    recommendation mix, and recent proxy (DEF 14A) shareholder-meeting
    filings. Sections independently degrade - a Yahoo hiccup doesn't
    hide the (fully reliable) SEC proxy-filing section, and vice versa.
    """
    earnings = svc.events.get_earnings_info(symbol)
    with svc.edgar_lock:
        cik = svc.fundamentals.ticker_to_cik(symbol)
        meetings = get_shareholder_meetings(svc.edgar, cik) if cik else []

    return {
        "symbol": symbol.upper(),
        "next_earnings_date": earnings.next_earnings_date if earnings else None,
        "analyst_recommendation": earnings.analyst_recommendation if earnings else None,
        "analyst_counts": (
            {
                "strong_buy": earnings.strong_buy,
                "buy": earnings.buy,
                "hold": earnings.hold,
                "sell": earnings.sell,
                "strong_sell": earnings.strong_sell,
            }
            if earnings
            else None
        ),
        "shareholder_meetings": meetings,
    }


def fed_events_view(limit: int = 20) -> list[dict]:
    """Recent FOMC statements + Fed speeches (official Fed RSS feeds)."""
    items = get_fed_events(limit=limit)
    return [
        {
            "title": i.title,
            "link": i.link,
            "source": i.source,
            "published": i.published.isoformat() if i.published else None,
        }
        for i in items
    ]


def macro_view() -> dict:
    """Fixed-income + macro snapshot: Treasury yield curve (always on),
    BLS headline series (keyless), and FRED series IF the user has set
    FRED_API_KEY - the one optional, key-gated source in this project.
    """
    from . import macro

    curve = macro.get_treasury_yield_curve()
    bls = macro.get_bls_series(list(macro.BLS_SERIES.values()))
    bls_by_label = {
        label: bls.get(series_id, [])
        for label, series_id in macro.BLS_SERIES.items()
    }
    fred_available = bool(os.environ.get("FRED_API_KEY"))
    return {
        "treasury_yield_curve": curve,
        "bls_series": bls_by_label,
        "fred_available": fred_available,
        "fred_series": macro.get_fred_snapshot() if fred_available else {},
    }


def screener_view(
    svc: Services,
    universe: Optional[list[str]] = None,
    filters: Optional[dict[str, tuple[Optional[float], Optional[float]]]] = None,
) -> dict:
    """Screen a ticker universe (default: a curated large-cap list - see
    `screener.py` for why this isn't a full S&P 500 screen) by valuation
    and growth metrics built from SEC fundamentals + Yahoo price.
    """
    rows = screen(
        svc.market, svc.fundamentals, universe=universe,
        cache=svc.screener_cache, filters=filters,
    )
    return {
        "universe_size": len(universe or DEFAULT_UNIVERSE),
        "matched": len(rows),
        "rows": [
            {
                "symbol": r.symbol,
                "price": r.price,
                "change_pct": r.change_pct,
                "market_cap": r.market_cap,
                "pe_ratio": r.pe_ratio,
                "eps_diluted": r.eps_diluted,
                "revenue": r.revenue,
                "revenue_growth_pct": r.revenue_growth_pct,
                "net_margin_pct": r.net_margin_pct,
            }
            for r in rows
        ],
    }


def options_view(svc: Services, symbol: str, expiration: Optional[str] = None) -> dict:
    """Bloomberg OMON-style: an options chain (calls + puts) for one
    expiration. Raises LookupError if the (unofficial) options endpoint
    is unavailable or the symbol has no listed options.
    """
    chain = svc.options.get_option_chain(symbol, expiration=expiration)
    if chain is None:
        raise LookupError(
            f"No options data for '{symbol}' (no listed options, or Yahoo's "
            "options endpoint is temporarily unavailable)"
        )
    return {
        "symbol": chain.symbol,
        "underlying_price": chain.underlying_price,
        "expiration_dates": chain.expiration_dates,
        "selected_expiration": chain.selected_expiration,
        "calls": [_contract_dict(c) for c in chain.calls],
        "puts": [_contract_dict(p) for p in chain.puts],
    }


def _contract_dict(c) -> dict:
    return {
        "contract_symbol": c.contract_symbol,
        "strike": c.strike,
        "last_price": c.last_price,
        "bid": c.bid,
        "ask": c.ask,
        "volume": c.volume,
        "open_interest": c.open_interest,
        "implied_volatility": c.implied_volatility,
        "in_the_money": c.in_the_money,
    }


def risk_view(svc: Services, holdings: list[dict], range_: str = "1y") -> dict:
    """Volatility/drawdown/Sharpe for a user-defined portfolio.

    `holdings` is [{"symbol": "AAPL", "shares": 10}, ...] - a personal
    position list, NOT a 13F manager (see `portfolio_view` for that).
    Symbols Yahoo can't price are silently dropped from the analysis.
    """
    priced: dict[str, tuple[float, list[float]]] = {}
    for h in holdings:
        symbol, shares = h["symbol"], float(h["shares"])
        q = svc.market.get_security(symbol, range_=range_)
        if q is None or len(q.sparkline) < 2:
            continue
        priced[symbol] = (shares * q.price, q.sparkline)

    result = analyze_portfolio(priced)
    if result is None:
        return {"positions": [], "error": "Not enough price history to analyze."}
    return {
        "portfolio_return_pct": result.portfolio_return_pct,
        "portfolio_annualized_volatility_pct": result.portfolio_annualized_volatility_pct,
        "portfolio_max_drawdown_pct": result.portfolio_max_drawdown_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "positions": [
            {
                "symbol": p.symbol,
                "weight_pct": p.weight_pct,
                "return_pct": p.return_pct,
                "annualized_volatility_pct": p.annualized_volatility_pct,
                "max_drawdown_pct": p.max_drawdown_pct,
            }
            for p in result.positions
        ],
    }


def news_view(
    svc: Services, symbols: Optional[list[str]] = None, limit: int = 30
) -> list[dict]:
    limit = min(limit, 100)
    if symbols:
        items = svc.news.get_ticker_news(symbols[:10], limit=limit)
    else:
        items = svc.news.get_market_news(limit=limit)
    return [
        {
            "title": i.title,
            "link": i.link,
            "source": i.source,
            "symbol": i.symbol,
            "published": i.published.isoformat() if i.published else None,
        }
        for i in items
    ]
