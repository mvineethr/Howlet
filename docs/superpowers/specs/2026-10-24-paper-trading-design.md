# Paper trading account — design

Approved 2026-10-24. Sub-project 2 of the redesign (after the React UI; before Schwab and Laya).

## Goal

A fake-money account inside Howlet for learning how trading works: start with pretend cash, place market,
limit and stop orders against real (delayed) prices, watch positions and P/L, and compare the result with
simply holding the S&P 500.

## Decisions (from brainstorming)

- Features: market buy/sell, limit & stop orders, benchmark vs SPY. No trade journal in v1.
- Storage: a server-side file, `~/.howlet/paper.json`, behind `/api/paper/*`, CLI and MCP.
- Realism: "learning-realistic" — market hours respected, limit/stop filled from real price bars even
  while the app was closed. No fees, slippage, shorting or margin.
- One account, with reset (old account archived). Start cash chosen at creation, default $100,000.
- Approach: append-only ledger + settle-on-read. No background thread or poller.

## Hard rules that apply

- No API key: prices come from the existing keyless `MarketClient` (Yahoo v8 chart, Nasdaq fallback).
- Market data is the fragile tier: missing prices leave orders open and show "prices unavailable";
  nothing raises out of a paper view.
- Keep the Yahoo 0.25 s self-throttle (use `MarketClient`, never raw requests).
- No database: one JSON file under `~/.howlet/`.
- UI colour only from `frontend/src/theme/tokens.ts`.

## Data model — `~/.howlet/paper.json`

```json
{
  "version": 1,
  "account": { "id": "<uuid4>", "created": "<ISO-8601 UTC>", "start_cash": 100000.0 },
  "orders": [
    {
      "id": "<uuid4>", "ts": "<ISO-8601 UTC>", "symbol": "AAPL", "side": "buy",
      "qty": 10.0, "type": "limit", "limit": 180.0, "stop": null, "tif": "day",
      "status": "open", "fill": null, "reason": null
    }
  ],
  "archive": [ { "account": { ... }, "orders": [ ... ], "reset_at": "<ISO-8601 UTC>" } ]
}
```

- `side`: `buy` | `sell`. `type`: `market` | `limit` | `stop`. `tif`: `day` | `gtc`.
- `status`: `open` | `filled` | `cancelled` | `rejected` | `expired`.
- `fill`: `{ "ts": "<ISO>", "price": float }` once filled. Orders fill all-or-nothing (no partials).
- `reason`: human-readable text for `rejected` / `expired`.
- Cash, positions, average cost and P/L are **derived** by replaying filled orders. They are never stored.
- No file means no account yet. Creating one happens on first `reset` (or on the first order, which creates
  the account with the default start cash first).
- A file that fails to parse is renamed to `paper.json.bad-<unix-ts>` and reported as "no account". It is
  never silently overwritten.
- Writes are atomic (write a temp file in the same directory, then `os.replace`). Each read-settle-write runs
  under one module-level `threading.Lock`.

## Fill engine — `settle(state, now, prices)`

A pure function: given the state, the current time and a price provider, it returns the new state. It does
no network I/O itself. It runs at the start of every paper view.

**Price bars.** For each open order, take the bars that **start after `order.ts`**. Use 5-minute intraday
bars while the order is inside Yahoo's intraday lookback window, and daily bars beyond it (daily bars start
on the day after placement). The exact lookback limit is checked live before planning; the spec assumes
~60 days and the code keeps it in one constant. Bars are walked oldest first and the first bar that
triggers wins.

**Market hours.** "Open" means Monday–Friday, 09:30–16:00 America/New_York (`zoneinfo`), **and** the
latest intraday bar is less than 30 minutes old. The second condition handles holidays: no fresh bar means
closed.

| Order | Triggers on bar when | Fill price |
|---|---|---|
| Market, placed while open | immediately at placement | current quote price |
| Market, placed while closed | first bar of the next session | that bar's open |
| Buy limit L | low ≤ L | min(L, bar open) |
| Sell limit L | high ≥ L | max(L, bar open) |
| Sell stop S | low ≤ S | min(S, bar open) |
| Buy stop S | high ≥ S | max(S, bar open) |

Fill timestamp = the triggering bar's start time (or `now` for an immediate market fill).

**Time in force.**
- `day` expires at 16:00 New York time of the session it was placed in. An order placed outside market
  hours lasts through the whole next session.
- `gtc` expires 90 days after placement.
- Status becomes `expired` with a reason.

**Validation at placement** (rejected orders are returned as errors, not stored):
- The symbol must resolve to a quote with `currency == "USD"` and `instrument_type` in {`EQUITY`, `ETF`}.
  Indexes (`^GSPC`), crypto (`BTC-USD`) and FX are refused with a clear message.
- `qty` must be > 0 and ≥ 0.0001, and is rounded to 4 decimals. The UI may take a dollar amount and convert
  it to qty at the current price.
- Limit and stop prices must be > 0. `limit` is required for `limit` orders and `stop` for `stop` orders;
  the other must be null.
