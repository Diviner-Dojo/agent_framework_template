---
name: feature-status-registry
description: "Pattern for tracking feature implementation status in derived projects. Reference when a derived project needs to track which framework features are implemented, planned, or deferred."
---

# Feature Status Registry Pattern

## When to Use

Use this pattern in **derived projects** (not the template itself) to track which framework features have been implemented, adapted, or deferred. This is especially useful when:

- A derived project adopts the framework incrementally
- Multiple developers need visibility into what's been built vs. what's planned
- The project needs to track divergence from the template's capabilities

## Pattern: FEATURE_STATUS.md

Create a `FEATURE_STATUS.md` file at the project root with this structure:

```markdown
# Feature Status

> Tracks implementation status of framework capabilities in this project.
> Last updated: YYYY-MM-DD

## Status Legend

| Status | Meaning |
|--------|---------|
| DONE | Fully implemented and tested |
| IN PROGRESS | Currently being built |
| PLANNED | Scheduled for a future sprint |
| ADAPTED | Implemented with project-specific modifications |
| DEFERRED | Intentionally postponed (with rationale) |
| N/A | Not applicable to this project |

## Core Framework

| Feature | Status | Notes |
|---------|--------|-------|
| Quality gate | DONE | |
| Capture pipeline | DONE | |
| Multi-agent review | DONE | |
| Education gates | PLANNED | Sprint 3 |
| Lineage tracking | ADAPTED | Simplified for single-repo |

## Project-Specific Features

| Feature | Status | Notes |
|---------|--------|-------|
| [feature name] | [status] | [notes] |
```

## Guidelines

1. **Update at sprint boundaries** — not after every commit
2. **Include rationale for DEFERRED** — prevents the same question from being asked repeatedly
3. **Track ADAPTED features separately** — these are intentional divergences from the template
4. **Link to ADRs** where adaptation decisions are documented
5. **Keep it flat** — resist the urge to nest categories deeply; a single table per section is sufficient

## Relationship to Other Tracking

- `FEATURE_STATUS.md` tracks **what** is implemented (high-level capability view)
- `BUILD_STATUS.md` tracks **current session** work (ephemeral, session-scoped)
- `framework-lineage.yaml` tracks **structural drift** from the template (file-level)
- `memory/lessons/adoption-log.md` tracks **patterns** evaluated from external projects
