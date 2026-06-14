---
discussion_id: DISC-20260610-001234-retry-chain-nesting-spec-review
started: 2026-06-10T00:12:46.846053+00:00
ended: 2026-06-10T00:18:44.542519+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 4
---

# Discussion: DISC-20260610-001234-retry-chain-nesting-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-10T00:12:46.846053+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Phase 3 Unit 3 — retry-chain nesting in the A2 Failure & Waste panel. Build per SPEC-20260607-183136 §Phase 3 final bullet (retry-chain nesting). Pure read-time helper group_retry_chains() over existing RankedFailure list; RetryChain dataclass; parent-row + nested child-row table shape; chain-of-length-1 must render identically to today's flat row (no regression).
- **Files/scope**: src/telemetry/failures.py (new helper + dataclass + constant); src/telemetry/dashboard.py (extend _render_failure_class_group to emit parent + link rows for chains length>=2); tests/test_telemetry.py (helper + render); memory/bugs/regression-ledger.md.
- **Developer-stated motivation**: cascade of N retries sharing a single root cause inflates the visual failure count; gatekeeper should read 'one root cause, four reactions' not 'four uncorrelated retry loops.' Completes Phase 3 cohort.
- **Explicit constraints**: TEMPORAL heuristic (NOT ARGUMENT-SHAPE — developer-resolved fork). ADR-0013 compute-don't-store (read-time only; no DB columns; no analyzer transport changes). ADR-0020 honesty (no fabricated chain; missing timestamp = no chain). Named module constant MAX_RETRY_CHAIN_GAP_SECONDS=120. Length-1 chain renders byte-identical to today's row. Within-class only (no cross-class chaining). No push. /review qa+arch+ux >=3. Final Phase 3 unit -> SUPERVISOR_DONE.

---

## Turn 2 — architecture-consultant (critique)
*2026-06-10T00:16:50.898282+00:00 | confidence: 0.88*
*tags: spec-review, architecture*

Verdict: APPROVE-WITH-CHANGES. Confidence 0.88. ADR-0013 + ADR-0020 alignment: full. Boundary placement (group_retry_chains in failures.py, not dashboard.py) correct on first read. R7 (group-then-chain per class) composes cleanly. F1 MED: _render_failure_class_group already ~44 lines; folding parent+link rows inline pushes past ~50-line guideline AND gives it two responsibilities. Recommend separate _render_retry_chain(chain) helper that internally short-circuits length-1 to today's flat-row shape — keeps A8 byte-identical invariant local to one function. F2 LOW: defer _group_by_key extraction; three callers have divergent shapes (sort-key-driven bucket / canonical-order bucket / temporal-window fold) so Rule-of-Three precondition not met; document trigger in regression-ledger entry (close-the-door, not leave-trigger-floating). F3 INFO: docstring should note public group_retry_chains vs private sibling _group_* — cross-module boundary justifies asymmetry. F4 INFO: MAX_RETRY_CHAIN_GAP_SECONDS placement matches DEFAULT_RETRY_THRESHOLD pattern; positive observation, no change. Strengths: out-of-scope section explicitly closes doors; R2/A6 mirrors _sum_optional honest-absence semantics; R4/A8 makes no-visual-regression claim auditable by single test.

---

## Turn 3 — qa-specialist (critique)
*2026-06-10T00:16:51.035864+00:00 | confidence: 0.91*
*tags: spec-review, qa*

Verdict: APPROVE-WITH-CHANGES. Confidence 0.91. F1 HIGH: 'orphan interleaved between two retries' scenario is genuine spec gap — R3 says non-retry signals never participate but doesn't say whether they RESET the chain pointer or are SKIPPED OVER. Add R3 sentence + A13 pinning the chosen behavior (recommend: orphan resets the chain pointer — simplest, safest, and matches the temporal-adjacency intuition). F2 HIGH: 'gap == 120s' boundary untested — spec uses <= in R3 but A2/A3 don't pin the exact == 120 / == 121 edges. Add explicit boundary criterion. F3 HIGH: TypeError from mixed tz-aware/naive datetime subtraction is a runtime crash. _build_retry_signal sources timestamps from analyzer transport (should be tz-aware UTC) but the FailureSignal type allows naive — fail-loud on subtraction failure is acceptable; need an explicit precondition statement OR a catch-and-treat-as-unchainable rule. F4 MED: A8 'byte-identical' is wrong framing — the actual property is structural absence (no data-chain-size attr, no .retry-chain-link rows). Drop byte-identical wording. F5 MED: first_seen==last_seen (zero-duration signal) + 0s gap must explicitly chain; also tie-break determinism. F6 MED: cost_usd==0.0 vs None — pin that 0.0 contributes to sum (priced at zero) vs None excluded. F7 LOW: all-orphan input -> empty list. F8 LOW: determinism probe (sort/shuffle invariance) if tiebreaker added per F5. Strengths: A5 honest-absence; A11 named-constant tunability mirrors DEFAULT_RETRY_THRESHOLD; R7 per-class scope keeps remediation-hint contract intact.

