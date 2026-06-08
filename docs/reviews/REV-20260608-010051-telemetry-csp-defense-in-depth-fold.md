---
review_id: REV-20260608-010051
discussion_id: DISC-20260608-005313-csp-defense-in-depth-fold-security-f2
pr_id: ""
risk_level: low
collaboration_mode: ensemble
exploration_intensity: low
agents_activated: [qa-specialist, security-specialist]
reviewed_files:
  - scripts/telemetry/dashboard_server.py
  - tests/test_dashboard_server.py
  - memory/bugs/regression-ledger.md
rounds: 1
consensus_reached: true
verdict: approve-with-changes
confidence: 0.90
review_duration_minutes: 8
---

## Request Context
- **What was requested**: Close security F2 (LOW observation) from REV-20260607-200447 — add a defense-in-depth Content-Security-Policy header to the Telemetry Layer B live dashboard daemon, with the advisory's documented policy value (`default-src 'self'; script-src 'self'; style-src 'unsafe-inline'`).
- **Files/scope**: scripts/telemetry/dashboard_server.py (added ContentSecurityPolicyMiddleware + CONTENT_SECURITY_POLICY constant, registered last so outermost); tests/test_dashboard_server.py (regression tests covering policy-string pin + 200 shell + 400 host-rejection + 500/503 fragment error paths + middleware-position); memory/bugs/regression-ledger.md (+1 entry, now 33 guards).
- **Developer-stated motivation**: REV-20260607-200447 burndown — 3 advisories remain after this session (qa F1 + arch F2 + security F2). The handoff identified security F2 as a small, well-bounded single unit suitable for a supervised session.
- **Explicit constraints**: NO push. /review must run before commit. Quality gate must pass. Capture never skipped. Use the policy value documented in the advisory verbatim. Operate within the autonomous execution authorization scope (feature branch fix/c-gate-log-integrity only).

## Summary

Both specialists APPROVE-WITH-CHANGES (consensus, ensemble mode). 0 BLOCKING findings. Implementation is structurally sound: policy correctly omits `'unsafe-inline'` from `script-src` (the load-bearing clause); middleware is verified outermost by index + by identity; error paths (400/500/503) all carry the header. **4 LOW findings folded in-session** (qa F1 tautology removed → object-identity guard; qa F2 503 retrospective path → parametrized add; qa F3 regression marker added to position test; sec F3 inline-style scope → docstring note pinning the bounded-float justification). **2 LOW findings deferred as advisory** (sec F1 policy extension to `frame-ancestors 'none'` + `object-src 'none'`; sec F2 framework-exception fail-open try/except around `call_next`).

Quality gate after the fold: 7/7 (235 telemetry+server tests; ledger now 33 guards).

## Specialist Findings

### qa-specialist (confidence 0.88)

- **qa F1 (LOW weak-assertion)** — `test_csp_middleware_is_outermost_in_user_middleware` second assertion `ContentSecurityPolicyMiddleware.__name__ == "ContentSecurityPolicyMiddleware"` is tautological (class.__name__ is always the definition-time name). **Folded in-session**: replaced with object-identity assertion `middleware_specs[0].cls is ContentSecurityPolicyMiddleware`, which catches a future move that swaps the import for a same-named shim.
- **qa F2 (LOW missing-edge-case)** — CSP test on `/fragments/live` 500 but no test on `/fragments/retrospective` 503 (sqlite3.OperationalError path). Both are htmx swap targets; same defense-in-depth argument. **Folded in-session**: the live 500 test was converted to a parametrized test `test_csp_header_present_on_fragment_error_response` covering BOTH `/fragments/live` (RuntimeError → 500) AND `/fragments/retrospective` (sqlite3.OperationalError → 503). A future refactor that extracts either route into a sub-app fails CSP coverage on the extracted half.
- **qa F3 (LOW marker inconsistency)** — `test_csp_middleware_is_outermost_in_user_middleware` lacked `@pytest.mark.regression`. The ledger entry names it as a regression guard; `pytest -m regression` would skip it. **Folded in-session**: marker added.
- **qa F4 (INFO)** — `/healthz` CSP coverage. No action needed — middleware is unconditional; `/healthz` is plain text, not an HTML surface. Tracked as advisory only.
- **qa F5 (INFO)** — No negative-path mutation guard (remove `add_middleware`, prove failure). Disproportionate for a LOW advisory; not a defect.

