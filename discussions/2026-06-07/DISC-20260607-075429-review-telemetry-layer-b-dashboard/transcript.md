---
discussion_id: DISC-20260607-075429-review-telemetry-layer-b-dashboard
started: 2026-06-07T07:54:44.488537+00:00
ended: 2026-06-07T08:01:00.638528+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist, security-specialist, ux-evaluator]
total_turns: 8
---

# Discussion: DISC-20260607-075429-review-telemetry-layer-b-dashboard

## Turn 1 — facilitator (evidence)
*2026-06-07T07:54:44.488537+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Multi-agent /review of the Layer B telemetry dashboard (render-only over A1/A2/A3 outputs). The developer's directive explicitly requires the review to probe honest-absence C4 (fabricated-zero risk) — the highest-risk axis per SPEC-20260607-064958.
- **Files/scope**: src/telemetry/dashboard.py (pure render+escape+ASCII); scripts/telemetry/dashboard.py (transport assemble+main); scripts/telemetry/analyze_value.py (A3 extract-method single-path); tests/test_telemetry.py (+34 dashboard tests). Reviewability artifacts: docs/reviews/artifacts/ (3 per-state HTML samples; PNG-capture boundary declared).
- **Developer-stated motivation**: North-star Layer B dashboard for understanding AI use; A1/A2/A3 were the data foundation. Build = render, NOT new measurement.
- **Explicit constraints**: read-side functions ONLY (NEVER analyze_cost/analyze_failures/init_db); html.escape in Python not raw innerHTML (escape every transcript-shaped field incl. FailureSignal.signature); honest-absence as first-class visual states (true-zero=data tile, not-yet-run=distinct absence tile, OTel=live enable link; WCAG 1.4.1 shape-not-color); plain-language (A1 pay-per-use legend, A3 List-price-equivalent multiple); ASCII-only console (cp1252); read-only DB ?mode=ro, no persistence; ntfy slug never printed. Spec carries 5 folded blocking findings (R1-R8/R2a/R3a/R5a) + Steward C1-C9.

---

## Turn 2 — independent-perspective (proposal)
*2026-06-07T07:59:35.954827+00:00 | confidence: 0.86*
*tags: blocking:1, advisory:1, c4-probe, instance:independent-analyst*

REQUEST-CHANGES (0.86). BLOCKING FINDING 1 (0.88): fabricated 0.00x leverage when a subscription fee IS configured but the cost analyzer has not run. Path: load_cost_rows returns [] -> build_cost_report total_cost_usd=0.0 (finite), cost_state=NOT_RUN; window_months derives from transcripts (independent of cost); value.py:279 absence guard is (fee is None or not finite(total)) -> 0.0 is finite + fee set -> configured=True branch -> renders authoritative 0.00x/mo headline beside a cost panel that says analyzer-not-yet-run. Console summary same defect (no not-run qualifier on the leverage line). Root cause / shared blind spot (build + arch 0.93 + security 0.96): leverage absence keys on the FEE, never on whether the NUMERATOR was measured; the failures+cost panels model true-zero-vs-not-run via watermarks but leverage inherits cost VALUE without cost STATE. The assembly comment scripts/telemetry/dashboard.py:165-169 is the fingerprint (assumes no fee on an un-analyzed DB). Fix (least-complex): propagate cost_state into leverage absence (typed absence cost-not-measured) OR gate the leverage subtile + console line on cost-measured. Make LeverageResult.available three-part like DivergenceResult (fee AND measured AND finite). SCENARIO 2 (medium): leverage headline lacks the cost-panel under-coverage caveat when coverage<100% (priced-only numerator silently understates). TEST GAP: every not-run test uses an UNCONFIGURED fee; the cost_state=NOT_RUN + configured fee + derivable window combo is never assembled; test_empty_db_renders_every_panel_in_absence passes for the wrong reason (no fee). Add a regression test that fails today. CLEARED: OTel zero-cost path is correctly guarded (cross_check indep<=0 -> absent). Strengths: _fmt_usd uncosted discipline, --since honesty guard, escaping seam.

---

## Turn 3 — ux-evaluator (proposal)
*2026-06-07T08:00:12.139084+00:00 | confidence: 0.91*
*tags: blocking:0, advisory:4, c4-probe*

