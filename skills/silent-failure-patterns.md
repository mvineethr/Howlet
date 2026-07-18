# Skill: This project's silent-failure catalog — the tells and the checks

## When to use
Whenever something "doesn't work" with no error, OR before integrating
anything third-party. Silent failures cost more than loud ones because you
debug the wrong layer first. These are the ones this project has actually
paid for, each with its tell and its mechanical check.

## The catalog

### 1. Third-party script URL wrong → nothing renders, no console error
Embeds fail silently on a wrong-but-plausible script URL: no iframe, no
console error, no network hint you'd notice. Happened twice: the
TradingView embed (correct host is
`s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js`)
and the KLineChart CDN (UMD build is at `dist/umd/klinecharts.min.js`;
plain `dist/klinecharts.min.js` 404s and the global loads as `undefined`).
**Check, before writing any integration code**: `curl -I` the exact URL
and require a 200 with a plausible content-length. After integrating:
verify in the browser that the expected global object exists
(`typeof klinecharts !== "undefined"`), not just that the page loaded.

### 2. "Unexpected token '<'" in a dashboard widget → a server error, not JS
That message means a widget received an HTML error page where it expected
JSON — i.e., an unhandled exception upstream. The Flask app maps every
`requests.RequestException` to a JSON 502 precisely to prevent this class.
**Check**: curl the failing `/api/...` endpoint directly and look at the
raw body. If it's HTML, find the exception that escaped the JSON error
mapping; do NOT debug the JavaScript.

### 3. Green tests + empty live output → the fixture shares the code's bug
The Treasury OData parser and its hand-built fixture both used the wrong
namespace: tests green, live output `{}`. **Check**: whenever live output
is empty/default but tests pass, diff the fixture against a freshly
fetched real response before touching the parser (see
fixtures-copy-reality.md).

### 4. Docker "pull access denied" for a locally built tag
Docker Desktop on this machine occasionally evicts freshly built images —
`docker images` comes up empty right after a successful build+run.
**Check**: it is not a registry/auth problem. Just rebuild
(`docker build -t edgar:latest .`); layer cache makes it fast.

### 5. WinError 10054 / ConnectionError from a long-running dashboard
SEC resets stale keep-alive connections on long-lived sessions. Not a
block, not a ban. **Check**: `client.py::_get` already retries
`ConnectionError` with backoff; if you see this raw, some code path is
bypassing `_get` — fix the routing, don't add sleeps.

### 6. A price/change that's plausibly wrong (not obviously wrong)
Range drift shown as day-change; thousands shown as dollars. No error
anywhere — just numbers a casual glance accepts. **Check**: the external
cross-check in sanity-check-magnitudes.md is the only detector.

## Rules I was following
- When there's no error message, generate one: curl the layer boundary
  (the URL, the API route, the fixture-vs-live diff) until some layer
  gives you a concrete artifact to reason from.
- Debug at the boundary where data changes hands, not where the symptom
  appears. The symptom is usually two layers downstream of the cause.
- After fixing a silent failure, leave a tripwire: a regression test, a
  clearer error, or a gotcha entry — the fix alone will be forgotten.

## Worked example (this project)
KLineChart integration (2026-07-07): the chart pane rendered empty,
`klinecharts` was `undefined`, and the console was clean — the CDN
returned a 404 for `dist/klinecharts.min.js` that nothing surfaced. The
catalog check (curl the exact script URL first) would have caught it
pre-integration; instead it cost live debugging. The correct UMD path
(`dist/umd/`) fixed it, and the ultimate fix was vendoring the file into
`static/` so the failure mode is gone entirely. Both the gotcha and the
vendoring decision are recorded in CLAUDE.md.

## Anti-patterns
- Debugging JavaScript because the symptom appeared in the browser.
- Interpreting "pull access denied" as an auth problem and logging into
  registries.
- Adding retries/sleeps around a failure you haven't identified. Retry is
  for transient faults you've named, not for hope.
