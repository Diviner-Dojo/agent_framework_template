---
name: adr-writing
description: "Guide for writing Architecture Decision Records. Reference when creating ADRs, reviewing architectural decisions, or documenting design choices."
---

# ADR Writing Guide

## What is an ADR?

An Architecture Decision Record captures a single significant architectural decision: what was decided, why, what alternatives were considered, and what consequences follow. ADRs are the framework's backbone — they create an interconnected chain of reasoning.

## When to Write an ADR

Write an ADR when:
- Choosing between technologies, frameworks, or libraries
- Defining module boundaries or component responsibilities
- Establishing patterns that will be reused across the codebase
- Making trade-offs that should be documented (performance vs. readability, etc.)
- Changing a previous architectural decision

Do NOT write an ADR for:
- Implementation details that don't affect architecture
- Bug fixes or minor refactoring
- Configuration changes

## ADR Quality Criteria

### Context Section
- Describes the problem, not the solution
- Explains what forces are at play
- Mentions relevant constraints and requirements
- A reader should understand WHY this decision was necessary

### Decision Section
- States the decision clearly and specifically
- Explains the reasoning, not just the conclusion
- Someone unfamiliar with the project should understand what was decided

### Alternatives Section
- Lists genuinely considered alternatives (not straw men)
- Each alternative has pros, cons, and a specific reason for rejection
- Demonstrates that the decision space was explored

### Consequences Section
- Honest about negative consequences (trade-offs accepted)
- Specific enough to be verifiable later
- Includes neutral consequences (things that change but aren't good or bad)

## Common ADR Mistakes

1. **Too vague**: "We decided to use a good architecture" → Be specific about what pattern/tool/approach
2. **Missing alternatives**: Only documenting the chosen option → Always document what was NOT chosen and why
3. **No consequences**: Skipping trade-offs → Every decision has costs; document them
4. **Missing context**: Starting with the decision → Context should make the decision feel inevitable
5. **Stale status**: ADR says "proposed" but was implemented months ago → Keep status current

## Template

See `docs/templates/adr-template.md` for the full template with YAML frontmatter.

## ADR Lifecycle

1. **Proposed**: Written during planning or review
2. **Accepted**: Approved by the developer/team
3. **Superseded**: Replaced by a newer ADR (the old one is never deleted, just marked superseded with a link to the replacement)
4. **Deprecated**: No longer relevant but not replaced (context changed)

Nygard's insight: "The consequences of one ADR are very likely to become the context for subsequent ADRs."

## Deferred ADR Placeholder Pattern

When a decision is identified during planning or review but cannot be fully resolved yet, create a **deferred ADR placeholder** to reserve the ADR number and capture the decision context before it's lost.

### When to Use

- A spec review identifies an architectural decision that needs its own ADR
- Multiple specs reference the same ADR number and you need to resolve the conflict early
- A decision is blocked on information that will arrive later (e.g., performance benchmarks, external API availability)

### Template

```yaml
---
adr_id: ADR-NNNN
title: "[Decision title — be specific even if deferred]"
status: proposed
date: YYYY-MM-DD
decision_makers: []
discussion_id: null
supersedes: null
scope: project  # framework (universal to all projects) / project (this project only) / hybrid
risk_level: medium
confidence: 0.50
tags: [deferred]
---

## Context

[Capture the context NOW while it's fresh. This is the most important section
for a deferred ADR — if you lose the context, the ADR becomes much harder to
write later.]

## Decision

**Status: DEFERRED** — [reason for deferral and what will unblock it]

Expected resolution: [date or trigger condition]

## Alternatives Considered

[List known alternatives even if analysis is incomplete]

## Consequences

[To be completed when the decision is made]
```

### Rules

1. **Reserve the ADR number immediately** — prevents conflicts when multiple specs need ADRs
2. **Capture context while fresh** — the context section should be complete even if the decision isn't
3. **Set confidence to 0.50** — signals this is not yet a real decision
4. **Include the `deferred` tag** — makes deferred ADRs queryable
5. **Set a resolution trigger** — prevents deferred ADRs from being forgotten
6. **Classify `scope:`** (framework / project / hybrid) per the `documenting-decisions` skill — framework-scoped ADRs are propagation candidates for the template and shared-memory changelog
