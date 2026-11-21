"""Corporate & macro events: earnings, analyst views, shareholder meetings,
Fed speeches/FOMC decisions.

Three different trust levels here, by design:

  - Shareholder meetings come straight from SEC EDGAR (DEF 14A proxy
    filings) - same reliability as the rest of this project.
  - Earnings dates + analyst recommendations come from Yahoo's
    `quoteSummary` endpoint, which needs the cookie+crumb workaround in
    `yahoo_auth.py` - unofficial, can silently stop working, always
    degrades to an empty/`None` result rather than raising.
  - Fed speeches/decisions come from the Federal Reserve's own public RSS
    feed - official, free, no key, same reliability tier as EDGAR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

from .client import EdgarClient
from .news import NewsItem, _dedupe_and_sort, _parse_rss
from .yahoo_auth import YahooAuthSession

QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
FED_PRESS_RSS = "https://www.federalreserve.gov/feeds/press_all.xml"
FED_SPEECHES_RSS = "https://www.federalreserve.gov/feeds/speeches.xml"

# One shared session for the Fed RSS feeds (module-level, like every
# other module's client) instead of a fresh Session per call.
_fed_session = requests.Session()

# SEC's proxy-statement form - what companies file ahead of an annual
# shareholder meeting (director elections, exec comp votes, etc).
PROXY_FORM = "DEF 14A"


@dataclass
class EarningsInfo:
    symbol: str
    next_earnings_date: str | None = None
    analyst_recommendation: str | None = None  # e.g. "buy", "hold"
    strong_buy: int | None = None
    buy: int | None = None
    hold: int | None = None
    sell: int | None = None
    strong_sell: int | None = None


class CorporateEventsClient:
    """Earnings/analyst data (Yahoo, crumb-authed) - degrades to None on failure."""

    def __init__(self, auth: YahooAuthSession | None = None):
        self.auth = auth or YahooAuthSession()

    def get_earnings_info(self, symbol: str) -> EarningsInfo | None:
        url = QUOTE_SUMMARY_URL.format(symbol=symbol)
        resp = self.auth.get(
            url, params={"modules": "calendarEvents,recommendationTrend"}
        )
        if resp is None:
            return None
        try:
            data = resp.json()
            result = data["quoteSummary"]["result"][0]
        except (KeyError, IndexError, ValueError, TypeError):
            return None
        return _parse_earnings_info(symbol, result)


def _parse_earnings_info(symbol: str, result: dict) -> EarningsInfo:
    info = EarningsInfo(symbol=symbol.upper())
    try:
        dates = result["calendarEvents"]["earnings"]["earningsDate"]
        if dates:
            info.next_earnings_date = dates[0].get("fmt")
    except (KeyError, IndexError, TypeError):
        pass

    try:
        trend = result["recommendationTrend"]["trend"][0]  # "0m" = current
        info.strong_buy = trend.get("strongBuy")
        info.buy = trend.get("buy")
        info.hold = trend.get("hold")
        info.sell = trend.get("sell")
        info.strong_sell = trend.get("strongSell")
        info.analyst_recommendation = _summarize_recommendation(trend)
    except (KeyError, IndexError, TypeError):
        pass
    return info


def _summarize_recommendation(trend: dict) -> str | None:
    weights = {"strongBuy": 2, "buy": 1, "hold": 0, "sell": -1, "strongSell": -2}
    total = sum((trend.get(k) or 0) * w for k, w in weights.items())
    count = sum(trend.get(k) or 0 for k in weights)
    if count == 0:
        return None
    avg = total / count
    if avg >= 1.5:
        return "strong buy"
    if avg >= 0.5:
        return "buy"
    if avg >= -0.5:
        return "hold"
    if avg >= -1.5:
        return "sell"
    return "strong sell"


def get_shareholder_meetings(client: EdgarClient, cik: str, limit: int = 5) -> list[dict]:
    """Recent DEF 14A (proxy statement) filings for a CIK - the filing
    that precedes a company's annual shareholder meeting."""
    data = client.get_submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    # SEC's parallel arrays are assumed aligned, but a short/missing
    # array must skip the row, never raise IndexError.
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []
    rows = []
    for i, form in enumerate(forms):
        if form != PROXY_FORM:
            continue
        if i >= len(filing_dates) or i >= len(accessions) or i >= len(primary_docs):
            continue
        rows.append(
            {
                "form": form,
                "filing_date": filing_dates[i],
                "accession_number": accessions[i],
                "primary_doc": primary_docs[i],
            }
        )
        if len(rows) >= limit:
            break
    return rows


def get_fed_events(limit: int = 20) -> list[NewsItem]:
    """Recent Fed press releases + speeches (FOMC decisions, statements)."""
    items: list[NewsItem] = []
    for source, url in (("Fed Press", FED_PRESS_RSS), ("Fed Speeches", FED_SPEECHES_RSS)):
        try:
            resp = _fed_session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            continue
        items.extend(_parse_rss(source, resp.content))

    # _dedupe_and_sort is the shared sort (newest first, deduped by link);
    # don't re-implement it here.
    return _dedupe_and_sort(items)[:limit]
