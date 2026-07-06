---
adr_id: ADR-0027
title: "Suchness invariant — name the source-canonical / provenance-tether property in PHILOSOPHY.md"
status: accepted
date: 2026-06-27
decision_makers: [orchestrator, steward]
discussion_id: DISC-20260627-200311-suchness-invariant-backflow
spec_id: SPEC-20260610-205507
supersedes:
scope: framework
risk_level: medium
confidence: 0.86
tags: [backflow, philosophy, suchness, provenance, dan-research-wiki]
---

## Context

The framework already enforces source-grounding for one artifact class — `scripts/quality_gate.py::check_adrs`
lists `discussion_id` in its `required_fields`, so an ADR that cannot point at the reasoning that
produced it fails the gate today — but it has never *named* that property, given it a home, or
stated why it matters. PHILOSOPHY.md's "What the framework refuses" section already enumerates
**silent forgetting** and **revisable history** as two of the eight extraction modes the framework
refuses (and ADR-0015 records why that section exists and where it lives), yet the *positive* form
of those two refusals — the commitment that a derived artifact must stay tethered to its source —
was left implicit. The Steward gate (confidence 0.86) diagnosed this as a **naming gap, not a
capability gap**: the framework half-does suchness and never says so.

**Origin (back-flow, SPEC-20260610-205507 decision D2, pattern 5 of 5).** This invariant is harvested
from **dan_research_karpathy_wiki** (a derived satellite, the "central brain" hub), which built it
first and pins it as a trait *broader in claim than the donor's "preserve reasoning"* (the wiki's also
asserts correctness-precedence; this port deliberately narrows to provenance — see Adaptations). The wiki's principles
state: *"Sources are canonical. Files in any `raw/` directory are the source of truth. Everything in
`wiki/` is a vehicle for engaging with them, never a replacement. If raw and wiki conflict, raw
wins."* and *"Suchness preservation. Every wiki page links back to the raw passages that grounded it.
A claim without a source pointer either gets one or gets removed."* The wiki enforces this
mechanically: in its atom-layer quality gate, **every atom's blockquote must be a verbatim substring
of its cited raw source.** Attribution per the Prime Objective test (a): the wiki is credited as
origin; the `back_flow` ledger line in its `framework-lineage.yaml` flips `owed → delivered` with
this ADR. This delivers **pattern 5 of 5**; with patterns 1 (ADR-0023 one-shot stop hook) and 2 (ADR-0024
calibration loop) already delivered, **3 of 5 are now done — patterns 3 (extraction-miss-log) and 4
(sha256-freshness manifest) remain owed.** (ADR-0022 knowledge-loop revival shipped in the same D2 batch
but is not itself one of the 5 backflow patterns.) The `back_flow` ledger lives in the **wiki's** manifest, not
this fork's `framework-lineage.yaml` (which carries only `pinned_traits` + `custodian`); this ADR is the
donor-side delivery that *authorizes* the flip, which must still be applied in the wiki repo to actually
record pattern 5's delivery (tracked as an open thread — so the cross-repo pointer is not severed, the very property this ADR names).

## Decision

Name the property in PHILOSOPHY.md and nowhere else. Add a single subsection,
**"Sources are canonical (the suchness invariant),"** as the **closing subsection of the existing
"What the framework refuses" section** — the positive, named form of the silent-forgetting and
revisable-history refusals that section already lists. The text:

1. States the one-way **provenance tether**: Layer 1 discussions are the canonical record of *why*;
   L2 metrics, L3 memory, ADRs, reviews, and promoted patterns are *vehicles*, never replacements.
