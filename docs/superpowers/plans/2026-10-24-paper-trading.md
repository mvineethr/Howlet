# Paper Trading Account Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fake-money account inside Howlet. You place market, limit and stop orders against real (delayed) prices. Orders fill from real price bars even while the app was closed. Positions, P/L and the account's value can be compared with simply holding SPY.

**Architecture:**
- **Engine.** A new pure engine `src/howlet/paper.py` replays an append-only order ledger stored in `~/.howlet/paper.json`. `settle()` runs before every read. It walks the price bars that started after each open order was placed, then fills, expires or rejects the order. The engine never fetches anything itself; prices come in through a small provider object. `MarketPrices` adapts the existing `YahooMarketClient`.
- **Thin layers.** Views in `views.py` sit under one module lock, and Flask routes, three MCP tools and a `howlet paper` CLI group wrap those views.
- **React.** A Portfolio → Paper tab, an order-ticket dialog, a stock-page button, a Home block and a Settings reset.

**Tech Stack:**
- Backend: Python 3.10+ stdlib only (no new dependencies; the US DST rule is hand-coded), Flask, click/rich, FastMCP.
- Frontend: React 18 + TypeScript + Fluent UI v9, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-24-paper-trading-design.md`

## Global Constraints

- No required API key, ever. Prices come only from the existing keyless `YahooMarketClient` (Yahoo v8 chart, Nasdaq fallback).
- Keep every self-throttle: use `YahooMarketClient.get_quote`, never raw `requests`.
- Market data is the fragile tier. Missing prices leave orders `open` and are listed in `prices_unavailable`; a paper **read** never raises because of market data.
- No database: one JSON file, `paper.json`, under the Howlet cache dir (`tickers.default_cache_dir()`, i.e. `~/.howlet/`). Writes are atomic: temp file + `os.replace`.
- **No new runtime dependency.** Python: `zoneinfo` needs `tzdata` on Windows and that is not declared, so New York time uses the hand-coded US DST rule in `to_ny`.
- Exact values (from the spec, verified live 2026-10-24):
  - `DEFAULT_START_CASH = 100_000.0`, `GTC_DAYS = 90`, `MIN_QTY = 0.0001` (qty rounded to 4 decimals).
  - `INTRADAY_LOOKBACK_DAYS = 59`. Yahoo serves 5m bars for `range=60d`; `range=3mo` with 5m returns nothing.
  - Daily bars are timestamped at the session open (13:30 UTC in summer).
  - Market open = Mon–Fri 09:30–16:00 New York **and** the latest SPY 5m bar is under 30 minutes old.
  - Tradable `instrument_type` ∈ {`EQUITY`, `ETF`} with currency `USD`. Yahoo reports `INDEX`, `CRYPTOCURRENCY` and `CURRENCY` for the others.
- No shorting, no margin, no fees, no partial fills.
- MCP goes from 27 to **30** tools. There is **no** reset tool on MCP or the CLI (an agent must not wipe the account).
- UI colour only via CSS variables (`var(--up)`, `var(--down)`, `var(--dim)`, `var(--amber)`, `var(--cyan)`, …) defined from `frontend/src/theme/tokens.ts`. No hex literals in `frontend/src` outside `tokens.ts`.
- Test commands (CI runs them bare):
  - Python: `PYTHONPATH=src pytest tests/ -q` and `ruff check src/ tests/` from the repo root.
  - Frontend, in `frontend/`: `npx vitest run` (output must contain no "Unhandled" and no "act(" warnings), `npx tsc --noEmit`, `npm run build`.
  - Commit the rebuilt `src/howlet/static/app` with any frontend change.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push.

## File Structure

| File | Responsibility |
|---|---|
| `src/howlet/paper.py` (new) | Time helpers, fill rules, ledger derivation, place/cancel/settle/reset, summary, history, `PaperStore` (file I/O), `MarketPrices` (price adapter), `LOCK` |
| `src/howlet/views.py` | `paper_account_view`, `paper_order_view`, `paper_cancel_view`, `paper_history_view`, `paper_reset_view`; `Services.paper` |
| `src/howlet/dashboard.py` | 5 `/api/paper*` routes + `PaperError` → 400 |
| `src/howlet/mcp_server.py` | `paper_account`, `paper_order`, `paper_cancel` |
| `src/howlet/cli.py` | `howlet paper` group: show, `buy`, `sell`, `cancel` |
| `tests/test_paper.py` (new) | Engine, storage and adapter tests |
| `tests/test_paper_api.py` (new) | Routes, MCP tool list and CLI tests |
| `frontend/src/lib/api.ts` | Paper types + `deleteJson` + 5 wrappers |
| `frontend/src/lib/paper.ts` (new) | Pure ticket helpers: `explain`, `sharesFor`, `estimate`, `parseNum`, `usd`, `orderLabel` |
| `frontend/src/components/OrderTicket.tsx` (new) | Order dialog |
| `frontend/src/components/CompareChart.tsx` (new) | Two-line SVG chart (account vs SPY) |
| `frontend/src/pages/portfolio/PaperTab.tsx` (new) | The Paper tab |
| `frontend/src/pages/PortfolioPage.tsx`, `StockPage.tsx`, `lib/commands.ts`, `pages/HelpPage.tsx` | Wiring |
| `frontend/src/blocks/PaperBlock.tsx` (new), `blocks/registry.tsx`, `pages/SettingsPage.tsx` | Home block and reset |

---

### Task 1: Paper engine core (time, fills, ledger, orders, settle)

**Files:**
- Create: `src/howlet/paper.py`
- Test: `tests/test_paper.py`

**Interfaces:**
- Produces (used by Tasks 2–3):
  - `PaperError(ValueError)`, `Bar(NamedTuple: ts:int, open, high, low)`, `LOCK: threading.Lock`
  - `DEFAULT_START_CASH`, `GTC_DAYS`, `INTRADAY_LOOKBACK_DAYS`, `MIN_QTY`
  - `to_ny(dt) -> datetime` (naive NY wall time), `ny_from_unix(ts:int) -> datetime`, `in_session_hours(now) -> bool`, `is_market_open(now, last_bar_ts: Optional[int]) -> bool`
  - `ledger(state) -> tuple[float, dict[str, list[float]], float]` → (cash, `{symbol: [qty, cost]}`, realized)
  - `new_state(start_cash, now) -> dict`, `reset(state|None, start_cash, now) -> dict`
  - `place_order(state|None, prices, now, symbol, side, qty, type="market", limit=None, stop=None, tif="day") -> tuple[dict, dict]` → (state, order)
  - `cancel_order(state, order_id, now) -> dict` → order; raises `LookupError` for an unknown id
  - `settle(state, prices, now) -> dict`
  - `_iso(dt) -> str` and `_utc(s) -> datetime` (ISO-8601 UTC with seconds, e.g. `2026-10-23T14:00:00+00:00`)
- The **prices** object is duck-typed. Task 2 provides the real one:
  - `quote(symbol) -> Optional[Quote]`
  - `bars(symbol, since: datetime, now: datetime) -> Optional[list[Bar]]` (oldest first; may include bars before `since`, which the engine skips)
  - `market_open(now) -> bool`
  - `daily_closes(symbol, since: date, now: datetime) -> Optional[dict[str, float]]` (keys are ISO dates)
- Order dict keys: `id, ts, symbol, side, qty, type, limit, stop, tif, status, fill, reason, ref_price, closed_at`. Of these, `ref_price` is the quote price at placement and `closed_at` is the ISO time of cancel/expire/reject; both are additions to the spec's list.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paper.py`:

