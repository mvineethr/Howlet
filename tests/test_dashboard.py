"""Tests for the dashboard's JSON API (Flask test client, mocked services)."""

from __future__ import annotations

import threading
from datetime import date
from unittest.mock import MagicMock

import pytest

from edgar13f.dashboard import create_app
from edgar13f.market import Quote
from edgar13f.models import FilingSummary, Holding
from edgar13f.news import NewsItem


def _filing(accession: str, period: date) -> FilingSummary:
    return FilingSummary(
        cik="0001067983",
        accession_number=accession,
        filing_date=date(2026, 5, 15),
        period_of_report=period,
        primary_doc="primary.xml",
    )


def _holding(issuer, cusip, value, shares, share_type="SH"):
    return Holding(
        name_of_issuer=issuer,
        cusip=cusip,
        value_usd=value,
        shares=shares,
        share_type=share_type,
        investment_discretion="SOLE",
    )


class FakeServices:
    """Stands in for DashboardServices with every client mocked."""

    def __init__(self):
        self.edgar = MagicMock()
        self.market = MagicMock()
        self.news = MagicMock()
        self.resolver = MagicMock()
        self.fundamentals = MagicMock()
        self.events = MagicMock()
        self.options = MagicMock()
        self.crypto = MagicMock()
        self.screener_cache = None  # bypass disk caching in tests
        self.cache = None  # bypass disk caching in tests
        self.form4_cache = None  # bypass disk caching in tests
        self.edgar_lock = threading.Lock()


@pytest.fixture
def services() -> FakeServices:
    return FakeServices()


@pytest.fixture
def api(services):
    app = create_app("Test Suite test@example.com", services=services)
    app.config["TESTING"] = True
    return app.test_client()


def test_crypto_endpoint_reports_source_and_rows(api, services):
    services.crypto.get_markets.return_value = (
        "coingecko",
        [{"rank": 1, "symbol": "BTC", "name": "Bitcoin", "price": 64132,
          "change_pct_24h": -0.01, "market_cap": 1286366720245,
          "volume_24h": 28499852020, "high_24h": 64286, "low_24h": 62528}],
    )
    data = api.get("/api/crypto?limit=10").get_json()
    assert data["source"] == "coingecko"
    assert data["rows"][0]["symbol"] == "BTC"
    services.crypto.get_markets.assert_called_once_with(limit=10)


def test_regulatory_endpoint_wraps_federal_register(api, monkeypatch):
    from edgar13f import regulatory

    monkeypatch.setattr(
        regulatory, "get_sec_documents",
        lambda limit=20: [{"title": "A rule", "type": "Rule",
                           "document_number": "2026-1", "html_url": "https://x",
                           "publication_date": "2026-07-17"}],
    )
    data = api.get("/api/regulatory").get_json()
    assert data == [{"title": "A rule", "type": "Rule",
                     "document_number": "2026-1", "html_url": "https://x",
                     "publication_date": "2026-07-17"}]


def test_index_serves_terminal_html(api):
    resp = api.get("/")
    assert resp.status_code == 200
    assert b"EDGAR13F" in resp.data


def test_managers_deduplicates_alias_ciks(api):
    data = api.get("/api/managers").get_json()
    ciks = [m["cik"] for m in data]
    assert len(ciks) == len(set(ciks))  # buffett/berkshire collapse to one


def test_portfolio_aggregates_by_cusip_and_joins_quotes(api, services):
    services.edgar.list_13f_filings.return_value = [
        _filing("0000000000-26-000001", date(2026, 3, 31))
    ]
    # AAPL split across two infoTable entries (Berkshire really does this).
    services.edgar.get_information_table.return_value = [
        _holding("APPLE INC", "037833100", 600, 6),
        _holding("APPLE INC", "037833100", 400, 4),
        _holding("BOND THING", "999999999", 1000, 10, share_type="PRN"),
    ]
    services.resolver.resolve.return_value = {"037833100": "AAPL"}
    services.market.get_quotes.return_value = {
        "AAPL": Quote(symbol="AAPL", price=210.0, previous_close=200.0,
                      currency="USD", sparkline=[200.0, 210.0])
    }

    data = api.get("/api/portfolio/buffett").get_json()
    assert data["period_of_report"] == "2026-03-31"
    assert data["total_value_usd"] == 2000
    assert data["position_count"] == 2

    by_cusip = {p["cusip"]: p for p in data["positions"]}
    aapl = by_cusip["037833100"]
    assert aapl["value_usd"] == 1000  # aggregated
    assert aapl["shares"] == 10
    assert aapl["weight_pct"] == 50.0
    assert aapl["ticker"] == "AAPL"
    assert aapl["price"] == 210.0
    assert round(aapl["change_pct"], 2) == 5.0

    # PRN (bond) positions are not sent for ticker resolution.
    resolved_cusips = services.resolver.resolve.call_args[0][0]
    assert "999999999" not in resolved_cusips
    assert by_cusip["999999999"]["ticker"] is None


