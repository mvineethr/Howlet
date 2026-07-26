# HANDOVER - Howlet

Session log for picking this project back up. See `CLAUDE.md` for the
standing dev brief (what the tool is, current status, constraints).
Newest session first.

---

# Session 2026-07-25: cold-start audit, Schwab read-only plan, dashboard design overhaul

Written just after midnight on 2026-07-26; dated 07-25 to match the work
and the external log's Session 3.

## What was asked

Three things, in order: (1) analyse the repo cold - where did we stop and
what's next - plus how to connect a Schwab Trader API to the dashboard;
(2) run a four-step gated design overhaul of `dashboard.html` through the
`design-taste-frontend` (tasteskill v2) skill: audit, mode declaration,
implementation, completion audits, stopping for approval between each;
(3) settle whether this project needs a database.

## What was done

### 1. Cold audit - the docs were the least reliable thing in the repo

This extends S11 (2026-07-17 part 5), which left publish as an open item.
It is no longer open, and both hand-off files said otherwise:

- `CLAUDE.md`'s roadmap listed **"Publish" as next-feature #1** for a
  package that had been live on PyPI for a week.
- `HANDOVER.md`'s newest entry was 2026-07-17 part 5, a full session
  behind reality (see the GAP note below).

Verified the real state live rather than trusting either file:

| Claim | Check | Result |
| --- | --- | --- |
| PyPI publish | `pypi.org/pypi/howlet/json` | **0.8.0 live, only release** |
| GitHub + CI | `git log origin/main` | `origin/main` == local at `4c75cf7` |
| Tests | `PYTHONPATH=src pytest tests/` | **145 passed** in 4.4s |
| Lint | `ruff check .` | All checks passed |
| Release tag | `git tag` | **EMPTY** - 0.8.0 shipped untagged |

### 2. Live-found bug: the editable install has been broken for a week

The suite initially failed to collect **23 of 23 test modules** with
`ModuleNotFoundError: No module named 'howlet'`, while `pip show howlet`
reported 0.8.0 installed. Root cause:
`site-packages/__editable__.howlet-0.8.0.pth` contains one line,
`D:\src\edgar\src` - the **pre-rename path**, gone since S11 renamed
`D:\src\edgar` -> `D:\src\howlet`. So on this machine `howlet --version`
throws out of `Scripts\howlet.exe\__main__.py` and bare `pytest tests/`
collects nothing. Editable installs fail asymmetrically: metadata stays
valid, only resolution breaks.

