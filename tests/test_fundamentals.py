"""Tests for SEC XBRL fundamentals extraction (offline, mocked HTTP)."""

from __future__ import annotations

import responses

from edgar.client import EdgarClient
from edgar.fundamentals import (
    COMPANY_FACTS_URL,
    TICKER_MAP_URL,
    FundamentalsClient,
    extract_annual_metrics,
    extract_shares_outstanding,
)


def _facts_payload():
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            # Quarterly comparative inside a 10-K: must be skipped.
                            {"form": "10-K", "fp": "FY", "fy": 2025,
                             "start": "2025-06-29", "end": "2025-09-27",
                             "filed": "2025-11-01", "val": 94_930_000_000},
                            # Full-year figures.
                            {"form": "10-K", "fp": "FY", "fy": 2024,
                             "start": "2023-10-01", "end": "2024-09-28",
                             "filed": "2024-11-01", "val": 391_035_000_000},
                            {"form": "10-K", "fp": "FY", "fy": 2025,
                             "start": "2024-09-29", "end": "2025-09-27",
                             "filed": "2025-11-01", "val": 416_161_000_000},
                            # 10-Q data must be ignored.
                            {"form": "10-Q", "fp": "Q1", "fy": 2025,
                             "start": "2024-09-29", "end": "2024-12-28",
                             "filed": "2025-01-30", "val": 124_300_000_000},
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2025,
                             "start": "2024-09-29", "end": "2025-09-27",
                             "filed": "2025-11-01", "val": 112_010_000_000},
                        ]
                    }
                },
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {"form": "10-K", "fp": "FY", "fy": 2025,
                             "start": "2024-09-29", "end": "2025-09-27",
                             "filed": "2025-11-01", "val": 7.46},
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2025,
                             "end": "2025-09-27", "filed": "2025-11-01",
                             "val": 365_000_000_000},
                        ]
                    }
                },
            }
        },
    }


def test_extract_annual_metrics_filters_to_full_year_10k_data():
    rows = extract_annual_metrics(_facts_payload(), years=5)
    assert [r.fiscal_year for r in rows] == [2025, 2024]

    fy2025 = rows[0]
    assert fy2025.end_date == "2025-09-27"
    assert fy2025.revenue == 416_161_000_000  # not the Q4 comparative
    assert fy2025.net_income == 112_010_000_000
    assert fy2025.eps_diluted == 7.46
    assert fy2025.total_assets == 365_000_000_000
    assert fy2025.total_liabilities is None  # absent concept -> None

    fy2024 = rows[1]
    assert fy2024.revenue == 391_035_000_000
    assert fy2024.net_income is None


def test_extract_handles_missing_gaap_section():
    assert extract_annual_metrics({"facts": {}}) == []


def test_extract_shares_outstanding_picks_the_most_recent_entry():
    facts = {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {"end": "2025-06-30", "val": 15_200_000_000},
                            {"end": "2025-10-15", "val": 14_900_000_000},  # newest
                            {"end": "2024-11-01", "val": 15_500_000_000},
                        ]
                    }
                }
            }
        }
    }
    assert extract_shares_outstanding(facts) == 14_900_000_000


def test_extract_shares_outstanding_missing_returns_none():
    assert extract_shares_outstanding({"facts": {}}) is None


@responses.activate
def test_ticker_to_cik_and_annual_metrics_end_to_end():
    responses.get(
        TICKER_MAP_URL,
        json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}},
    )
    responses.get(
        COMPANY_FACTS_URL.format(cik="0000320193"), json=_facts_payload()
    )

    client = FundamentalsClient(EdgarClient("Test Suite test@example.com"))
    assert client.ticker_to_cik("aapl") == "320193"
    assert client.company_name("AAPL") == "Apple Inc."
    assert client.ticker_to_cik("NOPE") is None

    rows = client.annual_metrics("AAPL")
    assert rows[0].fiscal_year == 2025

    # Ticker map is fetched once and reused.
    assert sum(1 for c in responses.calls if TICKER_MAP_URL in c.request.url) == 1


@responses.activate
def test_shares_outstanding_end_to_end():
    responses.get(
        TICKER_MAP_URL,
        json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}},
    )
    facts = _facts_payload()
    facts["facts"]["dei"] = {
        "EntityCommonStockSharesOutstanding": {
            "units": {"shares": [{"end": "2025-10-15", "val": 14_900_000_000}]}
        }
    }
    responses.get(COMPANY_FACTS_URL.format(cik="0000320193"), json=facts)

    client = FundamentalsClient(EdgarClient("Test Suite test@example.com"))
    assert client.shares_outstanding("AAPL") == 14_900_000_000
    assert client.shares_outstanding("NOPE") is None


def test_normalize_company_name_strips_suffix_noise():
    from edgar.fundamentals import normalize_company_name

    # Both spellings seen live for the same company (13F vs SEC map).
    assert normalize_company_name("CHUBB LIMITED") == "CHUBB"
    assert normalize_company_name("CHUBB LTD SWITZ") == "CHUBB"
    assert normalize_company_name("Chubb Ltd") == "CHUBB"
    assert normalize_company_name("PROCTER & GAMBLE CO") == "PROCTER GAMBLE"
    # Mid-name tokens are NOT stripped - only trailing noise.
    assert normalize_company_name("GROUP 1 AUTOMOTIVE INC") == "GROUP 1 AUTOMOTIVE"


def test_name_to_ticker_matches_sec_titles_first_class_wins():
    from unittest.mock import MagicMock

    from edgar.fundamentals import FundamentalsClient

    edgar = MagicMock()
    edgar._get.return_value.json.return_value = {
        # File order matters: SEC lists the primary class first
        # (GOOGL before GOOG, verified live).
        "0": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
        "1": {"cik_str": 1652044, "ticker": "GOOG", "title": "Alphabet Inc."},
        "2": {"cik_str": 896159, "ticker": "CB", "title": "Chubb Ltd"},
    }
    f = FundamentalsClient(edgar)
    assert f.name_to_ticker("CHUBB LIMITED") == "CB"
    assert f.name_to_ticker("CHUBB LTD SWITZ") == "CB"
    assert f.name_to_ticker("ALPHABET INC") == "GOOGL"
    assert f.name_to_ticker("NO SUCH ISSUER CORP") is None