### security-specialist (confidence 0.92)

- **sec F1 (LOW — A05:2021 Security Misconfiguration)** — Policy completeness: missing `frame-ancestors 'none'` (not governed by default-src — has no fallback, so current policy provides no CSP-layer clickjacking defense) and `object-src 'none'` (default-src 'self' allows plugin content from same origin; standard tightening to 'none'). **Deferred as advisory**: the F2 advisory verbatim was the 3-directive form (REV-20260607-200447 line 81); extending to 5 directives is an enhancement beyond F2, not the F2 closure. Loopback-only single-developer deployment makes clickjacking risk minimal. Track for a future fold.
- **sec F2 (LOW — fail-open path on framework exceptions)** — If `call_next` raises (catastrophic FastAPI/Starlette framework crash bypassing the route handlers' `except Exception` clauses), the header is never set. **Deferred as advisory**: practically blocked because every route catches Exception and converts to HTMLResponse; only triggered by a routing-table-corruption-class crash. Defensible to defer; the regression-ledger entry for `test_retrospective_error_general_exception_response_is_generic` independently guards the route-level catch.
- **sec F3 (INFO scope note)** — `style-src 'unsafe-inline'` scope: currently bounded to one inline-style attribute (runway-bar `style="width:{_esc(bar_width)}%"`) whose value is a clamped float. **Folded in-session**: `CONTENT_SECURITY_POLICY` constant docstring now records the bounded-float justification and the rule that any future `style=` attribute with a STRING field must trigger a CSS-aware sanitization review.
- **sec F4/F5/F6 (INFO confirmed strengths)** — Overwrite semantics correct; no streaming/WebSocket transport-layer drop path; `script-src 'self'` (no `'unsafe-inline'`) is structurally correct and load-bearing (no inline `<script>` body anywhere; htmx uses only hx-get + hx-trigger, no eval).

## Required Changes
(none — both specialists APPROVE-WITH-CHANGES; the 4 in-session folds satisfy the review.)

## Advisory Findings — track in BUILD_STATUS for future fold

- **sec F1** (policy extension to 5 directives — `frame-ancestors 'none'` + `object-src 'none'`).
- **sec F2** (framework-exception fail-open — try/except around `call_next` in CSP middleware).

## Speculative Findings — Lower Confidence
(none — both specialists reported above the 0.80 threshold.)

## Strengths

- Single source of truth: `CONTENT_SECURITY_POLICY` in production code, imported into tests. Drift between production and test is structurally impossible.
- Middleware position verified mechanically by index AND object identity (after qa F1 fold).
- All three error-path response codes (400, 500, 503) covered by regression tests — the response codes most likely to be missed by a naive "test the happy path" approach.
- `script-src 'self'` (no `'unsafe-inline'`) is the load-bearing clause — bans every inline `<script>` block forever, paired with the `</script>`-injection guard the AC6 layer already enforces.
- Implementation mirrors the existing `HostHeaderGuard` middleware pattern; familiar to any contributor.

## Confidence Annotation

0 findings in speculative section (confidence < 0.80). 0 findings retained as unscored. Both specialists at or above 0.88.

## Model Tiers
- qa-specialist: sonnet (default for risk=low)
- security-specialist: sonnet (default for risk=low)

## Discarded Findings
(none.)

## Education Gate Recommendation

**Not required.** This is a single defense-in-depth middleware addition on a previously-reviewed component (Telemetry Layer B live daemon, REV-20260607-200447). The CSP pattern is widely understood; the middleware structure mirrors the existing `HostHeaderGuard` pattern; the regression-ledger entry captures the load-bearing invariants (policy string, middleware position, header on every error path). No new concepts requiring walkthrough or quiz.

## Verdict

**APPROVE-WITH-CHANGES → APPROVE post-fold** — 4 LOW findings folded in-session; 2 LOW deferred as advisory with explicit defensibility notes. Quality gate 7/7 after the fold. Ready to commit.
