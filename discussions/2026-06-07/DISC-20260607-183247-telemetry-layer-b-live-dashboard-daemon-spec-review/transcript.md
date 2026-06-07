---
discussion_id: DISC-20260607-183247-telemetry-layer-b-live-dashboard-daemon-spec-review
started: 2026-06-07T18:32:58.245943+00:00
ended: 2026-06-07T18:39:44.581090+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260607-183247-telemetry-layer-b-live-dashboard-daemon-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-07T18:32:58.245943+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Plan the Layer B telemetry dashboard REDESIGN — replace the shipped static HTML with a live, localhost-only, user-launched persistent daemon (htmx + vanilla JS + Chart.js, no build step). Phase the build internally; one spec, commit per phase.
- **Files/scope**: NEW scripts/telemetry/dashboard_server.py + src/telemetry/live.py; extend src/telemetry/dashboard.py; tests; ADR-0020 amendment. Spec: SPEC-20260607-183136.
- **Developer-stated motivation**: The live dashboard is the LOCKED north star for understanding AI use; the static snapshot has a structural gap vs a live view (analysis ANALYSIS-20260607-rh-oversight-deepdive). Developer chose the ambitious daemon path.
- **Explicit constraints**: Steward APPROVED form factor (0.86) with 9 BINDING conditions: explicit-launch-only (no hook/auto-launch); hard 127.0.0.1 literal bind; display-parity only + @regression no-inject guard; render R-B2 retrospective views from DB; read-only DB + compute-don't-store (no dollar column); html.escape every field + pinned CDN; zero idle overhead + teardown; no outbound surface; ADR-0020 amendment. Also: --render-static export mode for headless/derived (Fork B); read-side functions ONLY (never analyze_cost/analyze_failures/init_db); original Python (no verbatim Ross JS/fixtures).

---

## Turn 2 — security-specialist (critique)
*2026-06-07T18:36:34.055271+00:00 | confidence: 0.91*
*tags: security, blocking, xss, bind, spec-review*

VERDICT: REQUEST-CHANGES (0.91). Threat model = single-user localhost read-only viewer; 9 Steward conditions map well to attack surface.
[BLOCKING F1] R8/AC2 bind: 'host=127.0.0.1 literal' insufficient — uvicorn also reads --host CLI + HOST env; a --host flag would let a derived project bind 0.0.0.0 (no auth). Require: (1) NO --host/-H CLI flag; (2) runtime assert host=='127.0.0.1' before uvicorn.run (fail-fast, not just a test); (3) AC2 test mocks uvicorn.run + asserts host kwarg AND startup guard fires on non-loopback.
[BLOCKING F2] R11/AC6 XSS: html.escape is WRONG for data baked as JSON literal in <script> blocks — browser hands raw bytes to JS engine; '</script>' in a failure signature closes the block and injects JS. Require json.dumps() + </script> guard (replace '</' with '<\/' or \u003c) for all script-block data; add a test injecting '</script>' into chart data asserting no literal </script> in output. (html.escape stays correct for HTML attr/text contexts.)
[ADVISORY F3] CDN integrity: pinned version lacks SRI; prefer VENDORING Chart.js/htmx into src/telemetry/static/ + serve from FastAPI (also strengthens R13 no-outbound), else require integrity= SRI hashes. Strongest advisory — resolve before Phase 1 ships.
[ADVISORY F4] localhost CSRF/DNS-rebinding: add CORSMiddleware same-origin only (no wildcard) + validate Host header == 127.0.0.1:<port> (400 otherwise); test rejects Host: evil.example.com.
[ADVISORY F5] SSE DoS: cap concurrent SSE connections (default 5 -> 503); polling interval server-specified not client query-param.
Strengths: mode=ro is driver-level-correct; no-inject @regression guard (AC3) is the highest-value test; schema-test for no-dollar-column is mechanical; generic-errors required; contamination guard correctly scoped.

---

## Turn 3 — architecture-consultant (critique)
*2026-06-07T18:36:34.520480+00:00 | confidence: 0.82*
*tags: architecture, blocking, seam, a-arch1, spec-review*

