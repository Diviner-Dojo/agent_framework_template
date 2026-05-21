---
synthesis_id: SYNTHESIS-20260515-adoption-brief-v4
date_started: 2026-05-15
date_last_updated: 2026-05-16
status: LIVING DOCUMENT (working observations, non-binding)
supersedes: SYNTHESIS-20260515-adoption-brief-v3
sealed_discussion: DISC-20260516-050945-framework-adoption-sequence-two-project
sources:
  - SYNTHESIS-20260515-adoption-brief (v1, template-local only)
  - SYNTHESIS-20260515-adoption-brief-v2 (added Insight Journal telemetry)
  - SYNTHESIS-20260515-adoption-brief-v3 (added VerificationPortal telemetry)
  - DISC-20260516-050945 (12-agent dialectic deliberation, 18 turns)
purpose: Living document for accumulating framework adoption research before any binding action
---

# Adoption Synthesis v4 — Living Document

## Purpose & Posture

v4 is a **living document**, not an adoption plan. The developer is accumulating research before any framework changes are made. v3's adoption sequence has been re-cast as **working positions** that the next research wave can validate, refine, or invalidate.

**Nothing in this document is enacted.** No ADRs created. No `.claude/rules/`, `.claude/agents/`, `.claude/commands/`, `CLAUDE.md`, or `scripts/` edits. The 18-turn deliberation at `discussions/2026-05-16/DISC-20260516-050945-framework-adoption-sequence-two-project/transcript.md` is the captured reasoning; this document is the editable working surface.

## What Changed in v4

v3 was scoped as a deliberation brief — input to a `/deliberate` run. v4 absorbs the deliberation outputs (12-agent panel, 2 rounds, captured at DISC-20260516-050945) and reframes everything as **observations** plus **described-but-not-enacted future intent**, awaiting more research.

## Working Positions

### A. Three-Sprint Sequencing (observations, not commitments)

| Sprint | Item | Source turn | Confidence |
|---|---|---|---|
| 1 (parallel-with-Tier-0) | Panel-size domain-tiered dispatch using ux-evaluator's trigger conditions | ux-evaluator turn 9 | 0.82 |
| 1 | Pre-Report Gate sub-pattern from ECC FP Taxonomy (Pre-Report Gate only — not full taxonomy) | independent-perspective turn 4, turn 16 | 0.78 |
| 1 | REFERENCE.md split for facilitator + architecture-consultant + qa-specialist (hygiene value, NOT cost — savings ~\$0.04–\$0.08/90d but ~2.7M–5.4M tokens) | performance-analyst turn 7 | 0.58 |
| 1 | Karpathy Principles 1–3 as `.claude/rules/agent-behavior-defaults.md` | analysis-karpathy-skills | 0.85 |
| 1 | Karpathy Principle 4 (Goal-Driven Execution) merge into autonomous_workflow.md | project-analyst turn 10 (under-weighted) | 0.78 |
| 1 | Rationalization Tables in commit/autonomous/build-review rules | analysis-superpowers | 0.85 |
| 1 | Verification-Before-Completion as new rule | analysis-superpowers | 0.85 |
| 1 (Tier 0) | Trace one IJ finding end-to-end through disposition pipeline (6-step diagnostic) | architecture-consultant turn 3 | 0.78 |
| 1 (Tier 0) | Slug normalization fix in create_discussion.py + backfill for NULL command_type | architecture-consultant turn 3 | 0.78 |
| 1 (Tier 0) | Replace try/except: print-warning in close_discussion.py with structured CAPTURE_PIPELINE_ERROR events | architecture-consultant turn 3 | 0.78 |
| 1 (Tier 0) | Regression test `test_unresolved_checkpoint_flag_written_to_turns_table` | qa-specialist turn 6 | 0.72 |
| 1 (Tier 0) | Add DONE_WITH_CONCERNS as third disposition state in build_review_protocol.md (additive — uses existing risk_flags plumbing) | architecture-consultant turn 14 + project-analyst turn 10 | 0.74 |
| 1 (Tier 0) | 7th session-start dashboard point: pending Layer-3 promotion count | docs-knowledge turn 8 | 0.82 |
| 1 (Tier 0) | 14-day candidate-age + ownership sentence in `.claude/commands/promote.md` Step 1 | docs-knowledge turn 8 | 0.82 |
| 1 (Tier 0) | Run `/retro` on the template repo itself (first time in 68 days) | history-analyst turn 12 | 0.87 |
| 1 (Tier 0) | Resolve `memory/decisions/retro-action-registry.md` gap (file does not exist but retro.md references it) | history-analyst turn 12 | 0.87 |
| 2 (Tier-0-gated) | Agent Introspection Debugging skill from ECC | analysis-everything-claude-code | — |
| 2 | Santa Method context isolation for HIGH/CRITICAL only | analysis-everything-claude-code | — |
| 2 | Context Budget Audit one-time session | analysis-everything-claude-code | — |
| 2 | `/insights` adoption per project + ADR-0013 promotion to accepted with `ingest_token_usage.py` baseline run | performance-analyst turn 7 | 0.58 |
| 2 | Re-evaluate FP Taxonomy + Two-Stage Review now that survival rate is trustworthy | independent-perspective turn 16 | 0.78 |
| 2 | Decision: relax vs retain checkpoint protocol after DONE_WITH_CONCERNS has 30d of data | architecture-consultant turn 14 | 0.74 |
| 2 | `external_data_provenance` event field + facilitator dispatch template (transitive-taint mitigation) | architecture-consultant turn 14 | 0.74 |
| 3 (Tier 0 + Tier 1 in place) | Formalize cross-project pattern propagation (memory/patterns/ 2-of-2 sighting flow) | steward turn 2 | 0.78 |
| 3 | Lineage drift gates + `upstream_promotion_candidate` event class | steward turn 2 | 0.78 |
| 3 | Rule-of-Three-triggered automated promotion candidate surfacing | docs-knowledge turn 8 | — |

