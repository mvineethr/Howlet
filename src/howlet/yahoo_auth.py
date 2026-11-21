"""Cookie+crumb auth for Yahoo Finance's "walled" endpoints.

The chart endpoint (`market.py`) needs no auth. But `quoteSummary` (earnings
dates, analyst recommendations) and the options-chain endpoint now reject
anonymous requests with "Invalid Crumb" / "Invalid Cookie". The fix (the
same one community tools like yfinance use) is:

  1. GET https://fc.yahoo.com - not itself useful, but Yahoo's edge sets a
     session cookie on the response regardless of its (404) status.
  2. GET https://query1.finance.yahoo.com/v1/test/getcrumb with that
     cookie attached - returns a short-lived crumb string.
  3. Attach the same cookie jar to every subsequent request, with the
     crumb as a `crumb=` query parameter.

This is unofficial and Yahoo could close it at any time (they've changed
this exact mechanism before) - every caller must treat a failure here as
"feature unavailable", never as fatal, matching this project's rule that
market-data failures degrade gracefully instead of breaking 13F views.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# How long to wait after a failed crumb fetch before trying again.
# A single transient Yahoo outage must not disable earnings/options
# for the process lifetime: the old `_attempted` boolean was set even
# on failure, and its only reset path - a 401 - was unreachable when
# no crumb existed (no request is ever made without one), so one
# outage at startup killed the feature until restart.
_CRUMB_RETRY_SECONDS = 60.0


class YahooAuthSession:
    """Lazily fetches and caches a cookie+crumb pair for one process."""

    def __init__(self, user_agent: str | None = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or _DEFAULT_UA})
        self._crumb: str | None = None
        # Monotonic timestamp of the last failed crumb fetch (None if
        # never failed). A failed fetch is retried once its age passes
        # _CRUMB_RETRY_SECONDS instead of never.
        self._failed_at: float | None = None

    def get_crumb(self) -> str | None:
        """The cached crumb, refetching after a failed attempt ages out."""
        if self._crumb is None:
            retry_due = self._failed_at is None or (
                time.monotonic() - self._failed_at >= _CRUMB_RETRY_SECONDS
            )
            if retry_due:
                self._crumb = self._fetch_crumb()
                if self._crumb is None:
                    self._failed_at = time.monotonic()
        return self._crumb

    def _fetch_crumb(self) -> str | None:
        try:
            self.session.get("https://fc.yahoo.com", timeout=10)
            resp = self.session.get(
                "https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10
            )
            crumb = resp.text.strip()
            if not crumb or "{" in crumb:  # error bodies are JSON, crumbs aren't
                return None
            return crumb
        except requests.RequestException:
            return None

    def get(self, url: str, params: dict | None = None, **kwargs) -> requests.Response | None:
        """GET with the crumb attached. Retries the crumb once on 401.

        Returns None (never raises) if auth can't be established at all -
        callers should treat that as "this feature is unavailable right
        now" and degrade, not crash.
        """
        crumb = self.get_crumb()
        if crumb is None:
            return None
        params = dict(params or {})
        params["crumb"] = crumb
        try:
            resp = self.session.get(url, params=params, timeout=15, **kwargs)
        except requests.RequestException:
            return None

        if resp.status_code == 401:
            # Crumb may have expired; refresh once and retry.
            self._crumb = None
            self._failed_at = None  # force an immediate refetch
            crumb = self.get_crumb()
            if crumb is None:
                return None
            params["crumb"] = crumb
            try:
                resp = self.session.get(url, params=params, timeout=15, **kwargs)
            except requests.RequestException:
                return None

        return resp if resp.status_code == 200 else None
