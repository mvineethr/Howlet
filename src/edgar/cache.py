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


class FilingCache:
    """One JSON file of parsed holdings per accession number."""

    def __init__(self, cache_dir: Optional[Path] = None):
        base = Path(cache_dir) if cache_dir else default_cache_dir()
        self.holdings_dir = base / "holdings"

    def _path(self, accession_number: str) -> Path:
        return self.holdings_dir / f"{accession_number.replace('-', '')}.json"

    def get_holdings(self, accession_number: str) -> Optional[list[Holding]]:
        try:
            with open(self._path(accession_number), encoding="utf-8") as f:
                raw = json.load(f)
            return [Holding(**entry) for entry in raw]
        except (OSError, ValueError, TypeError):
            return None

    def put_holdings(self, accession_number: str, holdings: list[Holding]) -> None:
        try:
            self.holdings_dir.mkdir(parents=True, exist_ok=True)
            with open(self._path(accession_number), "w", encoding="utf-8") as f:
                json.dump([asdict(h) for h in holdings], f)
        except OSError:
            pass  # cache is an optimization, never a failure


class Form4Cache:
    """One JSON file of parsed insider transactions per accession number."""

    def __init__(self, cache_dir: Optional[Path] = None):
        base = Path(cache_dir) if cache_dir else default_cache_dir()
        self.form4_dir = base / "form4"

    def _path(self, accession_number: str) -> Path:
        return self.form4_dir / f"{accession_number.replace('-', '')}.json"

    def get_transactions(
        self, accession_number: str
    ) -> Optional[list[InsiderTransaction]]:
        try:
            with open(self._path(accession_number), encoding="utf-8") as f:
                raw = json.load(f)
            return [InsiderTransaction(**entry) for entry in raw]
        except (OSError, ValueError, TypeError):
            return None

    def put_transactions(
        self, accession_number: str, transactions: list[InsiderTransaction]
    ) -> None:
        try:
            self.form4_dir.mkdir(parents=True, exist_ok=True)
            with open(self._path(accession_number), "w", encoding="utf-8") as f:
                json.dump([asdict(t) for t in transactions], f)
        except OSError:
            pass  # cache is an optimization, never a failure


def cached_form4_transactions(
    client: EdgarClient, cache: Optional[Form4Cache], filing: FilingSummary
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
    client: EdgarClient, cache: Optional[FilingCache], filing: FilingSummary
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
