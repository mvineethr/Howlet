"""Offline tests for the Yahoo Finance market client (mocked HTTP)."""

from __future__ import annotations

import responses

from edgar.market import CHART_URL, YahooMarketClient

AAPL_URL = CHART_URL.format(symbol="AAPL")


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
