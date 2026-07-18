"""Company fundamentals from SEC's free XBRL "company facts" API.

This is the Bloomberg-FA-style data, straight from the source of truth:
every US filer's audited financials, as tagged in their own 10-K/10-Q
XBRL, served keylessly at data.sec.gov. Two endpoints:

  - https://www.sec.gov/files/company_tickers.json   ticker -> CIK
  - https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json

XBRL tagging is messy in the wild (concept names changed over the years,
some filers use custom tags), so each metric tries a list of common
us-gaap concepts and takes the first that has annual 10-K data. Missing
metrics come back as None rather than failing the whole view.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .client import EdgarClient

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# metric label -> candidate us-gaap concepts, in preference order.
_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
}

# Shares outstanding lives in the "dei" (Document and Entity Information)
# taxonomy, not "us-gaap" - it's a cover-page fact, not a financial one.
_DEI_CONCEPTS = ["EntityCommonStockSharesOutstanding"]

# Trailing tokens stripped when matching 13F issuer names against SEC
# titles. Both sides abbreviate differently ("CHUBB LIMITED" vs "Chubb
# Ltd", and 13Fs append jurisdiction tags like "CHUBB LTD SWITZ" - all
# seen live), so strip suffix noise from the end of both before
# comparing. Deliberately conservative: matching stays exact-equality on
# what's left, never fuzzy.
_NAME_NOISE_TOKENS = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY",
    "LTD", "LIMITED", "PLC", "LP", "LLC", "SA", "NV", "AG", "ADR",
    "HOLDINGS", "HOLDING", "HLDGS", "HLDG", "GROUP", "GRP",
    "DEL", "SWITZ", "NEW",
}


def normalize_company_name(name: str) -> str:
    """Reduce a company name to comparable tokens ("CHUBB LTD SWITZ" ->
    "CHUBB", "Chubb Ltd" -> "CHUBB")."""
    cleaned = "".join(ch if ch.isalnum() else " " for ch in name.upper())
    tokens = cleaned.split()
    while tokens and tokens[-1] in _NAME_NOISE_TOKENS:
        tokens.pop()
    return " ".join(tokens)


@dataclass
class FiscalYear:
    """One fiscal year of headline financials (whole USD; EPS per share)."""

    fiscal_year: int
    end_date: str
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps_diluted: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    stockholders_equity: Optional[float] = None
    operating_cash_flow: Optional[float] = None


class FundamentalsClient:
    """Ticker -> CIK -> annual headline financials, via SEC only."""

    def __init__(self, edgar: EdgarClient):
        self.edgar = edgar
        self._ticker_map: Optional[dict[str, dict]] = None
        self._name_index: Optional[dict[str, str]] = None

    # ------------------------------------------------------------------ #
    # ticker <-> CIK
    # ------------------------------------------------------------------ #

    def _load_ticker_map(self) -> dict[str, dict]:
        """SEC's ticker file, keyed by upper-cased ticker.

        Also useful as a keyless fallback for CUSIP resolution failures
        (match by name), so it's cached for the client's lifetime.
        """
        if self._ticker_map is None:
            raw = self.edgar._get(TICKER_MAP_URL).json()
            self._ticker_map = {
                entry["ticker"].upper(): entry for entry in raw.values()
            }
        return self._ticker_map

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """CIK for a US-listed ticker, or None if SEC doesn't list it.

        Yahoo-style share classes (BRK-B) are normalized to SEC's dash
        style, which happens to match.
        """
        entry = self._load_ticker_map().get(ticker.upper())
        return str(entry["cik_str"]) if entry else None

    def company_name(self, ticker: str) -> Optional[str]:
        entry = self._load_ticker_map().get(ticker.upper())
        return entry["title"] if entry else None

    def name_to_ticker(self, name: str) -> Optional[str]:
        """Ticker whose SEC title matches a (13F-style) company name.

        The keyless fallback for CUSIPs OpenFIGI can't map (e.g.
        Chubb's H1467J104): exact match on noise-stripped names only.
        When several tickers share a title (Alphabet's GOOGL/GOOG), the
        file's first occurrence wins - SEC lists the primary class
        first (verified live: GOOGL precedes GOOG).
        """
        if self._name_index is None:
            index: dict[str, str] = {}
            for entry in self._load_ticker_map().values():
                key = normalize_company_name(entry["title"])
                if key and key not in index:
                    index[key] = entry["ticker"].upper()
            self._name_index = index
        return self._name_index.get(normalize_company_name(name))

    # ------------------------------------------------------------------ #
    # fundamentals
    # ------------------------------------------------------------------ #

    def get_company_facts(self, cik) -> dict:
        url = COMPANY_FACTS_URL.format(cik=EdgarClient.pad_cik(cik))
        return self.edgar._get(url).json()

    def annual_metrics(self, ticker: str, years: int = 5) -> list[FiscalYear]:
        """Last `years` fiscal years of headline financials, newest first.

        Returns [] for unknown tickers or filers with no XBRL facts
        (foreign private issuers, funds, etc.).
        """
        cik = self.ticker_to_cik(ticker)
        if cik is None:
            return []
        facts = self.get_company_facts(cik)
        return extract_annual_metrics(facts, years=years)

    def shares_outstanding(self, ticker: str) -> Optional[float]:
        """Most recently reported shares outstanding, or None if unknown."""
        cik = self.ticker_to_cik(ticker)
        if cik is None:
            return None
        return extract_shares_outstanding(self.get_company_facts(cik))


def extract_annual_metrics(facts: dict, years: int = 5) -> list[FiscalYear]:
    """Pure extraction from a companyfacts payload (unit-testable offline)."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    per_year: dict[int, FiscalYear] = {}

    for metric, concepts in _CONCEPTS.items():
        series = _annual_series(gaap, concepts)
        for fy, (end, value) in series.items():
            row = per_year.setdefault(fy, FiscalYear(fiscal_year=fy, end_date=end))
            setattr(row, metric, value)
            # Prefer the latest end date seen for the year label.
            if end > row.end_date:
                row.end_date = end

    ordered = sorted(per_year.values(), key=lambda r: r.fiscal_year, reverse=True)
    # Some filers tag stray future/partial years; keep ones with a
    # revenue or net income figure to avoid empty rows.
    ordered = [
        r for r in ordered if r.revenue is not None or r.net_income is not None
    ]
    return ordered[:years]


def extract_shares_outstanding(facts: dict) -> Optional[float]:
    """Latest EntityCommonStockSharesOutstanding value across any form.

    This is a cover-page snapshot (point-in-time, not a duration), so
    unlike the annual metrics it's taken from whichever filing reported
    it most recently - 10-K or 10-Q - to stay as current as possible.
    """
    dei = facts.get("facts", {}).get("dei", {})
    for concept in _DEI_CONCEPTS:
        entries = dei.get(concept, {}).get("units", {}).get("shares", [])
        best = None
        for e in entries:
            end, val = e.get("end"), e.get("val")
            if end is None or val is None:
                continue
            if best is None or end > best[0]:
                best = (end, float(val))
        if best is not None:
            return best[1]
    return None


def _spans_a_year(start: str, end: str) -> bool:
    try:
        from datetime import date

        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        return (e - s).days >= 300
    except ValueError:
        return False


def _annual_series(
    gaap: dict, concepts: list[str]
) -> dict[int, tuple[str, float]]:
    """fy -> (end_date, value) for the first concept with annual 10-K data.

    Annual figures are the FY entries reported on 10-K forms. When a year
    appears multiple times (restatements in later filings), the entry
    with the latest `end` + `filed` wins.
    """
    for concept in concepts:
        units = gaap.get(concept, {}).get("units", {})
        # Monetary concepts use "USD"; EPS uses "USD/shares".
        entries = units.get("USD") or units.get("USD/shares") or []
        series: dict[int, tuple[str, str, float]] = {}
        for e in entries:
            if e.get("form") != "10-K" or e.get("fp") != "FY":
                continue
            fy, end, filed, val = e.get("fy"), e.get("end"), e.get("filed", ""), e.get("val")
            if fy is None or end is None or val is None:
                continue
            # Duration concepts (revenue etc.) also carry quarterly
            # comparatives inside 10-Ks; only keep ~full-year spans.
            start = e.get("start")
            if start is not None and not _spans_a_year(start, end):
                continue
            key = (end, filed)
            if fy not in series or key > (series[fy][0], series[fy][1]):
                series[fy] = (end, filed, float(val))
        if series:
            return {fy: (end, val) for fy, (end, _filed, val) in series.items()}
    return {}
