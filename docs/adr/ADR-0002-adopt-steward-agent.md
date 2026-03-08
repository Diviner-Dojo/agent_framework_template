---
adr_id: ADR-0002
title: "Adopt the Steward Agent for Framework Lineage Management"
status: accepted
date: 2026-03-07
decision_makers: [facilitator, architecture-consultant]
discussion_id: docs/STEWARD_ARCHITECTURE.md
supersedes: null
risk_level: medium
confidence: 0.85
tags: [framework, lineage, steward, agent]
---

## Linked Discussion

The deliberation artifact for this decision is `docs/STEWARD_ARCHITECTURE.md`, produced through deep research across Claude and Gemini. It defines the five-phase Steward Architecture and served as the specification for this ADR.

## Context

As the framework is adopted by multiple derived projects, there is no mechanism to track how each project relates to the canonical template — what version it forked from, how far it has drifted, which changes are intentional specializations vs. unintentional divergence, and which improvements could flow back upstream.

A detailed architectural proposal (`docs/STEWARD_ARCHITECTURE.md`) produced through deep research across Claude and Gemini defines a five-phase plan for bidirectional improvement flow. Phase 1 ("The Chronicler Awakens") establishes the foundation: lineage tracking, drift detection, and a manifest file.

The key design question was whether to embed steward capabilities into the existing `project-analyst` agent or create a separate agent.

## Decision

Create a new **Steward agent** (`.claude/agents/steward.md`) as a separate, peer-level agent alongside the Facilitator and Project Analyst. Implement Phase 1 of the Steward Architecture: manifest (`framework-lineage.yaml`), drift scanning, `/lineage` command, and SQLite schema extensions.

### Why a Separate Agent

1. **Directionality**: Project Analyst is outward-facing (evaluating external projects). The Steward is inward-facing (tracking this project's lineage relationship to its template). These are fundamentally different concerns.
2. **Tooling**: Project Analyst is explicitly read-only on targets (Critical Rule #1). The Steward requires Write access to maintain the manifest and lineage events.
3. **Lifecycle**: Project Analyst runs on-demand during `/analyze-project`. The Steward has a graduated autonomy model that evolves over time.
4. **Principle #4 (Independence)**: Combining external pattern evaluation with internal lineage management conflates concerns that benefit from separation.

### Phase 1 Scope

- `framework-lineage.yaml` manifest at project root
- `scripts/lineage/` package (manifest CRUD, drift scanning, initialization)
- `.claude/custodian/lineage-events.jsonl` append-only event log
- SQLite tables: `lineage_nodes`, `lineage_file_drift`
- `/lineage` command (status, validate, drift-report)
- Steward agent definition (Chronicler sub-function only, sonnet tier)

### Deferred to Later Phases

- Version vectors, git hooks, speciation alerts (Phase 2)
- Vouchers, `/gift` command, change classification, three-way merge (Phase 3)
- Attribution system, contribution tracking (Phase 4)
- Compatibility matrix, lateral transfer, ecosystem dashboard (Phase 5)

## Alternatives Considered

### Alternative 1: Extend project-analyst with steward capabilities

- **Pros**: Fewer agents, shared orchestration infrastructure
- **Cons**: Conflates inward/outward concerns, requires changing project-analyst's read-only constraint, different autonomy models
- **Reason rejected**: Violates Principle #4 and creates a god-agent with too many responsibilities

### Alternative 2: Embed steward logic into facilitator prompts

- **Pros**: Lightest touch per Principle #8, no new agent
- **Cons**: Facilitator already has complex orchestration responsibilities, limits future autonomy graduation, no independent context window for lineage analysis
- **Reason rejected**: Would overload the facilitator and prevent the graduated autonomy model

## Consequences

### Positive

- "How out of date am I?" becomes answerable in one command (`/lineage`)
- Framework drift becomes visible and measurable
- Foundation for bidirectional improvement flow in later phases
- Clean separation between external analysis (project-analyst) and internal lineage (steward)

### Negative

- Agent count increases from 10 to 11
- New SQLite tables and scripts to maintain
- Additional framework infrastructure to learn

### Neutral

- The Steward starts at low autonomy (observe and report only)
- Integration with `/ship`, `/review`, `/retro` deferred to Phase 2+
