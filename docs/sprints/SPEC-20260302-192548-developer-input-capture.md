---
spec_id: SPEC-20260302-192548
title: "Developer Input Capture — Graduated Implementation"
status: reviewed
risk_level: medium
source_discussion: DISC-20260302-192548-developer-input-capture-design
spec_review_discussion: DISC-20260302-201821-developer-input-capture-spec-review
reviewed_by: [architecture-consultant, qa-specialist, docs-knowledge]
---

## Goal

Close the gap where the four-layer capture stack records only agent reasoning, leaving the
developer's initial requests, explicit decisions, domain context corrections, and approval
caveats entirely invisible. Implement in three graduated steps per the dialectic resolution
from `DISC-20260302-192548-developer-input-capture-design`.

## Context

**The gap**: Discussion transcripts currently contain only agent turns. Reading any closed
transcript, you can reconstruct what agents said but not what the developer originally wanted
or decided. This violates Principle #1 ("reasoning is the primary artifact — deliberation,
trade-offs, and decision lineage are the durable assets") because the developer's reasoning
is the causal root of every discussion.

**Dialectic outcome**: Three specialists deliberated in two rounds and converged on a
graduated approach. The key constraints that shaped the recommendation:
- Principle #8 (least-complex intervention first) demands the synthesis template fix ships
  before any infrastructure is built.
- Privacy exposure from raw developer utterances in immutable Layer 1 is a real compliance
  risk for enterprise deployment (Wells Fargo context). All capture must be
  facilitator-mediated, not verbatim.
- `findings.disposition` is operationally inert today (all 48 findings are `open`). Developer
  input enabling disposition updates is the most valuable pipeline improvement.
- The extraction pipeline must be reformed in parallel — new capture categories only add
  value if the pipeline can process them.

**What is not in scope**: Raw developer utterance capture in Layer 1. The independent-
perspective's pre-mortem identified this as a high-probability compliance incident for an
enterprise deployment. All developer context flows through a facilitator-mediated
summarisation layer.

## Requirements

### Step 1 — Synthesis Template (Immediate, prompt-only)

**Scope rationale**: Step 1 targets `/review` and `/deliberate` only. `/build_module`
synthesis captures checkpoint outcomes, not developer framing. `/retro` synthesis captures
pattern analysis across historical discussions, not per-request context. These two are
excluded from Step 1 because the developer-context problem is concentrated in the two
request-driven workflows. Step 2 extends to all four.

- R1.1: The `/review` command synthesis step includes a `## Request Context` section.
  The facilitator populates all four fields before findings.
- R1.2: The `/deliberate` command synthesis step includes the same `## Request Context`
  section.
- R1.3: `CLAUDE.md` Capture Pipeline "Known limitation" block gains the following entry
  (exact text, inserted after the existing known-limitation bullets):

  > **Known limitation**: Developer input (verbatim requests, overrides, domain context
  > corrections, approval caveats) is not captured in Layer 1. Facilitator synthesis
  > templates include a `## Request Context` section as a partial mitigation. ADR-0030
  > (deferred, conditional on Step 3 trigger) will define `agent="developer"` as a reserved
  > turn author if facilitator-mediated capture proves insufficient. See
  > `DISC-20260302-192548-developer-input-capture-design` and
  > `SPEC-20260302-192548-developer-input-capture.md`.

- R1.4: `.claude/rules/documentation_policy.md` "What Must Be Documented" list gains:
  `All facilitator synthesis events must include a ## Request Context section documenting
  developer framing.`
- R1.5: `docs/templates/review-report-template.md` gains a `## Request Context` section
  in the summary block (between `## Summary` and `## Findings by Specialist`) matching
  the four-field template below.
- R1.6: The `/retro` command template gains a Step 3 evaluation checklist item:
  "Evaluate developer-input capture (SPEC-20260302-192548): Are specialists repeating
  findings stated as developer constraints? Is `findings.disposition` remaining 100% open?
  Is framing drift observed? If yes to any: initiate Step 3."

**Synthesis template addition** (insert at top of synthesis event body, before findings):