```python
"""Paper trading engine tests - synthetic bars, no network."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from howlet import paper
from howlet.market import Quote
from howlet.paper import Bar, PaperError

UTC = timezone.utc
# 2026-10-23 is a Friday; New York is on EDT (UTC-4) until 2026-11-01.
FRI = datetime(2026, 10, 23, 14, 0, tzinfo=UTC)  # 10:00 New York
SAT = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)


def at(day, h, m=0):
    return datetime(2026, 10, day, h, m, tzinfo=UTC)


def bar(when: datetime, o, h, lo):
    return Bar(int(when.timestamp()), o, h, lo)


def q(sym, price, kind="EQUITY", cur="USD", prev=None):
    return Quote(symbol=sym, price=price, previous_close=prev, currency=cur, instrument_type=kind)


class FakePrices:
    def __init__(self, quotes=None, bars=None, open_=False, closes=None):
        self.quotes, self._bars, self.open, self.closes = quotes or {}, bars or {}, open_, closes or {}

    def quote(self, s):
        return self.quotes.get(s)

    def bars(self, s, since, now):
        return self._bars.get(s)

    def market_open(self, now):
        return self.open

    def daily_closes(self, s, since, now):
        return self.closes.get(s)


def account(cash=10_000.0):
    return paper.new_state(cash, at(22, 14))


# ---- time ----

def test_to_ny_handles_dst():
    assert paper.to_ny(datetime(2026, 7, 1, 16, 0, tzinfo=UTC)).hour == 12   # EDT
    assert paper.to_ny(datetime(2026, 12, 1, 16, 0, tzinfo=UTC)).hour == 11  # EST
    assert paper.to_ny(datetime(2026, 3, 8, 6, 59, tzinfo=UTC)).hour == 1    # just before spring-forward
    assert paper.to_ny(datetime(2026, 3, 8, 7, 0, tzinfo=UTC)).hour == 3


def test_market_open_needs_session_hours_and_a_fresh_bar():
    fresh = int(at(23, 13, 55).timestamp())
    assert paper.is_market_open(FRI, fresh)
    assert not paper.is_market_open(FRI, int(at(22, 19, 55).timestamp()))  # holiday: no bar today
    assert not paper.is_market_open(FRI, None)
    assert not paper.is_market_open(SAT, int(SAT.timestamp()))  # weekend
    assert not paper.is_market_open(at(23, 20, 30), int(at(23, 20, 25).timestamp()))  # after 16:00


# ---- fill rules ----

@pytest.mark.parametrize("otype,side,level,b,expected", [
    ("limit", "buy", 100, (101, 102, 99.5), 100),
    ("limit", "buy", 100, (98, 99, 97), 98),         # gap down: better price
    ("limit", "buy", 100, (101, 102, 100.5), None),
    ("limit", "sell", 110, (109, 110.5, 108), 110),
    ("limit", "sell", 110, (112, 113, 111), 112),    # gap up: better price
    ("stop", "sell", 95, (96, 97, 94.5), 95),
    ("stop", "sell", 95, (93, 94, 92), 93),          # gap down: worse price
    ("stop", "sell", 95, (96, 97, 95.5), None),
    ("stop", "buy", 105, (104, 105.5, 103), 105),
    ("stop", "buy", 105, (107, 108, 106), 107),      # gap up: worse price
    ("market", "buy", None, (50, 51, 49), 50),
])
def test_trigger_table(otype, side, level, b, expected):
    order = {"type": otype, "side": side, "limit": level if otype == "limit" else None,
             "stop": level if otype == "stop" else None}
    assert paper._trigger(order, Bar(0, *b)) == expected


# ---- placing ----

def test_market_buy_while_open_fills_at_quote():
    prices = FakePrices({"AAPL": q("AAPL", 200.0)}, open_=True)
    state, order = paper.place_order(account(), prices, FRI, "aapl", "buy", 10)
    assert order["status"] == "filled" and order["fill"] == {"ts": paper._iso(FRI), "price": 200.0}
    assert order["symbol"] == "AAPL" and order["ref_price"] == 200.0
    assert paper.ledger(state)[0] == pytest.approx(8_000.0)


def test_market_buy_while_closed_fills_at_next_bar_open():
    prices = FakePrices({"AAPL": q("AAPL", 200.0)})
    state, order = paper.place_order(account(), prices, at(23, 21), "AAPL", "buy", 10)  # Fri 17:00 NY
    assert order["status"] == "open"
    prices._bars["AAPL"] = [bar(at(23, 19, 55), 199, 199, 199),     # before the order: ignored
                            bar(at(26, 13, 30), 203, 204, 202)]     # Monday's first bar
    paper.settle(state, prices, at(26, 14))
    assert order["status"] == "filled" and order["fill"]["price"] == 203
    assert order["fill"]["ts"] == paper._iso(at(26, 13, 30))


def test_place_order_without_account_creates_default_one():
    state, _ = paper.place_order(None, FakePrices({"AAPL": q("AAPL", 10.0)}), FRI, "AAPL", "buy", 1, "limit", limit=9)
    assert state["account"]["start_cash"] == paper.DEFAULT_START_CASH


def test_fractional_qty_rounds_to_four_decimals():
    _, order = paper.place_order(account(), FakePrices({"AAPL": q("AAPL", 10.0)}), FRI, "AAPL", "buy", 0.123456, "limit", limit=9)
    assert order["qty"] == 0.1235


@pytest.mark.parametrize("kwargs,quote,msg", [
    ({"symbol": "^GSPC"}, q("^GSPC", 7000, "INDEX"), "isn't a US stock or ETF symbol"),
    ({"symbol": "BTC-USD"}, q("BTC-USD", 80000, "CRYPTOCURRENCY"), "US stocks and ETFs only"),
    ({"symbol": "SHOP"}, q("SHOP", 100, "EQUITY", "CAD"), "US stocks and ETFs only"),
    ({"qty": 0.00001}, q("AAPL", 10), "at least 0.0001"),
    ({"qty": "lots"}, q("AAPL", 10), "must be a number"),
    ({"type": "limit"}, q("AAPL", 10), "needs a limit price"),
    ({"type": "market", "stop": 5}, q("AAPL", 10), "only for stop orders"),
    ({"side": "short"}, q("AAPL", 10), "buy or sell"),
    ({"tif": "ioc"}, q("AAPL", 10), "day or gtc"),
    ({"qty": 1000}, q("AAPL", 200), "Not enough cash"),
    ({"side": "sell"}, q("AAPL", 10), "You can sell at most 0"),
    ({}, None, "No price for AAPL"),
])
def test_placement_rejections(kwargs, quote, msg):
    args = {"symbol": "AAPL", "side": "buy", "qty": 1, "type": "market", "limit": None, "stop": None, "tif": "day"}
    args.update(kwargs)
    prices = FakePrices({args["symbol"]: quote} if quote else {})
    with pytest.raises(PaperError, match=msg):
        paper.place_order(account(), prices, FRI, args.pop("symbol"), args.pop("side"), args.pop("qty"), **args)


def test_open_buys_reserve_cash():
    prices = FakePrices({"AAPL": q("AAPL", 120.0)})
    state, _ = paper.place_order(account(), prices, FRI, "AAPL", "buy", 50, "limit", limit=100)  # reserves 5,000
    with pytest.raises(PaperError, match="Not enough cash"):
        paper.place_order(state, prices, FRI, "AAPL", "buy", 60, "limit", limit=100)


def test_open_sells_reserve_shares():
    prices = FakePrices({"AAPL": q("AAPL", 100.0)}, open_=True)
    state, _ = paper.place_order(account(), prices, FRI, "AAPL", "buy", 10)
    state, _ = paper.place_order(state, prices, FRI, "AAPL", "sell", 6, "limit", limit=150)
    with pytest.raises(PaperError, match="sell at most 4"):
        paper.place_order(state, prices, FRI, "AAPL", "sell", 5, "limit", limit=150)


# ---- settling ----

def test_rejected_at_fill_time_when_cash_ran_out():
    prices = FakePrices({"AAPL": q("AAPL", 100.0)})
    state, stop_buy = paper.place_order(account(), prices, FRI, "AAPL", "buy", 95, "stop", stop=100)  # reserves 9,500
    prices.open = True
    state, _ = paper.place_order(state, prices, FRI, "AAPL", "buy", 4)  # 400 of the 500 still free
    prices._bars["AAPL"] = [bar(at(23, 14, 5), 105, 106, 104)]          # gaps over the stop: 95 * 105 > 9,600
    paper.settle(state, prices, at(23, 15))
    assert stop_buy["status"] == "rejected" and "Not enough cash" in stop_buy["reason"]
    assert stop_buy["closed_at"] == paper._iso(at(23, 14, 5))
    assert paper.ledger(state)[0] == pytest.approx(9_600.0)


def test_day_order_expires_at_the_close():
    prices = FakePrices({"AAPL": q("AAPL", 120.0)}, bars={"AAPL": [bar(at(23, 14, 5), 120, 121, 119),
                                                                   bar(at(23, 19, 55), 120, 121, 119),
                                                                   bar(at(26, 13, 30), 90, 91, 89)]})
    state, order = paper.place_order(account(), prices, FRI, "AAPL", "buy", 1, "limit", limit=100)
    paper.settle(state, prices, at(26, 14))
    assert order["status"] == "expired" and order["reason"] == "Day order expired at the close."
    assert order["closed_at"] == paper._iso(at(23, 20))  # 16:00 New York; Monday's bar never counted


def test_day_order_placed_after_hours_waits_for_the_next_session():
    prices = FakePrices({"AAPL": q("AAPL", 120.0)}, bars={"AAPL": []})
    state, order = paper.place_order(account(), prices, at(23, 22), "AAPL", "buy", 1, "limit", limit=100)
    paper.settle(state, prices, SAT)
    assert order["status"] == "open"


def test_gtc_expires_after_90_days():
    prices = FakePrices({"AAPL": q("AAPL", 120.0)}, bars={"AAPL": [bar(at(23, 14, 5), 120, 121, 119)]})
    state, order = paper.place_order(account(), prices, FRI, "AAPL", "buy", 1, "limit", limit=100, tif="gtc")
    paper.settle(state, prices, FRI + timedelta(days=91))
    assert order["status"] == "expired" and "90 days" in order["reason"]


def test_unavailable_prices_leave_orders_open():
    prices = FakePrices({"AAPL": q("AAPL", 120.0)})  # bars() returns None
    state, order = paper.place_order(account(), prices, FRI, "AAPL", "buy", 1, "limit", limit=100)
    paper.settle(state, prices, SAT)
    assert order["status"] == "open"


# ---- ledger, cancel, reset ----

def test_ledger_average_cost_and_realized_pnl():
    state = account()
    for side, qty, price in [("buy", 10, 100), ("buy", 10, 120), ("sell", 5, 130)]:
        state["orders"].append({"id": f"{side}{qty}{price}", "ts": paper._iso(FRI), "symbol": "AAPL", "side": side,
                                "qty": qty, "type": "market", "limit": None, "stop": None, "tif": "day",
                                "status": "filled", "fill": {"ts": paper._iso(FRI), "price": price},
                                "reason": None, "ref_price": price, "closed_at": None})
    cash, pos, realized = paper.ledger(state)
    assert pos["AAPL"] == pytest.approx([15, 1650])
    assert realized == pytest.approx(100)
    assert cash == pytest.approx(10_000 - 1_000 - 1_200 + 650)


def test_cancel_open_order_only():
    state, order = paper.place_order(account(), FakePrices({"AAPL": q("AAPL", 10.0)}), FRI, "AAPL", "buy", 1, "limit", limit=9)
    assert paper.cancel_order(state, order["id"], SAT)["status"] == "cancelled"
    assert order["reason"] == "Cancelled by you." and order["closed_at"] == paper._iso(SAT)
    with pytest.raises(PaperError, match="Only open orders"):
        paper.cancel_order(state, order["id"], SAT)
    with pytest.raises(LookupError):
        paper.cancel_order(state, "nope", SAT)


def test_reset_archives_the_old_account():
    state, _ = paper.place_order(account(), FakePrices({"AAPL": q("AAPL", 10.0)}), FRI, "AAPL", "buy", 1, "limit", limit=9)
    fresh = paper.reset(state, 50_000, SAT)
    assert fresh["account"]["start_cash"] == 50_000 and fresh["orders"] == []
    assert fresh["archive"][0]["orders"] == state["orders"] and fresh["archive"][0]["reset_at"] == paper._iso(SAT)
    with pytest.raises(PaperError):
        paper.reset(None, 0, SAT)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `PYTHONPATH=src pytest tests/test_paper.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'howlet.paper'`.

- [ ] **Step 3: Write the engine**

Create `src/howlet/paper.py`:

```python
"""Paper trading: a fake-money account filled against real price bars.

The account lives in ~/.howlet/paper.json as an append-only list of
orders. Cash and positions are never stored - `ledger()` derives them by
replaying fills. `settle()` runs before every read and fills or expires
open orders from the price bars that began after each order was placed,
so orders fill correctly even while the app was closed. This module does
no network I/O except through the `prices` object passed in.
"""

from __future__ import annotations

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
    if not start_cash > 0:
        raise PaperError("Starting cash must be more than zero.")
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
    elif later:  # a day order lives through the first session that has a bar after it
        deadline, why = _close_utc(ny_from_unix(later[0].ts).date()), "Day order expired at the close."
    else:
        deadline, why = None, None
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
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `PYTHONPATH=src pytest tests/test_paper.py -q`, then `ruff check src/ tests/`
Expected: all tests pass and ruff is clean. If a parametrized message test fails on wording, fix the **code's** message so it contains the tested phrase. Don't weaken the test.

- [ ] **Step 5: Commit**

```bash
git add src/howlet/paper.py tests/test_paper.py
git commit -m "Paper trading engine: orders, fill rules, settle, ledger

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Summary, history, storage and the price adapter

**Files:**
- Modify: `src/howlet/paper.py` (append)
- Test: `tests/test_paper.py` (append)

**Interfaces:**
- Consumes everything from Task 1.
- Produces:
  - `summary(state, prices, now) -> dict` with keys `account, cash, positions, positions_value, equity, day_change, total_return_pct, realized_pnl, open_orders, activity, market_open, prices_unavailable`. Each position is `{symbol, qty, avg_cost, cost_basis, price, value, unrealized, unrealized_pct}`.
  - `history(state, prices, now) -> {"dates", "account", "spy", "account_return_pct", "spy_return_pct"}`
  - `PaperStore(cache_dir=None)` with `.path`, `.load() -> Optional[dict]` and `.save(state)`
  - `MarketPrices(market)`, implementing the prices interface over `YahooMarketClient.get_quote(symbol, range_=..., interval=...)`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_paper.py`)

