"""Disk cache for parsed EDGAR filings (13F info tables, Form 4s).

A filing never changes once it's on EDGAR, so its parsed contents are
cached forever, keyed by accession number. This makes repeated `holdings`
/ `diff` / `insiders` runs and every dashboard reload near-instant after
the first fetch, and keeps request volume against SEC low.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .client import EdgarClient
from .form4 import InsiderTransaction, get_form4_transactions
from .models import FilingSummary, Holding
from .tickers import default_cache_dir

# Bump whenever a parser change makes previously cached rows wrong
# (e.g. the 13F put/call + pre-2023 thousands fixes): caches written by
# an older version are ignored and re-fetched instead of served stale.
CACHE_VERSION = 2


def _versioned(payload: dict) -> dict:
    return {"version": CACHE_VERSION, **payload}


def _unversioned(raw) -> dict | None:
    """Payload dict when `raw` is a current-version cache file, else None.

    Old cache files (bare list/dict with no "version" key) are treated
    as version 1 and invalidated, so a parser fix can't keep serving
    rows written by the old parser.
    """
    if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
        return None
    return raw


class FilingCache:
    """One JSON file of parsed holdings per accession number."""

    def __init__(self, cache_dir: Path | None = None):
        base = Path(cache_dir) if cache_dir else default_cache_dir()
        self.holdings_dir = base / "holdings"

    def _path(self, accession_number: str) -> Path:
        return self.holdings_dir / f"{accession_number.replace('-', '')}.json"

    def get_holdings(self, accession_number: str) -> list[Holding] | None:
        try:
            with open(self._path(accession_number), encoding="utf-8") as f:
                raw = json.load(f)
            payload = _unversioned(raw)
            if payload is None:
                return None
            return [Holding(**entry) for entry in payload["holdings"]]
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def put_holdings(self, accession_number: str, holdings: list[Holding]) -> None:
        try:
            self.holdings_dir.mkdir(parents=True, exist_ok=True)
            with open(self._path(accession_number), "w", encoding="utf-8") as f:
                json.dump(
                    _versioned({"holdings": [asdict(h) for h in holdings]}), f
                )
        except OSError:
            pass  # cache is an optimization, never a failure


class Form4Cache:
    """One JSON file of parsed insider transactions per accession number."""

    def __init__(self, cache_dir: Path | None = None):
        base = Path(cache_dir) if cache_dir else default_cache_dir()
        self.form4_dir = base / "form4"

    def _path(self, accession_number: str) -> Path:
        return self.form4_dir / f"{accession_number.replace('-', '')}.json"

    def get_transactions(
        self, accession_number: str
    ) -> list[InsiderTransaction] | None:
        try:
            with open(self._path(accession_number), encoding="utf-8") as f:
                raw = json.load(f)
            payload = _unversioned(raw)
            if payload is None:
                return None
            return [InsiderTransaction(**entry) for entry in payload["transactions"]]
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def put_transactions(
        self, accession_number: str, transactions: list[InsiderTransaction]
    ) -> None:
        try:
            self.form4_dir.mkdir(parents=True, exist_ok=True)
            with open(self._path(accession_number), "w", encoding="utf-8") as f:
                json.dump(
                    _versioned({"transactions": [asdict(t) for t in transactions]}), f
                )
        except OSError:
            pass  # cache is an optimization, never a failure


def cached_form4_transactions(
    client: EdgarClient, cache: Form4Cache | None, filing: FilingSummary
) -> list[InsiderTransaction]:
    """Fetch a Form 4's transactions through the cache (if provided)."""
    if cache is not None:
        cached = cache.get_transactions(filing.accession_number)
        if cached is not None:
            return cached
    transactions = get_form4_transactions(client, filing)
    if cache is not None:
        cache.put_transactions(filing.accession_number, transactions)
    return transactions


def cached_information_table(
    client: EdgarClient, cache: FilingCache | None, filing: FilingSummary
) -> list[Holding]:
    """Fetch a filing's holdings through the cache (if one is provided)."""
    if cache is not None:
        cached = cache.get_holdings(filing.accession_number)
        if cached is not None:
            return cached
    holdings = client.get_information_table(filing)
    if cache is not None:
        cache.put_holdings(filing.accession_number, holdings)
    return holdings
