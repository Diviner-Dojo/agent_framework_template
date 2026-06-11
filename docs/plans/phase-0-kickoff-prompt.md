# Phase 0 Kickoff Prompt

> Paste the prompt below into a Claude Code session running in the project root, on a fresh branch cut from `main` (after the substrate PR has merged).
>
> The framework's `/plan` command will turn this into a structured spec, send it to specialists for review, gate on developer approval, then hand off to `/build_module` for implementation.
>
> Phase 0 is intentionally small — a mechanical bug fix with a regression test. It is the seed that proves the framework's own promotion pipeline works end-to-end.

---

## The prompt

```
/plan Fix the framework's promotion pipeline API drift so reasoning can actually accumulate into Layer 3 memory.

Context
This is Phase 0 of the framework memory evolution plan (docs/plans/framework-memory-evolution-2026-05.md). The framework's central claim — "reasoning is the primary artifact" — is currently broken at the seam between captured discussions and curated memory. Two pipeline calls in scripts/close_discussion.py invoke functions with the wrong signatures; the resulting TypeErrors are swallowed as non-fatal warnings and the pipeline silently fails to populate promotion_candidates. The parent SQLite shows 109 pattern_sightings and 0 promotion_candidates as a result. This is logged as deferred bug R5.4 in prior BUILD_STATUS notes.

What to fix
1. scripts/close_discussion.py line 95 calls surface_candidates(discussion_id=discussion_id) but scripts/surface_candidates.py:20 signature is `def surface_candidates(threshold: int = 3)`. Every closure raises TypeError.
2. scripts/close_discussion.py line 101 imports `compute_effectiveness` from compute_agent_effectiveness.py; verify the exported function name and align the call signature.

Recommended approach (the plan's preference, open to specialist challenge)
- Extend surface_candidates.py to accept an optional `discussion_id` parameter. When present, scope candidate-surfacing to patterns touching that discussion. When absent, retain the existing project-wide behavior. Preserves both the auto-invoke and manual CLI call sites.
- Apply the same pattern to compute_effectiveness if the same drift exists there.

Required artifacts
- A regression test under tests/ that runs close_discussion.py end-to-end against a fixture discussion and asserts a promotion_candidates row appears. Tag the test @pytest.mark.regression.
- An entry in memory/bugs/regression-ledger.md documenting the bug, root cause, fix, and test location.
- A Solution Path entry in memory/projects/_self.md under "## Solution Paths" capturing what was tried and why this approach was chosen, with the tag [framework/promotion-pipeline].

Acceptance criteria
- Running close_discussion.py on a fixture discussion with one Rule-of-Three-qualifying pattern produces a row in the promotion_candidates table.
- A manual /promote against that surfaced candidate writes a real file under memory/patterns/ (not just .gitkeep).
- The new regression test passes; quality_gate.py passes 7/7.
- No existing close_discussion.py call sites in tests/ break.

Risk tier
Low. Mandatory specialists: qa-specialist, architecture-consultant. No security or performance specialist needed unless the spec review surfaces a reason.

Out of scope
- Do not attempt to repair Layer 3 retroactively (i.e., do not bulk-promote the existing 109 pattern_sightings). Only validate that one pattern can now flow end-to-end.
- Do not touch the substrate (assertion_store, mcp_server). Phase 1 wires substrate into a workflow; Phase 0 is the prerequisite, not that phase.
- Do not add compliance instrumentation. That is Phase 4.

What happens after this lands
After Phase 0 merges to main, the next prompt (Phase 1: cure the substrate in one workflow) will be generated. Phase 0 ships independently — no need to wait for Phase 1 design.

Operating constraints
- Follow .claude/rules/autonomous_workflow.md sequencing: /plan → /build_module → quality_gate → /review → commit.
- Use the build_review_protocol.md checkpoint pattern if the build touches more than one of: scripts/, tests/, memory/.
- Update BUILD_STATUS.md before any compaction.
- This is framework-only work (.claude/, scripts/, tests/, memory/); follow framework-doc-sync if any documentation surfaces are affected.
```

---

## Usage notes

- Run this in a Claude Code session on the project root. If the substrate PR has not yet merged, branch from `feature/sourced-assertion-substrate` instead of `main` to avoid context loss — but `main` is the cleaner base once that PR is in.
- The `/plan` command will produce a structured spec, dispatch the named specialists for design review, and stop at the developer-approval gate. Do not let it auto-advance into `/build_module` until you've read the spec.
- If a specialist objects to the recommended approach (e.g., proposes a different parameter shape), let them — the recommended approach is a starting point, not a directive. Phase 0's value is in restoring the pipeline, not in any specific signature.
- Phase 0's expected wall-clock is 1–2 days end to end (spec → review → build → checkpoint review → final review → quality gate → commit).

## Pre-flight (must be true before pasting)

- [ ] Substrate PR merged to `main`, OR a deliberate decision made to base Phase 0 on the substrate branch
- [ ] Working tree is clean (`git status` shows no uncommitted code in the chosen base)
- [ ] BUILD_STATUS.md reflects "entering Phase 0"
- [ ] You are not in a hurry — the spec review gate is load-bearing
