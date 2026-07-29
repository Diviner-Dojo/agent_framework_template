---
adr_id: ADR-0029
title: "Separate scaffolding from governance; delete the scaffolding"
status: accepted
date: 2026-07-28
decision_makers: [developer, steward]
discussion_id: DISC-20260728-071754-framework-v4-modernization
spec_id:
supersedes: [ADR-0013, ADR-0016, ADR-0018, ADR-0020, ADR-0023, ADR-0026, ADR-0028]
extends:
scope: framework
risk_level: critical
confidence: 0.82
tags: [v4, scaffolding, governance, context-engineering, education-gate, opus-5]
---

## Context

The framework was built and refined across several model generations. Each
generation's weaknesses left a deposit: the model forgot mid-task, so we added
session-state files; it reasoned shallowly, so we gave it Domain Lens reasoning
sequences; it skipped verification, so we mandated verification steps; it lost
the thread in long sessions, so we built context sensors and wrap-up protocols.

Every one of those additions was correct when it was made. By v3.5 they totalled
roughly 9,000 lines of instruction: 25 slash commands, 26 skills, 12 agent
personas, 4 always-loaded rule files, and a 155KB session-state document that
`CLAUDE.md` instructed the agent to read at the start of every session.

Two things then changed at once.

**The model.** Opus 5 has a 1M-token context window with instruction-following
that holds across it, native planning, native self-verification, and native
self-correction. Anthropic deleted more than 80% of Claude Code's own system
prompt when migrating to it, with no measurable loss on coding benchmarks.

**The evidence about what scaffolding now costs.** Anthropic's published Opus 5
prompting guidance is specific: explicit verification instructions ("include a
final verification step," "use a subagent to verify") cause *over*-verification
and should be removed; self-correction instructions compound with the model's
own behaviour and add cost without improving results; and conflicting rules make
the model spend reasoning tokens deciding which instruction wins before it does
any work. It names "legacy harness scaffolding that adds separate verification
steps" as a thing to delete.

So the framework's instruction layer had stopped being free. It was no longer
neutral weight — it was actively degrading the thing it was built to improve.

## Decision

Split the framework in two along a single question, applied per file:

> **Does this exist because the model was weak?**

**Scaffolding** — instructions telling the model *how to think*. Collaboration
mode spectrums, exploration-intensity dials, Domain Lens reasoning sequences,
cross-agent dispatch protocols, mandated verification steps, hand-written git
scope detection, context-occupancy sensors, session wrap-up protocols. All
deleted.

**Governance** — constraints on *what may happen to the human*. Capture is
automatic and non-optional. ADRs are never deleted. Curated memory needs human
approval. The generator is never the sole evaluator. Understanding is offered
before merge. All kept, and several strengthened.

The load-bearing claim is that **these two categories move in opposite
directions as models improve.** Scaffolding decays toward deadweight.
Governance becomes *more* necessary, because the same capability that lets a
model rewrite a codebase in days lets it outrun its owner's understanding in
days.

A corollary about mechanism: where something must be guaranteed, it belongs in
deterministic code rather than in prose. Code that persists state after the
context window ends is not scaffolding at any model capability. That is why the
capture pipeline, the quality gate, and the risk scorer survive while the
documents describing how to use them mostly did not.

## Alternatives Considered

**Keep v3 and add an Opus 5 compatibility layer.** Rejected: it treats
accumulated instruction as an asset to be preserved. The instruction layer is a
liability that happened to be worth paying at the time. Layering on top makes
the conflict problem worse, not better.

**Aggressive consolidation in place** — merge and prune without deleting first.
Rejected because it optimizes toward the existing shape. You cannot discover
that a command is unnecessary by editing it; you discover it by removing it and
finding you never wanted it back. This is the reasoning behind the
delete-and-rebuild practice this ADR follows.

**Delete the education gates too**, on the argument that a more capable model
needs fewer human checkpoints. Rejected, and it is the most important rejection
here. It mistakes a guardrail for a crutch. The gates do not exist because the
model might write bad code; they exist because the developer must remain able
to make decisions about their own system. That need grows with model capability.

**Keep the goal-loop driver** (1,704 lines of deterministic build→verify→refine
control flow). Rejected: extended autonomous operation is now native model
behaviour, and an external driver constrains it to the loop shape we imagined in
advance. The human gates it enforced are preserved by `/review` and `/teach`.

## Consequences

**What this costs.** Roughly 100 files and the specific vocabulary built around
them — collaboration modes, exploration intensity, dispatch protocols, the
Bloom's-taxonomy education ladder. Anyone fluent in v3 has to relearn a smaller
surface. Some deletions will prove wrong; two were caught during the rebuild
itself (see below) and more will surface in use. Git history is the recovery
path, and this ADR is the map.

**What it buys.** The instruction surface drops from ~9,000 lines to under 900.
`CLAUDE.md` goes from 17KB to roughly 5KB. The 155KB session-state read at every
session start is gone. Context that was spent on process description is
available for the actual codebase.

**What it forecloses.** The framework can no longer claim to work identically
across model generations. It is now explicitly tuned to a capability level, and
that tuning has to be re-examined at each major model release. This ADR asserts
that the alternative — instruction that outlives its cause — is worse.

**The counter-argument, recorded honestly.** Deleting scaffolding transfers
trust from the framework to the model. If a future model regresses, or a
different model is used, behaviour this framework used to guarantee by
instruction is now assumed. The mitigation is that everything genuinely
load-bearing was moved into deterministic code and hooks rather than deleted —
but the mitigation is partial, and a reader should treat "the model does this
natively" as a claim to re-verify, not a permanent fact.

**Two over-deletions, caught during the rebuild and reversed**, because the
error mode is instructive:

1. The two-way ntfy collaboration loop was deleted as scaffolding. It is not:
   it is an I/O channel to a human, orthogonal to model capability, and *more*
   useful as sessions get longer.
2. `surface_candidates.py` was deleted while `close_discussion.py` still called
   it — and it produces the promotion candidates that Principle #6's human gate
   approves.

Both restored. The lesson is that the test question must be applied per file,
not per directory, and that "nothing references this" must be checked rather
than assumed.

**What we will wish we had known.** Whether the risk-scoring weights in
`assess_risk.py` actually track regret. They are a first guess, calibrated
against intuition rather than outcomes. `/retro` should revisit them once the
briefing ledger holds enough history to compare deferrals against the changes
that later caused trouble.

## Post-review amendments (2026-07-28)

Reviewed by four independent contexts before merge — REV-20260728-140000,
`DISC-20260728-135213-v4-framework-review`. Verdict REVISE, nine blocking.
Three of those findings change what this ADR claims, so they are recorded here
rather than only in the review:

**The classification test was not applied as stated.** The review found a third
over-deletion — `scripts/audit_calibration.py`, whose docstring describes
itself in this ADR's own governance vocabulary (writes proposals to a
human-approved queue, never edits a classifier surface) and which was
nonetheless swept up in a directory-level pass. The honest account is that
directory membership and category did some of the sorting this ADR credits to
the per-file question. Restored.

