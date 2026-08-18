---
adr_id: ADR-0035
title: "I clear it: the education gate clears only on the developer's explicit action — the tutor teaches, records, and registers, but never marks the gate complete"
status: accepted  # Principle #6 developer approval given in-conversation 2026-08-14 ("Approve both"), after being taught (DISC-20260815-014203, sealed) and steering the gate lighter mid-walkthrough (walkthrough-only default queued for the tutor-loop dedup spec)
date: 2026-08-11
decision_makers: [developer]
decision_provenance: >-
  All three governing decisions are the developer's, verbatim, with their channels:
  (1) "I clear it" — ntfy reply, 2026-08-10, allow-list matched; (2) "Yes,
  everywhere" — in-conversation, 2026-08-10, extending the rule to the ADR-0029
  ingested-transcript route; (3) the Q9 conditions — sealed in
  DISC-20260810-181205-quiz-wave3-sliced as a decision event: no independent
  grading check gets built now ("empty governance" risk), per-attempt verbatim
  capture continues, and the tutor-asymmetry question travels with any
  propagation. The implementation mechanics (the "clear-eligible" outcome word,
  the clear_command field, the v1.1 document revision, the guard shapes) are the
  builder's elaboration and have NOT been individually approved.
discussion_id: DISC-20260811-210611-i-clear-it-gate-clearing
discussion_provenance: >-
  The build discussion holds 18 events: 14 `path-not-taken` records written via
  scripts/write_event.py at the moment each choice was made (9 in the first
  build round; 3 in the REVISE round — eligibility persistence, marker
  lifecycle, the wire-the-watch choice; 1 in the N round — the N3
  detector-widening call, chosen over documenting a hole only after the
  widening was measured safe; 1 in the Steward round — carrying the three
  Steward-measured escape classes as a rot-checked KNOWN-UNCAUGHT register
  rather than a widening, with the measured collisions that decided it),
  3 append-only corrections (two falsifier refinements, and the N2 turn
  recording that the F2 authorization superseded turn 7's
  leave-SKILL.md-unedited decision), and 1 reflection recording a drive-by
  lint fix. Several falsifiers are honestly declared absent rather than
  invented; one clause-granularity decision was driven by a measured detector
  escape on the real pre-rule text. The developer's decisions themselves are
  sealed in DISC-20260810-181205-quiz-wave3-sliced.
precedent: >-
  The first real clearing under this rule happened BY HAND before the code
  matched it: gate EDU-20260810-wave3-sliced, cleared by the developer, commit
  d521a21. This ADR makes the code and prose match the practiced rule, not the
  other way round.
spec_id:
supersedes:
extends: ADR-0029
scope: framework
risk_level: high
confidence: 0.8
tags: [education-gate, gate-registry, principle-5, principle-6, repocademy, ingest, contracts, i-clear-it, instruments-first]
---

## Context

The education gate had two closers and neither was the developer:

- **The in-session route.** `/quiz` Step 5 instructed the agent: *"And when a
  session CLOSES an open gate, retire it… clear it in the same breath as
  recording the results"*, followed by the `gate_registry.py clear` invocation.
  `/walkthrough` Step 7 echoed it: a deferred gate is *"retired with
  `gate_registry.py clear` once `/quiz` closes it"*.
- **The ingested-transcript route (ADR-0029).**
  `scripts/education/ingest_walkthrough_session.py::_decide` computed the LOCKED
  formula (`walked AND quiz_avg >= 0.70 AND explain_back_passed`) and, on a pass,
  called `clear_gate()` itself — the registry flipped with no human in the loop.

`gate_registry.py`'s own module docstring names the hazard: `clear_gate` writes
`--session-id`/`--discussion-id` through as opaque strings, validating nothing —
so an agent that clears is an agent that can produce a registry reporting zero
education debt with zero education having happened. A tidy backlog bought by the
agent clearing unpaid gates measures the tutor's tidiness, not the developer's
understanding. The developer's reply closed the question: **"I clear it."**
Asked whether the phone route — where he was present for the session — kept its
auto-clear, he answered **"Yes, everywhere."**

## Decision

The education gate clears **only** on the developer's explicit
`gate_registry.py clear` action, recorded with `cleared_by` provenance. The
educator/tutor and the commands that orchestrate it **teach, record, and
register — and never mark the gate complete**. Concretely:

