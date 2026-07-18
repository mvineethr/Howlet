"""Offline tests for CUSIP -> ticker resolution via OpenFIGI (mocked HTTP)."""

from __future__ import annotations

import json

import responses

from edgar.tickers import OPENFIGI_URL, CusipTickerResolver


@responses.activate
def test_resolve_maps_cusips_and_normalizes_share_class_slash(tmp_path):
    responses.post(
        OPENFIGI_URL,
        json=[
            {"data": [{"ticker": "AAPL", "exchCode": "US"}]},
            {"data": [{"ticker": "BRK/B", "exchCode": "US"}]},
            {"error": "No identifier found."},
        ],
    )
    resolver = CusipTickerResolver(cache_dir=tmp_path)
    mapped = resolver.resolve(["037833100", "084670702", "999999999"])

    assert mapped["037833100"] == "AAPL"
    # OpenFIGI writes BRK/B; Yahoo (our quote source) wants BRK-B.
    assert mapped["084670702"] == "BRK-B"
    assert mapped["999999999"] is None


@responses.activate
def test_resolve_prefers_us_composite_listing(tmp_path):
    # Chevron's CUSIP really does list a stale "CHV" entry before the US
    # composite "CVX" one - found running the dashboard live.
    responses.post(
        OPENFIGI_URL,
        json=[
            {
                "data": [
                    {"ticker": "CHV", "exchCode": "UN"},
                    {"ticker": "CVX", "exchCode": "US"},
                ]
            }
        ],
    )
    resolver = CusipTickerResolver(cache_dir=tmp_path)
    assert resolver.resolve(["166764100"]) == {"166764100": "CVX"}


@responses.activate
def test_resolve_uses_disk_cache_and_never_reasks(tmp_path):
    responses.post(OPENFIGI_URL, json=[{"data": [{"ticker": "AAPL"}]}])
    resolver = CusipTickerResolver(cache_dir=tmp_path)
    assert resolver.resolve(["037833100"]) == {"037833100": "AAPL"}
    assert len(responses.calls) == 1

    # Fresh resolver instance -> should hit the disk cache, not the network.
    resolver2 = CusipTickerResolver(cache_dir=tmp_path)
    assert resolver2.resolve(["037833100"]) == {"037833100": "AAPL"}
    assert len(responses.calls) == 1

    cached = json.loads((tmp_path / "cusip_tickers.json").read_text())
    assert cached == {"037833100": "AAPL"}


@responses.activate
def test_resolve_survives_network_failure_without_caching_bad_answers(tmp_path):
    responses.post(OPENFIGI_URL, status=500, json={})
    resolver = CusipTickerResolver(cache_dir=tmp_path)
    mapped = resolver.resolve(["037833100"])

    assert mapped == {"037833100": None}
    # Failure must NOT be persisted as "no ticker" - retry next run.
    assert not (tmp_path / "cusip_tickers.json").exists()


@responses.activate
def test_resolve_batches_at_keyless_limit_of_five(tmp_path):
    cusips = [f"00000000{i}" for i in range(7)]  # 7 -> batches of 5 + 2
    responses.post(OPENFIGI_URL, json=[{"data": [{"ticker": f"T{i}"}]} for i in range(5)])
    responses.post(OPENFIGI_URL, json=[{"data": [{"ticker": f"T{i}"}]} for i in range(5, 7)])

    resolver = CusipTickerResolver(cache_dir=tmp_path)
    resolver._last_request_at = 0.0
    # Avoid the real 3s inter-batch throttle in tests.
    import edgar.tickers as tickers_mod

    original = tickers_mod._MIN_INTERVAL_SECONDS
    tickers_mod._MIN_INTERVAL_SECONDS = 0.0
    try:
        mapped = resolver.resolve(cusips)
    finally:
        tickers_mod._MIN_INTERVAL_SECONDS = original

    assert len(responses.calls) == 2
    assert json.loads(responses.calls[0].request.body) == [
        {"idType": "ID_CUSIP", "idValue": c} for c in cusips[:5]
    ]
    assert mapped[cusips[6]] == "T6"
