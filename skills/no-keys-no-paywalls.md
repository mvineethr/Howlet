# Skill: The free-and-open constraint governs design, not just docs

## When to use
Evaluating any new data source, library, widget, or dependency. This is the
project's identity: "free, no-API-key, open-source." Every design decision
gets filtered through it BEFORE technical merit is even considered.

## Procedure — the acceptance gate for any new component
1. **Data sources**: can it be used with zero registration? If yes, it's a
   candidate. If it needs a free key (FRED, OpenFIGI), it may ONLY be an
   optional enricher: the env var is optional, and every feature must
   render sensibly without it. If it needs payment, it is rejected — there
   is no "we'll make it optional" path for paid sources; don't even wrap it.
2. **Libraries/widgets**: check the license (must be genuinely open —
   Apache/MIT/BSD) AND check the *functional* fine print: does the free
   tier cap something (indicator stacking, request volume, branding) that
   pushes users toward a subscription? A free-to-embed widget with paid
   limits is a paywalled component. Reject it.
3. **Runtime independence**: no CDN at runtime for anything load-bearing.
   Bundle the asset into the package (KLineChart is installed from npm,
   pinned 9.8.12, and bundled into `static/app`; no CDN at runtime). An
   open-source tool that breaks offline or when a third-party CDN changes paths isn't done.
4. **Verify the license file ships**: vendored code carries its LICENSE
   into the repo, next to the asset.
5. When a candidate fails the gate, record WHAT it was and WHY it failed in
   HANDOVER.md, so the next person doesn't re-evaluate it from scratch.

## Rules I was following
- "No required API key, ever" is absolute. The test: a user who clones the
  repo, sets only `EDGAR_USER_AGENT`, and runs the dashboard must get a
  working product. Keys only ever ADD data.
- A component's license and its business model are separate checks.
  TradingView's widget is free to embed — and caps stacked indicators
  behind a subscription. It passed the license sniff test and failed the
  paywall test in production.
- Unofficial-but-free (Yahoo v8 chart, cookie+crumb) is acceptable ONLY in
  the degrade-never-break tiers (see degrade-never-break.md). Free and
  fragile is fine for decoration; the authoritative tier is SEC only.

## Worked example (this project)
The charting saga (2026-07-07). DES needed serious charting; TradingView's
advanced-chart embed was integrated first — huge study library, free to
embed, worked in one session. Then the user hit the real constraint: the
free widget allows 2 stacked indicators; more requires a subscription.
That's a paywalled component inside an open-source terminal, so it was
removed entirely — not feature-flagged, removed. Replacement: KLineChart
(Apache-2.0), ~30 built-in indicators with no stacking limit, rendering
OUR OWN OHLCV (so no third party controls the chart), first loaded from
CDN and then vendored into `static/` for offline/open-source distribution.
Live verification: 10 indicators stacked simultaneously.

The FRED integration shows the other side of the gate: it's genuinely
useful, needs a free key, so it went in behind optional `FRED_API_KEY` —
`macro_view` includes `fred_series` only when the key is set, and the ECO
screen is complete without it (Treasury + BLS are keyless).

## Anti-patterns
- "It's free for our use case." If any adjacent capability is paid, users
  will hit the wall exactly like the TradingView indicator cap.
- Adding a paid API as the default path with a free fallback. The rule is
  inverted: free is the path; keys enrich.
- Loading a vendored-able asset from a CDN "temporarily." The CDN path
  itself burned a session (`dist/umd/...` vs `dist/` 404ing silently).