def test_portfolio_404_when_no_filings(api, services):
    services.edgar.list_13f_filings.return_value = []
    resp = api.get("/api/portfolio/nobody")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_upstream_connection_error_returns_json_502_not_html(api, services):
    import requests as _requests

    services.edgar.list_13f_filings.side_effect = _requests.ConnectionError(
        "Connection aborted (10054)"
    )
    resp = api.get("/api/portfolio/buffett")
    assert resp.status_code == 502
    # The frontend widgets JSON-parse every response - an HTML error page
    # here shows up as "Unexpected token '<'" in the UI (seen live).
    assert resp.get_json()["error"].startswith("Upstream request failed")


def test_diff_endpoint_reports_changes_between_filings(api, services):
    current = _filing("0000000000-26-000002", date(2026, 3, 31))
    prior = _filing("0000000000-25-000001", date(2025, 12, 31))
    services.edgar.list_13f_filings.return_value = [current, prior]
    services.edgar.get_information_table.side_effect = lambda f: (
        [_holding("APPLE INC", "037833100", 1000, 10)]
        if f is prior
        else [_holding("APPLE INC", "037833100", 1500, 15),
              _holding("NEW CO", "111111111", 500, 5)]
    )

    data = api.get("/api/diff/buffett").get_json()
    assert data["prior_period"] == "2025-12-31"
    statuses = {c["cusip"]: c["status"] for c in data["changes"]}
    assert statuses == {"111111111": "NEW", "037833100": "INCREASED"}


def test_tape_returns_labeled_quotes(api, services):
    services.market.get_quotes.return_value = {
        "^GSPC": Quote(symbol="^GSPC", price=6100.0, previous_close=6000.0)
    }
    data = api.get("/api/tape").get_json()
    assert data == [
        {
            "symbol": "^GSPC",
            "label": "S&P 500",
            "price": 6100.0,
            "change": 100.0,
            "change_pct": pytest.approx(100 / 6000 * 100),
        }
    ]


def test_security_endpoint_returns_detail_and_history(api, services):
    services.market.get_security.return_value = Quote(
        symbol="AAPL", price=210.0, previous_close=200.0, currency="USD",
        long_name="Apple Inc.", exchange="NasdaqGS", instrument_type="EQUITY",
        day_low=207.5, day_high=212.0, week52_low=164.0, week52_high=260.0,
        volume=54321000, sparkline=[200.0, 210.0], history_ts=[1, 2],
    )
    # The stats side is a separate daily-bar quote so CHANGE is the day
    # move even when the chart shows a 1y range.
    services.market.get_quote.return_value = Quote(
        symbol="AAPL", price=210.0, previous_close=208.0, volume=99,
        sparkline=[208.0, 210.0],
    )
    data = api.get("/api/security/AAPL?range=1y").get_json()
    assert services.market.get_security.call_args.kwargs["range_"] == "1y"
    assert data["name"] == "Apple Inc."
    assert data["week52_high"] == 260.0
    assert data["history_close"] == [200.0, 210.0]
    assert data["history_ts"] == [1, 2]
    assert data["range"] == "1y"
    assert data["previous_close"] == 208.0  # daily, not range start
    assert round(data["change_pct"], 3) == round(2 / 208 * 100, 3)
    assert round(data["range_change_pct"], 3) == 5.0  # 200 -> 210 over 1y


def test_security_endpoint_404_for_unknown_symbol(api, services):
    services.market.get_security.return_value = None
    resp = api.get("/api/security/NOPE")
    assert resp.status_code == 404


