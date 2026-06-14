---
discussion_id: DISC-20260608-020046-arch-f2-event-source-seam
started: 2026-06-08T02:01:03.904169+00:00
ended: 2026-06-08T02:11:37.814798+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 5
---

# Discussion: DISC-20260608-020046-arch-f2-event-source-seam

## Turn 1 — facilitator (evidence)
*2026-06-08T02:01:03.904169+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Close the LAST originating REV-20260607-200447 advisory (arch F2 event-source seam) and ship the recommended Phase-2 prerequisite. Abstract the lazy disk-walk in scripts/telemetry/dashboard_server.py::_extract_live_events behind a Callable[[], list[LiveEvent]] seam so the Phase 2 background watcher can swap in cleanly without changing the route handler.
- **Files/scope**: scripts/telemetry/dashboard_server.py (added _default_event_source helper, added event_source constructor kwarg on create_app defaulting to functools.partial(_default_event_source, proj_root), route handler now reads via app.state.event_source()); tests/test_dashboard_server.py (two new @pytest.mark.regression tests — custom-source + default-fallback paired guards); memory/bugs/regression-ledger.md (ledger entry +1).
- **Developer-stated motivation**: Direct Phase-2 enabler — Phase 2's background watcher swaps in as one constructor argument (event_source=watcher.snapshot) instead of a route-handler refactor. Drains the REV-20260607-200447 backlog (1→0 open advisories).
- **Explicit constraints**: Default behavior MUST be preserved byte-for-byte (Phase 1 lazy-fold-from-disk within LIVE_FOLD_LOOKBACK_MINUTES). All existing AC1-AC9 invariants (bind, host guard, no-inject, read-only DB, CSP, escape, generic errors) MUST remain intact. No security regressions, no API surface changes beyond the new optional kwarg.

---

## Turn 2 — qa-specialist (proposal)
*2026-06-08T02:07:55.676228+00:00 | confidence: 0.9*
*tags: blocking:0, med:1, low:4, info:0, arch-f2*

## QA-Specialist Findings

Verdict: APPROVE-WITH-CHANGES. 0 BLOCKING / 1 MED / 4 LOW. Seam implementation sound; paired guards correctly pin the contract.

**F1 MED — test_dynamic_lane_fields_are_html_escaped silently depends on dynamic name lookup** (tests/test_dashboard_server.py:402-409). The existing AC6 XSS guard works correctly today because _default_event_source resolves _extract_live_events at call time via module namespace, so monkeypatch.setattr reaches it. A future refactor of _default_event_source to capture the symbol as a closure variable (or to call _extract_live_events through any other indirection) would silently degrade this test to a no-op (empty fixture root → no events → assertion 'no <script> in r.text' trivially passes). Fix: migrate the test to use create_app(..., event_source=fake_events) directly — same pattern as the new sentinel test. Removes the implicit dynamic-lookup dependency and makes AC6 coverage durable.

**F2 LOW — event_source raising is not independently pinned**. The route catches Exception and returns generic 500, but the specific 'Phase 2 watcher crashed' failure mode has no named guard. Recommend adding test_live_fragment_event_source_exception_returns_generic_500 asserting AC6 generic-error contract (no class name, no marker leak in body).

**F3 LOW — non-list iterable return type unenforced**. Annotation says Callable[[], list[LiveEvent]] but a generator/tuple/None return would pass through. Genuine but speculative; skip unless Phase 2 watcher interface is being finalized now.

**F4 INFO — app.state.event_source mutability advisory**. Plain attribute; nothing prevents post-construction rebind. Starlette state is mutable by design; documentation concern only.

**F5 LOW — default test could pin partial wrapper for tighter contract**. Adding 'assert isinstance(app.state.event_source, partial)' makes the test claim more precise ('default seam is partial(_default_event_source)') than the current 'SOME path calls _extract_live_events'.

Strengths: sentinel lane ID is physically impossible on empty tmp_path → genuinely falsifiable; identity check (is custom_source) catches lambda-wrap regressions; module-level _default_event_source (not inline) tracebackable + independently testable.

