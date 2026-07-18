# Skill: Know the real key before you group, diff, or dedupe

## When to use
Any feature that compares, ranks, joins, or deduplicates rows: Q/Q diffs,
consensus across managers, holders lookups, screener joins, news merging.

## Procedure
1. Before writing any comparison, answer in writing: what is the true
   identity key of a row in this dataset? For 13F holdings it is the
   **CUSIP**, not the issuer name, not the ticker.
2. Check whether one filing can contain multiple rows with the same key.
   In 13F: YES — Berkshire's own filing lists AAPL across 5 separate
   infoTable entries. So the first step of any cross-filing operation is
   to aggregate by key WITHIN each filing (`diff.py::_aggregate_by_cusip`
   is the reference implementation — reuse it, don't re-derive it).
3. Check the opposite trap: rows that LOOK like duplicates but are
   distinct keys. Alphabet appears as GOOGL and GOOG, Lennar as LEN and
   LEN.B — different CUSIPs for different share classes. Two rows is
   CORRECT output. Do not "fix" it.
4. When mapping keys across systems (CUSIP → ticker), never take the first
   match. OpenFIGI returns listings in arbitrary order; prefer
   `exchCode == "US"`, and normalize class notation for the target system
   (BRK/B → BRK-B for Yahoo).
5. Write one test for the multi-row-same-key case and one asserting the
   distinct-classes case produces separate rows.

## Rules I was following
- Aggregation comes BEFORE comparison, always. Diffing unaggregated
  filings produces phantom NEW/SOLD rows for every internal split.
- "Looks like a duplicate" is a hypothesis, not a finding. Check the keys.
  The GOOGL/GOOG double row survived review only because someone verified
  the CUSIPs differ; HANDOVER explicitly flags it as "worth remembering if
  it looks surprising later."
- A cross-system key mapping needs a preference rule, not a `[0]`. First
  results are ordered by the vendor's convenience, not yours.

## Worked example (this project)
`diff.py::diff_holdings` (2026-06-30). The naive design — dict prior
filing by CUSIP, dict current filing by CUSIP, compare — collapses
silently when a filing lists one CUSIP five times: a plain dict keeps
only the last entry, understating Berkshire's AAPL position by whatever
the other four entries held. The shipped design aggregates by CUSIP
within each filing first (summing shares and value), then classifies each
CUSIP as NEW / SOLD / INCREASED / DECREASED / UNCHANGED. Live run
`edgar diff buffett` (Q4 2025 → Q1 2026) then surfaced GOOGL and GOOG
as two rows — investigated, confirmed as separate CUSIPs, kept.

The mapping half: Chevron's CUSIP returned stale "CHV" as OpenFIGI's
first listing; Yahoo has no CHV quote, so the portfolio row rendered
priceless. `_extract_tickers` now prefers the US composite listing
("CVX"), with a regression test.

## Anti-patterns
- `{h.cusip: h for h in holdings}` on a raw filing — silently drops
  multi-entry positions.
- Deduping news or holdings by display name. Names vary in case,
  punctuation, and suffixes; keys don't.
- "Fixing" correct multi-class rows because a user or reviewer eyeballs
  them as duplicates. Verify the key first; if keys differ, the rows stay.
