"""Free market data via Yahoo Finance's public chart endpoint.

No API key - this uses the same unauthenticated JSON endpoint that powers
finance.yahoo.com's charts (query1.finance.yahoo.com/v8/finance/chart).
It returns the latest price, previous close, and a daily close series in a
single request per symbol, which is all the dashboard needs for quotes and
sparklines.

This is an unofficial endpoint: it can change without notice, so every
parse failure degrades to "no quote" rather than raising, and callers must
treat quotes as best-effort decoration on top of the SEC 13F data (which is
the authoritative part of this tool).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Yahoo rejects blank/robotic user agents with 429s; a plain browser UA is
# what their own site sends and keeps the free endpoint happy.
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Be polite: this is a free consumer endpoint, not a data contract.
_MIN_INTERVAL_SECONDS = 0.25
_MAX_RETRIES = 2
_RETRY_BACKOFF_BASE_SECONDS = 1.0

# Sensible bar interval for each chart range (Yahoo rejects mismatched
# combos like range=5y&interval=5m).
RANGE_INTERVALS = {
    "1d": "5m",
    "5d": "30m",
    "1mo": "1d",
    "3mo": "1d",
    "6mo": "1d",
    "1y": "1d",
    "2y": "1wk",
    "5y": "1wk",
    "max": "1mo",
}


@dataclass
class Quote:
    """A point-in-time quote plus a close-price history.

    `sparkline` holds the close series and `history_ts` the matching unix
    timestamps (same length, None closes already dropped from both).
    """

    symbol: str
    price: float
    previous_close: Optional[float] = None
    currency: Optional[str] = None
    market_time: Optional[datetime] = None
    sparkline: list[float] = field(default_factory=list)
    history_ts: list[int] = field(default_factory=list)
    history_open: list[float] = field(default_factory=list)
    history_high: list[float] = field(default_factory=list)
    history_low: list[float] = field(default_factory=list)
    history_volume: list[float] = field(default_factory=list)
    long_name: Optional[str] = None
    exchange: Optional[str] = None
    instrument_type: Optional[str] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    week52_high: Optional[float] = None
    week52_low: Optional[float] = None
    volume: Optional[int] = None

    @property
    def change(self) -> Optional[float]:
        if self.previous_close is None:
            return None
        return self.price - self.previous_close

    @property
    def change_pct(self) -> Optional[float]:
        if not self.previous_close:
            return None
        return (self.price - self.previous_close) / self.previous_close * 100.0


class YahooMarketClient:
    """Fetch quotes/history from Yahoo Finance's free chart endpoint."""

    def __init__(self, user_agent: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or _DEFAULT_UA})
        self._last_request_at = 0.0

    def _get(self, url: str, **kwargs) -> requests.Response:
        resp: Optional[requests.Response] = None
        for attempt in range(_MAX_RETRIES + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < _MIN_INTERVAL_SECONDS:
                time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            resp = self.session.get(url, timeout=15, **kwargs)
            self._last_request_at = time.monotonic()

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_BASE_SECONDS * (2**attempt))
                    continue

            resp.raise_for_status()
            return resp

        resp.raise_for_status()
        return resp  # pragma: no cover - unreachable

    def get_quote(
        self, symbol: str, range_: str = "1mo", interval: str = "1d"
    ) -> Optional[Quote]:
        """Latest quote + close history for one symbol, or None on failure.

        Never raises for a bad/unknown symbol - a dashboard row without a
        price is better than a dashboard that 500s because one CUSIP mapped
        to a delisted ticker.
        """
        url = CHART_URL.format(symbol=symbol)
        try:
            resp = self._get(url, params={"range": range_, "interval": interval})
            data = resp.json()
        except (requests.RequestException, ValueError):
            return None
        quote = self._parse_chart(symbol, data)

        # chartPreviousClose is the close before the *range start*, so for
        # multi-day ranges quote.change would be the whole range's drift,
        # not the day move. With daily bars the true previous close is the
        # second-to-last bar (the last bar is the current/latest session).
        if quote is not None and interval == "1d" and len(quote.sparkline) >= 2:
            quote.previous_close = quote.sparkline[-2]
        return quote

    def get_security(self, symbol: str, range_: str = "6mo") -> Optional[Quote]:
        """Quote + price history for one symbol, with the bar interval
        picked automatically for the requested range (for chart screens)."""
        interval = RANGE_INTERVALS.get(range_, "1d")
        return self.get_quote(symbol, range_=range_, interval=interval)

    def get_quotes(
        self, symbols: list[str], range_: str = "1mo", interval: str = "1d"
    ) -> dict[str, Quote]:
        """Quotes for many symbols. Symbols that fail are simply absent."""
        quotes: dict[str, Quote] = {}
        for symbol in symbols:
            quote = self.get_quote(symbol, range_=range_, interval=interval)
            if quote is not None:
                quotes[symbol] = quote
        return quotes

    @staticmethod
    def _parse_chart(symbol: str, data: dict) -> Optional[Quote]:
        try:
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = float(meta["regularMarketPrice"])
        except (KeyError, IndexError, TypeError, ValueError):
            return None

        previous_close = meta.get("chartPreviousClose", meta.get("previousClose"))
        market_time = None
        if meta.get("regularMarketTime"):
            market_time = datetime.fromtimestamp(
                meta["regularMarketTime"], tz=timezone.utc
            )

        closes: list[float] = []
        history_ts: list[int] = []
        opens: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        volumes: list[float] = []
        try:
            quote0 = result["indicators"]["quote"][0]
            raw_closes = quote0["close"]
            raw_ts = result.get("timestamp") or [None] * len(raw_closes)
            raw_opens = quote0.get("open") or [None] * len(raw_closes)
            raw_highs = quote0.get("high") or [None] * len(raw_closes)
            raw_lows = quote0.get("low") or [None] * len(raw_closes)
            raw_volumes = quote0.get("volume") or [None] * len(raw_closes)
            for ts, close, open_, high, low, vol in zip(
                raw_ts, raw_closes, raw_opens, raw_highs, raw_lows, raw_volumes
            ):
                if close is None:
                    continue
                closes.append(float(close))
                history_ts.append(int(ts) if ts is not None else 0)
                opens.append(float(open_) if open_ is not None else float(close))
                highs.append(float(high) if high is not None else float(close))
                lows.append(float(low) if low is not None else float(close))
                volumes.append(float(vol) if vol is not None else 0.0)
        except (KeyError, IndexError, TypeError):
            pass

        def _num(key: str) -> Optional[float]:
            v = meta.get(key)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        volume = meta.get("regularMarketVolume")
        return Quote(
            symbol=meta.get("symbol", symbol),
            price=price,
            previous_close=(
                float(previous_close) if previous_close is not None else None
            ),
            currency=meta.get("currency"),
            market_time=market_time,
            sparkline=closes,
            history_ts=history_ts,
            history_open=opens,
            history_high=highs,
            history_low=lows,
            history_volume=volumes,
            long_name=meta.get("longName") or meta.get("shortName"),
            exchange=meta.get("fullExchangeName") or meta.get("exchangeName"),
            instrument_type=meta.get("instrumentType"),
            day_high=_num("regularMarketDayHigh"),
            day_low=_num("regularMarketDayLow"),
            week52_high=_num("fiftyTwoWeekHigh"),
            week52_low=_num("fiftyTwoWeekLow"),
            volume=int(volume) if volume is not None else None,
        )
