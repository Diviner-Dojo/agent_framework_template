# DISC-20260608-011500-csp-f1-f2-extension-fold

Sealed discussion for REV-20260608-011936 — Telemetry Layer B Content-Security-Policy F1+F2 extension fold.

Closes the two LOW advisories deferred-as-advisory from REV-20260608-010051: security F1 (extend CSP from 3-directive to 5-directive standard hardening) and security F2 (try/except around `call_next` in `ContentSecurityPolicyMiddleware.dispatch` with CSP still stamped on the 500 fallback). Both findings live in `scripts/telemetry/dashboard_server.py` and cohere as one defensive-only hardening fold.

## Risk Assessment
**low** — defense-in-depth only; no behavioral change to the happy path; no surface added (loopback only); no test deletion or weakening.

## Collaboration Mode
**ensemble** (qa-specialist + security-specialist), 1 round.

## Turn 1 — facilitator: evidence (context brief)
*See `events.jsonl` turn 1.*

## Turn 2 — qa-specialist: proposal
*See `events.jsonl` turn 2.* Confidence 0.88. One BLOCKING assertion-completeness gap (Traceback negative missing from the catastrophic-exception test, peer test already pins it); LOW exact-body pin + LOW naming clarity; INFO confirmations of verbatim/per-directive complementarity, new-test non-redundancy with the existing 500-path test, and ledger classification.

## Turn 3 — security-specialist: proposal
*See `events.jsonl` turn 3.* Confidence 0.91. MED exception-hierarchy concern about `except Exception` scope (two resolution options: narrow OR document why HTTPException cannot reach this path); LOW PlainTextResponse → htmx swap-target shape mismatch (recommend HTMLResponse); LOW-INFO base-uri evaluated-and-omitted docstring note; INFO confirmations of frame-ancestors / object-src threat model, connect-src / img-src / font-src / form-action correctly omitted, ledger entry accuracy.

## Turn 4 — facilitator: critique (finding verification)
*See `events.jsonl` turn 4.* 13 verified, 0 inconclusive, 0 discarded. Convergence: both specialists independently surfaced the catastrophic-exception test as the load-bearing surface, from orthogonal directions (qa: assertion completeness; security: exception-hierarchy + htmx swap-target shape). The two perspectives compose into a strictly stronger test than either individual proposal.

## Turn 5 — facilitator: synthesis
*See `events.jsonl` turn 5.* All 5 actionable findings folded in-session; 0 deferred-as-advisory.

**Final verdict: APPROVE-WITH-CHANGES → APPROVE post-fold.**

Folds applied:
- **qa F1 (BLOCKING)**: `assert "Traceback" not in body` added to the catastrophic-exception test.
- **qa F2 (LOW)**: exact-body pin `assert body.strip() == "<p>Internal Server Error</p>"` added.
- **qa F3 (LOW)**: test renamed `test_csp_middleware_returns_generic_500_and_stamps_policy_when_call_next_raises`; regression-ledger entry updated.
- **security F1 (MED)**: `except Exception` scope justified via expanded inline docstring — Starlette's `ExceptionMiddleware` is added automatically below the user middleware stack and converts `HTTPException` to a Response before it could reach this `call_next`, so any exception arriving at this `try/except` is by definition catastrophic. Narrowing would lose the load-bearing "CSP on every byte" invariant for the catastrophic path. `BaseException` subclasses (`asyncio.CancelledError`) already propagate naturally.
- **security F2 (LOW)**: `PlainTextResponse("Internal Server Error", ...)` → `HTMLResponse("<p>Internal Server Error</p>", ...)`. Minimal HTML fragment that htmx `hx-swap` targets handle cleanly; AC6 compliance preserved.
- **security F2-INFO**: `CONTENT_SECURITY_POLICY` docstring now records `base-uri` / `connect-src` / `img-src` / `font-src` / `form-action` as evaluated and intentionally omitted, with the explicit re-evaluation trigger for each ("re-evaluate if a `<base>` tag / outbound fetch / external image / web font / `<form>` is ever added").

Quality gate after fold: 7/7 (235 telemetry+server tests; ledger now 34 guards; ruff format + check clean).
