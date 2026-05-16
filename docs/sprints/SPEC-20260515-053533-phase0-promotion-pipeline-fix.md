---
spec_id: SPEC-20260515-053533
title: "Phase 0 — Fix promotion pipeline API drift (close_discussion → surface_candidates / compute_effectiveness)"
type: spec
status: complete
completed_at: 2026-05-15
risk_level: low
intake_ids: []
discussion_id: DISC-20260515-053700-phase0-promotion-pipeline-fix-spec-review
reviewed_by:
  - qa-specialist
  - architecture-consultant
completed_at:
completed_commit:
---

## Goal

Repair the silently-failing seam between Layer 1 discussion closure and Layer 3 promotion candidacy so that reasoning captured in `/review` and `/deliberate` discussions can actually accumulate into curated memory. After this lands, closing a discussion whose findings cluster into a Rule-of-Three-qualifying pattern must produce a row in `promotion_candidates`, and a developer running `/promote` on that row must be able to write a real file under `memory/patterns/`.

This is Phase 0 of `docs/plans/framework-memory-evolution-2026-05.md`. It is the prerequisite for Phase 1 (substrate wiring) — without it, the framework's central claim ("reasoning is the primary artifact") is structurally violated end-to-end.

## Context

### Symptom
Parent SQLite reports **109 pattern_sightings, 0 promotion_candidates**. Every `close_discussion` invocation prints non-fatal warnings during candidate-surfacing and effectiveness-computation steps. The pipeline appears to run cleanly because the warnings are easy to miss.

### Root causes (two confirmed defects + one collateral discovery)

