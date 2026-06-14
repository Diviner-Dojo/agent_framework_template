---
discussion_id: DISC-20260607-193135-build-telemetry-layer-b-dashboard-server-phase1
started: 2026-06-07T19:31:56.386745+00:00
ended: 2026-06-07T20:00:35.088329+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 8
---

# Discussion: DISC-20260607-193135-build-telemetry-layer-b-dashboard-server-phase1

## Turn 1 — facilitator (evidence)
*2026-06-07T19:31:56.386745+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Run /build_module Phase 1 of SPEC-20260607-183136 (live dashboard daemon), per the session 8 handoff (docs/handoff/HANDOFF-20260607-191616.md). Per-phase loop: build -> quality gate -> /review -> fix blocking -> commit on fix/c-gate-log-integrity (NO push, NO auto-merge) -> ntfy milestone via collab_loop say.
- **Files/scope**: NEW scripts/telemetry/dashboard_server.py (FastAPI app, 127.0.0.1 bind, htmx endpoints); NEW src/telemetry/live.py (pure event-fold LiveState); extend src/telemetry/dashboard.py with live-panel helpers; NEW src/telemetry/static/ (vendored htmx + Chart.js, pinned); A-ARCH1 promotion in scripts/ingest_token_usage.py (public _collect_messages/_parse_since/_is_inside_projects_root + 3 call-site updates); tests + ADR-0020 Layer B amendment.
- **Developer-stated motivation**: The shipped static Layer B dashboard categorically cannot show live agent lanes / context runway / per-turn cost (form-factor gap; see ANALYSIS-20260607-rh-oversight-deepdive.md). The Telemetry & Oversight north star is a live dashboard for understanding AI use; A1/A2/A3 are the data foundation. Steward APPROVE 0.86 overturns DISC-20260607-063709's no-standing-process constraint with 9 binding conditions (= AC1-AC9).
- **Explicit constraints**: NEVER auto-inject telemetry into agent prompts (no-inject standing regression guard); NO push to any remote; NO auto-merge; Phase 1 must carry all 9 Steward conditions; AC15 R16 A-ARCH1 promotion is a Phase 1 prerequisite (daemon = 4th consumer, Rule of Three crossed); HTMX polling NOT SSE in Phase 1 (TestClient compatibility); 127.0.0.1 hardcoded literal, NO --host flag, NO HOST env read, runtime guard before uvicorn.run(); CORS same-origin only + Host header validation (DNS-rebinding); html.escape for HTML contexts but json.dumps + </script>-guard for data in <script> blocks; vendored frontend assets (NO CDN); read-only DB connection (file:...?mode=ro); live.py pure (no scripts.* imports, no transcript-IO); generic errors (no DB-path/exception class leakage); no outbound HTTP client; ASCII-safe in console paths (cp1252 guard, 5th class instance); Ross's repo is MIT but DO NOT copy verbatim JS or reuse Ross's fixtures (contamination guard); stop-by-exception via ntfy ask for genuine forks.

---

## Turn 2 — facilitator (proposal)
*2026-06-07T19:32:11.174633+00:00 | confidence: 0.8*
*tags: build-plan*

