"""Tests for the EdgarClient.

These use `responses` to mock HTTP calls, so they run offline and don't hit
the real SEC servers. TODO(claude-code): add integration tests behind a
--run-live flag that hit the real API sparingly (1-2 requests, respecting
rate limits) to catch schema drift.
"""

from __future__ import annotations

from datetime import date

import pytest
import requests
import responses

from howlet.client import EdgarClient
from howlet.models import FilingSummary

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
    monkeypatch.setattr("howlet.client.time.sleep", lambda seconds: None)
    responses.add(responses.GET, "https://example.test/thing", status=429)
    responses.add(responses.GET, "https://example.test/thing", json={"ok": True}, status=200)

    resp = client._get("https://example.test/thing")

    assert resp.json() == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_get_raises_after_exhausting_retries(client: EdgarClient, monkeypatch):
    monkeypatch.setattr("howlet.client.time.sleep", lambda seconds: None)
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
    monkeypatch.setattr("howlet.client.time.sleep", lambda seconds: None)
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
    monkeypatch.setattr("howlet.client.time.sleep", lambda seconds: None)
    for _ in range(4):  # 1 initial attempt + 3 retries, all resets
        responses.add(
            responses.GET, "https://example.test/thing",
            body=requests.ConnectionError("Connection aborted (10054)"),
        )
    with pytest.raises(requests.ConnectionError):
        client._get("https://example.test/thing")
    assert len(responses.calls) == 4


# --- Phase 0/1 fixes: put/call, pre-2023 scaling, defensive parsing ---

PUT_CALL_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>NVIDIA CORP</nameOfIssuer>
    <cusip>67066G104</cusip>
    <value>1000000</value>
    <shsPrnAmt>
      <sshPrnamt>5000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shsPrnAmt>
    <putCall>PUT</putCall>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
  <infoTable>
    <nameOfIssuer>NVIDIA CORP</nameOfIssuer>
    <cusip>67066G104</cusip>
    <value>2000000</value>
    <shsPrnAmt>
      <sshPrnamt>10000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shsPrnAmt>
    <putCall>CALL</putCall>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
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
</informationTable>
"""


def test_parse_information_table_reads_put_call(client: EdgarClient):
    holdings = client._parse_information_table(PUT_CALL_XML)
    assert len(holdings) == 3

    put, call, long = holdings
    assert put.put_call == "PUT"
    assert put.is_option
    assert call.put_call == "CALL"
    assert call.is_option
    assert long.put_call is None
    assert not long.is_option


def test_parse_information_table_scales_pre_2023_values(client: EdgarClient):
    from datetime import date

    # <value> 1,000,000 in a 2022 filing is $1,000,000 thousands.
    old = client._parse_information_table(
        PUT_CALL_XML, period_of_report=date(2022, 12, 31)
    )
    assert old[0].value_usd == 1_000_000_000
    assert old[2].value_usd == 50_000_000_000

    # Same XML in a 2023 filing is already whole dollars - no scaling.
    new = client._parse_information_table(
        PUT_CALL_XML, period_of_report=date(2023, 3, 31)
    )
    assert new[0].value_usd == 1_000_000
    assert new[2].value_usd == 50_000_000

    # No period (offline parsing) applies no scaling either.
    assert client._parse_information_table(PUT_CALL_XML)[0].value_usd == 1_000_000


def test_parse_information_table_tolerates_malformed_numbers(client: EdgarClient):
    assert EdgarClient._to_int("1,234") == 1234
    assert EdgarClient._to_int("12.5") == 12
    assert EdgarClient._to_int("  42 ") == 42
    assert EdgarClient._to_int("") == 0
    assert EdgarClient._to_int(None) == 0
    assert EdgarClient._to_int("not-a-number") == 0

    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <informationTable>
      <infoTable>
        <nameOfIssuer>WEIRD CO</nameOfIssuer>
        <cusip>123456789</cusip>
        <value>1,234</value>
        <shsPrnAmt><sshPrnamt>12.5</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shsPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
      </infoTable>
    </informationTable>
    """
    holdings = client._parse_information_table(xml)
    assert holdings[0].value_usd == 1234
    assert holdings[0].shares == 12


