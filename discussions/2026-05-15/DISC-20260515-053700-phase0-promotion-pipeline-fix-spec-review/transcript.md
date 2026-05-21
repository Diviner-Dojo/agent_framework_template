---
discussion_id: DISC-20260515-053700-phase0-promotion-pipeline-fix-spec-review
started: 2026-05-15T05:37:12.167274+00:00
ended: 2026-05-15T05:41:28.441399+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 4
---

# Discussion: DISC-20260515-053700-phase0-promotion-pipeline-fix-spec-review

## Turn 1 — facilitator (evidence)
*2026-05-15T05:37:12.167274+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Fix the framework's promotion pipeline API drift so reasoning can actually accumulate into Layer 3 memory. Phase 0 of the framework memory evolution plan (docs/plans/framework-memory-evolution-2026-05.md). Two pipeline calls in scripts/close_discussion.py invoke functions with the wrong signatures; resulting TypeErrors are swallowed as non-fatal warnings and the pipeline silently fails to populate promotion_candidates.
- **Files/scope**: scripts/close_discussion.py (lines 141-146 and 149-155), scripts/surface_candidates.py (extend signature with optional discussion_id), confirm scripts/compute_agent_effectiveness.py needs only an import-name fix at the caller. New regression test under tests/. Entries in memory/bugs/regression-ledger.md and memory/projects/_self.md. Collateral defect surfaced in /promote.md schema drift may or may not be in scope (specialists decide).
- **Developer-stated motivation**: The framework's central claim — 'reasoning is the primary artifact' — is currently broken at the seam between captured discussions and curated memory. Parent SQLite shows 109 pattern_sightings and 0 promotion_candidates as a result. Phase 1 (substrate wiring) is gated on Phase 0 landing.
- **Explicit constraints**: Risk tier low; mandatory specialists qa-specialist and architecture-consultant; no security or performance specialist unless review surfaces a reason. Do not bulk-promote the existing 109 pattern_sightings (only validate end-to-end flow for one pattern). Do not touch assertion_store or mcp_server. Do not add compliance instrumentation. Follow autonomous_workflow.md sequencing and update BUILD_STATUS.md before compaction.

---

## Turn 2 — qa-specialist (critique)
*2026-05-15T05:39:51.860023+00:00 | confidence: 0.82*
*tags: spec-review, blocking-findings, update-branch, stdout-brittleness*

## QA Verdict: REQUEST_CHANGES (confidence 0.82)

The spec is structurally sound and the root cause analysis is correct, but two issues should be resolved before implementation begins.

### Finding 1 (HIGH / BLOCKING) — UPDATE branch of surface_candidates.py:67-93 untested
The proposed regression test covers only the INSERT branch (new candidate row). The UPDATE branch — when a matching candidate already exists and gets refreshed — is a distinct code path inside the same patched function with no test prescribed. If a future refactor regresses the UPDATE branch, no test will catch it.
Recommendation: Add a second small test seeding an existing promotion_candidates row before running the pipeline, then assert that sighting_count / last_seen / evidence_ids advance as expected. (Note: qa-specialist's response referenced 'recurrence_count / status' columns which do not exist — actual UPDATE columns per surface_candidates.py:75-78 are sighting_count, last_seen, evidence_ids. Finding's spirit holds; spec edit uses correct column names.)

### Finding 2 (MEDIUM / BLOCKING) — Brittle stdout-no-warnings acceptance criterion
The spec flags but does not resolve the 'no warnings printed during the pipeline run' criterion. A stdout/stderr capture check breaks on any logging or formatting change.
Recommendation: Drop the stdout check. Replace with a direct row-count assertion: SELECT COUNT(*) FROM promotion_candidates > 0 after the pipeline run. The presence of the row is what the fix is meant to produce; the absence of the swallowed warning is incidental.

### Finding 3 (MEDIUM / ADVISORY) — Regression test must demonstrably fail without the fix
The spec mentions 'fail before, pass after' but does not prescribe how the reviewer verifies this property. Without it, a green test that proves nothing is still allowed.
Recommendation: Add an in-test comment naming the pre-fix wrong signature (e.g., 'Regression: close_discussion called surface_candidates(discussion_id=...) against signature def surface_candidates(threshold=3)') as a traceability link.

### Finding 4 (LOW / ADVISORY) — Verify DB_PATH binding pattern before adopting monkeypatch
The spec references tests/test_close_discussion_rollup.py as the isolation model. If surface_candidates / mine_patterns / compute_agent_effectiveness bind DB_PATH to a local at import time rather than resolving via module attribute, monkeypatching arrives too late.
Recommendation: Confirm during implementation by reading the module bodies. All three currently resolve DB_PATH at call time via module attribute, so the pattern works — but make the verification explicit, not assumed.

