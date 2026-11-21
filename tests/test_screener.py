"""Tests for the screener's pure row-building/filtering logic and cache."""

from __future__ import annotations

from howlet.fundamentals import FiscalYear
from howlet.screener import ScreenerCache, ScreenRow, _build_row, _passes_filters


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


# --- Phase 2: write-once cache (B3) + per-symbol guard (B6) ---

def test_screener_cache_put_does_not_write_until_save(tmp_path):
    cache = ScreenerCache(cache_dir=tmp_path)
    cache.put("AAPL", "2026-07-06", {"symbol": "AAPL", "price": 200.0})
    cache.put("MSFT", "2026-07-06", {"symbol": "MSFT", "price": 300.0})
    # Puts are in-memory only: no file yet after two puts.
    assert not cache.path.exists()
    cache.save()
    assert cache.path.exists()
    # A fresh instance reads back what save() wrote.
    fresh = ScreenerCache(cache_dir=tmp_path)
    assert fresh.get("AAPL", "2026-07-06") == {"symbol": "AAPL", "price": 200.0}
    assert fresh.get("MSFT", "2026-07-06") == {"symbol": "MSFT", "price": 300.0}


def test_screener_cache_save_is_noop_when_nothing_changed(tmp_path):
    cache = ScreenerCache(cache_dir=tmp_path)
    cache.save()  # nothing put: no file, no error
    assert not cache.path.exists()


def test_screen_skips_symbol_whose_facts_fetch_fails(tmp_path):
    from unittest.mock import MagicMock

    import requests

    from howlet.market import Quote
    from howlet.screener import screen

    market = MagicMock()
    market.get_quote.side_effect = lambda symbol, **kw: Quote(
        symbol=symbol, price=100.0, previous_close=99.0
    )
    fundamentals = MagicMock()
    fundamentals.ticker_to_cik.side_effect = lambda symbol: "0000320193"
    fundamentals.get_company_facts.side_effect = requests.ConnectionError(
        "SEC hiccup"
    )

    # Every symbol's facts fetch fails: the screen is empty, not an exception.
    rows = screen(market, fundamentals, universe=["AAPL", "MSFT"], cache=None)
    assert rows == []


def test_screen_keeps_good_symbols_when_one_fails(tmp_path):
    from unittest.mock import MagicMock

    import requests

    from howlet.market import Quote
    from howlet.screener import screen

    market = MagicMock()
    market.get_quote.side_effect = lambda symbol, **kw: Quote(
        symbol=symbol, price=100.0, previous_close=99.0
    )
    fundamentals = MagicMock()
    fundamentals.ticker_to_cik.side_effect = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
    }.get
    def facts(cik):
        if cik == "0000789019":
            raise requests.ConnectionError("SEC hiccup")
        return {"facts": {}}
    fundamentals.get_company_facts.side_effect = facts

    cache = ScreenerCache(cache_dir=tmp_path)
    rows = screen(
        market, fundamentals, universe=["AAPL", "MSFT"], cache=cache
    )
    assert [r.symbol for r in rows] == ["AAPL"]
    # The run wrote the cache file once at the end.
    assert cache.path.exists()
