---
adr_id: ADR-0008
title: "v3.1.0: Real-World Enhancement Extraction from Derived Project"
status: accepted
date: 2026-03-24
discussion_id: DISC-20260323-182242-v31-framework-extraction-spec-review
supersedes: null
decision_makers: [facilitator, architecture-consultant, qa-specialist, docs-knowledge]
---

## Context

The agentic_journal project was the framework's first real-world deployment, forking from the template at v3.0.0. Over 33 days of intensive use (323 discussions, 385 commits, 49 ADRs, 11 retros), the framework evolved significantly through daily practice. An extraction report was produced by the source project's specialist team to guide the upstream process.

This ADR documents the decision to extract those enhancements back into the canonical template as v3.1.0.

## Decision

Extract battle-tested framework enhancements from the agentic_journal project into the template, filtered through a tech-stack-neutrality constraint. This is the first "feedback loop" release where a derived project's improvements flow back to the template.

### Included (41 items across 6 categories)

**Process Bug Fixes (6):** Spec lifecycle completion automation, retro spec audit, retro action tracking, spec budget with type distinction, review-to-commit traceability, related discussions linking.

**New Capabilities (7):** BUILD_STATUS freshness check, promotion notifications, session health nudges (6-point dashboard), context-brief formalization, agent reflection capture, developer assessment (counterfactual) in reviews, record education script.

**Rule Enhancements (4):** Trust boundary sanitization, injectable seams gate, data correctness blocking gate, advisory carry-forward requirement.

**Agent Definition Upgrades (13 agents):** Verdict-first output format (all agents), facilitator expansion (dispatch table, survival rate, Socratic prompting, model tier guidance, team development), independent-perspective capability expansion, steward streamlining with Tool Use Protocol, architecture-consultant/docs-knowledge/educator/qa-specialist/security-specialist refinements.

**Infrastructure (6):** Micro-fix protocol rule, version bump, CLAUDE.md sync, framework doc sync, lineage event, this ADR.

**Test Coverage (5 files):** test_record_education.py, test_ingest_reflection.py, test_template_neutrality.py, test_build_status_freshness.py, test_related_discussion.py.

### Excluded (with rationale)

| Item | Reason |
|------|--------|
| Capability protection (CPP C2/C3) | Flutter-specific provider default pattern — not generalizable |
| ADHD clinical UX constraints | Domain-specific design requirements for the journaling app |
| Sync boundary whitelisting pattern | Domain-specific data sync pattern (Supabase/local DB) |
| Flutter/Dart tooling in quality_gate.py | Template uses Python/ruff, not dart format/analyze |
| Journal-specific commands (journal-review) | Product-specific feedback pipeline |
| Version management details (deploy.py) | Flutter-specific deployment automation |
| Project-specific scripts (13 scripts) | deploy, screenshots, tablet, emulator, voice harness, etc. |
| Pillar framework | Product-specific vision |
| Independent-perspective elevation to "peer of facilitator" | Contradicts ADR-0005 hierarchy; reframed as capability expansion |

## Alternatives Considered

1. **Cherry-pick individual enhancements as needed** — Rejected because the enhancements form a coherent set (e.g., verdict-first across all agents, spec lifecycle across all commands). Piecemeal extraction would create inconsistency.
2. **Import everything including project-specific content** — Rejected because the template must remain tech-stack-neutral. Flutter/Dart/ADHD content is domain-specific and would confuse derived projects with different tech stacks.
3. **Wait for a second derived project to validate patterns** — Rejected because 33 days of real-world use with 323 discussions provides sufficient evidence. The Rule of Three applies to pattern sightings within a project, not to the number of projects.

## Consequences

### Architectural

- **Tech-stack-neutrality** is a named architectural consequence. All future extraction exercises should reference this ADR as precedent for the neutrality constraint.
- The template remains Python/FastAPI by default but with parameterization guidance for derived projects using other tech stacks.
- The 14-agent roster is preserved. Agent tier assignments are unchanged.
- Independent-perspective remains a specialist (equal standing per ADR-0005), with expanded capabilities but no hierarchy modification.

### Process

- The spec lifecycle is now closed-loop: specs created by `/plan` are automatically marked complete by `/build_module` and `/ship`.
- Retros now audit spec pipeline health and track action items across sprints.
- Review reports include `reviewed_files` for commit-to-review traceability.
- Advisory findings have a carry-forward requirement preventing silent accumulation.

### Agent Behavior

- All agents now lead with a plain-language verdict before technical details (verdict-first pattern).
- The facilitator has richer dispatch guidance, survival rate checking, and team development responsibility.
- Agents with Tool Use Protocols (steward, architecture-consultant, ux-evaluator) explicitly gate destructive operations.

## Source

- **Project**: agentic_journal (Flutter/Dart, v1.3.0)
- **Period**: 33 days of real-world use
- **Corpus**: 323 discussions, 385 commits, 49 ADRs, 11 retros
- **Extraction report**: FRAMEWORK_TEMPLATE_EXTRACTION_REPORT.md (produced by source project's specialist team)
- **Spec**: SPEC-20260323-182134-v31-framework-extraction.md
- **Review discussion**: DISC-20260323-182242-v31-framework-extraction-spec-review
