<p align="center">
  <img src="https://raw.githubusercontent.com/mvineethr/Howlet/main/assets/logo.png" alt="Howlet - free, open-source SEC EDGAR market terminal" width="260">
</p>

<h1 align="center">Howlet</h1>
<p align="center"><i>Free, open-source SEC EDGAR market terminal</i></p>

<p align="center">
<a href="https://pypi.org/project/howlet/"><img src="https://img.shields.io/pypi/v/howlet.svg" alt="PyPI"></a>
<a href="https://github.com/mvineethr/Howlet/actions/workflows/ci.yml"><img src="https://github.com/mvineethr/Howlet/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
</p>

A free, no-API-key Python client + CLI + **Bloomberg-style terminal
dashboard** for SEC EDGAR data — starting from **Form 13F** (the
quarterly filings that disclose what stocks institutional investors like
Berkshire Hathaway and Pershing Square hold) and grown into a full
market terminal: insider transactions, fund holdings, full-text filing
search, live quotes, and multi-source market news.

This is the same public, government-provided data source that apps like
Blossom Social, GuruFocus, and WhaleWisdom use to show "what is Warren
Buffett buying?" features. There's no API key and no cost — SEC EDGAR just
asks for a descriptive `User-Agent` header on every request.

**Data sources (all free, all keyless):**

| Source | Used for |
| --- | --- |
| SEC EDGAR | 13F holdings, quarter-over-quarter changes, filer search |
| OpenFIGI | CUSIP → ticker mapping (keyless tier, cached to disk; falls back to matching issuer names against SEC's company_tickers.json for CUSIPs the keyless tier can't map, e.g. Chubb) |
| Yahoo Finance | quotes, 1-month sparklines, index/futures/crypto tape |
| Yahoo / CNBC / MarketWatch / SEC RSS | market-wide and per-ticker news |

## Why this exists

13F filings are public record, but the raw format (XML "information
tables" buried inside filing folders, inconsistent namespaces across
decades of filers) is annoying to work with directly. This wraps that in a
small, typed Python client and a CLI.

## What it can and can't tell you

**Can:**
- Show the stock-by-stock long equity holdings a given manager reported
  in their most recent 13F-HR.
- Look up a manager's CIK by name.
- Diff two consecutive quarters' holdings — what's new, sold, or changed
  size, aggregated by CUSIP.
- Export holdings or diffs to CSV.

**Can't (these are limitations of 13F itself, not this library):**
- **No real-time data.** Filings are due 45 days after quarter-end, so
  what you see is always 1.5–4.5 months old.
- **No short positions, most options, cash, or non-US holdings.**
  13F only covers US-listed long equity positions over certain thresholds.
- **It's the fund's aggregate, not "the person."** Berkshire's 13F is
  Berkshire's filing, not Warren Buffett's personal brokerage account.

## Setup

```bash
pip install howlet
export EDGAR_USER_AGENT="Your Name your-email@example.com"
```

SEC requires that User-Agent string to include a real contact email — see
https://www.sec.gov/os/webmaster-faq#developers. Generic strings like
`python-requests` get rate-limited or blocked.

Developing on Howlet itself (editable install, test/lint extras) instead
of just using it:

```bash
git clone https://github.com/mvineethr/Howlet.git
cd Howlet
pip install -e ".[dev]"
```

## Usage

```bash
# Look up a manager's CIK by name
howlet search berkshire

# Show the latest holdings for a preset (see src/howlet/presets.py -
# 14 tracked managers: buffett, burry, ackman, icahn, tepper, klarman,
# loeb, dalio, druckenmiller, marks, lilu, einhorn, fundsmith, tigerglobal)
howlet holdings buffett
howlet holdings druckenmiller
howlet holdings tepper

# Or use a raw CIK directly
howlet holdings 1067983

# Export to CSV instead of printing a table
howlet holdings buffett --csv buffett_latest.csv

# What changed since last quarter's filing? (new/sold/increased/decreased)
howlet diff buffett
howlet diff buffett --show-unchanged
howlet diff buffett --csv buffett_changes.csv

# Which stocks do the tracked famous managers agree on right now?
howlet consensus
howlet consensus --min-managers 3 --csv consensus.csv

# Live-ish quotes from Yahoo Finance (works for stocks, indices, futures, crypto)
howlet quote AAPL BRK-B ^GSPC BTC-USD

# Market headlines (Yahoo Finance / CNBC / MarketWatch / SEC press releases)
howlet news
howlet news --symbol AAPL --symbol MSFT

# Annual fundamentals from SEC XBRL (audited 10-K data)
howlet facts AAPL

# Which tracked managers hold a ticker (Bloomberg HDS-style)
howlet holders KO

# Form 4 insider transactions - who's actually buying/selling their own stock
howlet insiders AAPL
howlet insiders NVDA --filings 25 --all

# One manager's stake in one name across quarters (watch Buffett trim AAPL)
howlet history buffett AAPL --quarters 12

# Screen a whole list for open-market insider BUYS (the conviction signal)
howlet insider-buys AAPL MSFT NVDA OXY JPM --filings 10

# What does an ETF actually hold? (latest monthly NPORT-P filing)
howlet fund ARKK
howlet fund VOO --csv voo_holdings.csv

# A company's recent SEC filings feed
howlet filings AAPL --form 8-K

# Full-text search the CONTENT of every filing since 2001
howlet fts '"supply chain disruption"' --forms 8-K

# Pre-fetch all tracked managers + ticker mappings (cron-able) so the
# dashboard's first consensus/holders load is instant
howlet warm
```

