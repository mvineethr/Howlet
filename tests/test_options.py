"""Tests for options-chain parsing (auth session mocked, not re-tested here)."""

from __future__ import annotations

from unittest.mock import MagicMock

from edgar.options import OptionsClient


def _fake_resp(payload: dict):
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


def _chain_payload():
    return {
        "optionChain": {
            "result": [
                {
                    "underlyingSymbol": "AAPL",
                    "expirationDates": [1783296000, 1785456000],
                    "quote": {"regularMarketPrice": 210.5},
                    "options": [
                        {
                            "expirationDate": 1783296000,
                            "calls": [
                                {
                                    "contractSymbol": "AAPL260101C00200000",
                                    "strike": 200.0,
                                    "lastPrice": 15.2,
                                    "bid": 15.0,
                                    "ask": 15.4,
                                    "volume": 1200,
                                    "openInterest": 5000,
                                    "impliedVolatility": 0.28,
                                    "inTheMoney": True,
                                }
                            ],
                            "puts": [
                                {
                                    "contractSymbol": "AAPL260101P00200000",
                                    "strike": 200.0,
                                    "lastPrice": 2.1,
                                    "bid": 2.0,
                                    "ask": 2.2,
                                    "volume": 400,
                                    "openInterest": 1000,
                                    "impliedVolatility": 0.3,
                                    "inTheMoney": False,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    }


def test_get_option_chain_parses_calls_and_puts():
    auth = MagicMock()
    auth.get.return_value = _fake_resp(_chain_payload())
    client = OptionsClient(auth=auth)

    chain = client.get_option_chain("AAPL")
    assert chain.symbol == "AAPL"
    assert chain.underlying_price == 210.5
    assert len(chain.expiration_dates) == 2
    assert chain.calls[0].strike == 200.0
    assert chain.calls[0].in_the_money is True
    assert chain.puts[0].implied_volatility == 0.3


def test_get_option_chain_returns_none_when_auth_fails():
    auth = MagicMock()
    auth.get.return_value = None
    assert OptionsClient(auth=auth).get_option_chain("AAPL") is None


def test_get_option_chain_returns_none_on_malformed_payload():
    auth = MagicMock()
    auth.get.return_value = _fake_resp({"unexpected": "shape"})
    assert OptionsClient(auth=auth).get_option_chain("AAPL") is None


def test_get_option_chain_passes_expiration_as_unix_timestamp():
    from datetime import date, datetime, timezone

    auth = MagicMock()
    auth.get.return_value = _fake_resp(_chain_payload())
    OptionsClient(auth=auth).get_option_chain("AAPL", expiration="2026-08-21")
    _, kwargs = auth.get.call_args
    expected = int(
        datetime.combine(date(2026, 8, 21), datetime.min.time(), tzinfo=timezone.utc)
        .timestamp()
    )
    assert kwargs["params"]["date"] == expected


def test_get_option_chain_rejects_bad_expiration_string():
    auth = MagicMock()
    result = OptionsClient(auth=auth).get_option_chain("AAPL", expiration="not-a-date")
    assert result is None
    auth.get.assert_not_called()