def test_facts_endpoint_maps_ticker_to_metrics(api, services):
    from edgar13f.fundamentals import FiscalYear

    services.fundamentals.ticker_to_cik.return_value = "320193"
    services.fundamentals.company_name.return_value = "Apple Inc."
    services.fundamentals.annual_metrics.return_value = [
        FiscalYear(fiscal_year=2025, end_date="2025-09-27",
                   revenue=416e9, net_income=112e9, eps_diluted=7.46)
    ]
    data = api.get("/api/facts/AAPL").get_json()
    assert data["company"] == "Apple Inc."
    assert data["fiscal_years"][0]["fiscal_year"] == 2025
    assert data["fiscal_years"][0]["revenue"] == 416e9

    services.fundamentals.ticker_to_cik.return_value = None
    assert api.get("/api/facts/NOPE").status_code == 404


def test_holders_endpoint_finds_managers_holding_the_symbol(api, services):
    filing = _filing("0000000000-26-000001", date(2026, 3, 31))
    services.edgar.list_13f_filings.return_value = [filing]
    services.edgar.get_information_table.return_value = [
        _holding("APPLE INC", "037833100", 1000, 10),
        _holding("OTHER CO", "111111111", 500, 5),
    ]
    services.resolver.resolve.return_value = {
        "037833100": "AAPL", "111111111": "OTHR"
    }
    data = api.get("/api/holders/aapl").get_json()
    assert data["symbol"] == "AAPL"
    assert len(data["holders"]) == len(data["tracked_managers"])
    top = data["holders"][0]
    assert top["issuer"] == "APPLE INC"
    assert round(top["weight_pct"], 2) == round(1000 / 1500 * 100, 2)


def test_quotes_endpoint_returns_watchlist_rows(api, services):
    services.market.get_quotes.return_value = {
        "AAPL": Quote(symbol="AAPL", price=210.0, previous_close=200.0,
                      sparkline=[1.0, 2.0])
    }
    data = api.get("/api/quotes?symbols=AAPL,MISSING").get_json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["sparkline"] == [1.0, 2.0]


def test_markets_endpoint_groups_by_section(api, services):
    services.market.get_quotes.return_value = {
        "^GSPC": Quote(symbol="^GSPC", price=6100.0, previous_close=6000.0)
    }
    data = api.get("/api/markets").get_json()
    sections = {s["section"]: s["rows"] for s in data}
    assert "AMERICAS" in sections
    # Crypto deliberately is NOT part of the stocks view - it lives on the
    # MKTS screen's CRYPTO toggle, served by /api/crypto (CoinGecko).
    assert "CRYPTO" not in sections
    assert sections["AMERICAS"][0]["label"] == "S&P 500"


def test_events_endpoint_combines_earnings_and_meetings(api, services):
    from edgar13f.events import EarningsInfo

    services.events.get_earnings_info.return_value = EarningsInfo(
        symbol="AAPL", next_earnings_date="2026-07-30",
        analyst_recommendation="buy", strong_buy=10, buy=5, hold=3, sell=1, strong_sell=0,
    )
    services.fundamentals.ticker_to_cik.return_value = "320193"
    services.edgar.get_submissions.return_value = {
        "filings": {"recent": {
            "form": ["DEF 14A"], "filingDate": ["2026-03-15"],
            "accessionNumber": ["a1"], "primaryDocument": ["d1.htm"],
        }}
    }
    data = api.get("/api/events/AAPL").get_json()
    assert data["next_earnings_date"] == "2026-07-30"
    assert data["analyst_recommendation"] == "buy"
    assert len(data["shareholder_meetings"]) == 1


def test_events_endpoint_degrades_when_earnings_unavailable(api, services):
    services.events.get_earnings_info.return_value = None
    services.fundamentals.ticker_to_cik.return_value = None
    data = api.get("/api/events/UNKNOWN").get_json()
    assert data["next_earnings_date"] is None
    assert data["shareholder_meetings"] == []


def test_fed_events_endpoint(api, monkeypatch):
    from edgar13f import views
    from edgar13f.news import NewsItem as NI

    monkeypatch.setattr(
        views, "get_fed_events",
        lambda limit=20: [NI(title="FOMC holds rates", link="https://fed.gov/a", source="Fed Press")],
    )
    data = api.get("/api/fed-events").get_json()
    assert data[0]["title"] == "FOMC holds rates"


