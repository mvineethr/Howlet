# Skill Library Index — edgar

Sixteen skills, ranked by **quality bought per token spent reading**.
The ranking logic: skills that prevent whole classes of silent, expensive
bugs with a short mechanical rule rank highest; skills that mostly encode
process or architecture rank lower — still load-bearing, but their failure
modes are cheaper or louder.

If you can only load a few skills into context, take them from the top.

| Rank | Skill | What it buys | Why this rank |
| --- | --- | --- | --- |
| 1 | [verify-live-before-done.md](verify-live-before-done.md) | The project's single highest-yield habit. One live command per change has caught a real bug in essentially every session (atom-search, units, namespaces, day-change, CDN path). | Cheapest possible check, catches the most expensive class of bug — the kind offline tests structurally cannot see. If you follow one skill, follow this one. |
| 2 | [sanity-check-magnitudes.md](sanity-check-magnitudes.md) | Stops silently-wrong numbers (1000x units bug, range-drift-as-day-change). In a finance tool, wrong numbers are the worst possible failure — worse than a crash. | One external cross-check per new field. Tiny cost; the bugs it catches are invisible to every other technique here. |
| 3 | [degrade-never-break.md](degrade-never-break.md) | The three reliability tiers and which error handling each demands. Governs every `try/except` you will ever write here. | You touch error handling in almost every change; getting the tier wrong either breaks the core product or masks real failures. High frequency × high stakes. |
| 4 | [probe-before-building.md](probe-before-building.md) | One curl before any parser/integration. Found the flat-vs-nested pagination shape and the Yahoo auth wall before code was written against wrong assumptions. | Converts hours of rework into a 30-second read of a real payload. Slightly below the top three only because it applies at build time, not every change. |
| 5 | [silent-failure-patterns.md](silent-failure-patterns.md) | The six known no-error failure modes and the mechanical check for each ("Unexpected token '<'" = HTML error page; wrong CDN path; Docker eviction; WinError 10054...). | Pure paid-for pattern-matching. When one of these hits, this file turns a lost afternoon into a two-minute diagnosis. Ranked by expected value: massive when triggered, but only triggered sometimes. |
| 6 | [fixtures-copy-reality.md](fixtures-copy-reality.md) | Fixtures copied from live responses, never hand-built; fix-the-fixture-first regression procedure. Kills the "tests green, live empty" trap (Treasury namespaces). | Every mocked test you write flows through this. Ranked just below the failure catalog because its bug class overlaps with #1 — live verification is the backstop when this is violated. |
| 7 | [aggregate-by-the-real-key.md](aggregate-by-the-real-key.md) | CUSIP is the key; aggregate within a filing before comparing; GOOGL/GOOG twice is CORRECT; never take OpenFIGI's first listing. | Domain-specific but non-negotiable for anything touching holdings — and the traps run in both directions (real dupes AND false dupes). |
| 8 | [read-the-briefing-first.md](read-the-briefing-first.md) | The pre-edit ritual: CLAUDE.md hard rules + gotchas + top HANDOVER entry, and the three questions to answer before touching code. | Force-multiplier for every other skill — it's how you find out the gotchas exist. Ranked mid-table only because CLAUDE.md itself already does the heavy lifting once you open it. |
| 9 | [never-guess-identifiers.md](never-guess-identifiers.md) | Verify every CIK, ticker, symbol, and URL live before hardcoding; degradation guarantees your typo will be a silent blank, not an error. | Narrow trigger (adding identifiers) but the failure — showing the wrong manager's portfolio under a famous name — is a trust-destroyer. |
| 10 | [no-keys-no-paywalls.md](no-keys-no-paywalls.md) | The acceptance gate for any new source, library, or widget: zero-registration or optional-key only; license AND functional fine print; vendor load-bearing assets, no runtime CDN. | Guards the project's identity. Triggered only when adding components, but a violation (the TradingView indicator cap) costs a full rip-and-replace cycle, as it already did once. |
| 11 | [be-a-good-citizen.md](be-a-good-citizen.md) | The exact throttle numbers, the User-Agent rule, what retries and what doesn't, and "reduce N requests, never touch the throttle." | The rules are simple and mostly already encoded in `client.py`; the skill's value is stopping you from "optimizing" them away under latency pressure. |
| 12 | [write-the-handover.md](write-the-handover.md) | The session-close checklist and the HANDOVER/CLAUDE.md division of labor. This is the mechanism that created every skill above. | Compounding value across sessions rather than immediate bug prevention. Skipping it once is cheap; skipping it habitually re-buys every gotcha at full price. |
| 13 | [one-view-layer.md](one-view-layer.md) | Features land in `views.py` first; Flask and MCP are thin wrappers; fixes go to the lowest owning layer. | Architecture discipline. Violations cause drift bugs (browser and AI disagree) that are annoying but loud and localized — cheaper than the silent classes above. |
| 14 | [cache-by-immutability.md](cache-by-immutability.md) | Key/TTL derived from mutability; never cache a failure; verify cold AND warm paths. | The existing caches already model the pattern; you mostly need this when adding a new one, which is rare. |
| 15 | [scope-honestly.md](scope-honestly.md) + [finish-autonomously.md](finish-autonomously.md) | How to split a big vague ask into free-buildable / optional-key / not-replicable / dangerous; and what you do and don't own when the user says "go ahead." | Judgment codified. Ranked last per-token not because it's optional but because it triggers per-session rather than per-edit — read both once, at the start of any big or delegated session. |

## How to use this library

- **Every session**: #8 (read the briefing), and at close, #12 (write the
  handover).
- **Before any edit**: know your tier (#3) and your layer (#13).
- **Before adding any new component or source**: #10 (the free-and-open
  gate), then #4 to probe it, #6 when writing its tests, #11 if it adds
  requests, #14 if it adds a cache.
- **Before saying "done"**: #1, with #2's cross-check for any number.
- **When something's broken with no error**: #5 first, always.
- **Big vague request or open delegation**: #15's pair, then the roadmap.

The skills cite each other where they interlock; the citations are the
map of how this project actually gets built: probe → build in the right
tier and layer → test against real fixtures → verify live → write it down.
