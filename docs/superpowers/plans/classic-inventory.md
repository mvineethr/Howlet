# Classic dashboard inventory (src/howlet/dashboard.html, 2,642 lines)

Working doc for the React port. Line numbers refer to `src/howlet/dashboard.html` unless a file is named.
Flask wiring: `src/howlet/dashboard.py` (classic served at `/classic`, line 63; `/` serves the React build if `static/app/index.html` exists, else classic, lines 57-61). JSON builders: `src/howlet/views.py`.

## 0. Global plumbing

| Thing | Where | Notes |
|---|---|---|
| `$`, `esc` | 794-796 | `esc` escapes & < > " '; everything is built with template-string `innerHTML` |
| `fmtNum(n,digits=2)` | 798 | null/undefined -> `--`; `toLocaleString("en-US")` fixed min=max digits |
| `fmtInt` | 803 | `--` on null; locale integer |
| `fmtMoneyK(usd)` | 808 | `--` on null; `$1.23T` (>=1e12, 2dp), `$x.xxB` (>=1e9, 2dp), `$x.xM` (>=1e6, 1dp), else `$`+fmtInt; `-` sign prefix |
| `pctCls(v)` | 817 | >0 `up`, <0 `down`, else `flat` (null/0 -> flat). up #00d26a, down #ff433d, flat dim |
| `signed(v,d=2)` | 818 | `--` on null; leading `+` when >0 |
| `tkrCell(t)` | 822 | cyan `.tkr[data-sym]` span (click -> `loadSecurity`), dim `--` if falsy |
| `sparkline(values,w=70,h=16)` | 826 | inline SVG polyline, "" if <2 pts; green if last>=first else red |
| `getJSON(url)` | 838 | fetch -> `resp.json()` -> throws `Error(data.error || statusText)` if `!ok`. A non-JSON error body (Flask HTML 500) throws a JSON parse error instead |
| `setStatus(msg,isErr)` | 845 | top-bar `#status`; class `err` |
| clock | 852-856 | 1s interval, LOCAL + UTC |
| `showScreen(name)` | 869 | toggles `.active` among `SCREENS = dash, port, sec, news, my, mkts, eqs, opt, eco, pf, help` (859). Sets `state.backTo` to the previous screen when entering `sec` from elsewhere |
| `state` | 860 | `{manager, symbol, range:"6mo", tickers[], managers[], backTo:"dash"}` |
| `newsItemsHtml(items)` | 1055 | shared news row: `<a href=link target=_blank rel="noopener noreferrer">title</a>`; meta = `source` (amber-dim) + `, symbol` if present + `, new Date(published).toLocaleString()` if present (local TZ) |
| `exportTableCsv(id, filename)` | 1037 | scrapes first `<table>` in container, cell `textContent` as displayed (trimmed, whitespace collapsed), RFC4180 quoting, Blob download; `alert("Nothing to export yet...")` if none. Any `[data-csvfrom]` button (handler 2438-2442). CSV buttons on: PORT portfolio (`portfolio-body`/`portfolio.csv`, line 419), PORT changes (`changes.csv`, 424), PORT consensus (`consensus.csv`, 434), EQS (`eqs-body`/`screener.csv`, 516) |
| Clickable tickers | 2563-2564 | `.tkr[data-sym]` -> `loadSecurity(sym)` (DES). `.fkey[data-cmd]` -> `runCommand(cmd)` (2565-2566) |
| Top-bar | 395-402 | `#cmd` (uppercase CSS), GO button, bell `#alerts`, `#status`, `#clock`. Enter in `#cmd` clicks GO (2549-2550); GO runs `runCommand` then clears the input |
| F-key bar | 774-785 | `data-cmd` spans (HOME, PORT, DES, NEWS, MY, MKTS, EQS, ECO, PF, HELP). **No keydown handler for F1..F9** - labels are click-only |
| URL param | 2628 | `?cmd=XYZ` runs `runCommand` once at boot |
| Legacy migration | 1468-1481 | copies `edgar13f_*` / `edgar_*` localStorage keys to `howlet_*` if target absent (old keys left in place) |

### Ticker tape (`loadTape`, 919-931)
- `GET /api/tape` (no params). Reads `label, price, change_pct` (symbol/change returned, unused). Item = amber label, `fmtNum(price)`, arrow (up/down/flat glyph) + `signed(change_pct)%` coloured by `pctCls`. HTML doubled (`html + html`) "so the scroll never shows a gap" (929). CSS marquee 55s linear (76), pause on hover; `prefers-reduced-motion` sets `padding-left:0` (389).
- Empty array -> silent return (keeps "connecting to market data..."); error -> silently keeps last good tape.
- Refresh: boot + `setInterval(loadTape, 60_000)` (2614-2615).

### Command grammar (`runCommand`, 875-916)
- `HOME|DASH` -> dash. `MKTS|WEI|FXC` -> mkts + `loadMarkets()`. `MY|WATCH|W` -> my + `loadMy()`. `NEWS|N|TOP` -> news + `loadWire()`. `EQS` -> eqs (no auto-run). `ECO` -> eco + `loadEco()`. `PF` -> pf + `loadPF()`. Bare `OPT|OMON` -> opt + `loadOptions(state.symbol)` if a symbol is loaded, else status error "No security loaded - try e.g. AAPL OPT". `HELP|?|ABOUT|FAQ` -> help. `ALERT ...` -> `alertCommand`. Bare `PORT` -> port + `ensurePortScreen()` + `loadPortfolio(first manager label or "buffett")` only if `!state.manager`. Bare `DES` -> sec if a symbol is loaded else error.
- `X DES|GP|FA|HDS|GIP` (last token) -> `loadSecurity(rest)`; the function code is discarded - all land on the same screen (906). `X OPT|OMON` -> `loadOptions(UPPER(rest))`. `X PORT` -> `loadPortfolio(rest)`.
- Bare single token: matches a preset label (case-insens.) or `/^\d{4,10}$/` -> `loadPortfolio`; otherwise `loadSecurity`.

---

## 1. PORT (13F manager portfolio)

Markup 414-443. JS: `loadPortfolio` 934-976, `renderAllocation` 978, `loadDiff` 990, `loadConsensus` 1013, `loadNews` 1065, `ensurePortScreen` 2633. Entry only via the command line (`buffett PORT`, bare preset/CIK, `PORT`) or alerts-panel `.fkey` (`data-cmd="<label> PORT"`, 2262). **No manager dropdown on this screen.**

| Call | Path | Query | Fed by |
|---|---|---|---|
| portfolio | `GET /api/portfolio/<identifier>` | `top=25` (hard-coded; server caps 100) | typed identifier (preset label or CIK), URL-encoded |
| diff | `GET /api/diff/<identifier>` | none | same identifier |
| consensus | `GET /api/consensus` | `min=2&limit=15` | none |
| news | `GET /api/news` | `limit=25` + `symbols=<first 8 non-null tickers of loaded portfolio>` if any | `state.tickers` |

