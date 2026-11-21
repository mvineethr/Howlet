"""Phase 3 (paper trading + security) and Phase 4 (performance) fixes.

Offline tests: prices mocked, no network. The Yahoo batch path uses
`responses`; the paper views use stub markets and real PaperStores.
"""

from __future__ import annotations

import multiprocessing as mp
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import responses

from howlet import paper, views
from howlet.dashboard import create_app
from howlet.market import CHART_URL, QUOTE_URL, Quote, YahooMarketClient
from howlet.paper import PaperStore
from howlet.views import _EdgarLocks

FRI = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)  # Friday


def _at(day_offset=0, hour=14, minute=0):
    return FRI + timedelta(days=day_offset, hours=hour - 14, minutes=minute)


# --------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------- #


class _StubMarket:
    """get_quote returns canned Quotes keyed by symbol (range ignored)."""

    def __init__(self, quotes):
        self._quotes = quotes

    def get_quote(self, symbol, range_="5d", interval="1d"):
        return self._quotes.get(symbol)


def _aapl_quote(price=200.0, bars=None):
    """AAPL quote; `bars` is [(ts, open, high, low)] for settlement."""
    q = Quote(symbol="AAPL", price=price, previous_close=198.0,
              currency="USD", instrument_type="EQUITY")
    if bars:
        q.history_ts = [b[0] for b in bars]
        q.history_open = [b[1] for b in bars]
        q.history_high = [b[2] for b in bars]
        q.history_low = [b[3] for b in bars]
    return q


def _spy_quote(fresh_bar_ts=None):
    q = Quote(symbol="SPY", price=500.0, currency="USD", instrument_type="ETF")
    if fresh_bar_ts is not None:
        q.history_ts = [fresh_bar_ts]
    return q


def _paper_svc(tmp_path, aapl=None, spy=None):
    market = _StubMarket({
        "AAPL": aapl or _aapl_quote(),
        "SPY": spy or _spy_quote(),
    })
    return SimpleNamespace(paper=PaperStore(tmp_path), market=market)


def _v7_entry(symbol, price, prev):
    return {
        "symbol": symbol, "regularMarketPrice": price,
        "regularMarketPreviousClose": prev, "currency": "USD",
        "longName": f"{symbol} Inc", "fullExchangeName": "NasdaqGS",
        "quoteType": "EQUITY", "regularMarketDayHigh": price + 1,
        "regularMarketDayLow": price - 1, "fiftyTwoWeekHigh": price + 50,
        "fiftyTwoWeekLow": price - 50, "regularMarketVolume": 1234567,
    }


def _v7_payload(*entries):
    return {"quoteResponse": {"result": list(entries), "error": None}}


def _chart_payload(symbol, price, closes):
    ts = [1_700_000_000 + i * 86400 for i in range(len(closes))]
    return {
        "chart": {"result": [{
            "meta": {"symbol": symbol, "regularMarketPrice": price,
                     "chartPreviousClose": closes[-2], "currency": "USD"},
            "timestamp": ts,
            "indicators": {"quote": [{
                "close": closes, "open": closes, "high": closes,
                "low": closes, "volume": [100] * len(closes),
            }]},
        }], "error": None},
    }


# --------------------------------------------------------------------- #
# C1 - GET endpoints no longer settle-and-save
# --------------------------------------------------------------------- #


def test_read_settles_in_memory_but_does_not_save(tmp_path):
    """A day order that would fill shows filled on GET, but the file on
    disk still says open until a write path settles it."""
    bar_ts = int((_at(hour=15)).timestamp())
    aapl = _aapl_quote(bars=[(bar_ts, 160.0, 165.0, 140.0)])
    svc = _paper_svc(tmp_path, aapl=aapl)
    views.paper_order_view(svc, "AAPL", "buy", 1, type="limit", limit=150,
                           tif="gtc", now=_at(hour=14))
    assert svc.paper.load()["orders"][0]["status"] == "open"

    acct = views.paper_account_view(svc, now=_at(hour=16))
    assert acct["open_orders"] == []  # settled in memory: filled
    assert acct["activity"][0]["status"] == "filled"
    # ...but nothing was written back.
    assert svc.paper.load()["orders"][0]["status"] == "open"

    hist = views.paper_history_view(svc, now=_at(hour=16))
    assert hist["dates"] == []  # no SPY closes from the stub market
    assert svc.paper.load()["orders"][0]["status"] == "open"

    # A write path persists the settlement.
    views.paper_order_view(svc, "AAPL", "buy", 1, type="limit", limit=150,
                           tif="gtc", now=_at(hour=16))
    assert svc.paper.load()["orders"][0]["status"] == "filled"