```python
# ---- summary & history ----

def _filled(sym, side, qty, price, when):
    return {"id": f"{sym}{side}{when.isoformat()}", "ts": paper._iso(when), "symbol": sym, "side": side, "qty": qty,
            "type": "market", "limit": None, "stop": None, "tif": "day", "status": "filled",
            "fill": {"ts": paper._iso(when), "price": price}, "reason": None, "ref_price": price, "closed_at": None}


def test_summary_values_positions_and_flags_missing_prices():
    state = account()
    state["orders"] += [_filled("AAPL", "buy", 10, 100, at(22, 15)), _filled("MSFT", "buy", 5, 200, at(22, 16))]
    state["orders"].append({**_filled("AAPL", "buy", 1, 90, at(23, 14)), "id": "o1", "status": "open", "fill": None})
    prices = FakePrices({"AAPL": q("AAPL", 110, prev=105)})  # MSFT price missing
    s = paper.summary(state, prices, FRI)
    aapl, msft = s["positions"]
    assert aapl == {"symbol": "AAPL", "qty": 10, "avg_cost": 100, "cost_basis": 1000, "price": 110,
                    "value": 1100, "unrealized": 100, "unrealized_pct": 10}
    assert msft["price"] is None and msft["value"] is None and s["prices_unavailable"] == ["MSFT"]
    assert s["cash"] == 8_000 and s["equity"] == 8_000 + 1_100 + 1_000  # missing price counts at cost
    assert s["day_change"] == 50 and s["total_return_pct"] == 1.0
    assert [o["id"] for o in s["open_orders"]] == ["o1"] and len(s["activity"]) == 2
    assert s["activity"][0]["symbol"] == "MSFT"  # newest first
    assert s["market_open"] is False


def test_history_tracks_account_and_spy():
    state = paper.new_state(10_000, at(21, 14))
    state["orders"].append(_filled("AAPL", "buy", 10, 100, at(22, 15)))
    prices = FakePrices(closes={"SPY": {"2026-10-21": 500, "2026-10-22": 510, "2026-10-23": 520},
                                "AAPL": {"2026-10-21": 95, "2026-10-22": 104, "2026-10-23": 110}})
    h = paper.history(state, prices, FRI)
    assert h["dates"] == ["2026-10-21", "2026-10-22", "2026-10-23"]
    assert h["account"] == [10_000, 10_040, 10_100]
    assert h["spy"] == [10_000, 10_200, 10_400]
    assert h["account_return_pct"] == 1.0 and h["spy_return_pct"] == 4.0


def test_history_without_spy_data_is_empty():
    h = paper.history(account(), FakePrices(), FRI)
    assert h == {"dates": [], "account": [], "spy": [], "account_return_pct": None, "spy_return_pct": None}


# ---- storage ----

def test_store_round_trip_and_missing_file(tmp_path):
    store = paper.PaperStore(tmp_path)
    assert store.load() is None
    store.save(account())
    assert store.load()["account"]["start_cash"] == 10_000
    assert not (tmp_path / "paper.json.tmp").exists()


def test_store_sets_corrupt_file_aside(tmp_path):
    (tmp_path / "paper.json").write_text("{not json", encoding="utf-8")
    store = paper.PaperStore(tmp_path)
    assert store.load() is None
    assert not (tmp_path / "paper.json").exists()
    assert len(list(tmp_path.glob("paper.json.bad-*"))) == 1


# ---- price adapter ----

def test_market_prices_adapter_ranges_and_degradation():
    from unittest.mock import MagicMock
    market = MagicMock()
    market.get_quote.return_value = Quote(symbol="AAPL", price=1.0, sparkline=[1, 2, 3],
                                          history_ts=[int(at(22, 13, 30).timestamp()), int(at(23, 13, 30).timestamp()),
                                                      int(at(24, 13, 30).timestamp())],
                                          history_open=[1, 2, 3], history_high=[1, 2, 3], history_low=[1, 2, 3])
    mp = paper.MarketPrices(market)
    assert mp.quote("AAPL").price == 1.0
    market.get_quote.assert_called_with("AAPL", range_="5d", interval="1d")
    assert len(mp.bars("AAPL", at(22, 14), FRI)) == 3
    market.get_quote.assert_called_with("AAPL", range_="60d", interval="5m")
    old = at(22, 14) - timedelta(days=70)
    mp.bars("AAPL", old, FRI)
    market.get_quote.assert_called_with("AAPL", range_="6mo", interval="1d")
    closes = mp.daily_closes("AAPL", at(23, 0).date(), FRI)
    assert closes == {"2026-10-23": 2, "2026-10-24": 3}
    market.get_quote.side_effect = RuntimeError("boom")
    assert mp.quote("AAPL") is None and mp.bars("AAPL", FRI, FRI) is None and mp.market_open(FRI) is False


def test_market_prices_daily_bars_skip_the_placement_day():
    from unittest.mock import MagicMock
    market = MagicMock()
    ts = [int(at(d, 13, 30).timestamp()) for d in (22, 23)]
    market.get_quote.return_value = Quote(symbol="X", price=1.0, sparkline=[1, 2], history_ts=ts,
                                          history_open=[1, 2], history_high=[1, 2], history_low=[1, 2])
    since = at(22, 15)  # mid-session on the 22nd, but older than the intraday window
    bars = paper.MarketPrices(market).bars("X", since, since + timedelta(days=70))
    assert [b.ts for b in bars] == [ts[1]]
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `PYTHONPATH=src pytest tests/test_paper.py -q`
Expected: the new tests fail with `AttributeError: module 'howlet.paper' has no attribute 'summary'`, and similar for `history`, `PaperStore` and `MarketPrices`.

- [ ] **Step 3: Implement** (append to `src/howlet/paper.py`; add `json`, `os`, `time`, `from datetime import date`, `from pathlib import Path`, `from .market import Quote` and `from .tickers import default_cache_dir` to the imports)

```python
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
        tmp = self.path.with_name("paper.json.tmp")
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
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `PYTHONPATH=src pytest tests/test_paper.py -q && ruff check src/ tests/`
Expected: all tests pass and ruff is clean.

- [ ] **Step 5: Commit**

```bash
git add src/howlet/paper.py tests/test_paper.py
git commit -m "Paper trading: summary, SPY history, file store, price adapter

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Views, routes, MCP tools and CLI

**Files:**
- Modify: `src/howlet/views.py` (imports; `Services.__init__`; five view functions at the end)
- Modify: `src/howlet/dashboard.py` (inside `create_app`, before `return app`)
- Modify: `src/howlet/mcp_server.py` (before `return server`)
- Modify: `src/howlet/cli.py` (new command group)
- Modify: `CLAUDE.md`, `README.md` (MCP count 27 → 30; module map row; tool list)
- Test: `tests/test_paper_api.py` (new)

**Interfaces:**
- Consumes from `paper`: `LOCK, PaperStore, MarketPrices, PaperError, DEFAULT_START_CASH, settle, place_order, cancel_order, summary, history, reset`.
- Produces:
  - `views.paper_account_view(svc, now=None)`, `views.paper_order_view(svc, symbol, side, qty, type="market", limit=None, stop=None, tif="day", now=None)`, `views.paper_cancel_view(svc, order_id, now=None)`, `views.paper_history_view(svc, now=None)`, `views.paper_reset_view(svc, start_cash=DEFAULT_START_CASH, now=None)`
  - `svc` only needs `.paper` (a `PaperStore`) and `.market`.
  - With no account, `paper_account_view` returns `{"account": None, "market_open": bool}` and `paper_history_view` returns the empty history shape.
  - HTTP:
    - `GET /api/paper`
    - `GET /api/paper/history`
    - `POST /api/paper/orders` with body `{symbol, side, qty, type, limit, stop, tif}` → **201** + order
    - `DELETE /api/paper/orders/<id>` → order
    - `POST /api/paper/reset` with body `{start_cash}` → account summary
    - `PaperError` → **400** `{error}`; an unknown order id → 404.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paper_api.py`:

```python
"""Paper trading: Flask routes, MCP tool list, CLI (prices mocked, no network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from howlet import cli
from howlet.dashboard import create_app
from howlet.market import Quote
from howlet.paper import PaperStore


def fake_market():
    """AAPL quotes at 200 and is an equity; SPY has no intraday bars, so the market reads as closed."""
    m = MagicMock()

    def get_quote(symbol, range_="5d", interval="1d"):
        if symbol == "SPY":
            return Quote(symbol="SPY", price=500.0, currency="USD", instrument_type="ETF")
        if symbol == "AAPL":
            return Quote(symbol="AAPL", price=200.0, previous_close=198.0, currency="USD", instrument_type="EQUITY")
        if symbol == "BTC-USD":
            return Quote(symbol="BTC-USD", price=80_000.0, currency="USD", instrument_type="CRYPTOCURRENCY")
        return None

    m.get_quote.side_effect = get_quote
    return m


@pytest.fixture
def svc(tmp_path):
    return SimpleNamespace(paper=PaperStore(tmp_path), market=fake_market())


@pytest.fixture
def api(svc):
    app = create_app("Test Suite test@example.com", services=svc)
    app.config["TESTING"] = True
    return app.test_client()


def test_no_account_yet(api):
    assert api.get("/api/paper").get_json() == {"account": None, "market_open": False}
    assert api.get("/api/paper/history").get_json()["dates"] == []


def test_place_list_and_cancel_an_order(api):
    r = api.post("/api/paper/orders", json={"symbol": "aapl", "side": "buy", "qty": 2, "type": "limit",
                                            "limit": 150, "stop": None, "tif": "gtc"})
    assert r.status_code == 201
    order = r.get_json()
    assert order["status"] == "open" and order["symbol"] == "AAPL" and order["tif"] == "gtc"
    acct = api.get("/api/paper").get_json()
    assert acct["account"]["start_cash"] == 100_000 and acct["open_orders"][0]["id"] == order["id"]
    assert api.delete(f"/api/paper/orders/{order['id']}").get_json()["status"] == "cancelled"
    assert api.delete(f"/api/paper/orders/{order['id']}").status_code == 400
    assert api.delete("/api/paper/orders/nope").status_code == 404


def test_bad_orders_are_400(api):
    r = api.post("/api/paper/orders", json={"symbol": "BTC-USD", "side": "buy", "qty": 1})
    assert r.status_code == 400 and "US stocks and ETFs only" in r.get_json()["error"]
    assert api.post("/api/paper/orders", json={"symbol": "AAPL", "side": "buy", "qty": 0}).status_code == 400


def test_reset_starts_fresh_with_chosen_cash(api):
    api.post("/api/paper/orders", json={"symbol": "AAPL", "side": "buy", "qty": 1, "type": "limit", "limit": 100})
    d = api.post("/api/paper/reset", json={"start_cash": 25_000}).get_json()
    assert d["account"]["start_cash"] == 25_000 and d["open_orders"] == [] and d["cash"] == 25_000
    assert api.post("/api/paper/reset", json={"start_cash": -5}).status_code == 400


def test_mcp_has_30_tools_and_no_reset():
    pytest.importorskip("mcp")
    from howlet.mcp_server import build_server

    names = {t.name for t in asyncio.run(build_server("Test Suite test@example.com").list_tools())}
    assert len(names) == 30
    assert {"paper_account", "paper_order", "paper_cancel"} <= names
    assert not any("reset" in n for n in names)


def test_cli_buy_and_show(svc, monkeypatch):
    monkeypatch.setattr(cli, "_paper_svc", lambda: svc)
    runner = CliRunner()
    r = runner.invoke(cli.main, ["paper", "buy", "AAPL", "2", "--limit", "150"])
    assert r.exit_code == 0, r.output
    assert "OPEN" in r.output and "AAPL" in r.output
    r = runner.invoke(cli.main, ["paper"])
    assert r.exit_code == 0 and "100,000.00" in r.output
    r = runner.invoke(cli.main, ["paper", "buy", "BTC-USD", "1"])
    assert r.exit_code != 0 and "US stocks and ETFs only" in r.output
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `PYTHONPATH=src pytest tests/test_paper_api.py -q`
Expected: failures. The routes return 404, there are 27 MCP tools, and `cli` has no `_paper_svc`.

- [ ] **Step 3: Implement the views** (`src/howlet/views.py`)

Add imports near the others:

```python
from datetime import datetime, timezone

