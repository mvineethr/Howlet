---
name: debugging-playbook
description: Load when something "doesn't work" with no error message, when a symptom appears far from any obvious cause, or when you have two competing explanations and need the cheapest experiment to split them. Triggers - blank/empty output with green tests, "Unexpected token '<'", a widget or pane that renders nothing, connection resets, numbers that look plausible but feel off, "pull access denied" for something you just built, a third-party asset that never loads, or any bug report phrased as "it just stopped working".
---

# Debugging Playbook: silent failures and discriminating experiments

Silent failures cost more than loud ones because you debug the wrong layer
first — the symptom is usually two layers downstream of the cause. This
playbook gives you (1) a symptom→cause→check→fix-layer table seeded with
verified incident classes, (2) a procedure for manufacturing an error where
there is none, and (3) the cheapest experiments that split hypothesis A from
hypothesis B. Without it, each of these patterns costs a live debugging
session to rediscover (every row in the table below cost the exemplar repo
exactly that).

## Core procedure: manufacture an error where there is none

When there is no error message, your job is to generate one. Do not touch
code yet.

1. **List the layer boundaries** between intent and symptom.
   Example stacks: `source → build → CDN → browser global → render`, or
   `client JS → API route → upstream service → parser → UI`.
2. **At each boundary, extract a concrete artifact**, starting from the
   boundary closest to the EXTERNAL side (the thing you control least):
   - URL/asset: `curl -I <exact-url>` — demand a 200 and a plausible
     content-length.
   - API route: `curl` it and read the RAW body. Is it even the content
     type the consumer expects?
   - Parser: diff the test fixture against a freshly fetched real response.
   - Library/global: check the symbol exists at runtime
     (`typeof lib !== "undefined"` in the browser console; `python -c
     "import lib; print(lib.__file__)"` for Python), not just that the
     page/process loaded.
3. **Debug at the first boundary whose artifact contradicts your
   assumption.** Not where the symptom appeared.
4. **After fixing, leave a tripwire**: a regression test, a louder error,
   or an entry in the project's gotcha list (see failure-archaeology). The
   fix alone will be forgotten.

Hard rule: never add retries or sleeps around a failure you haven't named.
Retry is for transient faults you've identified, not for hope.

## The symptom→triage table

Each row is a universal pattern class; the edgar incident that proved it
is cited in parentheses (all verified against `HANDOVER.md` and `CLAUDE.md`,
2026-07-07).

