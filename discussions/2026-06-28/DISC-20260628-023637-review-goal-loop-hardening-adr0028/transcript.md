---
discussion_id: DISC-20260628-023637-review-goal-loop-hardening-adr0028
started: 2026-06-28T02:36:37.853359+00:00
ended: 2026-06-28T03:50:32.592340+00:00
agents: [facilitator, independent-perspective, qa-specialist, security-specialist]
total_turns: 6
---

# Discussion: DISC-20260628-023637-review-goal-loop-hardening-adr0028

## Turn 1 — facilitator (evidence)
*2026-06-28T02:36:37.853359+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- What was requested: independent /review of the ADR-0028 goal-loop reliability hardening (safety-critical control-flow) before commit. Steward APPROVED (0.88) with 4 required build-obligations; this review verifies the BUILD delivered them.
- Files/scope: scripts/goal_loop.py (6 changes: H1 qg-only reject, protected_paths field+parse+tripwire+_normalize_path, _SENSITIVE_PATH_RE, H2 branch protect, seam-2b poll fix, always-skeptic-on-goal-met=R5.4); tests/test_goal_loop.py (+42), tests/test_notify.py (+3); prose: authoring SKILL Step0/coaching, template, testing_requirements rule; docs/adr/ADR-0028; lineage BACKFLOW event.
- Motivation: first real /goal-loop use in VerificationPortal surfaced these defects (two adversarial review rounds). Reconcile VP ref fix 2ab77352 (itself REQUEST-CHANGES) into the hub; seam-2b is LIVE on public main.
- Constraints: fork-only commit (no push); keep notify.py body-first (do NOT take VP title-first); always-skeptic must be framed as R5.4 impl not new decision.
- Orchestrator pre-verification (confirm or refute): always-skeptic uses model.judge (independent checker), never verifier.run_command (builder); red skeptic PARKs (no self-green); seam-2b drives poll not check. OPEN CONCERN for reviewers: the REAL collab_loop poll exit semantics are unverified (unit-tested only via injected runner) -- if poll does not exit on a match, every AFK gate blocks the full _NTFY_GATE_POLL_SECONDS=3600 (correctness-safe but a UX/integration defect mirroring the very Lesson-2 transport seam being fixed). Verify against scripts/collab_loop.py poll.

---

## Turn 2 — security-specialist (proposal)
*2026-06-28T02:47:15.144177+00:00 | confidence: 0.86*
*tags: security, verifier-integrity, seam-2b*

approve-with-changes, conf 0.86. All 5 required safety guarantees verified SOUND: always-skeptic routes via model.judge (independent checker) never the builder verify, runs unconditionally regardless of shape, red verdict PARKs fail-closed (no self-green); seam-2b drives poll not check + REPLY-MATCH-only + allow-list label (untrusted-reply honored); protected_paths fail-closed (empty/leading-slash rejected, shared _normalize_path); H2 casefold+refs-strip+construction+per-tick defense-in-depth; seam-2b test genuinely fails on old check-based code. F1 MEDIUM: real collab_loop poll is while-True never-exit, so subprocess.run(timeout=3600) blocks the FULL hour every gate; approval NOT dropped (captured via TimeoutExpired.stdout + flush=True) so correctness-safe but undercuts AFK value prop; fix = exit-on-match poll. F2 LOW (pre-existing, not new to ADR-0028): delta.added_lines interpolated unfenced into judge_prompt (always-skeptic reuses path); follow-on, fence like anchor_context.

---

## Turn 3 — qa-specialist (proposal)
*2026-06-28T02:47:15.259124+00:00 | confidence: 0.92*
*tags: qa, test-efficacy*

approve, conf 0.92. 236 tests pass; every ADR-0028 guard has a revert-proof test; seam-2b (4 assertions incl ANSWER-MATCH-only returns None = fails on old code) and B3 FlipVerifier (PARKED + skeptic-in-report + all-author-criteria-green rules out criterion-red park) are strongest in suite; H2 7-variant + protected_paths 6-variant parametrized; 2a bind-shape revert-proof. Nits (all effective as-is): B3 set max_iterations=99 to remove MAX_ITERATIONS as confounder; assert modes==[ask,poll] to pin ordering; add comment to the two permissive validate tests.

