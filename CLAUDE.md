# CLAUDE.md - dev brief for edgar13f

## What this is

A free, no-API-key, open-source Bloomberg-style terminal built on SEC
EDGAR 13F data ("what is Warren Buffett buying"), grown into a full
market terminal: web dashboard (`edgar13f dashboard`), CLI, Python
library, and an MCP server (`edgar13f mcp`, 27 tools) so any AI agent
can drive it. Everything is verified live against the real APIs, not
just offline mocks - that habit has caught a real bug almost every
session (see Gotchas).

See `HANDOVER.md` for the full session-by-session history of what was
built, why, and what broke along the way. `README.md` is the user-facing
doc. Tests: `pytest tests/` - all offline/mocked.

## Module map (src/edgar13f/)

| Module | What it does |
| --- | --- |
| `client.py` | SEC EDGAR client: CIK search, 13F filings (paginated), info-table XML parsing, retry/backoff, ~10 req/s self-throttle |
| `models.py` | `FilingSummary`, `Holding` (values in whole USD - see Gotchas), `HoldingChange` |
| `diff.py` | Q/Q holdings diff by CUSIP (aggregates multi-entry CUSIPs first) |
| `form4.py` | Form 4 insider transactions: issuer CIK -> ownershipDocument XML, non-derivative rows only (P/S = the open-market signal) |
| `consensus.py` | Cross-manager "smart money consensus" over `presets.py` |
| `cache.py` | Parsed holdings + Form 4 transactions cached by accession number (filings are immutable) |
| `tickers.py` | CUSIP->ticker via OpenFIGI keyless tier, disk-cached forever, prefers US composite listing; misses fall back to SEC company_tickers.json name matching (`views._apply_name_fallback` + `fundamentals.name_to_ticker`) |
| `market.py` | Yahoo v8 chart endpoint (keyless): quotes, full OHLCV history, world tape |
| `fundamentals.py` | SEC XBRL companyfacts: annual 10-K metrics, shares outstanding (dei) |
| `indicators.py` | Pure-math studies: SMA/EMA/RSI/MACD/Bollinger/ORB |
| `risk.py` | Pure-math portfolio risk: volatility, max drawdown, Sharpe |
| `screener.py` | Screener over a curated universe (SEC fundamentals + chart quotes only) |
| `news.py` | RSS aggregation: Yahoo/CNBC/CNBC Earnings/MarketWatch/Google News/Seeking Alpha/SEC; per-ticker feeds |
| `events.py` | Earnings date + analyst mix (Yahoo, crumb-authed), DEF 14A proxies (EDGAR), Fed RSS |
| `options.py` | Options chains (Yahoo, crumb-authed) - EXPERIMENTAL, de-emphasized per user |
| `macro.py` | Treasury yield curve (keyless), BLS unregistered tier, FRED (optional key) |
| `crypto.py` | Top coins by market cap: CoinGecko keyless tier, Coinpaprika fallback, 60s TTL cache; degrades to empty |
| `regulatory.py` | SEC rulemaking/notices from the Federal Register API (keyless, official); degrades to empty |
| `fulltext.py` | EDGAR full-text search (efts.sec.gov, keyless official): search filing CONTENT since 2001 |
| `fx.py` | ECB daily FX reference rates via Frankfurter (`api.frankfurter.dev/v1` - old .app domain 301s); derived cross-rate matrix, 1h cache; degrades to {} |
| `nport.py` | N-PORT fund holdings: ticker->series via company_tickers_mf.json, series-scoped browse-edgar for accessions, primary_doc.xml parse. UITs (SPY) have no NPORT trail |
| `yahoo_auth.py` | Yahoo cookie+crumb workaround for walled endpoints; consumers must degrade, never raise |
| `views.py` | Shared JSON view layer - Flask endpoints AND MCP tools both wrap these |
| `dashboard.py` | Flask wiring only; UI lives in `dashboard.html` (single file, vanilla JS) |
| `mcp_server.py` | FastMCP stdio server, 21 tools (optional dep: `pip install "edgar13f[mcp]"`) |

## Hard rules

- **No required API key, ever.** FRED (`FRED_API_KEY`) and OpenFIGI
  (`OPENFIGI_API_KEY`) are optional enrichers; everything must work
  without them. Never add a paid wrapper as a default path.