VERDICT: APPROVE-WITH-CHANGES (0.82). Compute-don't-store holds; read-side-functions-only holds; form-factor reversal recorded via ADR amend (Principle #5). Pure/transport cut is the right boundary — live STATE is a pure events->LiveState fold even though the SERVER is stateful (statefulness lives only in transport process memory). Dependency direction correct (src/ never imports scripts/).
[BLOCKING F1] live.py purity seam asserted but not specified: temptation in build is to let live.py import the transcript parser directly, inverting dependency direction + pulling scripts IO into src/. Require: live.py consumes already-parsed event structs (a LiveEvent dataclass list) produced by the server transport; imports no transcript-IO, no scripts.* module; a test asserts src.telemetry.live has no 'scripts' import. (Live analogue of the DashboardData seam.)
[BLOCKING F2] --render-static (Fork B) risks a divergent 2nd renderer: AC12 shares read-side DATA but not the RENDER path. Over 5 phases the static export silently diverges from the live view. Require: htmx live fragments + --render-static doc compose from the SAME src/telemetry/dashboard.py panel/section render helpers, differing only in shell (full doc vs fragment+polling wrapper); AC12 test asserts static export & live retrospective render byte-identical panel bodies for the same DashboardData.
[ADVISORY F3] A-ARCH1: fold the transcript-parsing public-surface promotion HERE. _collect_messages/discover_session_dirs/_parse_since/_is_inside_projects_root are underscore-private but imported cross-module by analyze_cost/failures/value (3 consumers); the daemon is the 4th in a STANDING server (sanctions the bad pattern). Rule-of-Three crossed; ~20 min: drop underscores + re-export + update call sites. Do NOT over-engineer into a new transcript_parser module/class (flat function promotion only). Verify at build that the daemon reuses the same parsing (vs a distinct live-tail) before committing the promotion.
[ADVISORY F4] Phase 1 'independently shippable' true for value; ensure htmx shell uses named slots/fragments (one per future panel) so Phases 2-4 are additive — build-checkpoint note.
[ADVISORY F5] disposition of existing scripts/telemetry/dashboard.py (one-shot static): retire into --render-static mode or clearly keep as Fork-B entry — avoid two static entry points; make explicit in Affected Components.
Strengths: right boundary not reflexive; defense-in-depth matches existing seam (no new pattern); resisted over-arch traps (no telemetry.db fork, no WebSocket-everything — htmx polling is least-complex).

---

## Turn 4 — qa-specialist (critique)
*2026-06-07T18:36:48.459420+00:00 | confidence: 0.82*
*tags: qa, blocking, testability, fixtures, spec-review*

VERDICT: REQUEST-CHANGES (0.82). Inherits strong test culture (fixture-transcript helpers, _schema_snapshot, _populate_dashboard_db, @regression markers, honest-absence tests) — reusable. Gaps are in net-new territory: the FastAPI server, live.py, and async test strategy. ACs name invariants but not HOW to test them deterministically.
[BLOCKING F1] AC2 bind test: a REAL non-loopback bind is OS-permission-dependent + flaky/CI-unfriendly. Implement via uvicorn.Config inspection (assert config.host=='127.0.0.1') + a source grep that '0.0.0.0' absent + a TestClient 127.0.0.1 positive path. Spec must state a live non-loopback bind test is NOT the AC2 impl.
[BLOCKING F2] AC3 no-inject guard risks being tautological if it only spies known function names. Two layers: (a) STATIC — import server module, assert it does not import hooks/settings/prompt-assembly modules (module-name allowlist); (b) BEHAVIORAL — call every endpoint via TestClient against a tmp_path copy of .claude/hooks/ + settings.json, diff before/after = no writes. Behavioral layer is what bites new vectors. Both @regression.
[BLOCKING F3] live.py has NO test strategy + AC11 fixture inventory unspecified (and contamination guard forbids reusing Ross fixtures -> must author new). Specify minimum fixtures before build: active-session-with-orphaned-subagent; context 75% (amber); context 91% (red); partial/truncated last line. Extend the existing A2 line factory (_assistant_line/_subagent_line) rather than static JSON. Defer amber/red only if the runway gauge is explicitly deferred past Phase 1.
[ADVISORY F4] AC7 port-in-use: test that a pre-bound port yields a clear human message (not a raw [Errno 98] trace) / no hang. @regression.
[ADVISORY F5] async strategy: existing suite is synchronous, no anyio configured. LOCK Phase 1 to htmx POLLING (not SSE) to keep TestClient usable (SSE hangs TestClient); else add pytest-anyio + AsyncClient. Add conftest TestClient fixture w/ tmp_path DB monkeypatched into DB_PATH.
[ADVISORY F6] AC5 teardown 'persists nothing': test FastAPI lifespan __exit__ then assert no new files in tmp_path + live singleton reset/empty; trivial if live.py purely functional.
[ADVISORY F7] AC6 error-leak: patch assemble_dashboard_data to raise sqlite3.OperationalError, assert 500 + body lacks DB path + lacks 'OperationalError'.
[ADVISORY F8] AC12 'parity' not byte-identical-testable (different render path) — assert DashboardData field-for-field equality between both paths on same fixture DB (the meaningful proxy). [reconcile w/ arch F2 which wants byte-identical PANEL bodies — both: same panel helpers => panel bodies identical, full-doc shell differs.]
[ADVISORY F9] AC11 partial-line: live reader processes files being actively appended; test truncated last JSONL line skipped gracefully (extends test_corrupt_jsonl_line_skipped) — only if tailing vs whole-file read; make that explicit.
Strengths: existing regression discipline exemplary; _schema_snapshot+_table_row_counts dual-invariant; mature fabricated-zero awareness; AC1 grep is the right tool.

