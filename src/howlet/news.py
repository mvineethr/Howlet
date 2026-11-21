"""Market and per-ticker news from free RSS feeds. No API key.

Sources (all public RSS, no auth):
  - Yahoo Finance: market-wide top stories + a per-ticker headline feed
  - CNBC: top news
  - MarketWatch: top stories
  - SEC: press releases (enforcement actions, rule changes)

Feeds occasionally break, move, or rate-limit; a broken feed is silently
skipped so the news panel degrades instead of failing. Items are de-duped
by link/title and sorted newest first.

Feed health: every fetch is recorded per feed (see `NewsClient.feed_health`),
so a dead feed is visible instead of indistinguishable from "no news
today" - the dashboard exposes it at `/api/news/health` and the CLI
prints it when a feed is down. Health is HTTP-level only: a feed that
answers 200 counts as ok even if its XML parses to zero items.
"""

from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests
from lxml import etree

# (source label, feed url) - all public RSS, no auth. A dead feed is a
# skipped feed, so adding sources here can only add coverage, not risk.
MARKET_FEEDS: list[tuple[str, str]] = [
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    (
        "CNBC",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml"
        "?partnerId=wrss01&id=100003114",
    ),
    (
        "CNBC Earnings",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml"
        "?partnerId=wrss01&id=15839135",
    ),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    (
        "Google News",
        "https://news.google.com/rss/headlines/section/topic/BUSINESS"
        "?hl=en-US&gl=US&ceid=US:en",
    ),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
    ("SEC", "https://www.sec.gov/news/pressreleases.rss"),
]

# Per-ticker feeds, tried for every requested symbol. Yahoo is the
# highest signal; Google News search casts the widest net; Seeking Alpha
# adds analysis pieces. Broken/blocked ones silently contribute nothing.
TICKER_FEED_URLS: list[tuple[str, str]] = [
    (
        "Yahoo Finance",
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        "?s={symbol}&region=US&lang=en-US",
    ),
    (
        "Google News",
        "https://news.google.com/rss/search?q={symbol}+stock"
        "&hl=en-US&gl=US&ceid=US:en",
    ),
    ("Seeking Alpha", "https://seekingalpha.com/api/sa/combined/{symbol}.xml"),
]

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_MIN_INTERVAL_SECONDS = 0.25


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: datetime | None = None
    symbol: str | None = None


class NewsClient:
    """Aggregate headlines from multiple free RSS feeds.

    Feed health is tracked per (kind, source): "ok" with a last-ok
    timestamp after any HTTP 200, "failed" with the last error after a
    request exception, "never" before the first check. See feed_health().
    """

    def __init__(self, user_agent: str | None = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or _DEFAULT_UA})
        self._last_request_at = 0.0
        self._feed_health: dict[str, dict] = {}
        for kind, feeds in (("market", MARKET_FEEDS), ("ticker", TICKER_FEED_URLS)):
            for source, _url in feeds:
                self._feed_health[f"{kind}:{source}"] = {
                    "source": source, "kind": kind, "status": "never",
                    "last_ok": None, "last_error": None,
                    "last_check": None, "items": None,
                }

    def feed_health(self) -> list[dict]:
        """Per-feed status, newest-checked first within each kind.

        Each entry: source, kind ("market"/"ticker"), status
        ("ok"/"failed"/"never"), last_ok / last_check (ISO timestamps or
        None), last_error (short message or None), items (headline count
        from the last successful fetch or None).
        """
        def _iso(dt):
            return dt.astimezone(timezone.utc).isoformat() if dt else None

        out = []
        for key in sorted(self._feed_health):
            h = self._feed_health[key]
            out.append({
                "feed": key, "source": h["source"], "kind": h["kind"],
                "status": h["status"], "last_ok": _iso(h["last_ok"]),
                "last_error": h["last_error"], "last_check": _iso(h["last_check"]),
                "items": h["items"],
            })
        return out

    def get_market_news(self, limit: int = 30) -> list[NewsItem]:
        """Merged market-wide headlines across all configured feeds."""
        items: list[NewsItem] = []
        for source, url in MARKET_FEEDS:
            items.extend(self._fetch_feed(source, url, feed_key=f"market:{source}"))
        return _dedupe_and_sort(items)[:limit]

    def get_ticker_news(self, symbols: list[str], limit: int = 30) -> list[NewsItem]:
        """Headlines specific to the given tickers, from every per-ticker feed."""
        items: list[NewsItem] = []
        for symbol in symbols:
            for source, url_template in TICKER_FEED_URLS:
                url = url_template.format(symbol=symbol)
                for item in self._fetch_feed(source, url, feed_key=f"ticker:{source}"):
                    item.symbol = symbol
                    items.append(item)
        return _dedupe_and_sort(items)[:limit]

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _record_feed(self, feed_key: str, ok: bool, error: str | None, items: int | None) -> None:
        now = datetime.now(timezone.utc)
        entry = self._feed_health.get(feed_key)
        if entry is None:  # pragma: no cover - keys are pre-seeded in __init__
            return
        entry["last_check"] = now
        if ok:
            entry["status"] = "ok"
            entry["last_ok"] = now
            entry["last_error"] = None
            entry["items"] = items
        else:
            entry["status"] = "failed"
            entry["last_error"] = error

    def _fetch_feed(self, source: str, url: str, feed_key: str | None = None) -> list[NewsItem]:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        try:
            resp = self.session.get(url, timeout=15)
            self._last_request_at = time.monotonic()
            resp.raise_for_status()
        except requests.RequestException as exc:
            self._record_feed(feed_key or f"market:{source}", ok=False,
                              error=f"{type(exc).__name__}: {exc}"[:160], items=None)
            return []
        items = _parse_rss(source, resp.content)
        self._record_feed(feed_key or f"market:{source}", ok=True, error=None, items=len(items))
        return items


def _parse_rss(source: str, content: bytes) -> list[NewsItem]:
    """Parse RSS 2.0 <item> entries. Malformed XML yields an empty list."""
    try:
        # recover=True tolerates the stray entities real-world feeds contain.
        root = etree.fromstring(content, parser=etree.XMLParser(recover=True))
    except (etree.XMLSyntaxError, ValueError):
        return []
    if root is None:
        return []

    items: list[NewsItem] = []
    for item in root.iter("item"):
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        if not title or not link:
            continue
        published = None
        pub_date = _child_text(item, "pubDate")
        if pub_date:
            with suppress(TypeError, ValueError):
                published = parsedate_to_datetime(pub_date)
        items.append(
            NewsItem(title=title.strip(), link=link.strip(), source=source,
                     published=published)
        )
    return items


def _child_text(element, tag: str) -> str | None:
    child = element.find(tag)
    return child.text if child is not None else None


def _dedupe_and_sort(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = item.link or item.title
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    def sort_key(item: NewsItem):
        if item.published is None:
            return 0.0
        try:
            return item.published.timestamp()
        except (OSError, OverflowError, ValueError):
            return 0.0

    unique.sort(key=sort_key, reverse=True)
    return unique
