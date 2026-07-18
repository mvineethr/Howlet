"""Risk analytics for a user-defined (non-13F) portfolio.

Pure math over close-price history the caller supplies (from
`market.py`), so this has no I/O of its own and is fully unit-testable.
Volatility/Sharpe are annualized assuming daily bars (252 trading days);
callers passing weekly/monthly history should not treat these as
comparable without adjusting - documented, not silently handled, since
guessing the bar frequency wrong would produce a confidently wrong number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

TRADING_DAYS_PER_YEAR = 252


@dataclass
class PositionRisk:
    symbol: str
    weight_pct: float
    return_pct: float               # cumulative return over the supplied history
    annualized_volatility_pct: float
    max_drawdown_pct: float


@dataclass
class PortfolioRisk:
    positions: list[PositionRisk]
    portfolio_return_pct: float
    portfolio_annualized_volatility_pct: float
    portfolio_max_drawdown_pct: float
    sharpe_ratio: Optional[float]


def daily_returns(closes: list[float]) -> list[float]:
    return [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]


def annualized_volatility_pct(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0


def max_drawdown_pct(closes: list[float]) -> float:
    if len(closes) < 2:
        return 0.0
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        if peak:
            worst = min(worst, (price - peak) / peak)
    return worst * 100.0


def sharpe_ratio(returns: list[float], risk_free_rate_pct: float = 0.0) -> Optional[float]:
    """Annualized Sharpe. `risk_free_rate_pct` is an annual rate (e.g. pass
    the current 3-month T-bill yield from `macro.get_treasury_yield_curve`
    for a real risk-free proxy; defaults to 0 if you don't have one handy).
    """
    if len(returns) < 2:
        return None
    mean_daily = sum(returns) / len(returns)
    variance = sum((r - mean_daily) ** 2 for r in returns) / (len(returns) - 1)
    std_daily = math.sqrt(variance)
    if std_daily == 0:
        return None
    daily_rf = risk_free_rate_pct / 100.0 / TRADING_DAYS_PER_YEAR
    return (mean_daily - daily_rf) / std_daily * math.sqrt(TRADING_DAYS_PER_YEAR)


def analyze_portfolio(
    holdings: dict[str, tuple[float, list[float]]],
    risk_free_rate_pct: float = 0.0,
) -> Optional[PortfolioRisk]:
    """`holdings` maps symbol -> (dollar_value_now, close_price_history).

    All histories should cover the same period/frequency; positions with
    fewer than 2 closes are skipped (nothing to compute a return from).
    """
    usable = {s: (v, c) for s, (v, c) in holdings.items() if len(c) >= 2}
    if not usable:
        return None

    total_value = sum(v for v, _ in usable.values())
    positions = []
    weighted_returns_by_day: list[list[float]] = []

    for symbol, (value, closes) in usable.items():
        weight_pct = value / total_value * 100.0 if total_value else 0.0
        rets = daily_returns(closes)
        positions.append(
            PositionRisk(
                symbol=symbol,
                weight_pct=weight_pct,
                return_pct=(closes[-1] - closes[0]) / closes[0] * 100.0 if closes[0] else 0.0,
                annualized_volatility_pct=annualized_volatility_pct(rets),
                max_drawdown_pct=max_drawdown_pct(closes),
            )
        )
        weighted_returns_by_day.append([r * (weight_pct / 100.0) for r in rets])

    min_len = min((len(r) for r in weighted_returns_by_day), default=0)
    portfolio_returns = [
        sum(day[i] for day in weighted_returns_by_day) for i in range(min_len)
    ]

    portfolio_value_series = _synthetic_index(portfolio_returns)
    return PortfolioRisk(
        positions=sorted(positions, key=lambda p: p.weight_pct, reverse=True),
        portfolio_return_pct=sum(p.return_pct * p.weight_pct / 100.0 for p in positions),
        portfolio_annualized_volatility_pct=annualized_volatility_pct(portfolio_returns),
        portfolio_max_drawdown_pct=max_drawdown_pct(portfolio_value_series),
        sharpe_ratio=sharpe_ratio(portfolio_returns, risk_free_rate_pct),
    )


def _synthetic_index(returns: list[float], base: float = 100.0) -> list[float]:
    """Rebuild a price-like series from daily returns, for drawdown math."""
    series = [base]
    for r in returns:
        series.append(series[-1] * (1 + r))
    return series
