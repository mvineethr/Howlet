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