### Finding 5 (LOW / ADVISORY) — C4-a inclusion needs either a test or explicit scope-out for /promote.md
C4-a (patch /promote.md schema queries) is in scope but no test is prescribed for it. Either add a minimal schema-match check, or explicitly mark the /promote write as a manual smoke run with no automated coverage.

### Strengths
- R-3 fixture-realism analysis (Jaccard 0.4 + Rule-of-Three) is exactly right
- C1 scope boundary on no backfill is correct and conservative
- Decision lineage to ADR-0013, SPEC-20260405 R5.4, and the worktree diagnostic is preserved
- @pytest.mark.regression marker and ledger entry are correctly required

---

## Turn 3 — architecture-consultant (critique)
*2026-05-15T05:40:08.476079+00:00 | confidence: 0.86*
*tags: spec-review, approve-with-advisories, c4-a-correct, no-adr-required, canary-contract*

## Architecture Verdict: APPROVE with two advisory changes (confidence 0.86)

The spec is a defect repair, not an architectural change. It restores documented behavior from CLAUDE.md's Capture Pipeline section and aligns with the deferred-item note in ADR-0013. Boundaries of the four-layer capture stack are intact. The fix lives entirely within scripts/ and the orchestration of Layer 1 -> Layer 2 ingest. No cross-layer leak. Dependency direction is correct.

### Finding 1 (INFO) — R-1 per-discussion scoping mitigation is the right boundary
The 'no args' path (just call surface_candidates() without arguments) is simpler but every closure would do a full project-wide scan. More importantly, the broken close_discussion site already passes discussion_id=discussion_id — the existing code's intent was clearly per-discussion scoping. 'Fix by removing the kwarg' would be a regression in design intent.
Recommendation: Adopt the R-1 mitigation as written. discussion_id is additive and optional; Rule-of-Three count uses global pattern_sightings; emission/update is filtered to rows whose pattern_hash has a sighting in the closing discussion. Manual --all behavior unchanged.

### Finding 2 (INFO) — C4-a is correct; C4-b would canonize fictional columns
init_db.py defines the schema; the queries in /promote.md and enforce_forgetting_curve.py drifted from it (likely written before schema was finalized, never executed because upstream was broken). C4-b would extend the schema to match broken queries, canonizing fictional columns (status, reviewed_at, human_verdict, source_file, last_referenced_at) whose semantics are unclear and whose value is unproven.
Recommendation: C4-a as drafted. Also patch enforce_forgetting_curve.py — leaving phantom-column queries there is a known bomb. If a future need emerges for richer candidate state (e.g., distinct 'declined' vs 'deferred'), that becomes a future ADR with concrete callers.

### Finding 3 (INFO) — No ADR required for this spec
Signature extension is a one-line additive kwarg. C4-a is a correction not a decision. 'Fix silently-swallowed pipeline failures' as a pattern-level ADR is appealing but premature — one instance documented; a second similar incident in Phase 1 would justify an ADR like 'Pipeline boundaries that swallow exceptions require regression canaries.'

### Finding 4 (LOW / ADVISORY — spec-text only) — Name the canary contract explicitly
The spec correctly preserves the swallow-and-warn pattern (sealing must not abort) and identifies the regression test as the structural canary. But that contract is implicit. If someone later moves/rewrites the test without understanding its role, the canary dies without notice.
Recommendation: In the regression-ledger entry guidance (R6), explicitly state: 'This test is the structural canary for the swallow-and-warn pattern at close_discussion.py:140-155. Do not remove or weaken without an ADR addressing the swallowed-exception pattern.' One sentence, costs nothing, makes the door visible.

### Finding 5 (INFO) — Scope boundaries are correctly drawn
C1-C5 reviewed against 'should anything be pulled in or deferred?' Verdict: ship as scoped. C4-a inclusion is correct because deferring it to Phase 0.5 would leave /promote non-functional after this lands and create a confusing partial-fix state.

### Strengths
- Decision lineage to ADR-0013, SPEC-20260405, worktree diagnostic preserved
- R-1 mitigation correctly distinguishes 'Rule-of-Three counting uses global state; emission is per-discussion'
- R-3 fixture realism catches the failure mode that would have produced a passing-but-meaningless regression test
- Acceptance criteria correctly distinguish automated (regression test) from manual smoke (/promote write) — appropriate since /promote requires developer approval by design