from . import paper
```

In `Services.__init__`, after `self.crypto = CryptoClient()`:

```python
        self.paper = paper.PaperStore(cache_dir=cache_dir)
```

Append at the end of the file:

```python
# ---- paper trading (fake money; see paper.py) ----

def _now() -> datetime:
    return datetime.now(timezone.utc)


def paper_account_view(svc, now: Optional[datetime] = None) -> dict:
    """Settle open orders, then cash, positions at live prices, orders and recent activity."""
    now, prices = now or _now(), paper.MarketPrices(svc.market)
    with paper.LOCK:
        state = svc.paper.load()
        if state is None:
            return {"account": None, "market_open": prices.market_open(now)}
        paper.settle(state, prices, now)
        svc.paper.save(state)
        return paper.summary(state, prices, now)


def paper_order_view(svc, symbol: str, side: str, qty, type: str = "market", limit=None, stop=None,
                     tif: str = "day", now: Optional[datetime] = None) -> dict:
    """Place a paper order (creates a default account on first use). Raises paper.PaperError."""
    now, prices = now or _now(), paper.MarketPrices(svc.market)
    with paper.LOCK:
        state = svc.paper.load()
        if state is not None:
            paper.settle(state, prices, now)
        state, order = paper.place_order(state, prices, now, symbol, side, qty, type=type,
                                         limit=limit, stop=stop, tif=tif)
        svc.paper.save(state)
        return order


def paper_cancel_view(svc, order_id: str, now: Optional[datetime] = None) -> dict:
    now, prices = now or _now(), paper.MarketPrices(svc.market)
    with paper.LOCK:
        state = svc.paper.load()
        if state is None:
            raise LookupError("No paper account yet")
        paper.settle(state, prices, now)  # an order that already filled can't be cancelled
        order = paper.cancel_order(state, order_id, now)
        svc.paper.save(state)
        return order


def paper_history_view(svc, now: Optional[datetime] = None) -> dict:
    now, prices = now or _now(), paper.MarketPrices(svc.market)
    with paper.LOCK:
        state = svc.paper.load()
        if state is None:
            return {"dates": [], "account": [], "spy": [], "account_return_pct": None, "spy_return_pct": None}
        paper.settle(state, prices, now)
        svc.paper.save(state)
        return paper.history(state, prices, now)


def paper_reset_view(svc, start_cash=paper.DEFAULT_START_CASH, now: Optional[datetime] = None) -> dict:
    """Archive the current paper account and start a fresh one. Deliberately not an MCP tool."""
    now, prices = now or _now(), paper.MarketPrices(svc.market)
    with paper.LOCK:
        state = paper.reset(svc.paper.load(), start_cash, now)
        svc.paper.save(state)
        return paper.summary(state, prices, now)
```

- [ ] **Step 4: Implement the routes** (`src/howlet/dashboard.py`)

Add `from .paper import DEFAULT_START_CASH, PaperError` to the imports. Inside `create_app`, after the `LookupError` handler:

```python
    @app.errorhandler(PaperError)
    def bad_request(exc):
        return jsonify({"error": str(exc)}), 400
```

Before `return app`:

```python
    @app.get("/api/paper")
    def paper_account():
        return jsonify(views.paper_account_view(svc))

    @app.get("/api/paper/history")
    def paper_history():
        return jsonify(views.paper_history_view(svc))

    @app.post("/api/paper/orders")
    def paper_order():
        b = request.get_json(force=True, silent=True) or {}
        order = views.paper_order_view(
            svc, b.get("symbol", ""), b.get("side", ""), b.get("qty"), type=b.get("type", "market"),
            limit=b.get("limit"), stop=b.get("stop"), tif=b.get("tif", "day"),
        )
        return jsonify(order), 201

    @app.delete("/api/paper/orders/<order_id>")
    def paper_cancel(order_id: str):
        return jsonify(views.paper_cancel_view(svc, order_id))

    @app.post("/api/paper/reset")
    def paper_reset():
        b = request.get_json(force=True, silent=True) or {}
        return jsonify(views.paper_reset_view(svc, b.get("start_cash", DEFAULT_START_CASH)))
```

- [ ] **Step 5: Implement the MCP tools** (`src/howlet/mcp_server.py`, before `return server`)

```python
    # Paper trading (fake money). There is deliberately no reset tool: an
    # agent must never be able to wipe the user's practice account.
    @server.tool()
    def paper_account() -> dict:
        """The user's PAPER (fake money) trading account: cash, positions at
        live (delayed) prices, open orders, recent fills, and return vs simply
        holding SPY. Open orders are settled against real price bars first.
        Practice only - no real money moves."""
        d = views.paper_account_view(svc)
        if d.get("account"):
            h = views.paper_history_view(svc)
            d["vs_spy"] = {"account_return_pct": h["account_return_pct"], "spy_return_pct": h["spy_return_pct"]}
        return d

    @server.tool()
    def paper_order(symbol: str, side: str, qty: float, type: str = "market",
                    limit: Optional[float] = None, stop: Optional[float] = None, tif: str = "day") -> dict:
        """Place a PAPER (fake money) order for a US stock or ETF. side: buy|sell.
        type: market|limit|stop (limit needs `limit`, stop needs `stop`).
        tif: day|gtc. Market orders fill now while the market is open,
        otherwise at the next session's open. No shorting or margin."""
        return views.paper_order_view(svc, symbol, side, qty, type=type, limit=limit, stop=stop, tif=tif)

    @server.tool()
    def paper_cancel(order_id: str) -> dict:
        """Cancel an open PAPER order by its id (from paper_account)."""
        return views.paper_cancel_view(svc, order_id)
```

- [ ] **Step 6: Implement the CLI** (`src/howlet/cli.py`)

Add imports: `from types import SimpleNamespace`, `from . import views`, `from .market import YahooMarketClient` and `from .paper import PaperError, PaperStore`. Before adding any of these, check which `cli.py` already imports, and don't duplicate one. Append:

```python
def _paper_svc():
    # Paper trading needs no SEC access, so no EDGAR_USER_AGENT either.
    return SimpleNamespace(paper=PaperStore(), market=YahooMarketClient())


@main.group(invoke_without_command=True)
@click.pass_context
def paper(ctx):
    """Paper trading with fake money: show the account (subcommands place/cancel orders)."""
    if ctx.invoked_subcommand is not None:
        return
    d = views.paper_account_view(_paper_svc())
    if not d.get("account"):
        console.print("No paper account yet - place an order (a $100,000 account starts automatically).")
        return
    console.print(
        f"Account ${d['equity']:,.2f}  cash ${d['cash']:,.2f}  return {d['total_return_pct']:+.2f}%  "
        f"market {'OPEN' if d['market_open'] else 'closed'}  (start ${d['account']['start_cash']:,.2f})"
    )
    table = Table(title="Positions")
    for col in ("Symbol", "Qty", "Avg cost", "Price", "Value", "P/L"):
        table.add_column(col)
    for p in d["positions"]:
        table.add_row(p["symbol"], f"{p['qty']:g}", f"{p['avg_cost']:,.2f}",
                      "-" if p["price"] is None else f"{p['price']:,.2f}",
                      "-" if p["value"] is None else f"{p['value']:,.2f}",
                      "-" if p["unrealized"] is None else f"{p['unrealized']:+,.2f}")
    console.print(table)
    for o in d["open_orders"]:
        level = o["limit"] or o["stop"]
        console.print(f"open {o['id']}: {o['side']} {o['qty']:g} {o['symbol']} {o['type']}"
                      + (f" @ {level:,.2f}" if level else "") + f" ({o['tif']})")


def _paper_place(side: str, symbol: str, qty: float, limit, stop, gtc: bool) -> None:
    if limit is not None and stop is not None:
        raise click.UsageError("Use --limit or --stop, not both.")
    otype = "limit" if limit is not None else "stop" if stop is not None else "market"
    try:
        o = views.paper_order_view(_paper_svc(), symbol, side, qty, type=otype, limit=limit, stop=stop,
                                   tif="gtc" if gtc else "day")
    except PaperError as exc:
        raise click.ClickException(str(exc)) from None
    fill = f" @ ${o['fill']['price']:,.2f}" if o["fill"] else ""
    console.print(f"{o['status'].upper()}: {side} {o['qty']:g} {o['symbol']} {o['type']}{fill}  (id {o['id']})")


@paper.command("buy")
@click.argument("symbol")
@click.argument("qty", type=float)
@click.option("--limit", type=float, default=None, help="Limit price: fill only at this price or better")
@click.option("--stop", type=float, default=None, help="Stop price: becomes a market order once crossed")
@click.option("--gtc", is_flag=True, help="Good 'til cancelled (90 days) instead of today only")
def paper_buy(symbol, qty, limit, stop, gtc):
    """Paper-buy QTY shares of SYMBOL (fake money)."""
    _paper_place("buy", symbol, qty, limit, stop, gtc)


@paper.command("sell")
@click.argument("symbol")
@click.argument("qty", type=float)
@click.option("--limit", type=float, default=None, help="Limit price: fill only at this price or better")
@click.option("--stop", type=float, default=None, help="Stop price: becomes a market order once crossed")
@click.option("--gtc", is_flag=True, help="Good 'til cancelled (90 days) instead of today only")
def paper_sell(symbol, qty, limit, stop, gtc):
    """Paper-sell QTY shares of SYMBOL (fake money)."""
    _paper_place("sell", symbol, qty, limit, stop, gtc)


@paper.command("cancel")
@click.argument("order_id")
def paper_cancel_cmd(order_id):
    """Cancel an open paper order."""
    try:
        o = views.paper_cancel_view(_paper_svc(), order_id)
    except (PaperError, LookupError) as exc:
        raise click.ClickException(str(exc)) from None
    console.print(f"Cancelled {o['id']}: {o['side']} {o['qty']:g} {o['symbol']}")