2. Distinguishes **supersede from sever**: a derived artifact may supersede an earlier decision (that
   is what ADRs do — Principle #5) but may not sever its own provenance.
3. Claims **mechanical enforcement only where it exists** (ADR `discussion_id`), and explicitly types
   the rest of the L3 promotion path as a *standing obligation and a candidate for future
   enforcement* — not a guarantee.
4. Anchors the invariant as the structural form of **Principle #1** ("reasoning is the primary
   artifact") applied to the framework's own memory over time.

No new Non-Negotiable Principle and no new Always-On Invariant are added. The change is doc-only and
behavior-neutral.

### Adaptations (deliberate deviations from the wiki version)

- **Provenance tether, not "raw wins."** The wiki's *"if raw and wiki conflict, raw wins"* holds
  because `raw/` is an **immutable external source** — genuine ground truth. The template's L1
  discussions are **internally produced**; a discussion can itself contain a reasoning error that a
  later ADR correctly overrides. So the port preserves *"you may not sever the link"* (provenance is
  canonical and immutable) without importing *"the earlier artifact is always more correct"*
  (supersession via Principle #5 — superseded never deleted — stays intact). Load-bearing: without this distinction a
  specialist could cite the invariant to block a legitimate corrective ADR.
- **Claim only what the gate delivers.** The wiki earned its "stronger" claim with a verbatim-substring
  atom gate. The template enforces source-grounding mechanically only for ADRs; the L3 path's read
  side was disconnected as recently as ADR-0022 (0 of 19 promotion candidates consumed). Writing
  "checkable property" for unchecked surfaces would manufacture the **hollow-rhetoric** failure
  ADR-0015 explicitly warned against, so the text types the L3 leg as an obligation, not a guarantee.
- **Anchored to an existing passage, not a new doctrine.** Placed inside "What the framework refuses"
  as the positive form of two already-listed refusals — per ADR-0015's deliberate split (positive
  moral frame in PHILOSOPHY.md, operational/negative form in CLAUDE.md). It is not promoted to a peer
  Principle (ADR-0015 Path-1 rejection: a peer addition would be category-confused) nor to an
  Always-On Invariant (those are mechanically-checked per-action obligations; no per-action L3 check
  exists).
- **Scope: this fork only; public-upstream promotion is a separate, pending decision.** PHILOSOPHY.md
  is a **pinned trait** in `framework-lineage.yaml` ("private fork mission statement — not applicable
  to public template"). This ADR changes the fork's copy; it does **not** automatically reach the
  public canonical template (Diviner-Dojo), whose PHILOSOPHY.md is divergent by design. Promoting the
  invariant upstream would require re-phrasing to canonical (non-fork) voice, custodian approval, and
  the normal promote-to-public standard — tracked as an open thread, not executed here. The ledger
  flip records `delivered (fork); public-upstream promotion deferred-with-trigger` — revisit at the next
  custodian-approved upstream promotion batch, or when an L3 source-pointer gate lands (whichever first) — so the obligation cannot quietly
  evaporate (the Steward's primary residual risk).

## Consequences

- The framework names an anti-extraction property it already half-enforces, making it legible and
  defensible to the next maintainer (Principle #1; ADR-0015 frame extended honestly).
- Behavior-neutral: no gate, script, or command changes; nothing in `src/` or `tests/` moves. The
  only enforced leg (ADR `discussion_id`) was already enforced before this ADR.
- The text is deliberately calibrated to current enforcement: when an actual L3 source-pointer check
  is added to `quality_gate.py`, the philosophy text can be strengthened to match — until then it
  must not claim "checkable" for the L3 path.
- This invariant governs **provenance, not correctness adjudication**: superseding an earlier decision
  is *preserving* suchness, not violating it.
- The public-upstream PHILOSOPHY.md does **not** yet carry this invariant; that promotion is a
  separate gated decision, deferred with an explicit trigger (next custodian-approved upstream batch, or
  an L3 source-pointer gate — whichever first).

## Alternatives Considered

- **A new top-level PHILOSOPHY.md section ("Sources are canonical"):** rejected — it would duplicate
  or compete with the already-present "silent forgetting"/"revisable history" refusals rather than
  naming their positive form; ADR-0015's placement architecture says to extend, not sit beside.
- **A new Non-Negotiable Principle or Always-On Invariant:** rejected — it is the positive face of
  Principles #1 and #5, not a peer; and phrasing it as a mechanically-checked invariant would assert
  enforcement (per-action L3 source-grounding) that does not exist.
- **The punchier original draft ("a load-bearing, *checkable* property" everywhere):** deferred —
  accurate only once an L3 source-pointer gate exists. Strengthen the text then; do not let it run
  ahead of the gate.
- **Backflow straight into the public upstream template:** deferred — PHILOSOPHY.md is a pinned,
  divergent fork trait; upstream promotion needs canonical-voice rephrasing + custodian approval and
  is its own decision.
- **Doing nothing (leave suchness unnamed):** rejected — that leaves an enforced anti-extraction
  property invisible to the next maintainer and the 5/5 backflow set unclosed.
