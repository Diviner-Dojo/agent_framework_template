---
walkthrough_id: WALKTHROUGH-20260516-PHASE0
spec_id: SPEC-20260515-053533
review_id: REV-20260515-221223
subject: "Phase 0 — Promotion pipeline repair (Layer 1 → Layer 3 seam)"
audience: decision-maker
risk_tier: low
education_gate: required
date: 2026-05-16
---

# Phase 0 Walkthrough: Promotion Pipeline Repair

## What this is about

For approximately five weeks, the framework's central architectural claim — "reasoning is the
primary artifact" — was operationally false at one specific seam. Discussions were sealed,
findings were mined, pattern sightings accumulated. But the step that was supposed to translate
those sightings into promotion candidates silently did nothing. Nothing alarmed. 109 sightings
accumulated. Zero promotion candidates were ever created. The `/promote` command, which is how
curated knowledge enters Layer 3 memory, had effectively no inputs to work with.

Phase 0 repaired that seam. This walkthrough explains four framework concepts the fix
illustrates — not because you need to understand how to write the code, but because you need to
understand the decisions well enough to evaluate them, direct future work in this area, and
recognize if something goes wrong again.

---

## Concept 1: The swallow-and-warn pattern — and what you owe the system when you use it

The framework's discussion-closure pipeline runs several steps in sequence: mine patterns,
surface candidates, compute agent effectiveness, and a few more. Each step runs inside its own
`try/except` block. If any step fails, the error is caught, printed as a warning, and the
pipeline moves on.

This is a deliberate architectural choice, not laziness. The reasoning is that closing a
discussion is a high-stakes finalization event — it seals the record, marks it read-only, and
notifies the developer. A failure in the "surface candidates" step should not abort the entire
closure and leave the discussion in a half-sealed state. Resilience at the pipeline level
requires absorbing non-fatal step failures. This is sometimes called "swallow-and-warn."

The problem with swallow-and-warn is obvious in hindsight: the moment you decide that a failure
is non-fatal, you also remove its ability to cause pain. A non-fatal warning printed to a
terminal during a lengthy closure run is easy to miss, easy to mentally dismiss, and impossible
to track across time. The same warning printed on every single closure for five weeks produced
exactly zero escalations.

Phase 0's spec made a principled decision: retain the swallow-and-warn pattern (closure
resilience still matters), but acknowledge the debt it creates. When you choose to swallow
exceptions for resilience, you owe the system a canary — something that will fail loudly if the
swallowed exception returns. The fix at `scripts/close_discussion.py:140-155` is unchanged; the
regression tests at `tests/test_close_discussion_promotion_pipeline.py` are the canary.

This is the conceptual trade: you buy resilience by giving up alarm, and you pay for that alarm
separately, in a different layer. Understanding this trade is what lets you evaluate whether the
system's canary coverage is adequate as the framework grows.

---

## Concept 2: The canary contract — and what enforces what

The regression-ledger entry for this fix contains a sentence that reads like a warning label:

> "This test is the structural canary for the swallow-and-warn pattern at
> close_discussion.py:140-155. Do not remove or weaken without an ADR addressing the
> swallowed-exception pattern."

This is documentation-as-policy. It is an explicit statement that the test file is not just a
test — it is the structural guarantee that the silent failure mode does not silently return.

But a sentence in a markdown file is not enforcement. Here is how the actual enforcement is
layered:

The quality gate (`python scripts/quality_gate.py`) includes a regression-ledger check. It
reads `memory/bugs/regression-ledger.md`, finds every test file listed there, and fails if those
files are missing from the repository. This means: if someone deletes
`tests/test_close_discussion_promotion_pipeline.py`, the quality gate blocks the commit. The
canary's deletion is structurally blocked.

What is not structurally enforced is weakening. If someone edits the canary tests to no longer
test the thing they claim to test — removing the assertion, softening the condition — the quality
gate does not catch that. The architecture-consultant noted this explicitly in the review
(arch-F3). The canary contract sentence is the only guard against weakening; it creates a
documented obligation without mechanical enforcement.

Understanding this distinction matters when you are directing future work. "The regression tests
protect us" is only partially true. They protect against deletion (structural enforcement) and
accidental regression (they run in CI). They do not protect against intentional weakening that
leaves them green while hollowing out what they guard. The canary contract sentence is the social
and documentation layer of enforcement, and it requires human attention to remain meaningful.

---

## Concept 3: The C4-a vs C4-b decision — reconcile the client, never canonize the fiction

