"""Tests for portfolio risk analytics (pure math)."""

from __future__ import annotations

from edgar.risk import (
    analyze_portfolio,
    annualized_volatility_pct,
    daily_returns,
    max_drawdown_pct,
    sharpe_ratio,
)


def test_daily_returns_basic():
    assert daily_returns([100, 110, 99]) == [0.1, -0.1]


def test_daily_returns_skips_zero_previous_close():
    assert daily_returns([0, 100]) == []


def test_max_drawdown_from_peak():
    # Peaks at 120, troughs at 90 -> -25% drawdown from that peak.
    closes = [100, 120, 110, 90, 95]
    assert round(max_drawdown_pct(closes), 2) == -25.0


def test_max_drawdown_zero_for_monotonic_rise():
    assert max_drawdown_pct([100, 105, 110, 120]) == 0.0


def test_annualized_volatility_zero_for_flat_returns():
    assert annualized_volatility_pct([0.0, 0.0, 0.0]) == 0.0


def test_annualized_volatility_positive_for_varying_returns():
    assert annualized_volatility_pct([0.01, -0.02, 0.015, -0.01, 0.02]) > 0


def test_sharpe_ratio_none_for_zero_variance():
    assert sharpe_ratio([0.01, 0.01, 0.01]) is None


def test_sharpe_ratio_positive_when_mean_return_exceeds_risk_free():
    returns = [0.01, 0.02, -0.005, 0.015, 0.008]
    assert sharpe_ratio(returns, risk_free_rate_pct=0.0) > 0


def test_analyze_portfolio_weights_by_value_and_aggregates():
    holdings = {
        "AAPL": (800.0, [100, 102, 104, 106, 108]),   # +8%, 80% of value
        "MSFT": (200.0, [200, 198, 202, 204, 210]),   # +5%, 20% of value
    }
    result = analyze_portfolio(holdings)
    assert result is not None
    assert len(result.positions) == 2
    assert result.positions[0].symbol == "AAPL"  # bigger weight sorts first
    assert round(result.positions[0].weight_pct, 1) == 80.0
    # Weighted return should be between the two individual returns.
    assert 5.0 < result.portfolio_return_pct < 8.0


def test_analyze_portfolio_skips_positions_with_insufficient_history():
    holdings = {
        "AAPL": (800.0, [100, 102, 104]),
        "TOOSHORT": (200.0, [50]),  # only one data point - unusable
    }
    result = analyze_portfolio(holdings)
    assert result is not None
    assert [p.symbol for p in result.positions] == ["AAPL"]


def test_analyze_portfolio_returns_none_when_nothing_usable():
    assert analyze_portfolio({"X": (100.0, [1])}) is None
