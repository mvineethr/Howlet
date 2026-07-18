"""Tests for the screener's pure row-building/filtering logic and cache."""

from __future__ import annotations

from edgar.fundamentals import FiscalYear
from edgar.screener import ScreenerCache, ScreenRow, _build_row, _passes_filters


def test_build_row_computes_pe_market_cap_growth_and_margin():
    years = [
        FiscalYear(fiscal_year=2025, end_date="2025-09-27",
                   revenue=400.0, net_income=100.0, eps_diluted=8.0),
        FiscalYear(fiscal_year=2024, end_date="2024-09-28",
                   revenue=350.0, net_income=80.0, eps_diluted=6.0),
    ]
    row = _build_row("AAPL", price=160.0, change_pct=1.5, shares=25.0, years=years)

    assert row.pe_ratio == 20.0  # 160 / 8
    assert row.market_cap == 4000.0  # 160 * 25
    assert row.net_margin_pct == 25.0  # 100 / 400
    assert round(row.revenue_growth_pct, 4) == round((400 - 350) / 350 * 100, 4)


def test_build_row_handles_missing_fundamentals_gracefully():
    row = _build_row("NEWCO", price=10.0, change_pct=0.0, shares=None, years=[])
    assert row.pe_ratio is None
    assert row.market_cap is None
    assert row.revenue_growth_pct is None
    assert row.net_margin_pct is None


def test_build_row_skips_pe_for_negative_eps():
    years = [FiscalYear(fiscal_year=2025, end_date="2025-12-31",
                        revenue=100.0, net_income=-5.0, eps_diluted=-1.0)]
    row = _build_row("LOSSCO", price=20.0, change_pct=0.0, shares=10.0, years=years)
    assert row.pe_ratio is None  # negative EPS -> P/E is meaningless


def test_passes_filters_requires_all_bounds_and_rejects_missing_values():
    row = ScreenRow(symbol="AAPL", pe_ratio=18.0, market_cap=3e12)
    assert _passes_filters(row, {"pe_ratio": (10, 25)})
    assert not _passes_filters(row, {"pe_ratio": (20, None)})
    assert not _passes_filters(row, {"revenue_growth_pct": (0, None)})  # None -> excluded


def test_screener_cache_round_trip(tmp_path):
    cache = ScreenerCache(cache_dir=tmp_path)
    assert cache.get("AAPL", "2026-07-06") is None
    cache.put("AAPL", "2026-07-06", {"symbol": "AAPL", "price": 200.0})
    assert cache.get("AAPL", "2026-07-06") == {"symbol": "AAPL", "price": 200.0}
    # A different day is a cache miss even for the same symbol.
    assert cache.get("AAPL", "2026-07-07") is None
