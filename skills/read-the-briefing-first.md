# Skill: Read the briefing before touching anything

## When to use
At the start of every session, before your first edit, and before answering
any "how does X work" question about this repo.

## Procedure
1. Read `CLAUDE.md` completely. It has five sections; the two that prevent
   damage are **Hard rules** and **Gotchas**. Treat every gotcha as a bug you
   will reintroduce if you don't know it.
2. Read the **top entry** of `HANDOVER.md` (newest session is first). It tells
   you what state the code was left in, what was verified, and what is open.
   Read older entries only if your task touches something they describe.
3. Restate the task to yourself in one sentence, then answer three questions
   in writing before any edit:
   - Which modules from the CLAUDE.md module map will this touch?
   - Which hard rule is closest to being violated by the obvious approach?
   - Which gotcha is closest to the data I'm about to handle?
4. Check the **Next features** list in CLAUDE.md. If the task matches an item
   there, the priority order and any notes ("verify each CIK via
   `edgar search` before adding; never guess") are instructions, not
   suggestions.
5. Only then open source files.

## Rules I was following (written down)
- The gotchas list is a list of *paid-for* knowledge. Each entry cost a live
  debugging session. Never "simplify" code in a way that deletes the reason a
  gotcha exists (e.g., don't switch company search back to `output=atom`
  because it looks cleaner — it is broken server-side).
- If CLAUDE.md and the code disagree, the code is newer only if the top
  HANDOVER entry says so; otherwise assume you misread the code.
- If your plan requires relaxing a hard rule (adding a required API key,
  removing a throttle, letting a Yahoo failure raise), stop. The plan is
  wrong, not the rule.

## Worked example (this project)
Task: "add more indicators to the chart." The obvious approach is a
TradingView widget — it has hundreds of indicators built in. CLAUDE.md's hard
rule "No paywalled or proprietary components in the UI" plus the gotcha
"TradingView was removed because its free widget caps stacked indicators
behind a subscription" tells you this exact approach was already tried,
shipped, and ripped out in the 2026-07-07 session. The correct move (which is
what happened) was KLineChart (Apache-2.0), vendored into `static/`. Reading
the briefing first saves you from re-shipping a known-rejected design.

## Anti-patterns
- Grepping for a function name and editing it without knowing which tier
  (authoritative SEC vs. fragile Yahoo) it lives in.
- Treating README.md as the dev brief. It's user-facing; CLAUDE.md is yours.
- Skimming HANDOVER.md's "Verified live" sections. Those tell you the exact
  commands and screens that prove the system works — you will need them to
  verify your own change (see verify-live-before-done.md).