---

## Turn 5 — facilitator (synthesis)
*2026-06-07T18:39:44.581090+00:00 | confidence: 0.85*

## Request Context
- **What was requested**: Plan the Layer B telemetry dashboard REDESIGN — static HTML -> live, localhost-only, user-launched FastAPI daemon (htmx + vanilla JS + Chart.js, no build step). One spec, phased build, commit per phase.
- **Files/scope**: NEW scripts/telemetry/dashboard_server.py + src/telemetry/live.py + src/telemetry/static/; extend src/telemetry/dashboard.py; tests; ADR-0020 amendment. Spec SPEC-20260607-183136.
- **Developer-stated motivation**: live dashboard is the LOCKED north star; static snapshot has a structural gap vs live monitoring (ANALYSIS-20260607-rh-oversight-deepdive).
- **Explicit constraints**: Steward APPROVED form factor 0.86 w/ 9 binding conditions; display-parity only (never auto-inject); read-side DB only; original Python (no Ross JS/fixtures); --render-static for headless/derived (Fork B).

## Synthesis
Panel: security REQUEST-CHANGES (0.91), architecture APPROVE-WITH-CHANGES (0.82), qa REQUEST-CHANGES (0.82). No architectural redesign — all findings are spec-amendment-level. 7 BLOCKING findings folded into the spec before status->reviewed:
- SEC-F1 (bind): no --host flag / no HOST env + runtime fail-fast guard + Config-inspection test (R8/AC2).
- SEC-F2 (XSS): json.dumps + </script> guard for script-block data (html.escape is wrong there) + injection test (R11/AC6).
- ARCH-F1: live.py purity seam — consumes pre-parsed LiveEvent list, no scripts.* import, test asserts (R14/AC14).
- ARCH-F2: single render path — htmx fragments + --render-static share the SAME panel helpers; byte-identical panel-body test (R15/AC12).
- QA-F1: AC2 via Config inspection + source grep, NOT a flaky live non-loopback bind.
- QA-F2: AC3 two-layer no-inject guard (static import-graph check + behavioral file-diff of hooks/settings) — defeats tautology.
- QA-F3: authored fixture-transcript inventory (orphan / amber 75% / red 91% / truncated line); extend A2 factory (AC11).
Strong advisories also folded: vendor Chart.js+htmx locally (kills CDN/SRI + outbound surface, SEC-F3 -> R11a); CORSMiddleware + Host-header 400 (SEC-F4 -> R8a); fold A-ARCH1 public-surface promotion here as the 4th consumer (ARCH-F3 -> R16/AC15); lock Phase 1 to htmx polling not SSE (QA-F5 -> R2); SSE cap deferred (SEC-F5); error-leak test (QA-F7 -> AC6); port-in-use message (QA-F4 -> AC16); retire old static script into --render-static (ARCH-F5). Open advisory for build-time verification: confirm the daemon reuses batch transcript parsing before committing the A-ARCH1 promotion (else log skip). Spec now status: reviewed; ready for developer approval (Principle #7) then /build_module Phase 1.

---
