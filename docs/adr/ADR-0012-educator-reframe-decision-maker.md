---
adr_id: ADR-0012
title: "Reframe educator agent for non-coding decision-maker audience"
status: accepted
date: 2026-04-05
decision_makers: [facilitator, architecture-consultant, independent-perspective]
discussion_id: DISC-20260405-235356-build-v340-release
supersedes: null
risk_level: medium
confidence: 0.85
tags: [educator, audience-model, education-gate]
---

## Context

The educator agent was designed for developers who write code — its walkthroughs narrated code line-by-line, quizzes tested syntax knowledge and debugging skills, and mastery tiers tracked progression through CRUD → async → security implementation skills. The education gate was almost never used because it didn't match the actual audience: a non-coding manager/decision-maker who oversees an AI-augmented development team.

The user needs to understand terminology, concept relationships, and architecture trade-offs — not implementation details. They need to be well-informed about what their AI agents are doing, evaluate whether design decisions are sound, and explain changes to stakeholders.

## Decision

Reframe the educator agent definition for a non-coding decision-maker audience:

1. **Mastery tiers**: Vocabulary → Relationships → Judgment (replacing CRUD → async → security)
2. **Walkthroughs**: Explain concepts, relationships, and decision rationale — not code syntax
3. **Quizzes**: Test understanding of architecture, trade-offs, and impact — not implementation
4. **Bloom's levels**: Examples use decision-maker language ("evaluate trade-offs", "explain to stakeholder")
5. **Anti-patterns**: Explicit prohibition on code-syntax questions and assumption that the developer writes code
6. **Persona safeguard**: Inverted from "am I too lenient?" to "am I too technical?"

All structural integration points preserved: dispatch requests, capture hooks, tool references, output format.

## Alternatives Considered

### Alternative 1: Parameterized audience model
- **Pros**: Would support both developer and decision-maker audiences configurable per project
- **Cons**: Adds complexity with no current beneficiary; only one audience model is needed now
- **Reason rejected**: Principle #8 (least-complex intervention). Derived projects can customize the definition to their audience. No abstraction needed until a second audience type is actually used.

### Alternative 2: Two separate educator agents
- **Pros**: Clean separation of concerns, no audience switching
- **Cons**: Doubles agent count for a single role, fragments mastery tracking, complicates dispatch
- **Reason rejected**: The educator's structure is the same regardless of audience — only the content calibration changes. Two agents would be unnecessary duplication.

## Consequences

### Positive
- Education gate becomes usable for the actual audience for the first time
- Mastery tiers (Vocabulary → Relationships → Judgment) map directly to the decision-maker's progression
- Persona safeguard catches future drift toward code-level detail

### Negative
- Developer-audience projects using this template will need to recalibrate the educator for their audience
- Tier 3 ("Judgment") must be carefully calibrated to avoid expecting implementation knowledge

### Neutral
- Derived projects can override the educator definition to match their specific audience model

## Linked Discussion
See: discussions/2026-04-05/DISC-20260405-235356-build-v340-release/