```markdown
## Request Context
- **What was requested**: [verbatim or close paraphrase of developer's instruction]
- **Files/scope**: [what was handed to the review or deliberation]
- **Developer-stated motivation**: [why this change is being made, if stated]
- **Explicit constraints**: [any developer-stated constraints agents should respect;
  write "none stated" if none]
```

All four fields must be populated. Writing "(none provided)" or leaving a field as a
template placeholder fails the acceptance criterion.

### Step 2 — Context-Brief Event (Next sprint, command workflow change)

**Target commands**: `/review`, `/deliberate`, `/plan`, `/build_module`. Step 2 extends
to `build_module` and `plan` (excluded from Step 1) because the context-brief fires before
specialist dispatch and is useful in all request-driven workflows. `/retro` and
`/meta-review` are excluded — they do not have a developer-directed scope that needs
surfacing to specialists; they analyse existing captured data autonomously.

- R2.1: `/review`, `/deliberate`, `/plan`, and `/build_module` command definitions each
  add a context-brief capture step immediately after `create_discussion.py` succeeds and
  before any specialist is dispatched. The step calls `write_event.py` with
  `agent="facilitator"`, `intent="evidence"`, `tags="context-brief"`. Content uses the
  same four-field template as the Step 1 synthesis section. This produces `turn_id=1`
  for the context-brief in every new discussion created by these commands.
- R2.2: Specialist dispatch prompt templates in those four commands include a
  `## Developer Context` section populated from the context-brief content, so agents see
  developer intent during analysis rather than only learning it from the post-synthesis.
- R2.3: The context-brief event uses only existing schema (`agent="facilitator"`,
  `intent="evidence"`) — no schema migration required for this step.

### Step 3 — Agent-as-Developer (Conditional, requires ADR)

> **Gate**: Step 3 is initiated only if Step 2 proves insufficient after two sprints of
> use. Trigger condition: developer intent is demonstrably lost or distorted in
> facilitator-mediated summaries, evidenced by retro notes.

- R3.1: ADR-0030 created, reviewed via `/review`, and approved before any code changes.
  ADR must specify: reserved agent name (`"developer"`), new intent types (`"directive"`,
  `"context"`), privacy-filter protocol (structural intent only, no business context),
  three structured capture moments (initial directive, course correction, disposition), and
  all affected scripts.
- R3.2: `scripts/write_event.py` updated: (a) `valid_intents` set (line 66–74) extended to
  include `"directive"` and `"context"`; (b) accepts `agent="developer"` without error and
  writes a valid event readable from `events.jsonl` with `agent` field preserved; (c)
  end-to-end test: `write_event.py` with `agent="developer"` → `ingest_events.py` ingests
  without constraint violation.
- R3.3: `metrics/evaluation.db` schema migrated to add `"directive"` and `"context"` to
  the `turns.intent` CHECK constraint. Migration run against a backup first.
- R3.4: `scripts/extract_findings.py` updated: the existing `if agent == "facilitator"`
  guard (line 212–213) is refactored to use `NON_SPECIALIST_AGENTS`. An explicit exclusion
  for `"developer"` is code-verifiable (not reliant on absence of developer findings).
  Verification test: a discussion with a developer turn containing a severity-tagged line
  (e.g., `- (High) something`) must produce zero findings for that turn.
- R3.5: `scripts/compute_agent_effectiveness.py` updated with an explicit
  `NON_SPECIALIST_AGENTS` skip guard — code-verifiable, not reliant on the absence of
  developer rows in `agent_effectiveness`.
- R3.6: `scripts/ingest_events.py` excludes `"developer"` from `agent_count` aggregation.
- R3.7: `NON_SPECIALIST_AGENTS = {"facilitator", "developer"}` defined in a shared
  constants module. All pipeline scripts import from it. The existing hardcoded
  `"facilitator"` strings in `extract_findings.py` and `compute_agent_effectiveness.py`
  are replaced with the constant (not left as parallel mechanisms).

### Parallel Actions (not blocked on step ordering)

- P1: Run `scripts/backfill_findings.py` against all 82 historical discussions to
  establish an honest extraction pipeline performance baseline.