**Defect 1 — `surface_candidates` kwarg drift** (priority for this spec)
- [scripts/close_discussion.py:144](scripts/close_discussion.py#L144) calls `surface_candidates(discussion_id=discussion_id)`
- [scripts/surface_candidates.py:20](scripts/surface_candidates.py#L20) signature: `def surface_candidates(threshold: int = 3) -> int`
- Result: `TypeError: surface_candidates() got an unexpected keyword argument 'discussion_id'` on every closure. Caught by the broad `except Exception` at line 145, printed as a warning, swallowed.

**Defect 2 — `compute_effectiveness` import-name drift** (priority for this spec)
- [scripts/close_discussion.py:150](scripts/close_discussion.py#L150) `from compute_agent_effectiveness import compute_effectiveness`
- The actual exported function name is `compute_agent_effectiveness` (line 20 of that module). `compute_effectiveness` does not exist.
- Result: `ImportError: cannot import name 'compute_effectiveness'` on every closure. Same swallow behaviour at line 154.
- Note: `compute_agent_effectiveness` already accepts `discussion_id: str | None = None` — so unlike Defect 1, no signature extension is needed; only the import name and the call site need to match.

**Collateral defect 3 — `/promote` schema drift** (surfaced during this spec, scope question)
- [.claude/commands/promote.md:55-59](.claude/commands/promote.md#L55-L59) queries `promotion_candidates` with columns: `candidate_id, candidate_type, title, evidence_count, target_path, created_at, status`
- Actual schema (from [scripts/init_db.py:124](scripts/init_db.py#L124) and the live DB) is: `id, finding_pattern, category, sighting_count, first_seen, last_seen, promoted, promoted_at, promoted_to, evidence_ids`
- None of the queried columns exist. `/promote`'s SELECT fails with `sqlite3.OperationalError`, which `/promote` defensively catches and degrades to "promotion_candidates table not available — proceeding with manual promotion." A developer running `/promote` after this fix would still not see any surfaced candidate.
- The same drift affects [scripts/enforce_forgetting_curve.py:52](scripts/enforce_forgetting_curve.py#L52) which queries `source_file, last_referenced_at` (also non-existent).

### Prior art
- [docs/adr/ADR-0013-token-efficiency-telemetry.md:122](docs/adr/ADR-0013-token-efficiency-telemetry.md#L122) explicitly notes both Defect 1 and Defect 2 as known follow-ups discovered during the ADR's deliberation. The fix was deferred.
- [docs/sprints/SPEC-20260405-110000-v340-release.md:55](docs/sprints/SPEC-20260405-110000-v340-release.md#L55) records this as deferred bug **R5.4**.
- Diagnostic in worktree `.claude/worktrees/reverent-lovelace-84e718/diagnostics/framework_self_diagnostic_2026-05-13.md` ranks this as "single highest-ROI move in the framework" and retroactively explains the downstream Verification Portal's 82-sightings/0-candidates incident.
- No prior Solution Path exists in `memory/projects/_self.md` for `[framework/promotion-pipeline]` — this fix becomes the first.
- No Known-Broken Approach in `memory/bugs/regression-ledger.md` for this area.

## Requirements

### R1 — Restore the surface_candidates auto-invocation path
`close_discussion(discussion_id)` must, without warning, surface promotion candidates for patterns touching that discussion.

### R2 — Restore the compute_agent_effectiveness auto-invocation path
`close_discussion(discussion_id)` must, without warning, compute and persist agent-effectiveness records for the closed discussion.

### R3 — Preserve manual CLI behaviour
Both `python scripts/surface_candidates.py [--threshold N]` and `python scripts/compute_agent_effectiveness.py <id> | --all` must continue to work as documented. `.claude/commands/knowledge-health.md:31,39` invokes both manually; that path must not break.

### R4 — End-to-end fixture proves the seam works
A regression test runs a synthesized fixture discussion (three, to satisfy Rule of Three) through `close_discussion.py` and asserts at least one row appears in `promotion_candidates`. The test must cover **both** branches of `surface_candidates.py:67-93`:

- **R4.a — INSERT branch** (qa-F1): No prior `promotion_candidates` row exists for the pattern. Pipeline runs; assert exactly one new row is created with the expected `finding_pattern`, `category`, and `sighting_count` ≥ 3.
- **R4.b — UPDATE branch** (qa-F1, blocking): A `promotion_candidates` row already exists for the pattern with `sighting_count = N`. Pipeline runs after adding more sightings; assert the existing row's `sighting_count`, `last_seen`, and `evidence_ids` are updated (and no new row is inserted). Use the actual column names from `surface_candidates.py:75-78` (`sighting_count`, `last_seen`, `evidence_ids`) — NOT the phantom columns the qa critique briefly referenced (`recurrence_count`, `status` do not exist in the real schema).

The regression test file should include an in-code comment naming the pre-fix wrong signature (qa-F3 advisory adopted): `# Regression: close_discussion called surface_candidates(discussion_id=...) against signature def surface_candidates(threshold=3) → TypeError swallowed as non-fatal warning`.

### R5 — Promotion target reachable
After the regression test passes, a developer running `/promote` against the surfaced row must be able to write a file to `memory/patterns/` (not `.gitkeep`). See Constraints C4 for how this requirement interacts with the collateral defect.

### R6 — Knowledge persistence
The fix is captured as a Solution Path in `memory/projects/_self.md` and a regression-ledger entry in `memory/bugs/regression-ledger.md`. The regression test is tagged `@pytest.mark.regression`.

The regression-ledger entry must explicitly name the canary contract (arch-F4 advisory adopted): *"This test is the structural canary for the swallow-and-warn pattern at close_discussion.py:140-155. Do not remove or weaken without an ADR addressing the swallowed-exception pattern."*

## Constraints

### C1 — No retroactive backfill
Do not bulk-promote the existing 109 pattern_sightings or attempt to populate `promotion_candidates` from historical data. Demonstrating end-to-end flow for a single new pattern is sufficient. Layer 3 hygiene under historical drift is a separate decision.

### C2 — Do not touch the substrate
`assertion_store/` and `mcp_server/` are out of scope. Phase 1 wires substrate into a workflow; Phase 0 is the prerequisite, not that phase.

### C3 — No compliance instrumentation
Do not add new logging frameworks, observability hooks, or telemetry surfaces. Phase 4 covers compliance.

### C4 — Treatment of collateral Defect 3 (/promote schema drift)
This spec defaults to **fixing the collateral defect** because R5 explicitly requires `/promote` to write a real file after seeing the surfaced candidate, and without that fix the acceptance criterion is unverifiable. Two viable approaches; the architecture review should pick one:

- **C4-a (preferred default):** Patch `.claude/commands/promote.md` to query the actual schema (`id, finding_pattern, category, sighting_count, first_seen, last_seen, promoted, evidence_ids`) and update its UPDATE statement to set `promoted=1, promoted_at=?, promoted_to=?` instead of the fictional `status/reviewed_at/last_referenced_at/human_verdict` columns. Lightest touch. Same approach applied to `scripts/enforce_forgetting_curve.py` if the same drift exists there.
- **C4-b:** Extend the `promotion_candidates` schema (and a one-shot migration) to add the missing columns. Heavier; matches what /promote was "designed for"; risks a deeper rewrite of surface_candidates that contradicts C1.

If specialists prefer to scope C4 out of Phase 0, R5 must be downgraded to "a manual `/promote <path>` invocation still writes a file" — the queue-driven path becomes a Phase 0.5 ticket.

### C5 — Swallowed-exception hygiene
The bare `except Exception` blocks at [close_discussion.py:128, 137, 145, 154](scripts/close_discussion.py) are how this bug stayed alive. We retain them (a single failed step should not abort sealing), but the warnings they emit must carry the actual exception type. This is already the current behaviour (`f"Warning: ... failed (non-fatal): {e}"`). No change required; mention for completeness.

## Acceptance Criteria

- [ ] Running `close_discussion.py` on three fixture discussions whose findings share the same `pattern_hash` (Rule-of-Three qualifying) produces at least one row in the `promotion_candidates` table. **Verified by row-count assertion in the regression test** (qa-F2 adopted), not by parsing stdout.
- [ ] The new regression test under `tests/` reproduces the above end-to-end. Tagged `@pytest.mark.regression`. Covers **both** the INSERT branch (R4.a) and the UPDATE branch (R4.b) of `surface_candidates.py:67-93`. Includes an in-code comment naming the pre-fix wrong signature for traceability.
- [ ] Quality gate's regression check passes — the new test demonstrably fails when the broken signatures are restored. Verification protocol: during implementation, briefly revert the close_discussion fix, run the new test, observe failure, then re-apply the fix. The build summary records that this verification was performed.
- [ ] **C4-a adopted** (per architecture-consultant Finding 2): manual `/promote` against the surfaced candidate writes a real file under `memory/patterns/`. Verified by a single manual smoke run captured in the build summary. No automated test for `/promote` itself in this spec (qa-F5 acknowledged — `/promote` is an interactive slash command requiring developer approval at every promotion, not unit-testable here).
- [ ] `python scripts/quality_gate.py` passes 7/7.
- [ ] Existing test `tests/test_close_discussion_rollup.py` continues to pass.
- [ ] An entry is added to `memory/bugs/regression-ledger.md` documenting bug, root cause, fix, the new test's location, **and the canary-contract sentence** (per arch-F4).
- [ ] A Solution Path entry is added to `memory/projects/_self.md` under `## Solution Paths` with the compound tag `[framework/promotion-pipeline]`.
- [ ] No new ADR is required (defect repair; confirmed by architecture-consultant Finding 3). C4-b path (schema extension) was considered and explicitly rejected as canonizing fictional columns.
- [ ] BUILD_STATUS.md is updated before the build's compaction boundary, per `.claude/rules/autonomous_workflow.md`.

## Risk Assessment

### R-1 — Per-discussion scoping of `surface_candidates` changes semantics
The plan's recommendation extends `surface_candidates` to accept `discussion_id` and "scope candidate-surfacing to patterns touching that discussion." This is subtly different from the current project-wide behaviour. A pattern that crosses the Rule-of-Three threshold only when this newly-closed discussion is added would surface either way; but a pattern that was *already* over-threshold and was missed before would still be surfaced under project-wide behaviour and might be filtered out under per-discussion scoping. Mitigation: make the new parameter additive — when `discussion_id` is set, the candidate-search still considers global pattern_sightings, but only emits/updates rows whose `pattern_hash` has a sighting in the closing discussion. This preserves Rule-of-Three counting while making the closure-time invocation "the same as the manual --all run, except scoped to interesting rows."

### R-2 — Test isolation against the project SQLite
The regression test must not pollute the project's real `metrics/evaluation.db`. Use a temp directory + monkeypatched `DB_PATH` (the scripts already gate on `DB_PATH.exists()`; a temp DB with the right schema works). Existing test `tests/test_close_discussion_rollup.py` is the reference for how to do this.

**Implementation note (qa-F4 advisory adopted):** Before writing the test, verify by reading each affected module that `DB_PATH` is resolved at *call time* via module attribute (so `monkeypatch.setattr("scripts.surface_candidates.DB_PATH", tmp_path / "test.db")` works). All currently inspected modules (`surface_candidates`, `mine_patterns`, `compute_agent_effectiveness`, `extract_findings`) appear to follow this pattern, but the test author should confirm before adoption rather than assume.

### R-3 — Fixture realism
The fixture must produce findings that actually cluster — `mine_patterns.py` uses Jaccard similarity ≥ 0.4 on tokenized summaries, and `surface_candidates` requires ≥ 3 *distinct* discussion_ids per pattern_hash. The fixture must satisfy both. A naive single-discussion fixture will not surface a candidate even after the fix. Mitigation: synthesize three minimal discussions in the test, each containing one finding whose summaries Jaccard-collide.

### R-4 — Collateral schema drift (Defect 3)
If C4-a is the chosen scope, edits to `.claude/commands/promote.md` are a doc change in form but a behaviour change in effect (it actually runs SQL). The build review protocol checkpoint should treat this as touching multiple categories (commands + memory infrastructure). Lightly mitigated by the fact that `/promote` requires explicit developer approval at every promotion.

### R-5 — Silent rollout
The bug was deferred for ~5 weeks because nothing alarmed when it failed. After the fix, a *future* break of either step would re-introduce silent rollback. Out of scope to fix the swallowing pattern (C5), but the regression test acts as the canary: if either step regresses, the test fails. This is acceptable for Phase 0.

## Affected Components

- [scripts/close_discussion.py](scripts/close_discussion.py) — call sites at lines 141-146 and 149-155
- [scripts/surface_candidates.py](scripts/surface_candidates.py) — signature, body, and CLI argparse must accept new optional kwarg
- [scripts/compute_agent_effectiveness.py](scripts/compute_agent_effectiveness.py) — confirm no edits needed beyond the corrected import on the caller side
- [.claude/commands/promote.md](.claude/commands/promote.md) — only if C4-a is adopted
- [scripts/enforce_forgetting_curve.py](scripts/enforce_forgetting_curve.py) — only if C4-a is adopted *and* the schema-drift fix extends here
- `tests/test_close_discussion_promotion_pipeline.py` (new) — regression test
- [memory/bugs/regression-ledger.md](memory/bugs/regression-ledger.md) — new entry
- [memory/projects/_self.md](memory/projects/_self.md) — new Solution Path entry
- BUILD_STATUS.md — updated during/after the build

Not affected: CLAUDE.md (no constitutional change), `docs/adr/` (no new decision), `assertion_store/`, `mcp_server/`, framework presentations (no agent/rule/command count changes).

## Dependencies

### Depends on
- A live `metrics/evaluation.db` with the canonical schema (already present; verified by inspection)
- The capture pipeline scripts (`mine_patterns`, `extract_findings`, `surface_candidates`, `compute_agent_effectiveness`) being individually importable — already the case.

### Depended on by
- **Phase 1 (substrate wiring)** of the memory-evolution plan — Phase 1's prompt is generated *after* Phase 0 merges to main. Phase 0 ships independently.
- All downstream `/promote` activity until this fix lands (currently 0 candidates ever, so no real backlog).
- The Verification Portal incident is retroactively explained but not directly fixed by this spec; the lesson should be captured in the Solution Path.

## Out of Scope

- Retroactive promotion of the existing 109 pattern_sightings (per C1)
- Substrate / MCP server / assertion_store changes (per C2)
- New logging or telemetry frameworks (per C3)
- A general fix to the "swallowed exception" pattern (per C5 — retained for resilience; regression test is the canary)
- Schema migrations adding `candidate_id, candidate_type, title, target_path, status` columns to `promotion_candidates` (C4-b path) — only adopted if architecture review explicitly chooses it
- Rewriting `/promote` from scratch