```

- [ ] **Step 7: Update the docs**
  - `CLAUDE.md`: change "27 tools" to "30 tools" in the "What this is" paragraph, the module-map `mcp_server.py` row and "**MCP: 27 tools.**". Add a module-map row after `risk.py`:
    `| `paper.py` | Paper trading (fake money): append-only order ledger in `~/.howlet/paper.json`, fills market/limit/stop orders from real Yahoo bars on every read (`settle`), SPY benchmark |`
  - `README.md`: change "Exposed tools (27)" to "Exposed tools (30)" and append `paper_account`, `paper_order`, `paper_cancel` to that tool list.

- [ ] **Step 8: Run all the tests and watch them pass**

Run: `PYTHONPATH=src pytest tests/ -q && ruff check src/ tests/`
Expected: everything passes, including the existing `tests/test_dashboard.py` (its `FakeServices` has no `.paper`, which is fine because no existing route touches it). Ruff is clean.

- [ ] **Step 9: Commit**

```bash
git add src/howlet/views.py src/howlet/dashboard.py src/howlet/mcp_server.py src/howlet/cli.py tests/test_paper_api.py CLAUDE.md README.md
git commit -m "Paper trading: views, /api/paper routes, 3 MCP tools, howlet paper CLI

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Frontend API, ticket helpers and the order ticket

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/paper.ts`, `frontend/src/lib/paper.test.ts`
- Create: `frontend/src/components/OrderTicket.tsx`, `frontend/src/components/OrderTicket.test.tsx`

**Interfaces:**
- Consumes: the HTTP API from Task 3.
- Produces:
  - `api.ts` types: `PaperOrder`, `PaperPosition`, `PaperAccount`, `PaperHistory`, `PaperOrderRequest`.
  - `api.ts` wrappers: `api.paperAccount()`, `api.paperHistory()`, `api.paperOrder(req)`, `api.paperCancel(id)`, `api.paperReset(startCash)`; plus the `deleteJson<T>(path)` helper.
  - `lib/paper.ts`: `Side`, `OrderType`, `explain(side, type, level)`, `sharesFor(dollars, price)`, `estimate(type, qty, price, level)`, `parseNum(s)`, `usd(n)`, `orderLabel(o)`.
  - `components/OrderTicket.tsx`: default export `OrderTicket({ open, onClose, symbol?, onPlaced? })`.

- [ ] **Step 1: Add the API types and wrappers** (`frontend/src/lib/api.ts`)

Replace the bodies of `getJson` and `postJson` with one shared parser, and add `deleteJson`:

```ts
async function parse<T>(res: Response): Promise<T> {
  let body: unknown = null;
  try { body = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    const msg = body && typeof body === "object" && "error" in body ? String((body as { error: unknown }).error) : `HTTP ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return body as T;
}

export const getJson = <T,>(path: string): Promise<T> => fetch(path).then((r) => parse<T>(r));
export const postJson = <T,>(path: string, body: unknown): Promise<T> =>
  fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => parse<T>(r));
export const deleteJson = <T,>(path: string): Promise<T> => fetch(path, { method: "DELETE" }).then((r) => parse<T>(r));
```

Add these types next to the other exported types:

```ts
export type PaperOrder = {
  id: string; ts: string; symbol: string; side: "buy" | "sell"; qty: number; type: "market" | "limit" | "stop";
  limit: number | null; stop: number | null; tif: "day" | "gtc";
  status: "open" | "filled" | "cancelled" | "rejected" | "expired";
  fill: { ts: string; price: number } | null; reason: string | null; ref_price: number; closed_at: string | null;
};
export type PaperPosition = { symbol: string; qty: number; avg_cost: number; cost_basis: number; price: number | null;
  value: number | null; unrealized: number | null; unrealized_pct: number | null };
export type PaperAccountData = {
  account: { id: string; created: string; start_cash: number }; cash: number; positions: PaperPosition[];
  positions_value: number; equity: number; day_change: number; total_return_pct: number; realized_pnl: number;
  open_orders: PaperOrder[]; activity: PaperOrder[]; market_open: boolean; prices_unavailable: string[];
};
export type PaperAccount = PaperAccountData | { account: null; market_open: boolean };
export type PaperHistory = { dates: string[]; account: number[]; spy: number[];
  account_return_pct: number | null; spy_return_pct: number | null };
export type PaperOrderRequest = { symbol: string; side: "buy" | "sell"; qty: number; type: "market" | "limit" | "stop";
  limit: number | null; stop: number | null; tif: "day" | "gtc" };
```

Add to the `api` object:

```ts
  paperAccount: () => getJson<PaperAccount>("/api/paper"),
  paperHistory: () => getJson<PaperHistory>("/api/paper/history"),
  paperOrder: (o: PaperOrderRequest) => postJson<PaperOrder>("/api/paper/orders", o),
  paperCancel: (id: string) => deleteJson<PaperOrder>(`/api/paper/orders/${q(id)}`),
  paperReset: (startCash: number) => postJson<PaperAccount>("/api/paper/reset", { start_cash: startCash }),
```

- [ ] **Step 2: Write the failing helper tests** (`frontend/src/lib/paper.test.ts`)

```ts
import { estimate, explain, orderLabel, parseNum, sharesFor, usd } from "./paper";
import type { PaperOrder } from "./api";

test("explains every order type in plain English", () => {
  expect(explain("buy", "limit", 180)).toBe("Buy limit: fills only if the price drops to $180.00 or lower.");
  expect(explain("sell", "limit", 210.5)).toBe("Sell limit: fills only if the price rises to $210.50 or higher.");
  expect(explain("sell", "stop", 150)).toContain("falls to $150.00 or lower");
  expect(explain("buy", "stop", null)).toContain("rises to your price or higher");
  expect(explain("buy", "market", null)).toContain("next session's opening price");
});

test("dollar amounts floor to 4 decimals so the cost never exceeds the amount", () => {
  expect(sharesFor(1000, 300)).toBe(3.3333);
  expect(sharesFor(1000, 300) * 300).toBeLessThanOrEqual(1000);
});

test("estimate uses the quote for market orders and the level otherwise", () => {
  expect(estimate("market", 2, 100, null)).toBe(200);
  expect(estimate("limit", 2, 100, 90)).toBe(180);
  expect(estimate("limit", 2, 100, null)).toBeNull();
  expect(estimate("market", 0, 100, null)).toBeNull();
});

test("parseNum, usd and orderLabel", () => {
  expect(parseNum(" 12.5 ")).toBe(12.5);
  expect(parseNum("")).toBeNull();
  expect(parseNum("abc")).toBeNull();
  expect(usd(-1234.5)).toBe("-$1,234.50");
  expect(usd(null)).toBe("—");
  const o = { side: "buy", qty: 10, symbol: "AAPL", type: "limit", limit: 180, stop: null, tif: "day" } as PaperOrder;
  expect(orderLabel(o)).toBe("Buy 10 AAPL · limit $180.00 · day");
});
```

- [ ] **Step 3: Run it and watch it fail**

Run (in `frontend/`): `npx vitest run src/lib/paper.test.ts`
Expected: FAIL. Vite can't resolve the import `./paper`.

- [ ] **Step 4: Write the helpers** (`frontend/src/lib/paper.ts`)

```ts
import { fmtNum } from "./fmt";
import type { PaperOrder } from "./api";

export type Side = "buy" | "sell";
export type OrderType = "market" | "limit" | "stop";

export const usd = (n: number | null | undefined): string =>
  n == null || Number.isNaN(n) ? "—" : `${n < 0 ? "-" : ""}$${fmtNum(Math.abs(n))}`;

export function explain(side: Side, type: OrderType, level: number | null): string {
  const p = level != null && level > 0 ? usd(level) : "your price";
  if (type === "market") return `Market ${side}: fills right away while the market is open, otherwise at the next session's opening price.`;
  if (type === "limit") return side === "buy"
    ? `Buy limit: fills only if the price drops to ${p} or lower.`
    : `Sell limit: fills only if the price rises to ${p} or higher.`;
  return side === "buy"
    ? `Buy stop: if the price rises to ${p} or higher, buys at the next available price — used to catch a breakout.`
    : `Sell stop: if the price falls to ${p} or lower, sells at the next available price — used to cap a loss.`;
}

/** Shares for a dollar amount, floored to 4 decimals so the cost never exceeds it. */
export const sharesFor = (dollars: number, price: number): number => Math.floor((dollars / price) * 1e4) / 1e4;

export function estimate(type: OrderType, qty: number, price: number | null, level: number | null): number | null {
  const p = type === "market" ? price : level;
  return p != null && p > 0 && qty > 0 ? qty * p : null;
}

export function parseNum(s: string): number | null {
  const t = s.trim();
  const n = Number(t);
  return t && Number.isFinite(n) ? n : null;
}

export function orderLabel(o: PaperOrder): string {
  const level = o.type === "limit" ? o.limit : o.type === "stop" ? o.stop : null;
  return `${o.side === "buy" ? "Buy" : "Sell"} ${o.qty} ${o.symbol} · ${o.type}${level != null ? ` ${usd(level)}` : ""} · ${o.tif}`;
}
```

- [ ] **Step 5: Write the failing ticket tests** (`frontend/src/components/OrderTicket.test.tsx`)

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import OrderTicket from "./OrderTicket";

const ACCOUNT = { account: { id: "a", created: "2026-10-23T14:00:00+00:00", start_cash: 10000 }, cash: 10000, positions: [],
  positions_value: 0, equity: 10000, day_change: 0, total_return_pct: 0, realized_pnl: 0, open_orders: [], activity: [],
  market_open: false, prices_unavailable: [] };

function mockFetch(order: { status: number; body: unknown }) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (init?.method === "POST") return new Response(JSON.stringify(order.body), { status: order.status });
    if (url.startsWith("/api/quotes")) return new Response(JSON.stringify([{ symbol: "AAPL", price: 200 }]));
    return new Response(JSON.stringify(ACCOUNT));
  });
}

const renderTicket = (props: Partial<Parameters<typeof OrderTicket>[0]> = {}) =>
  render(<FluentProvider theme={webDarkTheme}><OrderTicket open symbol="AAPL" onClose={() => {}} {...props} /></FluentProvider>);

afterEach(() => vi.restoreAllMocks());

test("shows a live estimate and the cash left", async () => {
  mockFetch({ status: 201, body: {} });
  renderTicket();
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "5" } });
  await waitFor(() => expect(screen.getByText(/Estimated cost \$1,000\.00/)).toBeTruthy());
  expect(screen.getByText(/Cash after: \$9,000\.00/)).toBeTruthy();
});

test("switching to limit shows the explainer and posts the right body", async () => {
  const f = mockFetch({ status: 201, body: { id: "x", status: "open" } });
  const onPlaced = vi.fn();
  renderTicket({ onPlaced });
  fireEvent.click(screen.getByLabelText("Limit"));
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Limit price"), { target: { value: "180" } });
  expect(screen.getByText("Buy limit: fills only if the price drops to $180.00 or lower.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Place paper order" }));
  await waitFor(() => expect(onPlaced).toHaveBeenCalled());
  const post = f.mock.calls.find(([, init]) => init?.method === "POST")!;
  expect(JSON.parse(String(post[1]!.body))).toEqual({ symbol: "AAPL", side: "buy", qty: 2, type: "limit", limit: 180, stop: null, tif: "day" });
});

test("dollar mode converts to whole-cent-safe shares", async () => {
  const f = mockFetch({ status: 201, body: { id: "x" } });
  renderTicket();
  fireEvent.click(screen.getByLabelText("Dollars"));
  await waitFor(() => expect(f).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("Amount in dollars"), { target: { value: "1000" } });
  await waitFor(() => expect(screen.getByText(/= 5 shares/)).toBeTruthy());
});

test("server errors show inline and keep the dialog open", async () => {
  mockFetch({ status: 400, body: { error: "Not enough cash: this needs $2,000.00 and $1.00 is available." } });
  const onClose = vi.fn();
  renderTicket({ onClose });
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "Place paper order" }));
  await waitFor(() => expect(screen.getByText(/Not enough cash/)).toBeTruthy());
  expect(onClose).not.toHaveBeenCalled();
});
```

- [ ] **Step 6: Run them and watch them fail**

Run: `npx vitest run src/components/OrderTicket.test.tsx`
Expected: FAIL. The import `./OrderTicket` doesn't resolve.

- [ ] **Step 7: Write the ticket** (`frontend/src/components/OrderTicket.tsx`)

```tsx
import { useEffect, useState } from "react";
import {
  Button, Caption1, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle,
  Field, Input, Radio, RadioGroup, Text,
} from "@fluentui/react-components";
import { api, type PaperOrder } from "../lib/api";
import { useApi } from "../lib/useApi";
import { estimate, explain, parseNum, sharesFor, usd, type OrderType, type Side } from "../lib/paper";

type Props = { open: boolean; onClose: () => void; symbol?: string; onPlaced?: (o: PaperOrder) => void };

export default function OrderTicket({ open, onClose, symbol = "", onPlaced }: Props) {
  const [sym, setSym] = useState(symbol);
  const [quoteSym, setQuoteSym] = useState(symbol.trim().toUpperCase());
  const [side, setSide] = useState<Side>("buy");
  const [type, setType] = useState<OrderType>("market");
  const [mode, setMode] = useState<"shares" | "dollars">("shares");
  const [amount, setAmount] = useState("");
  const [levelText, setLevelText] = useState("");
  const [tif, setTif] = useState<"day" | "gtc">("day");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSym(symbol); setQuoteSym(symbol.trim().toUpperCase()); setAmount(""); setLevelText(""); setErr("");
  }, [open, symbol]);
  useEffect(() => { // wait for typing to pause before fetching a quote
    const t = setTimeout(() => setQuoteSym(sym.trim().toUpperCase()), 400);
    return () => clearTimeout(t);
  }, [sym]);

  const quote = useApi(open && quoteSym ? `ticket-quote:${quoteSym}` : null, () => api.quotes([quoteSym]));
  const acct = useApi(open ? "ticket-account" : null, () => api.paperAccount());
  const price = quote.data?.[0]?.price ?? null;
  const level = type === "market" ? null : parseNum(levelText);
  const amt = parseNum(amount);
  const unit = type === "market" ? price : level;
  const qty = amt == null || amt <= 0 ? null : mode === "shares" ? amt : unit ? sharesFor(amt, unit) : null;
  const est = qty == null ? null : estimate(type, qty, price, level);
  const a = acct.data?.account ? acct.data : null;
  const held = a?.positions.find((p) => p.symbol === quoteSym)?.qty ?? 0;
  const after = !a || est == null ? null
    : side === "buy" ? `Cash after: ${usd(a.cash - est)}` : `${quoteSym} shares after: ${+(held - (qty ?? 0)).toFixed(4)}`;

  const submit = async () => {
    if (!sym.trim() || qty == null) { setErr("Enter a symbol and a quantity."); return; }
    if (type !== "market" && (level == null || level <= 0)) { setErr(`Enter a ${type} price.`); return; }
    setBusy(true); setErr("");
    try {
      const o = await api.paperOrder({ symbol: sym.trim().toUpperCase(), side, qty, type,
        limit: type === "limit" ? level : null, stop: type === "stop" ? level : null, tif });
      onPlaced?.(o);
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(_, d) => { if (!d.open) onClose(); }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Paper order</DialogTitle>
          <DialogContent style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Caption1 style={{ color: "var(--dim)" }}>Fake money — practice only. Prices are delayed up to 15 minutes.</Caption1>
            <Field label="Symbol">
              <Input value={sym} onChange={(_, d) => setSym(d.value)} />
            </Field>
            {price != null && <Text size={200}>Last price {usd(price)}</Text>}
            <RadioGroup layout="horizontal" value={side} onChange={(_, d) => setSide(d.value as Side)} aria-label="Side">
              <Radio value="buy" label="Buy" /><Radio value="sell" label="Sell" />
            </RadioGroup>
            <RadioGroup layout="horizontal" value={type} onChange={(_, d) => setType(d.value as OrderType)} aria-label="Order type">
              <Radio value="market" label="Market" /><Radio value="limit" label="Limit" /><Radio value="stop" label="Stop" />
            </RadioGroup>
            {type !== "market" && (
              <Field label={type === "limit" ? "Limit price" : "Stop price"}>
                <Input inputMode="decimal" value={levelText} onChange={(_, d) => setLevelText(d.value)} />
              </Field>
            )}
            <RadioGroup layout="horizontal" value={mode} onChange={(_, d) => setMode(d.value as "shares" | "dollars")} aria-label="Size by">
              <Radio value="shares" label="Shares" /><Radio value="dollars" label="Dollars" />
            </RadioGroup>
            <Field label={mode === "shares" ? "Quantity" : "Amount in dollars"}>
              <Input inputMode="decimal" value={amount} onChange={(_, d) => setAmount(d.value)} />
            </Field>
            {mode === "dollars" && qty != null && <Text size={200}>= {qty} shares</Text>}
            <RadioGroup layout="horizontal" value={tif} onChange={(_, d) => setTif(d.value as "day" | "gtc")} aria-label="Time in force">
              <Radio value="day" label="Today only" /><Radio value="gtc" label="Good 'til cancelled (90 days)" />
            </RadioGroup>
            <Text size={200}>{explain(side, type, level)}</Text>
            {est != null && <Text weight="semibold">Estimated {side === "buy" ? "cost" : "proceeds"} {usd(est)}</Text>}
            {after && <Text size={200} style={{ color: "var(--dim)" }}>{after}</Text>}
            {err && <Text role="alert" style={{ color: "var(--down)" }}>{err}</Text>}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={onClose}>Cancel</Button>
            <Button appearance="primary" disabled={busy} onClick={submit}>Place paper order</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
```

- [ ] **Step 8: Run all frontend checks and watch them pass**

Run (in `frontend/`): `npx vitest run && npx tsc --noEmit`
Expected: all green, no "act(" or "Unhandled" output. If a Fluent label query fails, adjust the **component's** label to match the test. The labels are the contract.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/paper.ts frontend/src/lib/paper.test.ts frontend/src/components/OrderTicket.tsx frontend/src/components/OrderTicket.test.tsx
git commit -m "Frontend: paper API wrappers, ticket helpers, order ticket dialog

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Paper tab, comparison chart and wiring

**Files:**
- Create: `frontend/src/components/CompareChart.tsx`
- Create: `frontend/src/pages/portfolio/PaperTab.tsx`, `frontend/src/pages/portfolio/PaperTab.test.tsx`
- Modify: `frontend/src/pages/PortfolioPage.tsx`, `frontend/src/pages/StockPage.tsx`, `frontend/src/lib/commands.ts`, `frontend/src/lib/commands.test.ts`, `frontend/src/pages/HelpPage.tsx`

**Interfaces:**
- Consumes `api.paper*`, `PaperAccountData`, `PaperHistory`, `PaperOrder` and `PaperPosition` (Task 4); `usd`, `orderLabel` and `OrderTicket` (Task 4); and the existing `DataTable`/`Column`, `Block`, `Ticker`, `useApi`, `fmtNum`, `signed`, `tone`.
- Produces:
  - `CompareChart({ dates, a, b, aLabel, bLabel })`
  - `PaperTab` (default export)
  - The `PortfolioTab` union gains `"paper"`
  - The `PAPER` command routes to `{ kind: "page", page: "portfolio", params: ["paper"] }`

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/portfolio/PaperTab.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import PaperTab from "./PaperTab";

const order = (over: object) => ({ id: "o1", ts: "2026-10-23T14:00:00+00:00", symbol: "AAPL", side: "buy", qty: 2, type: "limit",
  limit: 180, stop: null, tif: "day", status: "open", fill: null, reason: null, ref_price: 200, closed_at: null, ...over });
const ACCOUNT = {
  account: { id: "a", created: "2026-10-21T14:00:00+00:00", start_cash: 10000 }, cash: 8000,
  positions: [{ symbol: "AAPL", qty: 10, avg_cost: 200, cost_basis: 2000, price: 210, value: 2100, unrealized: 100, unrealized_pct: 5 }],
  positions_value: 2100, equity: 10100, day_change: 25, total_return_pct: 1, realized_pnl: 0,
  open_orders: [order({})],
  activity: [order({ id: "o2", qty: 3, status: "rejected", reason: "Not enough cash when it triggered at $105.00.", closed_at: "2026-10-23T15:00:00+00:00" })],
  market_open: false, prices_unavailable: [],
};
const HISTORY = { dates: ["2026-10-21", "2026-10-22"], account: [10000, 10100], spy: [10000, 10200], account_return_pct: 1, spy_return_pct: 2 };

function mockFetch(account: unknown) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (init?.method === "DELETE") return new Response(JSON.stringify(order({ status: "cancelled" })));
    if (init?.method === "POST") return new Response(JSON.stringify(ACCOUNT));
    if (url === "/api/paper/history") return new Response(JSON.stringify(HISTORY));
    return new Response(JSON.stringify(account));
  });
}
const renderTab = () => render(<FluentProvider theme={webDarkTheme}><PaperTab /></FluentProvider>);
afterEach(() => vi.restoreAllMocks());