---

## Turn 4 — facilitator (synthesis)
*2026-06-10T00:18:44.542519+00:00 | confidence: 0.92*

## Request Context
- **What was requested**: Phase 3 Unit 3 (retry-chain nesting) spec drafted + reviewed before /build_module per autonomous_workflow rule.
- **Files/scope**: src/telemetry/failures.py (helper + dataclass + constant); src/telemetry/dashboard.py (new _render_retry_chain helper + extension of _render_failure_class_group call shape); tests/test_telemetry.py; memory/bugs/regression-ledger.md.
- **Developer-stated motivation**: cascade of N retries sharing one root cause should read as one chain not N independent rows.
- **Explicit constraints**: TEMPORAL fork resolution; ADR-0013 read-time only; ADR-0020 honesty; named MAX_RETRY_CHAIN_GAP_SECONDS=120; length-1 = today's flat row.

## Synthesis
Both specialists APPROVE-WITH-CHANGES. 0 BLOCKING, 3 HIGH (qa F1/F2/F3) folded into the spec, 4 MED+LOW (qa F4-F8 + arch F1) folded into the spec, 2 INFO+LOW (arch F2/F3/F4) recorded as constraints/docstring notes.

**HIGH folds** (qa):
- F1 (interleaved orphan chain interruption): R3 now states non-retry signals are SKIPPED OVER, not chain-reset. Reasoning: per R7 chaining is within-class; today orphans go to ORPHAN class and retries to NOT_FOUND/VALIDATION/OTHER so the scenario is observationally a no-op, but skip-over preserves the 'one root cause, N reactions' semantic for future heterogeneous classes. Added A4b acceptance criterion.
- F2 (== 120s boundary): R3 now explicitly says boundary is inclusive (gap <= window chains). A2 rewritten to pin '< window' AND '== window' cases; A3 pins '== window + 1'.
- F3 (tz-aware/naive datetime crash): added C8 — TypeError on subtraction caught and treated identically to missing timestamp. Added A5b acceptance criterion. Defensive belt-and-braces; canonical analyzer transport emits tz-aware UTC.

**MED/LOW folds**:
- arch F1: spec R5 now mandates a separate _render_retry_chain helper (single seam for length-1 short-circuit AND length-≥2 shape) — keeps _render_failure_class_group under the ~50-line guideline.
- qa F4: A8 reframed from 'byte-identical' to structural-absence assertions (no data-chain-size attr, no .retry-chain-link rows, no aria-label on length-1 parent).
- qa F5: A7b added (zero-duration signals + 0s gap chain).
- qa F6: A6b added (cost_usd == 0.0 contributes to sum; guards against future truthy-guard regression).
- qa F7: A11b added (all-orphan input → []).
- qa F8: A10b added (determinism probe).
- arch F2: C9 — explicit DECLINE of _group_by_key Rule-of-Three extraction (three callers' shapes too divergent); document the decline in the regression-ledger entry to close the trigger rather than leave it floating.

**INFO recorded for build**:
- arch F3: group_retry_chains docstring will explain public-vs-private asymmetry (cross-module boundary).
- arch F4: MAX_RETRY_CHAIN_GAP_SECONDS placement matches DEFAULT_RETRY_THRESHOLD — no change needed, just positive observation.

Spec status: reviewed. Confidence to proceed to build: ~0.95. Acceptance criteria now 12 main + 7 sub-cases (A2-A11 expanded with 'b' variants for the folded edges). All assertions are direct test pinnings; no hand-waving.

---