Build plan: 6 tasks for Phase 1 (live core).
1. Vendor static assets: pin + drop htmx (1.9.x) + Chart.js (4.4.x) into src/telemetry/static/ (R11a, AC6). No CDN; the daemon serves them locally.
2. A-ARCH1 promotion (R16/AC15, Phase 1 prerequisite): rename _collect_messages -> collect_messages, _parse_since -> parse_since, _is_inside_projects_root -> is_inside_projects_root in scripts/ingest_token_usage.py + ADD back-compat private aliases (kept-as-test-asserted; per the rule, public-only promotion). Update 3 call sites: analyze_cost.py, analyze_failures.py, analyze_value.py.
3. NEW src/telemetry/live.py (R14/AC14): pure event-fold model. LiveEvent (already parsed by transport) + LiveState (agent lanes, context runway, per-turn cost). No scripts.* imports, no transcript-IO. Checkpoint: architecture + qa.
4. Extend src/telemetry/dashboard.py with live-panel render helpers (agent-lane panel, runway gauge panel, live cost/failure stream panel). Reuse _esc / _fmt_usd / _fmt_int / _absence_tile. Pure.
5. NEW scripts/telemetry/dashboard_server.py: FastAPI app. Hardcoded host=127.0.0.1 literal + runtime guard before uvicorn.run(); NO --host flag; NO HOST env read; CORSMiddleware same-origin only; Host-header middleware (400 on mismatch); static mount; routes: GET / (htmx shell), GET /fragments/cost, /fragments/failures, /fragments/value (retrospective); GET /fragments/live-state (live, htmx polled at server-specified intervals); lifespan teardown; generic errors. Checkpoint: security + architecture.
6. Tests covering AC1-AC10/AC14/AC15/AC16/AC17: source-grep no SessionStart/hook/auto-launch ref, Config.host inspection + source-grep 0.0.0.0 absence + Host:evil 400, two-layer no-inject (module-allowlist + byte-unchanged hooks/settings), read-only DB schema/row-counts unchanged + lifespan teardown, html.escape per field + </script>-injection test + 500 generic body, port-in-use clear message, A-ARCH1 contract test (4 helpers public).

Phase 2-5 deferred (per spec internal phasing): time-series, failure intelligence, self-monitoring, --render-static export (AC11/AC12 also deferred to a later phase that authors the live fixture inventory).
After Phase 1 build: quality gate -> /review -> fix blocking -> commit (NO push) -> ntfy milestone.

---

## Turn 3 — architecture-consultant (critique)
*2026-06-07T19:41:23.322730+00:00 | confidence: 0.88*
*tags: checkpoint, task-3*

Checkpoint task 3 (src/telemetry/live.py) — APPROVE 0.88. Fold algebra sound, R14/AC14 purity held. 3 findings: F1 (Low) _price_message coerces None to 0.0 - 'uncosted ≠ $0' honesty inconsistent with cost.py (CostReport keeps cost_usd=None for unknown tier); recommend uncosted_turns counter; F2 (Low) _estimate_turns_remaining uses session-wide rolling avg (mixes haiku subagent rate with main-Opus runway); scope to main lane only; F3 (Info) unknown kind silently dropped — forward-compat OK; optional unknown_events counter. Strengths: tuple-of-lanes + replace() snapshot-safe, mark_orphans externalizes session-end decision cleanly, runway thresholds parameterized.

---

## Turn 4 — qa-specialist (critique)
*2026-06-07T19:41:30.355855+00:00 | confidence: 0.92*
*tags: checkpoint, task-3*

Checkpoint task 3 (src/telemetry/live.py) — REVISE 0.92. Module is structurally sound and pure; 0% test coverage will fail the 80% gate. 12 findings: F1 (High) no test file — fold_events/apply_event/mark_orphans/_apply_*/handlers all uncovered; F2-F6 (High) edge cases per testing_requirements: empty events list, model=None (uncosted-turn token-vs-cost separation), est_turns_remaining cold-start None, duplicate dispatch idempotence, result-with-unknown-ref-id and duplicate-result no-ops; F7-F8 (Medium) boundary values: runway threshold inclusive boundaries (55.0/0.55=amber, 70.0/0.70=red), context_window=0 safe, RECENT_EVENTS_CAP exact-cap (101 events → 100 entries); F9 (Medium) unknown event kind no-op (forward-compat); F10 (Medium) mark_orphans triplet: no-agents, all-complete, mixed; F11 (Medium) ordering: message-before-dispatch then dispatch idempotence; F12 (Low) purity-seam test (AC14): assert no scripts.* in sys.modules after importing live. Recommendations: reuse pricing fixture from test_telemetry.py; tests can live in test_telemetry.py given the file already covers telemetry.

---

## Turn 5 — qa-specialist (critique)
*2026-06-07T19:48:20.938387+00:00 | confidence: 0.9*
*tags: checkpoint, task-3, round-2*

