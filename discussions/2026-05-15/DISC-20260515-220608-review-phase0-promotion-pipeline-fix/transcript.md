---
discussion_id: DISC-20260515-220608-review-phase0-promotion-pipeline-fix
started: 2026-05-15T22:06:48.614341+00:00
ended: 2026-05-15T22:13:30.648392+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 6
---

# Discussion: DISC-20260515-220608-review-phase0-promotion-pipeline-fix

## Turn 1 — facilitator (evidence)
*2026-05-15T22:06:48.614341+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Multi-agent code review of the Phase 0 promotion-pipeline fix just built via /build_module (SPEC-20260515-053533). Sequence per autonomous_workflow.md: /plan → /build_module → quality_gate → /review → commit. Quality gate already 7/7. Ready for /review.
- **Files/scope**: The Phase 0 changes in the working tree: scripts/surface_candidates.py (signature extension + scoped SELECT), scripts/close_discussion.py (import-name fix), scripts/enforce_forgetting_curve.py (phantom SQLite path removed), .claude/commands/promote.md (schema-reconciled queries), tests/test_close_discussion_promotion_pipeline.py (new, 6 regression tests), tests/test_enforce_forgetting_curve.py (4 phantom-schema tests removed, db_path kwarg dropped), memory/bugs/regression-ledger.md (entry + canary contract), memory/projects/_self.md (Solution Path [framework/promotion-pipeline]). Plus BUILD_STATUS.md, docs/sprints/SPEC-... (status complete). Auto-scope detected the full pr-diff (67 files spanning Phase 4 + token telemetry + Phase 0); narrowed because those prior phases already reviewed at REV-20260512-* and REV-20260513-*.
- **Developer-stated motivation**: Phase 0 of framework memory evolution. Phase 1 (substrate wiring) is gated on Phase 0 landing. The framework's central claim ('reasoning is the primary artifact') was operationally broken at the Layer 1 → Layer 3 seam for ~5 weeks; this fix restores it. Both defects verified to fail without the fix and pass after (canary protocol).
- **Explicit constraints**: Risk tier low per spec author. Mandatory specialists qa-specialist + architecture-consultant; no security/performance specialist unless review surfaces a reason. Per-discussion scoping in surface_candidates is additive (Rule-of-Three counting stays global; emission filtered to closing-discussion patterns). C4-a chosen over C4-b (no fictional schema growth). Regression-ledger entry includes canary contract sentence. Solution Path tagged [framework/promotion-pipeline].

---

## Turn 2 — qa-specialist (critique)
*2026-05-15T22:10:35.768104+00:00 | confidence: 0.91*
*tags: verdict:approve-with-changes, blocking:0, medium:1, advisory:2*

## QA Verdict: APPROVE-WITH-CHANGES (confidence 0.91)

### Finding 1 (MEDIUM) — Canary 2 regex captures only first imported name
**Location**: tests/test_close_discussion_promotion_pipeline.py:155
**Rule**: REVIEW.md #13 (success path + edge case coverage)
test_canary_compute_agent_effectiveness_import_name uses  — single-capture-group regex. If close_discussion.py is refactored to  (multi-name single-line), match.group(1) captures only the first name. If the correct name is the second, canary passes while defect is live.
**Recommendation**: Change regex to  and assert  rather than asserting captured token equals function name. One-liner.

### Finding 2 (LOW / ADVISORY) — Missing lower-boundary test
**Location**: tests/test_close_discussion_promotion_pipeline.py:201
INSERT branch tests all seed exactly 3 discussions (>= threshold). No explicit 'threshold=3 with 2 sightings → nothing surfaces' test to verify the HAVING COUNT boundary from below.
**Recommendation**: Add a short test seeding 2 discussions with a shared pattern, call surface_candidates(threshold=3, discussion_id=disc2_id), assert new_count == 0.

### Finding 3 (LOW / ADVISORY) — Root cause taxonomy classification
**Location**: memory/bugs/regression-ledger.md:30
Both defects classified as Schema/Serialization Drift. Defect 1 (wrong function signature) is closer to Abstraction Narrowing; Defect 2 (wrong import name) is closer to Intent Routing Gap. Schema/Serialization Drift fits 'JSON field renamed without migration', which is not exactly what happened. Non-blocking; taxonomy reclassification can be a follow-up.

### Strengths
- Isolation strategy correct: DB_PATH is module-level attribute resolved at call time at scripts/surface_candidates.py:18 and scripts/compute_agent_effectiveness.py:17. monkeypatch.setattr works immediately.
- Canary 1 exercises exact call pattern from close_discussion.py:144 — no indirection.
- Canary 2's source-inspection strategy is correct (catches caller-side rename desync, which a pure import test would not).
- Removed 4 enforce_forgetting_curve tests correctly classified as phantom — tested fictional schema that was never canonical.
- UPDATE branch test verifies row identity via id column (assert candidate_id_after == candidate_id_before).
- Canary contract sentence is present in regression-ledger entry.
- /promote.md Step 4 UPDATE uses canonical column names.

