---
adr_id: ADR-0021
title: "Framework apply-or-update unification — presence routing, the two-baseline floor, and the APPLY consent inversion"
status: accepted
date: 2026-05-24
decision_makers: [facilitator, steward, architecture-consultant, security-specialist, qa-specialist, independent-perspective]
discussion_id: DISC-20260524-205732-framework-apply-unification-steward-gate
supersedes: ADR-0017
scope: framework
risk_level: high
confidence: 0.86
tags: [apply-framework, distribute, onboard, down-propagation, greenfield, prime-objective, consent, baseline, b1]
---

## Context

> **Renumbering note (2026-06-11).** This ADR was drafted as ADR-0019 on `feat/distribute-b1-floor`
> (2026-05-24). While the branch awaited merge, `main` assigned ADR-0019 (async collaboration loop)
> and ADR-0020 (telemetry oversight), so it was renumbered to **ADR-0021** before merge. Sealed
> Layer 1 discussions from the 2026-05-24 build refer to it by its draft number, ADR-0019.

ADR-0017 recorded the **down-propagation** protocol for `/distribute`: classify each offered file
against a framework-carrying target, enforce the **B1 mechanical safety floor** (never silently
overwrite authored work — an overwrite the hub cannot prove safe is `value-unverified`, staged but
always surfaced), and stage safe files onto a dedicated branch with an advisory assessment doc.
`/onboard` was a *separate* command — the deeper "takeover" protocol — for projects that never had
the framework.

The developer wanted **one** mental model: "apply or update the framework on this project, show me
the value and risk first, then let me deploy safely." Today that was two commands with a hard split
at "does it have lineage," and `/distribute`'s dry-run emitted only counts, not a value/risk
narrative. `SPEC-20260524-203931` unified them; this ADR records the decisions that survived the
design review (`DISC-20260524-204142`, REVISE) and the Steward gate (`DISC-20260524-205732`, APPROVE
0.86, four conditions folded), and **supersedes ADR-0017** (whose protocol it preserves and extends).

Key forces (in addition to those in ADR-0017, which still hold):

1. **The APPLY route has the weakest consent and the widest blast radius.** Applying the framework
   to a project that never had it is the easiest operation to aim at a repo the operator does *not*
   own — a fork, a client's checkout, a colleague's repo — the exact extraction ADR-0015 forbids.
