---
discussion_id: DISC-20260608-001622-review-telemetry-friction-5-6-docs-f3-fold
started: 2026-06-08T00:16:39.724292+00:00
ended: 2026-06-08T00:23:30.763096+00:00
agents: [facilitator, qa-specialist, ux-evaluator]
total_turns: 5
---

# Discussion: DISC-20260608-001622-review-telemetry-friction-5-6-docs-f3-fold

## Turn 1 — facilitator (evidence)
*2026-06-08T00:16:39.724292+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: /review of the FRICTION-5 + FRICTION-6 + docs F3 fold from REV-20260607-200447 (session 10e). Three low-risk copy/docs polishes drained from the Phase 1 Layer B live dashboard advisory backlog.
- **Files/scope**: src/telemetry/dashboard.py (_otel_link default label spelled out + new-tab announcement; _render_live_stream_panel legend extended with inline Kind glossary); tests/test_telemetry.py (updated test_absence_otel_not_active_renders_live_link assertion + new @pytest.mark.regression test_live_stream_panel_carries_kind_legend); CLAUDE.md (Pointers entry for Telemetry & Oversight per docs F3); memory/bugs/regression-ledger.md (new entry covering F5 + F6 with canary test names).
- **Developer-stated motivation**: Per the rolling handoff (HANDOFF-supervisor-rolling.md), drain another cohering subset of the 9 remaining REV-20260607-200447 advisories before starting Phase 2. The trio was the explicitly-recommended default cohort.
- **Explicit constraints**: NO push to any remote. /review required before any commit touching src/. Capture never bypassed. Quality gate already 7/7 (31 guards; 234 telemetry+server tests). Reviewers should especially check (a) the FRICTION-5 legend addresses the actually-displayed vocabulary (LiveCostEvent.kind = turn/failure), not the advisory's erroneous example (which referenced LiveEvent.kind values message/dispatch/result); (b) the OTel new-tab-announcement phrasing is right.

---

## Turn 2 — ux-evaluator (proposal)
*2026-06-08T00:22:30.465454+00:00 | confidence: 0.91*
*tags: ux, FRICTION-5, FRICTION-6, sonnet*

## Findings
**F1 (MEDIUM, emotional-design/accuracy)** - Rule: WCAG 3.3.2 'Labels or Instructions' - labels must accurately describe the data they annotate. Location: src/telemetry/dashboard.py:839 - the legend gloss 'turn = priced assistant turn'. Description: gloss is inaccurate for uncosted turns. _bump_totals (live.py:550) appends every LiveCostEvent(kind='turn') to recent_events regardless of whether the turn was costed - uncosted turns arrive with cost_usd=0.0 and kind='turn' and are displayed in the same table column with $0.0000 in the Cost cell. Gatekeeper reading the legend before scanning the table will expect every turn row to carry a cost figure. When they encounter a turn row showing $0.0000, the legend actively misleads. Recommendation: change gloss to 'turn = assistant turn (cost shown if priced tier known)' or include the uncosted nuance directly. Confidence: 0.93. Exceptions: would not apply if uncosted turns were filtered out of recent_events.

**F2 (LOW, accessibility - advisory)** - Rule: WCAG 2.4.4 'Link Purpose (In Context)'. Location: src/telemetry/dashboard.py:184 - _otel_link default label. Description: 'enable OpenTelemetry (opens in new tab)' is grammatically lowercase at sentence start (correct for inline link in prose body, fine). Parenthetical announcement is the standard convention (H33). No blocking concern. Minor improvement: rel='noopener' present and correct, but no aria-label nor visually hidden sr-only span. Screen readers will read the full label including parenthetical, which is redundant but not wrong. Confidence: 0.78. Exceptions: only applies if audience includes screen-reader users; low for the developer-gatekeeper dashboard scope.

## Strengths
- OTel label expansion correctly identifies 'enable OTel' as insider abbreviation
- Kind glossary correctly targets LiveCostEvent.kind (not LiveEvent.kind), overriding the original advisory's misread
- Placing glossary inline in existing legend <p> rather than adding a second element is right cognitive-load choice
- <strong> treatment for 'Kind:' mirrors column-header emphasis without duplicating the table header visually

## Verdict: APPROVE-WITH-CHANGES
Finding 1 is the single blocker (one-line string edit). Finding 2 is advisory.

---

## Turn 3 — qa-specialist (proposal)
*2026-06-08T00:22:47.350672+00:00 | confidence: 0.91*
*tags: qa, test-adequacy, sonnet*

