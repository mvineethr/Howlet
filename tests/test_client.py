"""Tests for the EdgarClient.

These use `responses` to mock HTTP calls, so they run offline and don't hit
the real SEC servers. TODO(claude-code): add integration tests behind a
--run-live flag that hit the real API sparingly (1-2 requests, respecting
rate limits) to catch schema drift.
"""

from __future__ import annotations

import pytest
import requests
import responses

from edgar.client import EdgarClient

SAMPLE_INFO_TABLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <cusip>037833100</cusip>
    <value>50000000</value>
    <shsPrnAmt>
      <sshPrnamt>300000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shsPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
  <infoTable>
    <nameOfIssuer>COCA COLA CO</nameOfIssuer>
    <cusip>191216100</cusip>
    <value>25000000</value>
    <shsPrnAmt>
      <sshPrnamt>400000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shsPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
</informationTable>
"""


@pytest.fixture
def client() -> EdgarClient:
    return EdgarClient(user_agent="Test Suite test@example.com")


def test_requires_contact_email_in_user_agent():
    with pytest.raises(ValueError):
        EdgarClient(user_agent="just-a-name-no-email")


def test_pad_cik():
    assert EdgarClient.pad_cik(1067983) == "0001067983"
    assert EdgarClient.pad_cik("1067983") == "0001067983"
    assert EdgarClient.pad_cik("0001067983") == "0001067983"


def test_parse_information_table(client: EdgarClient):
    holdings = client._parse_information_table(SAMPLE_INFO_TABLE_XML)
    assert len(holdings) == 2

    apple = holdings[0]
    assert apple.name_of_issuer == "APPLE INC"
    assert apple.cusip == "037833100"
    assert apple.value_usd == 50000000
    assert apple.shares == 300000
    assert apple.share_type == "SH"


SAMPLE_COMPANY_SEARCH_HTML = b"""<!DOCTYPE html>
<html><body>
<table class="tableFile2" summary="Results">
  <tr>
    <th>CIK</th><th>Company</th><th>State/Country</th>
  </tr>
  <tr>
    <td><a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0000949012&amp;type=13F-HR">0000949012</a></td>
    <td>BERKSHIRE ASSET MANAGEMENT LLC/PA</td>
    <td><a href="/cgi-bin/browse-edgar?action=getcompany&amp;State=PA">PA</a></td>
  </tr>
  <tr class="evenRow">
    <td><a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0001067983&amp;type=13F-HR">0001067983</a></td>
    <td>BERKSHIRE HATHAWAY INC<br /><acronym title="Standard Industrial Code">SIC</acronym>: <a href="/cgi-bin/browse-edgar?action=getcompany&amp;SIC=6331">6331</a> - FIRE, MARINE &amp; CASUALTY INSURANCE</td>
    <td><a href="/cgi-bin/browse-edgar?action=getcompany&amp;State=NE">NE</a></td>
  </tr>
</table>
</body></html>
"""


@responses.activate
def test_search_company_cik_parses_html_table(client: EdgarClient):
    # Regression test: SEC's `output=atom` variant of this endpoint has a
    # live server-side bug where <entry title="..."> renders as a
    # stringified Perl array ref (e.g. "ARRAY(0x55d6f0feff88)") instead of
    # the company name - only caught by running against the real API.
    # search_company_cik now parses the HTML results table instead.
    responses.add(
        responses.GET,
        "https://www.sec.gov/cgi-bin/browse-edgar",
        body=SAMPLE_COMPANY_SEARCH_HTML,
        status=200,
    )

    results = client.search_company_cik("berkshire")

    assert results == [
        {"name": "BERKSHIRE ASSET MANAGEMENT LLC/PA", "cik": "0000949012"},
        {"name": "BERKSHIRE HATHAWAY INC", "cik": "0001067983"},
    ]


# Structure captured live 2026-07-17 from an exact-match query ("third
# point"): EDGAR skips the results table and renders the company's own
# filing list. Don't simplify - the tableFile2 on this page holds filing
# rows that used to parse as garbage {"name": "Documents", "cik": None}.
SAMPLE_SINGLE_COMPANY_HTML = b"""<!DOCTYPE html>
<html><body>
<span class="companyName">Third Point LLC CIK#: <a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0001040273">0001040273 (see all company filings)</a></span>
<form action="/cgi-bin/browse-edgar"><input name="CIK" type="hidden" value="0001040273"/></form>
<table class="tableFile2" summary="Results">
  <tr><th>Filings</th><th>Format</th><th>Description</th></tr>
  <tr><td>13F-HR</td><td><a href="#">Documents</a></td><td>Quarterly report</td></tr>
