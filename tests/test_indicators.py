"""Tests for pure-math technical studies."""

from __future__ import annotations

from edgar.indicators import (
    bollinger_bands,
    ema,
    macd,
    opening_range_breakout,
    rsi,
    sma,
)


def test_sma_warms_up_then_tracks_average():
    values = [1, 2, 3, 4, 5, 6]
    result = sma(values, 3)
    assert result[:2] == [None, None]
    assert result[2] == 2.0  # (1+2+3)/3
    assert result[-1] == 5.0  # (4+5+6)/3


def test_ema_seeds_with_sma_then_diverges():
    values = [10, 11, 12, 13, 14, 20]
    result = ema(values, 3)
    assert result[:2] == [None, None]
    assert result[2] == sum(values[:3]) / 3
    # A big jump should pull the EMA up but not all the way to the new value.
    assert result[-1] is not None
    assert values[3] < result[-1] < values[-1]


def test_rsi_is_100_when_all_moves_are_gains():
    values = [10 + i for i in range(20)]  # strictly increasing
    result = rsi(values, window=14)
    assert result[14] == 100.0


def test_rsi_is_0_when_all_moves_are_losses():
    values = [30 - i for i in range(20)]  # strictly decreasing
    result = rsi(values, window=14)
    assert result[14] == 0.0


def test_rsi_short_series_returns_all_none():
    assert rsi([1, 2, 3], window=14) == [None, None, None]


def test_macd_histogram_is_macd_minus_signal():
    values = [100 + (i % 5) + i * 0.3 for i in range(60)]
    result = macd(values)
    for i in range(len(values)):
        if result.macd[i] is not None and result.signal[i] is not None:
            assert abs(result.histogram[i] - (result.macd[i] - result.signal[i])) < 1e-9


def test_bollinger_bands_bracket_the_middle_band():
    values = [100, 102, 98, 105, 95, 110, 90, 108, 92, 106, 94, 103, 97, 101, 99, 100, 102, 98, 105, 95, 100]
    bb = bollinger_bands(values, window=20)
    for upper, mid, lower in zip(bb.upper, bb.mid, bb.lower):
        if mid is not None:
            assert lower < mid < upper


def test_opening_range_breakout_classifies_above_below_inside():
    highs = [101, 102, 101.5, 100.8, 101.2, 101.9] + [103]
    lows = [99, 99.5, 99.2, 99.8, 99.6, 99.9] + [102.5]
    closes = [100, 100.5, 100.2, 100.4, 100.6, 100.8] + [103.5]  # breaks above 102 range high
    orb = opening_range_breakout(highs, lows, closes, opening_bars=6)
    assert orb.status == "ABOVE_RANGE"
    assert orb.breakout_pct > 0


def test_opening_range_breakout_returns_none_when_not_enough_bars():
    assert opening_range_breakout([1, 2], [1, 2], [1, 2], opening_bars=6) is None