## Findings
**F1 (MEDIUM, weak-assertion)** - Rule: Testing #13 - guard must fail under the actual regression scenario, not a superset. Location: tests/test_telemetry.py:3036 - 'assert "<strong>Kind:</strong>" in html'. Description: assertion pins the HTML element <strong> rather than the semantic intent (the label 'Kind:' appears prominently). The ledger entry justifies this explicitly ('using <strong> for the Kind: anchor and <code> spans for each enum so a future style change can't silently strip the mapping'). That reasoning is sound for the <code> spans (stripping <code> would remove visual distinction between enum token and gloss), less sound for <strong>: a refactor that restyles 'Kind:' as <span class='legend-label'> or <b> preserves every bit of user-visible intent but the assertion fails. Recommendation: loosen first assertion to 'assert "Kind:" in html' OR document the deliberate <strong> pin in the test docstring. Confidence: 0.82.

**F2 (LOW, missing-edge-case)** - Rule: Testing #13. Location: tests/test_telemetry.py:3019 - test_live_stream_panel_carries_kind_legend. Description: Test reaches _render_live_stream_panel through full render_live_fragment call chain rather than calling the private helper directly. This is the right call for an integration-style guard, but a regression where render_live_fragment substitutes a different panel renderer would not be caught if the new renderer produced any HTML. Low-probability. Recommendation: add a one-line inline comment explaining why the public-entry-point path was chosen. Confidence: 0.74.

**F3 (LOW, taxonomy-mismatch)** - Rule: regression-ledger taxonomy consistency. Location: memory/bugs/regression-ledger.md - new F5+F6 entry's 'Schema/Serialization Drift' root-cause class. Description: ledger class is 'Data format changes without migration'; this fix is pure copy/affordance change - no data format, no serialization, no migration. Class was carried forward from the existing FRICTION-1/2/4 entry above. The existing taxonomy has no class for 'Plain-language gap' or 'Presentation vocabulary gap'. Using mismatched class doesn't break tooling but degrades signal for the 'three consecutive failures in same class + subsystem' structural-invariant trigger. Confidence: 0.78.

**F4 (LOW, weak-assertion)** - Rule: Testing #13. Location: tests/test_telemetry.py:2111 - 'assert "enable OpenTelemetry (opens in new tab)" in html'. Description: verbatim substring match on the exact default label - any wording variation fails. Two-part assertion ('OpenTelemetry' + 'opens in new tab') would catch both intended regressions independently and be more resilient. Judgment call: if exact label wording is a UX specification (which the ledger 'Do not re-introduce the abbreviated label without an a11y review' implies), keep the exact match. Confidence: 0.70.

## Strengths
- Entry-point level (render_live_fragment) is correct for the scenario
- The two assertions that matter most (<code>turn</code>, <code>failure</code>) are structurally sound
- Canary names in the ledger are exact (both function names appear verbatim in the file)
- @pytest.mark.regression applied to both tests, consistent with file pattern
- Test isolation is clean (deterministic, no shared mutable state)
- OTel test retains three-assertion structure (URL + target=_blank + label) - prior guarantees remain independently verifiable

## Verdict: APPROVE-WITH-CHANGES
Findings 2, 3, 4 are advisory. Finding 1 is the only item that warrants a decision before merge: either loosen the <strong> pin or document it.

---

## Turn 4 — facilitator (critique)
*2026-06-08T00:23:01.931654+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 6 verified, 0 inconclusive, 0 discarded.

ux-evaluator F1 (priced-assistant-turn inaccuracy) — VERIFIED. Read src/telemetry/live.py:528-562. Confirmed _bump_totals appends cost_event (with kind='turn') to recent_events unconditionally on line 550 ('recent = (state.recent_events + (cost_event,))[-RECENT_EVENTS_CAP:]'). The 'uncosted' flag is consumed for state.total_cost_usd and state.uncosted_turns ONLY — not for recent_events filtering. So uncosted turns DO appear in the rendered Live stream as 'turn' rows with cost_usd=0.0. Gloss 'priced assistant turn' is inaccurate.

ux-evaluator F2 (a11y observation) — VERIFIED non-blocking. The visible parenthetical satisfies WCAG H33.

qa-specialist F1 (<strong> over-pin) — VERIFIED. The original assertion 'assert "<strong>Kind:</strong>" in html' did pin the element rather than the intent. Looser 'Kind:' assertion correctly catches the principle.

qa-specialist F2 (entry-point comment) — VERIFIED minor. The test docstring did not previously explain the choice.

qa-specialist F3 (taxonomy mismatch) — VERIFIED but advisory. The existing FRICTION-1/2/4 entry above already uses 'Schema/Serialization Drift' for a pure copy/CSS change, so this is a pre-existing taxonomy debt, not a regression introduced by this fold.

qa-specialist F4 (exact-label OTel assertion) — VERIFIED. The assertion is verbatim; the ledger comment 'Do not re-introduce the abbreviated label without an a11y review' justifies the exact pin as a UX-spec boundary.