Fields read:
- portfolio: `cik, period_of_report, filing_date, position_count, total_value_usd, positions[]`. Sub-header `CIK x | period y | filed z | N positions | $total`. Position: `ticker, issuer, price, change_pct, sparkline[], value_usd, shares, weight_pct` (returned unused: `cusip, share_type, currency`).
- Table: `#` (index+1, dim) / TKR (`tkrCell`) / ISSUER (ellipsis, title=full) / PX (`--` if null) / %CHG (`--` if null/undef else `signed()%`, pct-coloured) / 1MO (sparkline 70x16) / VALUE (`fmtMoneyK`) / SHARES (`fmtInt`, dim) / WT (`fmtNum(weight_pct,1)%`).
- Allocation: top 10 positions; bar width = `weight_pct / max(top-10 weight_pct) * 100%` (relative to the top-10 max); label = ticker cell else issuer; value `x.x%`. Empty "No positions.".
- diff: `prior_period -> current_period` in sub; first 40 of `changes[]`: `status` (badge class NEW/SOLD/INCREASED/DECREASED), `issuer`, `value_change_usd` (`>=0 ? "+" : "-"` + `fmtMoneyK(abs)`, pct-coloured), `shares_change` (`signed(...,0)`, dim). Empty "No changes between the last two filings." (server already drops UNCHANGED, sorted by status order then |value change|).
- consensus: sub = `managers[].label` joined " / "; rows: `issuer`, `manager_count` (green) + "of N" (`managers.length`), `Object.keys(weights_pct)` joined ", " (tooltip `key: v.toFixed(1)%`), `total_value_usd`. Empty "No overlapping positions found.".
- news: `newsItemsHtml`; sub `for T1,T2` or `market wide`; empty "No headlines right now.".

Behaviour: `loadPortfolio` sets `state.manager`, shows screen, resets 3 panels to loading text (portfolio text mentions "first load of a manager maps tickers and can take ~30s"), sets `state.tickers`, then calls `loadNews()` and `loadDiff()`. `ensurePortScreen()` (once per page via `portScreenLoaded`) fires `loadNews()` + `loadConsensus()` - consensus loads only at first PORT visit, never refreshed. Errors: `ERROR: <msg>` in the panel (+ red status for portfolio). 404 for unknown manager or <2 filings. No polling, no stale-response guard.

---

## 2. DES / FA / HDS (one "sec" screen)

Markup 445-510. JS: `loadSecurity` 1207-1243, `renderKlineData` 1166, `renderStudies` 1180, `loadEvents` 1245, `loadFacts` 1267, `loadHolders` 1292, `loadSecNews` 1315, chart 1086-1164. Panels: chart (`p-chart`), DES stats (`p-stats`), STUDIES (`p-studies`), EVENTS (`p-events`), FA (`p-fa`), HDS (`p-holders`), NEWS (`p-secnews`). Grid areas (209-217) only name chart/stats/fa/holders/secnews; studies & events auto-flow.

`loadSecurity(symbol, range)`: trims + UPPERCASES; `showScreen("sec")` **before** rendering the chart (container must be visible when KLineChart inits); `newSymbol = symbol !== state.symbol`; sets `state.range` if given; re-renders range buttons; sets `#sec-title`; status "Loading X...". Only if `newSymbol` and the security call succeeded does it fire `loadFacts, loadHolders, loadSecNews, loadEvents` (1242). A range click re-calls only `/api/security`. On security error: stats body `ERROR: msg`, red status, **returns before side panels** (and since `state.symbol` was already updated, a retry of the same symbol will also skip them - gotcha). Back button (`#back-btn`, 2545): `showScreen(state.backTo || "dash")`.

### 2a. DES / chart: `GET /api/security/<symbol>?range=<state.range>`
- Ranges `RANGES = ["1d","5d","1mo","6mo","1y","5y","max"]` (1077), default `6mo`; `.range-btn[data-range]` upper-cased labels, active highlighted (`renderRangeButtons` 1079); click -> `loadSecurity(state.symbol, range)` (2567-2568).
- Header sub: `[name, exchange, currency].filter(Boolean).join(" | ")`.
- Stats (stat-grid) reads: `price` (22px bold, coloured by change_pct), `change` + `change_pct` ("CHANGE (1D)": `signed(change) (signed(change_pct)%)`), `range_change_pct` ("CHG (6MO)" label from `state.range.toUpperCase()`; `--` if null), `previous_close, day_low, day_high, week52_low, week52_high, volume (fmtInt), instrument_type, exchange, currency`. Server (views.py 767-796): chart history uses the requested range, but price/change/prev close/volume are overridden from a separate 5d/1d daily quote so "CHANGE (1D)" is always the day move; `range_change_pct` = first/last of range closes.
- Chart data (`renderKlineData`): bar = `{timestamp: history_ts[i]*1000, open, high, low, close, volume}` from `history_ts` (epoch SECONDS), `history_open/high/low/close/volume`; `klineChart.applyNewData(bars)` replaces all data each load (no streaming/auto-refresh). `history_close` is the same array as `sparkline` (`_quote_dict`, views.py 143).
- STUDIES (`renderStudies`): `studies` `{}` -> "Not enough history to compute studies at this range." Rows: SMA 20 `sma20`, SMA 50 `sma50`, EMA 12 `ema12`, EMA 26 `ema26`, RSI 14 `rsi14`, MACD `macd`, MACD signal `macd_signal`, MACD hist `macd_histogram`, Bollinger upper/mid/lower; null -> `--`; 2dp. Computed server-side on the range's closes (latest non-null of each series), so SMA 50 is `--` when the range has <50 bars.
- ORB (inside studies panel): `orb` `{range_high, range_low, last_price(unused), status, breakout_pct}`. Badge text `status.replace("_"," ")`; CSS classes `ABOVE_RANGE` (green bg), `BELOW_RANGE` (red bg), `INSIDE_RANGE` (dim border). "Range" = `low - high`; "Breakout" = `--` when `breakout_pct === 0` else `signed()%` coloured. `orb` null -> "ORB unavailable (needs today's intraday bars - try during market hours)." Server: separate fetch of today's 5-minute bars, `opening_bars=6` (first 30 min) (views.py 825-843). ORB is **not** drawn on the chart.

