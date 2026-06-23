---
# Goal Contract — the machine-readable "what done looks like" a /goal-loop runs against.
# ID convention: GOAL-YYYYMMDD-HHMMSS-slug. Authored via the `authoring-goal-contracts`
# skill (never hand-filled from blank — the interview proposes each field with examples).
# Spec: SPEC-20260621-064937-goal-loop-phase1 (R1). ADR-0026.

goal_id: GOAL-YYYYMMDD-HHMMSS-slug

# One sentence: the recursive purpose, in plain language ("what done looks like").
goal: >
  [e.g. Public API POST endpoints reject abusive traffic with a 429, without breaking
  normal users.]

# VERIFIABLE conditions — each one a machine (or independent checker) can decide.
# Coaching: verifiable-not-vibes ("returns 429" not "is secure"); deterministic-first;
# PREFER a verify method the builder cannot edit (frozen command / golden file).
# verify_owner: `gate` (deterministic — quality_gate or a command) or `checker`
#   (the independent checker agent). llm-judge criteria MUST be verify_owner: checker.
success_criteria:
  - id: SC1
    text: "[a checkable condition]"
    verify: "[deterministic command | quality_gate | llm-judge]"
    verify_owner: gate        # gate | checker
  # - id: SC2 ...

# Termination ladder. goal_met is the GOOD exit; the rest are backstops that PARK
# (halt + structured report), never silent-continue, never push/merge.
termination:
  max_iterations: 8
  no_progress: 2
  # net-progress (default, oscillation-proof): the no_progress counter increments when
  # the count of GREEN criteria did not increase this tick; resets when it does.
  no_progress_definition: net-progress    # net-progress | criterion-id-consecutive | fixed-red-set
  budget_output_tokens: 200000            # checked AFTER each complete tick

# Judge governance (R5.3): at least one deterministic/quality_gate criterion is required
# (all-judge contracts are rejected by the authoring interview); cap the judge fraction.
max_judge_fraction: 0.5

# Explicit out-of-bounds, so the loop does not scope-creep.
non_goals:
  - "[what this loop must NOT do]"

# Durable starting materials (paths). Treated as UNTRUSTED reference DATA by the driver/
# checker (delimited, never instructions) — a criterion is green only when its `verify`
# passed, never because anchor/prose says so.
anchor_context:
  - "[path to spec / ADR / relevant files]"

# L1 report-only (always allowed) | L2 assisted (requires the Autonomous Execution
# Authorization block ACTIVE on an in-scope branch). L3 + triggers are Phase 2.
autonomy_level: L1

# Critical-risk goals (auth/data/infra) are accepted but stamped L1 + mandatory_full_review.
mandatory_full_review: false

# Provenance: a SPEC id when /plan emitted this contract from its acceptance criteria;
# null when authored directly for a small/convergent goal.
derived_from: null
---

## Notes (free-form, optional)

Anything a human reviewer should know about this goal that does not belong in a field —
known hazards, why a particular verify method was chosen, links to prior art.

> Reminder: a `/goal-loop` never pushes, never auto-merges, and always halts at goal-met
> for `/review` + a required education walkthrough before anything merges. If "done" can
> only be verified by a prohibited/irreversible action, this is the wrong tool — sharpen
> the goal with `grill-me`/`/plan` or take it to `/deliberate`.
