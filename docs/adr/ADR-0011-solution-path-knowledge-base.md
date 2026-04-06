---
adr_id: ADR-0011
title: "Adopt solution-path knowledge base for cross-project learning"
status: accepted
date: 2026-04-05
decision_makers: [facilitator, architecture-consultant]
discussion_id: DISC-20260405-234809-v340-release-spec-review
supersedes: null
risk_level: low
confidence: 0.85
tags: [knowledge-management, solution-paths, cross-project]
---

## Context

The framework captures WHAT projects use (technology grids, patterns, ADRs) but not HOW they solved specific problems. When starting a new feature, there is no systematic way to check whether a similar problem has been solved before — what approaches were tried, what failed, and why the chosen approach won.

This gap leads to repeated mistakes (re-trying approaches that have been proven broken) and missed learning (not leveraging successful solution paths from other projects). The derived project (journal/RepoCademy) prototyped a solution-path system and validated its utility during active development.

## Decision

Embed solution paths into existing project profiles and workflows rather than creating new infrastructure. Specifically:

1. **Solution paths live in project profiles** (`memory/projects/*.md`) under a `## Solution Paths` section, using compound tags (`domain/sub-concept`) for cross-project lookup.
2. **Pre-build search rule** (`.claude/rules/pre_build_search.md`) triggers a grep-before-build check during `/plan` and `/build_module`.
3. **Capture is tied to existing workflows** — the commit protocol prompts solution-path capture at Steps 1.5 and 3.5, and spec closure captures solution paths from completed features.
4. **Known-broken approaches** are tracked in `memory/bugs/regression-ledger.md` under a dedicated section, queryable by the pre-build search.
5. **Taxonomy** is documented in `memory/projects/TAXONOMY.md` with compound tag conventions.

## Alternatives Considered

### Alternative 1: Separate Solution-Path Index
- **Pros**: Centralized, easy to query, dedicated structure
- **Cons**: Creates a new artifact type, new maintenance burden, duplicates information already in project profiles
- **Reason rejected**: Violates Principle #8 (least-complex intervention). Embedding in existing profiles is simpler and leverages existing workflows.

### Alternative 2: Extend ADRs with Solution Paths
- **Pros**: ADRs are already well-established, immutable
- **Cons**: ADRs capture architectural decisions, not implementation journeys. Mixing the two dilutes both. ADRs are never deleted (Principle #5), but solution paths should have a forgetting curve.
- **Reason rejected**: Different lifecycle and purpose. Solution paths are experiential knowledge with decay; ADRs are permanent decision records.

### Alternative 3: Vector-searchable Knowledge Store
- **Pros**: Powerful semantic search, handles large corpora
- **Cons**: Requires embedding infrastructure, adds dependencies, premature for current corpus size
- **Reason rejected**: Four-layer capture stack reserves vector search for Layer 4 "when corpus grows large enough." Current volume doesn't warrant it.

## Consequences

### Positive
- Prevents reinvention by making prior solution attempts discoverable
- Captures the journey (what was tried and failed), not just the destination
- Zero new infrastructure — embeds into existing commands, rules, and profiles
- Compound tag taxonomy enables precise cross-project lookup

### Negative
- Requires discipline to capture solution paths during commits (prompt-driven, not enforced)
- 90/180-day forgetting curve means stale entries need periodic review

### Neutral
- Solution paths in `_self.md` are project-specific; cross-project paths require analyzing external projects via `/analyze-project`

## Linked Discussion
See: discussions/2026-04-05/DISC-20260405-234809-v340-release-spec-review/
