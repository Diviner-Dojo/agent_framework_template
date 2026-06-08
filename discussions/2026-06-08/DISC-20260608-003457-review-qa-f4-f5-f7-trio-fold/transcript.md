# DISC-20260608-003457-review-qa-f4-f5-f7-trio-fold

**Command**: /review
**Status**: complete (sealed)
**Collaboration mode**: ensemble (qa-specialist + security-specialist)
**Report**: `docs/reviews/REV-20260608-003457-qa-f4-f5-f7-trio-fold.md`

## Verdict

APPROVE-WITH-CHANGES → APPROVE post-fold. 0 BLOCKING; 4 MED+LOW findings folded pre-commit; 3 LOW/INFO advisory.

## Turn timeline

1. **facilitator** — context-brief: trio of qa advisories (F4 CI portability + F5 CORS preflight + F7 retrospective Exception) targeting tests/test_dashboard_server.py; production code unchanged.
2. **qa-specialist** (sonnet, 0.91) — APPROVE-WITH-CHANGES; 1 MED (assertion precision on CORS test) + 4 LOW/INFO. Top fold: replace `allow_origin != "*"` AND `!= echoed_origin` with the precise header-absent contract `allow_origin == ""`.
3. **security-specialist** (sonnet, 0.91) — APPROVE-WITH-CHANGES; 2 MED (subdomain-spoof origin + credentials assertion) + 3 LOW/INFO. Top fold: add parametrize case for `http://127.0.0.1.evil.example.com` so an accidental regex `http://127\.0\.0\.1.*` is caught.
4. **facilitator** — finding-verification: 6 verified, 0 inconclusive. Convergence: qa F1 + security F1 + security F2 are strictly compatible and combine into one strictly-stronger parametrized test.
5. **facilitator** — synthesis: 0 BLOCKING; 4 folded pre-commit; 3 deferred as advisory. Education gate not needed (pure regression-test additions).

## Folds applied pre-commit

- **CORS test (qa F1 + security F1 + security F2 combined)** — parametrized over `[http://evil.example.com, http://127.0.0.1.evil.example.com]`; replaced inequalities with `assert allow_origin == ""` (header-absent contract); added `assert allow_creds.lower() != "true"`; renamed to `test_cors_preflight_from_foreign_origin_emits_no_allow_origin_header`.
- **Existing OperationalError test (qa F4)** — tightened `assert r.status_code in (500, 503)` to `assert r.status_code == 503` with a comment cross-referencing the paired 500 test.

## Advisory (deferred to follow-up)

- qa F3 (AC3 sandbox scope clarification — folded as docstring).
- security F3 (simple GET cross-origin coverage — theoretical under single-middleware architecture).
- compound ledger classification (Trust Boundary Gap as umbrella vs. split per-finding).
