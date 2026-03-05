---
discussion_id: DISC-20260304-214110-review-search-filter-only-browse-fix
started: 2026-03-04T21:41:24.517114+00:00
ended: 2026-03-04T21:53:24.979887+00:00
agents: [facilitator, performance-analyst, qa-specialist]
total_turns: 6
---

# Discussion: DISC-20260304-214110-review-search-filter-only-browse-fix

## Turn 1 — facilitator (evidence)
*2026-03-04T21:41:24.517114+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Fix search filter-only browse — tapping Mood/People/Topics filter chips and pressing Apply returned no results. The original plan misdiagnosed this as a data issue; real root cause was that the search stack short-circuited on empty query regardless of active filters.
- **Files/scope**: lib/database/daos/session_dao.dart (searchSessions query), lib/repositories/search_repository.dart (searchEntries early return + message search skip), lib/providers/search_providers.dart (searchResultsProvider early return), lib/ui/screens/search_screen.dart (_buildResultsBody pre-search state), plus regression tests for all three layers.
- **Developer-stated motivation**: Device testing on SM_G998U1 confirmed search filters (mood, people, topics) were completely non-functional when no keyword was typed.
- **Explicit constraints**: No schema changes. Fix must not break existing keyword+filter search. Regression tests required at DAO, repository, and provider layers.

---

## Turn 2 — qa-specialist (proposal)
*2026-03-04T21:44:23.879575+00:00 | confidence: 0.88*
*tags: critique*

## QA Specialist Review

**Confidence**: 0.88

### Blocking Findings

**B1 — @Tags(['regression']) missing from all three new regression test groups**
- Severity: High / Blocking
- Location: test/database/search_dao_test.dart, test/repositories/search_repository_test.dart, test/providers/search_providers_test.dart — all new regression groups
- testing_requirements.md states 'Tag regression tests with @Tags(["regression"]) and include a comment referencing the bug' without qualification. The tags are absent.
- Fix: Add @Tags(['regression']) to each regression test group.

**B2 — No widget regression test for _buildResultsBody filter-only path**
- Severity: Medium / Blocking per regression policy
- Location: test/ui/screens/ — no test for this fix site
- The _buildResultsBody guard change (query.isEmpty && !filters.hasActiveFilters) has no widget-level coverage. The documented fix site has no regression test. A filter-only browse with an active mood filter should show results, not the pre-search 'Search your journal' state.
- Fix: Add testWidgets case in search_screen_expanded_test.dart or search_screen_results_test.dart.

### Advisory Findings

**A1 — createSessionWith helper missing people/topicTags params** (Low)
- Repository test helper accepts only moodTags. No filter-only browse tests for People or Topics at repository layer. Code path identical, risk low.

**A2 — msgSnippetFutures with empty trimmed is unreachable but undocumented** (Low)
- Line 113 in search_repository.dart calls getMessageSnippets(id, trimmed) with empty trimmed if messageOnlyIdList is non-empty. This cannot happen (messages=[] when trimmed.isEmpty), but the invariant is not asserted.

### Edge Cases Not Tested
- Multi-filter combination with empty query (moodTags + topicTags simultaneously, no keyword)
- NULL metadata column in filter-only mode (existing 'null fields' test uses a keyword query)
- Whitespace-only query with active filter

### Strengths
- Constant(true) fallback in searchSessions is clean and readable
- Guard condition applied consistently at all three short-circuit sites
- Regression ledger entry is thorough — names all four files, all three root causes
- Pre-existing 'empty query with no filters still returns empty results' test guards against over-correction

---

## Turn 3 — performance-analyst (proposal)
*2026-03-04T21:44:33.556537+00:00 | confidence: 0.87*
*tags: critique*

## Performance Analyst Review

**Confidence**: 0.87

### All Advisory (no blocking findings)

**A1 — Document message search skip intent** (Low)
- Location: search_repository.dart — filter-only browse message skip branch
- Existing comment at lines 55-57 partially covers this. Acceptable.

**A2 — LIKE scans on unindexed tag columns** (Low)
- Location: session_dao.dart — moodTags/people/topicTags LIKE filters
- Full table scan on unindexed columns. At 100-1000 sessions: sub-millisecond, acceptable. At 10k-100k: 5-50ms range on mobile. No normalization exists (columns store JSON arrays). No action needed at current scale; document that these are linear scans by design.

**A3 — Future.value([]) for snippet skip is optimal** (Informational)
- Resolves synchronously, no DB work. Correct and cheapest possible path.

**A4 — Constant(true) full table scan for filter-only** (Low)
- Generates WHERE 1 or no WHERE clause, meaning all rows scanned before tag LIKE filters apply. Fine at current scale. If pagination added later, push LIMIT into DAO.