def test_macro_endpoint_reports_fred_availability(api, monkeypatch):
    from edgar13f import macro as macro_mod

    monkeypatch.setattr(macro_mod, "get_treasury_yield_curve", lambda: {"date": "2026-07-03", "curve": []})
    monkeypatch.setattr(macro_mod, "get_bls_series", lambda ids: {})
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    data = api.get("/api/macro").get_json()
    assert data["treasury_yield_curve"]["date"] == "2026-07-03"
    assert data["fred_available"] is False


def test_screener_endpoint_filters_by_pe(api, services):
    from edgar13f.market import Quote

    services.market.get_quote.return_value = Quote(symbol="AAPL", price=200.0)
    services.fundamentals.ticker_to_cik.return_value = "320193"
    # One companyfacts payload serves both metrics and shares outstanding.
    services.fundamentals.get_company_facts.return_value = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [
                    {"form": "10-K", "fp": "FY", "fy": 2025,
                     "start": "2024-10-01", "end": "2025-09-27",
                     "filed": "2025-11-01", "val": 400.0},
                ]}},
                "NetIncomeLoss": {"units": {"USD": [
                    {"form": "10-K", "fp": "FY", "fy": 2025,
                     "start": "2024-10-01", "end": "2025-09-27",
                     "filed": "2025-11-01", "val": 100.0},
                ]}},
                "EarningsPerShareDiluted": {"units": {"USD/shares": [
                    {"form": "10-K", "fp": "FY", "fy": 2025,
                     "start": "2024-10-01", "end": "2025-09-27",
                     "filed": "2025-11-01", "val": 10.0},  # P/E = 200/10 = 20
                ]}},
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {"units": {"shares": [
                    {"end": "2025-10-15", "val": 16.0},
                ]}},
            },
        }
    }

    ok = api.get("/api/screener?universe=AAPL&pe_ratio_max=25").get_json()
    assert ok["matched"] == 1
    assert ok["rows"][0]["pe_ratio"] == 20.0
    assert ok["rows"][0]["market_cap"] == 3200.0  # 200 * 16

    rejected = api.get("/api/screener?universe=AAPL&pe_ratio_max=10").get_json()
    assert rejected["matched"] == 0


def test_options_endpoint_returns_chain(api, services):
    from edgar13f.options import OptionChain, OptionContract

    services.options.get_option_chain.return_value = OptionChain(
        symbol="AAPL", underlying_price=210.0, expiration_dates=["2026-08-21"],
        selected_expiration="2026-08-21",
        calls=[OptionContract("AAPL260821C00200000", 200.0, 15.0, 14.8, 15.2, 100, 500, 0.3, True)],
        puts=[],
    )
    data = api.get("/api/options/AAPL").get_json()
    assert data["calls"][0]["strike"] == 200.0


def test_options_endpoint_404_when_unavailable(api, services):
    services.options.get_option_chain.return_value = None
    resp = api.get("/api/options/NOPE")
    assert resp.status_code == 404


def test_risk_endpoint_computes_portfolio_metrics(api, services):
    from edgar13f.market import Quote

    def fake_get_security(symbol, range_="1y"):
        prices = {"AAPL": 108.0, "MSFT": 210.0}
        histories = {"AAPL": [100, 102, 104, 106, 108], "MSFT": [200, 198, 202, 204, 210]}
        return Quote(symbol=symbol, price=prices[symbol], sparkline=histories[symbol])

    services.market.get_security.side_effect = fake_get_security
    resp = api.post(
        "/api/risk",
        json={"holdings": [{"symbol": "AAPL", "shares": 8}, {"symbol": "MSFT", "shares": 1}]},
    )
    data = resp.get_json()
    assert len(data["positions"]) == 2
    assert "sharpe_ratio" in data


def test_news_endpoint_routes_symbols_to_ticker_news(api, services):
    services.news.get_ticker_news.return_value = [
        NewsItem(title="Apple story", link="https://x/a", source="Yahoo Finance",
                 symbol="AAPL")
    ]
    data = api.get("/api/news?symbols=AAPL,MSFT").get_json()
    services.news.get_ticker_news.assert_called_once()
    assert services.news.get_ticker_news.call_args[0][0] == ["AAPL", "MSFT"]
    assert data[0]["title"] == "Apple story"

    services.news.get_market_news.return_value = []
    api.get("/api/news")
    services.news.get_market_news.assert_called_once()


