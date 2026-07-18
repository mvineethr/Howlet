"""Macro/fixed-income data: Treasury yields, BLS series, optional FRED.

Three tiers, cheapest-first:

  - Treasury.gov's daily par yield curve XML - official, free, no key,
    ever. This is the fixed-income desk's yield curve.
  - BLS (Bureau of Labor Statistics) public API v2 - free with NO signup
    at a reduced rate limit (25 queries/day/IP, 20 years of history,
    25 series/query) - plenty for a personal terminal. CPI, unemployment.
  - FRED (St. Louis Fed) - the richest macro source (GDP, Fed funds
    rate, every economic series imaginable), but needs a free *registered*
    API key. Purely optional: set FRED_API_KEY and it's used; unset and
    this module simply skips it. This is the one deliberate exception to
    "no key, ever" in this project, and it's opt-in for exactly that
    reason.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from lxml import etree

TREASURY_YIELD_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"
    "/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month={yyyymm}"
)

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# BLS series IDs for the headlines everyone actually asks about.
BLS_SERIES = {
    "cpi": "CUUR0000SA0",  # CPI-U, all items, not seasonally adjusted
    "unemployment_rate": "LNS14000000",
    "nonfarm_payrolls": "CES0000000001",
}

# FRED series shown on the ECO screen when FRED_API_KEY is configured.
# label -> (series_id, human description)
FRED_SERIES: dict[str, tuple[str, str]] = {
    "fed_funds_rate": ("FEDFUNDS", "Fed funds effective rate (%)"),
    "gdp": ("GDP", "US GDP ($B, quarterly)"),
    "cpi_index": ("CPIAUCSL", "CPI index (1982-84=100)"),
    "unemployment_rate": ("UNRATE", "Unemployment rate (%)"),
    "treasury_10y": ("DGS10", "10-year Treasury yield (%)"),
    "mortgage_30y": ("MORTGAGE30US", "30-year fixed mortgage rate (%)"),
}

# Treasury's XML field names for each maturity point on the curve.
_TREASURY_MATURITIES = [
    ("BC_1MONTH", "1mo"), ("BC_3MONTH", "3mo"), ("BC_6MONTH", "6mo"),
    ("BC_1YEAR", "1y"), ("BC_2YEAR", "2y"), ("BC_5YEAR", "5y"),
    ("BC_10YEAR", "10y"), ("BC_20YEAR", "20y"), ("BC_30YEAR", "30y"),
]


@dataclass
class YieldCurvePoint:
    maturity: str
    yield_pct: float


def get_treasury_yield_curve(session: Optional[requests.Session] = None) -> dict:
    """Most recent daily Treasury par yield curve. {} on any failure."""
    session = session or requests.Session()
    yyyymm = datetime.now(timezone.utc).strftime("%Y%m")
    url = TREASURY_YIELD_URL.format(yyyymm=yyyymm)
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return {}
    return _parse_treasury_xml(resp.content)


def _parse_treasury_xml(xml_bytes: bytes) -> dict:
    """Parse Treasury's OData/Atom feed by *local* tag names.

    The real feed nests values as <m:properties><d:BC_10YEAR>...</d:...>
    where m: is the OData *metadata* namespace and d: the dataservices
    one - found live after a first version searched for `properties` in
    the d: namespace and silently matched nothing. Matching local names
    sidesteps the whole namespace trap (same approach as the 13F parser).
    """
    try:
        root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True))
    except (etree.XMLSyntaxError, ValueError):
        return {}
    if root is None:
        return {}

    entries = [el for el in root.iter() if etree.QName(el).localname == "entry"]
    if not entries:
        return {}
    last_entry = entries[-1]  # most recent trading day in the month

    values: dict[str, str] = {}
    for el in last_entry.iter():
        name = etree.QName(el).localname
        if el.text and (name == "NEW_DATE" or name.startswith("BC_")):
            values[name] = el.text

    curve = []
    for field, label in _TREASURY_MATURITIES:
        raw = values.get(field)
        if raw is None:
            continue
        try:
            curve.append({"maturity": label, "yield_pct": float(raw)})
        except ValueError:
            continue
    if not curve:
        return {}
    date_raw = values.get("NEW_DATE")
    return {"date": date_raw[:10] if date_raw else None, "curve": curve}


def get_bls_series(series_ids: list[str], years: int = 3) -> dict:
    """Latest values for BLS series IDs. Works keyless (25 q/day/IP limit).

    Returns {series_id: [{"year": ..., "period": ..., "value": ...}, ...]}
    newest first; missing/failed series are simply absent.
    """
    current_year = datetime.now(timezone.utc).year
    payload = {
        "seriesid": series_ids,
        "startyear": str(current_year - years),
        "endyear": str(current_year),
    }
    try:
        resp = requests.post(BLS_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return {}
    if data.get("status") != "REQUEST_SUCCEEDED":
        return {}

    out: dict[str, list[dict]] = {}
    for series in data.get("Results", {}).get("series", []):
        sid = series.get("seriesID")
        if not sid:
            continue
        out[sid] = [
            {"year": d["year"], "period": d["periodName"], "value": d["value"]}
            for d in series.get("data", [])
        ]
    return out


def get_fred_series(series_id: str, api_key: Optional[str] = None) -> Optional[list[dict]]:
    """Recent observations for a FRED series. None if no key is configured
    (env var FRED_API_KEY) or the request fails - this is the one optional,
    key-gated data source in this project; everything else works without it.
    """
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        return None
    try:
        resp = requests.get(
            FRED_URL,
            params={
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 20,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    return [
        {"date": o["date"], "value": o["value"]}
        for o in data.get("observations", [])
        if o.get("value") not in (None, ".")
    ]


def get_fred_snapshot(api_key: Optional[str] = None) -> dict:
    """Latest value for every FRED_SERIES entry. {} without a key.

    label -> {"description", "latest", "date"} for each series that
    responded; individually failed series are simply absent, matching
    the degrade-not-crash rule everywhere else.
    """
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        return {}
    snapshot: dict[str, dict] = {}
    for label, (series_id, description) in FRED_SERIES.items():
        observations = get_fred_series(series_id, api_key=key)
        if not observations:
            continue
        latest = observations[0]  # sort_order=desc -> newest first
        snapshot[label] = {
            "description": description,
            "latest": latest["value"],
            "date": latest["date"],
        }
    return snapshot