- P2: Review `scripts/extract_findings.py` `FINDING_PATTERN` regex — document extraction
  coverage and identify gaps as a prerequisite to any future Step 3 work.

## Constraints

- **No raw utterance capture in Layer 1**: All developer content must be
  facilitator-summarised. Verbatim business context (deadlines, regulatory pressures,
  client names) must never enter `events.jsonl`.
- **No schema migration before Step 3 gate**: Steps 1 and 2 must use only existing
  `agent/intent` schema. The migration cost is justified only if the facilitator-mediated
  approach proves insufficient.
- **Framework-only changes**: No Flutter/Dart application code is affected. All changes
  are in `.claude/commands/`, `scripts/`, and `CLAUDE.md`.
- **Step 3 requires independent review**: ADR-0030 and the schema migration must go
  through `/review` before implementation — Principle #4 (independence) applies.
- **Principle #8 sequencing**: Steps must be implemented in order. Step 2 cannot begin
  before Step 1 ships and is observed for at least one sprint. Step 3 cannot begin before
  the two-sprint Step 2 evaluation period.

## Acceptance Criteria

### Step 1
- [ ] `.claude/commands/review.md` synthesis step contains a `## Request Context` section
      with all four fields (what, scope, motivation, constraints).
- [ ] `.claude/commands/deliberate.md` synthesis step contains the same four-field section.
- [ ] `CLAUDE.md` Capture Pipeline "Known limitation" block contains the verbatim entry
      specified in R1.3.
- [ ] `.claude/rules/documentation_policy.md` "What Must Be Documented" includes the
      synthesis event requirement from R1.4.
- [ ] `docs/templates/review-report-template.md` contains a `## Request Context` section
      in the summary block (between `## Summary` and `## Findings by Specialist`).
- [ ] `/retro` command template contains the Step 3 evaluation checklist item from R1.6.
- [ ] The next `/review` run produces a synthesis event with all four `## Request Context`
      fields non-empty (not placeholders, not "(none provided)").

### Step 2
- [ ] `/review`, `/deliberate`, `/plan`, `/build_module` command definitions each contain
      a context-brief capture step between `create_discussion.py` and first specialist
      dispatch.
- [ ] At least one newly-created discussion has `turn_id=1` with `agent="facilitator"` and
      `tags` containing `"context-brief"` in `events.jsonl`. Verifiable:
      `SELECT turn_id, agent, tags FROM turns WHERE discussion_id='<id>' AND turn_id=1`.
- [ ] Specialist dispatch prompts in those four commands include a `## Developer Context`
      section.
- [ ] `SELECT COUNT(*) FROM turns WHERE agent='facilitator' AND tags LIKE '%context-brief%'`
      returns ≥ 1 from a discussion created after Step 2 ships.

### Step 3 (conditional)
- [ ] ADR-0030 exists at `docs/adr/ADR-0030-developer-input-capture.md` with status
      `accepted`.
- [ ] `write_event.py` called with `agent="developer"`, `intent="directive"` writes a
      valid event; `ingest_events.py` ingests it without a CHECK constraint violation.
      (Full write-read path, not just "no error on write.")
- [ ] `flutter test` (full suite) unaffected — no application test regressions.
- [ ] `python scripts/quality_gate.py` passes after schema migration.
- [ ] `extract_findings.py` contains an explicit `NON_SPECIALIST_AGENTS` guard
      (code-verifiable); a test discussion with a developer turn containing
      `- (High) some finding` produces zero findings extracted for that turn.
- [ ] `compute_agent_effectiveness.py` contains an explicit `NON_SPECIALIST_AGENTS` skip
      guard (code-verifiable, not reliant on developer rows being absent from data).
- [ ] `v_agent_dashboard` definition contains an explicit `agent != 'developer'` filter
      OR `compute_agent_effectiveness.py` has a developer skip guard — verified in source,
      not inferred from query results.

### Parallel
- [ ] `SELECT COUNT(*) FROM findings` recorded before and after `backfill_findings.py`;
      post-run count is higher, or a comment documents all historical discussions were
      already processed in a prior run.