---

## Turn 5 — facilitator (synthesis)
*2026-06-08T00:23:30.763096+00:00 | confidence: 0.92*
*tags: blocking:0, advisory:3, speculative:0, folded:2, model-tiers:ux-evaluator:sonnet|qa-specialist:sonnet|facilitator:opus*

## Request Context
- **What was requested**: /review of the FRICTION-5 + FRICTION-6 + docs F3 fold from REV-20260607-200447 (session 10e). Three low-risk copy/docs polishes drained from the Phase 1 Layer B live dashboard advisory backlog.
- **Files/scope**: src/telemetry/dashboard.py (_otel_link default label + Live stream legend); tests/test_telemetry.py (test_absence_otel_not_active_renders_live_link assertion update + new test_live_stream_panel_carries_kind_legend); CLAUDE.md (Pointers entry for Telemetry & Oversight); memory/bugs/regression-ledger.md (new entry covering F5 + F6 with canary names).
- **Developer-stated motivation**: Drain three more cohering REV-20260607-200447 advisories per the rolling handoff before starting Phase 2.
- **Explicit constraints**: NO push. Quality gate already 7/7 (31 guards; 234 telemetry+server tests).

## Verdict: APPROVE-WITH-CHANGES (consensus across 2 specialists, ensemble mode)
2 MED findings folded pre-commit (1 ux + 1 qa), 4 LOW advisory findings retained (1 ux, 3 qa).

## Specialist Verdicts
| Specialist | Model | Verdict | Confidence | Top finding |
|---|---|---|---|---|
| ux-evaluator | sonnet | APPROVE-WITH-CHANGES | 0.91 | F1 MED accuracy: 'priced assistant turn' gloss is inaccurate for uncosted turns (_bump_totals appends them too). **(FOLDED pre-commit)** |
| qa-specialist | sonnet | APPROVE-WITH-CHANGES | 0.91 | F1 MED weak-assertion: <strong>Kind:</strong> pin over-fits markup vs. semantic intent. **(FOLDED pre-commit)** |

## Pre-commit folds (2)
- **ux F1**: Live stream legend gloss changed from 'turn = priced assistant turn' to 'turn = assistant turn (cost shown when the model tier is priced; 0.0000 when uncosted)'. Verified against live.py _bump_totals which appends cost_event regardless of uncosted flag. The 'uncosted' clause is now load-bearing (a regression that dropped it would silently misrepresent every $0.0000 turn row).
- **qa F1**: New test_live_stream_panel_carries_kind_legend assertions loosened — 'Kind:' (no element pin), 'assistant turn', 'uncosted', 'error or non-2xx event', plus the <code>turn</code> + <code>failure</code> pins (the visually-load-bearing markup). Docstring updated to explain entry-point choice (qa F2 fold).

## Confidence annotation
0 findings in speculative section (confidence < 0.80). 0 findings retained as unscored. All findings carried confidence scores >= 0.70 — the qa F4 (0.70) and qa F2 (0.74) are below 0.80 strictly but well-grounded; retained as advisory rather than discarded.

## Model tiers
ux-evaluator:sonnet, qa-specialist:sonnet, facilitator:opus.

## Advisory findings — track for Phase 2 / follow-up
- **ux F2 (LOW a11y)** — no aria-label / sr-only span on the OTel link. Acceptable for the current loopback-only developer-gatekeeper scope.
- **qa F3 (LOW taxonomy)** — regression-ledger 'Schema/Serialization Drift' classification is a poor fit for pure copy changes; pre-existing debt from the FRICTION-1/2/4 entry above. Future work: extend the taxonomy or annotate the rationale in both entries.
- **qa F4 (LOW weak-assertion-judgment-call)** — OTel link assertion is a verbatim match; intentional per the ledger 'do not re-introduce the abbreviated label without a11y review' boundary.

## Strengths (consensus)
- Both fixes correctly target the actually-displayed vocabulary (LiveCostEvent.kind, NOT LiveEvent.kind — overriding the original advisory's misread).
- Inline legend placement in the same <p class='legend'> as the existing caption is the right cognitive-load choice.
- @pytest.mark.regression applied to both tests; canary names exact in the ledger.
- Test isolation is deterministic.
- OTel test retains URL + target=_blank + label as three independent assertions — earlier guarantees remain independently verifiable.

## Education gate
Not needed for this fold. The change is pure copy + a regression-test pin update. The fold's load-bearing nuance (uncosted-turn handling in the Live stream legend) is documented in the legend itself, the test docstring, and the regression-ledger entry — three durable surfaces. A walkthrough would not add comprehension above what the diff already conveys.

---