### 2b. KLineChart (JS 1086-1164; script tag line 12; toolbar 455-482)
- Library: vendored `/static/klinecharts.min.js` (global `klinecharts`, v9-style API: `init`, `setStyles`, `createIndicator(name, isStack, {id})`, `removeIndicator(paneId, name)`, `createOverlay(name)`, `removeOverlay()`, `applyNewData`, `resize`). Loaded in `<head>`, no CDN.
- `initKlineChart()` is lazy (called from `renderKlineData`), guarded `if (klineChart || typeof klinecharts === "undefined") return`; container `#kline-chart` 440px high. Defaults added once at init: `MA` (candle pane), `VOL`, `MACD`. `window resize` -> `klineChart.resize()` (2589).
- **Theme reads CSS tokens off `:root`** (1093-1103), helper `T(name) = getComputedStyle(document.documentElement).getPropertyValue(name).trim()`; comment: the theme used to be a second hard-coded palette that silently went stale. Tokens: `--bg --hair --border --amber --amber-dim --text --dim --up --down --cyan` (values 14-33: bg #08090a, hair #1a1c1e, border #2e3134, amber #eaa53e, amber-dim #ae7013, text #d8d8d8, dim #8a8a8a, up #00d26a, down #ff433d, cyan #4dd7fa). `setStyles` mapping (1104-1133):
  - `grid.horizontal.color`, `grid.vertical.color` = hair
  - `candle.priceMark.last.upColor/downColor` = up/down
  - `candle.tooltip.text.color` = text
  - `candle.bar.{upColor,downColor,upBorderColor,downBorderColor,upWickColor,downWickColor}` = up/down
  - `indicator.tooltip.text.color` = dim
  - `xAxis.tickText.color`, `yAxis.tickText.color` = dim
  - `separator.color` = border
  - `crosshair.horizontal|vertical.line.color` = dim; `.text.backgroundColor` = amber; `.text.color` = bg
  - `overlay.point.color` = amber; `.point.borderColor` = amber-dim; `.line.color` = cyan; `.text.color` = bg; `.text.backgroundColor` = amber
  - Applied once at init (not re-applied on token change).
- Indicator picker `#ind-select` (456-471). "On price": `MA, EMA, BOLL (label Bollinger), SAR, BBI`. "Own pane": `VOL (Volume), MACD, RSI, KDJ, OBV, CCI, WR (Williams %R), TRIX, ROC, DMI, MTM (Momentum), PSY`. `MAIN_PANE_INDICATORS = {MA, EMA, BOLL, SAR, BBI}` (1086) -> `createIndicator(name, true, {id:"candle_pane"})`; others `createIndicator(name)` (new pane). Returned pane id stored: `activeIndicators = [{name, paneId, main}]`; duplicates ignored; chip row `#ind-chips` with `x` (`data-rmind`) -> `klineChart.removeIndicator(paneId, name)`. Indicators persist across symbols/ranges (JS memory only, no localStorage). Picker resets to "+ indicator..." after pick.
- Drawing tools: `[data-draw]` buttons (474-480) -> `klineChart.createOverlay(name)` (2580-2581): `segment` (line), `rayLine` (ray), `horizontalStraightLine` (h-line), `priceLine` (price), `priceChannelLine` (channel), `fibonacciLine` (fib), `simpleAnnotation` (note). `#draw-clear` -> `klineChart.removeOverlay()` (all). Drawings are not persisted nor cleared on symbol change.

### 2c. EVENTS: `GET /api/events/<symbol>`
Reads `next_earnings_date` (else "unknown"), `analyst_recommendation` (else "n/a"), `analyst_counts` (strong_buy/buy/hold/sell/strong_sell, `?? 0`; line omitted if null), `shareholder_meetings` first 5 (`form, filing_date, accession_number`). Empty -> "None on file." Loading "Loading earnings/analyst/meeting data...". Error `ERROR: msg`. Yahoo-crumb (unofficial) data; server degrades per section (views.py 935-962).

### 2d. FA: `GET /api/facts/<symbol>` (no `years`; server default 5)
Reads `company, cik, fiscal_years[]`: `fiscal_year, end_date, revenue, net_income, eps_diluted, total_assets, operating_cash_flow` (unused: `total_liabilities, stockholders_equity`). Row label `FY<year> <end_date dim>`; money `fmtMoneyK`; NET INC coloured via `pctCls`; EPS `--` if null else 2dp. Empty -> "No annual XBRL facts (fund, foreign issuer, or non-10-K filer)." Error text shown **without** `ERROR:` prefix (1288).

### 2e. HDS: `GET /api/holders/<symbol>`
Reads `holders[]` (`manager, shares, value_usd, weight_pct, period_of_report`) and `tracked_managers[]`. Cols MANAGER / SHARES / VALUE / PORT WT (1dp) / AS OF. Empty: "None of the tracked managers (a, b, ...) reported holding SYM in their latest 13F." Loading says "first run can take a minute".

### 2f. Security NEWS: `GET /api/news?limit=15&symbols=<SYM>`
`newsItemsHtml`; sub "for SYM"; empty "No headlines for this symbol.".

---

## 3. NEWS screen
Markup 593-611. JS `loadWire` 1395-1413 (command `NEWS|N|TOP`).
- `GET /api/news?limit=60` -> left "MARKET WIRE" via `newsItemsHtml` (empty "No headlines right now."). The same array is filtered client-side with `/CNBC Earnings|Seeking Alpha/.test(i.source)` -> "EARNINGS & ANALYSIS" panel (first 15; empty "Nothing tagged earnings/analysis in the current wire.").
- `GET /api/fed-events?limit=15` -> "FED & POLICY" (empty "No Fed items right now."). Reads `title, link, source, published`.
- Errors: `ERROR: msg` per request (a news failure repaints only the wire body; the earnings panel stays on "Loading...").
- Refresh: `setInterval` 300_000 while `#screen-news` is active (2617).

---

## 4. MY screen (watchlist, events, news)
Markup 613-637. JS: `loadMy` 1418-1459, `loadWatch` 1980-2010, add 2591-2599, remove 2570.

### Named watchlists store (1483-1499)
- Key `howlet_watchlists_v1` = JSON object `{ "<name>": ["SYM", ...] }` (must be a non-array object, else re-seeded). Seed: migrates legacy `howlet_watchlist` (array) if non-empty, else `["AAPL","MSFT","NVDA","AMZN","TSLA","^GSPC","BTC-USD"]`, stored under name `"default"` and written immediately. Helpers `getWL(name)`, `setWL(name, symbols)`.
- **The MY screen only edits the list named `default`** (1977-1978: "so it and any home-screen widgets bound to default always stay in sync"). Other named lists are created only through HOME "+ ADD BLOCK" -> "+ new list..." (prompt, `trim().toLowerCase()`, created empty, 1683-1688). No rename/delete list UI anywhere.
- Add: input uppercased/trimmed, deduped (`includes`), appended; Enter key works. Remove: `.rm[data-rm]` -> filter -> `loadMy()`.

### MY WATCHLIST (`loadWatch`): `GET /api/quotes?symbols=<default list csv>`
Server caps at 30 symbols (dashboard.py 159). Row per list entry (order preserved), matched via `bySym[sym] || bySym[sym.toUpperCase()]`; missing -> `no data` (colspan 6). Reads `symbol, name, price, change_pct, sparkline[], day_low, day_high, volume`. Cols: x, SYM, NAME (dim, ellipsis), PX, %CHG (`signed()%` coloured; no null guard so null shows `--%`), 5D sparkline 70x14, DAY RANGE `low - high`, VOLUME (`fmtInt`). Empty "Watchlist empty - add a symbol above."; loading "Loading quotes...". Refresh: `setInterval` 60s while `#screen-my` active (2616).

### MY NEWS
Symbols = default list minus entries starting `^`, containing `=`, or containing `-USD`; first 10 -> `GET /api/news?limit=40&symbols=<csv>`. Sub "for A, B" / "add stocks to your watchlist". No symbols: "Add stock symbols to the watchlist to see scoped news."; empty result "No headlines for your watchlist yet.".

### MY EVENTS
First 12 filtered symbols; **sequential** `GET /api/events/<sym>` per symbol, memoised in module-level `myEventsCache` (per page load, successes only, shared with the watchlist-events widget). Table repainted after each symbol (progressive). Cols SYM (tkr) / NEXT EARNINGS (`next_earnings_date` or `--`) / ANALYSTS (`analyst_recommendation` or `--`) / LAST PROXY (`DEF 14A <shareholder_meetings[0].filing_date>` or `--`). Failure -> row "unavailable". No symbols: "Add stock symbols to see upcoming earnings.". Loading: "Loading earnings dates (one lookup per symbol)...".

---

## 5. PF screen (personal portfolio risk)
Markup 562-581. JS: `getPfHoldings/setPfHoldings` 2151-2159, `renderPfHoldings` 2161, `loadPF` 2171-2204, add 2602-2612, remove 2571-2577. This is the "personal portfolio" UI (it lives on PF, not on MY; panel sub says "saved in this browser - not a 13F filing").
- localStorage `howlet_pf_holdings` = JSON array `[{symbol:"AAPL", shares:10}, ...]`; non-array -> `[]`.
- Add: `#pf-symbol` (uppercased/trimmed) + `#pf-shares` (`parseFloat`); ignored if symbol empty, NaN, 0 or negative; an existing symbol has shares **overwritten** (not summed); then `loadPF()`. Remove `.rm[data-pfrm=<index>]` -> splice by index.
- Holdings table: SYM (tkr) / SHARES (`fmtInt`) / x. Empty "No positions yet - add one above."; risk side "Add positions to compute risk.".
- Call: **`POST /api/risk`**, `Content-Type: application/json`, body `{holdings:[{symbol,shares}...], range:"1y"}` (raw `fetch`, not `getJSON`; error from `r.error || statusText`). Server fetches one `get_security` per holding sequentially and drops unpriceable symbols (views.py 1069-1102). Loading: "Fetching price history and computing risk...".
- Reads: `positions[]` (empty -> shows `r.error || "Not enough data."`; server returns `{positions:[], error:"Not enough price history to analyze."}` with HTTP 200), `portfolio_return_pct` (signed 1dp, coloured), `portfolio_annualized_volatility_pct` (1dp), `portfolio_max_drawdown_pct` (1dp, `pctCls` so negative = red), `sharpe_ratio` (null -> `--`, 2dp; label "Sharpe (rf=0)"). Position: `symbol, weight_pct (1dp), return_pct (signed 1dp, coloured), annualized_volatility_pct (1dp), max_drawdown_pct (1dp, coloured)`.
- No polling; runs on screen entry and after add/remove.

---

## 6. MKTS (STOCKS / CRYPTO toggle)
Markup 583-591. JS `getMktsMode` 1330, `loadMarkets` 1334-1360, `loadCryptoMarkets` 1362-1392; toggle click 2417-2422.
- localStorage `howlet_mkts_mode` = `"stocks"` | `"crypto"` (anything but `"crypto"` reads as stocks). `.mkts-mode[data-mktsmode]` spans; active gets `.on` (set inside `loadMarkets`). Click writes the key and reloads. `#mkts-source` cleared each load; crypto sets `source: <data.source>`.
- STOCKS: `GET /api/markets` (no params) -> array of `{section, rows[]}`; one panel per section (AMERICAS, EMEA, ASIA/PACIFIC, FX, COMMODITIES & RATES; views.py 65-91). Row reads `symbol` (tkr -> DES), `label` (dim), `price`, `change_pct` (`--` only if exactly `null`), `sparkline` (60x14). Loading "Loading world markets (30+ instruments)...". Server omits rows with no quote. Crypto is deliberately not a section (views.py 92-94).
- CRYPTO: `GET /api/crypto?limit=50` -> `{source, rows[]}`; empty rows -> "Crypto data unavailable right now (CoinGecko and Coinpaprika both unreachable).". One full-width panel, header "CRYPTO top N by market cap . 24h". Cols: `#` (`rank`), COIN (`symbol` + dim `name`), PRICE (`$` + 4dp if price<1 else 2dp), 24H % (`change_pct_24h`), MKT CAP & 24H VOLUME (`fmtMoneyK`), 24H LOW/HIGH (`low_24h / high_24h`, 4dp if <1; `--` if low null - Coinpaprika fallback has null low/high). Not clickable.
- No polling on this screen (fetch on entry or toggle). Server-side crypto TTL cache 60s (crypto.py 25).

---

## 7. EQS (screener)
Markup 512-528. JS `runScreener` 2013-2049, run button 2601.
- Inputs: `#eqs-pe-max` (P/E <=), `#eqs-mcap-min` (**$B**, multiplied by `1e9` client-side), `#eqs-growth-min` (rev growth %), `#eqs-margin-min` (net margin %). Blank inputs omitted.
- `GET /api/screener?pe_ratio_max=&market_cap_min=&revenue_growth_pct_min=&net_margin_pct_min=` (all optional). The route also accepts `*_min/_max` for pe_ratio, market_cap, revenue_growth_pct, net_margin_pct and `universe=csv`, which the UI never sends. Non-numeric input would make the server `float()` fail (HTML 500) - the UI does no validation. Enter does NOT run it (SCREEN button only). Never auto-runs on entering the screen.
- Reads `universe_size, matched, rows[]` -> `symbol` (tkr), `price`, `change_pct` (`--` if null, coloured), `market_cap` (fmtMoneyK), `pe_ratio` (1dp / `--`), `revenue` (fmtMoneyK), `revenue_growth_pct` (signed %, coloured), `net_margin_pct` (1dp %). (`eps_diluted` returned, unused.) Header line "`matched` of `universe_size` screened". Empty "No matches out of N screened.". Loading "Screening (first run per day is slow - same-day results are cached after)...". CSV button. No client-side sort (server order). `universe_size` = `len(DEFAULT_UNIVERSE)` (curated large-caps, not S&P 500; see HELP).

---

## 8. ECO (macro incl. SEC rulemaking)
Markup 540-560. JS `loadEco` 2093-2148 (command `ECO`). Four panels, three independent try-blocks.
1. `GET /api/macro` (no params):
   - `treasury_yield_curve` = `{date, curve:[{maturity, yield_pct}]}` -> table MATURITY / YIELD (`fmtNum()%`), date in header `#eco-curve-date`; missing -> "Yield curve unavailable right now.".
   - `bls_series` = `{cpi, unemployment_rate, nonfarm_payrolls}`, each an array of `{value, period, year, ...}`. Uses `series[0]` only (assumes newest first); label map `blsLabels` ("CPI (all items)", "Unemployment rate", "Nonfarm payrolls"); LATEST = `value` raw string; PERIOD = `period year`. Empty series skipped; none at all -> "BLS series unavailable right now (keyless tier is rate-limited to 25 requests/day/IP).".
   - `fred_series` = `{key:{description, latest, date}}` -> appended "FRED (St. Louis Fed):" table; else if `!fred_available` -> hint "Set FRED_API_KEY for deeper macro coverage (GDP, Fed funds rate, mortgage rates...) - free signup at fred.stlouisfed.org/docs/api/api_key.html." (`fred_available` = env `FRED_API_KEY` set).
   - Gotcha: if `/api/macro` fails only the curve panel shows the error; the BLS panel stays "Loading..." forever.
2. `GET /api/fed-events?limit=20` -> FED CALENDAR via `newsItemsHtml` (empty "No Fed items right now.").
3. `GET /api/regulatory?limit=15` -> SEC RULEMAKING. Docs `{title, type, document_number, html_url, publication_date}` mapped to news items `{title, link: html_url, source: (type || "Document") + " (middle-dot) " + (publication_date || "")}`. **Comment (2136-2138):** `publication_date` is date-only; passing it as `published` would be parsed as UTC midnight and render a day early in US timezones, so it rides in the source label verbatim. Empty "Federal Register unavailable right now.".
- No polling.

---

## 9. OPT (options chain / OMON)
Markup 530-538. JS `loadOptions(symbol, expiration)` 2052-2090. Entry: `AAPL OPT`, `AAPL OMON`, or bare `OPT` (uses `state.symbol`); no button on DES.
- `GET /api/options/<symbol>[?expiration=<date>]`. `#opt-expiry` select (panel header) is populated only on the call with no `expiration`, from `expiration_dates[]` with `selected_expiration` selected; its `onchange` is (re)assigned there to `loadOptions(symbol, value)`.
- Reads `underlying_price, selected_expiration, expiration_dates, calls[], puts[]`; contract: `strike` (green `.itm` when `in_the_money`), `last_price`, `bid` / `ask` (`--` per side), `volume`, `open_interest` (fmtInt), `implied_volatility` (x100, 1dp %, `--` if null). Two side-by-side tables CALLS / PUTS (flex-wrap, min 320px). (`contract_symbol` unused.) `#opt-sub` = symbol. Loading "Loading options chain...". Errors (incl. 404 "No options data for ...") -> `ERROR: msg`. Unofficial Yahoo endpoint (HELP says it may go dark).

---

## 10. HELP
Markup 639-772, static HTML, no API calls. Anchored sections: `#about`, `#glossary`, `#commands`, `#blocks`, `#charting`, `#faq`, `#tips`, then "PLUG THIS INTO YOUR AI" and "SOURCES". Contains logo `/static/logo.png` (floated right 120px), glossary tables (function codes, finance terms, chart studies), command table, HOME-blocks text, charting text, FAQ, tips. Jump links `.help-nav a` need a JS handler (2556-2562) because "body is the scroll container, so native #id anchors scroll the wrong element" - it `preventDefault`s and `scrollIntoView({block:"start"})`. Copy can be lifted verbatim from 639-772. HELP's `#blocks` paragraph (733-739) lists only a subset of widgets (omits insiders, filings, fund, fx-matrix, crypto, position-history, insider-buys).
---

## 11. HOME (customizable dashboard)

Markup 407-412 (`#tabbar`, `#dash-grid`, hidden `<input type=file id=import-file accept="application/json,.json">`). Default active screen. JS 1461-1972 plus boot handlers 2354-2630.

### localStorage keys (all `howlet_*`; EXPORT only carries that prefix)
| Key | Shape | Code |
|---|---|---|
| `howlet_layout_v1` | `{tabs:[{id,name,widgets:[{id,type,config,wide?,tall?}]}], active:"<tabId>"}`; default blank `{tabs:[{id:"home",name:"HOME",widgets:[]}], active:"home"}` (`getLayout` requires a non-empty `tabs` array) | 1502-1512 |
| `howlet_layouts_v1` | `{ "<snapshot name>": <layout object> }` | 1515-1523 |
| `howlet_watchlists_v1` | `{name: [symbols]}` | 1484 |
| `howlet_watchlist` | legacy array, migration source only | 1492 |
| `howlet_mkts_mode` | `"stocks"` or `"crypto"` | 1329 |
| `howlet_pf_holdings` | `[{symbol,shares}]` | 2151 |
| `howlet_seen_filings_v1` | `{ "<cik>": "<accession>" }` | 2210 |
| `howlet_price_alerts_v1` | `[{id, sym, op:">"|"<", px:number, fired:null|{price,at:ISO}}]` | 2286 |

Widget instance `{id: "w"+Date.now().toString(36)+rand4 (newId 1674), type, config, wide?, tall?}`. Config shapes: manager widgets `{manager:"<label>"}`; watchlist widgets `{list:"<name>"}`; symbol widgets `{symbol:"AAPL"}`; position-history `{manager, symbol}`; others `{}`.

### Tabs
- Render `renderTabbar` 1578-1597: `.dtab[data-dtab]` per tab (with `x` `data-dtabrm` for every tab except id `home`), `+ TAB`, then the layouts bar.
- **Create**: `+ TAB` -> `prompt("Name the new tab:")`; name `trim().toUpperCase()`; empty cancels; id `newId()`; becomes active; save; re-render (2363-2373).
- **Rename: NOT implemented in classic** (no rename code anywhere).
- **Delete**: `x` -> `confirm('Delete tab "NAME" and its blocks?')`; if it was active, active = `"home"` (2374-2384). `home` cannot be deleted.
- **Switch**: click -> `layout.active = id`, save, `showScreen("dash")`, `renderDashboard()` (re-fetches every widget on that tab) (2385-2392).

### Layout snapshots (LAYOUTS: bar, `#layouts-bar` 1584-1596)
- `<select id=layout-select>` lists snapshot names sorted alphabetically ("- none saved -" when empty).
- **SAVE** (2444-2457): prompt "Save current layout (all tabs + blocks) as:" prefilled with the currently selected name; name `trim().toLowerCase()`; existing -> `confirm('Overwrite saved layout "x"?')`; stores `JSON.parse(JSON.stringify(layout))`; re-render tabbar; selects new name.
- **LOAD** (2458-2468): `confirm('Replace the current layout with "x"?')`; deep copy; if `active` tab missing -> `"home"`; save; `renderDashboard()`.
- **DEL** (2487-2496): `confirm('Delete saved layout "x"? (The current screen is unaffected.)')`; delete; re-render tabbar.
- **EXPORT** (`#state-export`, 2469-2482): every localStorage key starting `howlet_` -> `{key: rawStringValue}`; downloads `howlet-backup-YYYY-MM-DD.json` (indent 1). Covers layouts, snapshots, watchlists, PF holdings, mkts mode, seen filings, price alerts.
- **IMPORT** (`#state-import` -> hidden file input 2483-2486; handler 2528-2543): JSON parse (alert "Not a valid JSON backup."); keeps keys that start `howlet_` with string values (alert "No Howlet state found in that file." if none); `confirm('Restore N settings (layouts, watchlists, portfolio) from "file"? Current state will be replaced.')`; `localStorage.setItem` each; `location.reload()`. Gotcha: only overwrites keys present in the file; does not delete other `howlet_*` keys despite the wording.
- **RESTORE CLASSIC LAYOUT** (`#restore-classic`, 1620 & 1642-1647): shown only in the empty-state of the tab with id `home` (text "This tab is a blank slate - add the blocks you want."). Replaces `tab.widgets` with `CLASSIC_WIDGETS` (1525-1531): `manager-portfolio{manager:"buffett"}`, `manager-changes{manager:"buffett"}`, `consensus{}`, `watchlist{list:"default"}`, `watchlist-news{list:"default"}`; fresh ids; save; re-render.

### Widget chrome / grid (`renderDashboard` 1599-1650)
- `#dash-grid`: CSS grid `repeat(auto-fit, minmax(420px,1fr))`, `grid-auto-flow: dense` (105-109). Widget header = label + header control + resize toggles + remove; body `#wb-<id>` starts "Loading...". `.widget .panel-b` max-height 420px; `.tall` 860px; `.wide` spans the row (`def.wide` OR `w.wide`).
- Header control (`widgetHeaderControl` 1564-1573): `needs:"manager"` widgets get an inline `<select class="w-mgr" data-wmgr=id>` of `state.managers` (from `/api/managers`, labels upper-cased); change -> `w.config.manager`, save, "Loading...", `loadWidget(w)` (2515-2525). Others get a dim sub-label from `widgetConfigLabel` (1554): `MANAGER . SYMBOL`, `MANAGER`, `list: name`, or `SYMBOL`.
- Resize toggles (`data-wwide` / `data-wtall`) flip classes in place with no re-fetch ("so the block's data isn't refetched just for a resize", 2393-2394) and save. `x` (`data-wrm`) removes, saves, re-renders (re-fetches all).
- **Add block** (`#add-block`, 1624-1634): "+ ADD BLOCK" opens picker `<select id=add-type>` (all WIDGETS by label) + `renderAddConfig` (1652-1672) by `needs`: `manager` -> manager select; `watchlist` -> existing list names + "+ new list..." (`__new__`); `symbol` -> text input; `manager-symbol` -> manager select + symbol input. `addWidgetFromPicker` (1676-1698): empty symbol -> silently does nothing; new list -> `prompt("Name the new watchlist:")` lowercased, created empty; pushes onto active tab, save, re-render.
- `loadWidget(w)` (1700): `def.load(el, w.config, w).catch(e => el.innerHTML = 'ERROR: msg')`. Unknown widget types are skipped on render.
- Refresh (`refreshDashWidgets` 1967-1972): `setInterval(()=>refreshDashWidgets(60), 60_000)` and `(300, 300_000)` (2618-2619); runs only while `#screen-dash` is active, only for the active tab's widgets whose registered `refresh <= minInterval`. **Gotcha:** the 300s tick matches every widget with `refresh <= 300`; the 60s tick matches only `watchlist`. So `world-markets` and `crypto` (declared 120) actually refresh only on the 300s tick. Refresh replaces the body in place (no loading placeholder); for `watchlist` this wipes text typed in its add-symbol input.
- Cross-sync: `reloadWidgetsForList(name)` reloads every active-tab widget with `config.list === name` (1782).

### WIDGETS registry (1534-1552) - exactly 17 types
| # | key | label | needs | refresh s | loader (lines) |
|---|---|---|---|---|---|
| 1 | manager-portfolio | 13F PORTFOLIO | manager | - | loadWManagerPortfolio 1710 |
| 2 | manager-changes | 13F Q/Q CHANGES | manager | - | loadWManagerChanges 1724 |
| 3 | consensus | SMART MONEY CONSENSUS | - | - | loadWConsensus 1735 |
| 4 | watchlist | WATCHLIST | watchlist | 60 | loadWWatchlist 1748 (+ wireWatchlistWidget 1768) |
| 5 | watchlist-news | WATCHLIST NEWS | watchlist | 300 | loadWWatchlistNews 1786 |
| 6 | watchlist-events | WATCHLIST EVENTS | watchlist | - | loadWWatchlistEvents 1794 |
| 7 | insiders | INSIDER TRANSACTIONS | symbol | 300 | loadWInsiders 1836 |
| 8 | insider-buys | INSIDER BUYS (SCREEN) | watchlist | - | loadWInsiderBuys 1893 |
| 9 | position-history | 13F POSITION HISTORY | manager-symbol | - | loadWPositionHistory 1810 |
| 10 | market-news | MARKET NEWS | - | 300 | loadWMarketNews 1862 |
| 11 | fed | FED & POLICY | - | 300 | loadWFed 1867 |
| 12 | yield-curve | TREASURY YIELD CURVE | - | - | loadWYieldCurve 1872 |
| 13 | world-markets | WORLD MARKETS (`wide:true`) | - | 120 | loadWWorldMarkets 1880 |
| 14 | crypto | CRYPTO TOP 20 | - | 120 | loadWCrypto 1953 |
| 15 | filings | SEC FILINGS | symbol | 300 | loadWFilings 1918 |
| 16 | fx-matrix | FX CROSS-RATE MATRIX | - | - | loadWFxMatrix 1941 |
| 17 | fund | ETF/FUND HOLDINGS | symbol | - | loadWFund 1929 |

List-scoped widgets (watchlist-news, watchlist-events, insider-buys) first drop symbols that start with `^`, contain `=`, or contain `-USD`. Errors in any loader fall to `ERROR: <message>`. Ticker cells click through to DES.

### Per-widget detail
1. **manager-portfolio** - `GET /api/portfolio/<cfg.manager>?top=15`. Reads `period_of_report, total_value_usd, position_count`; `positions[]`: `ticker, issuer, change_pct` (`== null` -> `--`, else `signed()%` coloured), `value_usd`, `weight_pct` (1dp). Header line "period X, $T total, N positions". Cols # / TKR / ISSUER / %CHG / VALUE / WT (no price, sparkline or shares, unlike PORT).
2. **manager-changes** - `GET /api/diff/<cfg.manager>`. Reads `prior_period`, `current_period` ("a -> b"), first 12 of `changes[]`: `status` (badge), `issuer`, `value_change_usd` (signed $ coloured). No header row, no shares column.
3. **consensus** - `GET /api/consensus?min=2&limit=10`. Row: issuer / `manager_count` (green) `/` `managers.length` / `Object.keys(weights_pct).join(", ")` / `total_value_usd`. Empty "No overlapping positions.".
4. **watchlist** - `GET /api/quotes?symbols=<list csv>` (skipped when list empty: "Empty list - add a symbol."). Inline add input + ADD button (Enter works): uppercases, dedupes, `setWL`, `reloadWidgetsForList`. Rows: x (`data-wlrm` + `data-wlname`), tkr, `price`, `change_pct` (`signed()%` coloured, no null guard), sparkline 60x14; no quote -> "no data". Refresh 60.
5. **watchlist-news** - `GET /api/news?limit=20&symbols=<filtered list, max 10>`; line "only: A, B"; empty list "Add stock symbols to this list to see scoped news."; empty result "No headlines yet for these names.". Refresh 300.
6. **watchlist-events** - sequential `GET /api/events/<sym>` for first 8 filtered symbols, shared `myEventsCache`; cols SYM / NEXT EARNINGS (`next_earnings_date`) / ANALYSTS (`analyst_recommendation`); failure row "unavailable"; repainted after each symbol. Empty "Add stock symbols to this list to see events.".
7. **insiders** - `GET /api/insiders/<cfg.symbol>?filings=15`. Reads `filings_scanned`, `summary.{open_market_purchases, purchase_value_usd, open_market_sales, sale_value_usd}`, `transactions[]` first 14: `date` (`?` if null), `insider` (tooltip `insider - relationship`), `code_label` text coloured by `code` (P green, S red, else dim; tooltip code_label), `shares` (0dp), `price_per_share` (`--` if null, 2dp), `value_usd` (`--` if null, fmtMoneyK). Summary "last N Form 4s . X buys $ . Y sells $". Empty "No non-derivative insider transactions in these filings.". 404 if ticker has no SEC filer. Refresh 300.
8. **insider-buys** - first 15 filtered symbols -> `GET /api/insider-buys?filings=8&symbols=<csv>` (server caps 25 symbols / 20 filings). Interim text "Scanning Form 4s for N symbols (first run is the slow one)...". Reads `buys[]` (first 20: `date, symbol, insider, relationship (tooltip), shares, price_per_share, value_usd`), `summary[]` (`symbol, buy_count, total_value_usd` -> green "SYM Nx $"), `filings_per_symbol`. Empty "No open-market insider buys across A, B in their last N Form 4s each. (Insider buying is rare - that's why it matters.)". No auto refresh.
9. **position-history** - `GET /api/position-history/<manager>/<symbol>?quarters=8`. Reads `issuer`, `cusips[]` (header "issuer . CUSIP a, b"), `quarters[]` (oldest first): `period_of_report` (`?`), `value_usd`, `shares`, `weight_pct`. Amber bar width = `value/max(values,1)*100%`. Share delta shown next to shares when `shares !== previous quarter` (green +/red, 0dp); none on the first row. (`held`, `filing_date` unused.) Server 404 "didn't report anything matching ..." when nothing matches (query may be ticker, 9-char CUSIP, or issuer-name substring).
10. **market-news** - `GET /api/news?limit=15`; empty "No headlines right now."; refresh 300.
11. **fed** - `GET /api/fed-events?limit=10`; empty "No Fed items right now."; refresh 300.
12. **yield-curve** - `GET /api/macro` (same heavy endpoint as ECO; reads only `treasury_yield_curve.date`, `.curve[].maturity`, `.curve[].yield_pct` as `x.xx%`). Missing -> "Yield curve unavailable right now.". No refresh.
13. **world-markets** (wide) - `GET /api/markets`; flex-wrap of sections (min 240px): section title, rows tkr / label (dim) / price / `change_pct` (`== null` -> `--`). No sparklines. Refresh 120 (effective 300).
14. **crypto** - `GET /api/crypto?limit=20`; header "top N by market cap . <source>"; rows `rank, symbol, price ($, 4dp if <1), change_pct_24h (== null -> --), market_cap (dim)`. Empty "Crypto data unavailable right now.". Refresh 120 (effective 300).
15. **filings** - `GET /api/filings/<symbol>?limit=15`. `filings[]`: `filing_date` (dim), `form` (link to `url`, new tab, `?` if null), `period_of_report` (`-` if null). Empty "No recent SEC filings.". Refresh 300.
16. **fx-matrix** - `GET /api/fx` (no `currencies`). Reads `date, currencies[], matrix`; `!d.matrix` -> "FX rates unavailable right now (ECB/Frankfurter unreachable)." Header "ECB reference rates, <date>, row -> column". Cell `matrix[row][col]`, 2dp if rate >= 100 else 4dp; diagonal "-" dim. Server caches 1h (fx.py 27).
17. **fund** - `GET /api/fund/<symbol>?top=25`. Reads `fund, report_period_date (? if null), net_assets, position_count`; `holdings[]`: `name` (tooltip `title`), `value_usd`, `pct_val` (2dp %). 404 for non-fund tickers.

---

## 12. Alerts bell (shell feature; also in the localStorage export)
- Bell `#alerts` (399): badge = `newFilings.length` + fired price alerts (2222-2227); click toggles `#alerts-panel` (`toggleAlertsPanel` 2251), which also calls `Notification.requestPermission()` when permission is `default`.
- 13F filing alerts: `GET /api/filing-alerts` -> `[{label, cik, form, accession_number, filing_date, period_of_report}]`. First poll with an empty `howlet_seen_filings_v1` baselines silently; later a row whose accession differs from stored `seen[cik]` (and `seen[cik]` exists) is new. Desktop `Notification` once per accession per session. "MARK ALL SEEN" (`dismissAlerts` 2272) writes seen accessions and clears fired price alerts. Poll at boot and every 30 min (1_800_000) (2623-2624). Panel rows are `.fkey[data-cmd="<label> PORT"]`.
- Price alerts: command `ALERT SYM > 350` / `ALERT SYM < 300` (regex 2301; bare `ALERT` opens the panel). One-shot rules; `pollPriceAlerts` (2314) calls `GET /api/quotes?symbols=<unfired syms, max 30>` at boot and every 60s (2626-2627); fires on cross, stores `fired:{price,at}`; Notification title `SYM op px`. Rows `.fkey[data-cmd="SYM DES"]`, remove `x[data-alertrm]`.

---

## 13. API route reference (dashboard.py -> views.py), exact JSON top-level keys

Error contract (dashboard.py 47-55): `requests.RequestException` -> 502 `{"error": "Upstream request failed: ..."}`; `LookupError` -> 404 `{"error": msg}`; `/api/fulltext` missing `q` -> 400 `{"error": "q parameter required"}`. 27 routes are defined; the classic page calls 26 (`/api/fulltext` is not used).

| Route | Query / body | Top-level JSON keys | Used by |
|---|---|---|---|
| `GET /api/managers` | - | array of `{label, cik}` (first label per unique CIK: buffett, burry, ackman, icahn, tepper, klarman, loeb, dalio, druckenmiller, marks, lilu, einhorn, fundsmith, tigerglobal) | boot -> `state.managers` |
| `GET /api/tape` | - | array of `{symbol,label,price,change,change_pct}` | tape |
| `GET /api/portfolio/<identifier>` | `top` (25, cap 100) | `identifier, cik, period_of_report, filing_date, accession_number, total_value_usd, position_count, positions[]` (`issuer,cusip,value_usd,shares,share_type,weight_pct,ticker,price,change_pct,currency,sparkline`) | PORT, widget 1 |
| `GET /api/diff/<identifier>` | - | `prior_period, current_period, changes[]` (`issuer,cusip,status,value_change_usd,shares_change,current_value_usd`) | PORT, widget 2 |
| `GET /api/consensus` | `min` (2), `limit` (20) | `managers[]` (`label,period_of_report`), `rows[]` (`issuer,cusip,manager_count,total_value_usd,combined_weight_pct,weights_pct{}`) | PORT, widget 3 |
| `GET /api/holders/<symbol>` | - | `symbol, tracked_managers[], holders[]` (`manager,period_of_report,cusip,issuer,shares,value_usd,weight_pct`) | HDS |
| `GET /api/position-history/<identifier>/<query>` | `quarters` (8, cap 40) | `identifier, cik, query, issuer, cusips[], quarters[]` (`period_of_report,filing_date,shares,value_usd,weight_pct,held`) | widget 9 |
| `GET /api/insiders/<symbol>` | `filings` (15, cap 40) | `symbol, cik, company, filings_scanned, summary{open_market_purchases,purchase_shares,purchase_value_usd,open_market_sales,sale_shares,sale_value_usd}, transactions[]` (`insider,relationship,date,code,code_label,acquired_disposed,shares,price_per_share,value_usd,shares_owned_after,security_title,direct_or_indirect,filing_date,accession_number`) | widget 7 |
| `GET /api/fulltext` | `q` (req), `forms` csv, `limit` (20, cap 50) | `query, forms[], results[]` | NOT used |
| `GET /api/filings/<symbol>` | `form`, `limit` (20, cap 50) | `symbol, cik, company, filings[]` (`form,filing_date,period_of_report,accession_number,url`) | widget 15 |
| `GET /api/fund/<symbol>` | `top` (50, cap 200) | `symbol, registrant, fund, series_id, report_period_date, total_assets, net_assets, accession_number, position_count, holdings[]` (`name,title,cusip,balance,value_usd,pct_val,asset_cat,issuer_cat,country`) | widget 17 |
| `GET /api/fx` | `currencies` csv | `date, currencies[], matrix{from:{to:rate}}` (fx.get_fx_matrix; no matrix when unreachable) | widget 16 |
| `GET /api/filing-alerts` | - | array of `{label,cik,form,accession_number,filing_date,period_of_report}` | bell |
| `GET /api/insider-buys` | `symbols` csv (cap 25), `filings` (8, cap 20) | `symbols_scanned[], filings_per_symbol, summary[]` (`symbol,buy_count,total_shares,total_value_usd,latest_date`), `buys[]` (`symbol,insider,relationship,date,shares,price_per_share,value_usd,shares_owned_after,filing_date,accession_number`) | widget 8 |
| `GET /api/security/<symbol>` | `range` (6mo) | `symbol,name,exchange,instrument_type,currency,price,change,change_pct,previous_close,day_low,day_high,week52_low,week52_high,volume,history_ts[],history_close[],history_open[],history_high[],history_low[],history_volume[],range,range_change_pct,studies{sma20,sma50,ema12,ema26,rsi14,macd,macd_signal,macd_histogram,bollinger_upper,bollinger_mid,bollinger_lower},orb{range_high,range_low,last_price,status,breakout_pct} or null` | DES |
| `GET /api/facts/<symbol>` | `years` (5) | `symbol,cik,company,fiscal_years[]` (`fiscal_year,end_date,revenue,net_income,eps_diluted,total_assets,total_liabilities,stockholders_equity,operating_cash_flow`) | FA |
| `GET /api/quotes` | `symbols` csv (cap 30) | array of `{symbol,name,exchange,instrument_type,currency,price,change,change_pct,previous_close,day_low,day_high,week52_low,week52_high,volume,sparkline}` (symbols with no quote omitted) | MY, widget 4, price alerts |
| `GET /api/markets` | - | array of `{section, rows[]}` (`symbol,label,price,change_pct,sparkline`) | MKTS, widget 13 |
| `GET /api/crypto` | `limit` (50) | `source, rows[]` (`rank,symbol,name,price,change_pct_24h,market_cap,volume_24h,high_24h,low_24h`) | MKTS, widget 14 |
| `GET /api/regulatory` | `limit` (20) | array of `{title,type,document_number,html_url,publication_date}` | ECO |
| `GET /api/news` | `limit` (30, cap 100), `symbols` csv (server uses first 10) | array of `{title,link,source,symbol,published (ISO or null)}` | PORT, DES, NEWS, MY, widgets 5/10 |
| `GET /api/events/<symbol>` | - | `symbol,next_earnings_date,analyst_recommendation,analyst_counts{strong_buy,buy,hold,sell,strong_sell} or null,shareholder_meetings[]` (`form,filing_date,accession_number,primary_doc`) | DES, MY, widget 6 |
| `GET /api/fed-events` | `limit` (20) | array of `{title,link,source,published}` | NEWS, ECO, widget 11 |
| `GET /api/macro` | - | `treasury_yield_curve{date,curve[{maturity,yield_pct}]}, bls_series{cpi,unemployment_rate,nonfarm_payrolls: [{value,period,year,...}]}, fred_available, fred_series{key:{description,latest,date}}` | ECO, widget 12 |
| `GET /api/screener` | `universe` csv, `{pe_ratio,market_cap,revenue_growth_pct,net_margin_pct}_{min,max}` | `universe_size, matched, rows[]` (`symbol,price,change_pct,market_cap,pe_ratio,eps_diluted,revenue,revenue_growth_pct,net_margin_pct`) | EQS |
| `GET /api/options/<symbol>` | `expiration` | `symbol,underlying_price,expiration_dates[],selected_expiration,calls[],puts[]` (`contract_symbol,strike,last_price,bid,ask,volume,open_interest,implied_volatility,in_the_money`) | OPT |
| `POST /api/risk` | JSON `{holdings:[{symbol,shares}], range:"1y"}` | `portfolio_return_pct,portfolio_annualized_volatility_pct,portfolio_max_drawdown_pct,sharpe_ratio,positions[]` (`symbol,weight_pct,return_pct,annualized_volatility_pct,max_drawdown_pct`); no-data: `{positions:[], error}` HTTP 200 | PF |

Distinct routes called by classic: **26**. By consumer: PORT (portfolio, diff, consensus, news); DES (security, events, facts, holders, news); NEWS (news, fed-events); MY (quotes, news, events); MKTS (markets, crypto); EQS (screener); ECO (macro, fed-events, regulatory); OPT (options); PF (risk); HELP (none); HOME widgets (portfolio, diff, consensus, quotes, news, events, insiders, insider-buys, position-history, fed-events, macro, markets, crypto, filings, fx, fund); shell (managers, tape, filing-alerts, quotes).

## 14. Gotchas for the port (summary)
1. `sec` screen is one component for DES/GP/FA/HDS/GIP; side panels load only for a new symbol, not on range change.
2. No DES polling; chart data replaced wholesale via `applyNewData`; indicators/overlays live only in JS memory; theme applied once at chart init.
3. `refresh: 120` on world-markets and crypto effectively fires every 300s (interval filter, 1967-1972 + 2618-2619).
4. No tab rename; `home` tab undeletable; layout snapshot names lowercased, tab names uppercased.
5. IMPORT merges keys (no clearing) then reloads the page.
6. MY edits only the `default` watchlist; PF holdings are separate (`howlet_pf_holdings`).
7. Dates: news `published` ISO -> `toLocaleString()`; date-only strings (`publication_date`, `filing_date`, `period_of_report`, earnings dates) shown raw to avoid TZ shift (2136-2138). Chart `history_ts` is epoch seconds.
8. Units: `*_usd`, `market_cap`, `revenue` are whole USD (`fmtMoneyK`); `weight_pct`/`change_pct` already percentages; options IV is a fraction (x100); EQS min-cap input is $B.
9. ECO macro failure leaves BLS panel on "Loading..."; NEWS wire failure leaves earnings panel on "Loading...".
10. HELP jump links need an explicit scroll handler because body is the scroll container.
11. FA error text lacks the `ERROR:` prefix; HDS empty-state interpolates `tracked_managers` unescaped.