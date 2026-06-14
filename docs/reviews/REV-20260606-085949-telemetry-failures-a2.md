---
review_id: REV-20260606-085949
discussion_id: DISC-20260606-085949-review-telemetry-failures-a2
date: 2026-06-06
risk_level: medium
verdict: approve-with-changes
reviewed_files:
  - src/telemetry/failures.py
  - scripts/telemetry/analyze_failures.py
  - scripts/init_db.py
  - tests/test_telemetry.py
panel: [qa-specialist, architecture-consultant, security-specialist, performance-analyst]
blocking_count: 2
advisory_count: 8
speculative_count: 0
---

# Review REV-20260606-085949 — Telemetry Layer A2 (failure signals)

## Verdict: APPROVE-WITH-CHANGES — both blocking findings fixed in-session.

Pre-commit code review of Telemetry Layer A2 (failure/waste signals;
SPEC-20260605-211756, ADR-0020). A2 detects two **grounded** failure classes —
`retry_loop` (unbroken run of identical `(tool, input-hash)` calls) and
`orphaned_subagent` (an `Agent` dispatch with no `tool_result`, or a subagent
transcript that doesn't terminate cleanly) — plus cost-weighted ranking, and
folds A1's carried mtime-watermark perf advisory. The third class (stop-loop) was
deliberately deferred: no reliable transcript signal was found (only a rare
`stop_hook_summary` record and ambiguous `"continue."` user messages), and a
guessed detector would violate the smoke-test-fidelity lesson.

Panel verdicts: qa approve-with-changes (0.87) · architecture approve-with-changes
(0.86, 0 blocking) · security **request-changes** (0.93) · performance
approve-with-changes (0.88, 0 blocking).

## Blocking findings (both FIXED in-session)

**B1 (security) — f-string DDL in `init_db._migrations`.** The ALTER TABLE loop
interpolates DDL identifiers (SQLite can't bind them). All entries are literals
today, but a future config/input-sourced entry would be SQL injection. Carried
from A1's review. **Fix:** extracted module-level `_assert_safe_migration()`
(table∈allowlist, column matches a safe-identifier regex, col_type∈allowlist;
raises ValueError otherwise). Regression test
`test_migration_allowlist_rejects_unsafe_identifier`. Mirror still owed in
`ingest_token_usage._ensure_token_columns` (carried — A1-committed file).

**B2 (security) — missing symlink guard in `_detect_for_session`.** A2 opened
subagent (`agent-*.jsonl`) and main files via its own `iterdir()` loop without the
`itu._is_inside_projects_root` guard that `itu._iter_jsonl_files` applies
everywhere else — a symlink under `<sessionId>/subagents/` could escape
`~/.claude/projects`. New defect introduced in A2. **Fix:** re-check the guard
before opening every file. Regression test
`test_subagent_file_outside_projects_root_is_skipped` (forces the guard False for
`agent-*` paths and asserts the orphan is suppressed — fails under the old code).

## Advisory findings (carried — non-blocking)

- **(architecture, medium) Promote reused `ingest_token_usage` private helpers.**
  `_parse_timestamp`, `_coerce_int`, `_load_discussion_windows`, `DiscussionWindow`
  now have 2+ external consumers (A1 + A2) — the Rule of Three has fired (carried
  from A1). Promote to a documented public surface (rename + alias). **Deferred:**
  touches committed A1 files; do as a focused follow-up so the A2 commit stays
  self-contained.
- **(performance, medium) `_session_mtime` stats every file each run.** ~7800
  `stat()` calls at current corpus before any parse. The safe optimization is
  `os.scandir` (mtime for free); the naive "gate on main-file mtime first"
  variant was **declined** — it could silently skip a session where only a
  subagent file changed (a correctness regression of the watermark guarantee).
- **(performance, low) Cost-path mtime still open.** `ingest_token_usage._collect_messages`
  re-parses the full ~430MB corpus each run; A2's `failures_last_analyzed_mtime`
  is the reference design for a symmetric `tokens_last_analyzed_mtime` (A1 path).
- **(qa, low) `source_tool_use_id` is a dead seam on the real path.** Subagent
  files carry no dispatch back-link, so `runs_by_source` is always empty in
  production; dispatched orphans are always `tier=unknown`. Documented via a code
  comment + `test_analyze_failures_dispatched_orphan_tier_is_unknown`.
- **(qa, low) Added edge-case tests** for empty subagent transcript (→ incomplete),
  interleaved/ping-pong calls (not flagged — documented A2.1 gap), empty detector
  inputs, threshold clamp.
- **(security, low) No per-file size cap in `_iter_records`** — local DoS only
  (hostile JSONL needs an already-compromised machine). Optional hardening.
- **(architecture, info) `_empty_summary`/watermark/init_db-call duplication**
  across the two analyzers — do NOT abstract yet (different watermark semantics);
  extract a shared `_runner` only if a third analyzer appears.
- **(architecture, info) `telemetry_failures` schema is sound** — `UNIQUE(session_id,
  failure_type, signature)` matches the per-session DELETE-then-INSERT idempotency;
  the `CHECK(failure_type IN ...)` forces a deliberate migration when A2.1 adds
  stop-loop.

## Gates
Quality gate **7/7** (60 tests; `failures.py` 98% coverage). Live-proven: template
1 orphan ($0.03), agentic-journal 2 runaway subagents ($11.61 + $10.22, 3.4M/4.5M
tokens) — exactly the expensive failures A2 exists to surface. mtime watermark
proven incremental (36 sessions → 1 on re-run).
