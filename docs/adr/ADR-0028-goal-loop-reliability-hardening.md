---
adr_id: ADR-0028
title: "Goal-loop reliability hardening — first-real-use backflow from VerificationPortal"
status: accepted
date: 2026-06-27
decision_makers: [orchestrator, steward]
discussion_id: DISC-20260628-022452-goal-loop-hardening-adr0028
spec_id:
supersedes:
extends: ADR-0026
scope: framework
risk_level: high
confidence: 0.88
tags: [backflow, goal-loop, verifier-integrity, reliability, verification-portal, safety-critical]
---

## Context

`/goal-loop` (ADR-0026) was exercised for the **first real time** in a derived project,
VerificationPortal (VP). Two adversarial `/review` rounds + a fix surfaced concrete defects and design
lessons. Because VP's copy was propagated *from* this hub, the hub was checked seam-by-seam — and the
result is a **mix**, not "all the same bugs": some defects reproduce in the hub (and are live on public
main via PR #100), some were VP-only propagation gaps the hub never had, and VP's own fix commit
(`2ab77352`) is itself REQUEST-CHANGES (round-2 left B1–B4 open), so it supplies clean reference code
for the pure-core fixes only — the transport fix, the always-skeptic, and the re-verify-fail test are
authored fresh here.

**Origin (backflow from VerificationPortal, first-real-use).** This is a leaf→hub backflow: VP's
adversarial use is exactly what the framework is for, and the lessons flow back so every project
benefits. Attribution per the Prime Objective test (a): VP is credited as the first-use source in this
ADR and, machine-traceably, in `.claude/custodian/lineage-events.jsonl` (a `BACKFLOW` event referencing
this ADR). Reference fix: VP `feature/goal-loop-enforcer-fix` @ `2ab77352` — reconciled, not re-derived.

Verified hub defects (all confirmed against hub source before deciding):
- **Seam-2b (AFK gate drops every approval).** `_ntfy_gate_transport` drove `collab_loop check 1h` and
  parsed `REPLY-MATCH:`, but `check` prints `ANSWER-MATCH` — only `poll` prints `REPLY-MATCH`. Every
  remote phone approval was silently dropped (a reliability defect: a dropped approval parks the run,
  it does not false-green — but it nullifies the entire AFK value proposition). Live on public main.
- **B4 (verifier-integrity sibling hole).** `validate_contract` rejected all-judge contracts but a
  `[quality_gate, "pytest tests/test_x.py"]` pair (two non-judge criteria) passed — nothing forced an
  *independent* actor to re-run the verifier the loop itself authored. A declarative per-shape rule
  structurally cannot catch this; it is a runtime property.
- **H2 (branch protection).** `FailClosedAuthAffirmer` filtered only the exact string `"main"`, so
  `MAIN`, `refs/heads/main`, `master`, `develop`, `trunk` all slipped through.
- **Answer-key tamper gap.** The tamper tripwire guarded the *verifier* surface but not arbitrary
  fixtures/baselines a contract's criteria read (the "answer key").

Verified NON-defects in the hub (so the port stays selective): the notify TypeError (2a) does NOT
reproduce — the hub is internally body-first consistent; `tests/test_goal_loop.py` and the facilitator
"Goal-Seeking Loop Mode" subsection already exist (VP's copy lacked them). Copying VP's title-first
`notify.py` would *introduce* the bug it claims to fix.

## Decision

Land the lessons as a single combined hardening change (one ADR extending ADR-0026, never amending it),
fork-only, with the public-main PR (the live seam-2b) as a separately-confirmed follow-on:

1. **Seam-2b** — `_ntfy_gate_transport` drives a **bounded `poll`** (which prints `REPLY-MATCH`) instead
   of `check 1h` (which prints `ANSWER-MATCH` and carries a stale-replay lookback). Ships with a binding
   integration test that fails on the old code.
2. **Always-skeptic on the goal-met candidate — this IMPLEMENTS ADR-0026 R5.4; it is NOT a new
   decision.** ADR-0026 §Decision 4 / R5.4 already mandates that *all criteria are re-verified at the
   goal-met candidate* and `evaluate_termination` already documents `GOAL_MET` as only a *candidate*.
   This change completes that mandate: the re-verification **always runs the independent skeptic checker
   on the goal-met candidate regardless of contract shape**, and the skeptic never runs the builder's
   own authored verify command. That closes the B4 reward-hack class (the per-shape `validate_contract`
   rule provably cannot). Moving the guarantee from declarative (contract shape) to imperative (driver
   runtime at the goal-met transition) is the correct *layer* for a runtime property — it is the faithful
   implementation of an existing R5 mandate, not new scope.

   **Behavior on a skeptic red — RETRY, not terminate-immediately (developer decision,
   DISC-20260628-022452).** A red verdict does not end the run outright; it consults the existing
   termination ladder via `_backstop_only`. While the ladder (`max_iterations` / `no_progress` / budget)
   has room, the loop re-verifies and re-runs the independent skeptic — so a *fluke* red (the judge is
   stochastic) clears on a subsequent pass and the run exits `GOAL_MET` normally. A *persistent* red makes
   no net progress (all criteria are already green, so the builder has no red target to advance), so the
   `no_progress` backstop trips and the run **PARKs** with a report naming the persistent veto and its
   count. This provably terminates (bounded by the ladder — no livelock), recovers correct-but-flukily-
   judged results, and still hands a persistent objection to the human — never a self-green. The re-check
   window borrows the `no_progress` count (Principle #8); an author can tune it and a dedicated cap is a
   future refinement if the borrowed window proves too history-dependent.
3. **H1** — `validate_contract` also rejects a `quality_gate`-only contract (every deterministic
   criterion is `quality_gate`, no judges): `quality_gate` runs over all of `src/`, a surface the tamper
   tripwire's filename allow-list cannot fully protect, so an independent checker must read the candidate.
   (Belt-and-suspenders with #2: H1 catches it at authoring, the always-skeptic catches it at runtime.)
4. **protected_paths** — a new optional `GoalContract` field naming the fixtures/baselines the criteria
   read (the "answer key"); a tick touching one (edit / rename / delete, all via `--name-status`) trips
   the tamper tripwire. **Hardened past VP:** normalized through the *same* path helper the tripwire
   already uses, and a leading-slash / empty entry is rejected by `validate_contract` (fail closed —
   VP's version fails open on its own unfixed A2).
5. **H2** — `_PROTECTED_BRANCHES` + `_is_protected_branch()` (casefold + `refs/heads/` strip +
   master/develop/trunk), filtered at `FailClosedAuthAffirmer` construction AND re-checked defense-in-
   depth on every `affirm_l2`. **_SENSITIVE_PATH_RE** extended with `setup.py|pytest.ini|.pytest.ini|noxfile.py`.
6. **Ship the proof (Lesson 1).** New tests land in the SAME change: the seam-2b integration test, a
   fresh B3 FlipVerifier re-verify-FAIL test (proving a builder-authored green that flips red under
   independent re-verification halts the run), the H1/protected_paths/H2 regressions, and a 2a bind-shape
   lock test. A new prose rule in `.claude/rules/testing_requirements.md` names the obligation generally:
   *a safety-critical control-flow capability ships its tests in the same change.*
7. **Authoring + propagation hygiene (Lessons 4–6).** Authoring skill gains a **Step 0 "lead with the
   goal + clarify up front,"** fixtures-must-be-captured-not-hand-authored coaching, a mandatory
   live-confirm at goal-met, and qg-only-needs-skeptic + `protected_paths` coaching. The contract
   template drops the stale `fixed-red-set` option (which `validate_contract` rejects) and gains
   `protected_paths`.

## Adaptations (deliberate divergences from the VP reference — reconcile, not copy)

- **Keep body-first `notify.py` + a lock test, do NOT take VP's title-first signature.** The hub is
  internally consistent; VP's signature change broke its own callers (B1). The least-complex, lowest-risk
  intervention (Principle #8) is a bind-shape test, not a signature change rippling to every caller.
- **Harden `protected_paths` to fail closed.** VP fails open on leading-slash entries (its own review's
  A2, unfixed). A safety tripwire must refuse ambiguous input (Always-On Invariant: sanitize at every
  trust boundary; a goal contract is untrusted on read, ADR-0026 §6). Divergence from a REQUEST-CHANGES
  reference is correctness, not drift.
- **Author B2 / B4 / B3 fresh.** VP's commit does not contain them; re-derived from the review findings
  and the established R5/R8/R10 design.

## Consequences

- The AFK gate works (seam-2b); the reward-hack sibling class is closed at runtime (always-skeptic);
  branch protection and the answer-key tamper guard are tightened. The capability's value proposition —
  provable reliability under autonomy — is now actually proven by tests that fail without the guards.
- Behavior change is confined to the goal-met transition (now always independently re-verified) and the
  AFK transport (now reaches the developer). No change to the deterministic-driver architecture ADR-0026
  established; this is hardening within its mandate.
- Fork-only. The public-main PR (the live seam-2b) is a tracked follow-on requiring explicit per-instance
  developer consent (push is never autonomous).
- **Single-poller constraint (review F4):** the goal-loop owns the ntfy poll lock for a gate's duration;
  a separate standing developer poll-monitor must not be armed during an autonomous goal-loop run — the
  newest poller supersedes older ones, and a split would route a reply to the wrong allow-list. Documented
  at `_ntfy_gate_transport`.
- Establishes the "ship the proof with a safety-critical capability" rule for future framework work.

## Alternatives Considered

- **A separate design note for the always-skeptic:** rejected (Steward) — it is the implementation of an
  existing R5.4 mandate, not a new surface; splitting it would fragment one verifier-integrity story and
  read as scope creep where there is none.
- **Skeptic-veto = immediate PARK (rejected, developer):** simplest, and the build's original behavior,
  but a single stochastic red terminally strands a legitimately-complete run; the developer chose Retry
  (bounded re-checks via the ladder) to distinguish a fluke from a persistent objection while still
  parking when genuinely stuck.
- **Skeptic-veto = surface-to-human goal-met gate without stopping (considered, not chosen):** keeps
  termination fully deterministic (the stochastic judge never affects control flow) and routes the
  objection to the human review gate. Rejected in favor of Retry: Retry recovers a fluke automatically
  and still parks (for the human) on a persistent veto, without declaring `GOAL_MET` while an objection
  stands. Revisit if judge non-determinism proves costly in practice.
- **Copy VP's fix wholesale:** rejected — VP's commit is REQUEST-CHANGES (B1–B4 open) and its title-first
  `notify.py` would introduce a bug the hub does not have; reconcile selectively, seam-verified.
- **Amend ADR-0026 in place:** rejected — 0026 is accepted and published; Principle #5 (ADRs are never
  deleted, only superseded/extended). A new extending ADR keeps the record honest.
- **Defer the qg-only rule to the always-skeptic alone:** rejected — defense-in-depth is cheap; catch it
  at authoring (H1) AND at runtime (always-skeptic).
- **Mechanical "safety-critical module lacks a test" gate now:** deferred — a prose rule + `/review`
  enforcement is the least-complex first intervention; mechanize only if it recurs.
