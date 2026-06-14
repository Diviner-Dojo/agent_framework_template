---
review_id: REV-20260606-070226
discussion_id: DISC-20260606-070226-review-telemetry-cost-a1
date: 2026-06-06
risk_level: medium
verdict: approve-with-changes
reviewed_files:
  - scripts/init_db.py
  - src/telemetry/__init__.py
  - src/telemetry/pricing.py
  - src/telemetry/cost.py
  - scripts/telemetry/__init__.py
  - scripts/telemetry/analyze_cost.py
  - tests/test_telemetry.py
  - docs/adr/ADR-0020-telemetry-oversight-component.md
  - docs/adr/ADR-0013-token-efficiency-telemetry.md
  - memory/bugs/regression-ledger.md
panel: [qa-specialist, architecture-consultant, security-specialist, performance-analyst]
blocking_count: 1
advisory_count: 11
speculative_count: 0
---

# Review REV-20260606-070226 — Telemetry Layer A1 (per-tier cost)

## Verdict: APPROVE-WITH-CHANGES — the one blocking finding was fixed in-session.

Pre-commit code review of Telemetry Layer A1 (SPEC-20260605-211756, ADR-0020). Prior gates:
spec review (4 specialists, DISC-20260606-041937), Steward APPROVE (0.86), build checkpoint
(architecture 0.91 + security 0.93, DISC-20260606-063822). Panel verdicts here:
qa-specialist 0.87, architecture-consultant 0.88, security-specialist 0.92,
performance-analyst 0.91.

## Required changes (blocking) — RESOLVED

1. **Watermark same-timestamp silent-skip** (qa-specialist, verified). `_target_discussion_ids`
   used a strict `closed_at > watermark` test. Two discussions can share an exact `closed_at`,
   so a *new* discussion closing at the watermark instant set by a prior run would be silently
   skipped forever (recoverable only via `--full-rescan`).
   **Fix applied:** added `_analyzed_discussion_ids` + a not-yet-analyzed backstop (a closed
   discussion with no breakdown rows is always a target) and a regression test
   (`test_target_selection_includes_unanalyzed_discussion_at_watermark`). 28 tests pass,
   quality gate 7/7.

## Recommended improvements (advisory — carried, non-blocking)

- **(performance, notable)** The watermark gates re-*writing*, not re-*reading*:
  `_collect_messages` parses the full ~430 MB transcript corpus every run. Cheapest fix is a
  session-file **mtime watermark** (stat-and-skip). Carry to Layer A2 or a follow-up — at
  current scale (~5–20 s) it is acceptable; at 10× it becomes the dominant cost.
- **(architecture)** `analyze_cost` reuses four *private* `ingest_token_usage` helpers
  (`_parse_timestamp`, `_attribute`, `_collect_messages`, `_load_discussion_windows`).
  Acceptable now (Rule of Three: two in-tree, co-owned consumers). Cheap guard: a contract
  test asserting the symbols/signatures; promote to public on a third consumer.
- **(security)** Pre-existing f-string DDL in `init_db._migrations` — safe today (hardcoded
  literals; SQLite forbids `?` in DDL identifiers). Add an allowlist assertion as
  future-proofing.
- **(security)** `pyyaml >= 6.0` not exact-pinned (REVIEW.md Rule 20). Pre-existing; the
  project pins all deps with `>=`. Revisit project-wide (or via a lockfile).
- **(qa)** Add tests for adjacent-window attribution, two-discussion per-model granularity,
  and `coverage_pct` rounding (non-round ratios).
- **(architecture)** `init_db` prints "Database initialized at…" on the already-exists path
  when called from `analyze_cost` — cosmetic; suppress for clean `--dry-run` output.

## Tightened in-session
- qa weak-assertion advisory fixed: `test_analyze_unknown_model_marked_not_dropped` now
  asserts `coverage_pct ≈ 90.0` (was `< 100.0`).

## Speculative findings (confidence < 0.80)
None.

## Strengths
- Clean pure (`src/telemetry`) / transport (`scripts/telemetry`) boundary; correct
  dependency direction.
- Honest `UNKNOWN_TIER` sentinel end-to-end — unknown tiers are never zero-rated; coverage %
  is token-weighted.
- Parameterized SQL throughout; path-traversal guard reused (not reimplemented); `yaml.safe_load`
  with layered defensive degradation; SQL-injection regression test asserts stored value.
- Compute-don't-store verified (no dollar persisted). ADR provenance hygiene praised
  (ratify ADR-0013 before amending).
- Live smoke test proves the transport path end-to-end ($666.26 over 270.2M tokens, 100% coverage).

## Education gate
Recommended at **understand/apply** Bloom levels (medium risk, new module): `/walkthrough`
on `src/telemetry/cost.py` + `scripts/telemetry/analyze_cost.py` (the coverage-honesty and
watermark logic are the load-bearing concepts), then `/quiz`. Not blocking for commit.
