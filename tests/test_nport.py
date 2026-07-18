"""Tests for N-PORT fund holdings (offline, mocked HTTP)."""

from __future__ import annotations

import json

import responses

from edgar import nport
from edgar.client import EdgarClient
from edgar.nport import (
    MF_TICKERS_URL,
    get_fund_holdings,
    list_nport_accessions,
    ticker_to_fund,
)

# Trimmed from ARK ETF Trust's live NPORT-P primary_doc.xml captured
# 2026-07-17 (accession 0000940400-26-025084). The nport namespace and
# nested value layout are the point - don't simplify.
SAMPLE_NPORT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo>
      <regName>ARK ETF Trust</regName>
      <regCik>0001579982</regCik>
      <seriesName>ARK Innovation ETF</seriesName>
      <seriesId>S000042977</seriesId>
      <repPdEnd>2026-07-31</repPdEnd>
      <repPdDate>2026-04-30</repPdDate>
    </genInfo>
    <fundInfo>
      <totAssets>6521307106.71</totAssets>
      <netAssets>6482466914.09</netAssets>
    </fundInfo>
    <invstOrSecs>
      <invstOrSec>
        <name>KRATOS DEFENSE &amp; SECURITY SOLUTIONS INC</name>
        <title>KRATOS DEFENSE &amp; SECURITY SOLUTIONS INC COM NEW</title>
        <cusip>50077B207</cusip>
        <balance>1080866.00000000</balance>
        <valUSD>68148601.30000000</valUSD>
        <pctVal>1.051275728872</pctVal>
        <assetCat>EC</assetCat>
        <issuerCat>CORP</issuerCat>
        <invCountry>US</invCountry>
      </invstOrSec>
      <invstOrSec>
        <name>TESLA INC</name>
        <title>TESLA INC COM</title>
        <cusip>88160R101</cusip>
        <balance>2000000</balance>
        <valUSD>500000000</valUSD>
        <pctVal>7.71</pctVal>
        <assetCat>EC</assetCat>
        <issuerCat>CORP</issuerCat>
        <invCountry>US</invCountry>
      </invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>"""

SERIES_HTML = b"""<html><body>
<a href="/Archives/edgar/data/1579982/000094040026025084/0000940400-26-025084-index.htm">doc</a>
<a href="/Archives/edgar/data/1579982/000094040026025084/0000940400-26-025084-index.htm">dup</a>
<a href="/Archives/edgar/data/1579982/000094040026012617/0000940400-26-012617-index.htm">doc</a>
</body></html>"""


def _client() -> EdgarClient:
    return EdgarClient("Test Suite test@example.com")


@responses.activate
def test_ticker_to_fund_maps_symbol_to_trust_and_series():
    nport._mf_map = None  # reset process cache
    responses.get(
        MF_TICKERS_URL,
        body=json.dumps({
            "fields": ["cik", "seriesId", "classId", "symbol"],
            "data": [
                [1579982, "S000042977", "C000133121", "ARKK"],
                [36405, "S000002839", "C000092055", "VOO"],
            ],
        }),
        content_type="application/json",
    )
    client = _client()
    assert ticker_to_fund(client, "arkk") == ("1579982", "S000042977")
    assert ticker_to_fund(client, "SPY") is None  # UITs aren't in the map
    # Second call must hit the process cache, not the network.
    assert ticker_to_fund(client, "VOO") == ("36405", "S000002839")
    assert len(responses.calls) == 1
    nport._mf_map = None


@responses.activate
def test_list_nport_accessions_dedupes_and_orders():
    responses.get(
        "https://www.sec.gov/cgi-bin/browse-edgar", body=SERIES_HTML
    )
    accessions = list_nport_accessions(_client(), "S000042977", limit=5)
    assert accessions == ["0000940400-26-025084", "0000940400-26-012617"]


@responses.activate
def test_get_fund_holdings_parses_info_and_positions():
    responses.get(
        "https://www.sec.gov/Archives/edgar/data/1579982/"
        "000094040026025084/primary_doc.xml",
        body=SAMPLE_NPORT_XML,
    )
    info, holdings = get_fund_holdings(
        _client(), "1579982", "0000940400-26-025084"
    )
    assert info.series_name == "ARK Innovation ETF"
    assert info.report_period_date == "2026-04-30"
    assert info.net_assets == 6482466914.09
    assert len(holdings) == 2
    # Sorted by value: Tesla ($500M) before Kratos ($68M).
    assert holdings[0].name == "TESLA INC"
    assert holdings[1].cusip == "50077B207"
    assert holdings[1].pct_val == 1.051275728872
