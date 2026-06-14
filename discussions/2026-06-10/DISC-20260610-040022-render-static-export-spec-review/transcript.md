---
discussion_id: DISC-20260610-040022-render-static-export-spec-review
started: 2026-06-10T04:00:33.438134+00:00
ended: 2026-06-10T04:06:40.930303+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260610-040022-render-static-export-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-10T04:00:33.438134+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Phase 5 Unit 5.1 per the rolling handoff + developer directive 2026-06-09 (run Phases 3-5 to completion autonomously): add a --render-static export mode to scripts/telemetry/dashboard_server.py (parent SPEC-20260607-183136 R4/R15/AC12) and retire the legacy one-shot CLI from scripts/telemetry/dashboard.py (arch F5 disposition - no second static entry point; module survives as the read-side loader library).
- **Files/scope**: SPEC-20260610-035920-render-static-export.md; dashboard_server.py CLI + export function; dashboard.py CLI retirement; test migration in tests/test_dashboard_server.py + tests/test_telemetry.py; regression-ledger entry.
- **Developer-stated motivation**: headless/derived instances with no standing-process option need the static artifact (R4); arch F5 dual-entry-point resolution; final unit of the Phases 3-5 directive.
- **Explicit constraints**: NO push; full workflow (/plan -> /build_module -> gate -> /review); single render path R15 with AC12 byte-identical parity test; fix the legacy str(exc) passthrough as part of retirement (REV-20260610-030010 sec note); temp-dir artifact placement (developer decision #6).

---

## Turn 2 — architecture-consultant (critique)
*2026-06-10T04:03:54.012807+00:00 | confidence: 0.88*
*tags: spec-review, architecture*

VERDICT: APPROVE-WITH-CHANGES (0.88). Boundary moves crisp; single render path preserved; door policy (no --out, RenderMode unbuilt) explicit. ADR-0020 layering preserved (transport imports loaders import pure render); ADR-0013 honoured; dead-helper rule (REV-20260607-200447 arch F3) untouched — export routes through assemble_dashboard_data, not _connect_readonly. FINDINGS: (MED, drift) doc-drift sweep named only in Risk, not Acceptance — add AC11: docs/FRAMEWORK_SPECIFICATION.md + docs/CAPTURE_PIPELINE.md contain no remaining 'python scripts/telemetry/dashboard.py' invocation lines; grep smoke check. (LOW) U5 docstring identity: line-1 becomes 'Read-side loader library...'; remove Usage block; point CLI users at dashboard_server.py --render-static / --summary. (LOW) U1 parenthetical: assemble_dashboard_data already imported by the server (retrospective route); only render_dashboard_html may be new — avoid F811 re-add. STRENGTHS: AC2 makes R15 mechanically enforceable; closed-doors section names reopen triggers; sec str(exc) fix bundled into retirement; AC8 hasattr pin scopes retirement to CLI surface only (Principle #8).

---

## Turn 3 — qa-specialist (critique)
*2026-06-10T04:04:07.660693+00:00 | confidence: 0.88*
*tags: spec-review, qa*

VERDICT: APPROVE-WITH-CHANGES (0.88). Migration plan structurally sound; --summary test infra (incl. _schema_snapshot/_row_counts no-mutation pattern) is the model. FINDINGS: F1 (HIGH, weak-assertion) AC2 byte-parity: generated_label is clock-derived independently on each path — spec must pin determinism: monkeypatched assembler IGNORES its generated_label arg and returns the fixed DashboardData (render embeds data.generated_label only), or inject a fixed label; without the explicit pin the test can be flaky. F2 (MED) AC7 wal/shm absence is wrong shape — read-only opens in WAL mode may create/touch sidecars; assert schema+row-counts unchanged (existing pattern) + .db file hash; wal/shm advisory only. F3 (MED) --render-static with --port undefined — add AC6a: accepted-and-ignored, exits 0, no run_server call. F4 (MED) initialized-but-empty DB uncovered — add AC1a: valid HTML with absence tiles, exit 0, 'not yet run' summary lines. F5 (LOW) ledger U7(b) must cite the AC5 sentinel test function + scripts/telemetry/dashboard.py:443 as removed defect site (legacy OperationalError branch was untested). F6 (LOW) AC8 clarify: assert not hasattr(dash,'main'); no __main__ block in source; loader surface remains importable. STRENGTHS: AC2 monkeypatch seam targets the right module-level name; AC9 reuses proven slug-leak regression shape; AC5 negative sentinel assertion catches print(str(exc)) regressions; mutex group stronger than branch precedence.

---

## Turn 4 — security-specialist (critique)
*2026-06-10T04:04:18.189384+00:00 | confidence: 0.88*
*tags: spec-review, security*

VERDICT: APPROVE-WITH-CHANGES (0.88). Narrow surface: local-only, read-only, no-bind, no outbound. Trust boundaries clean (mode=ro; escaping pinned upstream; file:// from constant path; sanitized OperationalError; slug no-leak migrated). FINDINGS: F1 (MED, A05) predictable temp filename on shared machines enables symlink-follow overwrite / co-tenant read — acknowledged trade-off of decision #6 (personal-machine deployment); add explicit Constraints sentence naming the trade-off + re-review trigger (shared-machine deployment => tempfile.NamedTemporaryFile non-predictable path). F2 (LOW, A03 latent) webbrowser.open(out_path.as_uri()) safe ONLY because out_path is a constant temp-dir path — pin the invariant in U2/Constraints: any future --out affordance must re-review this surface. STRENGTHS: str(exc) passthrough closure (REV-20260610-030010 sibling pattern) via code-path collapse; --no-open removes browser from headless env; AC5 sentinel + AC7 no-mutation pin invariants in tests; --out refusal is correct.

---

## Turn 5 — facilitator (synthesis)
*2026-06-10T04:06:40.930303+00:00 | confidence: 0.9*

## Request Context
- **What was requested**: Phase 5 Unit 5.1 (final unit, Phases 3-5 directive 2026-06-09): --render-static export mode on dashboard_server.py + retirement of the legacy one-shot CLI in scripts/telemetry/dashboard.py (arch F5 disposition).
- **Files/scope**: SPEC-20260610-035920-render-static-export.md; dashboard_server.py; dashboard.py; tests x2; regression ledger; live docs (AC11).
- **Developer-stated motivation**: headless/derived instances need the static artifact without a standing process (parent R4); single static entry point.
- **Explicit constraints**: NO push; R15 single render path with AC12 byte parity; fix str(exc) passthrough via retirement; temp-dir artifact (decision #6).

## Synthesis
3 specialists, all APPROVE-WITH-CHANGES at 0.88; 0 BLOCKING. All findings folded into the spec in-session: qa F1 HIGH (AC2 determinism pin: monkeypatched assembler ignores generated_label, render embeds data.generated_label only); qa F2 (AC7 reshaped: schema+row-counts+db-hash, wal/shm not strictly asserted); qa F3 (AC6a: --port accepted-and-ignored, no run_server call); qa F4 (AC1a: initialized-but-empty DB absence tiles); qa F5 (U7 ledger cites AC5 test + dashboard.py:443 defect site); qa F6 (AC8 assertion shape clarified); arch MED (AC11 live-docs drift sweep: FRAMEWORK_SPECIFICATION.md + CAPTURE_PIPELINE.md, grep smoke); arch LOW x2 (U5 docstring line-1 identity; U1 existing-import parenthetical); sec F1 MED (Constraints: fixed-temp-filename symlink trade-off acknowledged, personal-machine scope, shared-machine re-review trigger); sec F2 LOW (U2 webbrowser.open constant-path invariant pin). Spec status -> reviewed. Design ratified: export reuses the exact retrospective render chain; --summary/--render-static argparse mutex; no --out flag (closed door); RenderMode enum not triggered (artifact mode reused, N stays 2). Proceeding to /build_module under the autonomous directive (developer pre-approval per the 2026-06-09 Phases-3-to-5 directive).

---
