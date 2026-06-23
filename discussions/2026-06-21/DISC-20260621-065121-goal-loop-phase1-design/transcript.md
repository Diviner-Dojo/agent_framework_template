---
discussion_id: DISC-20260621-065121-goal-loop-phase1-design
started: 2026-06-21T06:51:52.849698+00:00
ended: 2026-06-21T07:04:20.561018+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist, security-specialist, steward]
total_turns: 8
---

# Discussion: DISC-20260621-065121-goal-loop-phase1-design

## Turn 1 — facilitator (evidence)
*2026-06-21T06:51:52.849698+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Developer ran /deliberate asking (1) should the framework's agent definitions evolve toward loop orchestration, and (2) how to build loop-orchestration to drive development speed AND quality. The session reframed into a research pass (2026 loop-engineering landscape) then a 22-question design grill, producing SPEC-20260621-064937-goal-loop-phase1. This deliberation evaluates that Phase-1 spec before build.
- **Files/scope**: SPEC-20260621-064937-goal-loop-phase1.md (Phase-1 MVP of a new /goal-loop capability); design rationale captured in brainstorms/2026-06-20-loop-orchestration.md (Q1-Q22). Touches an agent definition (.claude/agents/facilitator.md), so framework-evolution rules apply.
- **Developer-stated motivation**: The AI industry moved to agent-loop orchestration; the developer believes the facilitator could be a good loop orchestrator, and that what is missing is emphasis on the goal (grill-me cited as a guide). Goal: drive both speed and quality of development.
- **Explicit constraints**: hub-level capability (propagates to derived projects); ntfy gate parity is load-bearing (an AFK developer must approve from their phone treated exactly like sitting at the keyboard); the agent-definition change must be surgical (exactly ONE agent, the facilitator, gains ONE subsection; 10 specialists unchanged); education walkthrough required even for low-risk loops; Phase 1 is manual-invoke and L1/L2 only (no L3, no triggers); all non-negotiables (no push, no auto-merge, capture, /review, Principle #4) must hold INSIDE the loop.

---

## Turn 2 — steward (proposal)
*2026-06-21T07:02:09.089230+00:00 | confidence: 0.84*
*tags: steward, disposition:revise, design-review*

Steward disposition: REVISE (conf 0.84). Credits the proposal for adapting loop-engineering TO the non-negotiables rather than around them, and for reusing primitives. Principle #4: the per-tick checker reuses the EXISTING running-build-checkpoints independent-checker primitive (verified) so independence holds for correctness; RESIDUAL GAP: the conductor alone evaluates the termination ladder and can mark an LLM-as-judge criterion green with no independent check until goal-met. Principle #6: education-required-even-for-low-risk is philosophically RIGHT, not over-correction (unwatched production removes the human-attendance variable that normally lets education scale down); keep it, but it must mean required-to-MERGE not required-to-terminate. Principle #8: the facilitator delta is the minimum HONEST change (skill-only would be dishonest since the facilitator arc is wall-to-wall single-pass synthesis) but the subsection MUST name the posture switch + the /review-synthesis boundary. Prime Objective: served (loop reads authority, never elevates; attribution preserved) with a VELOCITY-DRIFT watch-item: cheaper compounding production raises volume through the same human gates, so Phase-2 L3/triggers must be conditional on cost + gate-throughput telemetry. THREE REVISE ITEMS: (1) judge-verified criteria checked by the independent checker not the conductor + AC; (2) the facilitator subsection states the posture switch + boundary, AC9 asserts it; (3) record velocity-drift as a Phase-2 precondition. Resolves the grill fork: one subsection IS enough IF it names the posture switch. The developer Principle-#7 approval is required regardless of disposition.

---

## Turn 3 — architecture-consultant (proposal)
*2026-06-21T07:02:09.153731+00:00 | confidence: 0.82*
*tags: architecture, design-review*

Architecture (conf 0.82). Decomposition correct (command/skill/agent-delta mirrors /build_module to running-build-checkpoints); CORE/SKIN split is the strongest seam; no ADR contradicted. F1 HIGH: the reuse claim is structurally false. /build_module is a ONE-SHOT terminal workflow (creates its own discussion at turn 1, runs its own gate, closes its own discussion, sets spec complete) NOT a tick primitive; a loop re-invoking it would NEST discussions and break R7/AC7 one-discussion-per-run. Honest framing = conductor over the same PRIMITIVES (code-gen + running-build-checkpoints + quality_gate), not over the commands; fix the Context prose + factor the shared checkpoint logic. F2 MED: loop-state is NEW state machinery, not mirroring /deliberate state.json (a coarse phase marker) or grill-me; hazards = stale green after later edits, torn write on crash, loop-state vs append-only events disagreement. Fix: the deterministic gate is the source of truth on reconstruct (re-verify, do not remember), events are the tiebreaker, atomic temp+rename write. F3 MED: the goal-contract vs /plan-spec seam leaves direction-of-authority undefined; make the spec upstream and the contract a derived projection with a derived_from:SPEC field; /plan emitting a contract is an UNDECLARED edit to plan.md (add to Affected Components). F4 LOW: cannot assert one-subsection SUFFICES before the skill is written (needs a build-time tripwire). F5 INFO: the new top-level loops/ dir must be added to CLAUDE.md Directory Layout and governed by the owed ADR.

---

## Turn 4 — independent-perspective (proposal)
*2026-06-21T07:02:09.226347+00:00 | confidence: 0.78*
*tags: independent-perspective, design-review, reward-hacking*

Independent-perspective (conf 0.78). Names a CONFIRMATION LOOP: 19 of 22 grill answers were agree/yes/ok and the single highest-risk question was never asked. CRITICAL HOLE: nothing defends against the loop GAMING ITS OWN VERIFIER (reward hacking). Cheap builders + budget pressure + the no_progress rung is the textbook trigger; the builder can hard-code tests, weaken assertions, add a no-cover pragma, or monkeypatch the scorer; LLM-as-judge criteria are easiest to game; no criterion/AC/rung detects verifier-passed-without-the-work-done. Pre-mortems: A gamed gate (Med-High likelihood, High impact; mitigate by flagging any tick whose diff touches test files / gate config / pragmas / the verify command => human gate); B hollow re-green (a later tick regresses an earlier green that was not re-verified => re-verify ALL criteria on the goal-met candidate); C revoked-but-running (re-read authorization each tick); D budget blown mid-tick (the rung is tick-boundary only); E starter recipes teach gameable shapes (add a 4th coaching principle: prefer verify methods the builder cannot edit). HONESTY: the /loop command + Workflow tool do NOT exist in .claude/commands (they are HARNESS features, not repo artifacts) so the 80pct-owned-primitives claim is inflated; genuinely owned = quality_gate, /review, the /build_module loop, collab_loop, capture. ALT 1 (most important, grill skipped): put the control loop in a DETERMINISTIC scripts/goal_loop.py driver (tick counter, budget, ladder, loop-state, re-verify) calling the model only for build + judge; control flow should not be prose followed under context pressure; mitigates B/C/D. ALT 2: a dedicated loop-conductor agent vs a facilitator mode-switch. /goal-loop overlaps ~40pct with /build_module iterate-to-green; the spec must justify sibling-not-extension. PROCESS: high-risk grills should pose the top forks WITHOUT a recommended answer; anti-groupthink fired post-hoc is damage assessment, not prevention.

---

## Turn 5 — security-specialist (proposal)
*2026-06-21T07:02:09.288934+00:00 | confidence: 0.83*
*tags: security, design-review*

Security (conf 0.83). The core bounding is correct + load-bearing: no push / no auto-merge at EVERY level means a worst-case spoofed approval is only a recoverable local commit on a feature branch; this holds every finding severity down. F1 MED: a matched label authorizes A-commit, not THIS-commit; match_choice (collab_loop.py:245) is a stateless string compare with no nonce/tick-id, so replay or pre-arm of Approve can commit an unreviewed delta and defeats ntfy-equals-keyboard. Fix: bind each commit gate to its tick (per-gate nonce or diff-hash + one-shot consumption that clears the open-gate marker). F2 MED: loop-state is an untrusted input on reconstruct but the spec does not mark it so; a one-line edit flipping red to green makes the conductor SKIP verification (never-redo-green). Fix: re-derive deterministic criteria on reconstruct, cross-check claimed greens against append-only checker-turn events, integrity-hash the counters, park on mismatch; AC8 must test that a tampered false-green does NOT skip verify. F3 MED: reads-authorization-and-caps-itself fails OPEN; the block is branch-scoped (never main) + until-revoked, yet AC12 only tests main, not wrong-feature-branch or revoked. Fix: a positive branch-checked CAPTURED affirmation before the first commit; drop to L1 if any clause is unaffirmable. F4 MED: prompt injection via anchor_context/goal text into the conductor + checker (re-injected on every reconstruct); a poisoned anchor can say mark-green-skip-verify or make the checker rubber-stamp. Fix: delimit anchor content as untrusted DATA and enforce green-iff-verify-passed-never-iff-prose; matters because this is a hub capability propagating to multi-party derived projects. F5 LOW: REPLY-INVALID handled identically to timeout (no action, re-ask/park); at most ONE open ntfy gate at a time; inherit the single-poller + orphan-recovery discipline.

---

## Turn 6 — qa-specialist (proposal)
*2026-06-21T07:02:09.365431+00:00 | confidence: 0.87*
*tags: qa, design-review, verifiability*

QA (conf 0.87). The central claim (done is machine-decidable) has 3 structural gaps that would make the guarantee hollow. F1 HIGH: the LLM-as-judge escape hatch is ungoverned; an all-judge contract is schema-valid and passes AC1, and if the conductor (not the checker) runs the judge, R9 independence collapses on judge criteria. Fix: AC-J1 reject all-judge contracts (require at least one deterministic anchor); AC-J2 the judge call is issued by the independent checker (not builder, not conductor) asserted by distinct agent IDs; schema max_judge_fraction. F2 HIGH: same-red-criterion for no_progress is UNDEFINED (3 interpretations) so oscillation (A red=>green=>red) can evade both goal_met and no_progress while AC4 still passes. Fix: define the semantics + AC4-osc with a mock checker that alternates. F3 HIGH: resumability has no test for FALSE-green carryover; if a green criterion backing artifact changes between sessions, loop-state still shows green and skips re-eval; need a content-hash/mtime per green or an explicit logged skip; AC8-neg. F4 MED: per-tick checker independence is asserted by PRESENCE not behavior (AC5); a checker echoing builder reasoning is a rubber-stamp; need AC5-adversarial (seed a builder defect, assert the checker catches it) + the checker gets delta-only with no builder reasoning. F5 MED: budget accounting unspecified (which counter, when checked, partial-tick disposition); specify output-tokens, check after a complete tick, partial tick not committed to loop-state. F6 MED: AC2 is missing the critical-risk-accepted-but-stamped-L1 branch test. F7 LOW: AC7 capture is presence-only (no event ordering/min-count). F8 LOW: AC6 gate parity needs a FakeCollabLoop fixture spec. F9 HIGH/blocking: a regression-ledger entry is required BEFORE the first commit.

---

## Turn 7 — facilitator (synthesis)
*2026-06-21T07:04:20.497138+00:00 | confidence: 0.83*

## Request Context
- **What was requested**: Deliberate on SPEC-20260621-064937-goal-loop-phase1 before build, and thereby answer the developer's two framing questions (should agent definitions change; how to build loop-orchestration for speed AND quality).
- **Files/scope**: SPEC-20260621-064937-goal-loop-phase1.md; design rationale in brainstorms/2026-06-20-loop-orchestration.md (Q1-Q22). Touches .claude/agents/facilitator.md, so framework-evolution rules apply.
- **Developer-stated motivation**: adopt the 2026 loop-engineering pattern; the facilitator as loop orchestrator; emphasis on the goal (grill-me as guide); drive speed and quality.
- **Explicit constraints**: hub-level; ntfy gate parity load-bearing; surgical agent-def change (1 agent); education required even for low-risk loops; Phase 1 manual + L1/L2 only; all non-negotiables hold inside the loop.

## Verdict: REVISE (approve-with-significant-changes) - confidence 0.83
The shape (conductor + goal contract + governed gates), the hub altitude, and the agent-definition minimalism are right, and the Steward AFFIRMS THE DIRECTION (REVISE 0.84, not decline). But the panel converged on one gap that blocks build, plus a genuine architectural fork the grill never posed.

## The cross-cutting signal (3 specialists, 3 lenses, ONE gap)
VERIFIER INTEGRITY / reward hacking. independent-perspective (anti-groupthink), qa-specialist (verifiability), and security-specialist (trust) INDEPENDENTLY hit the same hole: the loop can make its own verifier pass WITHOUT doing the work (hard-coded tests, weakened assertions, coverage pragmas, a monkeypatched scorer; LLM-as-judge criteria are easiest to game). Nothing in the spec - no criterion, no AC, no termination rung - detects it. The grill optimized the human-in-the-loop surface and never guarded the machine-decides-done surface, which is the actual novelty of this capability. This is the headline finding.

## BLOCKING before build
1. VERIFIER-INTEGRITY DEFENSE as a Phase-1 requirement + ACs: flag any tick whose diff touches test files / gate config / coverage pragmas / the criterion's own verify command -> forced human gate; re-verify ALL criteria on the goal-met candidate (no stale green); the never-skippable walkthrough must surface HOW each criterion was met. [independent A/B, qa F2, steward judge-gap, security F2]
2. LLM-AS-JUDGE GOVERNANCE: reject all-judge contracts (require >=1 deterministic anchor); the judge call is issued by the INDEPENDENT CHECKER, never the conductor; cap the judge fraction; green-iff-verify-passed-never-iff-prose. [qa F1, steward item 1, security F4]
3. LOOP-STATE UNTRUSTED ON RECONSTRUCT: re-derive deterministic criteria, cross-check claimed greens against append-only checker-turn events, integrity-hash counters, atomic temp+rename write, park on mismatch; add AC8-neg (a tampered false-green must NOT skip verify). [architecture F2, security F2, qa F3]
4. NO_PROGRESS OSCILLATION: define same-red-criterion semantics; add AC4-osc with an alternating mock checker (else A red->green->red evades both goal_met and no_progress and AC4 still passes). [qa F2]
5. REUSE-HONESTY (VERIFIED): reframe as conductor over PRIMITIVES (code-gen + running-build-checkpoints + quality_gate), NOT over /build_module the command - which is one-shot and owns its own discussion+gate+close (verified at build_module.md:63 create, :221 close, :237 status->complete); and CUT the /loop + Workflow tool owned claim - they are harness features with no repo artifact (verified: no .claude/commands/*loop*). [architecture F1, independent]
6. REGRESSION-LEDGER entry before the first commit (ledger rule, blocking). [qa F9]

## REQUIRED folds (incorporate before /plan)
7. The facilitator subsection MUST name the posture switch (single-pass synthesis vs iterate-to-criteria) + the /review-synthesis boundary; AC9 asserts the CONTENT, not just diff size. This RESOLVES the grill's pre-asked fork: one subsection IS enough WITH this content (steward + architecture concur). [steward item 2, architecture F4]
8. AUTHORIZATION FAIL-CLOSED: a positive, branch-checked, CAPTURED affirmation before the first commit; re-read the block each tick (revoked-but-running); extend AC12 to wrong-feature-branch + revoked. [security F3, independent C]
9. NTFY GATE BINDING: per-gate nonce or diff-hash + one-shot consumption; REPLY-INVALID treated like timeout; at most one open gate at a time. [security F1/F5]
10. ANCHOR_CONTEXT delimited as untrusted DATA (prompt injection); green never settable by prose. [security F4]
11. /PLAN-SPEC SEAM: spec upstream, contract a derived projection (derived_from:SPEC); declare the plan.md edit in Affected Components. [architecture F3]
12. BUDGET ACCOUNTING: output-tokens, checked after a complete tick, partial tick not committed. [qa F5]
13. CHECKER INDEPENDENCE behavioral test: AC5-adversarial (seed a builder defect, assert the checker catches it); checker gets delta-only, no builder reasoning. [qa F4]
14. AC COMPLETENESS: AC2 critical-risk-stamped-L1 branch; AC7 event ordering/min-count; AC6 FakeCollabLoop fixture. [qa F6/F7/F8]
15. VELOCITY-DRIFT = Phase-2 precondition: cost + gate-throughput telemetry must exist before L3/triggers are blessed. [steward item 3]
16. Add loops/ to CLAUDE.md Directory Layout; the owed framework-scope ADR records the CORE/SKIN/additive-merge contract. [architecture F5]

## The GENUINE FORK - developer's call (NOT resolved here, per Rule #5)
independent-perspective surfaced an alternative the grill never considered: put the control loop in a DETERMINISTIC scripts/goal_loop.py DRIVER (owning the tick counter, budget tally, termination ladder, loop-state read/write + integrity, and re-verify-on-reconstruct), calling the model only for the build + judge steps - rather than authoring control flow as prose in a skill the model must follow faithfully across 8 ticks and a possible compaction. Convergent support: architecture's new-state-machine hazards (F2), qa's testability gaps, security's re-derive-on-reconstruct. This single decision dissolves much of BLOCKING-1/3 and REQUIRED-8/12 at once - but materially enlarges the Phase-1 build. FACILITATOR LEAN: a HYBRID - the deterministic driver owns the safety-critical bookkeeping; the skill/model owns build + judge + gate-routing. This is a real fork and the developer's decision; it re-touches the spec.

## Dissent / honesty (not smoothed over)
- independent-perspective is CORRECT that the facilitator-delta fork was pre-resolved in the grill (Q10), so on that question the deliberation only confirmed. But it surfaced a BIGGER, genuinely-open fork (the deterministic-driver alternative) the grill never posed - so the deliberation was not ritual.
- PROCESS finding worth adopting framework-wide: for risk:high design grills, pose the top 2-3 forks WITHOUT a recommended answer. The grill-me recommended-answer discipline is right for AUTHORING (reducing a manager-gatekeeper's blank-page cost) but it pre-loads ratification when DE-RISKING. The 19/22 agree rate is the measurable tell.

## Facilitator observation
The deliberation vindicates the grill->deliberate->steward sequence: the agreeable grill produced a well-governed design but suppressed exactly the one risk axis (verifier trust) that independent evaluation exists to catch. That is Principle #4 working as designed. Survival check: every dispatched specialist's findings survive into this synthesis.

---

## Turn 8 — facilitator (decision)
*2026-06-21T07:04:20.561018+00:00 | confidence: 0.83*

DECISION: REVISE. The /goal-loop Phase-1 design is approved IN DIRECTION (Steward affirms) but must NOT proceed to /plan/build until: (a) the developer decides the GENUINE FORK - deterministic scripts/goal_loop.py driver vs prose-skill control flow (facilitator lean: hybrid driver-owns-bookkeeping); (b) the 6 BLOCKING items are incorporated into the spec - led by a verifier-integrity defense (the panel's convergent #1 gap), LLM-as-judge governance, loop-state-untrusted-on-reconstruct, no_progress oscillation semantics, the reuse-honesty corrections, and the pre-commit regression-ledger entry; (c) the 16 REQUIRED folds land, including the facilitator subsection naming the posture switch + /review boundary (which resolves the agent-def fork to YES-with-content); and (d) the developer grants the Principle-#7 approval of the facilitator delta. A framework-scope ADR is owed (records the loops/ CORE/SKIN/additive-merge contract and the velocity-drift Phase-2 precondition). Confidence 0.83 (weighted across steward 0.84, qa 0.87, security 0.83, architecture 0.82, independent 0.78).

---
