"""Tests for EDGAR full-text search parsing (offline, mocked HTTP)."""

from __future__ import annotations

import json

import responses

from edgar13f.client import EdgarClient
from edgar13f.fulltext import FULLTEXT_SEARCH_URL, search_filings

# Trimmed from a live efts.sec.gov response captured 2026-07-17 -
# Elasticsearch envelope, ids as "accession:filename", zero-padded ciks.
SAMPLE_EFTS_RESPONSE = {
    "hits": {
        "total": {"value": 10000, "relation": "gte"},
        "hits": [
            {
                "_id": "0001683168-20-000837:radnet_8k-ex9901.htm",
                "_source": {
                    "ciks": ["0000790526"],
                    "display_names": ["RadNet, Inc.  (RDNT)  (CIK 0000790526)"],
                    "root_forms": ["8-K"],
                    "file_date": "2020-03-16",
                    "form": "8-K",
                    "adsh": "0001683168-20-000837",
                    "file_type": "EX-99.1",
                    "file_description": "TRANSCRIPT OF CONFERENCE CALL",
                },
            },
            {  # missing filename separator - url must degrade to None
                "_id": "malformed-id-without-colon",
                "_source": {
                    "ciks": [],
                    "display_names": [],
                    "root_forms": [],
                    "file_date": "2026-01-01",
                    "form": "10-K",
                    "adsh": "",
                },
            },
        ],
    }
}


@responses.activate
def test_search_filings_parses_hits_and_builds_urls():
    responses.get(
        FULLTEXT_SEARCH_URL,
        body=json.dumps(SAMPLE_EFTS_RESPONSE),
        content_type="application/json",
    )
    client = EdgarClient("Test Suite test@example.com")
    results = search_filings(client, '"artificial intelligence"', forms=["8-K"])

    assert len(results) == 2
    first = results[0]
    assert first["company"].startswith("RadNet")
    assert first["form"] == "8-K"
    assert first["file_date"] == "2020-03-16"
    # cik is de-zero-padded in the archives path, accession loses dashes.
    assert first["url"] == (
        "https://www.sec.gov/Archives/edgar/data/790526/"
        "000168316820000837/radnet_8k-ex9901.htm"
    )
    # Malformed hit degrades instead of raising.
    assert results[1]["url"] is None
    assert results[1]["company"] == ""

    # The forms filter must be passed through to the API.
    assert "forms=8-K" in responses.calls[0].request.url


@responses.activate
def test_search_filings_respects_limit():
    responses.get(
        FULLTEXT_SEARCH_URL,
        body=json.dumps(SAMPLE_EFTS_RESPONSE),
        content_type="application/json",
    )
    client = EdgarClient("Test Suite test@example.com")
    assert len(search_filings(client, "anything", limit=1)) == 1