### B. Resolutions for 5 Open Conflicts (working positions)

1. **Sequential vs parallel review**: PARALLEL preserved; Two-Stage Review re-evaluation gated to Sprint 2 once survival rate is measurable.
2. **Skill description philosophy**: Adopt superpowers framing — descriptions name triggers, not workflows. obsidian-cli-skill + superpowers CSO converge (project-analyst turn 10 cross-source Rule-of-Three argument — two sources reached the same counter-intuitive finding via pressure testing).
3. **Automated promotion vs Principle #7**: Adopt instinct format (trigger / confidence / domain / evidence), reject automation. Use as richer queue for human gate review.
4. **Cost vs independence in reviews**: Santa Method context isolation for HIGH/CRITICAL only (steward + architecture-consultant agree).
5. **External-input command class** (`conversation` + `status`): NOT YET — track in `memory/patterns/` as observation only. Canonicalization waits for Howie OR 90 more days of two-project data. Lineage substrate needs `upstream_promotion_candidate` event class designed first (steward turn 2).

### C. Education-Gate Verdict (working position)

**Option C default with Option B carve-out.**

- **Default**: Decision Rationale Capture — two-paragraph plain-language summary (decision + alternatives declined; what would change if priorities shift) embedded in commit message body or `memory/decisions/`.
- **Option B carve-out (quiz still blocks)** for 4 security classes where rationale documents cannot build adversary-behavior recognition (security-specialist turn 15):
  1. Trust boundary changes (new data ingress, new external integrations)
  2. Cryptographic primitive use (signing, verification, randomness sources)
  3. Secret rotation procedures
  4. Subtractive / restructuring permission model changes

Steward (turn 2) requires deferring enactment until Tier 0 0a/0b land and 60d of healed-pipeline data show bypass is not pipeline-driven. **Honored.**

### D. `conversation` / `status` Canonicalization Verdict (working position)

**DEFER.** 2-of-2 from one developer is correlated, not independent. Per steward turn 2: track in `memory/patterns/` as observation only. Re-evaluate when Howie bootstraps or VP accumulates 60 more days of similar usage.

