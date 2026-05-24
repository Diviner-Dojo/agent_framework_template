# Regression Ledger

Tracks bugs that have been fixed along with their regression test files.
The quality gate's regression guard checks that files listed here have
corresponding test coverage to prevent regressions.

**Rule**: Write the ledger entry BEFORE the commit, not after. Post-commit deferral means the entry never gets written.

## Root-Cause Taxonomy

Classify every regression by root cause. Three consecutive failures in the same class + subsystem triggers a structural invariant promotion review.

| Class | Description | Example |
|-------|-------------|---------|
| **OS Resource Lifecycle** | OS-level resource not properly acquired/released | File handle leak, socket not closed |
| **Async Race** | Timing-dependent behavior under concurrent execution | Write-after-read race, stale cache |
| **Guard Inversion** | Boolean logic or condition check reversed | `if enabled` when it should be `if not enabled` |
| **Missing Null/Empty Case** | Code assumes non-null/non-empty without checking | Unhandled None from DB query |
| **Trust Boundary Gap** | Input crosses a trust boundary without validation | Unsanitized user input in SQL |
| **Provider Rebuild Side-Effect** | State mutation during dependency reconstruction | Config reset on service restart |
| **Schema/Serialization Drift** | Data format changes without migration | JSON field renamed without migration |
| **Intent Routing Gap** | Correct handler exists but input not routed to it | Missing URL pattern, wrong HTTP method |
| **Abstraction Narrowing** | Abstraction covers fewer cases than callers assume | Utility function rejects valid edge case |

## Format

| File | Bug Description | Root Cause Class | Fix Date | Test File | Test Function |
|------|----------------|-----------------|----------|-----------|---------------|
<!-- Add entries below this line -->
| scripts/close_discussion.py + scripts/surface_candidates.py | Promotion pipeline silently failed at the seam between Layer 1 closure and Layer 3 candidacy. (Defect 1) close_discussion.py:144 called `surface_candidates(discussion_id=discussion_id)` against signature `def surface_candidates(threshold=3)` — every closure raised TypeError. (Defect 2) close_discussion.py:150 imported `compute_effectiveness` from `compute_agent_effectiveness`; actual exported name is `compute_agent_effectiveness` — every closure raised ImportError. Both errors swallowed by broad `except Exception` and printed as non-fatal warnings. Parent SQLite accumulated 109 pattern_sightings and 0 promotion_candidates over ~5 weeks. **Canary contract: tests/test_close_discussion_promotion_pipeline.py is the structural canary for the swallow-and-warn pattern at close_discussion.py:140-155. Do not remove or weaken without an ADR addressing the swallowed-exception pattern.** Fix: extended surface_candidates with optional discussion_id kwarg (Rule-of-Three counting stays global; emission filtered to closing-discussion patterns); corrected import name; reconciled /promote.md and enforce_forgetting_curve.py with the canonical schema (removed phantom columns rather than back them with fictional schema). | Schema/Serialization Drift | 2026-05-15 | tests/test_close_discussion_promotion_pipeline.py | test_canary_surface_candidates_accepts_discussion_id_kwarg; test_canary_compute_agent_effectiveness_import_name; TestPromotionPipelineInsertBranch; TestPromotionPipelineUpdateBranch |
| mcp_server/server.py | SQLite connection opened at module import on one thread reused across FastMCP worker threads, causing every assert_fact / search_semantic call to raise "SQLite objects created in a thread can only be used in that same thread". Surfaced 2026-05-12 during Phase 4 canonical MCP test (Step 2). Fix: thread-local connection via threading.local(), lazily opened per worker thread. | OS Resource Lifecycle | 2026-05-12 | tests/test_mcp_server.py | TestThreadLocalIsolation::test_two_threads_receive_distinct_connections |
| mcp_server/server.py | get_source parsed a caller-supplied URI and used the embedded relpath directly as `Path(relpath).read_text()` without containment, allowing path traversal (`project://<id>/../../etc/passwd`) to read arbitrary files from the host filesystem. Surfaced 2026-05-12 via REV-20260512-132622 (Finding 1, qa + arch + security convergence). Fix: resolve path against _SERVER_DIR and verify is_relative_to() one of SOURCE_ROOTS. | Trust Boundary Gap | 2026-05-12 | tests/test_mcp_server.py | TestGetSourcePathTraversal::test_traversal_via_dotdot_rejected |
| mcp_server/server.py | _build_source_uri returned any caller-supplied URI starting with `project://` unchanged, allowing assertions to be stored with foreign project_ids (boundary corruption) and traversal patterns to be smuggled through the bare-path branch into stored assertions. Surfaced 2026-05-12 via REV-20260512-132622 (Finding 2, security). Fix: always re-canonicalise with current PROJECT_ID; reject `..` patterns at write time. | Trust Boundary Gap | 2026-05-12 | tests/test_mcp_server.py | TestBuildSourceUriTraversalRejection::test_traversal_in_bare_ref_raises |
| scripts/distribute/change_package.py | /distribute classified an unprovable overwrite as silent `value` and would clobber a target's authored customization on merge. Drift is computed against the target's own MUTABLE baseline DB, not a hub-target common ancestor, so `drift_status == "current"` (after a re-baseline-after-edit) or `None` (under a narrowed `tracked_paths`) does NOT prove the target's copy descends untouched from the hub. Surfaced 2026-05-23 via REV-20260523-065900 (B1, independent-perspective; Prime Objective tests (b)/(c)). Fix: mechanical safety floor — `_classify` routes such overwrites to `value-unverified` (stageable but ALWAYS surfaced with per-file detail), never silent `value`; `value` is unreachable for overwrites in v1 (reserved for v1.1 ancestor-proven safety, ADR-0017). | Abstraction Narrowing | 2026-05-23 | tests/test_distribute.py | TestStaleBaselineRegression::test_rebaseline_after_edit_is_flagged_not_silent |

## Known-Broken Approaches

Approaches that were tried and found broken. Queried by the pre-build search rule
(`.claude/rules/pre_build_search.md`) to prevent repeating mistakes.

| Approach | Domain | Why Broken | Use Instead | Evidence | Learned |
|----------|--------|-----------|-------------|----------|---------|
<!-- Add entries below this line -->
<!-- Note: quality_gate.py's _parse_regression_ledger() currently parses every
     pipe-delimited row as if it were a fixed-bug entry (6 cells: File | Bug |
     Root Cause | Fix Date | Test File | Test Function) and treats cell[4] as a
     test path. Known-Broken Approaches use a different 6-column schema (Approach
     | Domain | Why Broken | Use Instead | Evidence | Learned) and will trigger a
     spurious "missing test file" failure if added here. Captured as a follow-up
     for a future quality_gate.py refactor; until then, capture cross-spec
     anti-patterns in memory/projects/_self.md Solution Paths instead. -->

