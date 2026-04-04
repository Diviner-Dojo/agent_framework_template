---
adr_id: ADR-0010
title: "Replace Specialist Philosophy with Values + Domain Lens"
status: accepted
date: 2026-04-04
decision_makers: [facilitator, architecture-consultant, docs-knowledge, independent-perspective]
discussion_id: DISC-20260404-065224-review-agent-reasoning-upgrade
supersedes: null  # Partially supersedes ADR-0005 Section 1 (Specialist Philosophy)
risk_level: medium
confidence: 0.88
tags: [agent-architecture, reasoning-quality, finding-extraction]
---

## Context

ADR-0005 introduced "Specialist Philosophy" as a free-form prose section in every agent definition — core beliefs about each agent's craft. In production usage (agentic_journal project, 6 weeks), two problems emerged:

1. **Philosophy sections were skipped in practice.** Agents jumped straight to checklist execution without processing the philosophy prose. The narrative format affected tone but not reasoning procedure.
2. **Finding extraction rate degraded to 9.5%.** The extraction pipeline could not reliably parse findings from agents that lacked structured reasoning entry points.

Evidence: agentic_journal ADR-0055, DISC-20260330-142553, finding extraction rate measurements across 20+ reviews.

## Decision

Replace `## Specialist Philosophy` in all 12 agent definitions with two new sections:

- **`## Values`** (2-3 sentences): Load-bearing beliefs that shape judgment in edge cases. Extracted using the heuristic: keep every sentence that introduces a value or tension between values; cut every sentence that illustrates, persuades, or narrates. Operates at Bloom's Evaluate/Create level.

- **`## Domain Lens`** (3-5 steps): Structured reasoning sequence applied before analysis. The procedural scaffold that ensures minimum coverage. Operates at Bloom's Apply level.

Additionally:
- `Rule` and `Exceptions` fields added to specialist finding output formats (enables deduplication and pattern mining)
- Domain reframe instruction added to facilitator dispatch template
- Facilitator synthesis switched to delta format with location-aware deduplication

## Alternatives Considered

### Alternative 1: Keep Specialist Philosophy, add Domain Lens alongside
- **Pros**: Preserves narrative richness, no content loss risk
- **Cons**: Doesn't solve the "philosophy gets skipped" problem; increases definition length
- **Reason rejected**: The problem is that free-form prose doesn't produce procedural changes in agent behavior

### Alternative 2: Values + Domain Lens + Calibration Exemplars
- **Pros**: Adds concrete scenarios that anchor judgment (proposed by independent-perspective during review)
- **Cons**: Adds ~100 tokens per agent; may re-introduce narrative that gets skipped
- **Reason rejected for now**: Monitoring homogenization risk first. If agent uniqueness scores decline over 5-10 reviews, exemplars will be added as a targeted fix.

## Consequences

### Positive
- Finding extraction rate improved from 9.5% to ~16.2% in source project
- Agents have a guaranteed reasoning entry point before analysis
- Rule/Exceptions fields enable cross-agent deduplication in facilitator synthesis
- Domain reframe in dispatch activates specialist perspective on the right problem

### Negative
- Narrative richness reduced — some calibration anchors lost in compression (mitigated by restoring the educator's success criterion)
- Homogenization risk — 10 of 12 Values sections follow a similar rhetorical structure (monitor via agent_effectiveness uniqueness scores)
- Domain Lens steps could become rigid checklists if agents treat them as exhaustive rather than as starting points

### Neutral
- ADR-0005's "Specialist Philosophy" terminology is now stale in the ADR text but the intent (professional judgment) is preserved in the Values sections
- CLAUDE.md updated to reference Values + Domain Lens instead of "specialist philosophy"

## Linked Discussion
See: discussions/2026-04-04/DISC-20260404-065224-review-agent-reasoning-upgrade/
