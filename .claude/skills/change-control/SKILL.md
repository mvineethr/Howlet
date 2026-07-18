---
name: change-control
description: Load before making ANY change to a repo you did not just write — especially when adding a dependency/data source, modifying existing behavior, touching a throttle/validation/license, or when you just landed in an unfamiliar project and need to learn its non-negotiable rules before editing. Also load when a user request appears to conflict with a documented project rule, or when writing down a new project rule so it carries its rationale and incident.
---

# Change control: classify the change, find the non-negotiables, gate accordingly

Every repo has a small set of rules whose violation costs a user-facing
incident, a banned API client, or a license problem — and a much larger set
of code you can edit freely. This skill tells you how to (1) classify any
change by risk class and apply the right gate, (2) discover a fresh repo's
non-negotiables in ~10 minutes before your first edit, and (3) record rules
so each one carries its RATIONALE and the INCIDENT behind it. Without this,
you either move too slowly (treating every edit as dangerous) or — worse —
"clean up" a weird-looking constant that was the fix for a production
incident, and re-fight a settled battle.

## 1. Change classification and gates

Classify every change into the FIRST row that matches, top to bottom
(a change matching multiple rows takes the strictest — highest — row).

| Class | Definition | Gate before it merges |
|---|---|---|
| **Rule-touching** | Modifies, weakens, or removes anything a project doc or code comment marks as a hard rule: throttles, validation, license/vendoring decisions, identity constraints ("no API key ever") | STOP. Do not implement first. Surface the collision to the human with the rule quoted verbatim and its source (see section 4). Only proceed with explicit sign-off, and record the rule amendment with a new rationale + incident entry |
| **Dependency-adding** | New library, data source, API, embed, service, or vendored asset | Run the dependency gate BEFORE technical evaluation: access model (works under the project's key/cost constraints?), license, functional fine print (does a free tier cap something your users will hit?), runtime independence (vendor load-bearing assets, no CDN). Record rejected candidates and why. See external-data-integration for the full gate |
| **Behavior-changing** | Alters what existing code produces: output values, formats, API shapes, defaults, error handling, semantics of a field | Full offline suite green AND live verification of the changed path against the real system (offline mocks have repeatedly agreed with code and disagreed with reality) AND a regression test pinning the new behavior AND a chronicle entry (see failure-archaeology) if the change fixes a bug |
| **Config/interface-adding** | New env var, CLI flag, endpoint, tool, or cache | Must default to working when unset (new config is optional unless the project already requires it); documented in the project's config catalog (see config-and-flags); offline suite green |
| **Additive** | New feature or module that does not modify existing code paths | Offline tests for the new code; live verification of the new path; existing suite still green |
| **Docs-only** | Comments, README, chronicle, briefs — zero executable change | Read what you changed once for accuracy; verify any command you documented actually runs. Volatile numbers (test counts, versions) get a date stamp |

Rules of thumb:

- **When unsure between two classes, take the stricter one.** The cost of
  over-gating is minutes; the cost of under-gating is a live incident.
- **A "small" diff is not a low class.** Changing one constant
  (`_MIN_INTERVAL_SECONDS = 0.12` → `0.01`) is rule-touching, not a tweak.
- **Refactors are behavior-changing until proven otherwise** — the proof is
  the full suite plus live verification of at least one refactored path.
- **Deleting code that looks dead is behavior-changing.** Search for the
  incident that put it there first (section 2, step 5).

## 2. Discover the non-negotiables: fresh-repo runbook

Run this BEFORE your first edit in any repo you did not write. Budget
~10 minutes. Output: a written list of rules, each with its source file.

**Step 1 — Find the project brief.** Read it end to end; a "hard rules" or
"constraints" section is the highest-authority source.

```sh
ls CLAUDE.md AGENTS.md CONTRIBUTING.md CONTRIBUTING.rst .cursorrules \
   .github/copilot-instructions.md docs/CONTRIBUTING.md 2>/dev/null
```

**Step 2 — Find the chronicle / history.** Incident history explains WHY
rules exist. If there is no git history (it happens — the exemplar repo was
never `git init`ed), a handover/changelog file is the only chronicle.

```sh
ls HANDOVER.md CHANGELOG.md docs/adr/ docs/decisions/ NOTES.md 2>/dev/null
git log --oneline -20 2>/dev/null   # absent or empty means: rely on the files above
```

**Step 3 — Grep for imperative-voice comments in code and docs.** Authors
mark landmines with "never", "don't", "keep", "must", "required by".

```sh
# In docs (case-insensitive; adjust the file list to the repo):
grep -rniE 'never|must not|do ?not|don.t|hard rule|non-negotiab|always (require|keep)' \
  --include='*.md' . | grep -vi node_modules

# In source (add the repo's extensions):
grep -rniE '(never|do ?not|don.t|must|required by|keep (this|every)|by design|deliberate)' \
  --include='*.py' --include='*.js' --include='*.ts' src/ lib/ 2>/dev/null
```

**Step 4 — Read the enforcement points.** Validation that raises on purpose
is a rule in executable form; weakening it is rule-touching.

```sh
grep -rn 'raise ValueError\|raise RuntimeError\|throw new Error\|assert ' src/ 2>/dev/null \
  | grep -iE 'must|require|need|invalid'
```

**Step 5 — Read test names for encoded rules.** Tests named `*_rejects_*`,
`*_requires_*`, `*_prefers_*`, `*_does_not_*` pin decisions someone paid
for. Never delete one to make a change pass — that IS the collision signal.

```sh
grep -rnE 'def test_.*(reject|require|refus|invalid|forbid|prefer|not_)' tests/ 2>/dev/null
# JS equivalent: grep -rnE "(it|test)\(['\"].*(reject|require|never|not )" test/ tests/ 2>/dev/null
```

**Step 6 — CI, lint, and license config.** CI is the mechanized gate; lint
configs encode style rules you should not argue with; LICENSE constrains
what you may vendor or depend on.

```sh
cat .github/workflows/*.yml .gitlab-ci.yml Makefile 2>/dev/null | head -80
ls .flake8 ruff.toml .eslintrc* pyproject.toml setup.cfg 2>/dev/null
head -5 LICENSE* 2>/dev/null
```

**Step 7 — Environment and config surface.** Anything read from the
environment is a user-facing contract.

```sh
grep -rn 'os\.environ\|getenv\|process\.env' src/ lib/ 2>/dev/null | grep -v test
```

**Step 8 — Write the list down** in the rule format below (section 3), one
entry per rule, citing the source file. If the repo has a brief, propose
adding any undocumented rules you found to it (that addition is docs-only).

### Worked example (edgar, 2026-07-07)

Running this runbook on the exemplar repo (`D:\src\edgar`) yields, among
others: step 1 finds `CLAUDE.md` with an explicit "Hard rules" section
(no required API key ever; never relax SEC User-Agent validation; keep
every self-throttle; SEC authoritative / market data decoration; no
paywalled UI components; verify live before done). Step 2 finds
`HANDOVER.md` — the only chronicle, since the repo has no git history.
Step 4 finds the enforcement point in `src/edgar/client.py`: the
constructor raises `ValueError` when `"@" not in user_agent`, because the
SEC requires a contact email in the User-Agent. Step 5 finds tests like
the HTML-search-parsing regression test pinning the decision to never
revert to SEC's broken `output=atom` endpoint. Step 7 finds exactly three
env vars: `EDGAR_USER_AGENT` (required), `FRED_API_KEY` and
`OPENFIGI_API_KEY` (optional enrichers).

## 3. Recording rules: the rationale-and-incident format

A rule without its rationale gets "optimized" away by the next person. A
rule without its incident gets re-litigated. Record every non-negotiable in
this format, in the project brief (rule) and chronicle (incident detail):

```
RULE:      <one imperative line — what to do or never do>
SCOPE:     <what code/decisions it governs>
RATIONALE: <why, 1-2 lines — the mechanism, not just "it's important">
INCIDENT:  <date + what actually happened (or would happen) when violated;
            where the full story is chronicled>
ENFORCED:  <the code/test/CI that catches a violation, or "convention only">
```

### Worked examples (edgar — all four verified against CLAUDE.md, HANDOVER.md, and the code, 2026-07-07)

```
RULE:      No required API key, ever; no paywalled or proprietary component
           in the UI.
SCOPE:     Every new data source, library, widget, or embed.
RATIONALE: The project's identity is "free, no-API-key, open-source". A
           free-to-embed component whose free tier caps a feature is a
           paywall inside the product; license and business model are
           SEPARATE checks.
INCIDENT:  2026-07-07 (HANDOVER.md): TradingView's advanced-chart embed —
           free to embed, integrated and working — capped stacked
           indicators at 2 on the free tier (more required a subscription).
           It was removed entirely, not feature-flagged, and replaced with
           KLineChart (Apache-2.0, ~30 indicators, no cap), first via CDN
           and then vendored into static/ with its LICENSE. Keyed-but-free
           FRED went in the other door: optional FRED_API_KEY, every screen
           complete without it.
ENFORCED:  Convention + review; vendored LICENSE files ship in-repo.
```

```
RULE:      Never relax the SEC User-Agent validation.
SCOPE:     EdgarClient constructor (src/edgar/client.py); every SEC call.
RATIONALE: SEC requires a real name + contact email in the User-Agent;
           anonymous/generic UAs get blocked — and the block lands on the
           USERS of the tool, not on the developer who relaxed the check.
INCIDENT:  Preventive rule (no violation on record): the constructor has
           raised ValueError on user_agent without "@" since the first
           live verification session (2026-06-30, HANDOVER.md).
ENFORCED:  ValueError in EdgarClient.__init__; exercised by the test suite.
```

```
RULE:      Keep every self-throttle; the throttle is never the performance
           knob.
SCOPE:     SEC ~10 req/s (0.12s interval in client.py), Yahoo 0.25s,
           OpenFIGI 5 CUSIPs per 3s keyless.
RATIONALE: These are good-citizen limits on free public endpoints, not
           technical ceilings — the endpoint accepts faster traffic today
           and rate-limits or bans your users tomorrow. Reduce request
           COUNT instead: cache immutable data, batch, consolidate.
INCIDENT:  2026-07-06 (HANDOVER.md): the screener fetched a multi-megabyte
           SEC companyfacts document TWICE per symbol across a ~45-name
           universe; the pre-release fix consolidated to one fetch plus a
           per-ticker-per-day disk cache — volume halved then mostly
           eliminated, throttle untouched. Slow first loads (~20s via
           OpenFIGI keyless) were solved with a forever-cache, not a
           faster hammer.
ENFORCED:  _MIN_INTERVAL_SECONDS constant + code review; tests are offline
           so "tests are slow, lower the throttle" is always a false trail.
```

```
RULE:      SEC data is authoritative; market data is decoration. Fragile
           sources degrade to "unavailable", never raise into core views.
SCOPE:     Everything built on Yahoo/OpenFIGI/RSS, especially anything on
           the cookie+crumb tier (yahoo_auth.py consumers).
RATIONALE: The 13F views are the product; enrichment failing must cost a
           missing price, not a broken page. Unofficial endpoints get
           walled off without notice (Yahoo put v7/quote, v10/quoteSummary,
           v7/options behind cookie+crumb).
INCIDENT:  2026-07-07 (HANDOVER.md, live-found bug #6): SEC reset stale
           keep-alive connections (WinError 10054); the un-caught
           ConnectionError became an HTML 500 the frontend showed as
           "Unexpected token '<'". Fix: retry ConnectionError like a 5xx
           AND map every requests.RequestException to a JSON 502.
ENFORCED:  Degrade-paths in each consumer; Flask errorhandler; tests
           108 -> 111 added that session.
```

## 4. When a requested change collides with a non-negotiable

Surface, don't route around. The procedure:

1. **Stop implementing.** Do not build the compliant 80% and quietly bend
   the rule for the rest. Do not delete/skip the pinning test.
2. **Quote the rule verbatim with its source** (file + section) back to the
   requester, plus the incident behind it if recorded — the incident is
   usually more persuasive than the rule.
3. **Offer the compliant alternative(s)** if any exist. Often the request's
   goal survives the rule: "faster loads" → cache, not throttle removal;
   "that charting widget" → an open-source equivalent, vendored.
4. **If the human explicitly decides to change the rule**, treat that as a
   rule-touching change: update the rule's entry (new RATIONALE, note the
   old rule and why it changed, date it) in the brief and chronicle. A rule
   silently violated is worse than a rule openly amended.