| Symptom | Likely cause | Discriminating check | Fix at this layer |
|---|---|---|---|
| `Unexpected token '<'` (or any JSON/XML parse error) in a client consuming an API | Consumer got an HTML error page where it expected JSON — an exception upstream escaped the API's error-format mapping | `curl` the failing API route; read the RAW body. HTML doctype = server problem, not client | The API layer: map ALL upstream exception types to the API's own error format (edgar: Flask errorhandler widened from `HTTPError` to `requests.RequestException` → JSON 502, `src/edgar/dashboard.py`) |
| Third-party script/embed loads nothing — no console error, no element, library global is `undefined` | Wrong-but-plausible resource URL; loaders 404 silently (edgar: KLineChart UMD lives at `dist/umd/klinecharts.min.js`, plain `dist/` 404s; TradingView embed with wrong script host = no iframe, no error) | `curl -I` the exact URL BEFORE writing integration code; after, verify the global exists at runtime | The dependency layer: fix the URL, then consider removing the boundary entirely (edgar vendored the file into `static/`) |
| Tests green, live output empty/default | The fixture encodes the same wrong assumption as the parser — both were hand-built from the same misreading (edgar: Treasury OData values nest under the `m:` metadata namespace; parser AND fixture both used `d:` — tests green, live `{}`) | Diff the fixture against a freshly fetched real response | The test-data layer: fixtures must be captured from reality, never hand-built from docs (see validation-and-qa). Then fix the parser |
| Tests green, live output garbage | Inverse of the above: the hand-built mock is *correct* but the real feed is broken (edgar: SEC's `output=atom` search returns stringified Perl array refs server-side; the correct mock never caught it) | Fetch the real response once; compare to the mock | The client layer: parse the source that actually works (edgar switched to the HTML results table), and capture a real-response regression fixture |
| Intermittent `ConnectionError` / `ECONNRESET` / WinError 10054 from a long-running process | Server recycles stale keep-alive sockets on long-lived sessions — not a block, not a ban (edgar: data.sec.gov resets; parallel widget calls surfaced it) | Does a fresh single request to the same endpoint succeed? Then it's socket staleness, not the endpoint | The central HTTP helper: retry `ConnectionError` with the same backoff as a 5xx (edgar: `client.py::_get`). If you see it raw, some path is bypassing the helper — fix the routing, don't add sleeps |
| A number that is plausibly wrong (not obviously wrong) | Unit drift or semantic drift — no error is possible, only cross-checking detects it (edgar: 13F `<value>` is whole dollars post-Jan-2023, was labeled thousands → 1000x; Yahoo `chartPreviousClose` is the close before the RANGE start, so "day change" was actually multi-day range drift) | Compare ONE datum to an independent source (a filing total against a news figure; a quote against another site). Magnitude check: does $263T for one portfolio make sense? | The model/parsing layer: fix the semantics AND rename the field to carry its units (`value_usd`, not `value`) so the next reader can't repeat the mistake. See proof-and-analysis-toolkit |
| Identifier/entity lookup returns a stale or wrong-region result | Mapping APIs return lists ordered by something other than "current/primary"; code took `[0]` (edgar: OpenFIGI returned delisted "CHV" before US-composite "CVX" for Chevron's CUSIP) | Print the FULL candidate list for one failing identifier; look for a discriminating attribute | The resolver layer: filter on the discriminating attribute (edgar: prefer `exchCode == "US"`, `src/edgar/tickers.py`), never take the first element. Add a regression test with the real multi-candidate payload |
| "Not found" / "pull access denied" for an artifact you just built | Local tooling amnesia — a cache or image store evicted your artifact; it masquerades as an auth/registry/permissions problem (edgar: Docker Desktop evicted freshly built images; `docker images` empty right after a successful build+run) | List the local store (`docker images`, `ls dist/`, etc.). Empty = eviction, not auth | The build step: rebuild (layer caches make it fast). Do NOT log into registries or touch credentials first |

## Discriminating experiments

When you hold two hypotheses, run the cheapest experiment that can only
succeed under one of them. In rough cost order:

| You suspect A vs B | Experiment | Reads as |
|---|---|---|
| Upstream service broken vs your integration broken | `curl` the upstream endpoint directly, bypassing your app, with the same params/headers | Direct call fails → upstream. Direct call works → your layer |
| Client bug vs server bug | `curl` your own API route; inspect the raw body | Bad body → server. Good body → client |
| Logic bug vs stale cached state | Cold-cache run (delete/rename the cache dir) vs warm run | Cold run correct → cache staleness or invalidation. Both wrong → logic |
| Wrong values vs wrong plumbing | Compare ONE datum end-to-end against an independent source (edgar verified an AMZN candle O/H/L/C/V against the user's own TradingView screenshot — exact match) | Matches → plumbing AND values fine. Plausible-but-different → semantic drift (units, baseline, timezone) |
| Parser wrong vs feed changed | Diff the stored fixture against a freshly fetched response | Fixture ≠ reality → refresh fixture, then see which side the parser agrees with |
| Library not loaded vs library misused | Runtime symbol check (`typeof lib`, `import lib`) | `undefined`/ImportError → loading. Defined → usage |
| Environment vs code | Run the same command in a clean environment (fresh venv, `docker run`, CI) | Clean env works → local env drift (see build-and-env) |
| Which layer in a deep stack | Bisect: pick the middle boundary, extract its artifact, recurse into the bad half | log2(N) probes instead of N |

Rule of thumb: an experiment that cannot distinguish A from B is not worth
running, however easy it is. "Restart and see" distinguishes nothing.

## Fix at the layer that owns the fault

- **Root cause lives at exactly one layer; fix it there.** Patching the
  symptom's layer (a try/except in the UI, a sleep in the caller) leaves
  the fault live for every other caller.
- **Before shipping the fix, ask: "who else calls this?"** Grep for every
  caller of the fixed function/route. A fault in a shared helper has as
  many symptom sites as callers.
- **Some faults span two layers — then fix both, each in its own terms.**
  Worked example (edgar, 2026-07-07): connection resets from
  data.sec.gov were fixed "twice over": the HTTP helper `_get` retries
  `ConnectionError` (transport layer owns transient faults), AND the Flask
  errorhandler maps every `requests.RequestException` to a JSON 502 (API
  layer owns the contract that consumers get JSON, always). Either fix
  alone leaves a class of failure open: without the retry, users see
  spurious 502s; without the mapping, the NEXT unhandled upstream
  exception becomes "Unexpected token '<'" again.
- Anything beyond a one-line fix in shared code is a change — route it
  through change-control before touching non-negotiables.

## Worked example (edgar, 2026-07-07): the full loop on one bug

Symptom: dashboard widgets intermittently showed "Unexpected token '<'".

1. Table lookup: that message = HTML where JSON was expected → server
   problem, do not debug JavaScript.
2. Curl the API route during the failure: raw body was a Flask HTML 500
   page. Artifact obtained; boundary found.
3. Server log: `ConnectionResetError` (WinError 10054) from data.sec.gov —
   table row: stale keep-alive on a long-lived session.
4. Root-cause layers: `_get` only retried HTTP 429/5xx, so the transport
   exception propagated; the Flask errorhandler only caught `HTTPError`,
   so it escaped as HTML.
5. Fixed both at their owning layers (retry in `_get`; errorhandler
   widened to `requests.RequestException`); "who else calls this?" — every
   endpoint benefits, since all upstream calls flow through the same
   helper and handler.
6. Tripwires: 3 new regression tests (suite 108→111) and gotcha entries in
   `CLAUDE.md`.

## Anti-patterns (each observed in the wild)

- Debugging the layer where the symptom appeared (JavaScript, because the
  error showed in the browser).
- Interpreting infrastructure amnesia as an auth problem (logging into
  registries over an evicted image).
- Adding retries/sleeps around an unnamed failure.
- Trusting a green test suite as proof the live path works — offline-green
  is necessary, not sufficient (see validation-and-qa).
- Fixing the bug but not recording the pattern (see failure-archaeology).

## When NOT to use this skill

- The failure is LOUD and local (stack trace pointing at the faulty line)
  — just fix it; this playbook's value is when the error is missing or
  misplaced.
- You are deciding whether a change is safe to make, not diagnosing — see
  change-control.
- You are writing the incident up or mining past incidents — see
  failure-archaeology.
- You need measurement tooling (endpoint probers, smoke scripts) rather
  than a diagnosis method — see diagnostics-and-tooling.
- You are validating numbers/claims that are not (yet) suspected bugs —
  see proof-and-analysis-toolkit for the cross-check recipes.
- The problem is a third-party feed's auth/rate-limit/degradation design —
  see external-data-integration.

## Provenance and maintenance

- Written 2026-07-07. All exemplar incidents verified against
  `HANDOVER.md` (sessions 2026-06-30 through 2026-07-07) and `CLAUDE.md`
  gotchas; code claims verified in `src/edgar/client.py` (retries
  `requests.ConnectionError`), `src/edgar/dashboard.py`
  (`@app.errorhandler(requests.RequestException)`), and
  `src/edgar/tickers.py` (`exchCode == "US"` preference).
- Volatile facts: the exemplar's test count (111 as of 2026-07-07; CLAUDE.md
  says 108 — stale), third-party URL layouts (CDN paths, Yahoo endpoint
  walls), and Docker Desktop's eviction behavior are all subject to drift.
- Re-verify: `python -m pytest tests -q` (test count);
  `grep -n "ConnectionError" src/edgar/client.py` and
  `grep -n "errorhandler" src/edgar/dashboard.py` (fix-layer claims);
  `curl -I <asset-url>` for any third-party path before trusting it.
- The universal pattern classes themselves are stable; add new rows to the
  triage table as new silent-failure classes are paid for (one row per
  incident class, cite the incident).
