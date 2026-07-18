"""Technical studies computed from price history - pure math, no I/O.

Everything here operates on plain float lists (the close/high/low series
`market.py` already fetches), so it's independent of any data source and
fully unit-testable offline. Every function returns `None`/empty instead
of raising when there isn't enough history for the requested window -
callers decorate a chart, they shouldn't crash over a short series.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def sma(values: list[float], window: int) -> list[Optional[float]]:
    """Simple moving average, aligned 1:1 with `values` (None until warmed up)."""
    if window <= 0:
        raise ValueError("window must be positive")
    out: list[Optional[float]] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= window:
            running -= values[i - window]
        if i >= window - 1:
            out[i] = running / window
    return out


def ema(values: list[float], window: int) -> list[Optional[float]]:
    """Exponential moving average, seeded with an SMA over the first window."""
    if window <= 0:
        raise ValueError("window must be positive")
    out: list[Optional[float]] = [None] * len(values)
    if len(values) < window:
        return out
    k = 2.0 / (window + 1)
    seed = sum(values[:window]) / window
    out[window - 1] = seed
    prev = seed
    for i in range(window, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: list[float], window: int = 14) -> list[Optional[float]]:
    """Wilder's RSI (0-100). None for the warm-up period."""
    out: list[Optional[float]] = [None] * len(values)
    if len(values) <= window:
        return out

    gains = losses = 0.0
    for i in range(1, window + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain, avg_loss = gains / window, losses / window
    out[window] = _rsi_from_averages(avg_gain, avg_loss)

    for i in range(window + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain, loss = max(delta, 0.0), max(-delta, 0.0)
        avg_gain = (avg_gain * (window - 1) + gain) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window
        out[i] = _rsi_from_averages(avg_gain, avg_loss)
    return out


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@dataclass
class MACDResult:
    macd: list[Optional[float]]
    signal: list[Optional[float]]
    histogram: list[Optional[float]]


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> MACDResult:
    """MACD line (fast EMA - slow EMA), its signal EMA, and the histogram."""
    fast_ema, slow_ema = ema(values, fast), ema(values, slow)
    macd_line = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(fast_ema, slow_ema)
    ]
    # EMA of the MACD line itself, skipping the leading None gap.
    first = next((i for i, v in enumerate(macd_line) if v is not None), None)
    if first is None:
        return MACDResult(macd_line, [None] * len(values), [None] * len(values))

    tail_ema = ema([v for v in macd_line[first:] if v is not None], signal)
    signal_line: list[Optional[float]] = [None] * len(values)
    signal_line[first : first + len(tail_ema)] = tail_ema

    hist = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]
    return MACDResult(macd_line, signal_line, hist)


@dataclass
class BollingerBands:
    upper: list[Optional[float]]
    mid: list[Optional[float]]
    lower: list[Optional[float]]


def bollinger_bands(
    values: list[float], window: int = 20, num_std: float = 2.0
) -> BollingerBands:
    mid = sma(values, window)
    upper: list[Optional[float]] = [None] * len(values)
    lower: list[Optional[float]] = [None] * len(values)
    for i in range(len(values)):
        if mid[i] is None:
            continue
        window_vals = values[i - window + 1 : i + 1]
        mean = mid[i]
        variance = sum((v - mean) ** 2 for v in window_vals) / window
        std = variance**0.5
        upper[i] = mean + num_std * std
        lower[i] = mean - num_std * std
    return BollingerBands(upper=upper, mid=mid, lower=lower)


@dataclass
class OpeningRangeBreakout:
    """Today's opening-range high/low and where the last price sits vs it."""

    range_high: float
    range_low: float
    last_price: float
    status: str  # "ABOVE_RANGE" (bullish breakout), "BELOW_RANGE" (breakdown), "INSIDE_RANGE"

    @property
    def breakout_pct(self) -> float:
        """% distance of last price outside the range (0 if inside)."""
        if self.status == "ABOVE_RANGE":
            return (self.last_price - self.range_high) / self.range_high * 100.0
        if self.status == "BELOW_RANGE":
            return (self.last_price - self.range_low) / self.range_low * 100.0
        return 0.0


def opening_range_breakout(
    highs: list[float], lows: list[float], closes: list[float], opening_bars: int = 6
) -> Optional[OpeningRangeBreakout]:
    """Classic ORB: range of the first `opening_bars` intraday bars (e.g.
    6 x 5-minute bars = the first 30 minutes), compared to the latest price.
    Needs intraday (intraday-interval) bars for today, not daily closes.
    """
    if len(closes) < opening_bars + 1:
        return None
    range_high = max(highs[:opening_bars])
    range_low = min(lows[:opening_bars])
    last = closes[-1]
    if last > range_high:
        status = "ABOVE_RANGE"
    elif last < range_low:
        status = "BELOW_RANGE"
    else:
        status = "INSIDE_RANGE"
    return OpeningRangeBreakout(
        range_high=range_high, range_low=range_low, last_price=last, status=status
    )
