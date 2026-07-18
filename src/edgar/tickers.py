"""CUSIP -> ticker resolution via OpenFIGI, with a persistent disk cache.

13F filings identify securities by CUSIP only; market data sources
(Yahoo Finance etc.) want tickers. OpenFIGI's mapping API bridges the two
and is free without an API key (just heavily rate-limited: small batches,
~25 requests/minute). An `OPENFIGI_API_KEY` env var unlocks bigger batches
but is never required - consistent with this project's no-key-ever rule.

CUSIP->ticker mappings essentially never change, so results (including
"no match") are cached to a JSON file and each CUSIP is only ever asked
about once per machine.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import requests

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Batch limits documented by OpenFIGI: 5 mapping jobs/request without a
# key, 100 with one.
_BATCH_SIZE_NO_KEY = 5
_BATCH_SIZE_WITH_KEY = 100

# Keyless tier is ~25 requests/minute; stay comfortably under it.
_MIN_INTERVAL_SECONDS = 3.0
_MAX_RETRIES = 2


def default_cache_dir() -> Path:
    return Path.home() / ".edgar"


class CusipTickerResolver:
    """Resolve CUSIPs to exchange tickers, remembering answers on disk."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.cache_path = self.cache_dir / "cusip_tickers.json"
        self.api_key = api_key or os.environ.get("OPENFIGI_API_KEY")
        self.session = session or requests.Session()
        self._last_request_at = 0.0
        self._cache: dict[str, Optional[str]] = self._load_cache()

    # ------------------------------------------------------------------ #
    # cache
    # ------------------------------------------------------------------ #

    def _load_cache(self) -> dict[str, Optional[str]]:
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {}

    def _save_cache(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=0, sort_keys=True)
        except OSError:
            # A dead cache means slower runs, not wrong answers.
            pass

    # ------------------------------------------------------------------ #
    # resolution
    # ------------------------------------------------------------------ #

    def resolve(self, cusips: list[str]) -> dict[str, Optional[str]]:
        """Map each CUSIP to a Yahoo-style ticker (or None if unmappable).

        Unknown CUSIPs are looked up in batches against OpenFIGI; anything
        already answered (even as "no match") comes from the disk cache.
        Network failures leave the affected CUSIPs unresolved (absent from
        the cache) so they'll be retried next run, and never raise.
        """
        unique = list(dict.fromkeys(c for c in cusips if c))
        missing = [c for c in unique if c not in self._cache]

        if missing:
            batch_size = (
                _BATCH_SIZE_WITH_KEY if self.api_key else _BATCH_SIZE_NO_KEY
            )
            resolved_any = False
            for start in range(0, len(missing), batch_size):
                batch = missing[start : start + batch_size]
                mapped = self._resolve_batch(batch)
                if mapped is None:
                    break  # network trouble - keep what we have, retry later
                self._cache.update(mapped)
                resolved_any = True
            if resolved_any:
                self._save_cache()

        return {c: self._cache.get(c) for c in unique}

    def learn(self, cusip: str, ticker: str) -> None:
        """Record a mapping found outside OpenFIGI (e.g. the SEC
        company_tickers.json name fallback), overwriting a cached
        "no match" so future runs skip the fallback entirely."""
        if not cusip or not ticker:
            return
        self._cache[cusip] = ticker
        self._save_cache()

    def _resolve_batch(self, cusips: list[str]) -> Optional[dict[str, Optional[str]]]:
        jobs = [{"idType": "ID_CUSIP", "idValue": c} for c in cusips]
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-OPENFIGI-APIKEY"] = self.api_key

        for attempt in range(_MAX_RETRIES + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < _MIN_INTERVAL_SECONDS:
                time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            try:
                resp = self.session.post(
                    OPENFIGI_URL, json=jobs, headers=headers, timeout=15
                )
            except requests.RequestException:
                return None
            self._last_request_at = time.monotonic()

            if resp.status_code == 429 and attempt < _MAX_RETRIES:
                retry_after = resp.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 10.0
                )
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                return None

            try:
                results = resp.json()
            except ValueError:
                return None
            return self._extract_tickers(cusips, results)

        return None

    @staticmethod
    def _extract_tickers(
        cusips: list[str], results: list[dict]
    ) -> dict[str, Optional[str]]:
        """Pair OpenFIGI's positional results back up with the input CUSIPs.

        A CUSIP can map to many listings; prefer the US composite
        (exchCode "US") since Yahoo quotes trade off US tickers - e.g.
        Chevron's CUSIP lists a stale "CHV" entry before the "US" CVX one.
        OpenFIGI tickers use "/" for share classes (BRK/B); Yahoo wants "-"
        (BRK-B), so normalize here since Yahoo is our quote source.
        """
        mapped: dict[str, Optional[str]] = {}
        for cusip, result in zip(cusips, results):
            ticker = None
            for entry in result.get("data") or []:
                raw = entry.get("ticker")
                if not raw:
                    continue
                if ticker is None:
                    ticker = raw
                if entry.get("exchCode") == "US":
                    ticker = raw
                    break
            mapped[cusip] = ticker.replace("/", "-") if ticker else None
        return mapped
