---
description: "Pursue a developer-authored goal contract by iterating build -> verify -> refine until its verifiable criteria are met, then halt for /review + a required education walkthrough. Deterministic driver (scripts/goal_loop.py) owns control flow; the model is invoked only for build/judge/gate. Never pushes, never auto-merges."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[path to a GOAL-… contract, or a goal description to author one]"
---

# /goal-loop — Goal-Driven Loop Orchestration (Phase 1)

You are the **Facilitator in loop-mode** (see `.claude/agents/facilitator.md` → "Goal-Seeking Loop
Mode"). A `/goal-loop` iterates **build → verify → refine** toward a goal contract's *verifiable*
criteria, then **halts** for human `/review` + a required education walkthrough + approval. The
deterministic driver `scripts/goal_loop.py` owns ALL control flow; you (the model) are invoked only
for the build step, the judge step (as the independent checker), and gate-routing. Spec:
`docs/sprints/SPEC-20260621-064937-goal-loop-phase1.md`. Decision: **ADR-0026**.

## CRITICAL BEHAVIORAL RULES (pass/fail)

1. **NEVER push, NEVER auto-merge.** goal-met produces a *candidate* on the current branch; a human
   approves the merge after `/review` + education. No exceptions, at any autonomy level.
2. **NEVER skip capture.** The run owns exactly one discussion; the driver emits builder/checker/gate
   events + a terminal decision. Capture cannot be skipped (Principle #2).
3. **NEVER let prose mark a criterion green.** Green is earned by `verify` only (R5.2) — not by a
   contract line, an `anchor_context` file, a model turn, or an ntfy reply.
4. **Control flow is the driver's, not yours.** Do not re-implement ticks/budget/the termination
   ladder/loop-state in prose. If you're deciding *when to stop*, stop — that's `goal_loop.py`.
5. **STOP on a genuine design fork** (Principle #7). The loop runs routine in-tick decisions
   autonomously, but a real fork, the R5.1 tamper tripwire, an approval, or a blocker fires a human
   gate (keyboard `AskUserQuestion`; AFK `collab_loop.py` — act on the matched **label**, never raw
   reply text, never print the topic slug).

## Pre-flight

```bash
python -c "
import pathlib, sys
need = ['scripts/goal_loop.py','scripts/create_discussion.py','scripts/write_event.py',
        'scripts/close_discussion.py','loops/contracts','loops/starter']
miss = [p for p in need if not pathlib.Path(p).exists()]
print('PRE-FLIGHT FAILED: ' + ', '.join(miss) if miss else 'Pre-flight checks passed.')
sys.exit(1 if miss else 0)
"
```

## Procedure

### 1. Obtain a valid contract
- **A `GOAL-…` path was given** → use it.
- **A goal description (or nothing) was given** → run the **`authoring-goal-contracts`** skill: it
  gatekeeps non-loop-shaped goals FIRST (refusing subjective / exploratory / prohibited-to-verify
  goals and routing them to grill-me / `/plan` / `/deliberate`), then interviews the developer into a
  `loops/contracts/GOAL-…md`. Critical-risk goals are accepted but stamped `L1` +
  `mandatory_full_review: true`.

Validate mechanically before running — this is the contract's gate:
```bash
python scripts/goal_loop.py loops/contracts/GOAL-….md --validate-only
```
A `ContractError` names the exact rule to fix (all-judge rejected, judge-fraction cap, missing trio,
`llm-judge` not checker-owned, duplicate ids). Do not proceed until it validates.

### 2. Confirm autonomy scope (fail-closed, R10)
`L2` (commit-capable) requires the **existing** Autonomous Execution Authorization ACTIVE on an
**in-scope feature branch — never `main`**. If unaffirmable, the run drops to `L1` (report-only).
Pass the authorized branch explicitly; the driver re-reads the grant every tick (revoked → park).

### 3. Launch the driver
```bash
python scripts/goal_loop.py loops/contracts/GOAL-….md --run \
  --branch "$(git rev-parse --abbrev-ref HEAD)" \
  --authorized-branch "<in-scope feature branch>"   # omit to force L1
```
The driver creates the run discussion (contract = turn 1), then per tick: spawns the **builder**
(`claude -p`, build step of `orchestrating-goal-loops`), runs `quality_gate` + the **independent
checker** (a *separate* `claude -p` → distinct agent id, Principle #3 inside the loop), applies the
tamper tripwire, evaluates the termination ladder, and writes integrity-checked loop-state. It
**parks** (halt + structured report) on any backstop (`max_iterations` / `no_progress` / `budget`) or
guard (tampered loop-state / revoked L2) — never silent-continue.

### 4. At the terminal outcome
- **`goal_met`** → the driver has re-verified ALL criteria (no stale green). Now run the **full
  `/review`** panel, then the **required, never-skippable** education walkthrough (it must surface
  **how each criterion was met**, so a gamed solution is visible). Only after BOTH clear does a human
  approve the merge. Review-blockers become new criteria (continue if iterations remain, else
  backstop-halt). AFK → the candidate parks at the approval gate; education is deferred + logged.
- **a backstop / park** → present the structured loop report (green vs still-red, why it stopped).
  Do not retry blindly; surface the decision (sharpen the contract, raise a budget, take a fork).

## Resumability
The run is resumable via the **loop-state file** (`loops/.state/`), not the discussion: each run
seals exactly one discussion at its terminal outcome (R7), so a resume launches a **fresh run
discussion** and re-derives trust from loop-state, which is **untrusted on read** — the driver
re-runs every deterministic criterion, re-judges `llm-judge` criteria (corroborated against the
append-only checker events of the run that recorded them), and parks on an integrity mismatch.

## Known Phase-1 limitations (by design; Phase-2 refinements)
- **Cumulative delta.** The driver does not commit mid-run, so the checker and the tamper tripwire
  see the **cumulative** `git diff HEAD`, not a strict per-tick delta. Consequence: once a tick
  legitimately touches the test/verifier surface, later ticks keep re-tripping the tamper gate
  (R5.1) — so a coverage-raise/test-writing goal is **gate-heavy** over ntfy. Phase-1 starter
  recipes (e.g. `docs-sweep`) avoid this by not editing the verifier surface. Phase 2 adds a
  per-run approved-path set / per-tick snapshot.
- **Education is enforced at the human merge gate, not in driver code.** The driver never merges, so
  "never-skippable education" is a workflow guarantee (this command's §4 + R11), not a code lock.
- **L2 scope comes from `--authorized-branch` argv** (plus the hard `main` exclusion); Phase 2's live
  affirmer sources the branch scope from the durable Authorization signal, so the flag can only
  narrow authority, never grant it. Keep `/goal-loop` developer-launched until then.

## Notes
- Starter recipes: `loops/starter/` (CORE). Promote a contract that ran well into a reusable recipe
  via `/promote`.
- Phase 1 = manual, L1/L2, fully-governed. Triggers, unattended L3, and cost telemetry are Phase 2
  (gated on the velocity-drift precondition). Propagation to derived projects is Phase 3.
