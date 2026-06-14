---
discussion_id: DISC-20260607-233516-review-arch-f1-f3-fold-rev200447
started: 2026-06-07T23:35:39.684687+00:00
ended: 2026-06-07T23:41:58.957374+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 5
---

# Discussion: DISC-20260607-233516-review-arch-f1-f3-fold-rev200447

## Turn 1 — facilitator (evidence)
*2026-06-07T23:35:39.684687+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: /review of the arch F1 + arch F3 advisory fold from REV-20260607-200447 (Phase 1 Layer B dashboard daemon review). Two cohering small architecture findings landed in one unit per the supervisor handoff for session 10c.
- **Files/scope**: scripts/ingest_token_usage.py (added A-ARCH1 docstring footers to parse_timestamp + coerce_int + discover_session_dirs); scripts/telemetry/dashboard_server.py (deleted unused _connect_readonly per Principle #8); tests/test_dashboard_server.py (expanded AC15 contract test to 6 helpers, added new test_a_arch1_promoted_helpers_carry_promotion_docstring_footer regression guard, redirected test_db_connection_is_read_only_at_driver_level to the surviving scripts.telemetry.dashboard._connect_readonly); memory/bugs/regression-ledger.md (one combined ledger entry for F1+F3).
- **Developer-stated motivation**: Drain REV-20260607-200447 advisories one cohering unit at a time; F1+F3 are the cleanest pair (both small, both touch the same file or the daemon's public-surface seam) per the supervisor handoff. F1 makes the public surface internally consistent; F3 removes Principle-#8 inversion (premature promotion of a helper before a 2nd actual consumer).
- **Explicit constraints**: NO push; NO auto-merge; stay on fix/c-gate-log-integrity; no .claude/settings.json edits beyond developer-applied opt-in; capture must run; do not weaken the AC15/AC5 invariants while folding the advisories.

---

## Turn 2 — architecture-consultant (proposal)
*2026-06-07T23:40:35.473953+00:00 | confidence: 0.93*
*tags: verdict:approve, arch, a-arch1, principle-8, low-risk*

VERDICT: APPROVE (no blocking, no advisory; one Info judgement call). Confidence 0.93.

Both arch F1 and arch F3 close the original advisories exactly as written. The A-ARCH1 promoted public surface is now internally uniform across all 6 helpers; the daemon-side _connect_readonly was correctly identified as a Principle-#8 inversion (duplicate of scripts/telemetry/dashboard.py:_connect_readonly with zero call sites — the daemon delegates to assemble_dashboard_data which uses the surviving helper at line 130). Test redirection is structurally tighter: the AC5 driver-level guard now exercises the helper the daemon actually invokes at runtime, not a parallel dead one. The new test_a_arch1_promoted_helpers_carry_promotion_docstring_footer guards the right invariant (substring assertion catches the F1 failure mode — a contributor re-privatising or stripping the footer would fail fast). The sqlite3 import in dashboard_server.py is correctly retained for the OperationalError catch in retrospective_fragment (line 425). The 4th-cross-module-consumer claim in the new footer text is verified against the import graph (parse_timestamp at dashboard_server.py:220+:279; coerce_int at :235-238+:294-297).

INFO (judgement call, not advisory): Defer adding __all__ to scripts/ingest_token_usage.py until a 'from scripts.ingest_token_usage import *' consumer appears OR a private-helpers grouping emerges. The footer + AC15 contract test + new footer regression test already give one grep-able spot; an __all__ would force a follow-on audit of the rest of the public surface for no current benefit. Add later only when a contributor proposes star-imports or a private name accidentally re-exports.

STRENGTHS: F1 and F3 genuinely cohere (both about the public-vs-private seam at the scripts.ingest_token_usage / scripts.telemetry.dashboard* boundary). Ledger entry (line 58) names all four guarding tests with a 'Do not re-introduce' clause that hardens F3 against regression by a well-meaning future contributor. AC15 contract test extended without weakening (4 -> 6 names; not-underscored ban extended; new footer guard adds an orthogonal invariant).

---

## Turn 3 — qa-specialist (proposal)
*2026-06-07T23:40:51.584304+00:00 | confidence: 0.88*
*tags: verdict:approve-with-changes, qa, low-risk, 3-advisory*

VERDICT: APPROVE-WITH-ADVISORIES (no blocking; 3 LOW advisories). Confidence 0.88.

The change set delivers what the developer context claims: AC15 contract test grew 4 -> 6 helpers; new @pytest.mark.regression footer guard added; AC5 driver-level read-only test cleanly redirected to the helper the daemon actually invokes. All 6 helpers confirmed callable with footer at runtime. Three low-priority gaps worth noting, none blocking commit.

F1-QA (Low, missing-edge-case): test_a_arch1_promoted_helpers_carry_promotion_docstring_footer uses substring 'Promoted to public in the A-ARCH1 promotion' — catches total removal but not paraphrase drift (e.g. 'Promoted via A-ARCH1' would pass despite losing the SPEC reference). RECOMMENDATION: add a second clause asserting SPEC-20260607-183136 is also in the docstring, anchoring traceability. One-line addition, same test.

F2-QA (Low, missing-test): No test guards that dashboard_server._connect_readonly is ABSENT post-deletion. The ledger entry's 'Do not re-introduce the dead helper without a second actual consumer' rule is currently human-enforced only. RECOMMENDATION: add 'assert not hasattr(dashboard_server, "_connect_readonly")' to the existing not-underscored test (one line). Makes the Rule-of-Three guard machine-enforceable.

F3-QA (Low, weak-assertion / pre-existing): The redirected AC5 test exercises _connect_readonly in isolation; there is no test that asserts assemble_dashboard_data is the mechanism the daemon's route handler uses. This is a pre-existing gap, adequately covered by test_routes_do_not_mutate_database_schema_or_row_counts at the route level. The redirect is a regression improvement (testing the live helper instead of a dead one). No immediate action.

STRENGTHS: Fail-fast error messages (per-helper assertion with specific message); regression-marker discipline (both expanded + new tests carry @pytest.mark.regression); orphan check clean (git grep dashboard_server._connect_readonly = 0 code refs); AC5 guard stronger after redirect not weaker (testing live helper); negative source-text assertions extended correctly (bans itu._parse_timestamp / itu._coerce_int). All assertions are observable runtime truths, not hypotheses.

---

## Turn 4 — facilitator (critique)
*2026-06-07T23:41:13.263117+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 3 verified, 0 inconclusive, 0 discarded. arch-consultant: no findings to verify (verdict APPROVE; one INFO judgement on __all__ deferral). qa-specialist F1-QA verified: substring check would pass a paraphrase that drops SPEC reference. qa-specialist F2-QA verified: no test asserts dashboard_server._connect_readonly is absent (greppable: only ledger + discussion refs remain in repo). qa-specialist F3-QA verified as a pre-existing gap (not introduced by this change), advisory only — no action.

FOLD DECISION: F1-QA + F2-QA are both one-line additions that materially strengthen the regression coverage, matching the F1/F3 intent. Folding them pre-commit per session 10b precedent. F3-QA + arch INFO deferred.

---

## Turn 5 — facilitator (synthesis)
*2026-06-07T23:41:58.957374+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:3, folded:2, deferred:2, speculative:0, model-tiers:arch:sonnet|qa:sonnet|facilitator:opus*

VERDICT: APPROVE-WITH-CHANGES (3 advisory; 2 folded in-session; 0 BLOCKING). Confidence 0.90.

Consensus across 2 specialists (architecture-consultant 0.93 APPROVE; qa-specialist 0.88 APPROVE-WITH-ADVISORIES). Both arch F1 + arch F3 from REV-20260607-200447 closed correctly: A-ARCH1 public surface internally uniform across 6 helpers (arch verified 4th-consumer claim against import graph); dead _connect_readonly correctly identified as Principle-#8 inversion and removed; AC5 test redirect is structurally tighter (now exercises the helper the daemon actually invokes via assemble_dashboard_data).

Two qa advisories folded pre-commit (matching session 10b precedent for high-convergence fold): F1-QA — added SPEC-20260607-183136 substring assertion alongside the footer check so a paraphrase that drops traceability still fails; F2-QA — added 'assert not hasattr(dashboard_server, _connect_readonly)' to the not-underscored test, making the ledger's 'Do not re-introduce' rule machine-enforceable.

DEFERRED: arch INFO (defer __all__ in ingest_token_usage.py until a star-import consumer appears); qa F3-QA (pre-existing route-handler-uses-assemble gap, adequately covered by test_routes_do_not_mutate_database_schema_or_row_counts at the route level).

Quality gate 7/7 (215 tests pass, 29 ledger guards) pre-fold; 4-test re-run post-fold all green. Risk: low (docstring + dead-code + test additions; no behavioral change to the daemon).

Model tiers: architecture-consultant:sonnet, qa-specialist:sonnet, facilitator:opus. Confidence annotation: 0 speculative (< 0.80), 0 unscored.

---
