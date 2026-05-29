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
| src/context_sensor.py | statusLine display string contained a non-ASCII char (⚠ U+26A0); the statusLine hook prints to a raw terminal whose codec on Windows is cp1252, which cannot encode it → UnicodeEncodeError crashed the hook (sidecar still written, but the status line died). Surfaced 2026-05-23 during the ADR-0018 build smoke test. Fix: ASCII-only display ("ctx ?", pipe separators, "[wrap-up]"); nudge-text emoji are safe because the guard path emits them via json.dumps (ensure_ascii=True). | Schema/Serialization Drift | 2026-05-23 | tests/test_context_sensor.py | TestProcessStatusline::test_display_is_ascii_encodable |
| scripts/collab_loop.py + scripts/notify.py + scripts/ask_developer.py | ntfy topic slug (the only auth) could leak to the transcript/logs via error handlers that print str(exc): a URLError's str() embeds the full URL incl. the topic. Originating leak: an error handler printed `({topic})` in the agentic_journal project. Fix (ADR-0019): every poll/publish error path prints a source label ("reply"/"main"/"ask") + type(exc).__name__ only — never str(exc), the URL, or the topic; resolve_config raises topic-safe messages (env-var names + validator patterns, never the value). | Trust Boundary Gap | 2026-05-26 | tests/test_collab_loop.py | TestHttpGetNeverPrintsTopic::test_http_error_does_not_print_topic; TestHttpGetNeverPrintsTopic::test_generic_exception_does_not_print_topic; TestResolveConfig::test_error_message_never_contains_topic_value |
| scripts/notify.py | An emoji / non-ASCII char in an ntfy notification Title raises UnicodeEncodeError because ntfy titles ride an HTTP header that urllib encodes as latin-1, crashing the send mid-run. Same class as the src/context_sensor.py statusLine crash (2026-05-23). Fix (ADR-0019): notify.ensure_ascii_title sanitizes the Title header to ASCII (encode('ascii','replace')) at the header-construction point, preserving notify's never-raises contract; collab_loop.ask carries the title in a json.dumps body (ensure_ascii=True), which is latin-1-safe. | Schema/Serialization Drift | 2026-05-26 | tests/test_notify.py | TestEnsureAsciiTitle::test_emoji_title_header_is_latin1_safe |
| scripts/quality_gate.py | Gate-log integrity (C / META-REVIEW-20260528): `_log_outcome` computed `overall = "pass" if passed == total else "fail"`, but `total` is incremented only for checks that actually run (every `--skip-*` branch bumps nothing). So a run that skipped checks but passed the rest was logged as a clean, complete `overall: "pass"` — and the vacuous all-skipped case (`total == 0`, `0 == 0`) also logged `"pass"` despite verifying nothing. The per-check `checks` map recorded `"skipped"` correctly, but the top-level summary lied by omission (Principle #2 — capture must be honest). The 5-min verification-cache path was investigated and exonerated: it lives in `.claude/hooks/pre-commit-gate.sh` and only suppresses the reminder injection — it never writes to the log, so it cannot fabricate a `pass` entry. Fix: extracted pure `_build_outcome_record`; `overall` is `"pass"` only when every check ran and passed, `"pass_with_skips"` when any check was skipped (incl. the vacuous case), `"fail"` when a check that ran failed; added a `skipped_count` field; console summary prints a yellow "(N skipped — not a complete pass)" headline. Exit-code semantics unchanged (`--skip-*` is still an allowed deliberate bypass). | Missing Null/Empty Case | 2026-05-29 | tests/test_quality_gate.py | TestBuildOutcomeRecord::test_skipped_checks_are_not_a_clean_pass; TestBuildOutcomeRecord::test_vacuous_all_skipped_is_not_a_clean_pass; TestBuildOutcomeRecord::test_a_failed_check_overrides_skips |
| scripts/quality_gate.py | The end-of-run console summary for the new `pass_with_skips` path used an em-dash ("N skipped — not a complete pass"). `print()` writes to a raw terminal whose codec on Windows is cp1252, which cannot encode U+2014 → risks UnicodeEncodeError mid-run (rendered as a mojibake "?" when piped). THIRD occurrence of this class (after src/context_sensor.py statusLine 2026-05-23 and scripts/notify.py ntfy-title 2026-05-26) — non-ASCII char in a Windows terminal/header output path. Caught pre-commit by a live smoke test (`--skip-tests`) of the fix in the same session. Fix: extracted the summary into a pure `_format_summary(passed, total, skipped)` helper, replaced the em-dash with an ASCII hyphen, and guarded with a parametrized regression test asserting the summary round-trips through cp1252 + ascii on all four paths. Cross-subsystem pattern (statusLine, ntfy header, gate console) worth a future structural invariant: display/print strings must be ASCII-only. | Schema/Serialization Drift | 2026-05-29 | tests/test_quality_gate.py | TestFormatSummary::test_summary_is_ascii_encodable |

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

