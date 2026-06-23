---
spec_id: SPEC-20260621-064937-goal-loop-phase1
title: "Goal-Driven Loop Orchestration (`/goal-loop`) — Phase 1 MVP"
type: spec
status: complete
risk_level: high
intake_ids: []
reviewed_by: [steward, architecture-consultant, independent-perspective, security-specialist, qa-specialist]
discussion_id: DISC-20260621-065121-goal-loop-phase1-design
completed_at: 2026-06-23
completed_commit: c195ba1
revision: 2
revision_note: >
  Rev 2 folds the DISC-20260621-065121 deliberation (verdict REVISE 0.83; Steward
  REVISE 0.84). Adopts the HYBRID DETERMINISTIC DRIVER (developer decision): a
  deterministic scripts/goal_loop.py owns control flow; the model is invoked only for
  build + judge + gate-routing. Incorporates 6 blocking items (led by verifier-integrity
  defense) + 16 required folds. See "Deliberation Outcome" below.
---

## Goal
A new **`/goal-loop`** capability. A **deterministic driver** (`scripts/goal_loop.py`) pursues a
developer-authored **goal contract** by iterating **build → verify → refine** until the contract's
*verifiable* success criteria are met, then halts for human `/review` + education + approval. The
driver owns all control flow (tick counter, budget, termination ladder, loop-state + integrity,
re-verify-on-reconstruct); the **model — running in the main loop as the facilitator in loop-mode —
is invoked by the driver only for the build step, the judge step, and gate-routing**. When the goal
cannot be met, the loop **parks** (halts, preserves state, hands back a report) rather than
thrashing. Phase 1 ships the **manual, fully-governed core engine** — no scheduled/event triggers,
no unattended L3 — usable day one, with phone (ntfy) approval treated like sitting at the keyboard.

This is the framework's adaptation of the 2026 "loop engineering" shift (Berman Loop Library, Ralph
loop, Claude Code `/goal`; anatomy `trigger → action → verify → stop`), built *to* the framework's
non-negotiables rather than around them.

## Deliberation Outcome (DISC-20260621-065121)
A 5-specialist `/deliberate` (steward, architecture-consultant, independent-perspective,
security-specialist, qa-specialist) returned **REVISE (0.83)**. The load-bearing results this
revision incorporates:
- **Headline gap — verifier integrity / reward hacking** (converged by 3 specialists): the loop
  could make its own verifier pass *without doing the work*. Rev-1 had no defense. → **R5** is new.
- **Architecture decision (developer): the HYBRID DETERMINISTIC DRIVER** replaces "prose-skill
  control flow." Control flow is code, not model-followed prose under context pressure.
- **Reuse-honesty (verified)**: `/build_module` is a one-shot workflow that owns its own
  discussion + gate + close (`build_module.md:63,221,237`) — so the loop is a conductor over
  **primitives** (code-gen + `running-build-checkpoints` + `quality_gate`), **not** over the
  `/build_module` command. The "`/loop` + Workflow tool already owned" claim is removed — verified:
  no `.claude/commands/*loop*`; those are harness features, not repo artifacts.

## Context
- **Origin:** the 2026-06-20 design grill (`brainstorms/2026-06-20-loop-orchestration.md`, Q1–Q22).
- **Answers the developer's Q1 ("should agent definitions change?"):** YES, but **surgically** — one
  agent (facilitator) gains one subsection that **names the posture switch** (single-pass synthesis
  ↔ iterate-to-criteria) and the `/review`-synthesis boundary. The 10 specialists are unchanged.
- **Reuses primitives:** `scripts/quality_gate.py` (deterministic verify), the **code-gen +
  `running-build-checkpoints` checkpoint primitive** that `/build_module` itself uses (NOT the
  `/build_module` command), `create_discussion.py`/`write_event.py`/`close_discussion.py` (capture),
  `scripts/collab_loop.py` (ntfy gates), the **Autonomous Execution Authorization** block (autonomy),
  `/promote` (recipe growth). Phase-2-only: `session_supervisor.py` (L3), triggers, telemetry cost.
