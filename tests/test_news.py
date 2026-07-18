"""Offline tests for the RSS news aggregation (mocked HTTP)."""

from __future__ import annotations

import responses

from edgar13f.news import MARKET_FEEDS, NewsClient, _parse_rss

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>feed</title>
{items}
</channel></rss>"""


def _item(title, link, pub_date="Mon, 06 Jul 2026 12:00:00 GMT"):
    return (
        f"<item><title>{title}</title><link>{link}</link>"
        f"<pubDate>{pub_date}</pubDate></item>"
    )


def test_parse_rss_extracts_items_and_dates():
    xml = RSS_TEMPLATE.format(
        items=_item("Markets rally", "https://example.com/a")
    ).encode()
    items = _parse_rss("TestSource", xml)
    assert len(items) == 1
    assert items[0].title == "Markets rally"
    assert items[0].link == "https://example.com/a"
    assert items[0].source == "TestSource"
    assert items[0].published is not None
    assert items[0].published.year == 2026


def test_parse_rss_tolerates_garbage():
    assert _parse_rss("X", b"this is not xml at all") == []
    assert _parse_rss("X", b"<rss><channel><item><title>no link</title></item></channel></rss>") == []


@responses.activate
def test_market_news_merges_feeds_dedupes_and_sorts_newest_first():
    first_url = MARKET_FEEDS[0][1]
    responses.get(
        first_url,
        body=RSS_TEMPLATE.format(
            items=_item("Older story", "https://example.com/old",
                        "Sun, 05 Jul 2026 09:00:00 GMT")
            + _item("Newer story", "https://example.com/new",
                    "Mon, 06 Jul 2026 09:00:00 GMT")
            + _item("Dup of newer", "https://example.com/new")
        ),
    )
    # Every other feed is down - the panel should degrade, not fail.
    for _, url in MARKET_FEEDS[1:]:
        responses.get(url, status=503)

    items = NewsClient().get_market_news()
    assert [i.title for i in items] == ["Newer story", "Older story"]


@responses.activate
def test_ticker_news_merges_all_per_ticker_feeds_and_tags_symbol():
    from edgar13f.news import TICKER_FEED_URLS

    # Yahoo and Google News respond; Seeking Alpha stays unmocked (a
    # connection error there must not break the merge).
    responses.get(
        TICKER_FEED_URLS[0][1].format(symbol="AAPL"),
        body=RSS_TEMPLATE.format(
            items=_item("Apple ships thing", "https://example.com/aapl")
        ),
    )
    responses.get(
        TICKER_FEED_URLS[1][1].format(symbol="AAPL"),
        body=RSS_TEMPLATE.format(
            items=_item("Apple coverage elsewhere", "https://example.com/gn")
        ),
    )
    items = NewsClient().get_ticker_news(["AAPL"])
    assert {i.title for i in items} == {"Apple ships thing", "Apple coverage elsewhere"}
    assert all(i.symbol == "AAPL" for i in items)
    assert {i.source for i in items} == {"Yahoo Finance", "Google News"}
