"""Offline tests for the Yahoo Finance market client (mocked HTTP)."""

from __future__ import annotations

import responses

from howlet import market
from howlet.market import (
    CHART_URL,
    NASDAQ_HISTORY_URL,
    NASDAQ_INFO_URL,
    YahooMarketClient,
)

AAPL_URL = CHART_URL.format(symbol="AAPL")

# Shapes copied from live api.nasdaq.com responses (2026-10-19).
_NASDAQ_INFO = {
    "data": {
        "symbol": "BRK.B",
        "companyName": "Berkshire Hathaway Inc.",
        "exchange": "NYSE",
        "assetClass": "STOCKS",
        "primaryData": {
            "lastSalePrice": "$532.01",
            "netChange": "-2.00",
            "lastTradeTimestamp": "Oct 19, 2026 11:34 AM ET",
            "volume": "1,510,664.768107",
        },
        "keyStats": {
            "fiftyTwoWeekHighLow": {"value": "443.42 - 548.15"},
            "dayrange": {"value": "530.11 - 536.00"},
        },
    },
    "status": {"rCode": 200},
}
_NASDAQ_HIST = {
    "data": {
        "tradesTable": {
            "rows": [  # newest first, as Nasdaq sends it
                {"date": "10/16/2026", "close": "$534.01", "volume": "2,000",
                 "open": "$530", "high": "$535", "low": "$529"},
                {"date": "10/15/2026", "close": "$530.00", "volume": "1,000",
                 "open": "$528", "high": "$531", "low": "$527"},
            ]
        }
    }
}
_NASDAQ_MISSING = {"data": None, "status": {"rCode": 400}}