### Strengths
- trimmed.isEmpty && !filters.hasActiveFilters early return is correct hot-path guard
- Skipping messagesFuture and snippet futures for filter-only eliminates two async round-trips
- escapeLikeWildcards inside query.isNotEmpty branch prevents '%%' matching all rows

---

## Turn 4 — facilitator (synthesis)
*2026-03-04T21:52:07.926891+00:00 | confidence: 0.91*
*tags: blocking:0, advisory:4*

## Request Context
- **What was requested**: Fix search filter-only browse — tapping Mood/People/Topics filter chips and pressing Apply returned no results when no keyword was typed.
- **Files/scope**: lib/database/daos/session_dao.dart, lib/repositories/search_repository.dart, lib/providers/search_providers.dart, lib/ui/screens/search_screen.dart, plus regression tests at DAO/repository/provider/UI layers.
- **Developer-stated motivation**: Device testing on SM_G998U1 confirmed search filters were completely non-functional without a keyword.
- **Explicit constraints**: No schema changes. Fix must not break existing keyword+filter search. Regression tests required at all layers.

## Verdict: approve-with-changes

Both blocking findings resolved in-review before submission.

## Blocking Findings Resolved In-Review

**B1 — @Tags(['regression']) missing** (resolved)
Created dedicated regression test file test/database/search_filter_browse_regression_test.dart with @Tags(['regression']) library annotation. Covers all three filter types (mood, people, topics), date filter, and combined AND-logic filter — both DAO, repository, and provider layers. Avoids polluting mixed test files with a file-level tag.

**B2 — No widget regression test for _buildResultsBody** (resolved)
Added two testWidgets cases to test/ui/screens/search_screen_expanded_test.dart:
1. 'active mood filter with empty query shows results, not pre-search state'
2. 'no query and no filters shows pre-search state (unchanged behaviour)'

## Advisory Findings (open)

**A1 — createSessionWith helper in search_repository_test.dart missing people/topicTags** (Low)
Existing test helper accepts only moodTags. The new regression file uses a full-param helper. Risk low — code paths identical.

**A2 — msgSnippetFutures with empty trimmed is unreachable but undocumented** (Low)
Line 113 in search_repository.dart: getMessageSnippets(id, trimmed) called with empty trimmed when messageOnlyIdList is non-empty — structurally impossible since messagesFuture returns [] for filter-only. Comment at lines 55-57 partially covers the invariant.

**A3 — LIKE scans on unindexed tag columns** (Low/Performance)
Full table scan on moodTags/people/topicTags for filter-only browse. Acceptable at 100-1000 sessions. JSON array storage precludes B-tree indexing anyway. No action needed at current scale.

**A4 — Constant(true) generates WHERE 1 for no-constraint case** (Low/Performance)
Fine at current scale. If pagination added later, push LIMIT into DAO.

## Analysis

The root cause was a three-layer short-circuit: the DAO, repository, and provider each returned early when query was empty, regardless of active filters. The UI also showed the pre-search state in the same condition. The fix is correctly applied at all four sites with the guard condition (query.isEmpty && !filters.hasActiveFilters). The DAO fix differs appropriately — it uses Constant(true) instead of an early return, because the query builder context requires returning an expression rather than short-circuiting the method.

The message search skip for filter-only browse is correct (no keyword to match in message content) and optimized (two async round-trips avoided). The snippet skip (Future.value([])) is the cheapest possible path.

Quality gate 7/7, coverage 81.1%, all tests pass.

---

## Turn 5 — qa-specialist (reflection)
*2026-03-04T21:53:18.779649+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The whitespace-only query with an active filter edge case was identified but not escalated. The guard uses query.trim().isEmpty so it handles it correctly, but no test verifies this boundary explicitly. Also did not check whether searchSessions correctly handles combined AND-logic failure across filter types when data is partially null.

## Candidate Improvement Rule
When a bug fix spans 3+ layers with a consistent guard condition, the QA review must include at least one parameterized test that exercises the boundary value (e.g., whitespace-only query) at the lowest layer (DAO), rather than relying on the guard being obviously correct from reading.

## Confidence Calibration
Original: 0.88, Revised: 0.84, Delta: -0.04

---

## Turn 6 — performance-analyst (reflection)
*2026-03-04T21:53:24.979887+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The msgSnippetFutures loop at search_repository.dart:113 calls getMessageSnippets(id, trimmed) with empty trimmed when messageOnlyIdList is non-empty. I flagged this as A2 but framed it as 'unreachable' without fully tracing whether messagesFuture truly resolves to [] for all code paths when trimmed.isEmpty. Should have verified the structural guarantee, not just asserted it.

## Candidate Improvement Rule
Bug-fix search reviews must enumerate all callers of each modified method and verify guard-condition consistency. When a short-circuit guard is added at multiple layers, explicitly confirm that each upstream caller cannot bypass the guard through a distinct invocation path before marking the fix complete.

## Confidence Calibration
Original: 0.87, Revised: 0.82, Delta: -0.05

---