5. **Record the outcome either way** — including "considered and rejected"
   for the requested approach, so nobody re-evaluates it from scratch.

Never acceptable: implementing the violation "temporarily"; weakening a
validation "just for tests"; adding a config flag whose only purpose is to
bypass a hard rule by default.

## When NOT to use this skill

- Evaluating a specific third-party API/feed in depth (trust tiers, auth
  drift, degradation design) → see **external-data-integration**; this
  skill only tells you a dependency change needs that gate.
- Writing the incident chronicle itself, or mining history for a bug you
  are re-hitting → see **failure-archaeology**.
- Documenting design decisions and invariants that are architectural
  rather than rules-of-conduct → see **architecture-contract**.
- Deciding what counts as verification evidence for a gate → see
  **validation-and-qa**.
- Running a full improvement campaign in a new repo (which routes its
  promotions through this skill) → see **improvement-campaign**.

## Provenance and maintenance

- Written 2026-07-07 against the edgar exemplar (`D:\src\edgar`).
- All exemplar incidents verified against `HANDOVER.md` (sessions
  2026-06-30 through 2026-07-07 part 2) and `CLAUDE.md` "Hard rules";
  the User-Agent validation and `_MIN_INTERVAL_SECONDS = 0.12` verified
  directly in `src/edgar/client.py`.
- Volatile facts: the exemplar's test count (111 passing as of
  2026-07-07 — CLAUDE.md's "108" was already stale, which is why counts
  here are date-stamped), the exemplar's env-var list, and the grep file
  lists in section 2 (adapt extensions per repo).
- Re-verify: `python -m pytest tests -q  # or your project's suite` for
  the count; `grep -n '"@" not in user_agent' src/edgar/client.py` and
  `grep -n '_MIN_INTERVAL_SECONDS' src/edgar/client.py` for the
  exemplar enforcement points.
