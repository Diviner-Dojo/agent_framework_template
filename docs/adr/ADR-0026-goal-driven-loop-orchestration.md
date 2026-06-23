---
adr_id: ADR-0026
title: "Goal-Driven Loop Orchestration (/goal-loop)"
status: accepted  # developer Principle-#7 approval of the facilitator "Goal-Seeking Loop Mode" delta granted 2026-06-21
date: 2026-06-21
decision_makers: [facilitator, steward, architecture-consultant, independent-perspective, security-specialist, qa-specialist]
discussion_id: DISC-20260621-065121-goal-loop-phase1-design
supersedes: null
risk_level: high
scope: framework  # hub capability; propagates to all derived projects (Phase 3)
confidence: 0.83
tags: [loop-orchestration, agent-loops, goal-contract, facilitator, framework-evolution, verifier-integrity]
---

## Context

The 2026 AI-engineering shift is "loop engineering": leverage moved from writing good prompts to
designing the **system that prompts the agent** — a `trigger → action → verify → stop` loop that
iterates toward a goal and halts on a verifiable stop condition (Berman Loop Library, the Ralph
loop, Claude Code `/goal`). This framework already has *reflection* loops (`/meta-review`, `/retro`,
build checkpoints) but no goal-driven *execution* loop: the facilitator orchestrates a single
review/deliberation pass and stops, rather than iterating build→verify→refine to a defined goal.

The developer asked two questions: (1) should the framework's agent definitions evolve toward loop
orchestration, and (2) how to build loop orchestration to drive development speed **and** quality.
A 22-question design grill (`brainstorms/2026-06-20-loop-orchestration.md`) produced a Phase-1 spec
(`SPEC-20260621-064937`), which a 5-specialist `/deliberate` (`DISC-20260621-065121`) returned at
**REVISE (0.83)** — affirming the direction (Steward REVISE 0.84) while surfacing one gap the grill
never asked about (verifier integrity / reward hacking) and one genuine architectural fork
(deterministic driver vs prose-skill control flow). This ADR records the resulting decision.

## Decision

Adopt **`/goal-loop`** as a framework (hub) capability that pursues a developer-authored **goal
contract** by iterating build→verify→refine until the contract's *verifiable* success criteria are
met, then halts for human `/review` + a required education walkthrough + approval. Key decisions:

1. **Hybrid deterministic driver (the resolved fork).** A deterministic `scripts/goal_loop.py` owns
   all control flow — tick counter, budget, termination ladder, loop-state + integrity,
   re-verify-on-reconstruct. The model (the facilitator in loop-mode, in the main loop) is invoked
   **only** for the build step, the judge step, and gate-routing. Safety-critical control flow is
   code, not model-followed prose under context pressure.

2. **Conductor over primitives, not commands.** The loop reuses the same code-gen +
   `running-build-checkpoints` + `quality_gate` primitives that `/build_module` itself uses — it does
   **not** invoke the `/build_module` command (a one-shot workflow that owns its own
   discussion/gate/close). The earlier "we already own `/loop` + the Workflow tool" framing was
   incorrect (those are harness features, not repo artifacts) and is removed.

3. **The goal is the centerpiece, and authoring is guided.** A 7-field goal contract
   (`success_criteria` + `verify` + `termination` are load-bearing) is authored through a
   grill-flavored interview that also **gatekeeps** non-loop-shaped goals (subjective, exploratory,
   or verifiable-only-via-a-prohibited-action) and routes them elsewhere.

4. **Verifier integrity is a first-class requirement** (the deliberation headline). The loop must
   not satisfy a criterion by altering its own verifier: a tamper tripwire forces a human gate when a
   tick touches tests/gate-config/pragmas/the verify command; green is earned by `verify`, never by
   prose; LLM-as-judge criteria are capped, never all-judge, and judged by the *independent checker*;
   all criteria are re-verified at the goal-met candidate.

5. **Surgical agent-definition change.** Exactly one agent (facilitator) gains one "Goal-Seeking Loop
   Mode" subsection that names the posture switch (single-pass synthesis ↔ iterate-to-criteria) and
   the `/review`-synthesis boundary. The other 10 specialists are unchanged. (Answers the developer's
   Q1: yes, but surgically.)