## ADR-0015 Content Sketch (NOT a created file)

Per developer direction, this section describes what `ADR-0015-education-gate-amendment.md` would say *if drafted*. No file is created. This is content captured for future review only.

```
# ADR-0015: Education Gate Amendment (Option C with Option B Carve-Out)

Status: WORKING-DRAFT (not authored as ADR file)
Date: [draft date]
Scope: framework
Decision: Amend Principle #6 to permit Option C (Decision Rationale Capture)
         as default education gate for medium-risk changes, with Option B
         (quiz blocks) surviving as a mandatory carve-out for 4 named
         high-risk security classes.

## Context
Education gates are dead-letter in both derived projects (IJ + VP).
Bypass is formalized in IJ's autonomous_workflow.md; VP has 4 deferrals
in 21 days. Principle #6 is silently abandoned in practice. The current
gate (walkthrough → quiz → explain-back) was never calibrated for the
developer's stated audience: a non-coding manager who needs decision
rationale, not code-syntax fluency. With ADHD-piercing-focus user profile,
gate friction is structurally hostile; bypass is rational response to
design misfit, not discipline failure.

## Decision
1. Education-gate default becomes "Decision Rationale Capture": a
   two-paragraph plain-language summary embedded in the commit message
   body or `memory/decisions/`. The summary states (a) what decision
   was made and what alternatives were declined, and (b) what would
   change if priorities shifted.

2. Option B (quiz blocks) survives as a mandatory carve-out for four
   security change classes where adversary-behavior recognition cannot
   be captured by intent-language alone:
   - Trust boundary changes (new data ingress, new external integrations)
   - Cryptographic primitive use (signing, verification, randomness)
   - Secret rotation procedures
   - Subtractive / restructuring permission model changes

3. Amendment does not enact until Tier 0 capture-pipeline fixes
   (0a + 0b in v4 Sprint 1) have landed and 60 days of healed-pipeline
   data confirm bypass is not pipeline-driven. Steward gate honored.

## Consequences
- Principle #6 ("Education gates before merge") is reinterpreted, not
  removed. The intent (decision-maker can evaluate work six months hence)
  is preserved via Decision Rationale Capture.
- Pre-existing `walkthrough`/`quiz`/`explain-back` skills remain available
  for the 4 carve-out classes and any developer who opts in.
- educator agent definition needs updating to surface the new default
  and the carve-out classes.

## Alternatives Considered
- Option A (structural enforcement, block commit, no override): Rejected.
  Maximum friction, no diagnosis, increases bypass not decreases it.
- Option B as default: Rejected. Quiz format never calibrated for stated
  audience; quiz of non-coding manager produces zero learning.
- Option D (defer the decision): Honored as enactment timing, but the
  amendment content is decided now to be ready when pipeline data lands.
```

## ADR for Lineage Manifest Extension (NOT a created file)

Steward (turn 2) requires designing `upstream_promotion_candidate` event class in the lineage substrate before any canonicalization of `conversation` / `status` happens. Content sketch for what that ADR would propose:

```
# ADR-NNNN: Lineage Substrate — Upstream Promotion Candidate Event

Status: WORKING-DRAFT (not authored as ADR file)
Scope: framework

## Decision
Add `upstream_promotion_candidate` to the lineage event taxonomy in
`.claude/custodian/lineage-events.jsonl`. Schema:
- event_type: "upstream_promotion_candidate"
- pattern_id: stable identifier
- observed_in_projects: [project names with sighting count]
- proposed_addition: {agents | commands | rules | skills} target slot
- evidence_refs: paths to derived-project artifacts
- steward_review_required: true

## Rationale
The framework-lineage.yaml manifest currently encodes a unidirectional
template→derived flow. There is no precedent for derived→template
promotion. Conversations and status command emergence in IJ + VP show
this is a real need; making the event class exist before any actual
promotion preserves auditability.
```

## Meta-Findings (v3 brief missed)

