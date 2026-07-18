---
name: failure-archaeology
description: Build and mine a project's incident chronicle so no settled battle is re-fought. Load when you land in an unfamiliar repo and need its history before touching code; when you're about to "fix" something that looks wrong but may be a documented non-bug; when an investigation ends and must be recorded (symptom, root cause, evidence, status); when you find a suspicious revert, dead branch, or a fix that seems to have been tried before; or when there is no git history and you must reconstruct what happened from docs alone.
---

# Failure Archaeology

Every debugging session a project survives produces knowledge that is more expensive
to re-derive than any feature: the symptom, the real root cause, the evidence, and
whether it was ever actually fixed. This skill is how to (a) MINE that history the
moment you land in a repo, and (b) MAINTAIN the chronicle so the next person — or
the next session of you — never re-fights a settled battle. The cost of not having
it is concrete: reverting to a "cleaner" API that is broken server-side, "fixing"
correct output that only looks like a duplicate-row bug, or re-debugging a 1000x
units error someone already paid a live session to understand.

---

## 1. The chronicle record format

Every closed (or abandoned) investigation becomes one record with exactly four
fields plus a status. Tables beat prose; one row per incident.

| Field | What goes in it | Bad version |
|---|---|---|
| **Symptom** | What was observed, verbatim if possible ("`ARRAY(0x55d6f0feff88)` in titles", "AAPL +10.18% on a flat day") | "search was broken" |
| **Root cause** | The mechanism, not the module ("SEC's atom feed stringifies Perl array refs server-side") | "bug in client.py" |
| **Evidence** | How you know: the live command run, the observed value, the discriminating fact ("Berkshire's reported total 263,095,703,570 only makes sense as $263B, not $263T") | "confirmed it" |
| **Status** | One of the five values below | "should be fine now" |

**Status vocabulary (use exactly these):**

| Status | Meaning | Obligation |
|---|---|---|
| `fixed+regression-tested` | Fixed, and a named test pins it | Name the test in the record |
| `fixed-untested` | Fixed and (usually) live-verified, but no regression test guards it | Say what the guard is (docstring, gotcha line) and why no test |
| `open` | Known, not fixed; may never have been exercised | Record the first command a future session should run |
| `won't-fix` | Deliberate; usually deferred-by-user or out of scope | Record WHO decided and why, so nobody re-pitches it |
| `superseded` | The whole component/approach was replaced, mooting the fix | Name the replacement and the reason |

**Where the chronicle lives — three layers, one fact per home:**

1. **The chronicle doc** (e.g. `HANDOVER.md`, `CHANGELOG-dev.md`, ADR log) — the
   full narrative record: symptom, investigation, dead ends, root cause, fix,
   verification values. Newest entry first. See docs-and-writing for the
   two-file (brief + chronicle) pattern and templates.