- [ ] `extract_findings.py` pattern match rate documented in a retro note or CLAUDE.md,
      with the current baseline rate recorded.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Privacy leak via facilitator summary | Low | High | Explicit filter instruction in command template: structural intent only, no business context |
| Synthesis template ignored in practice | Medium | Medium | Quality gate check or retro review of synthesis events for `## Request Context` presence |
| Step 2 context-brief not used consistently | Medium | Medium | Facilitator has explicit capture step; not developer-dependent |
| Schema migration corrupts evaluation.db | Low | High | Gate on ADR-0030 approval; run migration on a backup first |
| Step 3 never triggered (two-sprint gate never revisited) | Medium | Low | Add Step 3 gate check to retro agenda explicitly |
| extract_findings.py FINDING_PATTERN misses developer override intent | Medium | Medium | Parallel P2 action (extraction coverage review) before Step 3 |

## Affected Components

### Step 1
- `.claude/commands/review.md` — synthesis step template
- `.claude/commands/deliberate.md` — synthesis step template
- `.claude/commands/retro.md` — add Step 3 evaluation checklist item (R1.6)
- `CLAUDE.md` — Capture Pipeline known-limitation block (verbatim text in R1.3)
- `.claude/rules/documentation_policy.md` — "What Must Be Documented" addition (R1.4)
- `docs/templates/review-report-template.md` — `## Request Context` section (R1.5)

### Step 2
- `.claude/commands/review.md` — add context-brief event step before specialist dispatch
- `.claude/commands/deliberate.md` — same
- `.claude/commands/plan.md` — same
- `.claude/commands/build_module.md` — same
- Specialist dispatch prompt templates within those four commands (`## Developer Context`
  section)

### Step 3 (conditional)
- `docs/adr/ADR-0030-developer-input-capture.md` (new)
- `scripts/write_event.py` — accept `agent="developer"`, new intent types
- `metrics/evaluation.db` — schema migration (turns.intent CHECK constraint)
- `scripts/ingest_events.py` — agent_count exclusion
- `scripts/extract_findings.py` — developer-turn exclusion + disposition update path
- `scripts/compute_agent_effectiveness.py` — developer exclusion filter
- A new shared constants module or updated imports across pipeline scripts

### Parallel
- `scripts/backfill_findings.py` (run, not modified)

## Dependencies

- **Depends on**: `DISC-20260302-192548-developer-input-capture-design` (closed — design
  rationale is the source of record)
- **Step 3 depends on**: Two-sprint Step 2 evaluation period; ADR-0030 review and approval
- **Nothing depends on this spec yet** — it is a framework-internal improvement
- **Backfill (P1) depends on**: Nothing; can run immediately

## Implementation Order

```
Sprint N (now):
  ├── Step 1: review.md + deliberate.md synthesis template  [1–2 hours]
  ├── Step 1: CLAUDE.md known-limitation entry (verbatim)  [15 min]
  ├── Step 1: documentation_policy.md + review-report      [30 min]
  │           template + retro.md gate item
  └── Parallel P1: Run backfill_findings.py, record        [15 min]
                   before/after findings count

Sprint N+1:
  ├── Step 2: context-brief event in review, deliberate,
  │           plan, build_module commands                   [2–3 hours]
  ├── Step 2: Specialist prompt template updates            [1 hour]
  └── Parallel P2: Document extraction coverage            [1 hour]
                   (record baseline rate in CLAUDE.md)

Sprint N+2 (evaluation — retro gate):
  Evaluate: (a) Are specialists repeating findings already
  stated as developer constraints? (b) Is findings.disposition
  still 100% open? (c) Is framing drift documented in retro?
  → Any 'yes': initiate Step 3.
  → All 'no': defer Step 3 with documented rationale.

Sprint N+3 (conditional):
  ├── ADR-0030 (write + /review)                           [3–4 hours]
  ├── Shared constants module                              [30 min]
  ├── Script changes (write_event, extract_findings,       [4–6 hours]
  │   compute_agent_effectiveness, ingest_events)
  └── Schema migration + write-read path tests             [2–3 hours]
```