1. **Registering stays agent-runnable.** `gate_registry.py add` (and the
   ingest's automatic `re-defer`) are debt *bookkeeping*; the rule governs the
   *release* of debt, not its registration.
2. **Both education routes present; neither clears.** The in-session route
   presents evidence (sealed discussion ids, session id, what was demonstrated)
   plus the exact paste-ready command; the ingest computes the same locked
   formula, reports **CLEAR-ELIGIBLE**, prints the exact command, and records a
   durable **additive `clear_eligible` marker** on the gate — `status` stays
   `open`, and the marker (removed again by a clear or a re-defer, and rejected
   by the validator on a cleared gate) is what keeps a *paid-but-unclaimed* gate
   distinguishable from unpaid debt after the console is gone. The session-start
   backlog renders eligible gates as their own "awaiting YOUR clear" bucket, and
   `gate_registry.py list --eligible` re-prints the paste-ready command at any
   time (pinning `--registry` whenever a non-default registry is in play, so the
   paste can never mutate the wrong file).
3. **The `clear_gate` function and CLI remain intact** — they are the
   developer's tool. Only automatic invocation ends.

## What changed at each surface

| Surface | Change |
|---|---|
| `.claude/commands/quiz.md` Step 5 | The agent PRESENTS the clear command + evidence and never runs it; `add` stays agent-runnable; the one-way-ratchet warning re-aimed — the ratchet is released by the DEVELOPER's clear, and an agent-tidied backlog is the abolished defect |
| `.claude/commands/walkthrough.md` Step 7 | "retired with `gate_registry.py clear` once `/quiz` closes it" → presented by `/quiz` Step 5, run by the developer |
| `.claude/agents/educator.md` §2.7 + output contract | Parking is bookkeeping; the clear is the developer's; the ingested-path comment now says the 0.70 formula establishes CLEAR-ELIGIBILITY, flip is the developer's |
| `scripts/education/ingest_walkthrough_session.py` | `_decide`'s passing branch returns outcome `clear-eligible` with registry action `none`; `clear_gate` is never invoked on the automatic path (the step-5 comment states this at the exact spot the review-gates skill's grep lands on); the eligible branch writes the additive `clear_eligible` marker; `IngestResult.clear_command` carries the paste-ready command (with `--registry` pinned for non-default registries); the CLI prints the eligibility block after the unchanged machine summary line; validation, per-attempt rows, capture, idempotency guards, compensation, and the automatic re-defer are preserved |
| `scripts/education/gate_registry.py` | Additive schema field `clear_eligible` (validated; forbidden on a cleared gate); `mark_clear_eligible()`; `clear_gate`/`re_defer_gate` remove the marker; `backlog_summary` renders eligible gates as their own "paid, awaiting YOUR clear" bucket instead of unpaid debt; `list --eligible` re-prints the developer's command; `clear_command_for()` centralizes command construction |
| `docs/education/CONTRACTS.md` | FORMAL revision, not a quiet edit: session-transcript format bumped to **v1.1** with dated changelog entries (the semantic revision, then the additive `clear_eligible` field); §1.4 restated — formula passing establishes CLEAR-ELIGIBILITY; `cleared` requires the developer's explicit clear with `cleared_by` provenance. Wire `contract_version` stays the int 1 (schema unchanged; see Alternatives), and §4 now defines the semantic-revision/wire-compatible tier this uses, so the LOCKED versioning policy and the revision no longer contradict each other |
| `.claude/skills/selecting-review-gates/SKILL.md` | The pre-ADR-0035 auto-clear descriptions corrected ("does clear its registry gate arithmetically", "before `clear_gate()` mutates", "Both directions are instructed"): the skill now states eligibility-then-developer-clear, and the file is permanently scanned by the check-14 detector |
| `.claude/commands/retro.md` | The Q9 watched signal made real: a zero-miss-per-session query (the all-first-ask signature) added to the education data block, with reading guidance — a signal to a human, never a gate |
| `tests/test_education_gate.py` | New check 14: a relation-based detector (`agent_directed_clear_instructions`) bans agent-directed clear instructions across every wording it has been measured against — including a critic's escape phrased with no clear/retire verb — while permitting the presented command (residual holes named in the probes); behavioral guards run the ingest against a tmp registry and assert the gate stays open, the durable marker is written, the command prints and is re-printable via `list --eligible`, and a spy on `clear_gate` sees zero calls |
| `tests/test_ingest_walkthrough_session.py`, `tests/test_gate_registry.py` | Old auto-clear assertions updated to the new contract (a behavior change, not a weakening); new suites pin the marker's validation, lifecycle (clear/re-defer removal), command construction, backlog bucketing, and the `list --eligible` re-print |

