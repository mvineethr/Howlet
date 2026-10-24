"""Paper trading: a fake-money account filled against real price bars.

The account lives in ~/.howlet/paper.json as an append-only list of
orders. Cash and positions are never stored - `ledger()` derives them by
replaying fills. `settle()` runs before every read and fills or expires
open orders from the price bars that began after each order was placed,
so orders fill correctly even while the app was closed. This module does
no network I/O except through the `prices` object passed in.
"""

from __future__ import annotations

import math
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple, Optional

DEFAULT_START_CASH = 100_000.0
GTC_DAYS = 90
# Yahoo serves 5m bars for range=60d; range=3mo returns nothing (verified live 2026-10-24).
INTRADAY_LOOKBACK_DAYS = 59
MARKET_BAR_MAX_AGE = timedelta(minutes=30)
MIN_QTY = 0.0001
TRADABLE_TYPES = {"EQUITY", "ETF"}
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_EPS = 1e-9

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
    # instrument_type is None on the Nasdaq fallback; the symbol pattern already
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
        order["fill"] = {"ts": _iso(now), "price": q.price}
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
