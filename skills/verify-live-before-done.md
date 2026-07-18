# Skill: Verify live before calling anything done

## When to use
Before saying "done," "fixed," or "working" about ANY change in this
project. No exceptions — this is a CLAUDE.md hard rule, and it has caught a
real bug in essentially every session.

## Procedure
1. Run the offline suite first: `pytest tests/`. Green tests are the entry
   ticket, not the finish line.
2. Exercise the changed path against the REAL upstream:
   - SEC paths: run the actual CLI (`edgar search berkshire`,
     `edgar holdings buffett`, `edgar diff buffett`).
   - Dashboard paths: start `edgar dashboard`, then check BOTH the JSON
     endpoint (`curl` the `/api/...` route) and the rendered screen in the
     browser preview.
   - MCP paths: `call_tool(...)` against a running `edgar mcp`, don't
     just import the module.
3. Compare at least one number against an independent source you trust:
   a real 10-K figure, the SEC-reported filing total, or the user's own
   screenshot from another tool. Order-of-magnitude agreement is not
   enough — match the digits.
4. Exercise the change *the way a user would*, not just the way the code
   runs: stack 10 indicators, click through MY → DES, load a manager twice
   to confirm the cache path.
5. Record what you verified — the command, the numbers, the date — in
   HANDOVER.md's "Verified live" section (see write-the-handover.md).

## Rules I was following
- Mocks agree with the code by construction; only reality disagrees. A
  green offline suite proves internal consistency, nothing more.
- "Verified live" means a specific artifact: a number you saw, matched
  against a number from elsewhere. "It loaded without errors" is not
  verification.
- Verify at the outermost layer that changed. If the UI changed, the
  browser is the test — a working JSON endpoint under a broken widget is
  still broken.
- If live verification is impossible right now (needs a key, needs market
  hours), say so explicitly and record it as **untested**, like the FRED
  path ("built but untested with a real key"). Never let it silently pass
  as done.

## Worked example (this project)
Session 2026-07-07: after replacing TradingView with KLineChart, the
offline tests passed (108/108). Live verification then went further: AMZN
DES rendered 123 candles, and the last bar (O 243.79 H 246.04 L 240.88
C 244.16 V 37.57M) was compared against the user's own TradingView
screenshot — an exact match, digit for digit. Then 10 indicators were
stacked and removed, and the drawing overlay armed. That's the standard:
real symbol, real bars, independent cross-check, user-level interaction.

Counter-example that justifies the rule: in 2026-06-30, the very FIRST
live run ever (`edgar search berkshire` via Docker) found that SEC's
`output=atom` search returns Perl array refs as titles. Four offline tests
had been green the whole time, because the mock XML was hand-built
correctly. Live verification found in one command what the suite could
never find.

## Anti-patterns
- "Tests pass, shipping it." The Treasury OData parser had green tests and
  returned `{}` live.
- Verifying with the same fixture the code was written against.
- Cross-checking a number against your own other endpoint (both can share
  the bug). The cross-check source must be independent: the SEC filing
  itself, the printed 10-K, the user's screenshot.
