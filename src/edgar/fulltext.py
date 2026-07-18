"""EDGAR full-text search (efts.sec.gov) - keyless, official.

The backend of https://efts.sec.gov/LATEST/search-index?q=... - the same
API that powers EDGAR's own full-text search UI. It indexes the *content*
of filings (2001-present), so you can find every 8-K that mentions a
phrase, not just filings BY a company. Elasticsearch-style JSON out;
results are relevance-ranked (file_date included per hit).

Routed through EdgarClient for the shared throttle/retry and the
required User-Agent. SEC data tier: failures raise (callers map to 502).
"""

from __future__ import annotations

from typing import Optional

from .client import EdgarClient

FULLTEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


def search_filings(
    client: EdgarClient,
    query: str,
    forms: Optional[list[str]] = None,
    limit: int = 20,
) -> list[dict]:
    """Full-text search across EDGAR filings. Quote a phrase for exact
    match (the API treats "..." as a phrase, bare words as AND terms).

    `forms` filters to root form types (e.g. ["8-K", "10-K"]).
    """
    params = {"q": query}
    if forms:
        params["forms"] = ",".join(forms)
    data = client._get(FULLTEXT_SEARCH_URL, params=params).json()

    results = []
    for hit in data.get("hits", {}).get("hits", [])[:limit]:
        source = hit.get("_source", {})
        adsh = source.get("adsh", "")
        doc_id = hit.get("_id", "")
        filename = doc_id.split(":", 1)[1] if ":" in doc_id else ""
        ciks = source.get("ciks") or []
        cik = ciks[0].lstrip("0") if ciks else ""
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{adsh.replace('-', '')}/{filename}"
            if cik and adsh and filename
            else None
        )
        results.append(
            {
                "company": (source.get("display_names") or [""])[0],
                "cik": ciks[0] if ciks else None,
                "form": source.get("form"),
                "root_form": (source.get("root_forms") or [None])[0],
                "file_date": source.get("file_date"),
                "file_type": source.get("file_type"),
                "file_description": source.get("file_description"),
                "accession_number": adsh,
                "url": url,
            }
        )
    return results
