"""Tests for the crypto market client (CoinGecko + Coinpaprika fallback)."""

from __future__ import annotations

import responses

from edgar13f.crypto import COINGECKO_URL, COINPAPRIKA_URL, CryptoClient

# Trimmed from live responses captured 2026-07-17.
COINGECKO_JSON = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 64132,
        "market_cap": 1286366720245,
        "market_cap_rank": 1,
        "total_volume": 28499852020,
        "high_24h": 64286,
        "low_24h": 62528,
        "price_change_percentage_24h": -0.0002,
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "current_price": 3200.5,
        "market_cap": 386366720245,
        "market_cap_rank": 2,
        "total_volume": 8499852020,
        "high_24h": 3250.0,
        "low_24h": 3100.0,
        "price_change_percentage_24h": 1.25,
    },
]

COINPAPRIKA_JSON = [
    {
        "id": "eth-ethereum",
        "name": "Ethereum",
        "symbol": "ETH",
        "rank": 2,
        "quotes": {
            "USD": {
                "price": 3199.0,
                "volume_24h": 8400000000,
                "market_cap": 386000000000,
                "percent_change_24h": 1.2,
            }
        },
    },
    {
        "id": "btc-bitcoin",
        "name": "Bitcoin",
        "symbol": "BTC",
        "rank": 1,
        "quotes": {
            "USD": {
                "price": 64121.5,
                "volume_24h": 24973665833,
                "market_cap": 1286128046707,
                "percent_change_24h": 0.01,
            }
        },
    },
]


@responses.activate
def test_coingecko_is_primary():
    responses.get(COINGECKO_URL, json=COINGECKO_JSON)
    source, rows = CryptoClient().get_markets(limit=10)
    assert source == "coingecko"
    assert rows[0]["symbol"] == "BTC"  # normalized to upper case
    assert rows[0]["price"] == 64132
    assert rows[0]["market_cap"] == 1286366720245
    assert rows[0]["high_24h"] == 64286


@responses.activate
def test_falls_back_to_coinpaprika_on_coingecko_429():
    responses.get(COINGECKO_URL, status=429)
    responses.get(COINPAPRIKA_URL, json=COINPAPRIKA_JSON)
    source, rows = CryptoClient().get_markets(limit=10)
    assert source == "coinpaprika"
    # Coinpaprika's ordering isn't guaranteed - rows come back rank-sorted.
    assert [r["rank"] for r in rows] == [1, 2]
    assert rows[0]["symbol"] == "BTC"
    assert rows[0]["price"] == 64121.5
    assert rows[0]["high_24h"] is None  # coinpaprika doesn't report it


@responses.activate
def test_both_down_degrades_to_empty():
    responses.get(COINGECKO_URL, status=500)
    responses.get(COINPAPRIKA_URL, status=500)
    source, rows = CryptoClient().get_markets()
    assert (source, rows) == ("", [])


@responses.activate
def test_ttl_cache_prevents_repeat_fetches():
    responses.get(COINGECKO_URL, json=COINGECKO_JSON)
    client = CryptoClient()
    client.get_markets(limit=2)
    client.get_markets(limit=2)
    assert len(responses.calls) == 1  # second call served from cache