---

## Turn 4 — independent-perspective (proposal)
*2026-06-28T02:47:15.389426+00:00 | confidence: 0.83*
*tags: independent, anti-groupthink, design-fork*

approve-with-changes, conf 0.83. F1 HIGH: skeptic-veto path (goal_loop.py:965) goes straight to _finish(PARKED) but _backstop_only docstring (576-581) says IT decides park-vs-keep-building on veto -> dead code on its intended path AND a single stochastic llm-judge red terminally strands a legitimately-complete run. GENUINE DESIGN FORK surfaced to developer (Retry consult-ladder / Park terminal / Human adjudicate-at-goal-met-gate). F2 HIGH: transport happy path only tested vs a fake runner returning instantly; real poll never returns, so the gate hinges on subprocess timeout-stdout salvage (CPython detail, Windows-flaky) = feedback_smoke_test_fidelity gap; fix = bounded poll that actually returns + a real-poll contract test. F3 MEDIUM: no cross-module test binding the REPLY-MATCH parser to collab_loop emitter (the exact Lesson-2 drift class re-armed); cheap, do now. F4 MEDIUM: transport poll collides with a standing developer poll Monitor over the single poll-lock (matches feedback_ntfy_one_monitor_at_a_time / supervisor-orphan incidents) -> reply routes to wrong poller, silent re-park; document + assert lock ownership. Also: dead isinstance(raw,bytes) branch under text=True.

---

## Turn 5 — facilitator (critique)
*2026-06-28T02:47:15.513904+00:00 | confidence: 0.8*
*tags: finding-verification, synthesis-pending*

3-panel convergence: core design SOUND (security 0.86 / qa 0.92 / independent 0.83), all approve-with-changes, 2 HIGH. The skeptic-veto semantics (independent F1) is a genuine verifier-integrity design fork on the loop's terminal behavior -> surfaced to the developer via ntfy (Retry/Park/Human), NOT resolved unilaterally (autonomous invariant: stop on genuine design fork; high-risk-grill: no pre-loaded recommendation). The seam-2b poll-test-fidelity cluster (independent F2 + security F1) has a clear fix (bounded poll that returns + real-poll contract test) to apply regardless. F3 contract test + F4 poll-lock doc = same-change hardening. Security F2 (unfenced delta in judge_prompt) = pre-existing follow-on. Holding fix application + commit until the developer's veto decision lands.

---

## Turn 6 — facilitator (synthesis)
*2026-06-28T03:50:32.592340+00:00 | confidence: 0.85*
*tags: blocking:2, advisory:6, speculative:1, model-tiers:security-specialist:opus|qa-specialist:sonnet|independent-perspective:sonnet*

VERDICT: approve-with-changes (conf 0.85). 3-panel consensus: core design SOUND (always-skeptic genuinely independent + fail-closed; protected_paths fail-closed; H2 defense-in-depth; tests revert-proof; gate 7/7, 236 tests). 2 HIGH required before merge: (1) skeptic-veto semantics = a genuine verifier-integrity DESIGN FORK (Retry/Park/Human) surfaced to the developer via ntfy and PENDING their decision -- not resolved unilaterally (autonomous invariant: stop on genuine design fork); also fixes the dead _backstop_only docstring/code disagreement. (2) seam-2b poll test-fidelity: bounded poll that returns + real-poll contract test; touches collab_loop.py, deliberately DEFERRED because the autonomous session was using that channel to reach the developer. Medium: poll-lock single-poller doc (F4), cross-module contract test (F3). Advisory: QA test-hardening nits; security F2 (unfenced delta in judge_prompt) is pre-existing follow-on. NOT committed -- the 2 HIGH are the remaining work. Education gate REQUIRED (goal-loop, Tier 2). REV-20260628-024000.

---
