# Skill: Close every session by writing the handover

## When to use
At the end of every working session, and immediately after any live-found
bug (write the gotcha while the pain is fresh). This project's continuity
lives in two files with different jobs:
- `HANDOVER.md` — the narrative log: what happened this session and why.
  Newest first.
- `CLAUDE.md` — the standing brief: what is ALWAYS true. Only durable
  facts graduate here.

## Procedure — the session-close checklist
1. Run `pytest tests/` one last time; note the count (the log tracks it:
   "Tests 106 -> 108").
2. Prepend a new HANDOVER.md entry with exactly these sections:
   - **What was asked** — the user's request, including scope decisions
     and their attribution ("Schwab = not now" — user's call, not yours).
   - **Decisions** (when non-obvious) — what you chose and the reason,
     especially rejected alternatives ("KLineChart replaces TradingView
     because...").
   - **Changes** — per-module, one line each. Match the module-map names.
   - **Verified live** — dated, with the actual commands/screens and the
     ACTUAL NUMBERS you saw ("AMZN DES: 123 candles; last bar O 243.79
     ... matches the user's TradingView screenshot"). Numbers, because a
     future session can re-run the check and compare.
   - **Open** — what is unfinished, untested, or deferred, with enough
     context to pick up cold ("FRED path needs a real-key test once the
     user signs up").
3. Update CLAUDE.md only where standing truth changed:
   - New live-found bug → one line in **Gotchas**, phrased as the trap
     plus the rule ("Yahoo `chartPreviousClose` is the close before the
     RANGE start... use the second-to-last bar").
   - Feature shipped and verified → move it into **Status**.
   - Roadmap reordered → renumber **Next features**.
4. Anything "built but not verified live" gets flagged as such in BOTH
   files (Status says "Known-untested: FRED with a real key").
5. If a scope item was deferred by the user, record it as deferred-by-user
   so the next session doesn't re-pitch it or wrongly assume it's dead.

## Rules I was following
- The handover is written for someone with NO memory of the session —
  which is literally the next session's reality. If a sentence relies on
  context only you have, expand it.
- Gotchas earn their place by cost: every entry in CLAUDE.md's list
  represents a real live-debugging session. Don't dilute the list with
  hypotheticals; do add every genuinely paid-for lesson.
- "Verified live" entries must be falsifiable: date + command + observed
  value. "Dashboard works" cannot be re-checked; "9-point curve for
  2026-07-06, 10y 4.48%" can.
- Record correct-but-surprising output explicitly ("GOOGL/GOOG as two
  rows is CORRECT — different CUSIPs") so a future maintainer doesn't
  'fix' it. Documenting non-bugs prevents regressions too.

## Worked example (this project)
The 2026-06-30 entry is the template. It records: what was asked
(including the delegation "nothing going through my head, go ahead and
finish"), each work item with its reasoning (why pagination was probed
against Icahn before coding), the live-found atom-search bug with its
regression test name, the exact test count (4 → 11), the live commands
run, the `EDGAR_USER_AGENT` used, and an Open section precise enough
that the pre-2013 SGML item could be picked up cold months later — it
even names the verification procedure ("find an old 13F-HR via
`edgar search`, fetch its filing index live, confirm the error message
is useful"). Every later session was faster because of that entry.

## Anti-patterns
- Writing the handover from memory a day later. Half the numbers and all
  the dead ends are gone by then.
- Putting session narrative into CLAUDE.md or standing rules only into
  HANDOVER.md. Wrong file = invisible at the moment it's needed.
- An Open section that says "polish remaining." Name the item, the state
  it's in, and the first command the next person should run.