From project-analyst turn 10 (under-weighted in v3):
- **Implementer Status Protocol (superpowers, 20/25)** — folded as DONE_WITH_CONCERNS state in Sprint 1 (additive per architecture-consultant turn 14)
- **Karpathy Principle 4 (Goal-Driven Execution)** — merged into Sprint 1 (autonomous_workflow.md target)
- **Description-as-Activation-Classifier cross-source convergence** — adopt as Conflict 2 resolution (superpowers framing)

From deliberation:
- **Template has never executed `/retro` once in 68 days** (history-analyst turn 12) — derived projects inherited a discipline never validated upstream. Add to Sprint 1 Tier 0.
- **`memory/decisions/retro-action-registry.md` does not exist** despite `retro.md` referencing it (history-analyst turn 12) — the retro command's own designed tracking mechanism is broken. Sprint 1 Tier 0.
- **`write_event.content` is unsanitized in dispatch chain** (architecture-consultant turn 14) — transitive taint risk PRESENT for any agent processing external data. Sprint 2.

## Genuine Dissent Preserved

**Steward turn 2 vs. independent-perspective turns 4 + 16.** Steward argued DEFER everything until Tier 0 lands. Independent-perspective argued pipeline-INDEPENDENT items (prompt edits, dispatch heuristics, taxonomy additions) can land in Sprint 1 without waiting. The working position adopts independent-perspective's frame, but preserves steward caution by:
- Gating Sprint 2/3 items on Tier 0 health
- Describing (not enacting) Principle #6 amendment
- Describing (not enacting) lineage manifest extension
- Keeping canonicalization deferred to Howie or +60d two-project data

**Both also flagged** that 2-of-2 from one developer is correlated evidence, not independent Rule-of-Three. v4 honors this by explicitly not committing to any decision that depends on Rule-of-Three confirmation.

## Confidence (synthesis-level)

**0.75.** Load-bearing on a 2-of-2 derived-project sample. One Howie data point could shift Sprint 2/3 priorities. All Sprint 1 items are individually high-confidence (≥0.75 from their respective specialists).

## What This Document Will Accumulate Next

Anticipated research streams that should land here as appendices or revisions:
- **Howie bootstrap data** — if/when Howie becomes a third derived project, re-run the telemetry prompt; the 2-of-2 → 3-of-3 shift would validate or refute several working positions, especially canonicalization and Principle #6 amendment
- **Sprint 1 pre-flight investigation** — before executing any Sprint 1 item, document baseline (Context Budget Audit numbers, current /review cost from `ingest_token_usage.py`, NULL `command_type` row count)
- **Additional external-source analyses** — if more repos enter the research scope, their patterns should be measured against this document's working positions, not v3
- **VP telemetry expansion** — when VP's data window grows from 21d to 90d, several findings (0% Layer 3 promotion, ux-evaluator polarity, 4 aspirational unused agents) should be re-measured

## Cross-Reference

- Sealed deliberation transcript: `discussions/2026-05-16/DISC-20260516-050945-framework-adoption-sequence-two-project/transcript.md`
- 7 source ANALYSIS reports: `docs/analysis/ANALYSIS-20260515-*.md`
- Predecessor briefs: v1, v2, v3 at `docs/analysis/SYNTHESIS-20260515-adoption-brief*.md`
- Promotion candidate from this deliberation: 1 candidate awaiting review (per close_discussion.py output) — run `/promote` to inspect

## Living-Document Hygiene

When updating this document, preserve:
- The frontmatter's `date_last_updated` field
- Both Steward and independent-perspective dissent (do not smooth over)
- The ADR content sketches as sketches (do not promote them into actual ADR files without developer + steward gate sign-off)
- The "NOT YET" markers on canonicalization and Principle #6 amendment

When adding new research:
- Append new sections; do not overwrite working positions
- Cite source (turn ID if from a deliberation; analysis ID if from an external source; date if from new telemetry)
- If a working position is invalidated by new evidence, mark it `~~struck~~` with the supersession evidence cited inline — do not delete (preserve decision history)
