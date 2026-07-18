"""Tests for the accession-keyed filing cache."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from edgar.cache import FilingCache, cached_information_table
from edgar.models import FilingSummary, Holding

FILING = FilingSummary(
    cik="0001067983",
    accession_number="0000950123-26-001234",
    filing_date=date(2026, 5, 15),
    period_of_report=date(2026, 3, 31),
    primary_doc="primary.xml",
)

HOLDINGS = [
    Holding(
        name_of_issuer="APPLE INC",
        cusip="037833100",
        value_usd=50_000_000,
        shares=300_000,
        share_type="SH",
        investment_discretion="SOLE",
    )
]


def test_round_trip(tmp_path):
    cache = FilingCache(cache_dir=tmp_path)
    assert cache.get_holdings(FILING.accession_number) is None

    cache.put_holdings(FILING.accession_number, HOLDINGS)
    loaded = cache.get_holdings(FILING.accession_number)
    assert loaded == HOLDINGS


def test_cached_information_table_fetches_once_then_reads_disk(tmp_path):
    cache = FilingCache(cache_dir=tmp_path)
    client = MagicMock()
    client.get_information_table.return_value = HOLDINGS

    first = cached_information_table(client, cache, FILING)
    second = cached_information_table(client, cache, FILING)

    assert first == second == HOLDINGS
    client.get_information_table.assert_called_once_with(FILING)


def test_cached_information_table_without_cache_always_fetches():
    client = MagicMock()
    client.get_information_table.return_value = HOLDINGS
    cached_information_table(client, None, FILING)
    cached_information_table(client, None, FILING)
    assert client.get_information_table.call_count == 2
