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
