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

Two layers keep the UI from blanking when Yahoo hiccups:
- Nasdaq's public quote API (api.nasdaq.com, keyless) is a fallback for
  plain US stock/ETF tickers on daily bars. (Stooq, the usual free
  fallback, now sits behind a JS proof-of-work bot wall - not usable.)
- Every successful quote is kept in memory: reused while fresh, and served
  stale when every source fails, so an outage shows old prices, not none.
"""

from __future__ import annotations

import re
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
NASDAQ_INFO_URL = "https://api.nasdaq.com/api/quote/{symbol}/info"
NASDAQ_HISTORY_URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"

# Symbols per batched quote request (keeps the URL short).
_BATCH_CHUNK = 25

# Reuse a quote this long before refetching; past it, keep it as the
# stale-if-error copy. Dashboard polls are slower than this anyway.
_FRESH_SECONDS = 30.0

# Plain US tickers only (AAPL, BRK-B). Indices (^GSPC), FX (EURUSD=X),
# futures (CL=F), crypto (BTC-USD) and foreign listings aren't on Nasdaq.
_NASDAQ_SYMBOL = re.compile(r"^[A-Z]{1,5}(-[A-Z])?$")

# Calendar days of history to request from Nasdaq per Yahoo range.
_NASDAQ_RANGE_DAYS = {"5d": 7, "1mo": 31, "3mo": 92, "6mo": 183, "1y": 366}

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
    previous_close: float | None = None
    currency: str | None = None
    market_time: datetime | None = None
    sparkline: list[float] = field(default_factory=list)
    history_ts: list[int] = field(default_factory=list)
    history_open: list[float] = field(default_factory=list)
    history_high: list[float] = field(default_factory=list)
    history_low: list[float] = field(default_factory=list)
    history_volume: list[float] = field(default_factory=list)
    long_name: str | None = None
    exchange: str | None = None
    instrument_type: str | None = None
    day_high: float | None = None
    day_low: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    volume: int | None = None

    @property
    def change(self) -> float | None:
        if self.previous_close is None:
            return None
        return self.price - self.previous_close

    @property
    def change_pct(self) -> float | None:
        if not self.previous_close:
            return None
        return (self.price - self.previous_close) / self.previous_close * 100.0


def split_factor_between(splits: list[dict], start: date, end: date) -> float:
    """Cumulative split factor for splits with start < date <= end.

    Each split is {"date": "YYYY-MM-DD", "numerator": n,
    "denominator": d} - a 4:1 split is numerator 4, denominator 1, so
    100 shares before it are 400 after, and prior share counts are
    multiplied by the factor before comparing. 1.0 when no split
    applies in the window.
    """
    factor = 1.0
    for split in splits:
        try:
            when = date.fromisoformat(split["date"])
            num = float(split["numerator"])
            den = float(split["denominator"])
        except (KeyError, TypeError, ValueError):
            continue
        if den and start < when <= end:
            factor *= num / den
    return factor


def _open_stamp(day) -> datetime:
    # 14:30 UTC = US open, like Yahoo's daily stamps; midnight UTC would
    # render as the previous day in US timezones.
    return datetime(day.year, day.month, day.day, 14, 30, tzinfo=timezone.utc)


class YahooMarketClient:
    """Fetch quotes/history from Yahoo Finance's free chart endpoint."""

    def __init__(self, user_agent: str | None = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or _DEFAULT_UA})
        self._last_request_at = 0.0
        # (symbol, range, interval) -> (fetched_at monotonic, Quote)
        self._cache: dict[tuple[str, str, str], tuple[float, Quote]] = {}
        # symbol -> (fetched_at monotonic, Quote) for the batched quote
        # path. Kept separate from _cache on purpose: batch quotes carry
        # price fields but no history, and must never be served to a
        # caller that asked for a history (get_quote / with_history).
        self._batch_cache: dict[str, tuple[float, Quote]] = {}

    def _get(self, url: str, **kwargs) -> requests.Response:
        """GET with throttle + retry/backoff on 429 and 5xx.

        Transport-level ConnectionErrors are retried too, mirroring
        `EdgarClient._get`: Yahoo drops stale keep-alive connections
        just like SEC does, and a retry on a fresh connection almost
        always succeeds. After exhausting retries, callers see the
        usual requests exception.
        """
        resp: requests.Response | None = None
        for attempt in range(_MAX_RETRIES + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < _MIN_INTERVAL_SECONDS:
                time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            try:
                resp = self.session.get(url, timeout=15, **kwargs)
            except requests.ConnectionError:
                self._last_request_at = time.monotonic()
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_BASE_SECONDS * (2**attempt))
                    continue
                raise
            self._last_request_at = time.monotonic()

            if (resp.status_code == 429 or resp.status_code >= 500) and attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_BASE_SECONDS * (2**attempt))
                continue

            resp.raise_for_status()
            return resp

        resp.raise_for_status()
        return resp  # pragma: no cover - unreachable

    def get_quote(
        self, symbol: str, range_: str = "1mo", interval: str = "1d"
    ) -> Quote | None:
        """Latest quote + close history for one symbol, or None on failure.

        Never raises for a bad/unknown symbol - a dashboard row without a
        price is better than a dashboard that 500s because one CUSIP mapped
        to a delisted ticker.

        Order: fresh cache -> Yahoo -> Nasdaq (daily bars only) -> stale
        cache -> None.
        """
        key = (symbol, range_, interval)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < _FRESH_SECONDS:
            return cached[1]

        quote = self._yahoo_quote(symbol, range_, interval)
        if quote is None and interval == "1d":
            quote = self._nasdaq_quote(symbol, range_)
        if quote is None:
            return cached[1] if cached else None
        self._cache[key] = (time.monotonic(), quote)
        return quote

    def _yahoo_quote(self, symbol: str, range_: str, interval: str) -> Quote | None:
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

    def _nasdaq_json(self, url: str, asset_class: str, **params) -> dict | None:
        try:
            body = self._get(url, params={"assetclass": asset_class, **params}).json()
        except (requests.RequestException, ValueError):
            return None
        return body.get("data") if isinstance(body, dict) else None

    def _nasdaq_quote(self, symbol: str, range_: str) -> Quote | None:
        """Daily-bar Quote from api.nasdaq.com, or None. Same shape as Yahoo's."""
        days = _NASDAQ_RANGE_DAYS.get(range_)
        if days is None or not _NASDAQ_SYMBOL.match(symbol):
            return None
        nsym = symbol.replace("-", ".")  # Nasdaq spells BRK-B as BRK.B
        info_url = NASDAQ_INFO_URL.format(symbol=nsym)
        # A symbol is one asset class; "stocks" for SPY is "Symbol not exists".
        for asset_class in ("stocks", "etf"):
            info = self._nasdaq_json(info_url, asset_class)
            if info:
                break
        else:
            return None
        today = datetime.now(timezone.utc).date()
        hist = self._nasdaq_json(
            NASDAQ_HISTORY_URL.format(symbol=nsym),
            asset_class,
            fromdate=(today - timedelta(days=days)).isoformat(),
            todate=today.isoformat(),
            limit=400,
        )
        return self._parse_nasdaq(symbol, info, hist)

    @staticmethod
    def _parse_nasdaq(symbol: str, info: dict, hist: dict | None) -> Quote | None:
        def num(v) -> float | None:
            try:
                return float(str(v).replace("$", "").replace(",", "").replace("%", ""))
            except (TypeError, ValueError):
                return None

        primary = info.get("primaryData") or {}
        price = num(primary.get("lastSalePrice"))
        if price is None:
            return None
        net = num(primary.get("netChange"))
        trade_day = None
        with suppress(KeyError, TypeError, ValueError):  # "Oct 19, 2026 11:34 AM ET"
            trade_day = datetime.strptime(
                primary["lastTradeTimestamp"][:12].rstrip(), "%b %d, %Y"
            ).date()

        bars = []  # (date, o, h, l, c, v), oldest first
        rows = ((hist or {}).get("tradesTable") or {}).get("rows") or []
        for r in reversed(rows):
            try:
                day = datetime.strptime(r["date"], "%m/%d/%Y").date()
            except (KeyError, TypeError, ValueError):
                continue
            c = num(r.get("close"))
            if c is None:
                continue
            bars.append(
                (
                    day,
                    num(r.get("open")) or c,
                    num(r.get("high")) or c,
                    num(r.get("low")) or c,
                    c,
                    num(r.get("volume")) or 0.0,
                )
            )
        # Nasdaq history stops at the last close; Yahoo's daily series ends
        # with the live session, so add today's bar to keep the same shape.
        if trade_day and (not bars or bars[-1][0] < trade_day):
            bars.append(
                (
                    trade_day,
                    price,
                    price,
                    price,
                    price,
                    num(primary.get("volume")) or 0.0,
                )
            )

        def low_high(label: str) -> tuple[float | None, float | None]:
            value = ((info.get("keyStats") or {}).get(label) or {}).get("value", "")
            parts = [num(p) for p in str(value).split(" - ")]
            if len(parts) != 2 or None in parts:
                return None, None
            return min(parts), max(parts)  # "High/Low:" label, low-high values

        day_low, day_high = low_high("dayrange")
        wk_low, wk_high = low_high("fiftyTwoWeekHighLow")
        volume = num(primary.get("volume"))
        return Quote(
            symbol=symbol,
            price=price,
            previous_close=price - net if net is not None else None,
            currency="USD",
            market_time=_open_stamp(trade_day) if trade_day else None,
            sparkline=[b[4] for b in bars],
            history_ts=[int(_open_stamp(b[0]).timestamp()) for b in bars],
            history_open=[b[1] for b in bars],
            history_high=[b[2] for b in bars],
            history_low=[b[3] for b in bars],
            history_volume=[b[5] for b in bars],
            long_name=info.get("companyName"),
            exchange=info.get("exchange"),
            instrument_type=info.get("assetClass"),
            day_high=day_high,
            day_low=day_low,
            week52_high=wk_high,
            week52_low=wk_low,
            volume=int(volume) if volume is not None else None,
        )

    def get_splits(self, symbol: str, range_: str = "5y") -> list[dict]:
        """Stock splits for a symbol from Yahoo's chart events.

        Returns [{"date", "numerator", "denominator"}] oldest first;
        [] on any failure - splits are decoration on the diff, never a
        reason to fail it.
        """
        url = CHART_URL.format(symbol=symbol)
        try:
            resp = self._get(
                url,
                params={"range": range_, "interval": "1d", "events": "history"},
            )
            data = resp.json()
        except (requests.RequestException, ValueError):
            return []
        return self._parse_splits(data)

    @staticmethod
    def _parse_splits(data: dict) -> list[dict]:
        """Split events out of a Yahoo v8 chart payload.

        `events.split` is keyed by unix timestamp, each entry carrying
        numerator/denominator (a 4:1 split is 4/1) and the split date.
        """
        try:
            events = data["chart"]["result"][0].get("events") or {}
            raw_splits = events.get("split") or {}
        except (KeyError, IndexError, TypeError):
            return []
        splits = []
        for ts, entry in raw_splits.items():
            if not isinstance(entry, dict):
                continue
            try:
                when = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
                num = int(entry["numerator"])
                den = int(entry["denominator"])
            except (KeyError, TypeError, ValueError):
                continue
            if den:
                splits.append(
                    {
                        "date": when.isoformat(),
                        "numerator": num,
                        "denominator": den,
                    }
                )
        splits.sort(key=lambda s: s["date"])
        return splits

    def get_security(self, symbol: str, range_: str = "6mo") -> Quote | None:
        """Quote + price history for one symbol, with the bar interval
        picked automatically for the requested range (for chart screens)."""
        interval = RANGE_INTERVALS.get(range_, "1d")
        return self.get_quote(symbol, range_=range_, interval=interval)

    def get_quotes(
        self, symbols: list[str], range_: str = "1mo", interval: str = "1d",
        with_history: bool = False,
    ) -> dict[str, Quote]:
        """Quotes for many symbols. Symbols that fail are simply absent.

        Without history (the default) the symbols go out in ONE Yahoo
        v7 quote request per 25 symbols instead of one 0.25s-throttled
        chart request each - a 30-position portfolio used to cost ~7.5s+
        per load. Fresh per-symbol cache entries are still reused first,
        and anything the batch misses falls back to the sequential
        per-symbol path (chart, then Nasdaq for daily bars).

        with_history=True keeps the old behavior (one chart request per
        symbol, with sparkline/history) for callers that chart the
        series - quotes_view and markets_view. Batch quotes deliberately
        carry no history: the v7 endpoint returns price fields only.
        """
        seen: dict[str, None] = {}
        for symbol in symbols:
            seen.setdefault(symbol, None)
        ordered = list(seen)
        quotes: dict[str, Quote] = {}
        missing: list[str] = []
        for symbol in ordered:
            key = (symbol, range_, interval)
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < _FRESH_SECONDS:
                quotes[symbol] = cached[1]
                continue
            if not with_history:
                batch_cached = self._batch_cache.get(symbol)
                if batch_cached and time.monotonic() - batch_cached[0] < _FRESH_SECONDS:
                    quotes[symbol] = batch_cached[1]
                    continue
            missing.append(symbol)
        if not missing:
            return quotes

        if with_history:
            for symbol in missing:
                quote = self.get_quote(symbol, range_=range_, interval=interval)
                if quote is not None:
                    quotes[symbol] = quote
            return quotes

        try:
            batched = self._yahoo_batch_quotes(missing)
        except (requests.RequestException, ValueError):
            batched = {}
        for symbol, quote in batched.items():
            quotes[symbol] = quote
            self._batch_cache[symbol] = (time.monotonic(), quote)
        for symbol in missing:
            if symbol not in quotes:
                quote = self.get_quote(symbol, range_=range_, interval=interval)
                if quote is not None:
                    quotes[symbol] = quote
        return quotes

    def _yahoo_batch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Price fields for many symbols in one v7 quote request per chunk.

        Returns only the symbols Yahoo answered for. Raises on transport
        or JSON failure (callers fall back to the per-symbol path).
        """
        out: dict[str, Quote] = {}
        for i in range(0, len(symbols), _BATCH_CHUNK):
            chunk = symbols[i:i + _BATCH_CHUNK]
            resp = self._get(QUOTE_URL, params={"symbols": ",".join(chunk)})
            data = resp.json()
            results = (data.get("quoteResponse") or {}).get("result") or []
            for entry in results:
                quote = self._parse_v7_quote(entry)
                if quote is not None:
                    out[quote.symbol] = quote
        return out

    @staticmethod
    def _parse_v7_quote(entry: dict) -> Quote | None:
        """One v7 quote entry -> Quote with price fields, no history."""
        if not isinstance(entry, dict):
            return None
        try:
            symbol = entry["symbol"]
            price = float(entry["regularMarketPrice"])
        except (KeyError, TypeError, ValueError):
            return None

        def num(field):
            try:
                return float(entry[field])
            except (KeyError, TypeError, ValueError):
                return None

        volume = entry.get("regularMarketVolume")
        try:
            volume = int(volume) if volume is not None else None
        except (TypeError, ValueError):
            volume = None
        return Quote(
            symbol=symbol,
            price=price,
            previous_close=num("regularMarketPreviousClose"),
            currency=entry.get("currency"),
            long_name=entry.get("longName"),
            exchange=entry.get("fullExchangeName"),
            instrument_type=entry.get("quoteType"),
            day_high=num("regularMarketDayHigh"),
            day_low=num("regularMarketDayLow"),
            week52_high=num("fiftyTwoWeekHigh"),
            week52_low=num("fiftyTwoWeekLow"),
            volume=volume,
        )

    @staticmethod
    def _parse_chart(symbol: str, data: dict) -> Quote | None:
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
                raw_ts, raw_closes, raw_opens, raw_highs, raw_lows, raw_volumes,
                strict=False,  # ragged Yahoo arrays truncate; degrading beats raising
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

        def _num(key: str) -> float | None:
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