**The falsification plan was unexecutable as designed.** This ADR named one
thing it expected to be wrong about — whether the risk weights track regret —
and specified that `/retro` should check it. The deletion removed
`record_yield.py` (sole writer to `protocol_yield`) while leaving
`compute_agent_effectiveness.py` reading it, so `findings_false_positive` was
permanently 0 and calibration systematically flattering; and the `briefings`
table had no outcome column, so a deferral and a later regression could never
be joined. Measurement was classified as telemetry and telemetry as
scaffolding; the deletion prior in `/retro` survived while the only instrument
that could contradict it did not. The thin write path is restored — one
`protocol_yield` row per review, plus a `briefings.outcome` column — without
restoring the ~13,000 lines of dashboards and charts.

**A governance guarantee was moved from code into prose.** Rewriting
`/apply-framework` orphaned `scripts/distribute/`, dropping four fail-closed
controls on the cross-repo trust boundary — target-file prompt-injection
framing, secret redaction, per-instance assent, and the clean-tree gate — in
the same change whose `FRAMEWORK.md` states that a prose guarantee is a
request. The command is rewired onto the existing machinery; ADR-0021 stands.

The mechanism corollary in **Decision** therefore holds more strictly than
first written: *code that persists state after the context window ends is not
scaffolding at any model capability* — and that explicitly includes code whose
only job is to measure the framework, because a framework that deletes its own
instruments cannot tell whether its next deletion was right.

## Related

- ADR-0014 — memory substrate (retained unchanged)
- ADR-0021 — `/apply-framework` unification (still accepted; rewired, not retired)
- ADR-0024 — confidence calibration loop (still accepted; restored)
- REV-20260728-140000 — the review that produced these amendments
- `PHILOSOPHY.md` — the values this decision serves
- `memory/archive/v3-framework/` — v3 documents preserved verbatim
