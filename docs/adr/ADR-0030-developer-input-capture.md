---
adr_id: ADR-0030
title: "Developer Input Capture via agent=\"developer\" Turn Schema"
status: proposed
date: 2026-03-03
discussion_id: DISC-20260302-192548-developer-input-capture-design
supersedes: null
superseded_by: null
decision_makers: [Developer]
---

## Context

The four-layer capture stack (Layer 1 — discussions/) records facilitator synthesis events
and specialist critique events, but does not capture the developer's own voice: verbatim
requests, approval caveats, override rationale, domain context corrections, and framing
that shapes the entire discussion. Without this, specialist prompts rely on the
facilitator's paraphrase, which can introduce framing drift (specialists echo the
facilitator's framing rather than the developer's actual constraint).

SPEC-20260302-192548 defines a three-step roadmap for developer input capture:
- **Step 1** (complete): Add `## Request Context` section to facilitator synthesis events.
- **Step 2** (complete, PR #58): Capture a `context-brief` event (`turn_id=1`,
  `agent="facilitator"`) at the start of each workflow before specialist dispatch.
- **Step 3** (this ADR): Define `agent="developer"` as a reserved turn author and extend
  the schema to allow direct developer turn capture — verbatim developer messages
  inserted as turn events in discussions, without requiring facilitator mediation.

This ADR is the placeholder for Step 3. It is formally proposed but not yet implemented.
It will be evaluated for initiation after two sprints of Step 2 data, per the evaluation
gate defined in SPEC-20260302-192548.

## Decision

**Pending — requires two-sprint Step 2 evaluation gate.**

Step 3 will be initiated if either of the following signals fires in the retro evaluation:
- **Signal A (Specialist echo)**: Specialists are repeating findings already stated as
  explicit developer constraints in context-brief events.
- **Signal B (Framing drift)**: Facilitator synthesis diverges from what the developer
  actually requested (observed in retro or review feedback).

If both Signal A and Signal B are absent after two sprints, Step 3 will be formally
deferred with documented rationale.

Once initiated, the implementation will cover:
1. Schema extension: `agent` column in `turns` table accepts the reserved value
   `"developer"` in addition to current agent names.
2. `write_event.py` support for `agent="developer"` with validation.
3. Command workflow integration: facilitator captures developer messages at turn creation
   time using `write_event.py ... developer evidence "<verbatim text>"`.
4. Extraction pipeline update: `extract_findings.py` and `ingest_events.py` must handle
   `agent="developer"` events as context rather than findings.

## Alternatives Considered

**A. No additional capture (status quo after Step 2)**
The `context-brief` event (Step 2, PR #58) captures facilitator paraphrase of the
developer's request. If specialist echo and framing drift are absent after two sprints,
this may be sufficient. The evaluation gate determines whether Step 3 is needed.

**B. Out-of-band capture file**
Record developer input in a separate markdown file (e.g., `docs/sprints/developer-input-YYYYMMDD.md`)
rather than as turn events in the discussion. Rejected: this breaks the unified query
model — findings extraction and agent effectiveness scripts operate on `turns`, not
supplementary files. Separate files would be invisible to the pipeline.

**C. Prompt injection via system message**
Inject developer input into specialist prompts via the system message rather than
recording it as a turn. Rejected: this does not persist to Layer 1 (discussions/) and
cannot be queried retrospectively or included in trend analysis.

**D. Facilitator-mediated capture (selected approach IF Step 3 initiates)**
Facilitator captures developer messages as turn events with `agent="developer"`. This is
the minimal schema extension — it adds one reserved agent name, requires no new tables,
and keeps developer input in the same queryable structure as specialist turns.
Initiation is conditional on the two-sprint evaluation gate (Signal A or Signal B firing).

## Consequences

**If implemented:**
- Developer framing is captured verbatim, eliminating facilitator paraphrase as a source
  of framing drift.
- Specialist prompts can include direct developer quotes alongside the facilitator
  context-brief.
- Layer 2 (SQLite) `turns` table gains a new reserved `agent` value — backwards-compatible
  as a new enum value.
- The `extract_findings.py` pipeline must be updated to skip `agent="developer"` events
  for finding extraction (they are context, not findings).

**If not implemented (deferred after evaluation gate):**
- The `context-brief` Step 2 events (SPEC-20260302-192548 Step 2) remain the primary
  mitigation for framing drift.
- This ADR remains in `proposed` status as an explicit placeholder, preventing the
  "ADR-0030 deferred" reference in CLAUDE.md from being unresolvable.

## References

- SPEC-20260302-192548-developer-input-capture.md
- DISC-20260302-192548-developer-input-capture-design
- REV-20260302-232244 — Advisory A5: ADR-0030 stub creation
- CLAUDE.md — Capture Pipeline section, context-brief command list
