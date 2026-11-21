"""Tests for the Yahoo cookie+crumb auth workaround (mocked HTTP)."""

from __future__ import annotations

import responses

from howlet.yahoo_auth import YahooAuthSession


@responses.activate
def test_get_crumb_fetches_once_and_caches():
    responses.get("https://fc.yahoo.com", status=404)
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb", body="abc.123"
    )
    session = YahooAuthSession()
    assert session.get_crumb() == "abc.123"
    assert session.get_crumb() == "abc.123"
    # Only one crumb fetch despite two calls.
    crumb_calls = [
        c for c in responses.calls
        if "getcrumb" in c.request.url
    ]
    assert len(crumb_calls) == 1


@responses.activate
def test_get_crumb_returns_none_on_error_body():
    responses.get("https://fc.yahoo.com", status=404)
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        json={"finance": {"error": {"code": "Unauthorized"}}},
    )
    assert YahooAuthSession().get_crumb() is None


@responses.activate
def test_get_attaches_crumb_as_query_param():
    responses.get("https://fc.yahoo.com", status=404)
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb", body="thecrumb"
    )
    responses.get("https://example.com/data", json={"ok": True})

    session = YahooAuthSession()
    resp = session.get("https://example.com/data")
    assert resp is not None
    assert resp.json() == {"ok": True}
    data_call = next(c for c in responses.calls if "example.com" in c.request.url)
    assert "crumb=thecrumb" in data_call.request.url


@responses.activate
def test_get_returns_none_when_crumb_unavailable():
    responses.get("https://fc.yahoo.com", status=404)
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        json={"finance": {"error": {"code": "Invalid Cookie"}}},
    )
    assert YahooAuthSession().get("https://example.com/data") is None


@responses.activate
def test_get_refreshes_crumb_once_on_401_then_retries():
    responses.get("https://fc.yahoo.com", status=404)
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        body="stale", status=200,
    )
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        body="fresh", status=200,
    )
    responses.get("https://example.com/data", status=401, json={})
    responses.get("https://example.com/data", json={"ok": True})

    session = YahooAuthSession()
    resp = session.get("https://example.com/data")
    assert resp is not None
    assert resp.json() == {"ok": True}
    # Second data call should carry the refreshed crumb.
    data_calls = [c for c in responses.calls if "example.com" in c.request.url]
    assert len(data_calls) == 2
    assert "crumb=fresh" in data_calls[-1].request.url


# --- Phase 2: a failed crumb fetch is retried after a TTL (B4) ---

@responses.activate
def test_get_crumb_retries_after_failure_once_ttl_passes(monkeypatch):
    from howlet import yahoo_auth

    responses.get("https://fc.yahoo.com", status=404)
    # First fetch fails (error body), second succeeds.
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        json={"finance": {"error": {"code": "Unauthorized"}}},
    )
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        body="recovered",
    )
    # Retry immediately: the old boolean would never retry at all.
    monkeypatch.setattr(yahoo_auth, "_CRUMB_RETRY_SECONDS", 0.0)

    session = YahooAuthSession()
    assert session.get_crumb() is None  # first attempt fails
    assert session.get_crumb() == "recovered"  # TTL aged out -> refetch
    crumb_calls = [
        c for c in responses.calls if "getcrumb" in c.request.url
    ]
    assert len(crumb_calls) == 2


@responses.activate
def test_get_crumb_does_not_refetch_within_retry_window(monkeypatch):
    from howlet import yahoo_auth

    responses.get("https://fc.yahoo.com", status=404)
    responses.get(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        json={"finance": {"error": {"code": "Unauthorized"}}},
    )
    # A huge window: the failure must not be retried yet.
    monkeypatch.setattr(yahoo_auth, "_CRUMB_RETRY_SECONDS", 3600.0)

    session = YahooAuthSession()
    assert session.get_crumb() is None
    assert session.get_crumb() is None
    crumb_calls = [
        c for c in responses.calls if "getcrumb" in c.request.url
    ]
    assert len(crumb_calls) == 1