test("renders summary, vs-SPY, positions, open orders and activity reasons", async () => {
  mockFetch(ACCOUNT);
  renderTab();
  await waitFor(() => expect(screen.getByText("$10,100.00")).toBeTruthy());
  expect(screen.getByText("+1.0% vs S&P 500 +2.0%")).toBeTruthy();
  expect(screen.getByText("Buy 2 AAPL · limit $180.00 · day")).toBeTruthy();
  expect(screen.getByText("Not enough cash when it triggered at $105.00.")).toBeTruthy();
  expect(screen.getByRole("img", { name: "Account value vs S&P 500" })).toBeTruthy();
});

test("cancel calls DELETE and reloads", async () => {
  const f = mockFetch(ACCOUNT);
  renderTab();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel order o1" }));
  await waitFor(() => expect(f.mock.calls.some(([u, i]) => String(u) === "/api/paper/orders/o1" && i?.method === "DELETE")).toBe(true));
});

test("no account: start form posts the chosen cash", async () => {
  const f = mockFetch({ account: null, market_open: false });
  renderTab();
  fireEvent.change(await screen.findByLabelText("Starting cash"), { target: { value: "25000" } });
  fireEvent.click(screen.getByRole("button", { name: "Start paper account" }));
  await waitFor(() => {
    const post = f.mock.calls.find(([u, i]) => String(u) === "/api/paper/reset" && i?.method === "POST");
    expect(post && JSON.parse(String(post[1]!.body))).toEqual({ start_cash: 25000 });
  });
});
```

Append to `frontend/src/lib/commands.test.ts`:

```ts
test("PAPER opens the Paper tab", () => {
  expect(parseCommand("paper", [])).toEqual({ kind: "go", route: { kind: "page", page: "portfolio", params: ["paper"] } });
});
```

(Keep the file's existing import of `parseCommand`; add one only if it is missing.)

- [ ] **Step 2: Run them and watch them fail**

Run: `npx vitest run src/pages/portfolio/PaperTab.test.tsx src/lib/commands.test.ts`
Expected: FAIL. `./PaperTab` doesn't resolve, and the PAPER assertion fails because `paper` is parsed as a stock route.

- [ ] **Step 3: Write `CompareChart`** (`frontend/src/components/CompareChart.tsx`)

```tsx
type Props = { dates: string[]; a: number[]; b: number[]; aLabel: string; bLabel: string };

