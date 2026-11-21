"""N-PORT fund holdings: what an ETF or mutual fund actually holds.

Registered funds file NPORT-P monthly (public with a ~60 day lag) - the
fund-world equivalent of a 13F, but with exact balances, values, AND the
fund's own weight percentages. All free EDGAR data:

  1. company_tickers_mf.json maps fund tickers -> (trust CIK, seriesId).
  2. browse-edgar filtered by the SERIES id lists that series' NPORT-P
     accessions (a trust files one NPORT-P per series, so filtering by
     the trust CIK alone would mix its funds together).
  3. The filing's primary_doc.xml (namespaced, parsed by local name)
     carries genInfo + one invstOrSec per holding.

Known limitation, verified live: unit investment trusts (SPY, pre-2026
QQQ) don't appear in company_tickers_mf.json and don't file NPORT-P -
callers get a clear LookupError from the view layer, not silence.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from lxml import etree

from .cache import CACHE_VERSION
from .client import COMPANY_SEARCH_URL, EdgarClient
from .tickers import default_cache_dir

MF_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"

# Process-lifetime cache of the fund-ticker map (~28k rows, rarely changes).
_mf_map: dict[str, tuple[str, str]] | None = None


@dataclass
class FundHolding:
    """One invstOrSec entry from an NPORT-P filing."""

    name: str
    title: str
    cusip: str
    balance: float  # shares/units/principal, per `units`
    value_usd: float
    pct_val: float  # the fund's own reported weight (% of net assets)
    asset_cat: str  # EC = common equity, DBT = debt, ...
    issuer_cat: str
    country: str


@dataclass
class FundInfo:
    registrant: str
    series_name: str
    series_id: str
    report_period_date: str | None
    total_assets: float | None
    net_assets: float | None


def ticker_to_fund(client: EdgarClient, symbol: str) -> tuple[str, str] | None:
    """(trust_cik, series_id) for a fund ticker, or None if not a
    registered fund with an NPORT trail (e.g. unit investment trusts)."""
    global _mf_map
    if _mf_map is None:
        data = client._get(MF_TICKERS_URL).json()
        fields = data.get("fields", [])
        try:
            cik_i = fields.index("cik")
            series_i = fields.index("seriesId")
            symbol_i = fields.index("symbol")
        except ValueError:
            return None
        _mf_map = {}
        for row in data.get("data", []):
            sym = str(row[symbol_i]).upper()
            # First mapping wins; funds list one row per share class.
            _mf_map.setdefault(sym, (str(row[cik_i]), str(row[series_i])))
    return _mf_map.get(symbol.upper())


def list_nport_accessions(
    client: EdgarClient, series_id: str, limit: int = 5
) -> list[str]:
    """Accession numbers of a SERIES' recent NPORT-P filings, newest
    first, via browse-edgar filtered by series id (HTML, like company
    search - the JSON submissions API has no series filter)."""
    resp = client._get(
        COMPANY_SEARCH_URL,
        params={
            "action": "getcompany",
            "CIK": series_id,
            "type": "NPORT-P",
            "dateb": "",
            "owner": "include",
            "count": str(max(limit, 10)),
        },
    )
    accessions = re.findall(
        r"Archives/edgar/data/\d+/\d+/([\d-]+)-index\.htm", resp.text
    )
    seen: list[str] = []
    for acc in accessions:
        if acc not in seen:
            seen.append(acc)
        if len(seen) >= limit:
            break
    return seen


def _resolve_primary_doc(client: EdgarClient, cik: str, accession: str) -> str:
    """Primary-document filename for an NPORT-P filing, resolved from
    its filing index instead of assuming `primary_doc.xml`.

    Prefers a file literally named primary_doc.xml, then any other .xml
    file in the index; falls back to the hardcoded name when the index
    lists no XML at all, so odd layouts keep today's behavior.
    """
    base = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/"
    )
    index = client._get(f"{base}index.json").json()
    names = [
        str(item["name"])
        for item in index.get("directory", {}).get("item", [])
        if isinstance(item, dict)
        and str(item.get("name", "")).lower().endswith(".xml")
    ]
    for name in names:
        if name.lower() == "primary_doc.xml":
            return name
    if names:
        return names[0]
    return "primary_doc.xml"


class NportCache:
    """One JSON file of parsed NPORT-P holdings per accession number.

    Same versioned envelope as the 13F/Form 4 caches: a parser change
    bumps CACHE_VERSION and old files are ignored, not served stale.
    A filing never changes once it's on EDGAR, so entries never expire.
    """

    def __init__(self, cache_dir: Path | None = None):
        base = Path(cache_dir) if cache_dir else default_cache_dir()
        self.holdings_dir = base / "nport"

    def _path(self, accession: str) -> Path:
        return self.holdings_dir / f"{accession.replace('-', '')}.json"

    def get_holdings(
        self, accession: str
    ) -> tuple[FundInfo, list[FundHolding]] | None:
        try:
            with open(self._path(accession), encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
                return None
            info = FundInfo(**raw["info"])
            holdings = [FundHolding(**entry) for entry in raw["holdings"]]
            return info, holdings
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def put_holdings(
        self, accession: str, info: FundInfo, holdings: list[FundHolding]
    ) -> None:
        try:
            self.holdings_dir.mkdir(parents=True, exist_ok=True)
            with open(self._path(accession), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version": CACHE_VERSION,
                        "info": asdict(info),
                        "holdings": [asdict(h) for h in holdings],
                    },
                    f,
                )
        except OSError:
            pass  # cache is an optimization, never a failure


def cached_fund_holdings(
    client: EdgarClient,
    cache: NportCache | None,
    cik: str,
    accession: str,
) -> tuple[FundInfo, list[FundHolding]]:
    """Fetch a filing's fund holdings through the cache (if provided)."""
    if cache is not None:
        cached = cache.get_holdings(accession)
        if cached is not None:
            return cached
    result = get_fund_holdings(client, cik, accession)
    if cache is not None:
        cache.put_holdings(accession, *result)
    return result


