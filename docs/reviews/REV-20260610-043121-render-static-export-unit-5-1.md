---
review_id: REV-20260610-043121
discussion_id: DISC-20260610-042334-review-render-static-export
pr_id: ""
risk_level: medium
collaboration_mode: structured-dialogue
exploration_intensity: medium
agents_activated: [qa-specialist, architecture-consultant, security-specialist, ux-evaluator]
reviewed_files:
  - scripts/telemetry/dashboard_server.py
  - scripts/telemetry/dashboard.py
  - tests/test_dashboard_server.py
  - tests/test_telemetry.py
  - memory/bugs/regression-ledger.md
  - docs/adr/ADR-0020-telemetry-oversight-component.md
  - docs/sprints/SPEC-20260610-035920-render-static-export.md
rounds: 1
consensus_reached: true
verdict: approve
confidence: 0.91
review_duration_minutes: 8
---

## Summary

Phase 5 Unit 5.1 — the FINAL unit of the telemetry Layer B dashboard backlog: a
`--render-static` one-shot export mode on `dashboard_server.py` (writes the
retrospective dashboard HTML to the OS temp dir via the EXACT render chain the live
retrospective route uses — parent R15, pinned byte-for-byte by the AC12 parity test)
plus retirement of the legacy one-shot CLI from `scripts/telemetry/dashboard.py`
(now a read-side loader library with a signpost-only `__main__`). 0 blocking findings;
all 6 verified advisories folded in-session; 1 discarded as already-covered.

## Request Context

- **What was requested**: Pre-commit multi-agent review of Unit 5.1 per the autonomous
  Phases 3–5 directive: `--render-static` export + legacy CLI retirement
  (SPEC-20260610-035920, status complete; build DISC-20260610-040717 sealed).
- **Files/scope**: see `reviewed_files`.
- **Developer-stated motivation**: headless/derived instances need the static artifact
  without a standing process (parent R4); no second static entry point (arch F5);
  close the legacy `str(exc)` raw-error door.
- **Explicit constraints**: R15 single render path (AC12 byte parity); never `str(exc)`
  in CLI error copy; constant temp-dir artifact path (no `--out`, closed door); NO push.

## Findings by Specialist

### QA Specialist (0.88, APPROVE-WITH-CHANGES → folded)
- **F1 MED (verified, FOLDED)**: `export_static_dashboard` caught only
  `sqlite3.OperationalError` — a `PermissionError` on the artifact write propagated as a
  raw traceback. Fold: `except OSError` with sanitized path-only copy + regression test
  `test_export_static_write_failure_prints_sanitized_message` (sentinel never printed).
- **F2 LOW (verified, FOLDED)**: AC1 asserted only the `Dashboard:` prefix, not the path
  value. Fold: `assert str(out_file) in out` pin.
- **F3 LOW (verified, FOLDED)**: the `main()`-level browser gate on export failure was
  unverified. Fold: `test_main_render_static_operational_error_skips_browser`.
- Strengths: byte-parity test correctly designed (determinism pin, full-string diff);
  sentinel negative assertions meaningful; db-hash pin catches WAL side-effects.

### Architecture Consultant (0.91, APPROVE-WITH-CHANGES → folded)
- **F1 MED (verified, FOLDED)**: ADR-0020:216 still named the retired module as "the
  transport ... holds main". Fold: in-place factual edit (decision unchanged — the CLI
  moved to `dashboard_server.py`; loader-library identity named; SPEC referenced).
- Verified: layering direction holds (transport → loaders → pure render);
  `DASHBOARD_FILENAME` with its sole consumer + provenance comment; signpost `__main__`
  is a signpost, not a second entry point (structurally pinned); RenderMode-enum
  watchpoint VERIFIED CLOSED (export reuses the artifact renderer mode; trigger
  preserved); AC11 live-docs sweep clean; both closed doors recorded with re-review
  triggers in spec + ledger.

### Security Specialist (0.93, APPROVE)
- All 7 checklist items PASS: no `str(exc)`/repr anywhere on the new paths; error
  returns precede the write; browser gated on non-None; NTFY_TOPIC no-leak migrated
  intact (stdout+stderr); no new bind/outbound surface; signpost prints a static
  literal only; CSP/host-guard paths untouched; read-only invariant pinned
  (schema + rows + sha256, WAL sidecars correctly excluded).
- 1 LOW (DISCARDED — already covered, see appendix).

### UX Evaluator (0.91, APPROVE-WITH-CHANGES → folded)
- **F1 MED (verified, FOLDED)**: argparse description still framed the script as only a
  "live ... daemon". Fold: description now names all three modes (server / `--summary` /
  `--render-static`) before the bind invariant.
- **F2 LOW (verified, FOLDED)**: export error paths lacked an explicit closing signal.
  Fold: "No export was produced." on all three error paths.
- Verified: signpost copy clean; `Dashboard: <path>` keyed on the single `output_path`
  source of truth (copy never references an artifact not produced); `--no-open`
  cross-mode applicability documented; `--port` accepted-and-ignored is right for alias
  users; no HTML surface changed (WCAG scope nil).

## Speculative Findings — Lower Confidence

None (0 findings below 0.80 confidence; 0 unscored).

## Discarded Findings (verification appendix)

- **sec LOW (A05 coverage)**: requested a test distinguishing `exists()==True` +
  `OperationalError` from `exists()==False`. Facilitator verification: the AC5 direct
  test already uses `_empty_db` (file exists) with a raising assembler, so the
  distinction was already exercised; the missing-DB CLI test covers the other branch.
  Specialist reasoning preserved per the conservative-discard policy.

## Verdict

**APPROVE** (post-fold). Weighted confidence ~0.91. 0 blocking / 7 advisory
(6 folded in-session, 1 discarded as already-covered). Post-fold verification:
414 tests pass across the two test files; quality gate 7/7; regression ledger 48
guards (Unit 5.1 entry names both closed doors + re-review triggers).

## Model Tiers

qa-specialist:default · architecture-consultant:default · security-specialist:default ·
ux-evaluator:default (`--cost medium`).

## Education Gate

**Recommended** — joins the deferred Phase 3.x/4.x education cohort for the next
interactive session. Walkthrough scope (Bloom's: Understand→Analyze): (1) why the
byte-parity test makes R15 mechanically enforceable; (2) the retirement-signpost
pattern (loud redirect vs silent no-op vs hard removal); (3) the two closed doors
(`--out`, RenderMode enum) and what would legitimately reopen them.
