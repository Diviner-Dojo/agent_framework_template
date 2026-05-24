---
review_id: REV-20260524-182841
date: 2026-05-24
risk_level: high
verdict: approve
type: confirmation
confirms_review: REV-20260523-125823
confirms_discussion: DISC-20260523-195154-review-distribute-b1-floor
reviewed_files:
  - tests/conftest.py
  - scripts/distribute/change_package.py
  - scripts/distribute/assessment.py
  - scripts/distribute/stage_branch.py
  - tests/test_distribute.py
specialists: [qa-specialist, independent-perspective]
blocking_count: 0
advisory_count: 1
---

# Confirmation re-review — /distribute B1 floor + interpreted assessment

**Verdict: APPROVE.** This is a focused confirmation gate (specialists dispatched directly, not a
fresh full `/review`) that closes out `REV-20260523-125823` (REQUEST-CHANGES) and clears the work
for commit on `feat/distribute-b1-floor`. The substantive review record is REV-20260523-125823; this
captures the resolution.

## Blocking findings from REV-20260523-125823 — all confirmed RESOLVED

Re-confirmed by the two specialists who raised them, reading the **worktree** copies directly (the
precaution REV-125823's own process-lesson demands — its two discarded findings came from reading the
stale main checkout):

- **#1 escalate-only mechanical (independent-perspective, 0.93):** RESOLVED — `stage()` takes
  `exclude_paths` and `continue`s before `shutil.copy2`; the guarantee is in the writer, not
  orchestration prose. Proven by `TestStageExcludesEscalated`.
- **#2 B1 regression-ledger row (qa):** RESOLVED.
- **#3 `redact_secrets` fail-closed test (qa):** RESOLVED — `TestRedactSecretsFailClosed`.
- **#4 deleted-drift → collision-diverged test (qa):** RESOLVED — `TestDeletedDriftClassification`.

Advisory folds confirmed: sec F1, sec F2, qa F6, **qa F5** (new `TestNoneDriftClassification`, the
`drift_status is None` arm of B1), **indep D** (the `OverwriteDiff.triage_hint` provenance invariant).
Original-review must-fix carry-overs **B2/B3/B4** also folded.

## Test-harness fix reviewed this pass (new `tests/conftest.py`)

The git-using tests were not hermetic against an inherited git environment: run inside the pre-commit
hook, `GIT_DIR`/`GIT_INDEX_FILE` overrode `git -C <tmp>` and broke `git add` (exit 128) — the suite
passed standalone but failed only inside the commit hook (no test file in the repo shielded itself).
Fix: `tests/conftest.py` session-autouse fixture strips all `GIT_*` env vars.
**qa-specialist APPROVE (0.97):** correct, right scope, strip-all safer than a named subset (tests set
their own identity per-repo), no git-using test left leaking. Verified: full suite **319 passed**
normally and **319 passed** under a simulated hook env (`GIT_DIR` set) — the case that previously failed.

## Advisory (non-blocking, carry to v1.1)

- **independent-perspective:** the `stage()` `exclude_paths` backstop defends against an orchestrator
  that *forgets to halt* an escalated file but not one that *never populates* `exclude_paths` (a future
  Python port skipping the `reclassify_route` loop). Acceptable for v1 (the file is still surfaced as
  `value-unverified` regardless of routing); re-deriving escalation inside `stage()` would duplicate the
  room's judgment. Track if orchestration is ported to Python.

## Gate

Quality gate 7/7 standalone (73 distribute tests; 319 suite-wide); coverage ≥80%; 17 ADRs; 5+1
regression guards; ruff clean.