- **Always require a real User-Agent with contact email** for SEC
  (`EDGAR_USER_AGENT`). Don't relax the validation in `EdgarClient`.
- **Keep every self-throttle**: SEC ~10 req/s, Yahoo 0.25s, OpenFIGI
  3s/batch keyless. Good-citizen behavior, not a technical limit.
- **SEC data is authoritative; market data is decoration.** Yahoo/
  OpenFIGI/RSS failures must degrade to missing values or "unavailable",
  never break the 13F views. Anything built on `yahoo_auth.py` (events,
  options) is the fragile tier and must never raise.
- **No paywalled or proprietary components in the UI.** Charting is
  KLineChart (Apache-2.0) - TradingView was removed because its free
  widget caps stacked indicators behind a subscription.
- **Verify live before calling anything done.** Offline mocks have
  repeatedly agreed with the code and disagreed with reality.

## Gotchas (each cost a live debugging session - don't re-learn them)

- **13F `<value>` is whole dollars post-Jan-2023** (SEC amendment).
  Pre-2023 filings used thousands - old filings would read 1000x low.
- **SEC's `output=atom` company search is broken server-side** (Perl
  array refs in titles). Parse the HTML table instead. And an
  exact-match query skips the results table entirely (renders that
  company's filing list) - `search_company_cik` reads the
  `span.companyName` header on that layout.
- **Famous managers migrate filer entities.** Appaloosa Management LP
  (1006438) stopped filing in 2016 (now Appaloosa LP, 1656456);
  Greenlight's 1079114 stopped after 2023 (now DME Capital, 1489933).
  When adding a preset, check its latest 13F-HR is CURRENT, not just
  that the name matches.
- **One filing can list one CUSIP many times** (Berkshire lists AAPL
  5x). Always aggregate by CUSIP first. Alphabet GOOGL/GOOG and Lennar
  LEN/LEN.B as separate rows are CORRECT (different CUSIPs).
- **Submissions pagination**: `filings.files[]` pages are flat dicts,
  `recent` is nested. Both under `data["filings"]`.
- **OpenFIGI's first listing isn't always the US ticker** (Chevron
  returns stale "CHV" before "CVX"). Prefer `exchCode == "US"`;
  normalize BRK/B -> BRK-B for Yahoo.
- **Yahoo `chartPreviousClose` is the close before the RANGE start**,
  not yesterday - naive change_pct shows range drift as a day move.
  With daily bars use the second-to-last bar as previous close.
- **Yahoo walled off v7/quote, v10/quoteSummary, v7/options** behind
  cookie+crumb (see `yahoo_auth.py`). The v8 chart endpoint is still
  open - the screener deliberately uses only that plus SEC data.
- **Treasury's OData feed**: values are under `<m:properties>` (metadata
  namespace). Parse by local tag name; a namespace-based parser AND its
  hand-built fixture both had the same bug once (tests green, live {}).
- **XBRL 10-Ks tag quarterly comparatives too** - filter duration
  entries to >=300-day spans or Q4 values masquerade as annual.
- **KLineChart is vendored** at `static/klinecharts.min.js` (+ LICENSE),
  served by Flask's default `/static/` - no CDN at runtime. (When it was
  CDN-loaded: the path is `dist/umd/...`; plain `dist/` 404s silently.)
- **SEC resets stale keep-alive connections** on long-lived sessions
  (WinError 10054) - `_get` retries ConnectionError like a 5xx, and the
  Flask app maps every `requests.RequestException` to a JSON 502 (an
  HTML error page shows as "Unexpected token '<'" in the widgets).
- **Form 4 `primaryDocument` carries an XSL viewer prefix**
  (`xslF345X06/form4.xml`) - the raw XML is the bare filename in the
  filing folder. Prices can be footnote-only (RSU vests) -> None, and
  the same filing's derivativeTable would double-count the vest if
  parsed alongside the non-derivative rows.
- **TradingView-style embeds fail silently on a wrong script URL** - no
  console error, no iframe. Verify third-party URLs with curl first.
- **Date-only strings (e.g. Federal Register `publication_date`) must
  not go through `new Date(...)` display formatting** - JS parses them
  as UTC midnight, so US timezones render the previous day.