def _chart_payload(
    symbol="AAPL",
    price=210.5,
    previous_close=205.0,
    closes=(200.0, None, 204.0, 210.5),
):
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "symbol": symbol,
                        "currency": "USD",
                        "regularMarketPrice": price,
                        "chartPreviousClose": previous_close,
                        "regularMarketTime": 1750000000,
                        "longName": "Apple Inc.",
                        "fullExchangeName": "NasdaqGS",
                        "instrumentType": "EQUITY",
                        "regularMarketDayHigh": 212.0,
                        "regularMarketDayLow": 207.5,
                        "fiftyTwoWeekHigh": 260.0,
                        "fiftyTwoWeekLow": 164.0,
                        "regularMarketVolume": 54321000,
                    },
                    "timestamp": [1, 2, 3, 4],
                    "indicators": {
                        "quote": [
                            {
                                "close": list(closes),
                                "open": [199.0, None, 203.0, 209.0],
                                "high": [201.0, None, 205.0, 212.0],
                                "low": [198.0, None, 202.0, 207.5],
                                "volume": [1000, None, 2000, 3000],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


@responses.activate
def test_get_quote_parses_price_change_and_sparkline():
    responses.get(AAPL_URL, json=_chart_payload())
    quote = YahooMarketClient().get_quote("AAPL")

    assert quote is not None
    assert quote.symbol == "AAPL"
    assert quote.price == 210.5
    # With daily bars, previous close is the second-to-last bar - NOT
    # chartPreviousClose (that's the close before the range START, which
    # would make "change" the whole range's drift).
    assert quote.previous_close == 204.0
    assert quote.currency == "USD"
    assert quote.change == 6.5
    assert round(quote.change_pct, 4) == round(6.5 / 204.0 * 100, 4)
    # None gaps (market holidays etc.) are dropped from the sparkline,
    # and the timestamps stay aligned with the surviving closes.
    assert quote.sparkline == [200.0, 204.0, 210.5]
    assert quote.history_ts == [1, 3, 4]
    # Full OHLCV stays aligned after the None gap is dropped.
    assert quote.history_open == [199.0, 203.0, 209.0]
    assert quote.history_high == [201.0, 205.0, 212.0]
    assert quote.history_low == [198.0, 202.0, 207.5]
    assert quote.history_volume == [1000.0, 2000.0, 3000.0]
    # DES-style metadata from the chart meta block.
    assert quote.long_name == "Apple Inc."
    assert quote.exchange == "NasdaqGS"
    assert quote.instrument_type == "EQUITY"
    assert (quote.day_low, quote.day_high) == (207.5, 212.0)
    assert (quote.week52_low, quote.week52_high) == (164.0, 260.0)
    assert quote.volume == 54321000


@responses.activate
def test_get_quote_intraday_interval_keeps_meta_previous_close():
    responses.get(AAPL_URL, json=_chart_payload())
    quote = YahooMarketClient().get_quote("AAPL", range_="1d", interval="5m")
    # Non-daily bars: the second-to-last bar is minutes ago, so the meta
    # previous close stays authoritative.
    assert quote.previous_close == 205.0


@responses.activate
def test_get_quote_returns_none_on_http_error_not_raises():
    responses.get(AAPL_URL, status=404, json={"chart": {"result": None}})
    assert YahooMarketClient().get_quote("AAPL") is None


@responses.activate
def test_get_quote_returns_none_on_malformed_payload():
    responses.get(AAPL_URL, json={"unexpected": "shape"})
    assert YahooMarketClient().get_quote("AAPL") is None


@responses.activate
def test_get_security_picks_an_interval_that_matches_the_range():
    responses.get(AAPL_URL, json=_chart_payload())
    YahooMarketClient().get_security("AAPL", range_="5y")
    url = responses.calls[0].request.url
    assert "range=5y" in url and "interval=1wk" in url


@responses.activate
def test_get_quotes_skips_failed_symbols():
    responses.get(AAPL_URL, json=_chart_payload())
    responses.get(CHART_URL.format(symbol="BAD"), status=404, json={})
    quotes = YahooMarketClient().get_quotes(["AAPL", "BAD"])
    assert set(quotes) == {"AAPL"}


BRK_INFO_URL = NASDAQ_INFO_URL.format(symbol="BRK.B")
BRK_HIST_URL = NASDAQ_HISTORY_URL.format(symbol="BRK.B")


@responses.activate
def test_yahoo_failure_falls_back_to_nasdaq():
    responses.get(CHART_URL.format(symbol="BRK-B"), status=404, json={})
    responses.get(BRK_INFO_URL, json=_NASDAQ_INFO)
    responses.get(BRK_HIST_URL, json=_NASDAQ_HIST)
    quote = YahooMarketClient().get_quote("BRK-B")

    assert quote is not None
    assert quote.symbol == "BRK-B"  # caller's spelling, not Nasdaq's BRK.B
    assert quote.price == 532.01
    assert quote.previous_close == 534.01  # price - netChange
    # Oldest first, with today's live bar appended like Yahoo's series.
    assert quote.sparkline == [530.0, 534.01, 532.01]
    assert len(quote.history_ts) == 3 and quote.history_ts == sorted(quote.history_ts)
    assert quote.history_volume == [1000.0, 2000.0, 1510664.768107]
    assert (quote.week52_low, quote.week52_high) == (443.42, 548.15)
    assert (quote.day_low, quote.day_high) == (530.11, 536.0)
    assert quote.long_name == "Berkshire Hathaway Inc."


@responses.activate
def test_nasdaq_fallback_retries_etf_asset_class():
    responses.get(CHART_URL.format(symbol="SPY"), status=404, json={})
    info_url = NASDAQ_INFO_URL.format(symbol="SPY")
    stocks = responses.matchers.query_param_matcher({"assetclass": "stocks"})
    etf = responses.matchers.query_param_matcher({"assetclass": "etf"})
    responses.get(info_url, json=_NASDAQ_MISSING, match=[stocks])
    responses.get(info_url, json=_NASDAQ_INFO, match=[etf])
    responses.get(NASDAQ_HISTORY_URL.format(symbol="SPY"), json=_NASDAQ_HIST)
    quote = YahooMarketClient().get_quote("SPY")
    assert quote is not None and quote.price == 532.01
    assert "assetclass=etf" in responses.calls[-1].request.url


@responses.activate
def test_no_nasdaq_fallback_for_indices_or_intraday():
    responses.get(CHART_URL.format(symbol="^GSPC"), status=404, json={})
    responses.get(AAPL_URL, status=404, json={})
    client = YahooMarketClient()
    assert client.get_quote("^GSPC") is None
    assert client.get_quote("AAPL", range_="1d", interval="5m") is None
    assert all("nasdaq" not in c.request.url for c in responses.calls)


@responses.activate
def test_fresh_quote_is_reused_without_refetch():
    responses.get(AAPL_URL, json=_chart_payload())
    client = YahooMarketClient()
    first = client.get_quote("AAPL")
    assert client.get_quote("AAPL") is first
    assert len(responses.calls) == 1


@responses.activate
def test_stale_quote_served_when_every_source_fails(monkeypatch):
    client = YahooMarketClient()
    responses.get(AAPL_URL, json=_chart_payload())
    first = client.get_quote("AAPL")

    monkeypatch.setattr(market, "_FRESH_SECONDS", 0.0)
    responses.replace(responses.GET, AAPL_URL, status=404, json={})
    # Nasdaq isn't registered, so it fails too (ConnectionError).
    assert client.get_quote("AAPL") is first
