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

## Known-Broken Approaches

Approaches that were tried and found broken. Queried by the pre-build search rule
(`.claude/rules/pre_build_search.md`) to prevent repeating mistakes.

| Approach | Domain | Why Broken | Use Instead | Evidence | Learned |
|----------|--------|-----------|-------------|----------|---------|
<!-- Add entries below this line -->