---

## Turn 3 — architecture-consultant (critique)
*2026-05-15T22:10:51.862323+00:00 | confidence: 0.88*
*tags: verdict:approve, blocking:0, info:5*

## Architecture Verdict: APPROVE (confidence 0.88)

This fix correctly restores boundary integrity at the Layer 1 → Layer 2 → Layer 3 seam. C4-a is well-actualized (no fictional schema growth). Signature extension cleanly scoped with the right invariant (counting global, emission scoped). Canary contract is honest about what it guards. No blocking findings.

### Architectural Alignment
- No ADR required — defect repair against canonical schema at scripts/init_db.py:124-135. C4-a was a choice between two repair paths, not a new architectural direction.
- Principle #4 (independence): the swallow-and-warn pattern bypassed independent evaluation at runtime; canary tests structurally restore it.
- Boundary integrity preserved across the four-layer capture stack. No cross-layer leak.

### Finding 1 (LOW / INFO) — Invariant phrasing drifts between docstring and inline comment
**Location**: scripts/surface_candidates.py:21-42 (docstring) vs :51-53 (inline)
Docstring says 'Rule-of-Three counting still uses the global pattern_sightings table'; inline says 'Rule-of-Three counting always uses the full table'. Same invariant, slightly drifted phrasing. Align wording or combine into one source of truth.

### Finding 2 (LOW / INFO) — No display path for already-promoted candidates
**Location**: .claude/commands/promote.md:55-67
Queue shows pending candidates; no equivalent 'what's been promoted recently' view. Cognitive load for maintainers. Out of scope for Phase 0; future affordance.