</table>
</body></html>
"""


@responses.activate
def test_search_company_cik_handles_exact_match_redirect(client: EdgarClient):
    responses.add(
        responses.GET,
        "https://www.sec.gov/cgi-bin/browse-edgar",
        body=SAMPLE_SINGLE_COMPANY_HTML,
        status=200,
    )
    results = client.search_company_cik("third point")
    assert results == [{"name": "Third Point LLC", "cik": "0001040273"}]


@responses.activate
def test_list_13f_filings_filters_to_13f_hr(client: EdgarClient):
    fake_submissions = {
        "filings": {
            "recent": {
                "form": ["13F-HR", "4", "13F-HR"],
                "accessionNumber": ["0001-23-000001", "0001-23-000002", "0001-23-000003"],
                "filingDate": ["2026-05-15", "2026-05-10", "2026-02-14"],
                "reportDate": ["2026-03-31", "", "2025-12-31"],
                "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm"],
            }
        }
    }
    responses.add(
        responses.GET,
        "https://data.sec.gov/submissions/CIK0001067983.json",
        json=fake_submissions,
        status=200,
    )

    filings = client.list_13f_filings("1067983", limit=8)

    assert len(filings) == 2  # the "4" (Form 4) should be filtered out
    assert filings[0].accession_number == "0001-23-000001"
    assert filings[1].accession_number == "0001-23-000003"


@responses.activate
def test_list_13f_filings_paginates_into_files_when_recent_is_short(client: EdgarClient):
    # "recent" has no 13F-HR at all here; the two we want live in a
    # paginated files[] page, matching the real shape confirmed by
    # fetching a long-history filer's live submissions.
    fake_submissions = {
        "filings": {
            "recent": {
                "form": ["4"],
                "accessionNumber": ["0001-23-000001"],
                "filingDate": ["2026-05-10"],
                "reportDate": [""],
                "primaryDocument": ["doc1.htm"],
            },
            "files": [
                {
                    "name": "CIK0001067983-submissions-001.json",
                    "filingCount": 2,
                    "filingFrom": "2023-01-01",
                    "filingTo": "2024-12-31",
                },
            ],
        }
    }
    fake_page = {
        "form": ["13F-HR", "13F-HR"],
        "accessionNumber": ["0002-23-000001", "0002-23-000002"],
        "filingDate": ["2024-05-15", "2024-02-14"],
        "reportDate": ["2024-03-31", "2023-12-31"],
        "primaryDocument": ["doc2.htm", "doc3.htm"],
    }
    responses.add(
        responses.GET,
        "https://data.sec.gov/submissions/CIK0001067983.json",
        json=fake_submissions,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://data.sec.gov/submissions/CIK0001067983-submissions-001.json",
        json=fake_page,
        status=200,
    )

    filings = client.list_13f_filings("1067983", limit=2)

    assert len(filings) == 2
    assert filings[0].accession_number == "0002-23-000001"
    assert filings[1].accession_number == "0002-23-000002"


@responses.activate
def test_get_retries_on_429_then_succeeds(client: EdgarClient, monkeypatch):
    monkeypatch.setattr("edgar.client.time.sleep", lambda seconds: None)
    responses.add(responses.GET, "https://example.test/thing", status=429)
    responses.add(responses.GET, "https://example.test/thing", json={"ok": True}, status=200)

    resp = client._get("https://example.test/thing")

    assert resp.json() == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_get_raises_after_exhausting_retries(client: EdgarClient, monkeypatch):
    monkeypatch.setattr("edgar.client.time.sleep", lambda seconds: None)
    for _ in range(4):  # 1 initial attempt + 3 retries, all failing
        responses.add(responses.GET, "https://example.test/thing", status=503)

    with pytest.raises(requests.HTTPError):
        client._get("https://example.test/thing")

    assert len(responses.calls) == 4


@responses.activate
def test_get_does_not_retry_non_retryable_4xx(client: EdgarClient):
    responses.add(responses.GET, "https://example.test/thing", status=404)

    with pytest.raises(requests.HTTPError):
        client._get("https://example.test/thing")

    assert len(responses.calls) == 1


@responses.activate
def test_get_retries_on_connection_reset_then_succeeds(client: EdgarClient, monkeypatch):
    """SEC resets stale keep-alive connections on long-lived sessions
    (WinError 10054, seen live from the dashboard's shared client); the
    retry must reissue the request instead of propagating immediately."""
    monkeypatch.setattr("edgar.client.time.sleep", lambda seconds: None)
    responses.add(
        responses.GET, "https://example.test/thing",
        body=requests.ConnectionError("Connection aborted (10054)"),
    )
    responses.add(responses.GET, "https://example.test/thing", json={"ok": True})

    resp = client._get("https://example.test/thing")
    assert resp.json() == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_get_raises_connection_error_after_exhausting_retries(client: EdgarClient, monkeypatch):
    monkeypatch.setattr("edgar.client.time.sleep", lambda seconds: None)
    for _ in range(4):  # 1 initial attempt + 3 retries, all resets
        responses.add(
            responses.GET, "https://example.test/thing",
            body=requests.ConnectionError("Connection aborted (10054)"),
        )
    with pytest.raises(requests.ConnectionError):
        client._get("https://example.test/thing")
    assert len(responses.calls) == 4
