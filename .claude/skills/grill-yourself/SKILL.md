---
name: grill-yourself
description: Inverted grill — the model interrogates its own plan on the user's behalf, ghost-writing the hard questions in the user's voice and answering each with a recommendation, so the human's job shrinks to rendering verdicts. Use when the user wants a plan stress-tested but doesn't know what questions to ask, says "grill yourself," or asks the model to red-team its own proposal. Checkpoints every verdict to brainstorms/ so the session survives interruption.
---

_Purpose: freeze frontier-level interrogation into a reusable pattern. The
model plays both interrogator and expert; the human stays the arbiter. A
secondary and explicit goal is teaching: over repeated sessions the user
should begin anticipating the questions unaided. Success includes this skill
becoming less necessary._

## Roles

- **The model** ghost-writes the questions a top-tier skeptical engineer
  would ask about the current plan, phrased in the user's voice, one at a
  time — and answers each with a concrete recommendation.
- **The user** renders a verdict per question: **accept**, **amend X**,
  **dig deeper**, or **explain** (a first-class move, never a failure state —
  it means re-teach at a lower altitude before asking for a verdict).

## Three-altitude format (default for every question)

1. **Headline** — one plain sentence a tired person can act on alone.
2. **Plain-language layer** — what's at stake, why this question exists,
   which taxonomy category it belongs to, and an everyday analogy.
3. **Technical layer** — full detail and the recommendation's mechanics.
   Offer it; don't force it. If the user says they're tired, lead with
   altitudes 1–2 only and hold 3 for request.

Never make the user ask to have things simplified twice. If they downshift
once, stay downshifted for the rest of the session.

## The question taxonomy (the heart of this skill)

Walk the plan against these categories. Not every category applies to every
plan; say so and skip rather than manufacture a question. Order by risk, not
by list position.

1. **Validity** — Does this measure/do what it claims? What confound would
   make the result mean something else? (Rule: separate the thing tested
   from the scaffolding around it; add a control condition.)
2. **Checker ceiling** — Can whoever verifies the work recognize quality
   they couldn't produce? (Rule: verification is easier than generation —
   move intelligence into checklists the weaker checker can audit.)
3. **Ground truth** — What is actually true here, independent of anyone's
   performance? (Rule: authored manifests and historical records beat even
   an expert's transcript; experts get graded too.)
4. **Goodhart** — If we optimize against this measure, does it corrupt?
   (Rule: hold out a vault the optimization loop never sees; open it only
   at declared milestones.)
5. **Signal vs. noise** — Is run-to-run variance louder than the effect?
   (Rule: repeat runs, report median + range, only trust non-overlapping
   ranges; treat divergence in reference runs as a defect in the task, not
   the runner.)
6. **Consumer** — Who reads the output and what decision changes? (Rule: a
   measurement with no attached decision is a hobby; name every consumer
   and emit a view per consumer.)
7. **Opportunity cost** — What's the best thing NOT done because of this?
   (Rule: triage by perishability — spend scarce resources only on what
   nothing else can do; re-run the budget math after scope grows.)
8. **Staleness** — What changes under this over time, and how would we
   know? (Rule: pin baselines to versions; retire them to history rather
   than discard; alarm on same-conditions drift.)
9. **Leakage** — What escapes (into training data, into public view, into
   the optimization loop) and what does the escape corrupt? (Rule: keep one
   never-published yardstick; treat post-publication scores as suspect-high.)

## Session mechanics

- Open by listing the taxonomy branches you intend to walk for THIS plan,
  so the user sees the terrain and can reorder.
- One question per turn. Recommended answer always attached. Wait for the
  verdict before proceeding.
- If a question is someone else's call or needs data the user lacks, record
  it under **Flagged for others** and move on — don't guess.
- Scope-growth audit: accepted answers add work. Every few questions,
  re-ask category 7 against the plan's own growth.

## Checkpointing (inherited from grill-me)

One file per topic at `brainstorms/YYYY-MM-DD-<topic-slug>.md`, same
structure as grill-me (Highlights / Key decisions / Open threads / Flagged
for others / Q&A log). Append the exchange the moment a verdict lands,
before asking the next question. Record verdicts verbatim. Resume protocol
identical to grill-me: find the file, replay highlights, continue from the
first open thread, never re-ask answered questions.

## Teaching stance

You are not just resolving decisions; you are demonstrating how to think
about problems. Name the taxonomy category aloud each time so the pattern
becomes visible and transferable. If the user starts asking a category's
question before you do, say so — that's the skill working.

## Worked example

See `brainstorms/2026-07-01-fable-eval-design.md` — the session that
produced this skill, in which the user grilled the model over a nine-
question walk of an eval-suite design.
