# Changelog

All notable changes to Howlet. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver
(pre-1.0: minor bumps may include breaking changes).

## [0.8.1] - 2026-11-20

### Added
- **`howlet --version`** prints the installed version (0.8.1).
- **CLI `holdings` shows tickers and prices** alongside issuer/value/
  shares (CUSIPs resolve through the OpenFIGI disk cache; prices come
  from one batched Yahoo call). `--csv` gains `ticker` and `price`
  columns.
- **Screener consensus universe**: `/api/screener?universe=consensus`
  (and the MCP `screen_securities` tool's `universe_source="consensus"`)
  screens what the tracked 13F managers hold, built from their latest
  filings, instead of the hardcoded ~45-name list. Falls back to the
  default list when no manager portfolio loads.
- **Feed-health indicator**: `/api/news/health` reports every RSS feed's
  status with a last-ok timestamp (`ok`/`failed`/`never`), and `howlet
  news` prints which feeds are down. A dead feed is now visible instead
  of indistinguishable from "no news today".
- **Paper fees/slippage** (off by default): a flat fee per fill
  (`HOWLET_PAPER_FEE_USD`) and slippage in basis points
  (`HOWLET_PAPER_SLIPPAGE_BPS`, buys fill higher, sells lower; limit
  orders never fill past their limit). The account summary reports
  `fees_paid`; costs survive a reset.
- **Top-level paper exports**: `from howlet import PaperStore, PaperError`
  now works.
- **Frontend CI job**: the `frontend` job runs `npm ci && npm run build
  && npm test` on every push/PR (the 45 vitest files finally run
  automatically).

### Changed
- **13F correctness**: option rows (puts/calls) are parsed and excluded
  from equity totals instead of counting as long stock; pre-2023
  `<value>` figures are scaled x1000 (the SEC reported in thousands
  before 2023); `howlet diff --adjust-splits` adjusts prior shares for
  stock splits; 13F-HR/A amendments win over the original filing;
  defensive parsing for malformed 13F/options/BLS/FRED rows.
- **Risk**: histories align on common dates before portfolio math, and
  the Sharpe ratio uses the 3-month T-bill yield instead of 0.0.
- **Robustness**: malformed dashboard params return JSON 400 instead of
  an HTML 500; the Yahoo crumb retries after a transient failure; one
  broken manager no longer kills consensus and one bad symbol no longer
  kills a screen; NPORT resolves its primary doc from the filing index
  and is disk-cached; the screener cache writes once per run.
- **Paper trading**: GET endpoints settle in memory only and never save
  (a dashboard refresh can't fill orders); cross-process file lock +
  atomic saves; the dashboard binds `127.0.0.1` by default, is served by
  waitress (not the Flask dev server), runs as a non-root user in Docker,
  and token auth (`HOWLET_DASHBOARD_TOKEN`) guards paper writes. MCP
  paper orders are capped at $10,000 per order / $25,000 per day.
- **Performance**: EDGAR locking is per-manager/per-endpoint instead of
  one global lock, and quotes are batched (up to 25 symbols per Yahoo
  request).
- **Lint**: ruff now checks E/W/I/UP/B/SIM/C4 (was only E4/E7/E9/F);
  line length (E501) stays unenforced on purpose.
- **Docs**: the "145 tests" count (stale since the suite grew) now reads
  the real number; the dashboard's startup banner says HOWLET, not
  "EDGAR TERMINAL".

### Fixed
- Duplicate `## [0.8.0]` CHANGELOG sections merged; the two logo files
  consolidated to the 69KB version; dead `YieldCurvePoint` and
  `TICKER_FEED_URL` removed; `resolve_cik` deduplicated; CLI `holdings
  --limit` lists all N recent filings instead of ignoring the option.

## [0.8.0] - 2026-07-17

### Added
- **N-PORT fund holdings** (`nport.py`): what any SEC-registered ETF or
  mutual fund holds, from its latest monthly NPORT-P filing - exact
  balances, values, and the fund's own weight percentages. CLI
  `howlet fund ARKK` (with `--csv`), `/api/fund/<symbol>`, MCP tool
  `get_fund_holdings`, and an ETF/FUND HOLDINGS dashboard block.
  Ticker->series mapping via SEC's `company_tickers_mf.json`; unit
  investment trusts (SPY) don't file NPORT-P and error clearly.
- **EDGAR full-text search** (`fulltext.py`): search the CONTENT of all
  filings since 2001 (official efts.sec.gov index). CLI `howlet fts
  '"phrase"' --forms 8-K`, `/api/fulltext`, MCP tool
  `search_filing_text`.
- **Company filings feed**: any company's recent SEC filings (8-K,
  10-K/Q, proxies, ...), newest first with document links. CLI
  `howlet filings AAPL --form 8-K`, `/api/filings/<symbol>`, MCP tool
  `get_company_filings`, and a SEC FILINGS dashboard block.
- **Insider-buy screening**: scan a whole symbol list for open-market
  insider purchases (Form 4 code P). CLI `howlet insider-buys AAPL
  MSFT ...`, `/api/insider-buys`, MCP tool `screen_insider_buys`, and a
  watchlist-scoped INSIDER BUYS dashboard block.
- **New-filing alerts**: the dashboard polls tracked managers' latest
  13F accessions (on load + every 30 min); a topbar bell badges new
  filings and (opt-in) fires desktop notifications. MCP tool
  `get_latest_filings` for agents.
- **FX cross-rate matrix** (`fx.py`): ECB daily reference rates via the
  keyless Frankfurter API, derived cross rates for 9 majors.
  `/api/fx`, MCP tool `get_fx_matrix`, FX CROSS-RATE MATRIX block.
- **Crypto market screen** (`crypto.py`): CoinGecko keyless top-50 by
  market cap with automatic Coinpaprika fallback, 60s cache. MKTS
  screen gained a STOCKS/CRYPTO toggle (crypto left the stocks
  sections), plus a CRYPTO TOP 20 dashboard block and `/api/crypto`.
- **SEC rulemaking on ECO** (`regulatory.py`): newest SEC rules,
  proposed rules, and notices from the official Federal Register API
  (keyless). `/api/regulatory` + MCP tool.
- **`howlet warm`**: pre-fetch every tracked manager's latest 13F and
  map all CUSIPs so the dashboard's first consensus/holders load is
  instant. Cron-able; skips everything already cached.
- **State backup**: EXPORT/IMPORT buttons in the dashboard tab bar
  save/restore ALL terminal state (layouts, watchlists, portfolio,
  snapshots) as a JSON file - localStorage is no longer a single point
  of loss.
- **CSV export buttons** on the portfolio, Q/Q changes, consensus, and
  screener panels.
- Per-widget resize toggles (wide/tall) and named layout snapshots
  (SAVE/LOAD/DEL) in the dashboard tab bar.
- Ruff linting in CI (plus offline HTML smoke tests for the dashboard).

### Changed
- **Project renamed to Howlet** (a howlet is a small owl). Formerly
  edgar13f, briefly edgar - but PyPI's `edgar` name belongs to an
  unrelated library whose module is also `edgar`, an import collision
  waiting to happen. Now: `pip install howlet`, `import howlet`, CLI
  `howlet`, cache dir `~/.howlet`, MCP server name `howlet`. The
  dashboard migrates old browser state (edgar13f_*/edgar_* localStorage
  keys) automatically and never overwrites.
- MKTS stocks view no longer includes the 5 hardcoded crypto symbols
  (the CRYPTO toggle replaces them with real market-cap data).
- The top command bar dropped its placeholder hint text.
- `EdgarClient.list_filings(cik, form_type, limit)` generalizes
  `list_13f_filings` to any form type (or all forms with `None`);
  `FilingSummary` gained a `form` field.
- MCP server: 19 -> 27 tools.

## [0.7.0] - 2026-07-17

### Added
- **Form 4 insider transactions** (`form4.py`): CLI `howlet insiders
  AAPL`, `/api/insiders/<symbol>`, MCP tool
  `get_insider_transactions`, and an INSIDER TRANSACTIONS dashboard
  block. Non-derivative rows only; open-market purchases (P) and
  sales (S) are flagged as the signal. Parsed filings are disk-cached
  by accession number like 13F holdings.
- **13F position history**: CLI `howlet history buffett AAPL`,
  `/api/position-history/<manager>/<query>`, MCP tool
  `get_position_history`, and a 13F POSITION HISTORY dashboard block
  with per-quarter value bars - one manager's stake in one name across
  N quarters. Query by ticker, CUSIP, or issuer-name substring.
- **10 new tracked managers** (now 14): Tepper/Appaloosa, Klarman/
  Baupost, Loeb/Third Point, Dalio/Bridgewater, Druckenmiller/
  Duquesne, Marks/Oaktree, Li Lu/Himalaya, Einhorn/DME (Greenlight's
  successor filer), Fundsmith, Tiger Global. Every CIK verified live
  against a current (Q1 2026) 13F-HR.
- **Name-based ticker fallback**: CUSIPs OpenFIGI's keyless tier can't
  map (e.g. Chubb's H1467J104) now resolve by matching the 13F issuer
  name against SEC's `company_tickers.json`; learned mappings persist
  in the resolver's disk cache.

### Fixed
- `search_company_cik` now handles EDGAR's exact-match redirect (the
  single-company filing-list page), which previously parsed as garbage
  `{"name": "Documents", "cik": None}` rows.

## [0.6.0] - 2026-07-07 and earlier

Pre-changelog history - see `HANDOVER.md` for the session-by-session
record. Highlights: 13F client/CLI (search, holdings, diff, consensus,
holders), Bloomberg-style web dashboard with customizable widget tabs,
vendored KLineChart (Apache-2.0) charting with indicators + drawing,
quotes/world markets (Yahoo v8), SEC XBRL fundamentals, screener, news
(7 RSS feeds), corporate events, Treasury/BLS/FRED macro, portfolio
risk, options (experimental), MCP server, Docker, GitHub Actions CI.