APPROVE-WITH-CHANGES (0.91). C4 probe: absence tiles UNMISTAKABLE by shape/icon+copy not color alone (dashed border + repeating bg + icon; WCAG 1.4.1 met, grayscale-safe); true-zero (No failure signals detected, data tile) cleanly distinct from not-yet-run (absence tile) - the spec hardest requirement, done right; OTel enable affordance is a live <a> link with plain-language context; A1 pay-per-use legend + A3 List-price-equivalent multiple legend both pass the manager-gatekeeper test; ASCII summary 5-6 lines no jargon. FINDING 1 (MEDIUM, C4): _fmt_int(value or 0) coerces None->0; signature is int|None and a None token count would render a confident 0 (the C4 anti-pattern). _fmt_usd correctly returns uncosted for None; _fmt_int should match (return marker or tighten signature to int since callers always pass int). FINDING 2 (MEDIUM, C4): _render_attribution_block coverage fallback 0.0 when available=True but independent_cost_usd falsy -> renders 0.0% covered as a DATA tile; value.py guarantees available=False on zero denom but the render boundary does not enforce it -> add a render guard (indep falsy -> absence tile). FINDING 3 (LOW): attribution leads with raw dollars before the percentage/context; add a legend sentence like A1/A3. FINDING 4 (LOW): absence icon circle glyph semantics weak (dashed border does the work; optional). No fabricated zero in the rendered fixtures; uncosted shown italic with the not-zero-rated note.

---

## Turn 4 — qa-specialist (proposal)
*2026-06-07T08:00:12.263833+00:00 | confidence: 0.82*
*tags: blocking:0, advisory:5*

APPROVE-WITH-CHANGES (0.82). Honest-absence/escaping/read-side-only/no-persistence tests present + regression-tagged + correctly structured; ?mode=ro driver write-refusal tested directly; true-zero-vs-not-run tested at the classification level; no-slug tested on two paths. FINDING 1 (HIGH, missing test): the A1 cost-panel STATE_NOT_RUN RENDER path (_render_cost_panel not-run branch) has no HTML-level assertion - only assembly-level (cost_state==NOT_RUN) and ASCII. A regression collapsing it to $0.00 would not be caught. Add render test asserting data-state=absent + analyze_cost.py + no $0.00. FINDING 2 (MEDIUM, weak assertion): fidelity test omits pricing_check.divergence_pct and .direction (spec R5a names them); add both. FINDING 3 (MEDIUM, missing escaping): LeverageResult.reason/.note and tier-name keys + FailureSignal.tier have no injection test (the code itself flags note with a security comment). Add. FINDING 4 (LOW): non-OTel generic-absent branch of _render_pricing_block untested. FINDING 5 (LOW): fidelity reference uses analyze_value which calls init_db (write side-effect asymmetry); switch reference to assemble_value_inputs on the ro conn. Strengths: regression-ledger pre-committed naming the tests; driver-level ro test; not-call + not-hasattr write-side assertion; cp1252 parametrized.

---

## Turn 5 — security-specialist (proposal)
*2026-06-07T08:00:12.381814+00:00 | confidence: 0.94*
*tags: blocking:0, advisory:2*

APPROVE-WITH-CHANGES (0.94). Escaping seam _esc=html.escape(str,quote=True) applied at every HTML emission for every transcript-shaped field (signature/detail/failure_type/tier, divergence reason/source_label, fee labels, generated_label); injection vector tool-name->FailureSignal.signature correctly escaped (input_hash is hex, inert). Read-only ?mode=ro enforced at driver level + regression-tested; no init_db/DDL/INSERT in dashboard path; _watermark_present parameterized. No slug/env/secret reaches HTML/stdout/stderr on any path incl errors (DB_PATH constant + sqlite msg only; imports no notify, reads no env) - tested behaviorally on 2 paths. OTel file path symlink-safe within DATA_DIR, size-capped, source_label hardcoded not file-derived. FINDING 1 (LOW): _esc_reason docstring says escaped upstream but escape is DOWNSTREAM in _absence_tile via _esc(why); maintenance trap - fix docstring or rename _normalize_reason. FINDING 2 (INFO): _query_exists is dead code (zero call sites) with a raw sql:str param; delete it or constrain. No blocking security defect; escaping correct + complete as shipped.

---

## Turn 6 — architecture-consultant (proposal)
*2026-06-07T08:00:12.497049+00:00 | confidence: 0.92*
*tags: blocking:0, advisory:2*

