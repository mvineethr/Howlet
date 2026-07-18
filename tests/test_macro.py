"""Tests for macro data: Treasury yield curve (XML), BLS, optional FRED."""

from __future__ import annotations

import responses

from edgar import macro

# Mirrors the REAL feed structure: <m:properties> is in the OData
# *metadata* namespace, children in the d: dataservices one. The first
# version of this fixture put properties in d: - same bug as the parser -
# so the test passed while live parsing returned {}. Captured from the
# live feed on 2026-07-06; don't "simplify" the namespaces.
TREASURY_XML = """<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-07-02T00:00:00</d:NEW_DATE>
        <d:BC_1MONTH m:type="Edm.Double">5.20</d:BC_1MONTH>
        <d:BC_3MONTH m:type="Edm.Double">5.15</d:BC_3MONTH>
        <d:BC_10YEAR m:type="Edm.Double">4.30</d:BC_10YEAR>
      </m:properties>
    </content>
  </entry>
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-07-03T00:00:00</d:NEW_DATE>
        <d:BC_1MONTH m:type="Edm.Double">5.18</d:BC_1MONTH>
        <d:BC_3MONTH m:type="Edm.Double">5.12</d:BC_3MONTH>
        <d:BC_10YEAR m:type="Edm.Double">4.28</d:BC_10YEAR>
      </m:properties>
    </content>
  </entry>
</feed>"""


def test_parse_treasury_xml_takes_the_latest_entry():
    result = macro._parse_treasury_xml(TREASURY_XML.encode())
    assert result["date"] == "2026-07-03"
    by_maturity = {p["maturity"]: p["yield_pct"] for p in result["curve"]}
    assert by_maturity == {"1mo": 5.18, "3mo": 5.12, "10y": 4.28}


def test_parse_treasury_xml_handles_garbage():
    assert macro._parse_treasury_xml(b"not xml") == {}
    assert macro._parse_treasury_xml(b"<feed></feed>") == {}


@responses.activate
def test_get_treasury_yield_curve_degrades_on_http_error():
    import re

    responses.get(re.compile(r"https://home\.treasury\.gov/.*"), status=500)
    assert macro.get_treasury_yield_curve() == {}


@responses.activate
def test_get_bls_series_maps_by_series_id():
    responses.post(
        macro.BLS_URL,
        json={
            "status": "REQUEST_SUCCEEDED",
            "Results": {
                "series": [
                    {
                        "seriesID": "LNS14000000",
                        "data": [{"year": "2026", "periodName": "June", "value": "4.1"}],
                    }
                ]
            },
        },
    )
    result = macro.get_bls_series(["LNS14000000"])
    assert result["LNS14000000"][0]["value"] == "4.1"


@responses.activate
def test_get_bls_series_returns_empty_on_rejected_request():
    responses.post(macro.BLS_URL, json={"status": "REQUEST_NOT_PROCESSED"})
    assert macro.get_bls_series(["LNS14000000"]) == {}


def test_get_fred_series_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    assert macro.get_fred_series("GDP") is None


@responses.activate
def test_get_fred_series_uses_provided_key():
    responses.get(
        macro.FRED_URL,
        json={"observations": [{"date": "2026-01-01", "value": "27000"}, {"date": "2025-01-01", "value": "."}]},
    )
    result = macro.get_fred_series("GDP", api_key="test-key")
    assert result == [{"date": "2026-01-01", "value": "27000"}]


def test_get_fred_snapshot_empty_without_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    assert macro.get_fred_snapshot() == {}


@responses.activate
def test_get_fred_snapshot_collects_latest_per_series():
    responses.get(
        macro.FRED_URL,
        json={"observations": [{"date": "2026-06-01", "value": "4.33"}]},
    )
    snapshot = macro.get_fred_snapshot(api_key="test-key")
    # Every configured series responded with the same mock; spot-check one.
    assert snapshot["fed_funds_rate"]["latest"] == "4.33"
    assert snapshot["fed_funds_rate"]["date"] == "2026-06-01"
    assert "description" in snapshot["fed_funds_rate"]
    assert set(snapshot) == set(macro.FRED_SERIES)