2. **The B1 floor must not weaken on the new route.** Greenfield has no lineage DB and no manifest,
   so the drift-based UPDATE machinery (`drift_scan` + `repo_safety_check`'s fused verdict) is
   mechanically absent — yet an existing target file at a framework path is still authored work that
   must never be silently overwritten.

## Decision

### 1. One command, route reported as a spectrum (R1)
`/apply-framework <target>` detects framework presence by `framework-lineage.yaml` and reports the
route as a **spectrum**: "framework present (UPDATE)" / "no lineage, N pre-existing framework-path
files (partial — treat with care)" / "no framework (greenfield APPLY)". It **fails closed**: a
malformed/empty manifest *errors* (never silently falls to APPLY); a missing path *errors*.

### 2. Two phases — ASSESS (read-only by construction) then DEPLOY (clean-tree gated)
ASSESS has **no filesystem-write code path** — it runs safely against a dirty/active repo and
produces the value/risk report. DEPLOY is explicit, gates on a **clean target tree** via a
*separable* clean-tree check (not the fused `can_proceed`), lands on a dedicated back-out branch,
**never pushes, never auto-merges**, one target at a time.

### 3. One floor, two baselines (R4 / architecture (b))
The B1 floor decision is a **single shared primitive** consulting an injected `Baseline`:
`LineageBaseline` (drift + manifest — the UPDATE route, unchanged) and `OnDiskBaseline` (the target's
files on disk — greenfield). `OnDiskBaseline` has no ancestor and no policy, so **every existing
target file at a framework path classifies as `value-unverified`** (flagged, never silent) and every
path the target lacks as `inert`. The floor lives in one auditable place, tested against **both**
baselines — route divergence is structurally impossible. `value` (silent safe update) remains
**reserved for v1.1** (ancestor-proven) and is produced on neither route. Architecture: **two route
engines + a shared front-end/floor** (option (b)) — the single-command UX is honored at the
command/UX layer; the genuinely-different baseline acquisition stays separate.

### 4. The APPLY consent inversion — lineage-absence is NOT evidence of ownership (R8, Steward condition 1)
**First-class rationale, recorded so a future maintainer cannot drift back to "pointing = consent":**
*lineage-absence is **inversely** correlated with ownership.* The APPLY route — the weakest-consent,
easiest-to-misaim route — therefore requires the **STRONGEST explicit assent**, not the least. The
opt-in HARD GATE protects a derived project's autonomy on UPDATE (unchanged). On APPLY there is no
custodian to consult, so consent is **a human-authored assent record written INTO the target as
deploy step zero**: a minimal `framework-lineage.yaml` whose `custodian` block names a **non-null,
human-authored `primary_human`** AND `accepts_distribution: true`. This is **fail closed** (Steward
condition 2): `primary_human: null` — the `init_lineage` default — does **not** satisfy the gate.
APPLY and UPDATE thereby converge on one human-authored, per-instance assent record (ADR-0015 (a)/(b)/(c)).

### 5. The assent stub is written on the deploy branch (Steward condition 3)
The APPLY assent stub is written **inside the branched deploy** (under the clean-tree gate), as the
first write, via the staging layer — so deleting the back-out branch reverts it. A back-out leaves
**no orphaned consent record** on a repo that received nothing else.

### 6. Baseline gate defaults to skip on APPLY (Steward condition 4)
`baseline_gate_green` runs the *target's own* `quality_gate.py` — a code-execution surface. On the
UPDATE route (a target you own) it runs post-stage as the integrity check for the `--no-verify`
commit. On the APPLY route (an arbitrary target) it **defaults to skip** and runs only after a
**distinct, logged operator confirmation** ("I trust this project to run code locally"), separate
from the deploy confirmation. Never silently on an arbitrary repo.

### 7. Value/risk report; tiered, data-only interpretation (R3 / R6)
A new `build_assess_report` renders four sections — **Features added** (what each added capability
does) / **What changes** (scrubbed diff + interpretation) / **Conflicts & losses** (plain "deploy
this and you lose X") / **Value/risk extras** — composed from the **same** section-builders as the
staging doc, so `redact_secrets` and the directing-attention disclaimer are **single-sourced**.
`current` files never appear; the pre-deploy report is ephemeral (written only on DEPLOY). Every
file/diff read from the target and placed into an agent prompt is wrapped in the **R3a data-only
block** (both routes); interpretation is **tiered by category/directory** to bound cost and resist
banner-blindness on greenfield. Interpretation **explains**; it never decides what to flag (the
floor did).

### 8. Naming + `/onboard` disposition (R9)
The command is **`/apply-framework`**; `/distribute` became a misnomer (it now also *applies*) and is
retained as a deprecated alias. `/onboard` is **superseded but not deleted** (Principle #5): the
*light* apply lives in `/apply-framework`'s APPLY route, which **offers** `/onboard`'s **deeper
takeover** (codebase mapping, reverse-engineered ADRs, standards calibration, debt ledger) as an
explicit follow-on (R5). The heavy takeover is never inlined (Principle #8).

## Alternatives Considered

### Alternative A: a fully unified single code path (R10 option (a))
One code path branching internally on lineage-presence.
- **Reason rejected:** UPDATE and APPLY are genuinely different jobs (lineage history vs. reading a
  foreign codebase cold). A unified path entangles them and invites route divergence in the floor.
  Option (b) shares the front-end + the one floor primitive (behind `Baseline`) and keeps the
  baseline acquisition separate — Principle #8 applied where it matters.

### Alternative B: "pointing = consent" for APPLY (R8 option (i))
The operator's act of pointing + reviewing + branch-only deploy *is* the consent.
- **Reason rejected:** too weak — the easiest-to-misaim route would get the least protection, exactly
  inverting the risk. The consent inversion (Decision 4) is the whole point.

### Alternative C: keep `/onboard` and `/distribute` separate
- **Reason rejected:** two commands with a hard split at lineage-presence is the friction the spec
  removes; a partial/abandoned adoption fell into neither cleanly. The spectrum router subsumes both.

## Consequences

### Positive
- The Prime-Objective gap on the *new* route is closed **mechanically** (the floor) and the consent
  inversion is recorded as first-class rationale, so APPLY cannot silently overwrite authored work
  and cannot deploy without a named human's assent.
- One mental model + an up-front value/risk report; the human is still the merge authority.
- Route divergence is structurally prevented (one floor, tested against both baselines).

### Negative
- More files routed to review on greenfield (every existing framework-path file is flagged) — accepted
  (quality-first), bounded by the capped offer set + tiered interpretation.
- A second consent shape (assent stub) to maintain alongside the opt-in gate — justified by the
  ownership inversion; they converge on one human-authored record.
- `--assent-human` residual gap: the preflight gate validates the supplied name *syntactically*
  (non-empty, meaningful characters) — it cannot verify that a human was actually present for this
  instance. Per-instance assent therefore remains **human-mediated** (Prime Objective), enforced by
  process and review, not by the mechanical check.

### Neutral
- The `scripts/distribute/` package keeps its name; `value` remains a v1.1 waypoint (hub-side ancestor
  tracking will let proven-safe overwrites resolve back to silent `value` on both routes).

## Linked Discussion

Design review: discussions/2026-05-24/ DISC-20260524-204142-framework-apply-unification-spec-review.
Steward gate: discussions/2026-05-24/ DISC-20260524-205732-framework-apply-unification-steward-gate.
Build: DISC-20260524-212509-build-apply-framework. Spec: SPEC-20260524-203931. Supersedes ADR-0017
(B1 floor + classification taxonomy, preserved and extended). Cross-refs: ADR-0015 (Prime Objective),
ADR-0003 (branching / deferred down-axis).
