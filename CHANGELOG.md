# Changelog

All notable changes to edgar13f. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver
(pre-1.0: minor bumps may include breaking changes).

## [0.8.0] - 2026-07-17

### Added
- **N-PORT fund holdings** (`nport.py`): what any SEC-registered ETF or
  mutual fund holds, from its latest monthly NPORT-P filing - exact
  balances, values, and the fund's own weight percentages. CLI
  `edgar13f fund ARKK` (with `--csv`), `/api/fund/<symbol>`, MCP tool
  `get_fund_holdings`, and an ETF/FUND HOLDINGS dashboard block.
  Ticker->series mapping via SEC's `company_tickers_mf.json`; unit
  investment trusts (SPY) don't file NPORT-P and error clearly.
- **EDGAR full-text search** (`fulltext.py`): search the CONTENT of all
  filings since 2001 (official efts.sec.gov index). CLI `edgar13f fts
  '"phrase"' --forms 8-K`, `/api/fulltext`, MCP tool
  `search_filing_text`.
- **Company filings feed**: any company's recent SEC filings (8-K,
  10-K/Q, proxies, ...), newest first with document links. CLI
  `edgar13f filings AAPL --form 8-K`, `/api/filings/<symbol>`, MCP tool
  `get_company_filings`, and a SEC FILINGS dashboard block.
- **Insider-buy screening**: scan a whole symbol list for open-market
  insider purchases (Form 4 code P). CLI `edgar13f insider-buys AAPL
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
- **`edgar13f warm`**: pre-fetch every tracked manager's latest 13F and
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

### Changed
- MKTS stocks view no longer includes the 5 hardcoded crypto symbols
  (the CRYPTO toggle replaces them with real market-cap data).
- The top command bar dropped its placeholder hint text.
- `EdgarClient.list_filings(cik, form_type, limit)` generalizes
  `list_13f_filings` to any form type (or all forms with `None`);
  `FilingSummary` gained a `form` field.
- CI now runs ruff alongside the offline test suite; dashboard HTML has
  a smoke test.

## [0.8.0] - 2026-07-17

### Added
- **Insider-buy screening** (`edgar13f insider-buys AAPL MSFT ...`,
  `/api/insider-buys`, MCP `screen_insider_buys`, watchlist-scoped
  INSIDER BUYS dashboard block): open-market Form 4 purchases (code P)
  across a symbol list, with per-symbol rollups.
- **N-PORT fund holdings** (`nport.py`; `edgar13f fund ARKK`,
  `/api/fund/<symbol>`, MCP `get_fund_holdings`, ETF/FUND HOLDINGS
  block): what an ETF/mutual fund holds from its latest monthly NPORT-P
  filing, with the fund's own weights. Unit investment trusts (SPY)
  error clearly - they don't file NPORT-P.
- **EDGAR full-text search** (`fulltext.py`; `edgar13f fts '"phrase"'`,
  `/api/fulltext`, MCP `search_filing_text`): search the CONTENT of all
  filings since 2001 via the official efts.sec.gov index.
- **Company filings feed** (`edgar13f filings AAPL --form 8-K`,
  `/api/filings/<symbol>`, MCP `get_company_filings`, SEC FILINGS
  block): any company's recent filings, newest first, with links.
- **New-13F-filing alerts**: the dashboard's topbar bell polls
  `/api/filing-alerts` (MCP: `get_latest_filings`) every 30 minutes and
  flags tracked managers' brand-new filings; optional desktop
  notifications; MARK ALL SEEN to acknowledge.
- **Crypto market data** (`crypto.py`): CoinGecko keyless tier with
  automatic Coinpaprika fallback and a 60s cache. Powers the MKTS
  STOCKS/CRYPTO toggle screen and a CRYPTO TOP 20 block.
- **FX cross-rate matrix** (`fx.py`; `/api/fx`, MCP `get_fx_matrix`,
  FX CROSS-RATE MATRIX block): ECB daily reference rates via
  Frankfurter (api.frankfurter.dev), cross rates derived from one call.
- **SEC rulemaking on ECO** (`regulatory.py`; `/api/regulatory`, MCP
  `get_sec_rulemaking`): newest SEC rules/notices from the official
  Federal Register API.
- **`edgar13f warm`**: pre-fetches every tracked manager's latest 13F
  and maps all CUSIPs so the dashboard's first consensus/holders load
  is instant. Cron-able; safe to re-run.
- **EXPORT/IMPORT state backup** in the dashboard tab bar: download all
  terminal state (layouts, watchlists, portfolio, seen-filings) as one
  JSON file and restore it in any browser.
- **CSV export buttons** on the portfolio, Q/Q changes, consensus, and
  screener tables.
- ruff linting in CI (plus offline HTML smoke tests).

### Changed
- The MKTS screen's crypto section moved out of the stocks grid and
  behind a STOCKS/CRYPTO toggle backed by real market-cap data (was 5
  hardcoded Yahoo symbols mixed into the world grid).
- The command input's placeholder example text was removed (HELP/F9
  remains the cheat sheet).
- MCP server: 19 -> 27 tools.

## [0.7.0] - 2026-07-17

### Added
- **Form 4 insider transactions** (`form4.py`): CLI `edgar13f insiders
  AAPL`, `/api/insiders/<symbol>`, MCP tool
  `get_insider_transactions`, and an INSIDER TRANSACTIONS dashboard
  block. Non-derivative rows only; open-market purchases (P) and
  sales (S) are flagged as the signal. Parsed filings are disk-cached
  by accession number like 13F holdings.
- **13F position history**: CLI `edgar13f history buffett AAPL`,
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