- **Framework-evolution change** → Steward gate (Principle #7) precedes build; the owed ADR is
  ADR-0026 (this spec's sibling).
- **Altitude:** a **hub capability** (CORE) propagating to derived projects in Phase 3.

## Requirements

### Engine & control flow

- **R1 — Goal-contract artifact (`loops/contracts/`, SKIN).** YAML-frontmatter + Markdown, ID
  `GOAL-YYYYMMDD-HHMMSS-slug`. Seven fields: `goal`; `success_criteria` (each with a stable id);
  `verify` (per-criterion: deterministic command / `quality_gate` / `llm-judge`); `termination`
  (R6); `non_goals`; `anchor_context`; `autonomy_level` (L1/L2 in Phase 1). Load-bearing trio =
  `success_criteria` + `verify` + `termination`. New fields from the deliberation: `derived_from`
  (a `SPEC-…` id or `null`, R10); `no_progress_definition` (R6); criteria carry a `verify_owner`
  (`gate` | `checker`) — **`llm-judge` criteria MUST have `verify_owner: checker`** (R3/R5).

- **R2 — Deterministic driver `scripts/goal_loop.py` (the control-flow owner).** A pure-Python
  driver that OWNS, in code (not model prose): the tick counter; the budget tally; the termination
  ladder evaluation (R6); the loop-state read/write with integrity (R7); re-verify-on-reconstruct
  (R7); the maker/checker dispatch sequencing (R4); and the park-and-report behavior. The driver
  **invokes the model only for three things**: (a) the *build* step (produce the next delta),
  (b) the *judge* step (evaluate an `llm-judge` criterion — always as the independent checker, never
  the builder), (c) *gate-routing* (surface a human gate via R8). Everything else is deterministic.
  The driver is what `/goal-loop` launches.

- **R3 — `orchestrating-goal-loops` skill (model-facing procedure).** Holds ONLY the model-side
  procedure the driver calls into: how to build a delta against a criterion, how to judge a
  criterion as the independent checker, how to phrase a gate. It does **not** own control flow
  (that is R2). Mirrors the `running-build-checkpoints` split (a skill the deterministic step uses).

- **R4 — Two-tier verify with in-loop independence.** Every tick: `quality_gate.py` (deterministic)
  **+ one independent checker** reviewing only the delta (checker ≠ builder → Principle #4 inside the
  loop; reuses the `running-build-checkpoints` primitive). The checker is dispatched **delta-only**
  (no builder reasoning/intermediate state). For any `llm-judge` criterion, the *judge call is the
  checker's*, never the conductor's. The **full `/review` panel runs ONLY at the goal-met
  candidate**.

### Verifier integrity (NEW — the deliberation headline)

- **R5 — Verifier-integrity defense (anti reward-hacking).** The loop must not be able to satisfy a
  criterion by altering its own verifier or test surface.
  1. **Verifier-tamper tripwire:** any tick whose diff touches test files, the quality-gate config,
     coverage pragmas (`# pragma: no cover` and equivalents), or a criterion's own `verify` command
     **forces a human gate** (R8) before that tick can count toward `goal_met`.
  2. **Green is earned by `verify`, never by prose:** a criterion is green **iff** its `verify`
     method passed. No text in the contract, `anchor_context`, a model turn, or an ntfy reply can
     mark a criterion green. (Ties R10 injection defense.)
  3. **Judge governance:** the authoring interview (R12) **rejects all-judge contracts** (≥1
     deterministic or `quality_gate` criterion required) and caps the judge fraction
     (`max_judge_fraction`, default 0.5); every `llm-judge` criterion is verified by the independent
     checker (R4), recorded as a distinct checker turn.
  4. **Re-verify on the goal-met candidate:** before declaring `goal_met`, the driver re-verifies
     **all** criteria (including judge ones) — no stale green carries the exit.
  5. **Comprehension surfacing:** the required walkthrough (R11) must surface **how each criterion
     was met**, so a gamed solution is visible at the human gate.

### Termination, gates, capture

- **R6 — Termination ladder + stop semantics.** Good exit `goal_met`: all criteria green (after R5.4
  re-verify) → full `/review` (R11) → pass → **halt + present a ready-to-merge result for human
  approval** (no push, no auto-merge); review-blockers become new criteria, continue if iterations
  remain else backstop-halt. Backstop exits: `max_iterations` (default 8), `no_progress`
  (default 2), `budget` (output tokens; default = run target or 200k) → **halt + structured loop
  report**, never silent-continue. **`no_progress` semantics are explicit** (`no_progress_definition`,
  default = *net-progress*: the counter increments when the count of green criteria did not increase
  this tick; resets when it does) — chosen because it is oscillation-proof. **Budget** is measured in
  **output tokens, checked after each complete tick**; a partial tick that hits budget is **not**
  committed to loop-state (the report reflects the last complete tick).

- **R7 — Loop-state (UNTRUSTED on read) + capture.** A small loop-state record, written
  **atomically (temp+rename)** each tick, carrying: iteration, ladder counters, per-criterion status,
  and — for every green — a **content anchor** (hash/mtime of what made it green) plus the
  `GOAL-…` id and `DISC-…` id, and an **integrity hash** over the record. On reconstruct (compaction
  or fresh session), the driver treats loop-state as **untrusted**: it **re-derives** every
  deterministic/`quality_gate` criterion (cheap), **re-judges** `llm-judge` criteria if iterations
  remain, and **cross-checks** any claimed green against the **append-only checker-turn events** in
  the discussion; a green with no corresponding checker/gate evidence, or an integrity-hash
  mismatch, is treated as **red** and the loop **parks** for a stale/tampered record. Capture: ONE
  discussion per run (`DISC-…-loop-<slug>`), goal contract as `turn_id=1`, per-tick events (builder
  turn, checker turn, gate result, termination decision, ntfy prompts/replies-by-label), ordered;
  `close_discussion` at end. The append-only discussion is the **tiebreaker** over the mutable
  loop-state record. Capture cannot be skipped (Principle #2).

- **R8 — Transport-agnostic human gates with ntfy parity + binding.** A gate is a decision that
  needs the human. Keyboard → `AskUserQuestion`; AFK → `collab_loop.py` ask/poll with the SAME
  labeled choices; resume on the matched **label**. **Binding (new):** each gate carries a per-gate
  token (nonce or short diff-hash) and is **one-shot** — a matched reply clears the open-gate marker,
  so a replayed/pre-armed label finds no open gate; **at most one open gate at a time**. ntfy replies
  are unauthenticated → validate against a fixed allow-list, act on the matched **label, never raw
  text**, never print the topic slug. `REPLY-INVALID` is handled **identically to timeout** (no
  action, re-ask or park). Single-poller + orphan-recovery discipline inherited from
  `collaborating-async`. Routine in-tick decisions are made autonomously; gates fire only for
  approvals, the R5.1 tamper tripwire, genuine design forks, and blockers.

### Agent, autonomy, suggestion

- **R9 — Facilitator definition delta (the ONLY agent-definition change).** A single subsection
  **"Goal-Seeking Loop Mode"** in `.claude/agents/facilitator.md` that **explicitly names**: (a) the
  **posture switch** — in loop-mode the goal contract is the north star and the model iterates to its
  criteria, vs the facilitator's default single-pass synthesis; (b) the **boundary** — loop-mode does
  **not** change how `/review` itself is synthesized; (c) that the deterministic driver owns control
  flow and calls the model for build/judge/gate only; (d) that every non-negotiable holds inside the
  loop. No other agent definition changes. (Resolves the grill fork: one subsection suffices *with*
  this content — steward + architecture concur.)

- **R10 — Autonomy (fail-closed) + injection defense.** The loop is governed by the **existing**
  Autonomous Execution Authorization; it opens no new surface. **L2 fails closed:** before the first
  commit the driver emits a **captured, positive, branch-checked affirmation** — "block ACTIVE;
  branch ∈ authorized scope; effective date passed; not revoked" — and **re-reads the block at the
  top of every tick** (revoked-mid-run → park). If any clause is unaffirmable → drop to **L1**
  (report-only). **`anchor_context` is untrusted DATA:** its content is delimited as non-instruction
  reference material in any model prompt; combined with R5.2 (green only via `verify`), a poisoned
  anchor cannot mark a criterion green or make the checker rubber-stamp. **`derived_from` seam:** for
  big goals, `/plan` is **upstream** and *emits* the contract from the approved spec's acceptance
  criteria (`derived_from: SPEC-…`, criteria traceable to spec AC ids); small goals author directly
  (`derived_from: null`). `/plan` gaining this emit-a-contract behavior is a declared edit to
  `.claude/commands/plan.md`.

- **R11 — Verify + (required) education merge gate.** goal-met → full `/review` → **required,
  never-skippable** education walkthrough (teaches the concepts/possibility-space + **how each
  criterion was met**, R5.5) → human merge approval. Required-to-**merge**, never required-to-
  terminate (AFK: result parks at the approval gate; education deferred + logged, Principle #6).
  Nothing merges until BOTH `/review` and education clear.

- **R12 — Authoring interview, starter library, suggestion heuristic.** The
  `authoring-goal-contracts` skill: a grill-flavored interview (one question, recommended answer,
  worked example per field) that emits a structured `GOAL-…` and runs an **"is this even
  loop-shaped?" gatekeeper FIRST** — refusing (a) no-verifiable-criterion (→ grill-me/`/plan`),
  (b) design/exploration (→ `/deliberate`/`/plan`), (c) done-state needs a prohibited/irreversible
  action (→ human gate / out of scope); critical-risk goals (auth/data/infra) are **accepted but
  stamped `autonomy_level: L1` + `mandatory_full_review: true`**, not refused. It also enforces R5.3
  (reject all-judge; cap judge fraction) and a **coaching principle: prefer `verify` methods the
  builder cannot edit**. `loops/starter/` (CORE) seeds the example bank and provides instantiable
  recipes; a prompt-level **suggestion heuristic** in CLAUDE.md Workflow Sequencing (+ a `/plan`-end
  nudge) offers `/goal-loop` when a task has (1) a verifiable done-state, (2) expected iterative
  convergence, (3) is not a micro-fix — **suggest, never impose**; never auto-starts.

## Constraints
- **Non-negotiables hold INSIDE the loop**: never push, never auto-merge, never skip `/review`,
  capture, or the (required) education gate; STILL STOP on a genuine design fork (Principle #9).
- **Control flow is deterministic code (R2)**, not model-followed prose; the model is called only for
  build/judge/gate-routing.
- **Phase 1 = L1/L2 only.** L3 unattended, cross-session continuation, scheduled/event triggers,
  `loop-cost` estimation, and telemetry cost capture are **Phase 2**. **Velocity-drift precondition:**
  Phase-2 L3/triggers may **not** be blessed until per-goal cost + human-gate throughput are
  instrumented (Steward condition).
- **Exactly one agent definition changes** (facilitator). The 10 specialists are untouched.
- **Autonomy governed by the EXISTING authorization**, fail-closed (R10); the loop never elevates.
- **Park-don't-guess** on timeout / non-convergence / no-valid-reply / stale-or-tampered loop-state.
- **ntfy untrusted-reply discipline** (always-on invariant) is mandatory.
- Stack: Python 3.11+, pytest, ruff; coverage ≥80%; no new runtime dependencies for the engine.
- Hub-shape: `loops/starter/` + command + skills + facilitator delta are CORE; `loops/contracts/` +
  `loops/local/` are SKIN; `loops/` treated as **additive-merge, never replace** by `/apply-framework`.

## Acceptance Criteria
- [ ] **AC1 — Contract schema**: a 7-field `GOAL-…` validates; a contract missing the load-bearing
      trio is rejected with a plain reason; `derived_from` and `no_progress_definition` parse.
- [ ] **AC2 — Gatekeeper (all branches)**: the interview refuses each of the 3 out-of-scope cases and
      routes to the named alternative; a **critical-risk goal is accepted but emitted with
      `autonomy_level: L1` + `mandatory_full_review: true`** and a subsequent run enforces full review
      at every milestone.
- [ ] **AC3 — Judge governance**: an **all-judge contract is REJECTED** (≥1 deterministic anchor
      required); a `max_judge_fraction` breach is rejected; for a judge criterion, the green
      transition is attributable to a **checker** turn (distinct agent id), never a conductor turn.
- [ ] **AC4 — Termination + oscillation**: separate runs demonstrate each backstop HALT with a
      structured report and no push/merge; **AC4-osc** — a criterion alternating red→green→red while
      others stay red still hits a backstop (net-progress semantics tested with an alternating mock
      checker); budget halt fires after a complete tick and loop-state reflects the last complete tick.
- [ ] **AC5 — Verifier integrity**: **AC5-tamper** — a tick whose diff touches a test file / gate
      config / coverage pragma / a `verify` command forces a human gate before counting toward
      goal-met; **AC5-adversarial** — a seeded builder defect that the builder would self-approve is
      caught by the delta-only checker; goal-met re-verifies all criteria (no stale green carries).
- [ ] **AC6 — Gate parity + binding**: a gate resolves identically via `AskUserQuestion` and a
      `FakeCollabLoop` fixture, acting on the matched **label**; a **replayed/pre-armed** label finds
      no open gate (one-shot consumption); a non-matching reply and a timeout are handled identically
      (no action); the topic slug never appears; at most one open gate at a time.
- [ ] **AC7 — Capture (structural)**: exactly one sealed discussion; `turn_id=1` = contract; each
      tick contributes `[builder_turn, checker_turn, gate_result]` in order; the final event is a
      `termination_decision`; loop-state `iteration` matches the event count; parametrized across
      `goal_met` / `max_iterations` / `no_progress` exits.
- [ ] **AC8 — Resumability (trust)**: **AC8-pos** — a legitimate mid-run state reconstructs and
      continues without re-doing a green criterion; **AC8-neg** — a loop-state claiming a false green
      (tampered, or whose backing artifact changed) does **NOT** skip that criterion's verification
      (re-derived deterministically / cross-checked against checker events / integrity-hash mismatch
      → park).
- [ ] **AC9 — Facilitator delta is bounded AND self-explaining**: the diff to `facilitator.md` is a
      single subsection that **names the posture switch and the `/review`-synthesis boundary**; no
      other agent definition file changes.
- [ ] **AC10 — Autonomy fail-closed**: a run on `main` (no active block) cannot reach L2; a run on a
      **feature branch not in the authorization scope** drops to L1; a **revoked** block mid-run
      parks; the branch-scope affirmation is captured before the first commit; no path performs a
      push or auto-merge.
- [ ] **AC11 — Education required**: goal-met blocks merge until BOTH `/review` and the never-skippable
      walkthrough clear; the walkthrough surfaces how each criterion was met; AFK defers-and-logs.
- [ ] **AC12 — Hygiene**: regression-ledger entry written **before** the first commit; quality gate
      7/7; ruff clean; coverage ≥80%; `loops/` added to CLAUDE.md Directory Layout; ADR-0026 present.

## Risk Assessment
- **Reward hacking (the headline).** Mitigated by R5 (tamper tripwire → human gate; green only via
  `verify`; judge governance; goal-met re-verify; comprehension surfacing). Residual: a criterion
  whose `verify` is gameable-without-touching-the-tripwire-files — mitigated by R12's coaching
  ("prefer verify the builder cannot edit") and the never-skippable walkthrough.
- **Control-flow reliability.** Mitigated by R2 (deterministic driver owns ticks/budget/ladder/
  loop-state/re-verify) — the safety-critical flow is code, not prose under context pressure.
- **Loop-state tampering / staleness.** Mitigated by R7 (untrusted-on-read; re-derive; cross-check
  against append-only events; integrity hash; atomic write; park on mismatch).
- **Unauthenticated ntfy approval.** Bounded by no-push/no-merge at every level; tightened by R8
  per-gate binding + one-shot consumption; worst case = a recoverable local commit on a feature
  branch.
- **Autonomy scope-creep / revoked-but-running.** Mitigated by R10 fail-closed branch-checked
  affirmation + per-tick re-read.
- **Prompt injection via anchor/goal.** Mitigated by R10 delimiting + R5.2 (green only via verify).
- **Agent-definition evolution (high-stakes).** One self-explaining subsection; Steward gate
  (Principle #7) + developer approval precede build.
- **Comprehension debt from unwatched production.** Mitigated by R11 required walkthrough.
- **Velocity drift.** Phase-2 L3/triggers gated on cost + gate-throughput telemetry (Steward
  precondition).

## Affected Components
- `scripts/goal_loop.py` (NEW — deterministic driver, CORE)
- `.claude/commands/goal-loop.md` (NEW — thin entry, CORE)
- `.claude/skills/orchestrating-goal-loops/SKILL.md` (NEW — model-facing build/judge/gate procedure, CORE)
- `.claude/skills/authoring-goal-contracts/SKILL.md` (NEW — guided interview + gatekeeper + judge caps, CORE)
- `.claude/agents/facilitator.md` (MODIFIED — ONE "Goal-Seeking Loop Mode" subsection, CORE)
- `.claude/commands/plan.md` (MODIFIED — `/plan` emits a `derived_from` goal contract, CORE)
- `CLAUDE.md` (MODIFIED — suggestion heuristic in Workflow Sequencing + `loops/` in Directory Layout, CORE)
- `docs/templates/goal-contract-template.md` (NEW, CORE)
- `loops/starter/` (NEW — recipes, CORE) · `loops/contracts/`, `loops/local/` (NEW — SKIN)
- `tests/test_goal_loop.py` (NEW) · `memory/bugs/regression-ledger.md` (entry, pre-commit)
- `docs/adr/ADR-0026-*.md` (NEW — the owed framework-scope ADR)
- Doc sync: `docs/AGENT_ARCHITECTURE.md` (facilitator loop-mode), Rules Index (the two new skills),
  per `syncing-framework-docs`.

## Dependencies
- **Depends on (present):** quality_gate, the code-gen + `running-build-checkpoints` checkpoint
  primitive, `/review`, the capture pipeline, `collab_loop`, the Autonomous Execution Authorization
  block, `/promote`.
- **Gated by:** Steward APPROVE (Principle #7) on the facilitator delta + developer approval +
  ADR-0026.
- **Depended on by (later, not built here):** Phase 2 (triggers, L3 via `session_supervisor`,
  `loop-cost` + telemetry — **gated on the velocity-drift precondition**), Phase 3 (CORE/SKIN
  packaging into `/apply-framework`, rollout to Insight Journal / VerificationPortal / Howie).
