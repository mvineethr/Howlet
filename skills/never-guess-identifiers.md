# Skill: Never guess an identifier — verify every CIK, ticker, URL, and symbol

## When to use
Adding anything to `presets.py`, mapping a CUSIP or ticker, writing a URL
for a feed/CDN/API, or hardcoding any symbol into `views.py`'s tape/market
sections. Identifiers LOOK guessable — that's the trap. A wrong one either
fails silently or, worse, returns someone else's data.

## Procedure
1. **Manager CIKs** (`presets.py`): resolve every candidate via
   `edgar search <name>` against live EDGAR before adding. EDGAR names
   are messy ("BERKSHIRE HATHAWAY INC" vs "Berkshire Hathaway Inc."), and
   search deliberately returns candidates for a human to disambiguate —
   pick the one whose recent filings actually include 13F-HR, then run
   `edgar holdings <cik>` once to confirm the portfolio looks like the
   manager you meant. CLAUDE.md's roadmap states this rule verbatim:
   "verify each CIK via `edgar search` before adding; never guess."
2. **Tickers from CUSIPs**: never take OpenFIGI's first listing — prefer
   `exchCode == "US"` (Chevron returns stale "CHV" before "CVX"). Then
   normalize class notation for the consumer: BRK/B → BRK-B for Yahoo.
3. **Yahoo symbols** (indices, FX, futures for MKTS/tape): each has vendor
   notation (`^GSPC`, `CL=F`, `EURUSD=X`, `DX-Y.NYB`). Before adding one,
   fetch a quote for it live; a wrong symbol degrades to a silent blank
   row (tier-2 behavior), so you won't get an error telling you.
4. **URLs** (RSS feeds, CDN scripts, API hosts): `curl -I` the exact URL
   and require a 200 before writing integration code (see
   silent-failure-patterns.md — two sessions were burned by
   plausible-but-wrong script URLs).
5. **Anything you looked up from memory or a doc**: memory and docs give
   you the *format*; only a live round-trip gives you the *value*.

## Rules I was following
- An identifier that produces a silent blank is worse than one that
  errors, and this codebase's degrade-gracefully design GUARANTEES blanks
  instead of errors for market data. Graceful degradation makes live
  pre-verification mandatory, because the runtime will never call out
  your typo.
- Verify at ADD time, once, and the identifier is trusted forever (CIKs
  and CUSIPs are stable). The cost is one command; the failure mode is a
  user watching the wrong manager's money.
- When two candidates look right (parent company vs. the filing entity),
  the disambiguator is behavior, not the name: the entity that files
  13F-HRs is the one you want.

## Worked example (this project)
The Chevron mapping bug (2026-07-06 part 1) is the canonical case: the
identifier pipeline itself (OpenFIGI, a real API, no guessing involved!)
returned a stale first listing, "CHV". Yahoo has no CHV quote, so the row
rendered priceless — silently, per the degrade rules. It surfaced only
because the live-verification pass eyeballed a real Buffett portfolio
row by row. The fix (`_extract_tickers` prefers `exchCode == "US"`) got a
regression test. If a real API's first answer can be wrong, a guessed
identifier has no chance — hence the standing verify-before-add rule for
presets, and Chubb (no keyless US mapping at all) rendering tickerless
by design rather than with a guessed ticker.

## Anti-patterns
- Adding five famous investors to `presets.py` from memory in one commit.
  Each unverified CIK is a potential wrong-portfolio bug wearing a
  trustworthy name.
- "Fixing" a blank quote row by guessing a different symbol variant until
  something renders. Verify which symbol is CORRECT, not which one
  returns data.
- Copying an identifier from a blog post or an LLM's memory (including
  yours). Both are stale by design; the live API is the only current
  source.