# --------------------------------------------------------------------- #
# C2 - cross-process lock + unique temp names
# --------------------------------------------------------------------- #


def test_save_leaves_no_temp_files(tmp_path):
    store = PaperStore(tmp_path)
    state = {"version": 1,
             "account": {"id": "x", "created": "2026-01-01T00:00:00+00:00",
                         "start_cash": 100_000},
             "orders": [], "archive": []}
    for _ in range(20):
        store.save(state)
    assert list(tmp_path.glob("paper.json.*.tmp")) == []
    assert store.load()["account"]["id"] == "x"


def test_locked_serializes_threads(tmp_path):
    """Eight threads hammering save under locked(): the file always
    parses and holds one of the written states."""
    store = PaperStore(tmp_path)
    base = {"version": 1,
            "account": {"id": "base", "created": "2026-01-01T00:00:00+00:00",
                        "start_cash": 100_000},
            "orders": [], "archive": []}
    store.save(base)
    written = set()

    def worker(n):
        for i in range(25):
            with paper.locked(store):
                state = store.load()
                state["account"] = dict(state["account"], id=f"w{n}-{i}")
                store.save(state)
                written.add(f"w{n}-{i}")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    final = store.load()
    assert final["account"]["id"] in written
    assert (tmp_path / "paper.json.lock").exists()
    assert list(tmp_path.glob("paper.json.*.tmp")) == []


def _lock_worker(path, tag):
    store = PaperStore(path)
    base = {"version": 1,
            "account": {"id": "base", "created": "2026-01-01T00:00:00+00:00",
                        "start_cash": 100_000},
            "orders": [], "archive": []}
    for i in range(10):
        with paper.locked(store):
            state = store.load() or base
            state["account"] = dict(state["account"], id=f"{tag}-{i}")
            store.save(state)


def test_locked_serializes_processes(tmp_path):
    """Two processes writing under locked(): no torn file, no lost
    update beyond last-writer-wins."""
    store = PaperStore(tmp_path)
    store.save({"version": 1,
                "account": {"id": "base", "created": "2026-01-01T00:00:00+00:00",
                            "start_cash": 100_000},
                "orders": [], "archive": []})
    # Default start method: fork on POSIX, spawn on Windows (there is no
    # fork on Windows - mp.get_context("fork") raises ValueError there).
    # The lock under test is start-method agnostic; _lock_worker is a
    # top-level function so spawn can pickle it by reference.
    ctx = mp.get_context()
    procs = [ctx.Process(target=_lock_worker, args=(tmp_path, f"p{n}"))
             for n in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
    assert all(p.exitcode == 0 for p in procs)
    final = store.load()
    assert final is not None and final["account"]["id"].startswith("p")
    assert list(tmp_path.glob("paper.json.*.tmp")) == []


# --------------------------------------------------------------------- #
# D1 - dashboard token auth for mutating paper endpoints
# --------------------------------------------------------------------- #


def _token_api(tmp_path, token, monkeypatch=None):
    svc = _paper_svc(tmp_path)
    app = create_app("Test Suite test@example.com", services=svc,
                     dashboard_token=token)
    app.config["TESTING"] = True
    return app.test_client()


def _place(client, headers=None):
    return client.post("/api/paper/orders",
                       json={"symbol": "AAPL", "side": "buy", "qty": 1,
                             "type": "limit", "limit": 150},
                       headers=headers or {})


def test_token_required_for_paper_writes(tmp_path):
    api = _token_api(tmp_path, "secret")
    assert _place(api).status_code == 401
    assert api.post("/api/paper/reset", json={}).status_code == 401
    # Reads are never gated.
    assert api.get("/api/paper").status_code == 200
    assert api.get("/api/paper/history").status_code == 200
    # Either header form works.
    assert _place(api, {"X-Howlet-Token": "secret"}).status_code == 201
    assert _place(api, {"Authorization": "Bearer secret"}).status_code == 201
    assert _place(api, {"X-Howlet-Token": "wrong"}).status_code == 401


def test_token_from_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("HOWLET_DASHBOARD_TOKEN", "envsecret")
    api = _token_api(tmp_path, None)
    assert _place(api).status_code == 401
    assert _place(api, {"X-Howlet-Token": "envsecret"}).status_code == 201


def test_no_token_means_local_only_open(tmp_path):
    api = _token_api(tmp_path, None)
    assert _place(api).status_code == 201


# --------------------------------------------------------------------- #
# D2 - paper spending caps
# --------------------------------------------------------------------- #


def test_per_order_cap(tmp_path):
    svc = _paper_svc(tmp_path)
    with pytest.raises(paper.PaperError, match="per-order paper cap"):
        views.paper_order_view(svc, "AAPL", "buy", 60, type="limit", limit=200)
    # Exactly at the cap is allowed.
    views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200)


