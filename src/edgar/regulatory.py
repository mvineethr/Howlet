"""SEC rulemaking and notices from the Federal Register API.

federalregister.gov is the US government's official daily journal; its
API is free, keyless, and unthrottled for polite use - same tier as the
Treasury/BLS sources in `macro.py`. This module pulls the newest
documents filed by the Securities and Exchange Commission (proposed
rules, final rules, notices - e.g. exchange rule changes, ETF
approvals), which slot into the ECO screen next to the Fed feeds.

Decoration tier: any failure degrades to an empty list, never raises.
"""

from __future__ import annotations

from typing import Optional

import requests

FEDERAL_REGISTER_URL = "https://www.federalregister.gov/api/v1/documents.json"

_SEC_AGENCY_SLUG = "securities-and-exchange-commission"


def get_sec_documents(
    limit: int = 20, session: Optional[requests.Session] = None
) -> list[dict]:
    """Newest SEC documents in the Federal Register. [] on any failure.

    Returns [{"title", "type", "document_number", "html_url",
    "publication_date"}, ...] newest first. `type` is the Federal
    Register category: "Rule", "Proposed Rule", or "Notice".
    """
    session = session or requests.Session()
    params = [
        ("conditions[agencies][]", _SEC_AGENCY_SLUG),
        ("per_page", str(min(limit, 100))),
        ("order", "newest"),
        ("fields[]", "title"),
        ("fields[]", "type"),
        ("fields[]", "document_number"),
        ("fields[]", "html_url"),
        ("fields[]", "publication_date"),
    ]
    try:
        resp = session.get(FEDERAL_REGISTER_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    documents = []
    for item in data.get("results", []) or []:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        documents.append(
            {
                "title": item.get("title"),
                "type": item.get("type"),
                "document_number": item.get("document_number"),
                "html_url": item.get("html_url"),
                "publication_date": item.get("publication_date"),
            }
        )
    return documents
