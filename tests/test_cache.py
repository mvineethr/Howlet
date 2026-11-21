"""Tests for the accession-keyed filing cache."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from howlet.cache import FilingCache, cached_information_table
from howlet.models import FilingSummary, Holding

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


# --- Phase 1: cache versioning (B2) ---

def test_old_unversioned_cache_file_is_ignored(tmp_path):
    import json

    cache = FilingCache(cache_dir=tmp_path)
    path = cache._path(FILING.accession_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Pre-fix format: a bare list of holdings, no version envelope.
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    "name_of_issuer": "APPLE INC",
                    "cusip": "037833100",
                    "value_usd": 50_000,
                    "shares": 300,
                    "share_type": "SH",
                    "investment_discretion": "SOLE",
                    "ticker": None,
                }
            ],
            f,
        )
    # Stale rows must not be served: the caller re-fetches instead.
    assert cache.get_holdings(FILING.accession_number) is None


def test_versioned_round_trip_keeps_put_call(tmp_path):
    cache = FilingCache(cache_dir=tmp_path)
    holdings = [
        Holding(
            name_of_issuer="NVIDIA CORP",
            cusip="67066G104",
            value_usd=1_000_000,
            shares=5_000,
            share_type="SH",
            investment_discretion="SOLE",
            put_call="PUT",
        )
    ]
    cache.put_holdings(FILING.accession_number, holdings)
    assert cache.get_holdings(FILING.accession_number) == holdings


def test_form4_cache_round_trip_and_version_guard(tmp_path):
    import json

    from howlet.cache import Form4Cache
    from howlet.form4 import InsiderTransaction

    txn = InsiderTransaction(
        insider_name="Jane Doe",
        insider_cik="0001234567",
        relationship="Director",
        transaction_date="2026-05-01",
        transaction_code="P",
        acquired_disposed="A",
        shares=100.0,
        price_per_share=10.0,
        value_usd=1000.0,
        shares_owned_after=1100.0,
        security_title="Common Stock",
        direct_or_indirect="D",
        filing_date="2026-05-02",
        accession_number="0001234567-26-000001",
    )
    cache = Form4Cache(cache_dir=tmp_path)
    cache.put_transactions(FILING.accession_number, [txn])
    assert cache.get_transactions(FILING.accession_number) == [txn]

    # An old-format bare list is invalidated, not served.
    path = cache._path(FILING.accession_number)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"insider_name": "Jane Doe"}], f)
    assert cache.get_transactions(FILING.accession_number) is None
