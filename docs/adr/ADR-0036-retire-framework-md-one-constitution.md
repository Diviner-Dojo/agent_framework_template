---
adr_id: ADR-0036
title: "Retire FRAMEWORK.md: one constitution (CLAUDE.md), one philosophy (PHILOSOPHY.md), and /seed inlines the seven principles instead of delegating to a second file"
status: accepted  # Principle #6 developer approval given in-conversation 2026-08-17: "I want you to fix B2 so there is consistency between CLAUDE.md and the philosophy", after a recommendation on record (delete + rewire /seed) and a stated end state of CLAUDE.md = constitution, PHILOSOPHY.md = philosophy
date: 2026-08-17
decision_makers: [developer]
decision_provenance: >-
  The developer asked for a recommendation on B2 and received one (delete
  FRAMEWORK.md and rewire /seed, criterion given: "evolve elegantly without
  confusion"). He then named the end state himself — consistency between
  CLAUDE.md and the philosophy — which is the delete branch, not the
  fix-in-place branch. The mechanics below (inlining the seven into /seed's
  generated CLAUDE.md, the verification-step change, the register deletions)
  are the builder's elaboration and have NOT been individually approved.
discussion_id: DISC-20260816-194513-review-seven-principle-reconciliation
review_id: REV-20260818-004500
prior_review_id: REV-20260816-194513
review_provenance: >-
  REV-20260818-004500 is the review OF THIS CHANGE: a 3-specialist ensemble panel
  that saw the FRAMEWORK.md deletion, the /seed rewire and the guard rewrite, none
  of which any earlier review had seen. It returned THREE BLOCKING findings, all
  fixed before commit, two of them defects in this ADR itself: a false claim that
  CLAUDE.md is not in FRAMEWORK_PATHS, and a false claim that the deletion stops
  the public template publishing contradictory principle lists. Both corrections
  are recorded inline below rather than silently applied.
  The earlier REV-20260816-194513 is retained as prior_review_id: it is where
  B2 was raised as a BLOCKING finding and left as an open governance decision
  rather than fixed in that change. The panel's meta-finding — "the boundary tracked what the tooling
  made LOUD" — and its "clean tell" (FRAMEWORK.md excused as "does not
  propagate" while tests/ was deferred because "the promotion pushes the whole
  tree") are the direct ancestors of this ADR. This decision resolves the
  contradiction in favour of the measured model: the file propagates.
spec_id:
supersedes:
extends: ADR-0031
scope: framework
risk_level: high
confidence: 0.85
tags: [constitution, principles, seed, propagation, adr-0031, principle-4, doc-sync, instruments-first]
---

## Context

`FRAMEWORK.md` was the framework's "universal principles" file: the constitution
that applied to *any* project, with `CLAUDE.md` holding project-specific
configuration and `PHILOSOPHY.md` holding the *why*. Three files, three jobs.

The split did not hold. Measured on 2026-08-17:

- **It published a complete competing constitution.** `FRAMEWORK.md:9-16`
  enumerated **eight** non-negotiable principles while `CLAUDE.md` carried
  **seven** (ADR-0031 Decision 6, ratified per-principle 2026-08-05/06). It kept
  *Collaboration precedes adversarial rigor* at slot 3 and *Least-complex
  intervention first* at slot 8 — both retired — so a reader landing on it never
  learned a merge had happened. This is worse than a stale count string: a
  restatement in full under old numbering reads as authoritative.
- **It contradicted a ratified reversal.** Its principle 6 read *"Education gates
  before merge. Walkthrough, quiz, explain-back, then merge"* — the hard-gate
  model that Principle #5 (*understanding before merge — offered, not withheld*)
  and ADR-0035 (*"I clear it"*) explicitly replaced.
- **It was four months stale** — header `v3.0` against a template at `v3.6`.
- **It cited an ADR that never existed.** `FRAMEWORK.md:5` pointed at `ADR-0065`
  for "the decomposition rationale". The repository has 34 ADRs; the highest is
  `ADR-0035`. The file's own justification was a dangling reference.
- **It travelled on two channels.** It is on `upstream/main` (public), and
  `.claude/commands/seed.md:31` copied
  `~/.claude/shared-memory/FRAMEWORK.md` into **every project `/seed` created**.
  An earlier note in `tests/test_constitution_consistency.py` excused it as
  *"NOT in FRAMEWORK_PATHS so it does not propagate"* — true only of the
  `/apply-framework` channel, and false overall. That false clause is the
  "clean tell" the review panel identified.

Everything else in the file was duplicated elsewhere and was verified to have a
home before deletion: the agent roster, collaboration-mode spectrum and
exploration intensity in `docs/AGENT_ARCHITECTURE.md` and
`docs/FRAMEWORK_SPECIFICATION.md`; the capture pipeline in
`docs/CAPTURE_PIPELINE.md`; ID conventions, directory layout, commit protocol
and invocation pattern in `CLAUDE.md`.

**Why the split existed, recorded so it is not rebuilt.** The original intent was
sound: a project's *configuration* churns while *universal principles* do not, so
freezing the principles in a separate shared file looked like protection against
per-project drift. The failure mode was the opposite of the one anticipated. A
second copy of the constitution did not stay frozen — it went stale, and because
it was never the file anyone edited during a principle change, nothing pulled it
forward. Two homes for one rule is not redundancy; it is a guarantee that one of
them is wrong and no one can tell which.

## Decision

**Delete `FRAMEWORK.md`. There is exactly one constitution (`CLAUDE.md`) and one
philosophy (`PHILOSOPHY.md`), and `/seed` inlines the seven principles into each
new project's own `CLAUDE.md` rather than delegating to a shared file.**

Concretely:

1. `FRAMEWORK.md` is deleted from the template and from the public repository on
   the next promotion.
2. `/seed` Step 1 no longer copies it, and carries a standing note that the file
   is retired and a lingering `~/.claude/shared-memory/FRAMEWORK.md` must not be
   copied.
3. `/seed` Step 5 now requires the generated `CLAUDE.md` to carry the seven
   principles **inline, verbatim**, including ADR-0031's "Retired, and where the
   value went" note so a stale citation in an older artifact can be re-pointed.
4. `/seed`'s verification step checks that the seven are present in `CLAUDE.md`
   instead of checking that `FRAMEWORK.md` exists.
5. The `FRAMEWORK.md` entries in `KNOWN_STALE_CITATIONS` and
   `KNOWN_STALE_COUNTS` are deleted — the debt is paid by removal, not exempted.

The duplication this creates (each seeded project carries its own copy of the
seven) is deliberate and is the point: **one authoritative copy per project beats
one shared copy that silently drifts.** A project's constitution should be a file
its own maintainers edit and review, not an inherited artifact nobody owns.

## Alternatives Considered

- **Supersede in place** — replace the body with a pointer to `CLAUDE.md`.
  *Rejected*: it leaves the most authoritative-sounding filename in the
  repository containing nothing but a redirect, which invites a future
  maintainer to "fill it back in".
- **Fix it in place** — renumber to seven and re-sync it.
  *Rejected against the developer's stated criterion, "evolve elegantly without
  confusion."* It preserves exactly the structure that allowed four months of
  undetected divergence. The next principle change would have to remember to
  edit two files, and the guard that would catch a miss is the one that just
  demonstrated it reports such files as *tracked debt* rather than failures.
- **Keep it and add a sync guard** — a test asserting the two lists match.
  *Rejected*: this is the least-complex-intervention trap in reverse. Adding
  machinery to keep two copies of a constitution agreeing is more complexity
  than deleting one copy, and `PHILOSOPHY.md` § *Growth has a brake* prefers the
  removal.
- **Delete `FRAMEWORK.md` AND generate the principles block from a single canonical
  source**, recording its `sha256` in `framework-lineage.yaml` as a lineage trait so
  `/apply-framework` can report "constitution block is N revisions behind" as a
  per-instance, human-gated offer. **DEFERRED, not rejected** — developer decision
  2026-08-17, after the review raised it.

  > **Added after the fact (Principle #1).** The three alternatives above were the
  > only ones this ADR originally listed, and the independent review named that as a
  > false trichotomy: all three *keep* `FRAMEWORK.md`, so none of them was actually
  > an alternative to the chosen design's weak point, which is the *replacement*
  > mechanism rather than the deletion. The "sync guard" rejection above is answered
  > against the wrong target — a guard keeping two files in one repo agreeing, not a
  > generator with a recorded hash across a fleet.
  >
  > The review's argument for it is evidence-backed and is recorded here undiluted:
  > the shared `FRAMEWORK.md` drifted for four months and **was caught**, by a guard,
  > in a register, with a named owner. `agentic_journal` and `VerificationPortal`
  > carry **inlined** constitutions and have drifted to *different counts from each
  > other* — measured 2026-08-18: `agentic_journal` **9**, `VerificationPortal` **10**,
  > against this template's **7** — plus a superseded education model, caught only by
  > an ad-hoc read-only sweep with no guard, no register, no owner. On this repository's own evidence, inlining
  > generalises the *undetected* failure mode and retires the *detected* one.
  > Estimated cost of the alternative: ~40 lines of extraction and hash comparison,
  > one lineage field, one `/apply-framework` report line.
  >
  > It is deferred because the developer scoped this change to the review's blocking
  > items. The gap it addresses is live and is named honestly in Consequences rather
  > than closed here.

## Consequences

**Positive.** One constitution **in this repository**, so a principle change has
exactly one edit site and no possibility of silent divergence here. `/seed`'s output
becomes self-contained: a seeded project's constitution no longer depends on the
seeding machine's `~/.claude/shared-memory/` contents, and Step 1 now fails loudly
rather than silently producing a project with no philosophy file.

> **Correction (Principle #1).** The first version of this ADR also claimed "the
> public template stops publishing two mutually contradictory principle lists."
> Measured on `upstream/main` 2026-08-17, that is false: public `CLAUDE.md` carries
> **nine** numbered principles (including both that ADR-0031 retired), public
> `PHILOSOPHY.md` still reads *"Relationship to the eight principles"*, and
> **ADR-0031 was never promoted** — the newest public ADR is 0028. Deleting
> `FRAMEWORK.md` from the public tree in isolation therefore *removes* a list
> without adding the correction, and leaves a public adopter with two disagreeing
> lists and no record that a renumbering ever happened.
>
> **This makes a promotion requirement, not just a consequence:** the promotion that
> carries this deletion MUST also carry `CLAUDE.md`, `PHILOSOPHY.md`, and the ADRs
> that explain the renumbering (0029–0036, ADR-0031 above all). Promoting the
> deletion alone would leave the public template strictly worse than before.

**Negative / risks.**

- **Seeded projects diverge from the template over time.** Inlining means a later
  template principle change does not reach existing projects automatically.
  Propagation to derived projects is `/apply-framework`'s job: `CLAUDE.md` **is** in
  `FRAMEWORK_PATHS` (`scripts/lineage/manifest.py:24`), so the hub's version is
  offered against the target's, per file, for a human to accept or decline — an
  offer, never an automatic write. That is the property that matters here: the
  update is *available* and *visible*, and consent is per-instance, which is what
  Prime Objective test (c) requires. It is not the property of being untouchable.

  > **Correction, recorded rather than quietly fixed (Principle #1).** The first
  > version of this ADR asserted the opposite — that `CLAUDE.md` is *not* in
  > `FRAMEWORK_PATHS` and is "never overwritten in a derived project" — and rested
  > this consequence on it. That was false, and it is the same error shape this ADR
  > dissects above as the review panel's "clean tell": a confident claim about a
  > propagation channel that nobody measured. It was caught by the independent
  > review panel (`REV-20260818-004500`), not by the author. The correction does not
  > change the decision, but it does change the argument, and the argument is the
  > artifact.

  **The residual risk is real and is NOT closed by this change:** nothing audits
  whether a derived project's inlined constitution still matches the template's.
  `tests/test_constitution_consistency.py` is repo-local. Two derived projects
  (`agentic_journal`, `VerificationPortal`) already carry superseded constitutions of
  **9 and 10 principles respectively** (measured 2026-08-18), and that was found by an
  ad-hoc read-only sweep, not by any guard. A generated-block-plus-recorded-hash design was proposed during
  review as the fix for exactly this and is deliberately deferred, not rejected —
  see the review's advisory list.
- **A stale `~/.claude/shared-memory/FRAMEWORK.md` persists** on this developer's
  machine — measured 2026-08-17: present, 12,706 bytes, dated May 17, carrying a
  *different and larger* eight-principle variant than the file this ADR retires.
  It is outside this repository and is deliberately **not** deleted. `/seed` Step 1
  now refuses to copy it and hard-fails if a `FRAMEWORK.md` ever lands in a seeded
  target, so the mitigation is mechanical rather than an instruction to a reader
  (Principle #2). Machine-level cleanup remains the developer's action.
- **Historical references are left intact.** ADRs, sealed discussions, reviews
  and research comparisons that mention `FRAMEWORK.md` are **not** edited
  (Principle #4 in spirit: superseded, never rewritten). They correctly describe
  the state at the time they were written; this ADR is the reference that
  re-points them.
- **Derived projects already carry superseded constitutions, and not even the same
  one.** Measured read-only 2026-08-18 by counting the numbered items inside each
  project's own *Non-Negotiable Principles* section: `agentic_journal` **9**,
  `VerificationPortal` **10**, this template **7**.

  > **Correction (Principle #1).** Every prior artifact in this effort — the handoff,
  > `BUILD_STATUS.md`, and the first draft of this ADR — asserted these projects carry
  > "the retired **eight**-principle constitution", and one review round repeated it.
  > Nobody had counted. The real numbers are 9 and 10, and the divergence *between the
  > two derived projects* is the finding: they did not drift together, and no artifact
  > in this repository would have revealed that. This is the single strongest piece of
  > evidence for the deferred generated-block alternative above, and it was produced by
  > checking a number that four artifacts had been copying from each other. That is present state, not a consequence of this change, and it is owned by
  the separate propagation effort. No writes were made to either.

**Verification.** `tests/test_constitution_consistency.py` enforces the end state
mechanically: `enumerated_principle_lists()` fails any live file other than
`CLAUDE.md` that carries a self-contained numbered principle list, so a
reintroduced second constitution turns the suite red rather than drifting
quietly for four months.