def get_fund_holdings(
    client: EdgarClient, cik: str, accession: str
) -> tuple[FundInfo, list[FundHolding]]:
    """Fetch + parse one NPORT-P filing's fund info and holdings."""
    doc = _resolve_primary_doc(client, cik, accession)
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/{doc}"
    )
    root = etree.fromstring(client._get(url).content)

    def loc(el) -> str:
        return etree.QName(el).localname if isinstance(el.tag, str) else ""

    def child_text(parent, tag: str) -> str | None:
        for el in parent.iter():
            if loc(el) == tag:
                return el.text.strip() if el.text else None
        return None

    def child_float(parent, tag: str) -> float | None:
        text = child_text(parent, tag)
        try:
            return float(text) if text is not None else None
        except ValueError:
            return None

    info = FundInfo(
        registrant=child_text(root, "regName") or "",
        series_name=child_text(root, "seriesName") or "",
        series_id=child_text(root, "seriesId") or "",
        report_period_date=child_text(root, "repPdDate"),
        total_assets=child_float(root, "totAssets"),
        net_assets=child_float(root, "netAssets"),
    )

    holdings: list[FundHolding] = []
    for el in root.iter():
        if loc(el) != "invstOrSec":
            continue
        holdings.append(
            FundHolding(
                name=child_text(el, "name") or "",
                title=child_text(el, "title") or "",
                cusip=child_text(el, "cusip") or "",
                balance=child_float(el, "balance") or 0.0,
                value_usd=child_float(el, "valUSD") or 0.0,
                pct_val=child_float(el, "pctVal") or 0.0,
                asset_cat=child_text(el, "assetCat") or "",
                issuer_cat=child_text(el, "issuerCat") or "",
                country=child_text(el, "invCountry") or "",
            )
        )
    holdings.sort(key=lambda h: h.value_usd, reverse=True)
    return info, holdings
