# Skill: Cache policy follows the data's mutability, and never cache failure

## When to use
Adding any cache, choosing a cache key or TTL, or debugging stale/missing
data. Every cache in this project has a policy derived from ONE question:
when, if ever, can this data change?

## The existing caches and their reasoning (the pattern to copy)
All under `~/.edgar/` unless noted:

| Cache | Key | TTL | Why exactly that |
| --- | --- | --- | --- |
| `holdings/` | accession number | forever | A filed 13F is immutable. The accession number IDs one filing forever, so re-fetching is pure waste. |
| `cusip_tickers.json` | CUSIP | forever | A CUSIP's US listing effectively never changes; and the keyless OpenFIGI throttle (5 per 3s) makes first-resolve expensive, so amortize it once. |
| `screener_cache.json` | ticker + day | 1 day | Fundamentals move on filings but screener freshness only needs "today"; companyfacts responses are multi-MB, so daily is the right waste/freshness trade. |
| browser localStorage | n/a | user-owned | Watchlists, personal portfolio, layout — user preferences, never server data. |

## Procedure
1. Classify the data: **immutable** (filed documents — key by the immutable
   ID, cache forever), **slow-moving** (fundamentals — cache per day),
   **live** (quotes, news — don't disk-cache at all), or **user-owned**
   (client-side storage only).
2. Pick the key so that a new version of the data gets a NEW key. Accession
   number, not "latest filing for CIK" — the latter goes stale, the former
   can't.
3. Never write a failure into the cache. A network error resolving a CUSIP
   must leave no entry, so the next run retries. Caching a failure converts
   a transient outage into permanent data loss (`cusip_tickers.json`
   documents this rule explicitly: "network failures are NOT cached").
4. Distinguish "known-unmappable" from "failed-to-map" if you ever need to
   cache negatives: Chubb has no keyless OpenFIGI US mapping (a fact,
   cacheable in principle) vs. a timeout (an accident, never cacheable).
5. After adding a cache, verify BOTH paths live: cold (correct data, slower)
   and warm (same data, fast). A cache that's never hit and a cache that
   serves stale garbage look identical in offline tests.

## Rules I was following
- The cache exists to protect the throttles and the user's time, in that
  order (see be-a-good-citizen.md). If a cache would ever serve wrong data
  to save a request, the TTL is wrong.
- "Forever" is only legal when the KEY embeds immutability. Never cache
  "the answer to a query" forever; cache "the content of an immutable
  object" forever.
- User data (watchlist, portfolio) lives in the browser, not on the server.
  This is a privacy stance as much as an architecture one: the tool holds
  no user state server-side.

## Worked example (this project)
The manager-portfolio load path. First load of Buffett takes ~20s: fetch
the filing (SEC-throttled), then resolve ~29 CUSIPs through OpenFIGI's
keyless tier at 5-per-3s. Both results go to disk — holdings under the
accession number (immutable), tickers in the forever CUSIP map. Second
load is instant, verified live in the 2026-07-06 session ("subsequent
loads are instant thanks to both caches"). The one deliberate hole:
CUSIPs whose resolution FAILED (network) are absent from the map and
retried next run, while Chubb — genuinely unmappable keylessly — simply
renders tickerless/priceless by design each time, which is the honest
representation until the planned name-based fallback via SEC's
`company_tickers.json` lands (roadmap item #4).

## Anti-patterns
- Caching by mutable reference ("buffett/latest") instead of immutable ID.
- A TTL chosen by vibes ("an hour seems fine") instead of by asking when
  the data can change.
- Testing the cache only with mocks. The cold/warm live check is two runs
  of one command; do it.