@responses.activate
def test_list_13f_filings_prefers_amendment_over_original(client: EdgarClient):
    # Same period reported twice: the original 13F-HR and a later
    # 13F-HR/A. Only the amendment may be returned for that period.
    fake_submissions = {
        "filings": {
            "recent": {
                "form": ["13F-HR", "13F-HR/A", "13F-HR"],
                "accessionNumber": [
                    "0001-23-000001",
                    "0001-23-000002",
                    "0001-23-000003",
                ],
                "filingDate": ["2026-05-15", "2026-06-01", "2026-02-14"],
                "reportDate": ["2026-03-31", "2026-03-31", "2025-12-31"],
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

    assert len(filings) == 2  # one per period, not three
    assert filings[0].accession_number == "0001-23-000002"  # the amendment
    assert filings[0].form == "13F-HR/A"
    assert filings[1].accession_number == "0001-23-000003"


@responses.activate
def test_list_filings_skips_rows_with_short_parallel_arrays(client: EdgarClient):
    # reportDate is shorter than form: the second row has no period
    # (None is a valid state) and must be kept, not raise IndexError.
    # A row missing its filingDate has no usable identity and is skipped.
    fake_submissions = {
        "filings": {
            "recent": {
                "form": ["13F-HR", "13F-HR", "13F-HR"],
                "accessionNumber": [
                    "0001-23-000001",
                    "0001-23-000002",
                    "0001-23-000003",
                ],
                "filingDate": ["2026-05-15", "2026-02-14"],
                "reportDate": ["2026-03-31"],
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

    assert len(filings) == 2
    assert filings[0].accession_number == "0001-23-000001"
    assert filings[1].accession_number == "0001-23-000002"
    assert filings[1].period_of_report is None  # short reportDate array


@responses.activate
def test_list_filings_tolerates_missing_filings_key(client: EdgarClient):
    responses.add(
        responses.GET,
        "https://data.sec.gov/submissions/CIK0001067983.json",
        json={},
        status=200,
    )
    assert client.list_13f_filings("1067983", limit=8) == []


# --------------------------------------------------------------------- #
# 13F-HR/A amendment kinds (Codex review, P1)
# --------------------------------------------------------------------- #

_MSFT_INFO_TABLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>MICROSOFT CORP</nameOfIssuer>
    <cusip>594918104</cusip>
    <value>10000000</value>
    <shsPrnAmt>
      <sshPrnamt>100000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shsPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
</informationTable>
"""

_NVDA_INFO_TABLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>NVIDIA CORP</nameOfIssuer>
    <cusip>67066G104</cusip>
    <value>20000000</value>
    <shsPrnAmt>
      <sshPrnamt>150000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shsPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
</informationTable>
"""


def _cover_page_html(checked: str | None) -> bytes:
    """A 13F cover page with the amendment box marked as given.

    `checked` is "restatement", "adds", or None (neither box checked).
    """
    restatement = "[X]" if checked == "restatement" else "[ ]"
    adds = "[X]" if checked == "adds" else "[ ]"
    return f"""<html><body>
<p>Report for the Calendar Year or Quarter Ended: March 31, 2026</p>
<p>Check here if Amendment [X] Amendment Number: 1</p>
<p>This Amendment (Check only one.): {restatement} is a restatement.</p>
<p>{adds} adds new holdings entries.</p>
</body></html>""".encode()


def _register_13f_filing(accession: str, xml: bytes, cover: bytes | None = None,
                         primary_doc: str = "doc.htm") -> None:
    """Mock a filing's index.json + information table (+ cover page)."""
    base = (
        "https://www.sec.gov/Archives/edgar/data/1067983/"
        f"{accession.replace('-', '')}/"
    )
    responses.add(
        responses.GET, base + "index.json",
        json={"directory": {"item": [{"name": "infotable.xml"}, {"name": primary_doc}]}},
        status=200,
    )
    responses.add(responses.GET, base + "infotable.xml", body=xml, status=200)
    if cover is not None:
        responses.add(responses.GET, base + primary_doc, body=cover, status=200)


def _amendment_submissions(*rows) -> dict:
    """Submissions fixture for one period; rows are
    (form, accession, filing_date, primary_doc). All 2026-03-31."""
    return {"filings": {"recent": {
        "form": [r[0] for r in rows],
        "accessionNumber": [r[1] for r in rows],
        "filingDate": [r[2] for r in rows],
        "reportDate": ["2026-03-31"] * len(rows),
        "primaryDocument": [r[3] for r in rows],
    }}}


def _filing(accession: str, filing_date: str, form: str) -> FilingSummary:
    return FilingSummary(
        cik="0001067983", accession_number=accession,
        filing_date=date.fromisoformat(filing_date),
        period_of_report=date(2026, 3, 31),
        primary_doc="doc.htm", form=form,
    )


@responses.activate
def test_amendment_adds_new_holdings_merges_with_original(client: EdgarClient):
    """An 'adds new holdings entries' amendment is merged onto the
    original report instead of replacing it (Codex review, P1)."""
    responses.add(
        responses.GET, "https://data.sec.gov/submissions/CIK0001067983.json",
        json=_amendment_submissions(
            ("13F-HR", "0001-23-000001", "2026-05-15", "doc.htm"),
            ("13F-HR/A", "0001-23-000002", "2026-06-01", "doc.htm"),
        ),
        status=200,
    )
    _register_13f_filing("0001-23-000001", SAMPLE_INFO_TABLE_XML)
    _register_13f_filing("0001-23-000002", _MSFT_INFO_TABLE_XML,
                         cover=_cover_page_html("adds"))

    holdings = client.get_information_table(_filing("0001-23-000002", "2026-06-01", "13F-HR/A"))

    assert [h.cusip for h in holdings] == ["037833100", "191216100", "594918104"]


@responses.activate
def test_amendment_restatement_replaces_original(client: EdgarClient):
    """A restatement amendment replaces the original report outright."""
    responses.add(
        responses.GET, "https://data.sec.gov/submissions/CIK0001067983.json",
        json=_amendment_submissions(
            ("13F-HR", "0001-23-000001", "2026-05-15", "doc.htm"),
            ("13F-HR/A", "0001-23-000002", "2026-06-01", "doc.htm"),
        ),
        status=200,
    )
    _register_13f_filing("0001-23-000001", SAMPLE_INFO_TABLE_XML)
    _register_13f_filing("0001-23-000002", _MSFT_INFO_TABLE_XML,
                         cover=_cover_page_html("restatement"))

    holdings = client.get_information_table(_filing("0001-23-000002", "2026-06-01", "13F-HR/A"))

    assert [h.cusip for h in holdings] == ["594918104"]


@responses.activate
def test_amendment_unreadable_cover_page_replaces_original(client: EdgarClient):
    """An amendment whose kind cannot be read from its cover page is
    treated as a restatement - the previous behavior, never a guessed merge."""
    responses.add(
        responses.GET, "https://data.sec.gov/submissions/CIK0001067983.json",
        json=_amendment_submissions(
            ("13F-HR", "0001-23-000001", "2026-05-15", "doc.htm"),
            ("13F-HR/A", "0001-23-000002", "2026-06-01", "doc.htm"),
        ),
        status=200,
    )
    _register_13f_filing("0001-23-000001", SAMPLE_INFO_TABLE_XML)
    _register_13f_filing("0001-23-000002", _MSFT_INFO_TABLE_XML,
                         cover=_cover_page_html(None))

    holdings = client.get_information_table(_filing("0001-23-000002", "2026-06-01", "13F-HR/A"))

    assert [h.cusip for h in holdings] == ["594918104"]


@responses.activate
def test_amendment_chain_folds_oldest_first(client: EdgarClient):
    """Two amendments for one period apply in filing order: an adds
    amendment merges, a later restatement replaces everything before it."""
    responses.add(
        responses.GET, "https://data.sec.gov/submissions/CIK0001067983.json",
        json=_amendment_submissions(
            ("13F-HR", "0001-23-000001", "2026-05-15", "doc.htm"),
            ("13F-HR/A", "0001-23-000002", "2026-06-01", "doc.htm"),
            ("13F-HR/A", "0001-23-000003", "2026-07-01", "doc.htm"),
        ),
        status=200,
    )
    _register_13f_filing("0001-23-000001", SAMPLE_INFO_TABLE_XML)
    _register_13f_filing("0001-23-000002", _MSFT_INFO_TABLE_XML,
                         cover=_cover_page_html("adds"))
    _register_13f_filing("0001-23-000003", _NVDA_INFO_TABLE_XML,
                         cover=_cover_page_html("restatement"))

    holdings = client.get_information_table(_filing("0001-23-000003", "2026-07-01", "13F-HR/A"))

    assert [h.cusip for h in holdings] == ["67066G104"]


@responses.activate
def test_amendment_chain_restatement_then_adds(client: EdgarClient):
    """A restatement followed by an adds amendment: the restated table
    plus the later added rows (the pre-restatement rows stay dropped)."""
    responses.add(
        responses.GET, "https://data.sec.gov/submissions/CIK0001067983.json",
        json=_amendment_submissions(
            ("13F-HR", "0001-23-000001", "2026-05-15", "doc.htm"),
            ("13F-HR/A", "0001-23-000002", "2026-06-01", "doc.htm"),
            ("13F-HR/A", "0001-23-000003", "2026-07-01", "doc.htm"),
        ),
        status=200,
    )
    _register_13f_filing("0001-23-000001", SAMPLE_INFO_TABLE_XML)
    _register_13f_filing("0001-23-000002", _NVDA_INFO_TABLE_XML,
                         cover=_cover_page_html("restatement"))
    _register_13f_filing("0001-23-000003", _MSFT_INFO_TABLE_XML,
                         cover=_cover_page_html("adds"))

    holdings = client.get_information_table(_filing("0001-23-000003", "2026-07-01", "13F-HR/A"))

    assert [h.cusip for h in holdings] == ["67066G104", "594918104"]


def test_classify_amendment_cover_bracket_style():
    """[X] / [ ] boxes next to the two prescribed labels."""
    from howlet.client import _classify_amendment_cover

    adds = """Check here if Amendment [X] Amendment Number: 1
    This Amendment (Check only one.): [ ] is a restatement.
    [X] adds new holdings entries."""
    assert _classify_amendment_cover(adds) == "adds"

    restatement = """Check here if Amendment [X] Amendment Number: 1
    This Amendment (Check only one.): [X] is a restatement.
    [ ] adds new holdings entries."""
    assert _classify_amendment_cover(restatement) == "restatement"


def test_classify_amendment_cover_table_cell_x():
    """HTML table rendering: the checked box is a lone X in its own cell."""
    from howlet.client import _classify_amendment_cover

    html = """<table><tr><td>This Amendment (Check only one.):</td></tr>
    <tr><td>X</td><td>is a restatement.</td></tr>
    <tr><td></td><td>adds new holdings entries.</td></tr></table>"""
    assert _classify_amendment_cover(html) == "restatement"


def test_classify_amendment_cover_unclassifiable():
    """Neither box checked, both checked, or no labels: None, never a guess."""
    from howlet.client import _classify_amendment_cover

    neither = "This Amendment (Check only one.): [ ] is a restatement. [ ] adds new holdings entries."
    assert _classify_amendment_cover(neither) is None
    both = "This Amendment (Check only one.): [X] is a restatement. [X] adds new holdings entries."
    assert _classify_amendment_cover(both) is None
    assert _classify_amendment_cover("Report for the quarter ended March 31, 2026.") is None