---

## Turn 4 — facilitator (synthesis)
*2026-05-15T05:41:28.441399+00:00 | confidence: 0.85*

## Request Context
- **What was requested**: Fix the framework's promotion pipeline API drift so reasoning can actually accumulate into Layer 3 memory. Phase 0 of the framework memory evolution plan. Two pipeline calls in scripts/close_discussion.py invoke functions with the wrong signatures; resulting TypeErrors are swallowed as non-fatal warnings and the pipeline silently fails to populate promotion_candidates (109 sightings, 0 candidates).
- **Files/scope**: scripts/close_discussion.py, scripts/surface_candidates.py, confirm scripts/compute_agent_effectiveness.py only needs caller-side import-name fix. New regression test, Solution Path entry, regression-ledger entry. Collateral /promote.md schema drift may or may not be in scope (specialists decided).
- **Developer-stated motivation**: Framework's central claim ('reasoning is the primary artifact') broken at Layer 1 -> Layer 3 seam. Phase 1 (substrate wiring) is gated on Phase 0 landing.
- **Explicit constraints**: Risk tier low. No bulk backfill of historical 109 sightings. No substrate touches. No new compliance instrumentation.

## Synthesis

### Specialist verdicts
- **qa-specialist**: REQUEST_CHANGES (confidence 0.82). Two blocking findings (UPDATE branch coverage missing; brittle stdout assertion), three advisory.
- **architecture-consultant**: APPROVE with two advisories (confidence 0.86). Confirmed R-1 mitigation is the right boundary, confirmed C4-a is the correct collateral fix path, confirmed no ADR is needed, asked for an explicit canary-contract sentence in the regression-ledger entry.

### Blocking findings — both resolved in revised spec
1. **qa-F1 (HIGH, blocking) — UPDATE branch coverage**: Spec's regression test originally covered only the INSERT branch of surface_candidates.py:67-93. Added explicit R4.a (INSERT) and R4.b (UPDATE) sub-requirements; UPDATE-branch test seeds an existing promotion_candidates row and asserts sighting_count / last_seen / evidence_ids advance. Caveat: qa-specialist's recommendation referenced phantom columns ('recurrence_count', 'status') from the same schema-drift that produced Defect 3 — corrected to use the real schema columns (sighting_count, last_seen, evidence_ids) per surface_candidates.py:75-78.
2. **qa-F2 (MEDIUM, blocking) — Brittle stdout-no-warnings criterion**: Replaced. Acceptance now asserts SELECT COUNT(*) FROM promotion_candidates > 0 after the pipeline run. Stdout check dropped — the presence of the row is what the fix produces; absence of swallowed warning is incidental.

### Advisories adopted
- **qa-F3** — Regression test must demonstrably fail without the fix. Added 'in-code comment referencing pre-fix signature' to R4. Added a verification protocol acceptance criterion (during implementation, temporarily revert, observe failure, re-apply).
- **qa-F4** — DB_PATH binding pattern verification. Added implementation note to R-2 directing the test author to confirm module-attribute resolution before assuming the monkeypatch pattern works.
- **qa-F5** — C4-a /promote test or scope-out. Explicitly marked /promote write as a manual smoke run (no automated test); rationale captured (interactive slash command requiring developer approval).
- **arch-F4** — Canary contract sentence. Added to R6: regression-ledger entry must include 'This test is the structural canary for the swallow-and-warn pattern at close_discussion.py:140-155. Do not remove or weaken without an ADR addressing the swallowed-exception pattern.'

### Scope decisions confirmed
- **C4-a adopted** (per arch-F2): patch /promote.md and enforce_forgetting_curve.py to query the real schema. C4-b (extend schema) rejected as canonizing fictional columns whose value is unproven by zero callers.
- **No ADR required** (per arch-F3): defect repair, not architectural decision. 'Fix silently-swallowed pipeline failures' as a pattern-level ADR is appealing but premature — a second similar incident in Phase 1 would justify it.
- **Per-discussion scoping is additive** (per arch-F1): discussion_id kwarg is optional; Rule-of-Three counting still uses global pattern_sightings; emission/update is filtered to rows whose pattern_hash has a sighting in the closing discussion. Manual --all CLI behaviour preserved.

### Spec status: draft -> reviewed
Frontmatter updated: status=reviewed, discussion_id=DISC-20260515-053700, reviewed_by=[qa-specialist, architecture-consultant]. Ready for developer approval. Once approved, /build_module against this spec.

---
