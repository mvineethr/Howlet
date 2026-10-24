"""Paper trading: a fake-money account filled against real price bars.

The account lives in ~/.howlet/paper.json as an append-only list of
orders. Cash and positions are never stored - `ledger()` derives them by
replaying fills. `settle()` runs before every read and fills or expires
open orders from the price bars that began after each order was placed,
so orders fill correctly even while the app was closed. This module does
no network I/O except through the `prices` object passed in.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple, Optional

from .market import Quote
from .tickers import default_cache_dir

DEFAULT_START_CASH = 100_000.0
GTC_DAYS = 90
# Yahoo serves 5m bars for range=60d; range=3mo returns nothing (verified live 2026-10-24).
INTRADAY_LOOKBACK_DAYS = 59
MARKET_BAR_MAX_AGE = timedelta(minutes=30)
MIN_QTY = 0.0001
TRADABLE_TYPES = {"EQUITY", "ETF", "STOCKS"}  # STOCKS: Nasdaq fallback assetClass
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_EPS = 1e-9

# shortcut: per-process only; cross-process writes are rare (fills only) - upgrade to a file lock if it ever matters.
LOCK = threading.Lock()  # one read-settle-write at a time (Flask is threaded)


class PaperError(ValueError):
    """A rejected request (bad input, not enough cash or shares). Maps to HTTP 400."""


class Bar(NamedTuple):
    ts: int  # bar start, unix seconds UTC
    open: float
    high: float
    low: float


# ---- time ----

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _nth_sunday(year: int, month: int, n: int) -> datetime:
    d = datetime(year, month, 1)
    return d + timedelta(days=(6 - d.weekday()) % 7, weeks=n - 1)


def to_ny(dt: datetime) -> datetime:
    """Aware datetime -> naive New York wall time.

    shortcut: hand-coded US DST rule (2nd Sun Mar - 1st Sun Nov, since 2007) so
    Windows needs no tzdata package; switch to zoneinfo if the rule ever changes.
    """
    u = dt.astimezone(timezone.utc).replace(tzinfo=None)
    start = _nth_sunday(u.year, 3, 2) + timedelta(hours=7)  # 02:00 EST
    end = _nth_sunday(u.year, 11, 1) + timedelta(hours=6)   # 02:00 EDT
    return u - timedelta(hours=4 if start <= u < end else 5)


def ny_from_unix(ts: int) -> datetime:
    return to_ny(datetime.fromtimestamp(ts, timezone.utc))


def _close_utc(day) -> datetime:
    """16:00 New York on `day`, as an aware UTC datetime."""
    for hour in (20, 21):
        c = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
        if to_ny(c).hour == 16:
            return c
    raise AssertionError("unreachable")  # pragma: no cover


def in_session_hours(now: datetime) -> bool:
    ny = to_ny(now)
    return ny.weekday() < 5 and (9, 30) <= (ny.hour, ny.minute) < (16, 0)


def is_market_open(now: datetime, last_bar_ts: Optional[int]) -> bool:
    """Session hours AND a fresh bar - no fresh bar means a holiday."""
    return (
        in_session_hours(now)
        and last_bar_ts is not None
        and now - datetime.fromtimestamp(last_bar_ts, timezone.utc) < MARKET_BAR_MAX_AGE
    )


# ---- ledger ----

def ledger(state: dict) -> tuple[float, dict[str, list[float]], float]:
    """(cash, {symbol: [qty, cost]}, realized P/L) from replaying filled orders."""
    cash = float(state["account"]["start_cash"])
    pos: dict[str, list[float]] = {}
    realized = 0.0
    fills = sorted((o for o in state["orders"] if o["status"] == "filled"), key=lambda o: o["fill"]["ts"])
    for o in fills:
        qty, price = o["qty"], o["fill"]["price"]
        p = pos.setdefault(o["symbol"], [0.0, 0.0])
        if o["side"] == "buy":
            p[0] += qty
            p[1] += qty * price
            cash -= qty * price
        else:
            cost = p[1] * qty / p[0]
            p[0] -= qty
            p[1] -= cost
            cash += qty * price
            realized += qty * price - cost
            if p[0] < _EPS:
                del pos[o["symbol"]]
    return cash, pos, realized


def _reserved(state: dict) -> tuple[float, dict[str, float]]:
    """Cash held back by open buys and shares held back by open sells."""
    cash, shares = 0.0, {}
    for o in state["orders"]:
        if o["status"] != "open":
            continue
        if o["side"] == "buy":
            cash += o["qty"] * (o["limit"] or o["stop"] or o["ref_price"])
        else:
            shares[o["symbol"]] = shares.get(o["symbol"], 0.0) + o["qty"]
    return cash, shares


# ---- account ----

def new_state(start_cash, now: datetime) -> dict:
    try:
        start_cash = float(start_cash)
    except (TypeError, ValueError):
        raise PaperError("Starting cash must be a number.") from None
    if not (math.isfinite(start_cash) and start_cash > 0):
        raise PaperError("Starting cash must be a finite number more than zero.")
    return {
        "version": 1,
        "account": {"id": uuid.uuid4().hex, "created": _iso(now), "start_cash": start_cash},
        "orders": [],
        "archive": [],
    }


def reset(state: Optional[dict], start_cash, now: datetime) -> dict:
    fresh = new_state(start_cash, now)
    if state:
        fresh["archive"] = state.get("archive", []) + [
            {"account": state["account"], "orders": state["orders"], "reset_at": _iso(now)}
        ]
    return fresh


# ---- orders ----

def _level(value, required: bool, name: str, otype: str) -> Optional[float]:
    if not required:
        if value is not None:
            raise PaperError(f"A {name} price is only for {name} orders.")
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise PaperError(f"A {otype} order needs a {name} price.") from None
    if not v > 0:
        raise PaperError(f"The {name} price must be more than zero.")
    return v


def place_order(state: Optional[dict], prices, now: datetime, symbol: str, side: str, qty,
                type: str = "market", limit=None, stop=None, tif: str = "day") -> tuple[dict, dict]:
    sym = (symbol or "").strip().upper()
    if not _SYMBOL_RE.match(sym):
        raise PaperError(f"'{symbol}' isn't a US stock or ETF symbol.")
    if side not in ("buy", "sell"):
        raise PaperError("Side must be buy or sell.")
    if type not in ("market", "limit", "stop"):
        raise PaperError("Order type must be market, limit or stop.")
    if tif not in ("day", "gtc"):
        raise PaperError("Time in force must be day or gtc.")
    try:
        qty = round(float(qty), 4)
    except (TypeError, ValueError):
        raise PaperError("Quantity must be a number.") from None
    if not qty >= MIN_QTY:
        raise PaperError(f"Quantity must be at least {MIN_QTY}.")
    limit = _level(limit, type == "limit", "limit", type)
    stop = _level(stop, type == "stop", "stop", type)

    q = prices.quote(sym)
    if q is None:
        raise PaperError(f"No price for {sym} right now - try again in a minute.")
    # The Nasdaq fallback reports assetClass "STOCKS"; the symbol pattern already
    # excluded indexes (^), FX (=X) and futures (=F) there.
    if q.currency and q.currency != "USD":
        raise PaperError(f"{sym} trades in {q.currency}; paper trading covers US stocks and ETFs only.")
    if q.instrument_type and q.instrument_type not in TRADABLE_TYPES:
        raise PaperError(f"{sym} is a {q.instrument_type.lower()}; paper trading covers US stocks and ETFs only.")

    state = state or new_state(DEFAULT_START_CASH, now)
    cash, pos, _ = ledger(state)
    held_cash, held_shares = _reserved(state)
    if side == "buy":
        cost = qty * (limit or stop or q.price)
        available = cash - held_cash
        if cost > available + _EPS:
            raise PaperError(f"Not enough cash: this needs ${cost:,.2f} and ${max(available, 0):,.2f} is available.")
    else:
        sellable = pos.get(sym, [0.0])[0] - held_shares.get(sym, 0.0)
        if qty > sellable + _EPS:
            raise PaperError(f"You can sell at most {max(sellable, 0):g} {sym}.")

    order = {
        "id": uuid.uuid4().hex[:8], "ts": _iso(now), "symbol": sym, "side": side, "qty": qty,
        "type": type, "limit": limit, "stop": stop, "tif": tif, "status": "open", "fill": None,
        "reason": None, "ref_price": q.price, "closed_at": None,
    }
    if type == "market" and prices.market_open(now):
        order["status"] = "filled"
        order["fill"] = {"ts": _iso(now), "price": round(q.price, 4)}
    state["orders"].append(order)
    return state, order


def cancel_order(state: dict, order_id: str, now: datetime) -> dict:
    order = next((o for o in state["orders"] if o["id"] == order_id), None)
    if order is None:
        raise LookupError(f"No paper order '{order_id}'")
    if order["status"] != "open":
        raise PaperError(f"Only open orders can be cancelled; this one is {order['status']}.")
    order.update(status="cancelled", reason="Cancelled by you.", closed_at=_iso(now))
    return order


# ---- settling ----

def _trigger(order: dict, bar: Bar) -> Optional[float]:
    """Fill price if this bar triggers the order, else None. Gaps fill at the open."""
    otype, side = order["type"], order["side"]
    if otype == "market":
        return bar.open
    level = order["limit"] if otype == "limit" else order["stop"]
    if (otype, side) in (("limit", "buy"), ("stop", "sell")):
        return min(level, bar.open) if bar.low <= level else None
    return max(level, bar.open) if bar.high >= level else None


def _scan(order: dict, bars: list[Bar], now: datetime):
    """(event time, fill price or None, expiry reason or None) for the first event, else None."""
    placed = _utc(order["ts"])
    later = [b for b in bars if datetime.fromtimestamp(b.ts, timezone.utc) > placed]
    if order["tif"] == "gtc":
        deadline, why = placed + timedelta(days=GTC_DAYS), f"Good-'til-cancelled order expired after {GTC_DAYS} days."
    else:
        # Placed in a session: dies at that session's close, even if its last bar began before the order.
        # Placed outside hours: lives through the first session that has a bar after it.
        placed_day = to_ny(placed).date()
        if in_session_hours(placed) and any(ny_from_unix(b.ts).date() == placed_day for b in bars):
            day = placed_day
        elif later:
            day = ny_from_unix(later[0].ts).date()
        else:
            day = None
        deadline, why = (_close_utc(day), "Day order expired at the close.") if day else (None, None)
    for b in later:
        when = datetime.fromtimestamp(b.ts, timezone.utc)
        if deadline and when >= deadline:
            break
        price = _trigger(order, b)
        if price is not None:
            return when, price, None
    if deadline and now >= deadline:
        return deadline, None, why
    return None


def settle(state: dict, prices, now: datetime) -> dict:
    """Fill, expire or reject every open order from bars that began after it was placed."""
    events = []
    for o in state["orders"]:
        if o["status"] != "open":
            continue
        bars = prices.bars(o["symbol"], _utc(o["ts"]), now)
        if bars is None:
            continue  # prices unavailable: the order just stays open
        ev = _scan(o, bars, now)
        if ev:
            events.append((ev[0], o, ev[1], ev[2]))
    for when, o, price, why in sorted(events, key=lambda e: e[0]):
        if price is None:
            o.update(status="expired", reason=why, closed_at=_iso(when))
            continue
        cash, pos, _ = ledger(state)
        if o["side"] == "buy" and o["qty"] * price > cash + _EPS:
            o.update(status="rejected", closed_at=_iso(when),
                     reason=f"Not enough cash when it triggered at ${price:,.2f}.")
        elif o["side"] == "sell" and o["qty"] > pos.get(o["symbol"], [0.0])[0] + _EPS:
            o.update(status="rejected", closed_at=_iso(when), reason="Not enough shares when it triggered.")
        else:
            o.update(status="filled", fill={"ts": _iso(when), "price": round(price, 4)})
    return state


# ---- read models ----

def _closed_at(o: dict) -> str:
    return (o["fill"] or {}).get("ts") or o.get("closed_at") or o["ts"]


def summary(state: dict, prices, now: datetime) -> dict:
    cash, pos, realized = ledger(state)
    rows, unavailable, value, day = [], [], 0.0, 0.0
    for sym, (qty, cost) in sorted(pos.items()):
        q = prices.quote(sym)
        price = q.price if q else None
        if price is None:
            unavailable.append(sym)
            mv = None
        else:
            mv = qty * price
            if q.previous_close:
                day += qty * (price - q.previous_close)
        value += mv if mv is not None else cost  # missing price: count it at cost
        rows.append({
            "symbol": sym, "qty": round(qty, 4), "avg_cost": round(cost / qty, 4), "cost_basis": round(cost, 2),
            "price": price, "value": round(mv, 2) if mv is not None else None,
            "unrealized": round(mv - cost, 2) if mv is not None else None,
            "unrealized_pct": round((mv - cost) / cost * 100, 2) if mv is not None and cost else None,
        })
    start = state["account"]["start_cash"]
    equity = cash + value
    orders = state["orders"]
    return {
        "account": state["account"],
        "cash": round(cash, 2),
        "positions": rows,
        "positions_value": round(value, 2),
        "equity": round(equity, 2),
        "day_change": round(day, 2),
        "total_return_pct": round((equity - start) / start * 100, 2),
        "realized_pnl": round(realized, 2),
        "open_orders": sorted((o for o in orders if o["status"] == "open"), key=lambda o: o["ts"], reverse=True),
        "activity": sorted((o for o in orders if o["status"] != "open"), key=_closed_at, reverse=True)[:20],
        "market_open": prices.market_open(now),
        "prices_unavailable": unavailable,
    }


def history(state: dict, prices, now: datetime) -> dict:
    """Daily account value vs the same start cash held in SPY since creation."""
    empty = {"dates": [], "account": [], "spy": [], "account_return_pct": None, "spy_return_pct": None}
    since = to_ny(_utc(state["account"]["created"])).date()
    spy = prices.daily_closes("SPY", since, now)
    if not spy:
        return empty
    dates = sorted(spy)
    fills = [o for o in state["orders"] if o["status"] == "filled"]
    closes = {s: prices.daily_closes(s, since, now) or {} for s in {o["symbol"] for o in fills}}
    start = state["account"]["start_cash"]
    last: dict[str, float] = {}
    acct, spy_line = [], []
    for d in dates:
        for s, c in closes.items():
            if d in c:
                last[s] = c[d]
        upto = [o for o in fills if to_ny(_utc(o["fill"]["ts"])).date().isoformat() <= d]
        cash, pos, _ = ledger({"account": state["account"], "orders": upto})
        acct.append(round(cash + sum(qty * last.get(s, cost / qty) for s, (qty, cost) in pos.items()), 2))
        spy_line.append(round(start / spy[dates[0]] * spy[d], 2))
    return {
        "dates": dates, "account": acct, "spy": spy_line,
        "account_return_pct": round((acct[-1] - start) / start * 100, 2),
        "spy_return_pct": round((spy_line[-1] - start) / start * 100, 2),
    }


# ---- storage ----

class PaperStore:
    """paper.json under the Howlet cache dir. Atomic writes; a corrupt file is set aside, never overwritten."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.path = (Path(cache_dir) if cache_dir else default_cache_dir()) / "paper.json"

    def load(self) -> Optional[dict]:
        if not self.path.exists():
            return None
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if not (isinstance(state, dict) and isinstance(state.get("account"), dict)
                    and isinstance(state.get("orders"), list)):
                raise ValueError("not a paper account file")
            return state
        except ValueError:
            self.path.replace(self.path.with_name(f"paper.json.bad-{int(time.time())}"))
            return None

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"paper.json.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)


