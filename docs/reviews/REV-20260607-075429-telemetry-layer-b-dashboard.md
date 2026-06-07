---
review_id: REV-20260607-075429
discussion_id: DISC-20260607-075429-review-telemetry-layer-b-dashboard
date: 2026-06-07
risk_level: medium
collaboration_mode: structured-dialogue
verdict: approve-with-changes
reviewed_files:
  - src/telemetry/dashboard.py
  - scripts/telemetry/dashboard.py
  - scripts/telemetry/analyze_value.py
  - tests/test_telemetry.py
specialists: [independent-perspective, ux-evaluator, qa-specialist, security-specialist, architecture-consultant]
blocking: 1
advisory: 12
speculative: 0
---

# Review — Telemetry Layer B dashboard (render-only over A1/A2/A3)

## Request Context
- **What was requested**: Multi-agent `/review` of the north-star Layer B telemetry
  dashboard, with an explicit mandate to probe **honest-absence C4** (a visual
  surface can make a fabricated `0` look authoritative) — the highest-risk axis.
- **Files/scope**: `src/telemetry/dashboard.py` (pure render+escape+ASCII),
  `scripts/telemetry/dashboard.py` (transport assemble+main),
  `scripts/telemetry/analyze_value.py` (A3 extract-method single-path),
  `tests/test_telemetry.py` (+34 dashboard tests); `docs/reviews/artifacts/`.
- **Developer-stated motivation**: North-star dashboard for *honestly* understanding
  AI use; build = render, not new measurement.
- **Explicit constraints**: read-side only; `html.escape`; honest-absence first-class;
  plain-language; ASCII console; read-only DB; ntfy slug never printed.

## Verdict: APPROVE-WITH-CHANGES

The C4 probe did its job. The honest-absence discipline is rigorous *everywhere the
build thought to look* — failures (true-zero vs not-run via watermark), cost
(`cost_state`), cross-checks (typed `DivergenceResult.available`), escaping, and the
read-only/no-persistence contract are all clean and well-tested. **One blocking
fabricated-zero hole** survived the build and both build-checkpoints and was caught
by the independent-perspective panellist; it must be fixed before commit.

Panel: independent-perspective 0.86 (request-changes) · ux-evaluator 0.91 · qa 0.82 ·
security 0.94 · architecture 0.92 (approve). 0 findings below 0.80 confidence.

## Required changes (blocking — fix before commit)

### B1 — Fabricated `0.00x` leverage when a fee is configured but cost has not been analyzed (independent-perspective, 0.88; C4)
When `analyze_cost` has never run, `load_cost_rows` returns `[]` →
`build_cost_report([])` yields `total_cost_usd = 0.0` (finite) and
`cost_state = STATE_NOT_RUN`. `window_months` derives from *transcripts*
(independent of cost), so it can be a real number. `leverage()`'s absence guard
(`value.py:279`) is `fee is None or not math.isfinite(total)` — `0.0` is finite and
the fee is set, so it falls through to `configured=True` and renders an authoritative
`0.00x/mo` "List-price-equivalent multiple" data subtile **next to a cost panel that
says "analyzer not yet run."** `render_console_summary` has the identical defect.

**Root cause / shared blind spot**: leverage absence keys on the *fee*, never on
whether the *numerator was measured*. The failures and cost panels model
true-zero-vs-not-run; leverage inherits cost's *value* without cost's *state*. Both
build-checkpoints (arch 0.93, security 0.96) and the build reasoned about leverage
absence through the fee only.

**Fix (least-complex)**: propagate `cost_state` into the leverage presentation — when
cost is not measured, the leverage sub-panel and the console line render the honest
absence ("cost not yet measured — run `analyze_cost.py`"), regardless of the fee.
Add the failing regression test (cost not-run + configured fee + derivable window →
assert no `0.00x` headline, assert a `data-state="absent"` leverage tile).

## Recommended improvements (non-blocking — addressed this pass)

