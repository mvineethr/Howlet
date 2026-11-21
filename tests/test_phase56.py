"""Phase 5 + 6 tests: paper fees/slippage, feed health, consensus universe,
CLI holdings tickers, --version, and top-level paper exports.

All offline (mocked HTTP / stub prices).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
import responses
from click.testing import CliRunner

from howlet import cli, paper
from howlet.market import Quote
from howlet.news import MARKET_FEEDS, NewsClient
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


COSTS = {"fee_per_trade_usd": 5.0, "slippage_bps": 100.0}  # $5/fill, 1% slippage


def account(cash=10_000.0, costs=None):
    return paper.new_state(cash, at(22, 14), costs=costs)


# ---- C4: paper costs ------------------------------------------------

def test_paper_costs_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("HOWLET_PAPER_FEE_USD", raising=False)
    monkeypatch.delenv("HOWLET_PAPER_SLIPPAGE_BPS", raising=False)
    assert paper.paper_costs() == {"fee_per_trade_usd": 0.0, "slippage_bps": 0.0}


def test_paper_costs_read_env_and_reject_bad_values(monkeypatch):
    monkeypatch.setenv("HOWLET_PAPER_FEE_USD", "2.50")
    monkeypatch.setenv("HOWLET_PAPER_SLIPPAGE_BPS", "25")
    assert paper.paper_costs() == {"fee_per_trade_usd": 2.5, "slippage_bps": 25.0}
    monkeypatch.setenv("HOWLET_PAPER_FEE_USD", "not-a-number")
    with pytest.raises(PaperError):
        paper.paper_costs()
    monkeypatch.setenv("HOWLET_PAPER_FEE_USD", "-1")
    with pytest.raises(PaperError):
        paper.paper_costs()
    monkeypatch.setenv("HOWLET_PAPER_FEE_USD", "0")
    monkeypatch.setenv("HOWLET_PAPER_SLIPPAGE_BPS", "-5")
    with pytest.raises(PaperError):
        paper.paper_costs()


def test_immediate_market_buy_pays_slippage_and_fee():
    prices = FakePrices(quotes={"AAPL": q("AAPL", 100.0)}, open_=True)
    state, order = paper.place_order(account(costs=COSTS), prices, FRI, "AAPL", "buy", 10)
    assert order["status"] == "filled"
    assert order["fill"]["price"] == 101.0  # 1% slippage: buys pay more
    assert order["fill"]["fee"] == 5.0
    cash, pos, _ = paper.ledger(state)
    assert cash == pytest.approx(10_000 - 10 * 101.0 - 5.0)
    assert pos["AAPL"] == [10.0, 1010.0]  # cost basis is the fill price, fee excluded


def test_sell_fill_is_lower_and_fee_nets_against_realized():
    prices = FakePrices(quotes={"AAPL": q("AAPL", 100.0)}, open_=True)
    state, _ = paper.place_order(account(costs=COSTS), prices, FRI, "AAPL", "buy", 10)
    state, sell = paper.place_order(state, prices, FRI, "AAPL", "sell", 10)
    assert sell["fill"]["price"] == 99.0  # 1% slippage: sells get less
    assert sell["fill"]["fee"] == 5.0
    cash, pos, realized = paper.ledger(state)
    assert pos == {}
    assert realized == pytest.approx(10 * 99.0 - 5.0 - 10 * 101.0)  # -25
    assert cash == pytest.approx(10_000 - 1015.0 + 985.0)


def test_limit_fill_never_exceeds_the_limit():
    # Limit buy at $100, bar opens at $100: slippage would push the fill
    # to $101, but the limit caps it at $100. The fee still applies.
    prices = FakePrices(
        quotes={"AAPL": q("AAPL", 100.0)},
        bars={"AAPL": [bar(at(23, 15), 100, 102, 100)]},
    )
    state, order = paper.place_order(account(costs=COSTS), prices, FRI, "AAPL", "buy", 10, type="limit", limit=100)
    assert order["status"] == "open"
    paper.settle(state, prices, SAT)
    assert order["status"] == "filled"
    assert order["fill"]["price"] == 100.0
    assert order["fill"]["fee"] == 5.0


def test_settle_fill_applies_slippage_below_the_limit():
    # Gap-down open at $99 under a $100 limit: fill at $99 + 1% = $99.99.
    prices = FakePrices(
        quotes={"AAPL": q("AAPL", 100.0)},
        bars={"AAPL": [bar(at(23, 15), 99, 101, 98)]},
    )
    state, order = paper.place_order(account(costs=COSTS), prices, FRI, "AAPL", "buy", 10, type="limit", limit=100)
    paper.settle(state, prices, SAT)
    assert order["status"] == "filled"
    assert order["fill"]["price"] == pytest.approx(99.99)
    assert order["fill"]["fee"] == 5.0


def test_reset_preserves_costs():
    state = account(costs=COSTS)
    fresh = paper.reset(state, 50_000, SAT)
    assert fresh["costs"] == COSTS
    assert fresh["account"]["start_cash"] == 50_000


def test_summary_reports_fees_paid_and_costs():
    prices = FakePrices(quotes={"AAPL": q("AAPL", 100.0)}, open_=True)
    state, _ = paper.place_order(account(costs=COSTS), prices, FRI, "AAPL", "buy", 10)
    state, _ = paper.place_order(state, prices, FRI, "AAPL", "sell", 10)
    summary = paper.summary(state, prices, FRI)
    assert summary["fees_paid"] == 10.0
    assert summary["costs"] == COSTS


def test_state_without_costs_behaves_like_before():
    # A pre-0.8.1 paper.json has no "costs" key and fills have no "fee".
    state = account()
    del state["costs"]
    prices = FakePrices(quotes={"AAPL": q("AAPL", 100.0)}, open_=True)
    state, order = paper.place_order(state, prices, FRI, "AAPL", "buy", 10)
    assert order["fill"] == {"ts": order["fill"]["ts"], "price": 100.0, "fee": 0.0}
    cash, _, _ = paper.ledger(state)
    assert cash == pytest.approx(10_000 - 1000.0)
    assert paper.summary(state, prices, FRI)["fees_paid"] == 0.0


# ---- G7: feed health --------------------------------------------------

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>feed</title>
<item><title>Story</title><link>https://example.com/a</link>
<pubDate>Mon, 06 Jul 2026 12:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_feed_health_never_before_any_fetch():
    health = NewsClient().feed_health()
    assert len(health) == len(MARKET_FEEDS) + 3  # 7 market + 3 ticker feeds
    assert all(h["status"] == "never" and h["last_ok"] is None for h in health)
    assert {h["feed"] for h in health} == {f"market:{s}" for s, _ in MARKET_FEEDS} | {
        "ticker:Yahoo Finance", "ticker:Google News", "ticker:Seeking Alpha",
    }


@responses.activate
def test_feed_health_records_ok_and_failed():
    first_url = MARKET_FEEDS[0][1]
    responses.get(first_url, body=RSS_TEMPLATE)
    for _, url in MARKET_FEEDS[1:]:
        responses.get(url, status=503)

    client = NewsClient()
    client.get_market_news()
    by_feed = {h["feed"]: h for h in client.feed_health()}
    ok = by_feed[f"market:{MARKET_FEEDS[0][0]}"]
    assert ok["status"] == "ok"
    assert ok["last_ok"] is not None
    assert ok["items"] == 1
    assert ok["last_error"] is None
    failed = by_feed[f"market:{MARKET_FEEDS[1][0]}"]
    assert failed["status"] == "failed"
    assert failed["last_ok"] is None
    assert "503" in (failed["last_error"] or "")


@responses.activate
def test_ticker_news_records_ticker_feed_health():
    from howlet.news import TICKER_FEED_URLS

    for _source, template in TICKER_FEED_URLS:
        responses.get(template.format(symbol="AAPL"), body=RSS_TEMPLATE)
    client = NewsClient()
    client.get_ticker_news(["AAPL"])
    by_feed = {h["feed"]: h for h in client.feed_health()}
    assert by_feed["ticker:Yahoo Finance"]["status"] == "ok"
    assert by_feed["ticker:Yahoo Finance"]["items"] == 1


def test_news_health_endpoint_reports_feeds():
    from unittest.mock import MagicMock

    from howlet.dashboard import create_app
    from howlet.views import _EdgarLocks

    services = MagicMock()
    services.news = NewsClient()
    services.edgar_locks = _EdgarLocks()
    services.edgar_lock_for = services.edgar_locks.for_key
    app = create_app("Test Suite test@example.com", services=services)
    app.config["TESTING"] = True
    data = app.test_client().get("/api/news/health").get_json()
    assert len(data["feeds"]) == len(MARKET_FEEDS) + 3
    assert all(f["status"] == "never" for f in data["feeds"])


# ---- G1: consensus universe -------------------------------------------

def test_build_consensus_universe_unions_and_sorts_tickers(monkeypatch):
    from howlet.consensus import ManagerPortfolio
    from howlet.screener import build_consensus_universe

    portfolios = [
        ManagerPortfolio(label="A", cik="1", period_of_report="2026-09-30",
                         positions={"037833100": {}, "594918104": {}}),
        ManagerPortfolio(label="B", cik="2", period_of_report="2026-09-30",
                         positions={"594918104": {}, "023135106": {}, "000000000": {}}),
    ]
    monkeypatch.setattr(
        "howlet.screener.fetch_latest_portfolios", lambda client, managers, cache=None: portfolios
    )

    class _Resolver:
        def resolve(self, cusips):
            return {"037833100": "AAPL", "594918104": "MSFT",
                    "023135106": "AMZN", "000000000": None}

    tickers = build_consensus_universe(MagicMock(), resolver=_Resolver())
    assert tickers == ["AAPL", "AMZN", "MSFT"]  # sorted, deduped, unmapped skipped


def test_build_consensus_universe_empty_when_no_portfolios(monkeypatch):
    from howlet.screener import build_consensus_universe

    monkeypatch.setattr(
        "howlet.screener.fetch_latest_portfolios", lambda client, managers, cache=None: []
    )
    assert build_consensus_universe(MagicMock()) == []


def test_screener_view_consensus_source_and_fallback(monkeypatch):
    from howlet import views

    svc = MagicMock()
    captured = {}

    def fake_screen(market, fundamentals, universe=None, cache=None, filters=None):
        captured["universe"] = universe
        return []

    monkeypatch.setattr(views, "screen", fake_screen)
    monkeypatch.setattr(views, "build_consensus_universe", lambda *a, **k: ["AAPL", "MSFT"])
    result = views.screener_view(svc, universe_source="consensus")
    assert captured["universe"] == ["AAPL", "MSFT"]
    assert result["universe"] == "consensus"
    assert result["universe_size"] == 2
    assert result["rows"] == []

    # Empty consensus falls back to the default list, labelled as such.
    monkeypatch.setattr(views, "build_consensus_universe", lambda *a, **k: [])
    result = views.screener_view(svc, universe_source="consensus")
    assert captured["universe"] is None
    assert result["universe"] == "default"


def test_screener_endpoint_accepts_consensus(monkeypatch):
    from howlet import views
    from howlet.dashboard import create_app

    services = MagicMock()
    services.edgar_locks = views._EdgarLocks()
    services.edgar_lock_for = services.edgar_locks.for_key
    monkeypatch.setattr(views, "build_consensus_universe", lambda *a, **k: ["AAPL"])
    monkeypatch.setattr(views, "screen", lambda *a, **k: [])
    app = create_app("Test Suite test@example.com", services=services)
    app.config["TESTING"] = True
    data = app.test_client().get("/api/screener?universe=consensus").get_json()
    assert data["universe"] == "consensus"
    assert data["universe_size"] == 1


# ---- F6: CLI holdings tickers ------------------------------------------

def _filing(accession, period, filed):
    from howlet.models import FilingSummary

    return FilingSummary(
        cik="0001067983", accession_number=accession, filing_date=filed,
        period_of_report=period, primary_doc="primary.htm", form="13F-HR",
    )


def _holding(name, cusip, value, shares):
    from howlet.models import Holding

    return Holding(name_of_issuer=name, cusip=cusip, value_usd=value,
                   shares=shares, share_type="SH", investment_discretion="SOLE")


class _FakeEdgarClient:
    def __init__(self, filings):
        self._filings = filings

    def list_13f_filings(self, cik, limit=8):
        return self._filings[:limit]


class _FakeResolver:
    def __init__(self, mapping):
        self._mapping = mapping

    def resolve(self, cusips):
        return {c: self._mapping.get(c) for c in cusips}


class _FakeMarket:
    def __init__(self, quotes):
        self._quotes = quotes

    def get_quotes(self, symbols):
        return {s: self._quotes[s] for s in symbols if s in self._quotes}


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setenv("EDGAR_USER_AGENT", "Test Suite test@example.com")
    return CliRunner()


def _setup_holdings(runner, monkeypatch, holdings, mapping, quotes):
    filings = [_filing("0001-24-000001", date(2024, 3, 31), date(2024, 5, 15))]
    monkeypatch.setattr(cli, "EdgarClient", lambda ua: _FakeEdgarClient(filings))
    monkeypatch.setattr(cli, "cached_information_table", lambda client, cache, filing: holdings)
    monkeypatch.setattr(cli, "CusipTickerResolver", lambda: _FakeResolver(mapping))
    monkeypatch.setattr(cli, "YahooMarketClient", lambda: _FakeMarket(quotes))


def test_holdings_shows_tickers_and_prices(runner, monkeypatch):
    holdings = [
        _holding("APPLE INC", "037833100", 50_000, 1_000),
        _holding("MICROSOFT CORP", "594918104", 40_000, 500),
    ]
    _setup_holdings(runner, monkeypatch, holdings,
                    {"037833100": "AAPL", "594918104": "MSFT"},
                    {"AAPL": q("AAPL", 200.0), "MSFT": q("MSFT", 400.0)})
    result = runner.invoke(cli.main, ["holdings", "buffett"])
    assert result.exit_code == 0, result.output
    assert "AAPL" in result.output and "MSFT" in result.output
    assert "200.00" in result.output and "400.00" in result.output


def test_holdings_unresolved_ticker_shows_dash(runner, monkeypatch):
    _setup_holdings(runner, monkeypatch, [_holding("APPLE INC", "037833100", 50_000, 1_000)], {}, {})
    result = runner.invoke(cli.main, ["holdings", "buffett"])
    assert result.exit_code == 0, result.output
    assert "APPLE INC" in result.output
    assert "-" in result.output


def test_holdings_csv_has_ticker_and_price(runner, monkeypatch, tmp_path):
    holdings = [_holding("APPLE INC", "037833100", 50_000, 1_000)]
    _setup_holdings(runner, monkeypatch, holdings,
                    {"037833100": "AAPL"}, {"AAPL": q("AAPL", 200.0)})
    csv_path = tmp_path / "holdings.csv"
    result = runner.invoke(cli.main, ["holdings", "buffett", "--csv", str(csv_path)])
    assert result.exit_code == 0, result.output
    rows = csv_path.read_text().splitlines()
    assert rows[0] == "issuer,cusip,ticker,value_usd,shares,share_type,price"
    assert rows[1] == "APPLE INC,037833100,AAPL,50000,1000,SH,200.0"


# ---- F4 + G5 ------------------------------------------------------------

def test_version_flag(runner):
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert "0.8.1" in result.output


def test_top_level_paper_exports():
    from howlet import PaperError, PaperStore

    assert PaperStore.__name__ == "PaperStore"
    assert issubclass(PaperError, ValueError)