## The terminal dashboard

```bash
howlet dashboard          # then open http://127.0.0.1:8813
```

A Bloomberg-terminal-style dashboard in your browser (React + Fluent UI,
built into `src/howlet/static/app`, so no Node is needed to run it).
A rail on the left switches pages: **Home, Markets, Smart Money,
Screener, News, Portfolio, Settings**. `Ctrl+1`, `Ctrl+2`... jump to them
and `Ctrl+K` focuses the command box. There is no Back button; use the
browser's Back (Alt+Left).

**Home is yours to build.** It starts from a default layout; "Add block"
opens a dialog to pick a block type (13F portfolios for a manager, Q/Q
changes, smart-money consensus, watchlists, watchlist-scoped news and
events, Form 4 insiders, insider-buy screen, 13F position history,
company filings, ETF/fund holdings, market news, Fed & policy, the
Treasury yield curve, world markets, crypto, FX matrix and more) and
configure it. "+ Tab" adds extra Home tabs (rename or delete the active
one with the pencil and bin buttons). The Layouts menu saves the current
Home under a name, loads or deletes saved layouts, and restores the
default. Everything persists in your browser; **Settings -> Layouts &
backup** exports and imports it all as a `howlet-backup-<date>.json`
file. A topbar bell alerts you to new 13F filings from your tracked
managers (choose them, presets plus custom CIKs, in Settings -> Tracked
managers), and the owl chip on a stock shows each holder's last-quarter
action (new/added/trimmed/held). Click any symbol to open its stock page.

**Pages**

- **Markets** - Stocks, Crypto, FX and Economy tabs (indices, commodities,
  top crypto by market cap, ECB cross-rates, Treasury curve / BLS / FRED
  macro, Fed and SEC rulemaking).
- **Smart Money** - Managers, Consensus, Insider buys, Position history,
  Filing search and Funds tabs.
- **Screener** - P/E, market cap, revenue growth and net margin over a
  curated large-cap universe (CSV export).
- **News** - market wire, Fed & policy and earnings feeds.
- **Portfolio** - Watchlists, and Holdings & risk (volatility, max
  drawdown, Sharpe).