/** Two lines on one scale (e.g. account value vs SPY). Colours come from CSS tokens. */
export default function CompareChart({ dates, a, b, aLabel, bLabel }: Props) {
  const W = 600, H = 160, P = 4;
  if (dates.length < 2) return <span style={{ color: "var(--dim)" }}>The chart starts after the account's second trading day.</span>;
  const all = [...a, ...b];
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1;
  const pts = (v: number[]) => v.map((y, i) =>
    `${(P + (i / (v.length - 1)) * (W - 2 * P)).toFixed(1)},${(H - P - ((y - lo) / span) * (H - 2 * P)).toFixed(1)}`).join(" ");
  return (
    <div>
      <svg role="img" aria-label={`${aLabel} vs ${bLabel}`} viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none">
        <polyline points={pts(b)} fill="none" stroke="var(--cyan)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        <polyline points={pts(a)} fill="none" stroke="var(--amber)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
      </svg>
      <div style={{ display: "flex", gap: 16, fontSize: "0.85em", color: "var(--dim)" }}>
        <span><span style={{ color: "var(--amber)" }}>━</span> {aLabel}</span>
        <span><span style={{ color: "var(--cyan)" }}>━</span> {bLabel}</span>
        <span style={{ marginLeft: "auto" }}>{dates[0]} → {dates[dates.length - 1]}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write `PaperTab`** (`frontend/src/pages/portfolio/PaperTab.tsx`)

```tsx
import { useState } from "react";
import { Badge, Button, Caption1, Field, Input, Text } from "@fluentui/react-components";
import { api, type PaperOrder, type PaperPosition } from "../../lib/api";
import { useApi } from "../../lib/useApi";
import { fmtNum, signed, tone } from "../../lib/fmt";
import { orderLabel, parseNum, usd } from "../../lib/paper";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";
import Ticker from "../../components/Ticker";
import CompareChart from "../../components/CompareChart";
import OrderTicket from "../../components/OrderTicket";

const num = (s: string, color?: string) => <span className="num" style={color ? { color } : undefined}>{s}</span>;
const pct = (n: number | null | undefined) => (n == null ? "—" : `${signed(n, 1)}%`);
const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "—");

export default function PaperTab() {
  const acct = useApi("paper", () => api.paperAccount(), 60_000);
  const hist = useApi("paper-history", () => api.paperHistory(), 10 * 60_000);
  const [ticket, setTicket] = useState(false);
  const [cashText, setCashText] = useState("100000");
  const [msg, setMsg] = useState("");
  const reload = () => { acct.reload(); hist.reload(); };

  const start = async () => {
    const n = parseNum(cashText);
    if (n == null || n <= 0) { setMsg("Starting cash must be more than zero."); return; }
    try { await api.paperReset(n); setMsg(""); reload(); } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  };
  const cancel = async (id: string) => {
    try { await api.paperCancel(id); setMsg(""); reload(); } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  };

  const d = acct.data;
  const h = hist.data;
  const header = (
    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      <Button appearance="primary" onClick={() => setTicket(true)}>New order</Button>
      {d && <Badge appearance="outline" color={d.market_open ? "success" : "subtle"}>{d.market_open ? "Market open" : "Market closed"}</Badge>}
      <Caption1 style={{ color: "var(--dim)" }}>Fake money — practice only. Prices are delayed up to 15 minutes.</Caption1>
      {msg && <Text role="alert" style={{ color: "var(--down)" }}>{msg}</Text>}
      <OrderTicket open={ticket} onClose={() => setTicket(false)} onPlaced={reload} />
    </div>
  );

  if (d && !d.account) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {header}
        <Block fixed title="Start a paper account">
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
            <Field label="Starting cash"><Input inputMode="decimal" value={cashText} onChange={(_, v) => setCashText(v.value)} /></Field>
            <Button appearance="primary" onClick={start}>Start paper account</Button>
          </div>
          <Caption1 style={{ color: "var(--dim)" }}>Or just place an order — a $100,000 account starts automatically.</Caption1>
        </Block>
      </div>
    );
  }

  const posCols: Column<PaperPosition>[] = [
    { key: "s", label: "Symbol", render: (p) => <Ticker symbol={p.symbol} /> },
    { key: "q", label: "Qty", align: "right", render: (p) => num(String(p.qty)) },
    { key: "c", label: "Avg cost", align: "right", render: (p) => num(usd(p.avg_cost)) },
    { key: "p", label: "Price", align: "right", render: (p) => num(usd(p.price)) },
    { key: "v", label: "Value", align: "right", render: (p) => num(usd(p.value)) },
    { key: "u", label: "P/L", align: "right", render: (p) => num(`${usd(p.unrealized)} (${pct(p.unrealized_pct)})`, tone(p.unrealized)) },
  ];
  const openCols: Column<PaperOrder>[] = [
    { key: "o", label: "Order", render: (o) => orderLabel(o) },
    { key: "t", label: "Placed", render: (o) => when(o.ts) },
    { key: "x", label: "", render: (o) => <Button size="small" appearance="subtle" aria-label={`Cancel order ${o.id}`} onClick={() => cancel(o.id)}>Cancel</Button> },
  ];
  const actCols: Column<PaperOrder>[] = [
    { key: "t", label: "When", render: (o) => when(o.fill?.ts ?? o.closed_at) },
    { key: "o", label: "Order", render: (o) => orderLabel(o) },
    { key: "s", label: "Result", render: (o) => (o.status === "filled" ? `Filled at ${usd(o.fill?.price)}` : o.status) },
    { key: "r", label: "Why", render: (o) => o.reason ?? "" },
  ];
  const stat = (label: string, value: string, color?: string) => (
    <div style={{ display: "flex", flexDirection: "column", minWidth: 140 }}>
      <Caption1 style={{ color: "var(--dim)" }}>{label}</Caption1>
      <Text size={500} weight="semibold">{num(value, color)}</Text>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {header}
      <Block fixed title="Account" loading={acct.loading} error={acct.error} fetchedAt={acct.fetchedAt} refreshMs={60_000}>
        {d?.account && (
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            {stat("Account value", usd(d.equity))}
            {stat("Cash", usd(d.cash))}
            {stat("Today", usd(d.day_change), tone(d.day_change))}
            {stat("Total return", pct(d.total_return_pct), tone(d.total_return_pct))}
            {h && h.account_return_pct != null && (
              <Text style={{ alignSelf: "flex-end" }}>{`${pct(h.account_return_pct)} vs S&P 500 ${pct(h.spy_return_pct)}`}</Text>
            )}
            {d.prices_unavailable.length > 0 && <Caption1 style={{ color: "var(--dim)" }}>Prices unavailable: {d.prices_unavailable.join(", ")} (counted at cost)</Caption1>}
          </div>
        )}
      </Block>
      <Block fixed title="Account vs S&P 500" loading={hist.loading} error={hist.error} fetchedAt={hist.fetchedAt}>
        {h && <CompareChart dates={h.dates} a={h.account} b={h.spy} aLabel="Account value" bLabel="S&P 500" />}
      </Block>
      <Block fixed title="Positions">
        {d?.account && <DataTable columns={posCols} rows={d.positions} rowKey={(p) => p.symbol} empty="No positions yet — place an order." />}
      </Block>
      <Block fixed title="Open orders">
        {d?.account && <DataTable columns={openCols} rows={d.open_orders} rowKey={(o) => o.id} empty="No open orders." />}
      </Block>
      <Block fixed title="Activity">
        {d?.account && <DataTable columns={actCols} rows={d.activity} rowKey={(o) => o.id} empty="Nothing yet." />}
      </Block>
      <Caption1 style={{ color: "var(--dim)" }}>Realised P/L so far: {d?.account ? usd(d.realized_pnl) : "—"} · started with {d?.account ? usd(d.account.start_cash) : "—"} · {fmtNum(d?.account ? d.positions.length : 0, 0)} positions</Caption1>
    </div>
  );
}
```

- [ ] **Step 5: Wire it in**

`frontend/src/pages/PortfolioPage.tsx`:
- Add `import PaperTab from "./portfolio/PaperTab";`.
- Change the type to `export type PortfolioTab = "watchlists" | "holdings" | "paper";` and the TABS to `[["watchlists", "Watchlists"], ["holdings", "Holdings & risk"], ["paper", "Paper"]]`.
- Change the caption text to `Schwab accounts arrive in a later update.`.
- Replace the body line with:

```tsx
      {tab === "paper" ? <PaperTab /> : tab === "holdings" ? <HoldingsTab /> : <WatchlistsTab />}
```

`frontend/src/pages/StockPage.tsx`:
- Add `import { useState } from "react";`, add `Button` to the Fluent import, and add `import OrderTicket from "../components/OrderTicket";`.
- In the component, add `const [ticket, setTicket] = useState(false);`.
- In the header row, after the `{error && !q && …}` line, add:

```tsx
        <Button size="small" onClick={() => setTicket(true)}>Paper trade</Button>
        <OrderTicket open={ticket} symbol={symbol} onClose={() => setTicket(false)} />
```

`frontend/src/lib/commands.ts`: add this right after the HELP line:

```ts
  if (parts.length === 1 && head === "PAPER") return { kind: "go", route: { kind: "page", page: "portfolio", params: ["paper"] } };
```

`frontend/src/pages/HelpPage.tsx`:
- Add to the commands list (the list containing `["PF", …]`): `["PAPER", "Paper trading - a practice account with fake money; orders fill against real (delayed) prices."]`.
- Add to the glossary list (the one containing `["Max drawdown", …]`):
  - `["Limit order", "Buy or sell only at your price or better - it may never fill."]`
  - `["Stop order", "Waits until the price crosses your level, then trades at the next available price - often used to cap a loss."]`
  - `["Paper trading", "Practising with pretend money against real prices, so mistakes cost nothing."]`

  Match the separator style the file already uses in its strings.

- [ ] **Step 6: Run all frontend checks and watch them pass**

Run (in `frontend/`): `npx vitest run && npx tsc --noEmit`
Expected: all green, with no "act(" or "Unhandled" output.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/CompareChart.tsx frontend/src/pages/portfolio/PaperTab.tsx frontend/src/pages/portfolio/PaperTab.test.tsx frontend/src/pages/PortfolioPage.tsx frontend/src/pages/StockPage.tsx frontend/src/lib/commands.ts frontend/src/lib/commands.test.ts frontend/src/pages/HelpPage.tsx
git commit -m "Frontend: Paper tab with SPY comparison, stock-page Paper trade button, PAPER command

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Home block, Settings reset, docs and build

**Files:**
- Create: `frontend/src/blocks/PaperBlock.tsx`, `frontend/src/blocks/PaperBlock.test.tsx`
- Modify: `frontend/src/blocks/registry.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/pages/SettingsPage.test.tsx`
- Modify: `CLAUDE.md` (Status), `README.md` (a short "Paper trading" section)
- Rebuild: `src/howlet/static/app` (`npm run build`)

**Interfaces:**
- Consumes `api.paperAccount`, `api.paperReset`, `usd` (Task 4) and `Block`.
- Produces block type `paper` ("Paper account", needs nothing, default size w 6 h 8).

- [ ] **Step 1: Write the failing tests**

`frontend/src/blocks/PaperBlock.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import type { ReactElement } from "react";
import PaperBlock from "./PaperBlock";

afterEach(() => vi.restoreAllMocks());
const wrap = (el: ReactElement) => render(<FluentProvider theme={webDarkTheme}>{el}</FluentProvider>);

test("summary and top positions, removable", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    account: { id: "a", created: "x", start_cash: 10000 }, cash: 8000, equity: 10100, day_change: -12.5, total_return_pct: 1,
    positions: [{ symbol: "AAPL", qty: 10, avg_cost: 200, cost_basis: 2000, price: 210, value: 2100, unrealized: 100, unrealized_pct: 5 }],
    positions_value: 2100, realized_pnl: 0, open_orders: [], activity: [], market_open: false, prices_unavailable: [],
  })));
  wrap(<PaperBlock onRemove={() => {}} />);
  await waitFor(() => expect(screen.getByText("$10,100.00")).toBeTruthy());
  expect(screen.getByText("-$12.50 today")).toBeTruthy();
  expect(screen.getByText("AAPL")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Remove Paper account" })).toBeTruthy();
});

test("no account yet points to the Paper tab", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ account: null, market_open: false })));
  wrap(<PaperBlock />);
  await waitFor(() => expect(screen.getByText(/No paper account yet/)).toBeTruthy());
});
```

Append to `frontend/src/pages/SettingsPage.test.tsx`, reusing the file's existing render helper and imports. Add `fireEvent`/`waitFor` only if missing. The existing `beforeEach` stubs `fetch` with a never-settling promise; override it per test with `mockResolvedValue`:

```tsx
test("paper reset asks to confirm, then posts the start cash", async () => {
  // Only the reset resolves; other requests (e.g. tracked managers) stay pending as in beforeEach.
  const f = vi.spyOn(globalThis, "fetch").mockImplementation((u) => String(u) === "/api/paper/reset"
    ? Promise.resolve(new Response(JSON.stringify({ account: null, market_open: false })))
    : new Promise<Response>(() => {}));
  renderSettings();
  fireEvent.change(screen.getByLabelText("Paper starting cash"), { target: { value: "5000" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset paper account…" }));
  expect(f.mock.calls.some(([u]) => String(u) === "/api/paper/reset")).toBe(false);
  fireEvent.click(await screen.findByRole("button", { name: "Reset" }));
  await waitFor(() => {
    const post = f.mock.calls.find(([u]) => String(u) === "/api/paper/reset");
    expect(post && JSON.parse(String(post[1]!.body))).toEqual({ start_cash: 5000 });
  });
});
```

(If the file's render helper has a different name than `renderSettings`, use that name.)

- [ ] **Step 2: Run them and watch them fail**

Run: `npx vitest run src/blocks/PaperBlock.test.tsx src/pages/SettingsPage.test.tsx`
Expected: FAIL. `./PaperBlock` doesn't resolve, and there is no "Paper starting cash" label yet.

- [ ] **Step 3: Write `PaperBlock`** (`frontend/src/blocks/PaperBlock.tsx`)

```tsx
import { Caption1, Text } from "@fluentui/react-components";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { signed, tone } from "../lib/fmt";
import { usd } from "../lib/paper";
import Block from "./Block";
import Ticker from "../components/Ticker";

export default function PaperBlock({ onRemove }: { onRemove?: () => void }) {
  const { data, loading, error, fetchedAt } = useApi("paper-block", () => api.paperAccount(), 60_000);
  const a = data?.account ? data : null;
  return (
    <Block title="Paper account" {...{ loading, error, fetchedAt, refreshMs: 60_000, onRemove }} fixed={!onRemove}>
      {data && !a && <Caption1 style={{ color: "var(--dim)" }}>No paper account yet — open Portfolio → Paper to start one.</Caption1>}
      {a && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Text size={500} weight="semibold" className="num">{usd(a.equity)}</Text>
          <span className="num" style={{ color: tone(a.day_change) }}>{`${usd(a.day_change)} today`}</span>
          <span className="num" style={{ color: tone(a.total_return_pct) }}>{`${signed(a.total_return_pct, 1)}% total`}</span>
          {a.positions.slice(0, 5).map((p) => (
            <div key={p.symbol} style={{ display: "flex", justifyContent: "space-between" }}>
              <Ticker symbol={p.symbol} />
              <span className="num" style={{ color: tone(p.unrealized) }}>{usd(p.value)}</span>
            </div>
          ))}
        </div>
      )}
    </Block>
  );
}
```

Register it in `frontend/src/blocks/registry.tsx`. Add `import PaperBlock from "./PaperBlock";` and this entry in `BLOCKS` after `fund`:

```tsx
  paper: { label: "Paper account", needs: null, defaultSize: { w: 6, h: 8 }, render: (_c, r) => <PaperBlock onRemove={r} /> },
```

- [ ] **Step 4: Add the Settings reset** (`frontend/src/pages/SettingsPage.tsx`)

Add a component above `SettingsPage`, reusing the file's existing Fluent imports and adding any of `Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Input, Text` that are missing; also add `import { api } from "../lib/api";` and `import { parseNum } from "../lib/paper";` if missing:

```tsx
function PaperReset() {
  const [cash, setCash] = useState("100000");
  const [confirm, setConfirm] = useState(false);
  const [msg, setMsg] = useState("");
  const amount = parseNum(cash);
  const run = async () => {
    setConfirm(false);
    try { await api.paperReset(amount!); setMsg(`Paper account reset with $${amount!.toLocaleString("en-US")}. The old one is archived.`); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
        {/* the Input must be the Field's direct child so the label targets it */}
        <Field label="Paper starting cash"><Input inputMode="decimal" value={cash} onChange={(_, d) => setCash(d.value)} /></Field>
        <Button disabled={amount == null || amount <= 0} onClick={() => setConfirm(true)}>Reset paper account…</Button>
      </div>
      {msg && <Text role="status">{msg}</Text>}
      <Dialog open={confirm} onOpenChange={(_, d) => setConfirm(d.open)}>
        <DialogSurface><DialogBody>
          <DialogTitle>Reset paper account?</DialogTitle>
          <DialogContent>Your positions and order history move to the archive and a new account starts with ${amount?.toLocaleString("en-US")}.</DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={() => setConfirm(false)}>Cancel</Button>
            <Button appearance="primary" onClick={run}>Reset</Button>
          </DialogActions>
        </DialogBody></DialogSurface>
      </Dialog>
    </>
  );
}
```

In `SettingsPage`'s JSX, add a new card right after the "Layouts & backup" card:

```tsx
      <Card><Subtitle2>Paper account</Subtitle2>
        <PaperReset />
      </Card>
```

- [ ] **Step 5: Update the docs**
  - `CLAUDE.md` Status paragraph: after the per-stock pages sentence, add "Portfolio → Paper: a fake-money paper trading account (`paper.py`, `~/.howlet/paper.json`; market/limit/stop orders fill from real Yahoo bars, even while the app was closed; account vs SPY; stock-page Paper trade button; Home block; reset in Settings)."
  - `README.md`: add a short section near the dashboard docs:

```markdown
### Paper trading (fake money)

Practise without risking anything: Portfolio → **Paper** gives you a pretend account (default $100,000).
Place market, limit or stop orders from the **Paper trade** button on any stock page. They fill against
real (delayed) prices, including while Howlet was closed, and the tab shows your return vs simply holding
the S&P 500. Also available as `howlet paper` (CLI) and the `paper_account` / `paper_order` /
`paper_cancel` MCP tools. Reset lives in Settings. US stocks and ETFs only; no shorting, margin or fees.
```

- [ ] **Step 6: Run everything, then build**

Run in `frontend/`: `npx vitest run && npx tsc --noEmit && npm run build`
Then from the repo root: `PYTHONPATH=src pytest tests/ -q && ruff check src/ tests/`
Expected: all green, no "act(" or "Unhandled" output, and the build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/blocks/PaperBlock.tsx frontend/src/blocks/PaperBlock.test.tsx frontend/src/blocks/registry.tsx frontend/src/pages/SettingsPage.tsx frontend/src/pages/SettingsPage.test.tsx CLAUDE.md README.md
git add -A src/howlet/static/app
git commit -m "Paper account Home block, Settings reset, docs, rebuilt app

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Live verification (controller, after Task 6)

Restart the dev server (preview `howlet-dashboard`, port 8813). Back up `~/.howlet/paper.json` if it exists. Then:

1. `GET /api/paper` reads `{account: null, market_open: false}` (Saturday 2026-10-24).
2. Portfolio → Paper → Start with $10,000.
3. **After-hours market order.** Market-buy 1 SPY. It shows as open with "Market closed", and the explainer says it fills at the next open.
4. **A limit filled from real bars.** From the last session's 5m bars, take a level SPY traded at Friday afternoon. Then, through Python (`views.paper_order_view(..., now=<Fri 14:00Z>)`), place a backdated limit buy at that level against the real store. `GET /api/paper` should show it filled at that level or better, with the bar's timestamp.
5. **History.** The Paper tab chart and the vs-S&P line render; `GET /api/paper/history` has dates from the creation day.
6. Stock page → **Paper trade** opens the ticket with the symbol filled in; there is a Home block; Settings reset confirms and archives.
7. Restore the backup or delete the test `paper.json`.
8. **Not verifiable on a closed market:** an immediate in-session market fill. Flag it to the user as unverified until the next session.
