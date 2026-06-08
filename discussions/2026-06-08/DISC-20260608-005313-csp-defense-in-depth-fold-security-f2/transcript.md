---
discussion_id: DISC-20260608-005313-csp-defense-in-depth-fold-security-f2
started: 2026-06-08T00:53:28.171003+00:00
ended: 2026-06-08T01:01:44.393975+00:00
agents: [facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260608-005313-csp-defense-in-depth-fold-security-f2

## Turn 1 — facilitator (evidence)
*2026-06-08T00:53:28.171003+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Close security F2 (LOW observation) from REV-20260607-200447 — add a defense-in-depth Content-Security-Policy header to the Telemetry Layer B live dashboard daemon, with the advisory's documented policy value (default-src 'self'; script-src 'self'; style-src 'unsafe-inline').
- **Files/scope**: scripts/telemetry/dashboard_server.py (added ContentSecurityPolicyMiddleware + CONTENT_SECURITY_POLICY constant, registered last so outermost); tests/test_dashboard_server.py (5 regression tests: policy-string pin, 200 shell, 400 host-rejection, 500 live-fragment error fragment, middleware-position); memory/bugs/regression-ledger.md (+1 entry, now 33 guards).
- **Developer-stated motivation**: REV-20260607-200447 burndown — 3 advisories remain after this session (qa F1 + arch F2 + security F2). The handoff identified security F2 as a small, well-bounded single unit suitable for a supervised session.
- **Explicit constraints**: NO push. /review must run before commit. Quality gate must pass. Capture never skipped. Use the policy value documented in the advisory verbatim. Operate within the autonomous execution authorization scope (feature branch fix/c-gate-log-integrity only).

---

## Turn 2 — qa-specialist (proposal)
*2026-06-08T00:58:17.020198+00:00 | confidence: 0.88*
*tags: qa-specialist, csp, test-adequacy*

## QA Review (confidence 0.88) — CSP defense-in-depth fold

Suite locks contract at right abstraction level for LOW-risk advisory fold; one vacuous sub-assertion, one missing 503 CSP test, one marker inconsistency.

### Finding 1 (LOW weak-assertion)
Location: tests/test_dashboard_server.py test_csp_middleware_is_outermost_in_user_middleware second assertion (`ContentSecurityPolicyMiddleware.__name__ == 'ContentSecurityPolicyMiddleware'`) is tautological — class.__name__ is always the definition name; cannot fail unless the import already failed. Recommendation: drop or replace with object identity assertion `type(app.user_middleware[0].cls) is ContentSecurityPolicyMiddleware`. Exceptions: matches the existing test_host_header_guard_is_middleware_layer style — if convention, document it.

### Finding 2 (LOW missing-edge-case)
Location: scripts/telemetry/dashboard_server.py retrospective_fragment 503 + 500 branches; tests/test_dashboard_server.py has CSP test on /fragments/live 500 but NONE on /fragments/retrospective 503. The 503 (sqlite3.OperationalError) and 500 paths are both htmx swap targets — same argument for stamping CSP applies. The position test + the 400/500 tests provide induction-style coverage, but a future refactor extracting retrospective_fragment into a sub-app could bypass. Recommendation: add a regression test that monkeypatches assemble_dashboard_data to raise sqlite3.OperationalError, asserts 503 + CSP header. LOW because live run confirms header is present; gap is missing GUARD, not missing behavior.

### Finding 3 (LOW marker inconsistency)
Location: tests/test_dashboard_server.py:875 — test_csp_middleware_is_outermost_in_user_middleware lacks `@pytest.mark.regression` even though the regression ledger entry names it. Other 4 CSP tests carry it. pytest -m regression sweep would skip this test. Recommendation: add the marker (consistent with the ledger entry).

### Finding 4 (INFO)
/healthz route not covered by a CSP assertion — but it's plain text, not an HTML surface; middleware position test + behavior tests cover the invariant. No action.

### Finding 5 (INFO)
No negative-path mutation guard (remove add_middleware, prove failure). Disproportionate for a LOW advisory; skip.

### Strengths
- Single source of truth: CONTENT_SECURITY_POLICY in production code, imported into tests.
- 400 test correctly exercises HostHeaderGuard short-circuit + CSP wrapping.
- 500 test monkeypatches at module scope (fold_events), exercises actual exception branch.
- Position test reads user_middleware index 0 (correct Starlette LIFO model).

---

## Turn 3 — security-specialist (proposal)
*2026-06-08T00:58:37.567482+00:00 | confidence: 0.92*
*tags: security-specialist, csp, defense-in-depth*

## Security Review (confidence 0.92) — CSP defense-in-depth fold

Implementation structurally sound; policy correctly omits script-src 'unsafe-inline' (load-bearing); two LOW finding clusters worth folding.

### Finding 1 (LOW — A05:2021 Security Misconfiguration)
Policy completeness: missing `frame-ancestors 'none'` (NOT governed by default-src — has no fallback, so current policy provides NO CSP-layer clickjacking defense) AND `object-src 'none'` (default-src 'self' allows plugin content from same origin; standard tightening to 'none'). On a loopback-only single-developer tool the practical risk is minimal, but the standard hardened policy is 5 directives, not 3. Recommendation: extend CONTENT_SECURITY_POLICY to include both, update the pinning test literal. Exception: if the advisory explicitly specified the 3-directive policy as the closed state for F2, this is an enhancement beyond F2 rather than a correction (REV-20260607-200447 line 81 quotes only the 3-directive form).

### Finding 2 (LOW — fail-open path on framework exceptions)
Location: ContentSecurityPolicyMiddleware.dispatch — `response = await call_next(request)` then `response.headers['Content-Security-Policy'] = self._policy`. If call_next raises (catastrophic FastAPI/Starlette framework-level exception that bypasses the route handlers' `except Exception` clauses), the header is never set. Practically blocked because every route catches Exception and converts to HTMLResponse — so call_next always returns a response. Only triggered by a framework-level routing-table-corruption-class crash. Recommendation (optional): wrap call_next in try/except, fall back to PlainTextResponse(500) with the policy still stamped. Paired with a test that monkeypatches a route to raise BEFORE returning a response. Defensible to defer — the loopback threat model + the broad route-level catches make this implausible-chained.

### Finding 3 (INFO confirmed acceptable)
`style-src 'unsafe-inline'` covers `<style>` blocks + ONE inline `style="width:{_esc(bar_width)}%"` attribute on the runway bar. bar_width = max(0.0, min(100.0, runway.fill_pct)) — a Python float clamped to [0,100] before _esc; structurally cannot carry a CSS-injection vector (`}` or `;`). Permission correctly scoped. Recommendation: add a docstring note to CONTENT_SECURITY_POLICY explaining the bounded scope so a future contributor adding a string-valued `style=` attribute knows to trigger a CSS-sanitization review.

### Finding 4 (INFO strength)
Overwrite semantics (= not setdefault) are correct: no legitimate scenario where a route should relax CSP; overwrite is the safety-positive choice.

### Finding 5 (INFO confirmed)
No StreamingResponse / WebSocket / SSE routes; no transport-layer CSP-drop path.

### Finding 6 (INFO strength)
`script-src 'self'` (no 'unsafe-inline') is structurally correct + load-bearing: no inline `<script>` body anywhere; htmx is vendored at /static/. CSP blocks every injected `<script>...` body even if _esc regresses on a string field. htmx uses only hx-get + hx-trigger (no hx-on / js:), so 'unsafe-eval' absence has zero functional impact.

### Trust Boundary Map
Response path outermost-to-innermost: CSP > HostHeaderGuard > CORS > route handler. Verified by user_middleware index 0 assertion in test_csp_middleware_is_outermost_in_user_middleware. Correct.

### Strengths
- Policy string pinned in ONE place with exact-match test; any drift fails loudly.
- Middleware position verified mechanically by index.
- 400 + 500 paths covered (the high-leakage error paths).
- script-src 'self' (no 'unsafe-inline') is the load-bearing clause — confirmed structurally correct.
- Mirrors existing HostHeaderGuard middleware pattern; familiar to any contributor.

---

## Turn 4 — facilitator (critique)
*2026-06-08T01:00:49.632980+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 6 verified, 5 inconclusive (all INFO-tier confirmed strengths or single-judgment policy-completeness calls), 0 discarded. QA F1/F2/F3/F4/F5 + SEC F1/F2/F3/F4/F5/F6 all point to extant code locations (verified by direct file read). No discarded findings.

---

## Turn 5 — facilitator (synthesis)
*2026-06-08T01:01:44.393975+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:2, speculative:0, model-tiers:qa-specialist:sonnet+security-specialist:sonnet*

REV-20260608-010051 — CSP defense-in-depth fold for security F2 (REV-20260607-200447). Both specialists APPROVE-WITH-CHANGES (qa-specialist 0.88, security-specialist 0.92, ensemble consensus). 0 BLOCKING / 4 LOW folded in-session / 2 LOW deferred-as-advisory. Folded: qa F1 (object-identity guard replaces tautology), qa F2 (parametrized 500+503 fragment-error coverage), qa F3 (regression marker on position test), sec F3 (docstring note on inline-style scope). Deferred: sec F1 (5-directive policy extension — advisory verbatim was 3-directive), sec F2 (framework-exception fail-open try/except — practically blocked by route-level catches). Quality gate 7/7 after fold (235 telemetry+server tests, ledger now 33 guards). Verdict APPROVE-WITH-CHANGES → APPROVE post-fold.

---
