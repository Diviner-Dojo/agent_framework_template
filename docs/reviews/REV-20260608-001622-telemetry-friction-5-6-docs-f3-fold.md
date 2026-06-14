---
review_id: REV-20260608-001622
discussion_id: DISC-20260608-001622-review-telemetry-friction-5-6-docs-f3-fold
pr_id: ""
risk_level: low
collaboration_mode: ensemble
exploration_intensity: low
agents_activated: [ux-evaluator, qa-specialist]
reviewed_files:
  - src/telemetry/dashboard.py
  - tests/test_telemetry.py
  - CLAUDE.md
  - memory/bugs/regression-ledger.md
rounds: 1
consensus_reached: true
verdict: approve-with-changes
confidence: 0.91
review_duration_minutes: 8
---

## Summary

Review of the FRICTION-5 + FRICTION-6 + docs F3 fold from REV-20260607-200447 (session 10e) — three low-risk copy/docs polishes drained from the Phase 1 Layer B live dashboard advisory backlog. Both specialists returned APPROVE-WITH-CHANGES (0.91 confidence each) with one MEDIUM finding apiece, both folded pre-commit. The MED folds materially harden the change: ux F1 corrected a copy-accuracy bug (the original gloss "priced assistant turn" was misleading for uncosted-tier rows, which `_bump_totals` also appends to `recent_events`), and qa F1 loosened the new test's `<strong>Kind:</strong>` element pin to a semantic `Kind:` intent pin so a future CSS-only restyle does not false-positive.

## Request Context

- **What was requested**: /review of the FRICTION-5 + FRICTION-6 + docs F3 fold from REV-20260607-200447 (session 10e). Three low-risk copy/docs polishes drained from the Phase 1 Layer B live dashboard advisory backlog.
- **Files/scope**: src/telemetry/dashboard.py (`_otel_link` default label spelled out + new-tab announcement; `_render_live_stream_panel` legend extended with inline Kind glossary); tests/test_telemetry.py (updated `test_absence_otel_not_active_renders_live_link` assertion + new `@pytest.mark.regression test_live_stream_panel_carries_kind_legend`); CLAUDE.md (Pointers entry for Telemetry & Oversight per docs F3); memory/bugs/regression-ledger.md (new entry covering F5 + F6 with canary test names).
- **Developer-stated motivation**: Per the rolling handoff (`HANDOFF-supervisor-rolling.md`), drain another cohering subset of the 9 remaining REV-20260607-200447 advisories before starting Phase 2. The trio was the explicitly-recommended default cohort.
- **Explicit constraints**: NO push to any remote. /review required before any commit touching src/. Capture never bypassed. Quality gate already 7/7 (31 guards; 234 telemetry+server tests). Reviewers should especially check (a) the FRICTION-5 legend addresses the actually-displayed vocabulary (`LiveCostEvent.kind` = `turn`/`failure`), not the advisory's erroneous example which referenced `LiveEvent.kind` values `message`/`dispatch`/`result`; (b) the OTel new-tab-announcement phrasing.

## Findings by Specialist

### UX Evaluator (sonnet)
- **F1 (MEDIUM, emotional-design/accuracy — FOLDED pre-commit)**: WCAG 3.3.2 — gloss "turn = priced assistant turn" is inaccurate for uncosted turns. `_bump_totals` (live.py:550) appends every `LiveCostEvent(kind="turn")` to `recent_events` regardless of whether the turn was costed — uncosted turns arrive with `cost_usd=0.0` and `kind="turn"` and are displayed with `$0.0000` in the Cost cell. Gatekeeper reading the legend before scanning the table will expect every `turn` row to carry a cost figure; encountering a `$0.0000` row, the legend actively misleads. **Fix applied**: gloss changed to "turn = assistant turn (cost shown when the model tier is priced; 0.0000 when uncosted); failure = error or non-2xx event." The "uncosted" clause is now load-bearing — the regression test pins it.
- **F2 (LOW, accessibility — advisory)**: WCAG 2.4.4 — "enable OpenTelemetry (opens in new tab)" satisfies WCAG H33 (visible parenthetical announcement). The link uses `rel="noopener"` correctly. Minor non-blocking observation: no `aria-label` nor visually hidden `<span class="sr-only">`. Screen readers will read the parenthetical, which is redundant but not wrong. Acceptable for the loopback-only developer-gatekeeper scope.
- Confidence: 0.91

