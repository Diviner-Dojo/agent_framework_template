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
| mcp_server/server.py | SQLite connection opened at module import on one thread reused across FastMCP worker threads, causing every assert_fact / search_semantic call to raise "SQLite objects created in a thread can only be used in that same thread". Surfaced 2026-05-12 during Phase 4 canonical MCP test (Step 2). Fix: thread-local connection via threading.local(), lazily opened per worker thread. | OS Resource Lifecycle | 2026-05-12 | tests/test_mcp_server.py | TestThreadLocalIsolation::test_two_threads_receive_distinct_connections |
| mcp_server/server.py | get_source parsed a caller-supplied URI and used the embedded relpath directly as `Path(relpath).read_text()` without containment, allowing path traversal (`project://<id>/../../etc/passwd`) to read arbitrary files from the host filesystem. Surfaced 2026-05-12 via REV-20260512-132622 (Finding 1, qa + arch + security convergence). Fix: resolve path against _SERVER_DIR and verify is_relative_to() one of SOURCE_ROOTS. | Trust Boundary Gap | 2026-05-12 | tests/test_mcp_server.py | TestGetSourcePathTraversal::test_traversal_via_dotdot_rejected |
| mcp_server/server.py | _build_source_uri returned any caller-supplied URI starting with `project://` unchanged, allowing assertions to be stored with foreign project_ids (boundary corruption) and traversal patterns to be smuggled through the bare-path branch into stored assertions. Surfaced 2026-05-12 via REV-20260512-132622 (Finding 2, security). Fix: always re-canonicalise with current PROJECT_ID; reject `..` patterns at write time. | Trust Boundary Gap | 2026-05-12 | tests/test_mcp_server.py | TestBuildSourceUriTraversalRejection::test_traversal_in_bare_ref_raises |

## Known-Broken Approaches

Approaches that were tried and found broken. Queried by the pre-build search rule
(`.claude/rules/pre_build_search.md`) to prevent repeating mistakes.

| Approach | Domain | Why Broken | Use Instead | Evidence | Learned |
|----------|--------|-----------|-------------|----------|---------|
<!-- Add entries below this line -->