6. **Governance reused, not reinvented.** Autonomy is governed by the existing Authorization block,
   fail-closed and branch-checked; gates are transport-agnostic with ntfy parity (one-shot,
   per-gate-bound, allow-list-matched); loop-state is untrusted on read; capture is one discussion
   per run; the education walkthrough is required even for low-risk loops.

7. **Phased.** Phase 1 = the manual, L1/L2, fully-governed engine. Phase 2 = triggers + unattended
   L3 + cost telemetry, **gated on a velocity-drift precondition** (per-goal cost + human-gate
   throughput must be instrumented first). Phase 3 = CORE/SKIN propagation via `/apply-framework`.

## Alternatives Considered

### Alternative 1: Prose-skill control flow (the original spec rev 1)
- **Pros**: smaller build; "the facilitator just does it" elegance; no new Python control surface.
- **Cons**: puts a safety-critical, 8-iteration control loop in prose the model must follow
  faithfully across a possible context compaction; weakens budget/ladder/loop-state guarantees.
- **Reason rejected**: independent-perspective (with architecture/qa/security converging) showed the
  least-reliable home for control flow is model-interpreted prose; the developer chose the hybrid
  driver.

### Alternative 2: A new dedicated `loop-conductor` agent
- **Pros**: a single unconflicted directive; leaves the facilitator definition untouched.
- **Cons**: a larger roster change than a subsection; fights the model-tiering policy that the
  orchestrator runs in the main loop, never as a dispatched subagent.
- **Reason rejected**: heavier and policy-fighting; the deterministic driver + a one-subsection
  facilitator delta achieves the same minimal blast radius.

### Alternative 3: Extend `/build_module` rather than a sibling command
- **Pros**: `/goal-loop` overlaps ~40% with `/build_module`'s iterate-until-tests-pass loop; less new
  surface.
- **Cons**: the goal contract, the termination ladder (no-progress/budget/park), and the
  transport-agnostic ntfy gates are a genuinely distinct concern; folding them into `/build_module`
  would overload a one-shot terminal workflow.
- **Reason rejected**: kept as a sibling that **reuses `/build_module`'s primitives** (not the
  command); the spec now states this explicitly.

### Alternative 4: Skill-only, no agent-definition change
- **Pros**: zero agent-definition edits; maximal Principle-#8 minimalism.
- **Cons**: dishonest — the facilitator's definition is wall-to-wall single-pass synthesis; loop-mode
  is a genuine posture shift a loaded skill cannot silently override.
- **Reason rejected**: the Steward judged the one-subsection delta the *minimum honest* change.

## Consequences

### Positive
- A goal-driven execution loop that makes development both faster (cheap-tier build/check repeats
  cheaply) and higher-quality (iterates to a verifiable bar, with required comprehension at merge).
- Reuses existing primitives (quality_gate, checkpoints, capture, collab_loop, authorization) rather
  than inventing parallel machinery.
- Hub leverage: derived projects inherit the capability (Phase 3), with a shareable recipe library.
- Verifier-integrity defense makes "done is machine-decidable" honest, not self-graded.

### Negative
- A new control-flow surface (`scripts/goal_loop.py`) and a larger Phase-1 build than the prose-skill
  alternative.
- Reward hacking is an ongoing arms race; R5 raises the cost of gaming but cannot prove its absence —
  the never-skippable walkthrough is the human backstop.
- One agent definition and CLAUDE.md change, requiring the Steward gate + developer Principle-#7
  approval before build.

### Neutral
- A new top-level `loops/` directory (CORE `starter/`, SKIN `contracts/` + `local/`, additive-merge),
  added to the CLAUDE.md Directory Layout.
- Phase 2 (triggers, L3, cost telemetry) and Phase 3 (propagation) are deferred; L3 is gated on the
  velocity-drift telemetry precondition.
- **Process learning** (surfaced by independent-perspective): for `risk_level: high` design grills,
  pose the top 2-3 forks **without** a recommended answer — the grill-me recommended-answer
  discipline is right for authoring but pre-loads ratification when de-risking (this design's 19/22
  "agree" rate was the tell). Candidate follow-up to the grill-me skill.

## Linked Discussion
See: discussions/2026-06-21/DISC-20260621-065121-goal-loop-phase1-design/
Spec: docs/sprints/SPEC-20260621-064937-goal-loop-phase1.md (rev 2)
Design grill: brainstorms/2026-06-20-loop-orchestration.md