def test_insiders_endpoint_parses_form4s_and_summarizes(api, services):
    from tests.test_form4 import FILING, SAMPLE_FORM4_XML

    services.fundamentals.ticker_to_cik.return_value = "0000320193"
    services.fundamentals.company_name.return_value = "Apple Inc."
    services.edgar.list_filings.return_value = [FILING]
    services.edgar._get.return_value.content = SAMPLE_FORM4_XML

    data = api.get("/api/insiders/AAPL").get_json()
    assert data["symbol"] == "AAPL"
    assert data["company"] == "Apple Inc."
    assert data["filings_scanned"] == 1
    assert len(data["transactions"]) == 2  # derivative RSU row excluded
    # No open-market P/S rows in this filing - vest + withholding only.
    assert data["summary"]["open_market_purchases"] == 0
    assert data["summary"]["open_market_sales"] == 0
    codes = {t["code"] for t in data["transactions"]}
    assert codes == {"M", "F"}
    assert data["transactions"][0]["insider"] == "Newstead Jennifer"


def test_insiders_endpoint_404_for_unknown_ticker(api, services):
    services.fundamentals.ticker_to_cik.return_value = None
    resp = api.get("/api/insiders/NOPE")
    assert resp.status_code == 404


def test_position_history_walks_quarters_chronologically(api, services):
    current = _filing("0000000000-26-000002", date(2026, 3, 31))
    prior = _filing("0000000000-25-000001", date(2025, 12, 31))
    services.edgar.list_13f_filings.return_value = [current, prior]
    services.edgar.pad_cik.return_value = "0001067983"
    services.edgar.get_information_table.side_effect = lambda f: (
        # AAPL split across two entries in the prior filing (real pattern)
        [_holding("APPLE INC", "037833100", 600, 6),
         _holding("APPLE INC", "037833100", 400, 4),
         _holding("OTHER CO", "111111111", 1000, 10)]
        if f is prior
        else [_holding("APPLE INC", "037833100", 500, 5),
              _holding("OTHER CO", "111111111", 1500, 15)]
    )
    services.resolver.resolve.return_value = {
        "037833100": "AAPL", "111111111": "OTHR",
    }

    data = api.get("/api/position-history/buffett/AAPL?quarters=4").get_json()
    assert data["issuer"] == "APPLE INC"
    assert data["cusips"] == ["037833100"]
    periods = [q["period_of_report"] for q in data["quarters"]]
    assert periods == ["2025-12-31", "2026-03-31"]  # oldest first
    old, new = data["quarters"]
    assert old["shares"] == 10  # aggregated across the two entries
    assert old["value_usd"] == 1000
    assert old["weight_pct"] == 50.0
    assert new["shares"] == 5
    assert new["held"] is True


def test_position_history_name_fallback_and_404(api, services):
    f = _filing("0000000000-26-000002", date(2026, 3, 31))
    services.edgar.list_13f_filings.return_value = [f]
    services.edgar.pad_cik.return_value = "0001067983"
    services.edgar.get_information_table.return_value = [
        _holding("CHUBB LIMITED", "H1467J104", 700, 7)
    ]
    # OpenFIGI can't map it keylessly - ticker resolution comes back empty.
    services.resolver.resolve.return_value = {"H1467J104": None}

    data = api.get("/api/position-history/buffett/chubb").get_json()
    assert data["cusips"] == ["H1467J104"]
    assert data["quarters"][0]["shares"] == 7

    resp = api.get("/api/position-history/buffett/ZZZZ")
    assert resp.status_code == 404


def test_portfolio_name_fallback_fills_openfigi_misses(api, services):
    services.edgar.list_13f_filings.return_value = [
        _filing("0000000000-26-000001", date(2026, 3, 31))
    ]
    services.edgar.get_information_table.return_value = [
        _holding("CHUBB LIMITED", "H1467J104", 700, 7),
    ]
    # OpenFIGI keyless tier can't map Chubb's CUSIP (seen live).
    services.resolver.resolve.return_value = {"H1467J104": None}
    services.fundamentals.name_to_ticker.return_value = "CB"
    services.market.get_quotes.return_value = {
        "CB": Quote(symbol="CB", price=280.0, previous_close=275.0,
                    currency="USD", sparkline=[275.0, 280.0])
    }

    data = api.get("/api/portfolio/buffett").get_json()
    row = data["positions"][0]
    assert row["ticker"] == "CB"
    assert row["price"] == 280.0
    # The learned mapping is persisted so the fallback runs once ever.
    services.resolver.learn.assert_called_once_with("H1467J104", "CB")
