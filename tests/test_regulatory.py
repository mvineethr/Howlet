"""Tests for the Federal Register SEC-documents source."""

from __future__ import annotations

import responses

from edgar13f import regulatory

# Trimmed from a live response captured 2026-07-17 (fields[] filter on);
# keep the wrapper keys - results live under "results", not at top level.
FEDREG_JSON = {
    "description": "Documents from Securities and Exchange Commission",
    "count": 10000,
    "total_pages": 50,
    "results": [
        {
            "title": (
                "Self-Regulatory Organizations; NYSE American LLC; Notice of "
                "Filing... Options on iShares Bitcoin Trust ETF"
            ),
            "type": "Notice",
            "document_number": "2026-14526",
            "html_url": "https://www.federalregister.gov/documents/2026/07/17/2026-14526/x",
            "publication_date": "2026-07-17",
        },
        {
            "title": "Investment Company Act Release No. 35555",
            "type": "Notice",
            "document_number": "2026-14525",
            "html_url": "https://www.federalregister.gov/documents/2026/07/17/2026-14525/y",
            "publication_date": "2026-07-17",
        },
    ],
}


@responses.activate
def test_get_sec_documents_parses_results():
    responses.get(regulatory.FEDERAL_REGISTER_URL, json=FEDREG_JSON)
    docs = regulatory.get_sec_documents(limit=5)
    assert len(docs) == 2
    assert docs[0]["type"] == "Notice"
    assert docs[0]["publication_date"] == "2026-07-17"
    assert docs[0]["html_url"].startswith("https://www.federalregister.gov/")
    # The request must scope to the SEC agency and ask for newest first.
    query = responses.calls[0].request.url
    assert "securities-and-exchange-commission" in query
    assert "order=newest" in query


@responses.activate
def test_get_sec_documents_degrades_on_http_error():
    responses.get(regulatory.FEDERAL_REGISTER_URL, status=502)
    assert regulatory.get_sec_documents() == []


@responses.activate
def test_get_sec_documents_degrades_on_garbage():
    responses.get(regulatory.FEDERAL_REGISTER_URL, body="not json")
    assert regulatory.get_sec_documents() == []


@responses.activate
def test_get_sec_documents_skips_malformed_entries():
    payload = {"results": [{"type": "Rule"}, FEDREG_JSON["results"][0]]}
    responses.get(regulatory.FEDERAL_REGISTER_URL, json=payload)
    docs = regulatory.get_sec_documents()
    assert len(docs) == 1  # the title-less entry is dropped