### QA Specialist (sonnet)
- **F1 (MEDIUM, weak-assertion — FOLDED pre-commit)**: Testing #13 — the original assertion `assert "<strong>Kind:</strong>" in html` pinned the HTML element rather than the semantic intent. A future restyle to `<span class="legend-label">` or `<b>` preserves user-visible intent but the assertion fails. The `<code>` span assertions ARE correctly element-pinned (stripping `<code>` would remove the load-bearing visual distinction between enum tokens and gloss prose). **Fix applied**: loosened to `assert "Kind:" in html`; the docstring now explains the intent-over-markup choice + why `<code>` is element-pinned + why the public `render_live_fragment` entry-point was chosen (qa F2 fold same pass).
- **F2 (LOW, missing-edge-case — FOLDED pre-commit in F1 docstring revision)**: Testing #13 — test reached `_render_live_stream_panel` through the full `render_live_fragment` call chain. The transport-layer entry-point is right for this scenario, but the docstring did not previously explain why. **Fix applied**: docstring now includes the entry-point rationale.
- **F3 (LOW, taxonomy-mismatch — advisory)**: regression-ledger "Schema/Serialization Drift" classification is a poor fit for pure copy changes (no data format, no serialization, no migration). Pre-existing debt: the FRICTION-1/2/4 entry above uses the same class for CSS vocabulary + badge text. Using the mismatched class doesn't break tooling but degrades signal for the "three consecutive failures in same class + subsystem" structural-invariant trigger. Carried forward as Phase-2-or-later taxonomy work.
- **F4 (LOW, weak-assertion judgment call — advisory)**: Testing #13 — `assert "enable OpenTelemetry (opens in new tab)" in html` is a verbatim substring match; any wording variation fails. Intentional per the ledger comment ("Do not re-introduce the abbreviated label without an a11y review") — exact label is a UX-spec boundary, not an evolvable copy element. No change.
- Confidence: 0.91

## Required Changes Before Merge

None — both MED findings folded pre-commit (ux F1 + qa F1).

## Recommended Improvements (Non-Blocking)

1. **ux F2** — Add `aria-label` or visually hidden new-tab announcement to `_otel_link` if the dashboard's audience scope ever expands beyond loopback-only developer-gatekeepers.
2. **qa F3** — Extend the regression-ledger root-cause taxonomy with a "Presentation Vocabulary Gap" class (or similar) so pure copy/affordance changes are not classified as "Schema/Serialization Drift". Apply retroactively to the FRICTION-1/2/4 + FRICTION-5/6 entries.
3. **qa F4** — Document in the ledger why the exact OTel label is a UX-spec boundary (already partially implied by the "do not re-introduce the abbreviated label without a11y review" note; could be made explicit).

## Speculative Findings — Lower Confidence

None. The two findings with confidence < 0.80 (qa F4 at 0.70 and qa F2 at 0.74) are well-grounded judgment calls retained as advisory rather than discarded — neither met the speculative threshold strictly, but both have actionable framing.

## Developer Assessment (Counterfactual)

For each blocking finding, the developer may optionally tag:
- **would-have-caught**: Developer would have found this without the review
- **would-have-missed**: Developer would NOT have found this without the review

The ux F1 (priced-assistant-turn semantic bug) is a strong "would-have-missed" candidate: the gloss matched the surface-level intuition of "turn = a billable assistant exchange" and only the specialist's read of `_bump_totals`' append-unconditional logic surfaced the uncosted edge case. The qa F1 (`<strong>` over-pin) is a typical "test-tightness" finding a specialist review reliably catches — judgment call whether the developer would have caught it on a second pass.

## Education Gate

- **Required**: no
- **Scope**: not applicable — this is a copy + test-pin polish fold
- **Bloom's levels**: not applicable
- **Mastery tier**: not applicable
- **Rationale**: The fold's load-bearing nuance (uncosted-turn handling in the Live stream legend) is documented in the legend itself, the test docstring, and the regression-ledger entry — three durable surfaces. A walkthrough would not add comprehension above what the diff already conveys.
