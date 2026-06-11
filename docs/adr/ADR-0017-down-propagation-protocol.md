---
adr_id: ADR-0017
title: "Down-Propagation Protocol — consent model, classification taxonomy, and the mechanical safety floor"
status: superseded
date: 2026-05-23
decision_makers: [facilitator, architecture-consultant, independent-perspective, security-specialist, qa-specialist]
discussion_id: DISC-20260523-170335-distribute-interpreted-assessment-spec-review
supersedes: null
superseded_by: ADR-0021
scope: framework
risk_level: high
confidence: 0.85
tags: [distribute, down-propagation, prime-objective, consent, lineage, classification, b1]
---

## Context

ADR-0003 established **up**-propagation (derived → public via squash-merge) and explicitly deferred
the **down**-propagation axis (hub → derived) as a "known limitation deferred to Phase 2+." The
`/distribute` command opened that axis, and review `REV-20260523-065900` (item **B5**) required an
ADR to record the protocol — the consent model and classification taxonomy lived only in Layer-1
discussions. This ADR discharges B5 and records the decisions made while closing the **B1** finding
(`SPEC-20260523-100224`).

Key forces:

1. **The Prime Objective forbids extraction.** Down-propagation must not accrue the hub's version at
   the expense of a derivative's authored work without that derivative's per-instance, human-authored
   consent (tests (b)/(c), ADR-0015).
2. **There is no reliable common ancestor in v1.** Drift is computed against the *target's own
   mutable baseline DB*, not a hub–target common ancestor. A target that re-baselined after a local
   edit (or narrowed `tracked_paths`) cannot be proven to descend untouched from the hub. This is the
   root of B1.
3. **The evaluator must not share the generator's blind spot (Principle #4).** An LLM interpreting
   only the hub-new and target-current files has the *same* missing-ancestor deficit; it cannot tell
   "deliberate customization" from "never received the update." So agent judgment cannot be the
   consent guarantee.
4. **The gatekeeper is the merge authority and may be non-expert.** The mechanism must surface risk
   in a way a human can act on, and must "show its work" (developer-stated need), without pretending
   to certify safety.

## Decision

### 1. Push the proposal, pull the apply
`/distribute` stages an **unmerged, unpushed** branch + an **advisory, target-overridable** assessment
doc in each target. Nothing reaches a target's `main` without the human's explicit merge act. The
hub verdict has no authority over the target.

### 2. Classification taxonomy (the mechanical safety floor)
Each offered file is classified against one target:

- `value-unverified` — the hub's version differs and the target shows **no provable divergence**
  (drift `current` or untracked). The hub **cannot prove this overwrite safe** against an ancestor.
  **Stageable but always surfaced** with per-file detail in the assessment doc — *never* a silent
  safe update. **This is the floor: it fires by construction, not by judgment.**
- `value` — RESERVED for v1.1: an overwrite *proven* safe against a hub-side ancestor (silent). **Not
  produced in v1.**
- `inert` — pure addition (target lacks the file); no overwrite, safe to stage.
- `collision-pinned` — matches a target `pinned_trait`; **dropped**, never staged (absolute).
- `collision-diverged` — provable deliberate divergence (modified/added/deleted) + hub also changed
  it → **assess**, never auto-staged.
- `current` / `denied` / `not-accepted` / `unavailable` — no-op / excluded / defensive.

### 3. Interpretation explains; it never gates the flag
On top of the floor, an `independent-perspective` room answers four questions per `value-unverified`
file (meaningful? backflow? blast radius? confidence) and ranks attention. The interpretation is
*educational refinement*; the floor — not the interpretation — is the consent guarantee. The
assessment doc is ordered by **consent stakes** (not agent confidence) and carries a **counted**
directing-attention disclaimer ("N files could not be proven safe — read these N").