- **A1 (ux, C4 defense-in-depth)** — `_fmt_int(value or 0)` coerces `None→0`; both
  callers return `int` today, but the `int | None` signature allows a future
  fabricated `0`. Tighten to `int` (mirrors `_fmt_usd(None)→"uncosted"`).
- **A2 (ux, C4 defense-in-depth)** — `_render_attribution_block` falls back to
  `0.0% covered` (a data tile) when `available=True` but `independent_cost_usd` is
  falsy. `value.py` guarantees `available=False` on a zero denominator, so this is
  unreachable today; add a render-boundary guard so the absence is enforced where it
  is presented.
- **A3 (independent, Scenario 2)** — the leverage headline carries no prominent
  under-coverage caveat when `coverage_pct < 100`; surface a "computed on X% of
  priced tokens" note paralleling the cost panel.
- **A4 (qa)** — add an HTML-level render test for the A1 cost-panel `STATE_NOT_RUN`
  branch (assert `data-state="absent"` + `analyze_cost.py`, no `$0.00`).
- **A5 (qa)** — strengthen the transport-fidelity test to assert
  `pricing_check.divergence_pct` and `.direction` (spec R5a names them).
- **A6 (qa)** — add injection tests for `LeverageResult.reason`/`.note` and tier-name
  keys / `FailureSignal.tier` (the code itself flags `.note` with a security comment).
- **A7 (qa)** — add a render test for the non-OTel generic-absent branch of
  `_render_pricing_block`.
- **A8 (qa)** — switch the fidelity test's reference from `analyze_value` (which calls
  `init_db`) to `assemble_value_inputs` on the read-only connection (removes the
  write-side asymmetry; aligns with the single read-side path).
- **A9 (security)** — fix the `_esc_reason` docstring ("escaped upstream" is backwards;
  the escape is *downstream* in `_absence_tile`).
- **A10 (security)** — delete the dead `_query_exists` (zero source call sites).
- **A11 (ux)** — add a one-line plain-language legend to the attribution sub-panel.

## Carried advisories (non-blocking, tracked)

- **A-ARCH1 (architecture, A-INFO1)** — the dashboard does *not* add a new direct
  consumer of `ingest_token_usage._*` private helpers (reached transitively → smell
  *reduced* on the dashboard path), but the underlying 4-consumer condition remains
  live across A1/A2/A3. Promote the four helpers to a public surface in one change
  when A-ARCH1 is taken up (Rule of Three is well past satisfied). Do not let it
  expand to a fifth consumer silently.
- **ux A-LOW** — the absence icon glyph (`○`) is decorative (`aria-hidden`); the
  dashed border + copy carry the distinction. Optional polish.

## Strengths

- The true-zero-vs-not-run distinction (the spec's hardest requirement) is implemented
  correctly for failures and cost — distinct classes, `data-state`, and copy.
- `_fmt_usd(None) → "uncosted"` + per-tier `class="uncosted"` is the right primitive,
  applied consistently; no `$0.00` for an unknown tier in any rendered fixture.
- Single `_esc` escaping seam (`quote=True`) at every emission point; the
  transcript-tool-name → `FailureSignal.signature` vector is escaped; read-only
  `?mode=ro` enforced at the driver level and regression-tested; no slug/env leak on
  any path (tested behaviorally).
- Single-path A3 verified genuine (architecture): `assemble_value_inputs` is the one
  read-only assembler, the `a1_report` passthrough is a single source of truth, the
  fidelity test asserts field-for-field equality, and the scripts→src layer direction
  is clean (`src/` never imports `scripts/`).

## Discarded findings

None. All findings were verified true, latent-true, or inconclusive-but-retained.

## Education gate

**Recommended.** Medium risk + the C4 honest-absence axis is conceptually load-bearing
for the manager-gatekeeper. Run an interactive teach-the-gatekeeper walkthrough
(`feedback_teach_dont_dump` — one concept at a time, analogy-first, the "why" of
honest-absence and the fabricated-zero fix), then explain-back, before commit.