Alongside the two confirmed defects in `close_discussion.py`, the spec surfaced a collateral
problem. The `/promote` command — the interactive command a developer runs to actually promote a
pattern into Layer 3 memory — was querying the `promotion_candidates` database table using
column names that did not exist. Columns like `candidate_id`, `candidate_type`, `title`,
`target_path`, and `status` were referenced in the query. None of them were in the actual table
schema.

There were two ways to fix this.

Option C4-b: add the missing columns to the database schema. The table would then have the
columns the command expected. The command would work. This is the "extend the server to match
the client" approach.

Option C4-a: rewrite the command's query to use the columns the schema actually has. The command
would then correctly query real data. This is the "reconcile the client to the canonical server"
approach.

The spec chose C4-a, and the reasoning is worth internalizing: when client and server drift, the
question is always "which side is authoritative?" In this framework, the database schema defined
in `scripts/init_db.py` is the canonical definition. It was designed, reviewed, and represents
real decisions about what the pipeline actually stores. The `/promote` command's queries were
written by someone who imagined a richer schema — columns that never existed, tracking fields
whose semantics were never defined, status transitions that were never implemented. Those
imagined columns had no past and should not be given a future.

Extending the schema to back the fictional queries would not have been fixing the drift — it
would have been canonizing the fiction. Every fictional column added to satisfy a fictional query
is a commitment to implement the feature those columns imply, or to carry dead weight forever.

The rule this illustrates: when two things disagree about what the data looks like, identify
which one is the source of truth and reconcile everything else to it. Do not negotiate between
them by extending the source of truth to accommodate the drift.

---

## Concept 4: Verification before trust — a canary you haven't watched catch something isn't yet a canary

During the build, there was a step that could have been skipped under time pressure and would
have been invisible if it had been. Before committing the fixes, both defects were temporarily
reverted — the wrong kwarg removed from one call site, the wrong import name restored in the
other. The regression tests were then run against the broken code. They failed. With the exact
error messages they were designed to fail with. Then the fixes were re-applied, and the tests
passed again.

This is not routine CI behavior — it was a deliberate verification protocol. The reason it
matters is captured in how you should think about regression tests. A regression test that has
never been observed to fail against the regression it claims to guard is not yet a canary. It is
a green test. Green tests are good, but they make no promises about what they would catch. A
canary is a test that has demonstrably failed when the regression was present, and demonstrably
passed when the fix was applied.

The build summary records that this verification was performed. That record is not administrative
overhead — it is evidence that the canary contract has been honored in full, not just asserted in
a comment.

The broader principle: every test that is intended to serve as a structural canary should, at
least once, be observed catching the thing it claims to catch. This can happen during the
original build (as it did here), or it can happen when a future regression is introduced. If it
never happens either way, the canary is a claim without evidence.

---

## Where to look if something breaks

If the promotion pipeline begins silently failing again in the future, the first diagnostic step
is to check `promotion_candidates` in the Layer 2 database (`metrics/evaluation.db`) directly.
If `pattern_sightings` is accumulating but `promotion_candidates` is not, the seam is broken
again. The two most likely locations are `scripts/close_discussion.py:140-155` (the swallow-and-
warn zone) and any future drift between `surface_candidates`'s function signature and the call
site in `close_discussion.py`.

The regression tests are the fastest structural check. Run
`tests/test_close_discussion_promotion_pipeline.py` in isolation. The two canary tests
(`test_canary_surface_candidates_accepts_discussion_id_kwarg` and
`test_canary_compute_agent_effectiveness_import_name`) will fail immediately if either original
defect has returned, before you need to instrument anything.

If the canary tests pass but the pipeline still doesn't surface candidates, the issue is likely
in the Rule-of-Three counting logic inside `scripts/surface_candidates.py` — look at the HAVING
clause that requires three distinct discussion IDs per pattern hash.

---

## Summary of decisions made in this change

- **Retain swallow-and-warn, not fix it.** Closure resilience outweighs the alarm benefit.
  The debt is paid in canaries, not in restructuring.
- **Extend surface_candidates additively.** The new `discussion_id` parameter filters
  emission but not counting. Global Rule-of-Three integrity is preserved.
- **Adopt C4-a over C4-b.** Reconcile the command to the schema, not the schema to the
  command. The database schema is the source of truth.
- **Verify the canary before trust.** The build briefly reproduced both defects to confirm
  the tests fail correctly, then re-applied the fixes. This is documented in the build
  summary.
- **No ADR required.** This was defect repair, not a new architectural decision.
  (The architecture-consultant confirmed this; the C4-b path, had it been chosen, would
  have required an ADR because it would have changed the canonical schema.)