2. **The standing brief's gotcha list** (e.g. `CLAUDE.md`) — ONE line per incident,
   phrased as trap + rule ("atom search is broken server-side — parse the HTML
   table"). Only durable facts graduate here; the story stays in the chronicle.
3. **Regression test names** — the executable layer. A test named after the
   incident (`test_search_company_cik_parses_html_table`) is a chronicle entry
   that runs on every CI pass. Name tests after the trap, not the function.

A record isn't complete until it exists at every layer it qualifies for:
narrative in the chronicle, one line in the brief if the lesson is durable, and a
named test if the fix is testable.

---

## 2. History-mining runbook (do this BEFORE changing anything in a new repo)

### 2a. With git history

```bash
# The shape of the project's life: bursts, gaps, who, when
git log --oneline --graph --all | head -50

# Full history of the file you're about to change, following renames
git log --oneline --follow -- path/to/file.py

# Who last touched the exact lines you distrust, and in which commit
git blame -L 40,60 path/to/file.py

# "Pickaxe": every commit that ADDED or REMOVED this string — finds the
# commit that introduced a workaround, and the one that removed it
git log -S "chartPreviousClose" --oneline
git log -G "retry|backoff" --oneline          # regex variant

# Reverts are confessions: each one marks a fix that was tried and rejected
git log --oneline --grep="revert" -i
git log --oneline --grep="fix\|workaround\|hack" -i

# Stalled/abandoned branches: work someone walked away from — find out why
git branch -a --sort=-committerdate
git log main..some-stalled-branch --oneline

# What a suspicious commit actually changed
git show <sha> --stat
```

Read the commit that introduced any code you're about to delete. If its message
or diff shows it was a deliberate fix, you have found a chronicle entry that was
never written down — write it down (Section 3) before deciding anything.

### 2b. Without git history — the docs-only fallback

Repos exist that were never `git init`ed (the exemplar below is one: CI config
exists, has never run, and there are zero commits). Then documents are the ONLY
chronicle, and you mine them instead:

```bash
# 1. Find the chronicle candidates
ls *.md docs/ 2>/dev/null    # HANDOVER, CHANGELOG, NOTES, TODO, ADR, devlog

# 2. Sweep code and docs for incident markers
grep -rn -iE "gotcha|workaround|don't revert|do not revert|known issue|WRONG|CORRECT|regression" --include="*.md" --include="*.py" .
grep -rn -iE "TODO|FIXME|HACK|XXX" src/ | head -30

# 3. Comments that explain a non-obvious choice ARE chronicle entries
grep -rn -iE "because|instead of|deliberately|NOT " src/ --include="*.py" | grep "#" | head -40

# 4. Test names encode settled battles — read them as an incident index
grep -rn "def test_" tests/ | grep -iE "parses|degrades|retries|survives|not_html|prefers"
```

Then read the chronicle doc END TO END, newest first, and extract every incident
into the Section 1 table format before you touch code. In a docs-only repo this
table IS your safety net — there is no `git log -S` to catch you later.

### 2c. What you're mining FOR — the four questions

| Question | Why it matters |
|---|---|
| What looks broken but is CORRECT? | Documented non-bugs ("two rows here is CORRECT") are the #1 thing new arrivals wrongly "fix" |
| What was tried and rejected, and why? | So you don't re-try it (reverts, "replaced X because...") |
| What is `open` or untested? | So you don't assume it works, and know the first command to run |
| What is `won't-fix` and whose call was it? | So you don't re-pitch a user-deferred item as your idea |

---

## 3. The maintenance rule: no investigation ends without a record

**When an investigation ends — fixed, abandoned, or won't-fix — writing the
chronicle entry is part of "done."** Not optional, not later. (The session-close
mechanics — which file, which sections, test-count tracking — live in
docs-and-writing; this skill owns the record's content and status discipline.)

Checklist at investigation close:

- [ ] Chronicle entry written **while the pain is fresh** (same session — numbers
      and dead ends are gone by tomorrow), with all four fields.
- [ ] Status assigned from the five-value vocabulary. If `fixed+regression-tested`,
      the test name appears in the entry.
- [ ] If the lesson is durable, one trap+rule line added to the standing brief's
      gotcha list. Gotchas earn their place by cost — real paid-for lessons only,
      no hypotheticals.
- [ ] Evidence is falsifiable: date + command + observed value. "It works" can't
      be re-checked; "9-point curve for 2026-07-06, 10y 4.48%" can.
- [ ] Correct-but-surprising output recorded as CORRECT, with the reason, so a
      future maintainer doesn't "fix" it.
- [ ] Dead ends recorded too — a rejected fix with its rejection reason is worth
      as much as the accepted one.

---

## 4. Worked instance (edgar, mined 2026-07-07)

The exemplar repo (`D:\src\edgar` — a free SEC-EDGAR/market terminal; 13F is the
quarterly SEC filing where institutional managers disclose US long equity
holdings) was **never `git init`ed**. Its `HANDOVER.md` is the sole chronicle;
`CLAUDE.md` carries the gotcha layer; `tests/` carries the executable layer.
This table is Section 2b applied for real — every row extracted from
`HANDOVER.md` and verified against the code and tests:

| # | Symptom | Root cause | Evidence | Status |
|---|---|---|---|---|
| 1 | Company search returned `ARRAY(0x55d6f0feff88)` instead of company names | SEC's `output=atom` endpoint is broken **server-side** (stringified Perl array refs in `<entry title>`); offline mocks never caught it because the mock XML was hand-built correctly | First-ever live run (`edgar search berkshire`, 2026-06-30) vs green offline suite | `fixed+regression-tested` — parse the HTML results table instead; `test_search_company_cik_parses_html_table` (tests/test_client.py) uses a real anonymized HTML fixture |
| 2 | Portfolio totals 1000x too large; field labeled "$000s" | SEC's Jan-2023 amendment: 13F `<value>` is **whole dollars** post-2023 (was thousands before) | Berkshire's reported total 263,095,703,570 only makes sense as $263B, not $263T | `fixed-untested` — renamed `value_usd_thousands`→`value_usd` everywhere, live-verified ($263.10B); guard is the `Holding` docstring (src/edgar/models.py) + CLAUDE.md gotcha, no dedicated test (data-semantics rename) |
| 3 | Chevron rendered with ticker "CHV"; Yahoo has no CHV quote | OpenFIGI's first listing for a CUSIP isn't always the US ticker (stale "CHV" precedes US-composite "CVX") | Live dashboard render of Berkshire's portfolio, 2026-07-06 | `fixed+regression-tested` — prefer `exchCode == "US"`; `test_resolve_prefers_us_composite_listing` (tests/test_tickers.py) |
| 4 | AAPL showed "+10.18%" as a day change on a quiet day | Yahoo's `chartPreviousClose` is the close before the **range start**, not yesterday — "change" was actually the whole range's drift | 1-month-range quotes made the %CHG column show 1-month moves | `fixed+regression-tested` — daily bars use the second-to-last bar as previous close; `test_get_quote_parses_price_change_and_sparkline` + `test_get_quote_intraday_interval_keeps_meta_previous_close` (tests/test_market.py) |
| 5 | Yield-curve tests green, live curve empty `{}` | Treasury OData values nest under `<m:properties>` (metadata namespace); the parser AND its hand-built fixture **shared the same wrong assumption** (d: namespace) — mocks agreed with the code, not with reality | Live fetch returned nothing while the suite passed (2026-07-06) | `fixed+regression-tested` — rewrote with local-tag-name matching; fixture now copies the real feed (tests/test_macro.py); full curve verified live (10y 4.48%) |
| 6 | TradingView chart capped at 2 stacked indicators; more demanded a subscription | Paywall in the free widget — a proprietary dependency in an open-source, no-key project | User hit the cap live, 2026-07-07; also earlier: a wrong embed-script URL fails **silently** (no iframe, no console error) | `superseded` — TradingView ripped out entirely for vendored KLineChart (Apache-2.0, unlimited indicators, served from `/static/`, no CDN) |
| 7 | Widgets showed "Unexpected token '<'" under parallel load | SEC resets stale keep-alive connections (WinError 10054); `_get` only retried 429/5xx so `ConnectionError` propagated, and Flask returned an HTML 500 the frontend tried to parse as JSON | Dashboard widget grid's parallel calls, 2026-07-07 | `fixed+regression-tested` — twice over: `_get` retries `requests.ConnectionError` with backoff, AND the Flask errorhandler widened to `requests.RequestException` → JSON 502; `test_get_retries_on_connection_reset_then_succeeds`, `test_get_raises_connection_error_after_exhausting_retries` (tests/test_client.py), `test_upstream_connection_error_returns_json_502_not_html` (tests/test_dashboard.py); tests 108→111 |

Rows demonstrating the rest of the status vocabulary, from the same chronicle:

| Symptom / item | Status |
|---|---|
| FRED (macro data, optional `FRED_API_KEY`) built, never run with a real key | `open` — first command: set a real key and hit the ECO screen / `macro_view` |
| Pre-2013 SGML 13F filings — should error clearly, path never exercised | `open` — chronicle names the recipe: find an old 13F-HR via `edgar search`, fetch its index live, confirm the error is useful, not a raw traceback |
| Chubb (Swiss issuer) renders tickerless — OpenFIGI keyless can't map it | `open` (candidate fix recorded: name-based fallback via SEC `company_tickers.json`) — the tickerless render itself is a documented non-bug (degradation by design) |
| Schwab brokerage/trader API integration | `won't-fix` — "explicitly deferred by user ('not now')", attribution recorded so it isn't re-pitched |
| GOOGL/GOOG and LEN/LEN.B appear as two rows each | **Documented non-bug** — different CUSIPs for different share classes; chronicle says "correct output, not a duplicate-row bug. Worth remembering if it looks surprising later." |

What the mining bought: a new session that skims this table will not revert to
the atom endpoint (row 1), not "fix" the two-row Alphabet output (non-bug), not
re-pitch Schwab (won't-fix), and knows the exact first command for both open
items. That is the entire point of the skill.

---

## 5. When NOT to use this skill

| Situation | Use instead |
|---|---|
| You're mid-debug and need triage steps / a discriminating experiment | debugging-playbook (this skill records the outcome; that one produces it) |
| You need session-close mechanics, doc templates, which file gets what | docs-and-writing |
| You're deciding whether a change is even allowed / how to gate it | change-control |
| You need the evidence bar for calling something verified, or fixture discipline | validation-and-qa |
| You want the project's standing invariants rather than its incident history | architecture-contract |
| You just landed and want the full improvement loop, not only history | improvement-campaign (it calls this skill as its recon step) |

---

## 6. Provenance and maintenance

- Written 2026-07-07 against `D:\src\edgar` (edgar). All incident rows mined
  from `HANDOVER.md` (sessions 2026-06-30 → 2026-07-07) and `CLAUDE.md`, and
  cross-checked against `src/edgar/models.py`, `tests/test_client.py`,
  `tests/test_tickers.py`, `tests/test_market.py`, `tests/test_macro.py`,
  `tests/test_dashboard.py`.
- **Volatile facts:** test count (111 as of 2026-07-07 — CLAUDE.md's "108" was
  already stale the day this was written, which is itself the lesson:
  date-stamp volatile counts); "repo has no git history" (someone may
  `git init` later — re-run `git -C . rev-parse --is-inside-work-tree`); the
  `open` rows above may have closed.
- **Re-verify with:**
  - `python -m pytest tests -q` — current test count.
  - `grep -n "def test_search_company_cik\|def test_resolve_prefers_us\|def test_get_retries_on_connection_reset" tests/*.py` — regression tests still exist under these names.
  - Read the newest `HANDOVER.md` entry — any incident newer than 2026-07-07
    belongs in the worked table's next revision.
