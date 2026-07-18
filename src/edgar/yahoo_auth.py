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

from typing import Optional

import requests

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class YahooAuthSession:
    """Lazily fetches and caches a cookie+crumb pair for one process."""

    def __init__(self, user_agent: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or _DEFAULT_UA})
        self._crumb: Optional[str] = None
        self._attempted = False

    def get_crumb(self) -> Optional[str]:
        """The cached crumb, fetching it once. None if the flow fails."""
        if self._crumb is None and not self._attempted:
            self._crumb = self._fetch_crumb()
            self._attempted = True
        return self._crumb

    def _fetch_crumb(self) -> Optional[str]:
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

    def get(self, url: str, params: Optional[dict] = None, **kwargs) -> Optional[requests.Response]:
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
            self._attempted = False
            crumb = self.get_crumb()
            if crumb is None:
                return None
            params["crumb"] = crumb
            try:
                resp = self.session.get(url, params=params, timeout=15, **kwargs)
            except requests.RequestException:
                return None

        return resp if resp.status_code == 200 else None