Hit it a second time from a different direction: `preview_start` runs
`python -m howlet.cli` and died the same way. Fixed properly by adding
`"PYTHONPATH": "src"` to the `env` block in `.claude/launch.json`, so the
launcher works whether or not the package is installed. This also
mattered for correctness - without it the worktree would have served
`D:\src\howlet\src\howlet\dashboard.html` (the *main* worktree's file),
so the whole design verification would have been against the wrong file.

### 3. Schwab Trader API - planned in full, not built

Established first that `D:\src\Trader\src\schwab\` is an **empty
placeholder** (0-byte `__init__.py`); that project's live code is
Polymarket. So there was no client to reuse anywhere.

Verified the API surface from `schwab-py`'s actual `client/base.py` and
auth docs, not from memory:

- `GET /trader/v1/accounts/accountNumbers` -> plain number to `hashValue`
- `GET /trader/v1/accounts/{hash}?fields=positions`
- `GET /trader/v1/accounts/{hash}/orders`, `.../transactions`
- `GET /marketdata/v1/quotes?symbols=...`
- OAuth token endpoint `https://api.schwabapi.com/v1/oauth/token`
- **Access token 30 minutes. Refresh token 7 days, hard, no renewal.**
- Callback must be `https://127.0.0.1:<port>`, matching app config
  exactly; approval to `Ready for Use` is manual and takes days.

That 7-day expiry is the whole architecture: a Schwab panel can never be
"set up once", so it goes in the **fragile tier beside `yahoo_auth.py`**
where consumers degrade and never raise, rendering
`SCHWAB - RE-AUTH REQUIRED` and never blocking a 13F panel. Reconciled
with the "no required API key, ever" hard rule by making it an optional
FRED-style enricher: env credentials only
(`SCHWAB_APP_KEY`/`SCHWAB_APP_SECRET`/`SCHWAB_CALLBACK_URL`), token cache
at `~/.howlet/schwab_token.json`, gitignored, never a repo file (S11's
credential lesson applied). Chose the **paste-the-redirect-URL** flow
over a local HTTPS listener so no self-signed cert ships in the package.

Plan: new `src/howlet/schwab.py`; `broker_positions_view` /
`broker_balances_view` / `broker_orders_view` in `views.py`, each guarded
by `is_connected()` returning `{"connected": false, "reason": ...}`;
three routes in `dashboard.py`; three MCP tools (**27 -> 30**); three
blocks in `dashboard.html`'s registry; `howlet schwab-login` +
`howlet positions` in `cli.py`; `tests/test_schwab.py` covering token
refresh, 7-day expiry -> degraded, position parsing, disconnected path.
**Zero new dependencies.** Blocked on Schwab's manual app approval.

### 4. Design overhaul of `dashboard.html`

The skill's own **Section 13 names dashboards and data tables as out of
scope**, which was reported rather than ignored: findings were split
per-surface between what applied (typography, spacing, colour, motion,
a11y, AI-tells, the HELP/ABOUT surface) and what would have damaged a
cockpit UI (no 20-row tables - the 13F table *is* the product; cards
replaced by whitespace - panels carry the resize/remove controls; all
hero rules - there is no hero).

**Audit found** (mechanical, over all 2,490 lines): 9 raw greys bypassing
the token set (~25 usages); `11px` the most-used size at 13 declarations,
*below* the 12px base; **zero `:focus` rules and zero `transition:`
declarations**; no `prefers-reduced-motion`; 54 middle-dots including 13
in one line; one stray `border-radius: 6px` in an otherwise 0-radius
system; 11 screens on one URL. Dials read 3/2/9. Already-clean by
accident: **zero em-dashes** and zero `addEventListener("scroll")`.

Declared **Redesign-Preserve**, not the Overhaul the brief asked for,
because the brief's own completion gate required the brand accent, type
stack and logo to survive - mutually exclusive with Overhaul. Dials
3/2/9 -> 5/4/9 with `VISUAL_DENSITY` **locked at 9**.

Shipped:

- Tokenized elevation ramp: `--bg: #08090a` (off-black), `--panel`,
  `--elev-1` (chrome), `--elev-2` (interactive), `--hair` (row dividers),
  `--border: #2e3134`. All 9 raw greys gone.
- Brand amber recomputed from HSL: `#ff9900` is `hsl(36, 100%, 50%)`;
  new `#eaa53e` is `hsl(36, 80%, 58%)` - **hue held at exactly 36**,
  saturation to the 80% cap, lightness lifted to hold contrast.
  `--amber-dim` `#b36b00` -> `#ae7013`. `--dim` `#7a7a7a` -> `#8a8a8a`
  (was 4.53:1 on panel, now 5.60:1).
- All 13 `font-size: 11px` -> 12px; `th` uppercase + tracking;
  `font-variant-numeric: tabular-nums` on numeric cells.
- Panel surfaces: inset top highlight + tinted shadow, 2px `--amber-dim`
  left rule on `.panel-h`, `.panel-b` padding 6px -> 8px so chrome stays
  tight and content breathes.
- **First `:focus-visible` styles this terminal has ever had.**
- Motion layer: 0.13s colour transitions on interactive elements,
  `:active { translateY(1px) }`, a `panel-in` fade masking the async
  loading->loaded pop, all gated by a `prefers-reduced-motion` block.
- Removed the fake `.live` blink (2s loop asserting liveness regardless
  of feed state). Glyph and colour left byte-identical.
- Middle-dots **54 -> 13, max 1 per line**; deleted the footer SOURCES
  strip (13 dots, verbatim duplicate of HELP > SOURCES).

## Live-found bugs this session

1. **Editable install broken by the S11 rename** - see section 2 above.
2. **KLineChart held a second, complete copy of the palette in JS.**
   `initKlineChart` hardcoded 8 colours (`#141414` grid, `#ff9900`
   crosshair, `#2a2a2a` separator, ...) duplicating `:root`. Retuning the
   CSS tokens would have **silently left the chart on the old brand**,
   invisible to any amount of CSS review, because KLineChart is themed
   through a JS API. Replaced with a `getComputedStyle(documentElement)`
   reader. Caught by grepping the JS for hex before editing the CSS.
3. **13 form controls set `font-family` but never `font-size`**
   (`#eqs-pe-max`, `#eqs-mcap-min`, `#eqs-growth-min`, `#eqs-margin-min`,
   `#eqs-run`, `#pf-symbol`, `#pf-shares`, `#pf-add`, `#watch-input`,
   `#watch-btn`, `#restore-classic`, `#opt-expiry`, `#import-file`), so
   they had always rendered at the UA default 13.33px in a *proportional*
   metric inside a monospace terminal. Pre-existing; invisible to source
   grep since you cannot grep for a missing declaration. Found by probing
   computed styles on the live page. Fixed with one lowest-specificity
   rule, `input, select, button, textarea { font: inherit; }`, so every
   existing per-control rule still wins. All 28 controls now 12px.
4. **A naive `prefers-reduced-motion` block would have hidden the tape.**
   `#tape` is parked offscreen by `padding-left: 100%` and walked in by
   its keyframes; killing animation alone leaves it permanently off the
   right edge. Block also resets `padding-left: 0`.

## Verified live

- 145 offline tests pass; ruff clean; **zero console errors**.
- Tokens resolving in-page; contrast computed from the live values:
  `--text` 13.56:1, `--cyan` 11.42:1, `--up` 9.59:1, `--amber` 9.16:1,
  `--down` 5.63:1, `--dim` 5.60:1 on panel; `--bg` on amber fill 9.44:1;
  tightest `--amber-dim` (table headers) 4.72:1, above the 4.5 floor.
- `prefers-reduced-motion` block confirmed **parsed by the engine** via
  `document.styleSheets`, not merely present as text.
- `:focus-visible` proven with a real **Tab keypress** returning
  `solid 2px rgb(234, 165, 62)`. A scripted `.focus()` returns
  `focus_visible: false` / `outlineStyle: none` in Chrome and briefly
  looked like a bug in correct CSS.
- Chart theme read back from `klineChart.getStyles()`:
  `crosshairFill "#eaa53e"`, `grid "#1a1c1e"`, `separator "#2e3134"`,
  `crosshairText "#08090a"` - the new tokens.
- Live data flowing: tape at S&P 7,411.98; `AAPL DES` loaded **125 bars**
  with 3 indicators across 14 canvases; 31 panels rendering.
- Preservation diffs vs `HEAD`: form field ids **IDENTICAL**, `data-cmd`
  nav values **IDENTICAL**, anchor ids + hrefs **IDENTICAL** (all 7 HELP
  anchors), all 10 F-key labels intact, all 7 localStorage keys unchanged
  so existing layouts and watchlists survive. Em-dash audit 0/0/0/0.
- **Could NOT screenshot** - the browser pane was not displayed, so the
  page never composited frames. Verified by measurement instead; before/
  after images are still owed.

## No database (measured, not assumed)

`~/.howlet` totals **796 KB**: 25 holdings files (508K), 94 Form 4 files
(236K), 28 KB `cusip_tickers.json`, 13 KB `screener_cache.json`. Timed
the exact query a DB would exist to accelerate - the full cross-filing
aggregation walk - over 7 runs: all 25 filings, **2,720 holding rows**,
**1,287 unique CUSIPs**, **median 8.4 ms** (min 8.1 / max 10.6). It is
fast because filings are immutable, making accession-keyed flat files the
correct structure rather than a stopgap. Every genuinely slow path is a
network throttle a DB cannot touch: OpenFIGI at 5 CUSIPs / 3s,
`edgar_lock` at `views.py:108` serializing all EDGAR access (an
HTTP-politeness lock, not a storage lock), and multi-MB `companyfacts`
per screener symbol. If it is ever needed: stdlib `sqlite3` behind the
existing two-method `FilingCache` seam, never a service. Triggers to
revisit: multi-user shared state, the walk crossing ~200 ms, or queries
spanning filings by something other than accession.

## Pending

- **Fix the editable install**: `pip install -e "D:\src\howlet"`.
- **`git tag v0.8.0`** - still untagged.
- **Schwab build** - blocked on manual app approval. Prerequisites are
  the user's alone: create the app at `developer.schwab.com` selecting
  BOTH "Accounts and Trading Production" and "Market Data Production",
  callback `https://127.0.0.1:8182` exactly, credentials into the
  environment by hand.
- **Screenshot the redesign.**
- **Mobile grids** - `#news-grid` / `#my-grid` never collapse (inline
  `grid-template-columns`, no media query); HOME grid clipped below 420px
  by `body { overflow-x: hidden }`. Deferred for a 3-desktop-user
  audience.
- **0.8.1+ release** so the live PyPI page picks up the README logo and
  badges (PyPI freezes each release's rendered description at upload).
- Carried from S11: FRED with a real key; pre-2013 SGML filings; N-PORT
  depth; finer-grained EDGAR locking.

## Gap in this file - CORRECTION

This section originally claimed "2026-07-18 has no HANDOVER entry."
That was wrong: the entry existed all along, written the same day, but
sat **uncommitted in the main worktree's working directory** for a week
- neither this session nor the 2026-07-25 external log had visibility
into it until the merge below surfaced it. It is now committed as the
"doc system backfill" entry immediately following this one - see its
own "Note on gaps" section for the one remaining gap it flags (a
per-widget manager selector and a jump-nav scrolling fix with no dated
entry anywhere in this file).

---

# Session 2026-07-18: doc system backfill + CLAUDE.md/HANDOVER.md upkeep

## What was asked

Write the end-of-session record for parts 3-5 of the previous stretch
(crypto/Federal-Register, the 6-feature sprint, the two renames, the
PyPI publish, the owl logo) into the external EB-1A/content docs system
at `D:\project documentaions\howlet\`. Then bring this repo's own
`CLAUDE.md` and `HANDOVER.md` up to date with the same period, and turn
that update workflow into a reusable `/handover` slash command.

## What was done

- **External docs** (`D:\project documentaions\howlet\`): wrote
  `daily-log.md` Session 2 (full narrative for S9-S11 - crypto/
  Federal-Register, the insider-buy/filing-alerts/full-text/N-PORT/FX
  sprint, the `edgar13f`->`Edgar`->`howlet` rename saga including the
  PyPI import-collision discovery, the credential-exposure incident,
  the actual PyPI publish with fresh-venv verification, and the owl
  logo work including the sparkle-watermark pixel patch); updated
  `overview.md`'s Current Status/Architectural Decisions/Pending
  sections; queued 5 story candidates in docbot's `content/ideas.md`;
  updated `docbot/journey.md` and this project's `eb1a-evidence.md`
  with the first-public-release milestone.
- **This repo's `CLAUDE.md`**: added a `## Session History` block (S1
  through S12, one line each, grounded in this file's own session
  headers rather than invented); updated Status to note the project is
  now published (PyPI + public GitHub, CI green); replaced the
  "Publish" next-feature item (done) with a note that a 0.8.1 release
  is still needed before PyPI's *rendered* description picks up the new
  README/logo (PyPI freezes each release's description at upload time);
  added two Gotchas (PyPI import-name collisions vs. listing-name
  clashes; CI's bare `pytest` vs. local `python -m pytest` resolving
  `sys.path` differently) and one Hard rule (never a real credential in
  a repo-tracked file - `.pypirc` only). 186 -> 241 lines, within the
  200-300 target.
- **This entry** in `HANDOVER.md`, and a new `/handover` slash command
  at `~/.claude/commands/handover.md` (user-level, so it works the same
  way across projects) that encodes this exact workflow for future
  sessions.

## Note on gaps

Docbot's own daily-log Session 1 (written earlier from compacted
context) describes a per-widget manager-selector and a jump-nav
scrolling fix that has no corresponding dated entry anywhere in this
file - that work isn't represented in `CLAUDE.md`'s new Session History
either, since the block was built strictly from this file's real
headers rather than filled in from memory. If that work matters for the
record, it needs its own HANDOVER.md entry written from whoever still
has the detail, not reconstructed here.

---

# Session 2026-07-17 (part 5): rebrand to Howlet, GitHub + CI live

## What was asked

User pushed to github.com/mvineethr/Edgar, then learned "edgar" was
already a PyPI package (py-edgar, whose module is ALSO `edgar` - a
site-packages collision if both are installed). After a naming session
(owl themes; hedwig/hoot/owlet all taken or risky), settled on
**howlet** - a real archaic word for a small owl, free on PyPI and
GitHub-clean (verified live before choosing).

## What was done

- Full rename edgar -> howlet: package dir, imports, CLI, pyproject
  (name/script/package-data/urls), MCP server name, `~/.edgar` ->
  `~/.howlet` (existing cache moved), Dockerfile, launch.json, docs.
  CRITICAL constraint: "EDGAR" survives everywhere it means SEC EDGAR
  (URLs, EDGAR_USER_AGENT, `svc.edgar`, prose) - no blanket sed.
- Dashboard rebrand: HOWLET ● TERMINAL with an inline great-horned-owl
  SVG in the topbar + SVG data-URI favicon (no external assets).
  localStorage keys edgar_* -> howlet_* WITH a boot-time migration that
  copies any edgar13f_*/edgar_* state to howlet_* (never overwrites) -
  the previous two renames had silently orphaned saved state.
- Also this session, pre-rename: pushed to GitHub for the first time,
  and CI's first-ever run FAILED on a real latent bug -
  `from tests.test_form4 import ...` only works under `python -m
  pytest` (cwd on sys.path), not the bare `pytest` that ci.yml runs.
  Fixed to a same-directory import; CI green on all 6 matrix combos
  since. Lesson: run the EXACT CI command locally, not an equivalent.
- PyPI naming trap recorded: py-edgar owns `edgar`; `owlet` is a
  geospatial package; check the module name inside a dist, not just
  the project name, before declaring a name safe.

---

# Session 2026-07-17 (part 4): the full review slate - 6 features + release prep

## What was asked

"Do that all" after a thorough project review: every improvement and
every addition from the review, then a list of what only the user can
do (accounts).

## What was built (each verified live before moving on)

- **Quick wins**: `howlet warm` (14 portfolios + 1275 CUSIPs mapped in
  one pre-fetch run, verified), EXPORT/IMPORT full-state JSON backup in
  the tab bar, CRYPTO TOP 20 home block, ⤓ CSV buttons (portfolio/
  changes/consensus/EQS), ruff in CI (3 findings fixed), 2 HTML smoke
  tests. The "newsItemsHtml `<\\span>` typo" from the review turned out
  not to exist - review claim was wrong, nothing to fix.
- **Insider-buy screening**: `_symbol_form4_transactions` helper +
  `insider_buys_view`; CLI `insider-buys`, `/api/insider-buys`, MCP
  `screen_insider_buys`, watchlist-scoped block. Live verify found a
  real signal: OXY President/CEO Jackson bought 4,770 sh @ $52.38
  (2026-06-23); AAPL/JPM/INTC/BA correctly zero.
- **13F filing alerts**: `latest_filings_view` (per-preset newest
  accession, one broken manager can't kill the poll - tested), topbar
  bell polls every 30 min, baseline-then-diff against
  `edgar_seen_filings_v1`, optional desktop notifications, MARK ALL
  SEEN. Verified by rewinding Buffett's seen accession live - badge lit
  with his real Q1 filing, dismiss restored state.
- **EDGAR full-text search** (`fulltext.py`, efts.sec.gov) + **company
  filings feed** (list_filings generalized to form_type=None; new
  optional `form` field on FilingSummary). CLI `fts`/`filings`, two MCP
  tools, SEC FILINGS block. Both verified live (AAPL 8-Ks; phrase
  search returns real hits with working archive links).
- **FX matrix** (`fx.py`): Frankfurter/ECB - NOTE the old
  api.frankfurter.app domain 301s; use api.frankfurter.dev/v1. Cross
  rates derived from one USD-based call, 1h cache. Verified EUR->JPY
  185.65 against tape (162.35 x 1.1435 ✓).
- **N-PORT fund holdings** (`nport.py`): company_tickers_mf.json ->
  (trust CIK, seriesId); browse-edgar filtered BY SERIES ID (the trust
  CIK alone mixes its funds); primary_doc.xml parsed by local name.
  ARKK verified live ($6.48B net, Tesla 9.74% top). SPY/UITs correctly
  raise a clear LookupError - they don't file NPORT-P.
- **Release prep**: v0.8.0, CHANGELOG, README/CLAUDE.md updated (also
  fixed stale "KLineChart loaded from jsDelivr CDN" claim - it's
  vendored), dist rebuilt + twine-checked.

## State

145 offline tests green, ruff clean, all 7 new dashboard blocks
verified rendering live data in the browser, zero console errors.
MCP: 27 tools.

---

# Session 2026-07-17 (part 3): crypto screen, Federal Register, cleaner topbar

## What was asked

From the API-list review: wire in Federal Register (candidate #3), and
a crypto screen "along with stocks but under a toggle - not in the same
space". Also remove the example-hint placeholder from the command box.

## What was built

- **`crypto.py`**: CoinGecko keyless `/coins/markets` (probed live
  first) with automatic Coinpaprika fallback, normalized rows, 60s
  in-memory TTL cache, degrades to ("", []). `crypto_view` +
  `/api/crypto` + MCP `get_crypto_markets`.
- **MKTS STOCKS/CRYPTO toggle**: two modes in separate spaces, choice
  remembered (`edgar_mkts_mode`). The old 5-symbol CRYPTO section
  was removed from `MARKET_SECTIONS` (and its test updated to assert
  it's ABSENT). Crypto side: top-50 table w/ price, 24h %, mkt cap,
  volume, 24h range, "source: coingecko|coinpaprika" label.
- **`regulatory.py`**: Federal Register API (keyless, official) SEC
  documents; `regulatory_view` + `/api/regulatory` + MCP
  `get_sec_rulemaking` + SEC RULEMAKING panel on ECO. MCP now 21 tools.
- **Command box placeholder removed** per user.
- Tests 132 (fixtures trimmed from live payloads captured 2026-07-17).

## Live-found bug #7: date-only strings render a day early

Federal Register `publication_date` ("2026-07-17") fed to
`new Date(...).toLocaleString()` renders as "7/16/2026, 7:00:00 PM" in
US timezones (parsed as UTC midnight). Fixed by passing the date string
through verbatim in the source label. Gotcha added to CLAUDE.md.

## Verified live (browser)

Stocks side has NO crypto section; CRYPTO toggle renders top-50 with
BTC $64,123 / $1.29T cap (cross-checked against the Yahoo tape's
BITCOIN 64,120); ECO shows same-day Federal Register notices (first
item matched the raw API probe). NOTE: Python edits need a dashboard
server restart - only dashboard.html is re-read per request (this
nearly passed as "verified" against stale code).

---

# Session 2026-07-17 (part 2): widget resize + named layout snapshots

## What was asked

Per-widget resize, and saving layouts "like a memory" (single user, no
profiles needed). Plus a review of two public-API lists for candidate
integrations (assessment delivered in chat; no new sources wired in -
top keyless candidates recorded in CLAUDE.md's next-features list).

## What was built

- **Per-widget resize**: every dashboard block header now has ↔ (toggle
  full width, same grid mechanic as the built-in `wide` widgets) and ↕
  (double height: `.widget.tall .panel-b` max-height 420 -> 860px).
  Stored as `w.wide` / `w.tall` booleans on the widget entry in the
  layout; toggling flips classes in place so the block is NOT refetched
  just for a resize.
- **Named layout snapshots**: LAYOUTS: [select] SAVE/LOAD/DEL in the
  dashboard tab bar. SAVE deep-copies the whole layout (all tabs,
  blocks, sizes) into `edgar_layouts_v1` under a prompted name;
  LOAD replaces the live layout (with confirm); DEL removes a snapshot.
  All localStorage, consistent with watchlists/portfolio.

## Verified live (browser)

Toggled ↔/↕ on the insiders block (class + persisted booleans checked),
saved snapshot "work", deleted the insiders block, LOAD restored it with
its wide+tall sizing intact. Native prompt()/confirm() dialogs were
stubbed via console during automation - they block the browser-pane
tools - but the click path exercised was the real one.

---

# Session 2026-07-17: roadmap cleared - Form 4, position history, presets, ticker fallback, v0.7.0

## What was asked

"Follow the order, complete them one by one" - the whole CLAUDE.md
roadmap: (1) Form 4 insider transactions, (2) historical position
charts, (3) expand presets, (4) name-based ticker fallback,
(5) publishing checklist.

## What was built

- **Form 4 insider transactions** (`form4.py` + `Form4Cache` in
  cache.py): issuer CIK -> form "4" filings (via a new generic
  `EdgarClient.list_filings(cik, form_type)`; `list_13f_filings` is now
  a wrapper) -> ownershipDocument XML, parsed namespace-tolerantly.
  Non-derivative rows only (the derivativeTable would double-count RSU
  vests). Surfaces: CLI `insiders` (P/S only by default, `--all` for
  everything), `/api/insiders/<symbol>`, MCP `get_insider_transactions`,
  INSIDER TRANSACTIONS dashboard block (new `needs: "symbol"` picker
  config).
- **13F position history**: `position_history_view` walks N quarters of
  cached filings, aggregates by CUSIP, matches query as ticker (via the
  resolver, no new lookups) / raw CUSIP / issuer-name substring.
  Surfaces: CLI `history`, `/api/position-history/<mgr>/<query>`, MCP
  `get_position_history`, 13F POSITION HISTORY dashboard block with
  amber value bars + share-change deltas (new `needs: "manager-symbol"`
  picker config). MCP is now 19 tools.
- **Presets 4 -> 14 managers**: tepper/appaloosa 1656456, klarman/
  baupost 1061768, loeb/thirdpoint 1040273, dalio/bridgewater 1350694,
  druckenmiller/duquesne 1536411, marks/oaktree 949509, lilu/himalaya
  1709323, einhorn/greenlight 1489933 (DME Capital - see below),
  fundsmith 1569205, tigerglobal 1167483. EVERY CIK verified live two
  ways: name search AND latest 13F-HR is current (2026-03-31).
- **Name-based ticker fallback**: `fundamentals.name_to_ticker`
  (normalized exact match against company_tickers.json titles, trailing
  noise tokens stripped, first class in file order wins ->
  GOOGL not GOOG) wired into portfolio/holders views via
  `views._apply_name_fallback`; successes are written back into the
  resolver's disk cache via the new `CusipTickerResolver.learn`.
  Verified live: Berkshire's CHUBB LTD SWITZ / H1467J104 -> CB @ $353.
- **v0.7.0 published-ready**: CHANGELOG.md, version bump, sdist+wheel
  built, `twine check` PASSED, wheel verified to contain dashboard.html
  + vendored klinecharts + form4.py. Repo `git init`ed with the initial
  commit so the CI workflow finally has a repo to run in.

## Live-found bug #7: EDGAR exact-match company search redirect

An exact-name query ("third point") skips the results table - EDGAR
renders that company's own filing list instead, and the old parser
returned garbage rows ({"name": "Documents", "cik": None}) from the
filing table. `search_company_cik` now detects `span.companyName` and
reads the name + CIK from the header. Found because preset
verification searched "greenlight capital" live.

## Also learned live (now in CLAUDE.md gotchas)

- Form 4 `primaryDocument` is an XSL viewer path (`xslF345X06/form4.xml`);
  the raw XML is the bare filename. Prices can be footnote-only -> None.
- Famous managers migrate filer entities: Appaloosa Management LP
  (1006438) stopped filing in 2016 (Appaloosa LP 1656456 now files);
  Greenlight's 1079114 stopped after 2023-12-31 - Einhorn files as DME
  Capital Management LP (1489933). Name match alone is not enough;
  check the latest 13F-HR is current.
- SEC titles vs 13F issuer names disagree in suffixes AND jurisdiction
  tags ("Chubb Ltd" vs "CHUBB LIMITED" vs "CHUBB LTD SWITZ").

## Verified live this session

- `insiders AAPL`: 0 open-market buys, 14 sells $111.7M across 15
  Form 4s (Cook/Parekh/O'Brien/Levinson rows, prices in AAPL's real
  range); same numbers in the dashboard block.
- `history buffett AAPL --quarters 10`: 905,560,000 -> 789,368,450 ->
  400,000,000 -> 300,000,000 -> ... -> 227,917,808 shares - matches
  Berkshire's publicly reported AAPL trim exactly. Same data in the
  dashboard block after a server restart (a stale server 404s new
  routes as "Unexpected token '<'" - that's just Flask needing a
  restart, not bug #6 again).
- `holdings tepper`: Appaloosa's real Q1-2026 book (AMZN $900M top
  position, Alibaba, Vistra...).
- Chubb name-fallback via `/api/portfolio/buffett?top=30`.

## Tests

111 -> 122, all offline/mocked (`pytest tests/`): Form 4 parsing from a
captured live AAPL filing (footnote price -> None, derivative rows
excluded, XSL prefix stripped), position history (chronology,
multi-entry aggregation, name fallback, 404), exact-match search
redirect, name normalization, portfolio Chubb fallback + learn().

## What's still open

- **Publish to PyPI / push to GitHub** - artifacts are built and
  checked in `dist/`, repo is committed locally; pushing and
  `twine upload` need the user's accounts/credentials.
- Known-untested: FRED with a real key; pre-2013 SGML filings.
- First `holders`/`consensus` run with the 14-manager roster will be
  slow (OpenFIGI keyless mapping for ~10 new portfolios, Bridgewater
  and Tiger are big); disk-cached forever afterwards.

---

# Session 2026-07-07 (part 2): customizable dashboard, tabs, back button

## What was asked

Blank-slate HOME where the user picks blocks; multiple watchlists with
news scoped to only those symbols; a "+" for user-created tabs; a back
button on the security screen (which itself must NOT change); plus the
pre-publish items (CLAUDE.md cleanup, vendor KLineChart, CI).

## What was built

- **CLAUDE.md rewritten** from a session diary into a concise brief:
  module map, hard rules, gotchas list, status, roadmap. History lives
  here in HANDOVER.md only.
- **KLineChart vendored** into `src/howlet/static/` (+ its Apache-2.0
  LICENSE file); served via Flask's default /static/; no CDN at runtime.
  package-data updated.
- **GitHub Actions CI** (.github/workflows/ci.yml): ubuntu+windows x
  py3.10/3.12/3.13, offline test suite. (Repo isn't `git init`ed yet.)
- **Customizable dashboard** (new default screen `screen-dash`):
  - localStorage layout {tabs:[{id,name,widgets}], active}; blank HOME
    by default + RESTORE CLASSIC LAYOUT preset button.
  - 10 widget types: 13F portfolio / Q/Q changes (per manager),
    consensus, watchlist / watchlist-news / watchlist-events (per named
    list), market news, Fed, yield curve, world markets. Widgets have
    remove x, config label, periodic refresh (60s watchlists, 300s news).
  - "+ TAB" creates named tabs (deletable except HOME).
  - Multiple named watchlists (`edgar_watchlists_v1`, old single-list
    key migrated to "default"; MY screen now reads the "default" list so
    it stays in sync with home widgets).
- **BACK button** on the DES chart header; `showScreen` records the
  screen you came from (state.backTo). DES content otherwise untouched.
- PORT screen (classic manager view) kept as-is, reachable via manager
  dropdown/PORT command; its consensus/news panels now lazy-load on
  first visit instead of at boot.

## Live-found bug #6: SEC resets stale keep-alive connections

The widget grid's parallel calls surfaced ConnectionResetError 10054
from data.sec.gov on the long-lived shared session - `_get` only
retried HTTP 429/5xx, so the exception propagated and Flask returned an
HTML 500 page, which the frontend showed as "Unexpected token '<'".
Fixed twice over: `_get` now retries `requests.ConnectionError` with
the same backoff, and the Flask errorhandler was widened from HTTPError
to `requests.RequestException` so every upstream failure is a JSON 502.
Tests 108 -> 111.

## Verified live (browser)

- Blank slate on first load; klinecharts served locally (CDN removed).
- Built a layout programmatically via the same code paths as the picker:
  13F portfolio (buffett, $263.10B/29 positions), custom "ai-stocks"
  watchlist (NVDA/MSFT/GOOGL live quotes, inline add/remove), watchlist
  news showing ONLY those 3 names, yield curve; MISC tab holding a Fed
  widget. Layout + tabs survived a server restart.
- Add-picker opens with all 10 types; tab switching works.
- NVDA click in a widget -> DES -> BACK -> dashboard intact.

---

# Session 2026-07-07: KLineChart, NEWS/MY tabs, FRED

## What was asked

User hit TradingView's free-widget limit (2 stacked indicators, more =
subscription) and wants everything un-paywalled for the open-source
release. Also: a dedicated NEWS tab with more free sources, a
personalize (MY) tab (watchlist + scoped news + events, click-through to
DES), FRED enabled, options work paused.

## Decisions

- **KLineChart** (Apache-2.0) replaces the TradingView embed: ~30
  built-in indicators with NO stacking limit, drawing overlays, and it
  renders our own OHLCV - no third party controls the chart. CDN gotcha:
  the UMD build is at `dist/umd/klinecharts.min.js`; `dist/<file>` 404s
  (hit this live - klinecharts loaded as undefined until fixed).
- WATCH screen folded into the new MY tab (same localStorage key, WATCH/W
  still route there). OPT stays functional but off the F-key bar.

## Changes

- `market.py`: Quote.history_open added; parser keeps full OHLCV aligned
  after None-gap dropping. `views.security_view` returns the arrays.
- `news.py`: MARKET_FEEDS + Google News Business, CNBC Earnings, Seeking
  Alpha Market Currents. Per-ticker: TICKER_FEED_URLS (Yahoo + Google
  News search + Seeking Alpha per-symbol), merged/deduped.
- `macro.py`: FRED_SERIES + get_fred_snapshot(); macro_view includes
  fred_series when FRED_API_KEY set (untested with a real key so far).
- `dashboard.html`: KLineChart init/dark styles/indicator picker with
  removable chips/draw toolbar; NEWS + MY screens; fkeys now
  HOME/DES/NEWS/MY/MKTS/EQS/ECO/PF/HELP.
- Tests 106 -> 108 (FRED snapshot, multi-feed ticker news, OHLCV).

## Verified live (2026-07-07)

- AMZN DES: 123 candles; last bar O 243.79 H 246.04 L 240.88 C 244.16
  V 37.57M - matches the user's own TradingView screenshot exactly.
- 10 indicators stacked simultaneously, removed cleanly; drawing overlay
  armed without error.
- NEWS tab: 60 wire items across CNBC/CNBC Earnings/MarketWatch/Google
  News/Seeking Alpha, 15 Fed items, 8 earnings/analysis.
- MY tab: 7 watchlist quotes; 40 scoped news items; events table with
  real earnings dates (AAPL 07-30, MSFT 07-29, NVDA 08-26, AMZN 07-30,
  TSLA 07-22) + analyst views + last DEF 14A per name.

## Open

- FRED path needs a real-key test once the user signs up.
- Consider vendoring klinecharts.min.js into the package (currently CDN)
  for fully-offline/open-source distribution.
- Form 4 insider transactions still the top roadmap item.

---

# Session 2026-07-06 (part 3): analytics, screener, options, macro, events

## What was asked

Scale toward "full Bloomberg": advanced analytics, more asset classes
(fixed income, FX, derivatives, macro), screening, portfolio/risk mgmt,
corporate events (earnings, analyst data, meetings, Fed), technical
studies (ORB/EMA), TradingView integration, quant scripting, Schwab
Trader API. Clarified scope via AskUserQuestion: build all free chunks;
FRED as optional key (user initially confused, explained, proceeded);
Schwab = not now; quant scripting = the library itself, not server-side
code execution (RCE risk).

## Key discovery: Yahoo's auth wall + the crumb workaround

Probed live before building: v7/finance/quote, v10/quoteSummary, and
v7/finance/options ALL return 401 anonymously now. The classic
workaround (GET fc.yahoo.com for a cookie, then /v1/test/getcrumb, then
pass crumb= on every call) works and is what yfinance does. Built
`yahoo_auth.py` around it with the hard rule that its consumers (events,
options) degrade to "unavailable" instead of raising - only the chart
endpoint (quotes/history/screener) stays crumb-free.

## What was built (11 new/changed modules, tests 48 -> 106, MCP 11 -> 17 tools)

- `indicators.py` - SMA/EMA/RSI/MACD/Bollinger/ORB, pure math.
- `yahoo_auth.py` - cookie+crumb session, cached, refresh-once-on-401.
- `events.py` - earnings date + analyst mix (Yahoo), DEF 14A meetings
  (EDGAR), Fed press/speeches (official RSS).
- `options.py` - OMON-style chains (crumb-authed).
- `macro.py` - Treasury yield curve (keyless), BLS unregistered tier,
  FRED behind optional FRED_API_KEY.
- `screener.py` - SEC-XBRL-based screener, curated ~45-name universe,
  per-day disk cache, ONE companyfacts fetch per symbol (multi-MB).
- `risk.py` - vol/drawdown/Sharpe for a personal portfolio.
- `market.py` - Quote grew history_high/low/volume (for ORB).
- `fundamentals.py` - shares outstanding from dei taxonomy (market cap).
- Dashboard: TradingView advanced-chart embed in DES (their full study
  library), STUDIES + EVENTS panels, and 4 new screens: EQS, OPT, ECO,
  PF (localStorage personal portfolio). F1-F9 chips.
- MCP: +get_corporate_events, get_fed_calendar, get_macro_snapshot,
  screen_securities, get_options_chain, analyze_portfolio_risk.

## Live-found bugs this session

1. **Treasury OData namespaces**: values nest under `<m:properties>`
   (metadata ns); parser AND its hand-built fixture both wrongly used
   the d: ns -> tests green, live empty. Rewrote with local-name
   matching; fixture now copies the real feed. Full curve verified live.
2. **TradingView embed URL fails silently**: wrong (plausible) script
   host = no iframe, no console error. Correct:
   `s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js`.
3. Screener originally fetched companyfacts twice per symbol (metrics +
   shares) - halved to one fetch before first release.

## Verified live (browser + curl + MCP call_tool)

- DES NVDA: TradingView iframe, SMA20 202.33 / SMA50 209.66 / RSI 41.95
  / MACD -4.13, next earnings 2026-08-26, analyst "buy" (10/48/2/1/0).
- ORB AAPL during market hours: ABOVE_RANGE +0.87%.
- OPT AAPL: 23 expirations, 42 calls / 34 puts, sane IV/OI.
- ECO: 9-point curve for 2026-07-06 (10y 4.48%), real BLS CPI 335.123 /
  unemployment 4.2 / payrolls, 20 Fed items (Waller speech first).
- EQS (AAPL,MSFT,KO, P/E<=40): correctly passed MSFT 28.4 & KO 27.3 and
  filtered AAPL (41.9).
- /api/risk: 2-position portfolio, Sharpe 0.93.

## Still open / next

- FRED path is built but untested with a real key (user hasn't made one).
- Screener universe: consider a maintained-in-repo S&P 500 list or
  letting the dashboard pass the consensus/13F tickers as universe.
- Form 4 insider transactions remains the top "who purchased what" add.
- Schwab/brokerage: explicitly deferred by user ("not now").

---

# Session 2026-07-06 (part 2): full terminal screens + MCP server

## What was asked

"Add all the stuff available in a Bloomberg terminal... this is gonna be
open source where anyone can plug it to their AI."

Scoped honestly: Bloomberg's licensed feeds (real-time L2, chat,
execution) can't be replicated free; built the classic *screens* that can
be, plus an MCP server for the "plug into AI" part.

## What was built

- `views.py` - shared view layer. Flask endpoints and MCP tools are both
  thin wrappers over the same functions, so browser and AI see identical
  data. `Services` bundles all clients; `DashboardServices` aliases it.
- `fundamentals.py` (FA) - SEC XBRL companyfacts, ticker->CIK via SEC's
  company_tickers.json. Annual 10-K metrics only; a >=300-day duration
  check drops the quarterly comparatives 10-Ks also tag.
- `views.holders_view` (HDS) - which tracked managers hold a ticker;
  resolves every preset CUSIP once (disk-cached), ~1 min first run.
- `dashboard.html` v2 - command bar (`AAPL DES`, `MSFT FA`, `KO HDS`,
  `buffett PORT`, `MKTS`, `WATCH`, `HELP`), five screens, clickable
  tickers everywhere, range-selectable SVG chart, watchlist in
  localStorage.
- `mcp_server.py` + `howlet mcp` - FastMCP stdio server, 11 tools,
  optional dep (`pip install "edgar[mcp]"`).
- New CLI: `facts`, `holders`, `mcp`. Tests 37 -> 48, all offline.

## Live-found bug #3: day-change semantics

Yahoo's `chartPreviousClose` is the close before the *range start*, so
`change_pct` was actually range drift (AAPL "+10.18%" was a 5-day move;
part 1's portfolio %CHG column was showing 1-month moves). Fix: with
daily bars, previous close = second-to-last bar; the DES stats fetch a
separate daily quote and show CHG (1D) and CHG (RANGE) as distinct rows.

## Verified live

- DES AAPL: px 312.66, +1.31% (1d) vs +20.10% (6mo), 52w 201.5-317.4,
  123 chart bars, FA showing Apple's real FY2021-2025 (FY2024 rev
  $391.0B / EPS 6.08 - matches the actual 10-K), HDS showing Berkshire's
  227.9M shares / $57.84B / 22% weight.
- MCP: `call_tool("get_quote", ...)` returned real AAPL + ^GSPC data.
- MKTS/WATCH screens render from live Yahoo data.

---

# Session 2026-07-06 (part 1): Bloomberg-style dashboard + market data + news

## What was asked

"Add a Bloomberg-style dashboard, with functionality exceeding Bloomberg,
and add sources like Yahoo Finance and other finance sources for market
info and accurate news."

## What was built (all free/keyless, per the standing constraint)

- `market.py` - Yahoo Finance v8 chart endpoint client (`Quote` with
  price, prev close, 1-mo sparkline). All failures -> `None`, never raise.
- `tickers.py` - `CusipTickerResolver`: OpenFIGI keyless mapping of 13F
  CUSIPs to Yahoo tickers, batches of 5 @ 3s, disk-cached forever in
  `~/.howlet/cusip_tickers.json` (network failures NOT cached).
- `news.py` - RSS aggregation: Yahoo Finance (market + per-ticker), CNBC,
  MarketWatch, SEC press releases. Broken feeds skipped, deduped, sorted.
- `consensus.py` - the old wishlist #1: cross-manager CUSIP overlap with
  per-manager portfolio weights (`howlet consensus`).
- `cache.py` - old wishlist #2: holdings cached by accession number under
  `~/.howlet/holdings/`; wired into CLI, dashboard, consensus.
- `dashboard.py` + `dashboard.html` - Flask JSON API + single-file dark
  terminal UI (`howlet dashboard`, port 8813). World tape, portfolio w/
  live px + sparklines + weights, Q/Q changes, allocation bars, consensus
  panel, news panel scoped to held tickers. `.claude/launch.json` exists
  for the Claude Code preview panel.
- New CLI commands: `quote`, `news`, `consensus`, `dashboard`. New dep:
  flask. Tests went 11 -> 37, all offline/mocked.

## Live-found bugs (why live verification keeps paying off)

1. **13F `<value>` units were wrong by 1000x.** The field was named
   `value_usd_thousands` and displayed as "$000s", but since SEC's Jan
   2023 amendment filers report *whole dollars* - Berkshire's reported
   total (263,095,703,570) only makes sense as $263B, not $263T. Renamed
   to `value_usd` everywhere and fixed all labels. Pre-2023 filings DID
   use thousands; documented in the `Holding` docstring.
2. **OpenFIGI's first listing for a CUSIP isn't always the US ticker.**
   Chevron's CUSIP returned stale "CHV" before the US-composite "CVX";
   Yahoo has no CHV quote. `_extract_tickers` now prefers
   `exchCode == "US"` (regression test added).

## Verified live (browser + curl against the running dashboard)

- Buffett portfolio: Q1 2026 filing, 29 positions, $263.10B total, AAPL
  $57.84B @ 22% wt, real quotes + sparklines for 24/25 top names.
- Chubb (Swiss issuer) has no keyless OpenFIGI US mapping -> renders
  tickerless with no price, by design. Candidate fix: name-based fallback
  via SEC's `company_tickers.json`.
- Consensus found GOOGL held by buffett + ackman. News panel pulled real
  per-ticker headlines. Tape pulled indices/futures/crypto/FX.
- First portfolio load of a manager is slow (~20s: OpenFIGI keyless
  throttle); subsequent loads are instant thanks to both caches.

---

# Session 2026-06-30 (previous)

This file is the narrative of *what happened and why* in the
working session, 2026-06-30.

## What was asked

1. Dockerize the CLI (previous ask, already done before this segment).
2. "Nothing going through my head, go ahead and finish" - i.e. use
   judgment to close out the open items and hand back a clean state.

## What I did, in order

### 1. Verified the live SEC API path for the first time ever

This scaffold was originally built offline with no network access, so
nothing had ever round-tripped against real sec.gov servers. Built a
`Dockerfile` + `.dockerignore`, then ran `howlet search berkshire` and
`howlet holdings buffett` live via `docker run`.

**Found a real bug immediately:** `search_company_cik` parsed
`output=atom` from `/cgi-bin/browse-edgar`, but SEC's atom feed has a
server-side bug where `<entry title="...">` renders as a stringified Perl
array ref (`"ARRAY(0x55d6f0feff88)"`) instead of the company name. The
offline mocked tests never caught this because the mock XML was hand-built
correctly. Fixed by switching to parsing the default HTML results table
(`tree.xpath('//table[@class="tableFile2"]/tr[...]')`), verified against
live data, and added a regression test
(`test_search_company_cik_parses_html_table`) using a real anonymized HTML
fixture so this doesn't silently regress.

`holdings buffett` worked correctly on the first live try - XML namespace
handling and submissions JSON parsing were both right as originally built.

### 2. Closed out the three "not done" items from CLAUDE.md

**Retry/backoff** (`client.py::_get`): now retries up to 3 times on
429/5xx with exponential backoff, honoring `Retry-After` if present.
Non-retryable 4xx (404, etc.) still raise immediately - no wasted retries
on client errors. The existing ~10 req/sec self-throttle was left alone
per the CLAUDE.md constraint against removing it for speed.

**Pagination** (`client.py::list_13f_filings`): before touching code,
fetched a real long-history filer's submissions live (Icahn, CIK 921669)
to confirm the actual shape of `filings["files"][]` rather than guessing
from docs. Confirmed: each `files[]` entry names a JSON page at
`data.sec.gov/submissions/{name}`, and that page is a **flat dict** with
the same array-of-arrays shape as `recent` - *not* nested under a
`"filings"` key like `recent` is. `list_13f_filings` now walks `recent`
first, then those pages in filing-date order, stopping once `limit` 13F-HR
filings are collected.

**Quarter-over-quarter diffing** - this was CLAUDE.md's #1 "actually
interesting feature," so built it:
- `src/howlet/diff.py::diff_holdings(prior, current)` - pure function,
  no HTTP. Aggregates `Holding`s by CUSIP *within* each filing first
  (necessary: Berkshire's own 13F lists AAPL across 5 separate infoTable
  entries in one filing, split some other way internally), then compares
  the two aggregated snapshots and classifies each CUSIP as NEW / SOLD /
  INCREASED / DECREASED / UNCHANGED.
- `HoldingChange` dataclass added to `models.py`.
- `howlet diff <cik-or-preset>` CLI command, with `--csv` and
  `--show-unchanged` (unchanged positions are hidden by default - noise).
- Verified live: `howlet diff buffett` correctly diffed Berkshire's
  Q4 2025 -> Q1 2026 filings. Notably it correctly surfaced Alphabet
  (GOOGL/GOOG) and Lennar (LEN/LEN.B) as *two separate rows each* - these
  are genuinely different CUSIPs for different share classes, so that's
  correct output, not a duplicate-row bug. Worth remembering if it looks
  surprising later.

### 3. Test suite

Went from 4 tests to 11, all offline/mocked, all passing:
- `tests/test_client.py` - added pagination, retry-then-succeed,
  retry-exhausted, and non-retryable-4xx cases, plus the earlier HTML
  search-parsing regression test.
- `tests/test_diff.py` (new) - classification of all 5 statuses, and the
  multi-infoTable-per-CUSIP aggregation case.

Run with:
```bash
docker run --rm -v "$(pwd):/app" --entrypoint sh howlet:latest \
  -c "pip install -q pytest responses && python -m pytest -v"
```
(or locally: `pip install -e ".[dev]" && pytest -v`)

## Current state

- Docker image builds clean: `docker build -t howlet:latest .`
- 11/11 tests pass offline.
- `search`, `holdings`, and `diff` all verified against the live SEC API
  this session, not just offline mocks.
- `EDGAR_USER_AGENT` used for live testing: `"Vineeth Mudda
  vineethmudda@gmail.com"` (matches the user's email on file).

## What's still open

From CLAUDE.md, one item remains:
- **Pre-2013ish filers using `.txt` SGML instead of XML** for the
  information table - still untested. `get_information_table` should
  raise a clear error on these (by design) rather than silently failing,
  but that path has never been exercised against a real old filing. If
  picking this up: find an old 13F-HR (pre-~2013) via `howlet search`,
  fetch its filing index live, and confirm the error message is actually
  useful rather than a raw parse traceback.

Next features, in the order CLAUDE.md now recommends (updated this
session since diffing is done):
1. Multi-manager comparison ("which stock do the most famous investors
   agree on right now") - could reuse `diff_holdings`'s CUSIP-aggregation
   pattern across N managers instead of 2 filings.
2. Simple caching layer (sqlite or JSON keyed by accession number) -
   filings are immutable once filed, so repeated `diff`/`holdings` calls
   are needlessly re-fetching the same XML.
3. Expand `presets.py` beyond the current 5 - verify each new CIK via
   `howlet search` first, don't guess.
4. If heading toward public release: GitHub Actions (lint + pytest on
   push), a CHANGELOG, PyPI publishing.

## Gotchas worth remembering

- **SEC's `output=atom` company search is broken server-side.** Don't
  revert to it. The HTML table is the reliable source for company-name
  search results.
- **A single 13F can list one CUSIP multiple times.** Always aggregate by
  CUSIP within a filing before doing anything quarter-over-quarter or
  ranking-related. `diff.py::_aggregate_by_cusip` is the reference
  implementation if this comes up elsewhere.
- **`files[]` pagination pages are flat, `recent` is nested.** Both live
  under `data["filings"]`, but `recent` is `data["filings"]["recent"]`
  while a fetched page *is* the block directly (no `["filings"]["recent"]`
  wrapper on the paginated page itself).
- Docker Desktop on this machine has occasionally evicted a freshly built
  local image between commands (`docker images` came up empty after a
  successful build+run). If `docker run` says "pull access denied" for a
  clearly-local tag, just rebuild - it's fast because layers cache.