### 4. Escalate-only reclassification (`reclassify_route`, a pure function)
An interpretation verdict may only **increase** scrutiny: a `value-unverified` file judged
*behavioral + blast radius* or *likely-deliberate*, or one where the agent verdict disagrees with the
deterministic `behavioral` triage hint, is promoted to `collision-diverged` (held from staging /
toward UNMEDIABLE). It may **never** demote a file to silent-safe. The override is recorded as a
`RouteDecision` alongside the immutable machine `classification` (Principle #1; no temporal coupling).

### 5. Backflow is surfaced here, resolved elsewhere
When the target's version may be the better one, `/distribute` flags a **backflow candidate** (labelled
honestly: "may be better OR may be stale — cannot tell without an ancestor") and points to the
existing `/analyze-project` + adoption-log organ. `/distribute` does **not** implement up-propagation
and **does not** write any hub-side adoption-log entry during the run (ADR-0015 test (c)).

### 6. Confidentiality at both sinks
Target diffs/interpretations live **only** in the target-local assessment doc. The ntfy/`ask_developer`
channel and the hub `write_event` capture both carry **counts / routes / verdict labels only** — never
per-file diff or interpretation prose. Diff lines written into the doc are scrubbed against the hub's
canonical secret patterns (the staging commit uses `--no-verify`).

## Alternatives Considered

### Alternative 1: Interpretation-only (the first spec draft)
Make the agent's per-file judgment decide what to flag, surfacing diffs for the rest.
- **Reason rejected:** the agent shares the missing-ancestor deficit (force #3), so this only makes B1
  *visible*, not *closed*; per-file confidence scores manufacture false confidence and lower the
  human's guard. The consent gap would be relocated onto the agent + the human's reading discipline,
  neither of which can bear it.

### Alternative 2: Raw diffs, no interpretation (REV B1's original v1 mitigation)
- **Reason rejected (as the sole mechanism):** a raw framework diff is low-yield for a non-expert
  gatekeeper. Retained in spirit — the scrubbed diff is *included* — but paired with the floor + an
  interpretation that directs attention.

### Alternative 3: Full hub-side ancestor tracking + 3-way merge now
The correct root-cause fix: record the hub hash at each target's last adoption serial; classify an
overwrite `value` iff `target_current == hub_ancestor`.
- **Reason deferred to v1.1:** a larger build (schema + re-baseline-on-merge). The mechanical floor
  closes the consent gap *mechanically and cheaply* in v1; v1.1 then lets proven-safe overwrites
  resolve back to silent `value`. Principle #8 (least-complex intervention that closes the gap).

## Consequences

### Positive
- The Prime Objective (b)/(c) gap is closed **mechanically** (Principle #2), not behaviorally — no
  silent overwrite of authored work is possible in v1.
- The interpretation does what it is good at (explaining, ranking, teaching) without a load it cannot
  carry; injection cannot lower scrutiny below the floor (escalate-only + hint co-gate).
- B5 discharged: the protocol now has an ADR; classification taxonomy and consent model are recorded.

### Negative
- **More files routed to review.** In v1 every differing overwrite is `value-unverified` (flagged), so
  the human sees more "read this" items than a silent-value design. Accepted by the developer
  (2026-05-23) as aligned with the "don't break downstream" priority; tiering keeps the *room* cost
  proportional (single referee unless a provable divergence convenes the full room).
- **Backflow detection inherits the ancestor deficit** — hence the honest "better OR stale" label.

### Neutral
- `value-unverified` is a v1 waypoint; v1.1's hub-side ancestor tracking will let proven-safe
  overwrites become silent `value` again, shrinking the flagged set to the genuinely uncertain.

## Linked Discussion

See: discussions/2026-05-23/DISC-20260523-170335-distribute-interpreted-assessment-spec-review/ and
the build discussion DISC-20260523-191833-build-distribute-b1-floor. Cross-refs: ADR-0003
(branching / deferred down-axis), ADR-0015 (Prime Objective), REV-20260523-065900 (B1, B5).