---

## Turn 3 — architecture-consultant (proposal)
*2026-06-08T02:08:27.765405+00:00 | confidence: 0.88*
*tags: blocking:0, med:1, low:2, info:4, arch-f2*

## Architecture-Consultant Findings

Verdict: APPROVE. 0 BLOCKING / 1 MED / 2 LOW / 4 INFO. Seam at correct abstraction level; default-at-construction is right; Prime Objective clean.

**F1 MED — app.state.project_root is now vestigial** (scripts/telemetry/dashboard_server.py:511). The line app.state.project_root = proj_root no longer has any consumer (route used to read it; seam now captures proj_root via partial closure). Grep confirms zero readers across repo. Worse failure mode: a future contributor sees the attribute, assumes it's canonical, reads it from a new route — diverging from the root the seam was actually constructed against (e.g. if Phase 2 watcher is bound to a different root). Fix: delete the assignment now (clean break — the seam carries the dependency). Alternative: retain with diagnostic-only comment + a regression test that custom event_source doesn't need a matching project_root.

**F2 INFO — Callable shape is correct; do NOT escalate to Protocol**. Phase 2's watcher owns its own lifecycle; lifecycle belongs in FastAPI's lifespan (watcher.start before yield, watcher.stop in teardown), NOT on the seam. A Protocol with snapshot()+start()+stop() would leak responsibility upward. Callable[[], list[LiveEvent]] is the most-restrictive type admitting both partial and bound method.