- Buy: estimated cost ≤ available cash. Available cash = cash − reserved by open buys. A limit buy reserves
  qty × L, a stop buy qty × S, and a market buy qty × current price.
- Sell: qty ≤ held − qty reserved by open sells.

**Validation again at fill time.** If cash or shares are now insufficient (for example, an earlier fill used
them), the order becomes `rejected` with a reason. It never goes negative.

**Prices unavailable** (the provider returns None for a symbol): its orders stay `open`, and the account
view marks those positions with `price: null` plus a top-level `prices_unavailable: [symbols]`.

## Backend surfaces

`src/howlet/paper.py` contains the engine, storage, derivation (positions, cash, average cost, realised and
unrealised P/L) and the history computation. The price-provider seam wraps `MarketClient`.

| View (`views.py`) | Route | MCP tool |
|---|---|---|
| `paper_account_view()` — settle; account, cash, positions at live value, totals, today's change, open orders, last 20 fills/rejections, `prices_unavailable` | `GET /api/paper` | `paper_account` (also includes the history summary) |
| `paper_order_view(symbol, side, qty, type="market", limit=None, stop=None, tif="day")` | `POST /api/paper/orders` | `paper_order` |
| `paper_cancel_view(order_id)` — open orders only | `DELETE /api/paper/orders/<id>` | `paper_cancel` |
| `paper_history_view()` — daily account value vs SPY | `GET /api/paper/history` | — |
| `paper_reset_view(start_cash=100000)` — archive the account, start fresh | `POST /api/paper/reset` | **none** (an agent must not wipe the account) |

MCP goes from 27 to 30 tools. Validation errors return 400 JSON `{error}` and market-data failures degrade
(never 502 for a paper read).

**History / benchmark.** For each trading day from `account.created` to today: account value = cash that
day + Σ qty held × that day's close. SPY line = start_cash ÷ SPY close on the creation day × SPY close that
day. Returns `{dates, account, spy, account_return_pct, spy_return_pct}`. Daily closes come from
`MarketClient` with a range covering the account's age.

**CLI.** `howlet paper` prints the account. `howlet paper buy|sell SYMBOL QTY [--limit X | --stop X] [--gtc]`
places an order. `howlet paper cancel ID` cancels one. Reset is not in the CLI in v1; it lives in the UI
behind a confirm.

## Frontend surfaces

- `lib/api.ts` gets wrappers: `paperAccount`, `paperOrder`, `paperCancel`, `paperHistory`, `paperReset`.
- **Portfolio → "Paper" tab** (`pages/portfolio/PaperTab.tsx`):
  - Summary row: account value, cash, today's change, total return vs SPY.
  - Account-vs-SPY line chart.
  - Positions table: symbol (links to the stock page), qty, avg cost, price, value, unrealised P/L $ and %.
  - Open orders with Cancel.
  - Activity: fills, rejections and expiries with their reasons.
  - Empty state: "Start a paper account" with a start-cash field.
- **Order ticket** (`components/OrderTicket.tsx`, a Fluent Dialog):
  - Symbol, Buy/Sell, quantity **or** dollar amount, type, limit/stop price, Day/GTC.
  - A live estimate of cost/proceeds, plus cash/shares left after the order.
  - A one-line plain-English explainer for the chosen type, e.g. "Buy limit: fills only if the price drops
    to $180.00 or lower."
  - Server errors are shown inline.
- **Stock page** header gets a "Paper trade" button that opens the ticket with the symbol filled in.
- **Home block** `paper` ("Paper account", needs nothing): value, today's change, vs SPY, and the top
  positions.
- **Settings → Paper account**: Reset, with a confirm dialog and start-cash input.
- **Command box**: `PAPER` opens the Paper tab.

## Testing

- **Engine (pytest, synthetic bars):**
  - Every row of the fill table, plus a gap-through variant of each.
  - Bars before `order.ts` are ignored.
  - After-hours market order → next open.
  - `day` and `gtc` expiry.
  - Reservations against cash and shares.
  - Rejection at fill time.
  - Fractional qty rounding.
  - Refusing index, crypto and non-USD symbols.
  - Prices unavailable → the order stays open.
  - Market-hours check, including the stale-bar (holiday) rule.
- **Storage:** atomic write; corrupt file renamed and reported; reset archives.
- **Derivation:** average cost across several buys and a partial sell; realised and unrealised P/L.
- **Views / routes / MCP:** prices mocked; 400 on bad input; the MCP tool count is 30; no reset tool.
- **Frontend (Vitest):** ticket estimate and validation, explainer text per type, dollar → qty conversion,
  cancel, reset confirm, and the Home block rendering.
- **Live:**
  - 2026-10-24 is a Saturday, so the following run on a closed market: an after-hours market order queues;
    a limit order whose level traded in the last session's bars fills from real bars; the intraday lookback
    limit is measured; the SPY history renders.
  - An immediate in-session market fill is checked at the first market session after the build. It stays
    flagged as unverified until then.

## Out of scope (v1)

Trade journal, fees and slippage, shorting and margin, partial fills, several accounts, options and crypto
paper trading, live push of fills (a refresh or the existing polling picks them up), and Schwab (a separate
sub-project).