## The contract revision and its cross-repo obligation

`docs/education/CONTRACTS.md` is a LOCKED, versioned cross-repo contract; the
clearing-rule change is a semantic break at the boundary even though no payload
byte moved. It is therefore revised formally: version bump to v1.1, dated
changelog entries (the semantic revision, and the additive `clear_eligible`
gate field — tolerant readers ignore the unknown key by the contract's own
Reader-discipline rule, and the strict repo validator was updated in the same
change), and §1.4 restated. §4's versioning policy gained an explicit
**semantic-revision/wire-compatible tier** (document version moves, wire int
stays, consumers notified) — before that, the policy's own "changing the
clearing rule bumps `contract_version`" line contradicted the revision it was
being applied to; the tier also requires the notification to be discharged to a
named carrier whenever a consumer-visible value vocabulary moves, as it did
here (`outcome=cleared` → `outcome=clear-eligible`). **The notification is
REGISTERED, not merely owed**: a dated entry on the established
sibling-notification board
(`~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md`, 2026-08-11) carries this
ADR, the CONTRACTS v1.1 revision, the outcome-vocabulary change, the
`clear_eligible` additive field, the adoption constraints (human-run clear,
library-only `mark_clear_eligible`, eligible-inside-the-debt-rendering), and
the Q9 tutor-asymmetry rider. Sibling projects — insight_journal builds
against this contract — read that board at session start and pick the entry up
at their next framework update. No other project repo was touched by this
change (read-only rule respected). Per the Q9 conditions, **the
tutor-asymmetry question travels with any propagation** of this rule: the
phone-side tutor both teaches and grades, and a derived project adopting the
rule must inherit the open question, not just the mechanism.

## Alternatives Considered

1. **Keep auto-clear on the phone route, since the developer sat that session.**
   Rejected by his explicit **"Yes, everywhere."** The presence of the developer
   in the session is not the presence of his decision in the registry; the rule
   is about who performs the closing action, not who was in the room.
2. **Build an independent grading check now** (a second context re-grading the
   transcript before eligibility). Rejected by the developer's own Q9 reasoning:
   an automated grader bolted on today is **"empty governance"** — a mechanism
   that looks like oversight and verifies nothing he trusts. His recorded
   conditions instead: per-attempt verbatim capture continues (the evidence
   stays auditable), and the tutor-asymmetry question travels with any
   propagation. The grading gap is WATCHED, not closed (see Limitations).
3. **Block the gate — make an uncleared gate withhold something.** Rejected:
   Principle #5 makes understanding **offered, not withheld**; nothing in the
   framework fails on an open gate, and `gate_registry.py backlog` stays
   informational. Turning the developer's clear into a build condition would
   convert his authority into his chore.
4. **Bump the wire contract to v2 and pin the ingest to it.** Rejected: the
   payload schema is byte-identical, and a v2 pin would make the ingest reject
   every transcript the live phone producer emits (`contract_version: 1`),
   breaking the capture this slice explicitly preserves. The version signal
   belongs on the document revision (v1.1), and the wire gate stays where the
   compatibility risk actually is.
5. **Report `cleared` without flipping the registry.** Rejected: an outcome word
   that contradicts the registry teaches every log reader a state that never
   happened; the truthful verdict the formula can still establish is
   eligibility, so that is the word (`clear-eligible`).
6. **Make re-defer developer-only too (symmetry).** Rejected: re-defer
   registers/renews debt — the same class as `add`, which the decision keeps
   agent-runnable; a manual re-defer would leave a walked-away session parked
   under a stale reason.
7. **Keep eligibility ephemeral (stdout only), or in a sidecar file.** The first
   round shipped stdout-only and the review vetoed it: the registry lost the
   paid-but-unclaimed vs unpaid distinction — a gate the developer quizzed at
   0.9 rendered byte-identically to one nobody opened, and the session-start
   nudge asked him to re-learn paid gates. A sidecar file was rejected as a
   second store that can disagree with the registry it annotates. Chosen
   instead: the additive `clear_eligible` marker on the gate itself, with a
   **named naming risk** — "eligible" drifting into being read as "cleared" —
   mitigated by the field name, the validator forbidding the marker on a
   cleared gate, the backlog keeping eligible gates inside the debt block, and
   the changelog stating the distinction.