**F3 INFO — default-resolution at construction is correct (not lazy on first request)**. Construction-time keeps the identity invariant assertable (test's 'is custom_source' pin); lazy would introduce a concurrency race + 'did the seam resolve?' failure mode. Tests vary proj_root by constructing fresh apps (cheap).

**F4 LOW — lifecycle ownership for Phase 2 watcher needs naming in the lifespan docstring** (lines 475-482). Seam docstring names 'Phase 2 swap = one constructor arg' (good), but the SECOND Phase 2 need — watcher.start/stop lifecycle — has no signpost in the lifespan context manager. A future contributor might attach watcher.start to the seam itself rather than to lifespan. Add a one-liner: 'Phase 2 attaches watcher.start() here before yield and watcher.stop() in teardown, paired with event_source=watcher.snapshot constructor arg.'

**F5 INFO — Rule of Three exception is justified**. Seam IS premature under strict Rule-of-Three (only one consumer today), BUT the second consumer (Phase 2 watcher) is named + sized + shaped in ADR-0020 and REV-20260607-200447 — that is the canonical 'Rule of Two with named Phase 2' exception. Land it now. Track Phase 2 slip as a re-evaluation trigger.

**F6 LOW — _default_event_source naming hygiene**. Symbol name doesn't signal phase-scoped lifetime. No rename (regression-ledger reference is now load-bearing), but a one-line comment near line 410 like '# Sunsets when Phase 2 watcher lands (arch F2)' makes Phase 2 grep-discoverable.

**F7 INFO — Prime Objective check clean**. (a) attribution preserved (structural refactor of one developer's code); (b) no labor for third party; (c) no derivative-data accumulation. Three NOs = no extraction risk.

Strengths: seam at correct abstraction (Callable not Protocol); default behavior preserved byte-for-byte; paired regression guards pin contract from both sides; mark_orphans non-call comment correctly carried forward; module-level helper placement; regression-ledger entry exemplary.

---

## Turn 4 — facilitator (critique)
*2026-06-08T02:11:12.803047+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 9 verified, 0 inconclusive, 0 discarded. All file:line references in qa + arch findings confirmed against post-fold code. arch F1 vestigial-attribute claim independently re-confirmed by grep ('app.state.project_root' has zero readers across scripts/ + tests/ post-fold). qa F1 dynamic-lookup dependency reproduced by reading tests/test_dashboard_server.py:402-409 (confirmed monkeypatch + no event_source= kwarg). Both MED findings have falsifiable mechanisms — they would silently regress if folded later. Folding now.

---

## Turn 5 — facilitator (synthesis)
*2026-06-08T02:11:37.814798+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:4, speculative:0, model-tiers:qa-specialist:sonnet+architecture-consultant:sonnet+facilitator:opus, arch-f2*

## Request Context
- **What was requested**: Close the LAST originating REV-20260607-200447 advisory (arch F2 event-source seam). Abstract the lazy disk-walk in scripts/telemetry/dashboard_server.py::_extract_live_events behind a Callable[[], list[LiveEvent]] seam so Phase 2's background watcher can swap in cleanly without changing the route handler.
- **Files/scope**: scripts/telemetry/dashboard_server.py + tests/test_dashboard_server.py + memory/bugs/regression-ledger.md.
- **Developer-stated motivation**: Direct Phase-2 prereq; drains REV-20260607-200447 backlog (1→0).
- **Explicit constraints**: Default behavior MUST be preserved byte-for-byte; AC1-AC9 invariants MUST remain intact.

## Verdict
**APPROVE-WITH-CHANGES → APPROVE post-fold**. Quality gate 7/7 (60 dashboard_server tests; ledger 36 guards; ruff format + check clean).

## Findings Summary
- qa-specialist 0.90 + architecture-consultant 0.88. Convergent verdict: 0 BLOCKING / 2 MED / 6 LOW/INFO.
- **2 MED folded in-session**: (qa F1) test_dynamic_lane_fields_are_html_escaped migrated to event_source= constructor arg (removes opaque dynamic-lookup dependency that would silently degrade AC6 XSS coverage); (arch F1) vestigial app.state.project_root assignment deleted (replaced with explanatory comment so seam stays single source of truth — prevents future divergence when Phase 2 watcher binds to a different root via its own constructor).
- **2 LOW folded in-session**: (qa F5) added isinstance(partial) + .func is _default_event_source assertions to fallback test (pins default seam shape, not just that 'some path calls _extract_live_events'); (arch F4) lifespan docstring now signposts Phase 2 watcher.start/stop attachment point.
- **4 LOW/INFO deferred-as-advisory**: qa F2 (event_source raising → generic 500 — already covered by route's except Exception; nice-to-have named test), qa F3 (non-list iterable return — speculative; defer to Phase 2 watcher interface finalization), qa F4 (app.state.event_source mutability — Starlette state is mutable by design; documentation concern only), arch F6 (sunset comment on _default_event_source — regression-ledger entry already names Phase 2 sunset).
- 4 INFO design-rationale items recorded: arch F2 (Callable correct, not Protocol — lifecycle belongs on lifespan); arch F3 (construction-time resolution correct, not lazy); arch F5 (Rule-of-Two-with-named-Phase-2 exception justified); arch F7 (Prime Objective clean, no extraction risk).

## Convergence Note
qa + arch hit ORTHOGONAL surfaces: qa on test-precision (does the seam contract have falsifiable guards?), arch on state-hygiene (does the seam leave any vestigial coupling?). Both independently confirmed the Callable[[], list[LiveEvent]] shape + the construction-time default resolution as correct. The 4 in-session folds cohere on the same surface — one production-code fold (deleting the vestigial attribute) + one production-code addition (lifespan docstring) + two test-file folds (migrating the AC6 test + tightening the fallback test). REV-20260607-200447 backlog: **1 remaining → 0 (FULLY DRAINED)**.

## Speculative findings
0 in speculative section (no confidence <0.80). 0 unscored.

## Model tiers
qa-specialist:sonnet, architecture-consultant:sonnet, facilitator:opus.

## Education gate
Not needed. Refactor of a single well-understood seam; the seam shape is the same one REV-20260607-200447 prescribed verbatim; both reviewers gave APPROVE rationale signoff. Standard /walkthrough + /quiz would not surface anything the docstrings + ledger entry don't already pin.

---
