"""Tests for corporate events: earnings/analyst parsing (auth mocked),
shareholder meetings (submissions parsing), and Fed RSS aggregation."""

from __future__ import annotations

from unittest.mock import MagicMock

import responses

from edgar.client import EdgarClient
from edgar.events import (
    CorporateEventsClient,
    FED_PRESS_RSS,
    FED_SPEECHES_RSS,
    get_fed_events,
    get_shareholder_meetings,
)


def _fake_resp(payload: dict):
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


def _quote_summary_result():
    return {
        "calendarEvents": {
            "earnings": {"earningsDate": [{"raw": 1785441600, "fmt": "2026-07-30"}]}
        },
        "recommendationTrend": {
            "trend": [
                {"period": "0m", "strongBuy": 15, "buy": 2, "hold": 1, "sell": 0, "strongSell": 0},
            ]
        },
    }


def test_get_earnings_info_parses_date_and_recommendation():
    auth = MagicMock()
    auth.get.return_value = _fake_resp(
        {"quoteSummary": {"result": [_quote_summary_result()]}}
    )
    info = CorporateEventsClient(auth=auth).get_earnings_info("AAPL")
    assert info.next_earnings_date == "2026-07-30"
    assert info.strong_buy == 15
    assert info.analyst_recommendation == "strong buy"


def test_get_earnings_info_returns_none_when_auth_unavailable():
    auth = MagicMock()
    auth.get.return_value = None
    assert CorporateEventsClient(auth=auth).get_earnings_info("AAPL") is None


def test_summarize_recommendation_buckets():
    from edgar.events import _summarize_recommendation

    assert _summarize_recommendation({"strongBuy": 0, "buy": 0, "hold": 10, "sell": 0, "strongSell": 0}) == "hold"
    assert _summarize_recommendation({"strongBuy": 0, "buy": 0, "hold": 0, "sell": 10, "strongSell": 0}) == "sell"
    assert _summarize_recommendation({"strongBuy": 0, "buy": 0, "hold": 0, "sell": 0, "strongSell": 0}) is None


@responses.activate
def test_get_shareholder_meetings_filters_to_def_14a():
    responses.get(
        "https://data.sec.gov/submissions/CIK0001067983.json",
        json={
            "filings": {
                "recent": {
                    "form": ["10-K", "DEF 14A", "13F-HR", "DEF 14A"],
                    "filingDate": ["2026-02-01", "2026-03-15", "2026-05-15", "2025-03-10"],
                    "accessionNumber": ["a1", "a2", "a3", "a4"],
                    "primaryDocument": ["d1.htm", "d2.htm", "d3.htm", "d4.htm"],
                }
            }
        },
    )
    client = EdgarClient("Test Suite test@example.com")
    meetings = get_shareholder_meetings(client, "1067983", limit=5)
    assert [m["accession_number"] for m in meetings] == ["a2", "a4"]
    assert all(m["form"] == "DEF 14A" for m in meetings)


@responses.activate
def test_get_fed_events_merges_press_and_speeches():
    rss = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>FOMC statement</title><link>https://fed.gov/a</link>
      <pubDate>Mon, 06 Jul 2026 12:00:00 GMT</pubDate></item>
    </channel></rss>"""
    responses.get(FED_PRESS_RSS, body=rss)
    responses.get(FED_SPEECHES_RSS, status=503)  # one feed down - should degrade

    items = get_fed_events(limit=10)
    assert len(items) == 1
    assert items[0].source == "Fed Press"