## Consequences

- The registry's `cleared` status becomes what it claims to be: a record of the
  developer's own act, with `cleared_by` as his provenance. The precedent
  clearing (EDU-20260810-wave3-sliced, commit d521a21) is the pattern, not an
  exception.
- One more manual step per paid gate: paste one presented command. The evidence
  and command arrive assembled, the command survives the console (`list
  --eligible` re-prints it from the durable marker), and the paste pins its
  registry when a non-default one is in play. The cost is a decision, not a
  chore.
- The non-atomic clear window in the ingest is gone by design — no crash state
  can leave a gate cleared without evidence, because the automatic path cannot
  clear at all. The remaining window (re-defer or marker not yet saved after
  the DB commit) fails toward under-claiming.
- **The outcome vocabulary is the real cross-repo break, and it is named, not
  soft-pedaled**: the value `cleared` no longer occurs on the automatic path —
  the CLI machine summary line now emits `outcome=clear-eligible` where it
  emitted `outcome=cleared`, and §1.4's Reported-outcome column changed the
  same value. The line's *shape* is unchanged, but any watcher or log parser
  matching on `outcome=cleared` silently stops matching; the concrete diff is
  in the CONTRACTS.md v1.1 changelog. Clear-eligible runs additionally append
  the ingest's own eligibility lines after the summary line.
- The routine `cleared` flip moving to a human CLI puts a human paste and a
  watcher batch on the same file as a matter of routine. Atomic replace
  prevents torn files, not lost updates, so a paste-during-batch collision can
  silently drop a write; the single-watcher, human-at-desk topology makes it
  unlikely, and the lockfile decision is explicitly re-affirmed as DEFERRED in
  CONTRACTS.md §4 — revisit on first observed collision or a second watcher.

## Honest limitations (WATCHED, per Q9)

- **Nothing verifies the grading itself.** Per-item scores remain
  producer-authoritative (CONTRACTS.md §1.3): the phone-side tutor both teaches
  and grades, and the in-session tutor judges the answers it elicited. The
  developer's clear attests *his* act on the presented evidence; it does not
  re-grade the evidence. This is deliberately not closed now (Alternative 2) —
  it is WATCHED, and the watch is **wired, not aspirational**: `/retro`'s
  education block now runs the zero-miss-per-session query (the all-first-ask
  signature — a sustained run of sessions with zero recorded misses is grading
  gone soft; per-attempt rows are what make it visible), with instructions to
  name the pattern in the retro report and gate nothing on it.
- **The detector's coverage is measured, not total.** Check 14 catches every
  wording in its planted set — including a critic's escape phrased with no
  clear/retire verb at all ("execute the presented registry command … update
  its status to cleared") — but its exemptions are a known residual hole: a
  violation phrased with "developer" in the same clause, or inside a quotation
  of "I clear it", is exempted, the price of leaving the legitimate
  presentation unflagged. The ingest-side guards are LAYERED, not independent:
  a critic's alias mutation defeated both the source grep and the `clear_gate`
  spy, and the behavioral gate-stays-open assertion on a real tmp registry was
  the layer that held. All of this is recorded in the guard file's probes, not
  papered over.
- **The registry's own trust model is unchanged.** `clear_gate` still validates
  nothing about the ids it is given; the rule changes who runs it, not what it
  checks. A forged developer clear was out of scope here and remains so. The
  `clear_eligible` marker inherits the same posture: it attests that an ingest
  run recorded a passing session, not that the grading was sound.
- **A small housekeeping fix rode along, on record**: one pre-existing ruff
  UP038 finding in the ingest (`isinstance` tuple form, untouched line, verified
  identical at HEAD) was modernized so the touched-file lint runs clean —
  logged as a reflection event in the build discussion rather than left as an
  unexplained diff line.

## Status of this decision

Proposed; the developer's three decisions are on record (see provenance), the
implementation awaits `/review` (high-risk framework governance surface — the
`selecting-review-gates` plurality floor of at least two independent
specialists applies) and the education gate itself, which — fittingly — he
clears.
