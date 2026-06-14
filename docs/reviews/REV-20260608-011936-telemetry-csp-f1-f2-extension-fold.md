---
review_id: REV-20260608-011936
discussion_id: DISC-20260608-011500-csp-f1-f2-extension-fold
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
review_duration_minutes: 9
---

## Request Context
- **What was requested**: Close the two LOW advisories deferred-as-advisory in REV-20260608-010051 — security F1 (extend the Telemetry Layer B CSP from the 3-directive form to the 5-directive standard hardening by adding `frame-ancestors 'none'` + `object-src 'none'`) and security F2 (wrap `await call_next(request)` in `ContentSecurityPolicyMiddleware.dispatch` in a `try/except` that converts a catastrophic framework exception to a generic 500 with the CSP header still stamped). Both advisories live in the same file and cohere as one defense-in-depth fold.
- **Files/scope**: `scripts/telemetry/dashboard_server.py` (CSP constant extended to 5 directives with expanded docstring explaining each new directive's threat model + an evaluated-and-omitted note for `base-uri` / `connect-src` / `img-src` / `font-src` / `form-action`; `ContentSecurityPolicyMiddleware.dispatch` now has try/except around `call_next` with HTMLResponse 500 fallback that still stamps the policy); `tests/test_dashboard_server.py` (updated verbatim policy literal; new parametrized per-directive guard; new catastrophic-exception fail-closed test); `memory/bugs/regression-ledger.md` (+1 entry, ledger now 34 guards).
- **Developer-stated motivation**: REV-20260607-200447 burndown carry-over: the cohering small bite identified by the rolling handoff as the most-bounded supervised-session unit (small two-finding hardening cluster, same file, defensive-only, no behavior change).
- **Explicit constraints**: NO push. /review must run before commit. Quality gate must pass. Capture never skipped. Operate within the autonomous execution authorization scope (feature branch `fix/c-gate-log-integrity` only). Defensive-only — do not weaken any existing CSP guard or regression test.

## Summary

Both specialists **APPROVE-WITH-CHANGES** (consensus, ensemble mode). 0 BLOCKING in their assessment of design — the qa-specialist tagged one assertion-completeness gap as BLOCKING (the catastrophic-exception test must pin `"Traceback" not in body` to match the peer AC6 contract). **All findings folded in-session** (5 LOW/MED folded, no advisories deferred):

- **qa F1 BLOCKING (assertion completeness)** — folded: `assert "Traceback" not in body` added.
- **qa F2 LOW (exact-body pin)** — folded: `assert body.strip() == "<p>Internal Server Error</p>"` added (the switch to HTMLResponse + exact pin together catch any future fallback-body drift).
- **qa F3 LOW (naming clarity)** — folded: test renamed `test_csp_middleware_returns_generic_500_and_stamps_policy_when_call_next_raises` (ledger entry updated to match).
- **security F1 MED (exception-hierarchy / `except Exception` scope)** — folded as docstring-justification: extended the inline comment to record that Starlette's `ExceptionMiddleware` sits BELOW the user middleware stack and converts `HTTPException` to a Response before it could reach `call_next` here, so any exception arriving at this `try/except` is by definition catastrophic — narrowing to specific types would lose the load-bearing "CSP on every byte" invariant for the catastrophic path. `BaseException` subclasses like `asyncio.CancelledError` propagate by design (not blocked here).
- **security F2 LOW (PlainTextResponse → HTMLResponse for htmx swap compatibility)** — folded: `PlainTextResponse("Internal Server Error", ...)` replaced with `HTMLResponse("<p>Internal Server Error</p>", ...)`; htmx `hx-swap` targets handle the minimal HTML fragment cleanly rather than landing raw text in the DOM swap target.
- **security F2 INFO (docstring note on `base-uri`)** — folded: `CONTENT_SECURITY_POLICY` docstring now records that `base-uri` was evaluated and intentionally omitted (no `<base>` element today), along with the same justification for `connect-src` / `img-src` / `font-src` / `form-action` (all covered by `default-src 'self'` fallback). Adding any of those surfaces in the future MUST add the matching directive in the same change.

Quality gate after the fold: **7/7** (235 telemetry+server tests; ledger now 34 guards; ruff format + check clean).

## Specialist Findings

### qa-specialist (confidence 0.88)

- **qa F1 (BLOCKING assertion-completeness, AC6 contract)** — `test_csp_middleware_stamps_policy_when_call_next_raises` asserts `"_BoomError" not in body` and `"simulated catastrophic" not in body` but NOT `"Traceback" not in body`. The peer test `test_retrospective_error_general_exception_response_is_generic` (line 513) holds the full AC6 contract: class name absent + marker absent + traceback absent. The new catastrophic-exception test must hold the same contract; the current test pins two of three. **Folded in-session**: `assert "Traceback" not in body` added.
- **qa F2 (LOW exact-body pin)** — Negative-only assertions miss "the fallback body grew a new field" regressions (e.g. a future edit that echoed the request path in the 500 body). **Folded in-session**: exact-body pin `assert body.strip() == "<p>Internal Server Error</p>"` added. Paired with the security F2 LOW fold (PlainTextResponse → HTMLResponse), the pin documents BOTH the body content AND the HTML media-type choice in one assertion.
- **qa F3 (LOW naming clarity)** — Test name `test_csp_middleware_stamps_policy_when_call_next_raises` describes one of two load-bearing assertions; the body-generic AC6 assertion is equally load-bearing. **Folded in-session**: renamed `test_csp_middleware_returns_generic_500_and_stamps_policy_when_call_next_raises`; regression-ledger entry updated to match.
- **qa F4 (INFO verbatim vs per-directive complementarity confirmed)** — `test_csp_policy_string_pins_documented_policy` and `test_csp_policy_contains_each_load_bearing_directive` are genuinely complementary, not redundant: verbatim catches order changes that drop a directive; per-directive catches careful edits that retain the count but weaken a value, AND isolates exactly which directive drifted under a future re-order. No action.
- **qa F5 (INFO existing 500-path coverage vs new test)** — `test_csp_header_present_on_fragment_error_response[/fragments/live]` covers a route-level exception caught INSIDE the route handler (call_next returns a real Response object). The new catastrophic-exception test covers the structurally distinct path where the exception escapes BEFORE any response is built (call_next never returns). The existing test does NOT cover the new try/except branch; the new test is non-redundant. No action.
- **qa F6 (INFO regression-ledger classification)** — Trust Boundary Gap is the project convention for the CSP series (consistent with REV-20260608-010051's entry, the session-10g CSP ledger entry, and the prior CSP fold). Defensible. No action.

### security-specialist (confidence 0.91)

- **security F1 (MED `except Exception` scope)** — Coding standard `coding_standards.md` requires specific exceptions; `except Exception` here is broad and could absorb framework control-flow signals like Starlette's `HTTPException`, which would convert a legitimate 404/422 from an inner middleware into a generic 500 and mask the routing error. **Folded in-session as docstring-justification (specialist's Option 2)**: Starlette's `ExceptionMiddleware` is added automatically BELOW the user middleware stack and converts `HTTPException` to a proper Response BEFORE it could reach `call_next` here. The structural model makes any exception arriving at this `try/except` catastrophic by construction (inner-middleware regression, ASGI-level framework bug, or a route that bypassed `except Exception`). Narrowing the catch would lose the load-bearing "CSP on every byte" invariant for the catastrophic path. `BaseException` subclasses (`asyncio.CancelledError`, `KeyboardInterrupt`) already propagate naturally on Python 3.11+. Documented explicitly in the middleware's inline comment so a future reviewer does not raise the same concern.
- **security F2 (LOW PlainTextResponse → htmx swap-target shape mismatch)** — `PlainTextResponse("Internal Server Error", ...)` landed as raw text in the `<section id="live-section">` htmx swap target, breaking DOM structure for subsequent polls (next poll would still recover, but transient one-poll state is unstructured). **Folded in-session**: `HTMLResponse("<p>Internal Server Error</p>", ...)`. The minimal HTML fragment swaps cleanly into any htmx target; AC6 compliance preserved (no exception class, no path, no stack). The exact-body pin in the test now structurally enforces the HTML media-type choice too (qa F2 fold).
- **security F2 LOW-INFO (`base-uri` evaluated and omitted)** — `base-uri 'self'` is genuinely load-bearing IF a `<base>` element ever ships (an injected `<base href="...">` would redirect every relative URL on the page regardless of `default-src`). At this surface the dashboard has no `<base>` and htmx does not require one; omitting `base-uri` is correct today. **Folded in-session**: `CONTENT_SECURITY_POLICY` docstring now records that `base-uri` was evaluated and intentionally omitted with the explicit trigger ("re-evaluate if a `<base>` tag is ever added"). Same docstring also records that `connect-src` / `img-src` / `font-src` / `form-action` were evaluated and omitted because they fall back to `default-src 'self'` and the dashboard makes no outbound fetch / loads no remote images / bundles no web fonts / renders no `<form>` — over-specifying the policy carries maintenance cost with no attack-surface reduction over the existing fallback.
- **security F3 (INFO `connect-src` / `img-src` / `font-src` correctly NOT recommended)** — Adding them buys nothing: `default-src 'self'` already covers them at this surface; over-spec'ing has maintenance cost. Affirmed by the docstring fold above.
- **security F4 (INFO threat model coverage)** — `frame-ancestors 'none'` blocks clickjacking via DNS-rebinding (a page that has already navigated an iframe and rebinds mid-session would bypass `HostHeaderGuard` which only inspects the incoming Host header). `object-src 'none'` is forward defense against a future regression that serves plugin content. Both directives correctly characterized as defense-in-depth with real (low-probability) threats behind them.
- **security F5 (INFO regression-ledger entry accuracy)** — All three test function names in the ledger entry verified to exist at the named locations in `tests/test_dashboard_server.py`. Root-cause class `Trust Boundary Gap` is consistent with the prior CSP-series entries and defensible as "response crosses output boundary without the security header on ALL code paths." No correction needed.

## Required Changes
(none — all 5 findings folded in-session.)

## Advisory Findings — track in BUILD_STATUS for future fold
(none deferred — every LOW/MED/INFO with an action was folded; INFO confirmations carry no follow-up.)

## Speculative Findings — Lower Confidence
(none — both specialists reported above the 0.80 threshold.)

## Strengths

- **Verbatim + per-directive pinning are complementary** — verbatim catches order-and-count drift, per-directive catches careful weakenings and isolates which directive changed. Both kept by design.
- **`raise_server_exceptions=False` on the catastrophic-exception test** — the correct `TestClient` configuration to let the middleware's `except` clause run (without it the exception would be re-raised by the test client before the assertions could fire).
- **Monkeypatch target choice** — `HostHeaderGuard.dispatch` (the next-inner middleware) is the right raiser because it exercises the real middleware stack order (CSP outermost → HostHeaderGuard next) and would catch a future `create_app` re-order that moved CSP inside `HostHeaderGuard`.
- **`script-src 'self'` (no `'unsafe-inline'`)** is still the load-bearing clause — unchanged from session 10g.
- **`frame-ancestors 'none'`** is the authoritative modern replacement for `X-Frame-Options: DENY`; correctly complementary to (not redundant with) `HostHeaderGuard` (different trust boundaries).
- **Docstring records the "evaluated and intentionally omitted" rationale** for each directive considered but not added, so a future contributor adding a `<base>`, an external image, a web font, or a form knows exactly which directive must be added in the same change.
- **AC6 compliance verified** — body of the 500 catastrophic fallback contains no exception class, no path, no marker, no traceback (test pins all four).

## Confidence Annotation

0 findings in speculative section (confidence < 0.80). 0 findings retained as unscored. Both specialists at or above 0.88.

## Model Tiers
- qa-specialist: sonnet (default for risk=low)
- security-specialist: sonnet (default for risk=low)

## Discarded Findings
(none — every finding either folded or annotated as INFO confirmation.)

## Convergence Notes

Both specialists independently flagged the catastrophic-exception test as the load-bearing surface of the change. qa-specialist focused on assertion completeness (Traceback + exact body), security-specialist focused on exception-hierarchy correctness and response-shape compatibility with htmx. The two perspectives are orthogonal and together produce a test that pins BOTH the AC6 leak-prevention contract AND the htmx swap-target shape — strictly stronger than either specialist's individual proposal. The security-specialist also independently confirmed that the existing `frame-ancestors`-vs-`HostHeaderGuard` argument in the docstring is accurate and important (they operate at different layers: Host-header inspection vs. browser-level embedding rule).

## Education Gate Recommendation

**Not required.** Defense-in-depth follow-up on a previously-reviewed component (Telemetry Layer B CSP middleware, REV-20260607-200447 + REV-20260608-010051). The pattern is established; this fold extends the same middleware with two well-understood additions (extra CSP directives + try/except fail-closed). The regression-ledger entry captures the load-bearing invariants. No new concepts requiring walkthrough or quiz.

## Verdict

**APPROVE-WITH-CHANGES → APPROVE post-fold** — 5 LOW/MED + 1 INFO docstring fold applied in-session; 0 deferred. Quality gate 7/7 after the fold (235 telemetry+server tests; ledger now 34 guards). Ready to commit.