APPROVE (0.92). Dependency direction clean: scripts->src only, src NEVER imports scripts (the most important boundary, verified). scripts/src split placed correctly + consistent with A1/A2/A3 (IO/orchestration in scripts/telemetry; pure format/measure in src/telemetry); assemble_dashboard_data belongs in scripts because it does DB+transcript IO. Single-path A3 GENUINE not nominal: assemble_value_inputs is the one read-only assembler, analyze_value delegates after init_db, dashboard calls it directly with a1_report passthrough (single source of truth, no fork); --since honesty guard preserved inside the shared fn; fidelity test asserts field-for-field equality. R7 honored: no math leaked into the transport script (the attribution coverage% is presentation-local, mirrors the A3 CLI, not a re-derived stored figure). Compute-don-t-store honored (no table, schema+rowcounts snapshot). ADR-0020 Layer B note accurate vs implementation; the layering self-correction is exemplary ADR hygiene. A-INFO1: A-ARCH1 (itu._ private helpers) is contained for the dashboard path (reduced, reached transitively) but the underlying 4-consumer condition remains live across A1/A2/A3 - carry as the named A-ARCH1 advisory, promote in one change when taken up. A-LOW1: STATE_DATA import is correctly used (3 sites), optional comment. No pre-commit action.

---

## Turn 7 — facilitator (critique)
*2026-06-07T08:00:39.448906+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 13 findings across 5 specialists. VERIFIED TRUE: independent FINDING 1 (fabricated 0.00x leverage when fee configured + cost not run) - confirmed at value.py:279 (0.0 is finite, fee set -> configured=True) + dashboard.py:285-296 (renders 0.00x/mo data subtile) + console line; this is a genuine C4 honest-absence hole, BLOCKING. security FINDING 2 (_query_exists dead code) - confirmed zero source call sites. qa FINDINGS 1-5 (test gaps) - verified real (cost-not-run render path, fidelity pricing fields, leverage reason/note + tier-key escaping, generic-absent pricing branch, fidelity reference asymmetry). security FINDING 1 (_esc_reason docstring backwards) - verified. ux FINDING 1 (_fmt_int None->0) - verified LATENT: both callers (total_tokens/wasted_total_tokens) return int today, but signature is int|None; tighten. ux FINDING 2 (attribution 0.0% when indep falsy + available True) - verified INCONCLUSIVE/defense-in-depth: value.py cross_check guarantees available=False on zero denom, so unreachable today, but the render boundary does not enforce it. ux F3/F4, arch A-INFO1/A-LOW1 - inconclusive/advisory. 0 discarded. Verdict: approve-with-changes; 1 blocking must be fixed before commit.

---

## Turn 8 — facilitator (synthesis)
*2026-06-07T08:01:00.638528+00:00 | confidence: 0.88*
*tags: blocking:1, advisory:12, speculative:0, model-tiers:qa-sonnet+security-sonnet+ux-sonnet+arch-opus+ip-opus*

## Request Context
- What was requested: /review of the Layer B telemetry dashboard (render-only over A1/A2/A3), with an explicit mandate to probe honest-absence C4 (fabricated-zero risk).
- Files/scope: src/telemetry/dashboard.py, scripts/telemetry/dashboard.py, scripts/telemetry/analyze_value.py, tests/test_telemetry.py + docs/reviews/artifacts/.
- Developer-stated motivation: north-star dashboard for honestly understanding AI use; build = render not measurement.
- Explicit constraints: read-side only; html.escape; honest-absence first-class; plain-language; ASCII console; read-only DB; no slug.

VERDICT: APPROVE-WITH-CHANGES. Panel: independent-perspective 0.86 (request-changes), ux 0.91, qa 0.82, security 0.94, architecture 0.92 (approve). The C4 probe WORKED: independent-perspective caught 1 BLOCKING fabricated-zero the build + both build-checkpoints shared a blind spot on - leverage renders an authoritative 0.00x/mo when a fee is configured but the cost analyzer has not run (absence guard keys on the fee, never on whether the numerator was measured). Must fix before commit by propagating cost-state into leverage absence (render + console). Corroborating C4 defense-in-depth (ux): _fmt_int(None)->0 latent path (tighten to int); attribution 0.0%-covered render guard. Recommended (qa): +cost-not-run render test, fidelity pricing_pct/direction, leverage-reason/note + tier-key escaping tests, generic-absent pricing branch test, switch fidelity reference to assemble_value_inputs. Cheap (security): fix _esc_reason docstring, delete dead _query_exists. Architecture APPROVE (single-path + layering verified). Carry A-ARCH1 as named advisory. Confidence annotation: 0 findings <0.80; all scored. Model tiers: qa-specialist:sonnet, security-specialist:sonnet, ux-evaluator:sonnet, architecture-consultant:opus, independent-perspective:opus.

---