- **Stock page** - Overview, Chart, Financials, Holders, News tabs, plus
  Options (experimental, off until you enable it in Settings). The chart
  is [KLineChart](https://github.com/klinecharts/KLineChart) 9.8.12
  (Apache-2.0) from npm, bundled into `static/app`, with stackable
  indicators and drawing tools.

Tables export to CSV where an "Export CSV" button is shown (screener,
manager portfolio and changes, consensus, financials, fund holdings).

**Command box** (`Ctrl+K`):

| Command | Goes to |
| --- | --- |
| `AAPL` / `AAPL DES` | stock page, Overview |
| `AAPL GP` (or `GIP`) | Chart |
| `MSFT FA` | Financials |
| `KO HDS` | Holders |
| `AAPL CN` | stock News |
| `AAPL OPT` (or `OMON`) | Options |
| `buffett`, `buffett PORT`, or a CIK | that manager in Smart Money |
| `HOME` / `DASH` | Home |
| `MKTS` / `WEI` / `FXC` / `ECO` | Markets |
| `NEWS` / `N` / `TOP` | News |
| `EQS` | Screener |
| `PF` / `MY` / `WATCH` | Portfolio |
| `SETTINGS` | Settings |
| `HELP` / `?` / `ABOUT` / `FAQ` | Help |
| `ALERT AAPL > 350` | add a price alert |

Any CIK or preset name works, not just the managers list. First load of a
manager is slow (keyless OpenFIGI rate limits); cached afterwards.

## Plug it into your AI (MCP)

The whole terminal is also an MCP server, so Claude or any MCP-capable
agent can use it as a tool belt — ask your AI "what did Buffett buy last
quarter and how have those stocks done since?" and it can actually answer:

```bash
pip install "howlet[mcp]"

# Claude Code
claude mcp add howlet -e EDGAR_USER_AGENT="Your Name you@example.com" -- howlet mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{"mcpServers": {"howlet": {
  "command": "howlet", "args": ["mcp"],
  "env": {"EDGAR_USER_AGENT": "Your Name you@example.com"}}}}
```

Exposed tools (27): `search_manager`, `list_managers`, `get_portfolio`,
`get_portfolio_changes`, `get_consensus`, `get_holders`,
`get_position_history` (a manager's stake across quarters),
`get_insider_transactions` (Form 4), `screen_insider_buys` (open-market
P buys across a symbol list), `get_latest_filings` (new-13F detection),
`search_filing_text` (EDGAR full-text search), `get_company_filings`
(8-K/10-K feed), `get_fund_holdings` (ETF/fund NPORT-P holdings),
`get_quote`, `get_price_history` (incl. technical studies),
`get_fundamentals`, `get_news`, `get_world_markets`,
`get_crypto_markets`, `get_fx_matrix` (ECB cross rates),
`get_sec_rulemaking` (Federal Register), `get_corporate_events`,
`get_fed_calendar`, `get_macro_snapshot`, `screen_securities`,
`get_options_chain`, `analyze_portfolio_risk`.

## Data source tiers (honesty section)

Not everything here has the same reliability. Know what you're standing on:

- **Official & keyless (rock solid):** SEC EDGAR (13F, Form 4, NPORT-P
  fund holdings, XBRL fundamentals, proxy filings, full-text search),
  Treasury.gov (yield curve), Federal Reserve (RSS), BLS (25
  queries/day/IP without signup), Federal Register (SEC rulemaking on
  the ECO screen), ECB reference rates via Frankfurter (FX matrix -
  daily fixings, not live ticks).
- **Unofficial & keyless (can break silently):** Yahoo's chart endpoint
  (quotes/history) and especially its crumb-authed endpoints (options
  chains, earnings dates, analyst views) — Yahoo has changed this auth
  before. Everything degrades to "unavailable" rather than crashing.
  CoinGecko's keyless tier (crypto market caps) sits here too — rate
  limits drift, so Coinpaprika is an automatic fallback and the CRYPTO
  view shows "unavailable" if both are down.
- **Optional key:** set `FRED_API_KEY` (free signup at
  https://fred.stlouisfed.org/docs/api/api_key.html) and the ECO screen +
  `get_macro_snapshot` MCP tool automatically add Fed funds rate, GDP,
  CPI, unemployment, 10-year yield, and 30-year mortgage rate from FRED.
  Never required — the only key-gated source in the project.
- **Open-source charting:** the stock-page chart is KLineChart (Apache-2.0),
  installed from npm and bundled into the package (no CDN at runtime) and fed entirely by this
  terminal's own data — no indicator or drawing-tool paywalls.

## Caching

Parsed filings are cached under `~/.howlet/` keyed by accession number
(filings never change once filed), and CUSIP→ticker answers are cached
there too. Delete that directory to force a full refresh.

Or use it as a library:

```python
from howlet import EdgarClient, diff_holdings

client = EdgarClient(user_agent="Your Name your-email@example.com")
filings = client.list_13f_filings(cik="1067983", limit=2)
current_holdings = client.get_information_table(filings[0])
prior_holdings = client.get_information_table(filings[1])

for h in sorted(current_holdings, key=lambda x: x.value_usd, reverse=True)[:10]:
    print(h.name_of_issuer, h.value_usd)

for change in diff_holdings(prior_holdings, current_holdings):
    if change.status in ("NEW", "SOLD"):
        print(change.status, change.name_of_issuer)
```

## Running with Docker

```bash
docker build -t howlet:latest .

docker run --rm -e EDGAR_USER_AGENT="Your Name your-email@example.com" \
  howlet:latest search berkshire

docker run --rm -e EDGAR_USER_AGENT="Your Name your-email@example.com" \
  howlet:latest holdings buffett

# --csv writes inside the container; mount a volume to get the file out
docker run --rm -e EDGAR_USER_AGENT="Your Name your-email@example.com" \
  -v "$(pwd)/out:/out" howlet:latest holdings buffett --csv /out/buffett.csv

# The dashboard needs the port published and 0.0.0.0 binding inside Docker
docker run --rm -e EDGAR_USER_AGENT="Your Name your-email@example.com" \
  -p 8813:8813 howlet:latest dashboard --host 0.0.0.0
```

## Rate limits

SEC asks that automated tools stay under roughly 10 requests/second. The
client throttles itself with a small fixed delay between requests — fine
for personal/CLI use, not tuned for bulk historical backfills.

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests run fully offline against mocked HTTP responses — they don't hit the
real SEC servers.

## Frontend development

The UI at `/` is a React + Fluent UI app in `frontend/`. The built files are
committed under `src/howlet/static/app/`, so Node is not needed to run Howlet.

```bash
cd frontend && npm install && npm run dev
```

```bash
npm test
```

```bash
npm run build
```

The dev server (port 5173) has its own localStorage; your real data lives at
`http://localhost:8813/`.

## License

MIT. See `LICENSE`.

## See also

`CLAUDE.md` for a development brief — open this project in Claude Code and
it'll pick up context on what's built and what's worth building next.
