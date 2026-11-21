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
    sharpe_ratio: float | None


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


def sharpe_ratio(returns: list[float], risk_free_rate_pct: float = 0.0) -> float | None:
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


def _align_on_timestamps(
    stamped: dict[str, tuple[float, list[float], list[int]]],
) -> dict[str, tuple[float, list[float]]]:
    """Intersect timestamped histories on their common dates.

    Returns {symbol: (value, aligned_closes)} using only dates present
    in every series, oldest first. Returns {} when fewer than 2 common
    dates exist - the caller then falls back to the unaligned series
    rather than computing on a single bar.
    """
    per_symbol: dict[str, tuple[float, dict[int, float]]] = {}
    for symbol, (value, closes, stamps) in stamped.items():
        by_ts: dict[int, float] = {}
        for ts, close in zip(stamps, closes, strict=False):  # aligned by _align_on_timestamps; truncate if ragged
            if ts:
                by_ts.setdefault(int(ts), float(close))
        per_symbol[symbol] = (value, by_ts)
    common: set[int] | None = None
    for _, by_ts in per_symbol.values():
        keys = set(by_ts)
        common = keys if common is None else common & keys
    if not common or len(common) < 2:
        return {}
    ordered = sorted(common)
    return {
        symbol: (value, [by_ts[ts] for ts in ordered])
        for symbol, (value, by_ts) in per_symbol.items()
    }


def analyze_portfolio(
    holdings: dict[
        str,
        tuple[float, list[float]] | tuple[float, list[float], list[int]],
    ],
    risk_free_rate_pct: float = 0.0,
) -> PortfolioRisk | None:
    """`holdings` maps symbol -> (dollar_value_now, close_price_history),
    optionally with a third element of matching unix timestamps.

    Histories with timestamps are aligned on their common dates first:
    an IPO mid-range, a halted stock, or a missing bar must not shift
    one series against the others (index-zipping silently combines
    different calendar days). Without timestamps the old index-based
    behavior applies; positions with fewer than 2 closes are skipped.
    """
    usable: dict[str, tuple[float, list[float]]] = {}
    stamped: dict[str, tuple[float, list[float], list[int]]] = {}
    for symbol, entry in holdings.items():
        if len(entry) == 3:
            value, closes, stamps = entry
            if len(closes) >= 2 and len(stamps) == len(closes):
                stamped[symbol] = (value, closes, stamps)
            elif len(closes) >= 2:
                # Timestamps that don't line up with the closes (e.g. a
                # hand-built Quote with no history_ts) degrade to the
                # unaligned 2-tuple form rather than dropping the position.
                usable[symbol] = (value, closes)
        elif len(entry) == 2:
            value, closes = entry
            if len(closes) >= 2:
                usable[symbol] = (value, closes)

    if stamped:
        aligned = _align_on_timestamps(stamped)
        if aligned:
            usable.update(aligned)
        else:
            # Too few common dates to align: fall back to the raw
            # (index-based) series rather than dropping the positions.
            usable.update(
                {s: (v, c) for s, (v, c, _t) in stamped.items()}
            )
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