def test_daily_cap(tmp_path):
    svc = _paper_svc(tmp_path)
    views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200)
    views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200)
    with pytest.raises(paper.PaperError, match="daily cap"):
        views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200)


def test_sells_are_exempt_from_caps(tmp_path):
    """A sell returns cash, it doesn't spend it - even a $20k sell of a
    position built from two $10k buys must go through."""
    # 14:30 UTC is 10:30 New York: inside session hours, so market buys fill.
    now = _at(hour=14, minute=30)
    svc = _paper_svc(tmp_path, spy=_spy_quote(fresh_bar_ts=int(now.timestamp()) - 60))
    views.paper_order_view(svc, "AAPL", "buy", 50, type="market", now=now)
    views.paper_order_view(svc, "AAPL", "buy", 50, type="market", now=now)
    order = views.paper_order_view(svc, "AAPL", "sell", 100, type="market", now=now)
    assert order["status"] == "filled"


def test_caps_configurable_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOWLET_PAPER_MAX_ORDER_USD", "100")
    svc = _paper_svc(tmp_path)
    with pytest.raises(paper.PaperError, match="per-order paper cap"):
        views.paper_order_view(svc, "AAPL", "buy", 1, type="limit", limit=200)
    monkeypatch.setenv("HOWLET_PAPER_MAX_ORDER_USD", "not-a-number")
    with pytest.raises(paper.PaperError, match="must be a number"):
        views.paper_order_view(svc, "AAPL", "buy", 1, type="limit", limit=200)


# P2 (Codex review) - pending buys count at their limit/stop level
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("type_,level_kw", [
    ("limit", {"limit": 150}),
    ("stop", {"stop": 150}),
])
def test_pending_buy_counts_at_limit_or_stop(tmp_path, type_, level_kw):
    """An open buy whose level is above the quote commits qty x level.

    Quote is $100, level is $150: the first order commits $7,500, not
    $5,000. Two further $10,000 buys must then breach the $25,000 daily
    cap; at the reference price they would total exactly $25,000 and pass.
    """
    svc = _paper_svc(tmp_path, aapl=_aapl_quote(price=100.0))
    views.paper_order_view(svc, "AAPL", "buy", 50, type=type_, **level_kw)
    views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200)
    with pytest.raises(paper.PaperError, match="daily cap"):
        views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200)


def test_filled_order_counts_on_fill_date_not_place_date(tmp_path):
    """A GTC buy placed yesterday that fills today counts toward TODAY's
    daily cap, not yesterday's (the order's creation date)."""
    friday_bar = (int(_at(0).timestamp()), 199, 201, 198)
    svc = _paper_svc(tmp_path, aapl=_aapl_quote(price=200.0, bars=[friday_bar]))
    # Thursday: GTC limit buy, 50 x $200 = $10,000 committed.
    views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200,
                           tif="gtc", now=_at(day_offset=-1))
    # Friday: placing the next order settles the GTC one against the
    # Friday bar (fills at $199) - it now counts toward Friday's spend.
    views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200, now=_at(0))
    with pytest.raises(paper.PaperError, match="daily cap"):
        views.paper_order_view(svc, "AAPL", "buy", 50, type="limit", limit=200, now=_at(0))


# --------------------------------------------------------------------- #
# E1 - finer-grained EDGAR locking
# --------------------------------------------------------------------- #