### Finding 3 (INFO) — Canary enforceability partial
**Location**: memory/bugs/regression-ledger.md:30 + tests/test_close_discussion_promotion_pipeline.py:17-18
Canary contract: 'Do not remove or weaken without ADR'. Deletion IS structurally blocked (quality_gate.py's regression ledger check verifies test file exists). Weakening is NOT structurally enforced. Future improvement: content-hash assertion or CODEOWNERS-style required-reviewer rule. Worth capturing as architectural debt note.

### Finding 4 (INFO) — Unused DB_PATH import in enforce_forgetting_curve.py
**Location**: scripts/enforce_forgetting_curve.py:27
After deleting SQLite path, DB_PATH = PROJECT_ROOT / 'metrics' / 'evaluation.db' is unused. Dead code. Two small cleanups: remove unused DB_PATH; module docstring already explains historical context. Not blocking.

### Finding 5 (INFO) — Swallow-and-warn retention architecturally correct for Phase 0
**Location**: scripts/close_discussion.py:118, 127, 136, 145, 154, 171, 193
Retention is correct for Phase 0: closure must not be blocked by downstream pipeline failures. Canary tests now make the SPECIFIC failure modes (signature drift, import-name drift) detectable. The general problem (new unrelated defect inside one of these try blocks remains hidden) is real and acknowledged. Future ADR on swallow-and-warn pattern could distinguish 'non-fatal but must surface in metrics' from 'truly non-fatal'. Out of scope here.

### Strengths
- C4-a decision well-actualized. Phantom path deletion is door-closing, not door-opening.
- Signature extension minimal and load-bearing; preserves --all CLI path (test_insert_branch_manual_all_path_unchanged confirms).
- Canary 2's source-inspection catches the specific drift class (caller-side rename desync) — exactly the right canary shape.
- Regression-ledger entry detailed: defects, 5-week silent duration, 109/0 evidence, canary contract.
- Schema reconciliation in /promote.md references scripts/init_db.py:124 — consistent cross-file pointing-at-canonical-schema discipline.
- No cross-layer leak introduced.

---

## Turn 4 — qa-specialist (evidence)
*2026-05-15T22:11:20.746995+00:00 | confidence: 0.8*
*replying to turn 2*
*tags: addendum, finding-1-regex*

## QA Finding 1 — Technical addendum (lost in prior turn due to bash backtick stripping)

The Defect 2 canary regex is currently this (single-capture-group):
    re.search(r"from\s+compute_agent_effectiveness\s+import\s+(\w+)", cd_source)

The qa-specialist's proposed fix is:
    re.search(r"from\s+compute_agent_effectiveness\s+import\s+([\w,\s]+)", cd_source)
    # Then assert 'compute_agent_effectiveness' in match.group(1)

Reasoning: \w+ matches a single word token. If close_discussion.py imports multiple names
on a single line — e.g. `from compute_agent_effectiveness import compute_agent_effectiveness, helper` —
the current regex captures only the first token. If a future refactor reordered them or aliased,
the canary could pass while the defect is live.

The fix uses [\w,\s]+ to capture a comma-separated group, then asserts membership of the
target name in the captured string.

---

## Turn 5 — facilitator (critique)
*2026-05-15T22:12:09.348889+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification pass: 7 verified, 1 inconclusive, 0 discarded.

Verified:
- qa-F1 (Medium): regex at tests/test_close_discussion_promotion_pipeline.py:155 confirmed as single-capture-group (\w+). Multi-name single-line refactor would defeat it. Fix valid.
- qa-F2 (Low): no 2-sightings/threshold-3 lower-boundary test in the file. Coverage gap confirmed.
- arch-F1 (Low): surface_candidates.py docstring (lines 27-32) vs inline (lines 51-53) — phrasing drift confirmed; both correct but slightly different word choices.
- arch-F2 (Low): /promote.md has no already-promoted display path. Confirmed.
- arch-F3 (Info): quality_gate.py _parse_regression_ledger checks file existence but not content; deletion blocked structurally, weakening not.
- arch-F4 (Info): enforce_forgetting_curve.py:27 DB_PATH constant present but unused after SQLite-path deletion. Dead-code confirmed.
- arch-F5 (Info): swallow-and-warn retention intentional per spec C5. Confirmed.

Inconclusive (retained per conservative posture):
- qa-F3 (Low): root cause taxonomy classification. Defect 1 as Schema/Serialization Drift vs Abstraction Narrowing — judgment-dependent; both arguably fit. No mechanical resolution available.

---

## Turn 6 — facilitator (synthesis)
*2026-05-15T22:13:30.648392+00:00 | confidence: 0.9*
*tags: verdict:approve-with-changes, blocking:1, advisory:6, speculative:0, model-tiers:qa-specialist:sonnet, architecture-consultant:opus, facilitator:opus*

## Request Context
- **What was requested**: Multi-agent code review of the Phase 0 promotion-pipeline fix just built via /build_module (SPEC-20260515-053533). Sequence per autonomous_workflow.md: /plan → /build_module → quality_gate → /review → commit. Quality gate already 7/7.
- **Files/scope**: 8 files: scripts/surface_candidates.py, scripts/close_discussion.py, scripts/enforce_forgetting_curve.py, .claude/commands/promote.md, tests/test_close_discussion_promotion_pipeline.py (new), tests/test_enforce_forgetting_curve.py (rewritten), memory/bugs/regression-ledger.md, memory/projects/_self.md.
- **Developer-stated motivation**: Phase 0 of framework memory evolution; Phase 1 gated on Phase 0 landing; restores 'reasoning is the primary artifact' end-to-end after ~5-week silent break.
- **Explicit constraints**: Risk tier low. qa-specialist + architecture-consultant mandatory; no security/performance unless review surfaces a reason (it did not). C4-a chosen. Per-discussion scoping additive.

## Synthesis

Verdict: APPROVE-WITH-CHANGES (confidence 0.90, weighted average of qa 0.91 / arch 0.88).

Specialist verdicts:
- qa-specialist: APPROVE-WITH-CHANGES (1 medium, 2 low)
- architecture-consultant: APPROVE (5 info-level)

Blocking findings: 1 (qa-F1, one-line regex fix on the Defect 2 canary).
Advisory findings: 6 (3 trivial cleanups + 3 future-phase debt notes).
Speculative findings (<0.80 confidence): 0.

Finding verification pass: 7 verified, 1 inconclusive (qa-F3 root cause taxonomy — judgment-dependent, retained), 0 discarded.

The one required change is qa-F1: tests/test_close_discussion_promotion_pipeline.py:155 uses a single-capture-group regex (\w+) to extract the imported name from close_discussion.py. A multi-name single-line import would defeat the canary. One-line fix to capture [\w,\s]+ and assert membership. Cost: trivial.

Advisory cleanups (zero-risk): arch-F4 (remove unused DB_PATH at enforce_forgetting_curve.py:27); arch-F1 (align invariant phrasing in surface_candidates.py). Worth doing inline before commit.

Architectural debt for Phase 1+: arch-F2 (/promote --list-promoted affordance); arch-F3 (canary content-hash enforcement); arch-F5 (general swallow-and-warn telemetry path).

Model tiers: qa-specialist:sonnet, architecture-consultant:opus, facilitator:opus. No cost flag provided; default tiers used.

Education gate: recommended despite Low risk tier — the structural-canary pattern, swallow-and-warn boundary semantics, and C4-a vs C4-b decision are non-obvious framework concepts worth verifying. Tier 1 mastery.

Next: apply qa-F1, optionally arch-F4 + arch-F1, then commit. Report at docs/reviews/REV-20260515-221223.md.

---