# ---- prices ----

class MarketPrices:
    """Adapts YahooMarketClient to the engine. Never raises: market data is the fragile tier."""

    def __init__(self, market):
        self.market = market

    def _get(self, symbol: str, range_: str, interval: str) -> Optional[Quote]:
        try:
            return self.market.get_quote(symbol, range_=range_, interval=interval)
        except Exception:
            return None

    def quote(self, symbol: str) -> Optional[Quote]:
        return self._get(symbol, "5d", "1d")

    def market_open(self, now: datetime) -> bool:
        q = self._get("SPY", "1d", "5m")
        return is_market_open(now, q.history_ts[-1] if q and q.history_ts else None)

    def bars(self, symbol: str, since: datetime, now: datetime) -> Optional[list[Bar]]:
        intraday = now - since < timedelta(days=INTRADAY_LOOKBACK_DAYS)
        q = self._get(symbol, "60d", "5m") if intraday else self._get(symbol, "6mo", "1d")
        if q is None or not q.history_ts:
            return None
        out = [Bar(*b) for b in zip(q.history_ts, q.history_open, q.history_high, q.history_low)]
        if not intraday:  # a daily bar covers the whole day, so start the day after placement
            day = to_ny(since).date()
            out = [b for b in out if ny_from_unix(b.ts).date() > day]
        return out

    def daily_closes(self, symbol: str, since: date, now: datetime) -> Optional[dict[str, float]]:
        age = (to_ny(now).date() - since).days
        range_ = next((r for r, lim in (("1mo", 28), ("3mo", 88), ("6mo", 180), ("1y", 360), ("2y", 720))
                       if age <= lim), "5y")
        q = self._get(symbol, range_, "1d")
        if q is None or not q.history_ts:
            return None
        out = {ny_from_unix(t).date().isoformat(): c for t, c in zip(q.history_ts, q.sparkline)}
        return {d: c for d, c in out.items() if d >= since.isoformat()}