Checkpoint task 3 ROUND 2 — APPROVE 0.90. 28 tests added covering F1-F12 plus arch F2 verification (uses_main_lane_only). One Low advisory: F3 missing subagent-lane variant of unknown-tier uncosted path. FOLDED (test_subagent_lane_with_unknown_tier_model_is_uncosted added). LiveCostEvent.detail-always-empty deferred to transport-layer cycle (developer can log as known gap).

---

## Turn 6 — security-specialist (critique)
*2026-06-07T19:54:23.583370+00:00 | confidence: 0.91*
*tags: checkpoint, task-5*

Checkpoint task 5 (scripts/telemetry/dashboard_server.py) — APPROVE 0.91. Bind invariant enforced at two layers (CLI absence of --host + run_server runtime assertion before uvicorn.Config). HostHeaderGuard added second = outermost in Starlette reverse-order; CORS same-origin only. _esc/html.escape at every dynamic interpolation; AC6 holds. Generic error bodies (no DB path / exception class). _safe_text + is_inside_projects_root guards on every file walk. AC8 structural (no HTTP client imported); read-only mode=ro at driver level (AC5). 2 findings: F1 (Low UX) webbrowser.open before run_server can race; not exploitable, just blank tab on slow start; recommendation: move into lifespan startup or signal-ready; F2 (Info) portless 127.0.0.1 entry in _allowed_hosts handles curl/tooling, document why.

---

## Turn 7 — architecture-consultant (critique)
*2026-06-07T19:54:30.075106+00:00 | confidence: 0.86*
*tags: checkpoint, task-5*

Checkpoint task 5 (scripts/telemetry/dashboard_server.py) — APPROVE 0.86. R14 purity preserved (live.py imports nothing transport-side); R15 single render path honored (/fragments/retrospective reuses assemble_dashboard_data + render_dashboard_html verbatim); R16/AC15 A-ARCH1 helpers used at parse seam (discover_session_dirs, is_inside_projects_root, parse_timestamp, coerce_int). create_app is pure constructor / run_server is the only binder = clean test seam. Lazy per-request fold = right Phase 1 shape. Route shape extends to Phase 2 (/fragments/series/*) + Phase 5 (--render-static) without refactor. 2 findings: F1 (Low coupling) mark_orphans(state) if not state.agents else state has INVERTED condition (mark_orphans only does work when there ARE agents; idempotent so harmless today); FOLDED — removed call entirely with comment explaining why lazy fold without session-end signal must not mark orphans (Phase 2 will reintroduce); F2 (Info pattern-consistency) _safe_text/_parse_main_session/_parse_subagent overlap with itu.collect_messages — defensible (live needs per-line event projection, not aggregated turn rows) — comment cross-reference advisable.

---

## Turn 8 — facilitator (synthesis)
*2026-06-07T20:00:35.088329+00:00 | confidence: 0.8*
*tags: build-summary, blocking:0, advisory:0*

Build Phase 1 complete: 6 tasks, 2 checkpoints fired (task 3 live.py: arch APPROVE 0.88 + qa REVISE 0.92 -> APPROVE 0.90 R2; task 5 dashboard_server.py: security APPROVE 0.91 + arch APPROVE 0.86), 0 unresolved concerns. Findings folded: arch F1 (uncosted-turns accounting), arch F2 (main-lane-only runway), arch F1-task5 (inverted mark_orphans removed), qa F1-F12 + sub-variant. Files: NEW src/telemetry/live.py (~600 lines pure fold) + NEW scripts/telemetry/dashboard_server.py (~470 lines FastAPI transport) + NEW src/telemetry/static/htmx.min.js (vendored 48KB pinned 1.9.12, SRI sha384 recorded) + extended src/telemetry/dashboard.py (+200 lines live-panel renderers) + A-ARCH1 rename in scripts/ingest_token_usage.py + 5 call-site updates (analyze_cost, analyze_failures, analyze_value, 2 test files) + NEW tests/test_dashboard_server.py (30 invariant tests AC1-AC10/AC14/AC15/AC16/AC17) + 29 new tests in tests/test_telemetry.py + ADR-0020 Layer B amendment + 4 regression-ledger entries. 229 tests pass.

---
