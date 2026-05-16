---
project_name: "[Your Project Name]"
source: "local"
analyzed: "[YYYY-MM-DD]"
tags: []
---

## Overview

[Describe your project here. This is the self-profile — it documents YOUR project's solution paths so future builds can reference them.]

## Solution Paths

<!-- Add solution paths as you build. Each entry documents HOW you solved a problem,
     what you tried first, and why you chose your approach. This knowledge prevents
     re-inventing solutions and helps future contributors understand the journey. -->

<!-- Format:
### [domain/sub-concept] — Short title

**Problem**: What needed solving
**Tried**: What approaches were attempted (including failures)
**Chosen**: What approach was ultimately used and why
**Evidence**: Where in the codebase this can be seen
**Tags**: [domain/sub-concept]
-->

### [framework/promotion-pipeline] — Repair the Layer 1 → Layer 3 seam without back-filling fictional schema

**Problem**: The framework's central claim ("reasoning is the primary artifact") was operationally false at the closure → candidacy seam. `close_discussion.py` invoked `surface_candidates(discussion_id=...)` against a function whose signature was `def surface_candidates(threshold=3)`, and imported `compute_effectiveness` from a module whose actual exported name was `compute_agent_effectiveness`. Both errors were swallowed by broad `except Exception` blocks and surfaced only as non-fatal warnings. Parent SQLite accumulated 109 pattern_sightings → 0 promotion_candidates over ~5 weeks. Spec/discussion architectures depended on this seam working.

**Tried**:
- *Considered C4-b (extend the schema to back what `/promote.md` and `enforce_forgetting_curve.py` queried).* Rejected. The drifted queries referenced ten columns (`candidate_id, candidate_type, title, evidence_count, target_path, status, reviewed_at, last_referenced_at, human_verdict, source_file`) whose semantics were never defined by a real caller. Canonizing them would have given fictional columns a future, not a past.
- *Considered calling `surface_candidates()` with no args* (preserving exact original semantics). Rejected — close_discussion's call site already passed `discussion_id=discussion_id`, signalling clear design intent toward per-discussion scoping. "Fix by removing the kwarg" would have been a regression in design intent and would have made every closure perform a full project-wide scan.
- *Considered narrowing both Rule-of-Three counting AND emission to the closing discussion's sightings.* Rejected — this would have inverted the Rule of Three (which is fundamentally cross-discussion) into a local-only count.

**Chosen**: Extend `surface_candidates(threshold=3, discussion_id: str | None = None)` such that, when `discussion_id` is set, Rule-of-Three counting still uses the full `pattern_sightings` table but emission/update is filtered to rows whose `pattern_hash` has a sighting in the closing discussion. Manual `--all` path is character-for-character unchanged. Fix the import name `compute_effectiveness → compute_agent_effectiveness` (the function already accepted `discussion_id`). Reconcile `/promote.md` and `enforce_forgetting_curve.py` to the canonical schema; the latter's SQLite path was deleted (it had always failed silently) — mtime is the real implementation.

The regression test is a structural canary, not just a fix verifier: tests/test_close_discussion_promotion_pipeline.py contains two source-inspection canaries (one per defect) plus INSERT and UPDATE branch coverage. Defect 2's canary reads close_discussion.py and asserts the imported name actually exists in compute_agent_effectiveness.py — a pure import-symbol-exists test would not catch close_discussion.py being reverted to the wrong name.

**Evidence**:
- `scripts/surface_candidates.py:20-94` (signature + dual SELECT branches; the comment at lines 51-53 names the counting-vs-emission invariant)
- `scripts/close_discussion.py:144,150-153` (corrected call sites)
- `.claude/commands/promote.md` (schema-reconciled SELECT and UPDATE)
- `scripts/enforce_forgetting_curve.py` (deleted phantom SQLite path)
- `tests/test_close_discussion_promotion_pipeline.py` (canaries + branch coverage)
- `memory/bugs/regression-ledger.md` (canary contract: "Do not remove or weaken without an ADR addressing the swallowed-exception pattern")
- `docs/sprints/SPEC-20260515-053533-phase0-promotion-pipeline-fix.md` (spec with C4-a/C4-b deliberation)
- `discussions/2026-05-15/DISC-20260515-053700-phase0-promotion-pipeline-fix-spec-review/` (sealed spec review)
- `docs/adr/ADR-0013-token-efficiency-telemetry.md:122` (where the defects were first noted, then deferred)

**Tags**: [framework/promotion-pipeline]