- Docker Desktop here sometimes evicts freshly built images; rebuild.

## Caches (all under `~/.edgar13f/`)

`holdings/` (by accession, immutable), `form4/` (same), `cusip_tickers.json` (forever;
network failures are NOT cached), `screener_cache.json` (per ticker per
day). Browser localStorage holds watchlists, personal portfolio, layout.

## Status

Working and verified live: **customizable HOME dashboard** (blank slate,
"+ ADD BLOCK" widget picker with 12 block types, "+ TAB" user tabs,
per-block resize toggles (wide/tall), named layout snapshots
(SAVE/LOAD/DEL in the tab bar, `edgar13f_layouts_v1`), multiple named
watchlists with scoped news/events, all in localStorage,
"RESTORE CLASSIC LAYOUT" one-click preset), manager portfolios w/ live
quotes, Q/Q changes, consensus, holders (HDS), fundamentals (FA), DES
screen with vendored KLineChart (unlimited indicators + drawing) and a
BACK button, studies incl. ORB, NEWS tab (7 feeds), MY tab, MKTS with a
STOCKS/CRYPTO toggle (crypto = CoinGecko top-50 by market cap,
Coinpaprika fallback - separate spaces, remembered choice), EQS
screener, ECO (Treasury/BLS/FRED/Fed + SEC RULEMAKING from the Federal
Register), PF risk, options (experimental),
**Form 4 insider transactions** (CLI `insiders`, `/api/insiders`, MCP
tool, dashboard block), **13F position history** (CLI `history`,
`/api/position-history`, MCP tool, dashboard block w/ value bars),
**insider-buy screening** (CLI `insider-buys`, `/api/insider-buys`,
watchlist-scoped dashboard block), **new-13F-filing alerts** (topbar
bell + optional desktop notifications, 30-min poll), **EDGAR full-text
search** (CLI `fts`, `/api/fulltext`) + **company filings feed** (CLI
`filings`, `/api/filings`, SEC FILINGS block), **N-PORT fund holdings**
(CLI `fund`, `/api/fund`, ETF/FUND HOLDINGS block; ARKK verified live -
UITs like SPY correctly error), **FX cross-rate matrix** (Frankfurter/
ECB, `/api/fx`, dashboard block), **CRYPTO TOP 20 block**, **`edgar13f
warm`** cache pre-fetcher, **EXPORT/IMPORT state backup**, CSV export
buttons on the main tables, ruff in CI + HTML smoke tests, MCP
server with 27 tools, GitHub Actions CI, Docker. Presets: 14 tracked
managers (Buffett, Burry, Ackman, Icahn, Tepper, Klarman, Loeb, Dalio,
Druckenmiller, Marks, Li Lu, Einhorn/DME, Fundsmith, Tiger Global) -
every CIK verified live against a current 13F-HR.

Known-untested: FRED with a real key; pre-2013 SGML filings (should
error clearly, never exercised).

## Next features (in rough priority order)

1. **Publish** - the only remaining step needs the user's accounts:
   create the GitHub repo + push (CI will run then), and
   `twine upload dist/edgar13f-0.8.0*` to PyPI. CHANGELOG, version
   0.8.0, sdist+wheel (twine-checked), and the local git history are
   all done.
2. **N-PORT depth** - disk-cache parsed NPORT filings by accession
   (immutable, same as 13F/Form 4), fund position history across
   months, or fund-vs-13F overlap views.
3. **Finer-grained EDGAR locking** - `edgar_lock` serializes ALL EDGAR
   access; a cold consensus load still blocks the other EDGAR-backed
   panels (mitigated day-to-day by `edgar13f warm`).

## Working rules

1. Plan before touching anything. Write the goal, the steps, and the success criteria first. No edits until the plan exists.

2. Before presenting any answer, try to refute it. Check the case where it fails. If it survives, present it along with the one caveat that matters.

3. Open every reply with the result. "Done: X changed, Y verified." Never open with what you are about to do.

4. Keep replies short by default. No narrating your own process, no restating my question, no summary of what you just said.

5. Do exactly what was asked. If you notice adjacent problems, flag them in one line each. Never silently fix things outside the task.

6. Trust the live system over documentation. Before asserting anything that matters, verify it against the actual files, the actual data, the actual output.