def test_lock_registry_keys():
    registry = _EdgarLocks()
    assert registry.for_key("cik:123") is registry.for_key("cik:123")
    assert registry.for_key("cik:123") is not registry.for_key("cik:456")
    assert registry.for_key("cik:123") is not registry.for_key("consensus")


def test_different_keys_run_in_parallel():
    registry = _EdgarLocks()
    entered_a, entered_b = threading.Event(), threading.Event()
    release = threading.Event()

    def hold(key, entered):
        with registry.for_key(key):
            entered.set()
            assert release.wait(timeout=5)

    a = threading.Thread(target=hold, args=("cik:1", entered_a))
    b = threading.Thread(target=hold, args=("cik:2", entered_b))
    a.start()
    b.start()
    assert entered_a.wait(timeout=5) and entered_b.wait(timeout=5)
    release.set()
    a.join(timeout=5)
    b.join(timeout=5)


def test_same_key_serializes():
    registry = _EdgarLocks()
    acquired = threading.Event()

    def hold_first():
        with registry.for_key("cik:1"):
            acquired.set()
            threading.Event().wait(0.3)

    t = threading.Thread(target=hold_first)
    t.start()
    assert acquired.wait(timeout=5)
    second_in = threading.Event()
    t2 = threading.Thread(
        target=lambda: (registry.for_key("cik:1").__enter__(), second_in.set()))
    t2.start()
    assert not second_in.wait(timeout=0.1)  # blocked behind the first holder
    t.join(timeout=5)
    assert second_in.wait(timeout=5)
    registry.for_key("cik:1").release()


# --------------------------------------------------------------------- #
# B10 - batched get_quotes
# --------------------------------------------------------------------- #


@responses.activate
def test_batch_quotes_one_request():
    responses.get(QUOTE_URL, json=_v7_payload(
        _v7_entry("AAPL", 210.0, 205.0),
        _v7_entry("MSFT", 400.0, 390.0),
        _v7_entry("GOOG", 150.0, 148.0),
    ))
    client = YahooMarketClient()
    quotes = client.get_quotes(["AAPL", "MSFT", "GOOG"])
    assert len([c for c in responses.calls if c.request.url.startswith(QUOTE_URL)]) == 1
    assert quotes["AAPL"].price == 210.0
    assert quotes["MSFT"].change_pct == pytest.approx((400.0 - 390.0) / 390.0 * 100)
    assert quotes["GOOG"].volume == 1234567
    assert quotes["AAPL"].sparkline == []  # batch quotes carry no history


@responses.activate
def test_batch_quotes_cached_within_ttl():
    responses.get(QUOTE_URL, json=_v7_payload(_v7_entry("AAPL", 210.0, 205.0)))
    client = YahooMarketClient()
    client.get_quotes(["AAPL"])
    client.get_quotes(["AAPL"])
    assert len(responses.calls) == 1


@responses.activate
def test_batch_failure_falls_back_to_sequential():
    responses.get(QUOTE_URL, status=500)
    responses.get(CHART_URL.format(symbol="AAPL"),
                  json=_chart_payload("AAPL", 210.0, [200.0, 205.0, 210.0]))
    client = YahooMarketClient()
    quotes = client.get_quotes(["AAPL"])
    assert quotes["AAPL"].price == 210.0
    assert quotes["AAPL"].sparkline == [200.0, 205.0, 210.0]


@responses.activate
def test_batch_missing_symbol_falls_back():
    responses.get(QUOTE_URL, json=_v7_payload(_v7_entry("AAPL", 210.0, 205.0)))
    responses.get(CHART_URL.format(symbol="MSFT"),
                  json=_chart_payload("MSFT", 400.0, [390.0, 395.0, 400.0]))
    client = YahooMarketClient()
    quotes = client.get_quotes(["AAPL", "MSFT"])
    assert quotes["AAPL"].price == 210.0
    assert quotes["MSFT"].sparkline == [390.0, 395.0, 400.0]


@responses.activate
def test_with_history_uses_per_symbol_chart():
    responses.get(CHART_URL.format(symbol="AAPL"),
                  json=_chart_payload("AAPL", 210.0, [200.0, 205.0, 210.0]))
    client = YahooMarketClient()
    quotes = client.get_quotes(["AAPL"], with_history=True)
    assert quotes["AAPL"].sparkline == [200.0, 205.0, 210.0]
    assert not any(c.request.url.startswith(QUOTE_URL) for c in responses.calls)
