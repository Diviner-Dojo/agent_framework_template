---
adr_id: ADR-0028
title: "Knowledge Amplification Pipeline (automated Layer 2 enrichment at closure)"
status: accepted
date: 2026-03-01
decision_makers: [facilitator, architecture-consultant, independent-perspective]
discussion_id: DISC-20260301-215431-review-knowledge-amplification-pipeline
supersedes: null
risk_level: medium
confidence: 0.85
tags: [knowledge-pipeline, layer-2, layer-3, findings, patterns, effectiveness]
---

## Context

The four-layer capture stack (Layer 1: immutable files, Layer 2: SQLite index, Layer 3: curated memory, Layer 4: optional vector) captures rich multi-agent discussion content — 85+ discussions with 430+ agent turns. However, knowledge was locked in Layer 1. The `findings`, `reflections`, and `decisions` tables in Layer 2 were empty. All `memory/` subdirectories (patterns, decisions, reflections, rules) contained only `.gitkeep`. Knowledge was captured but never amplified into reusable patterns.

The `/promote` command existed but required manual candidate identification with no pipeline feeding it. The Rule of Three (patterns seen in 3+ independent sources get priority consideration) had no automated detection mechanism for discussion-derived patterns.

## Decision

Add an automated Knowledge Amplification Pipeline that enriches Layer 2 at discussion closure time. The pipeline runs as Steps 4-6 in `close_discussion.py`, after the existing transcript generation, event ingestion, and status update:

1. **Extract findings** (`extract_findings.py`): Parse events.jsonl for structured findings with severity and category
2. **Mine patterns** (`mine_patterns.py`): Cluster similar findings using Jaccard similarity, record sightings in `pattern_sightings` table
3. **Surface candidates** (`surface_candidates.py`): Identify recurring findings/reflections for the promotion queue
4. **Compute effectiveness** (`compute_agent_effectiveness.py`): Track per-agent uniqueness, survival rate, confidence calibration

Each step is wrapped in `try/except` so pipeline failures cannot block discussion closure (the core seal operation). This preserves the existing guarantee that `close_discussion.py` always seals the discussion.

New schema additions:
- Tables: `findings`, `promotion_candidates`, `pattern_sightings`, `agent_effectiveness`
- Views: `v_rule_of_three` (patterns with 3+ discussion sightings), `v_agent_dashboard` (per-agent metrics)
- Columns: `turns.content_excerpt` (searchable), `turns.tags` (JSON)

Pattern matching uses Jaccard similarity on key-phrase sets (stop-word removal, length > 2 filter) with a 0.4 threshold for clustering. No ML dependencies.

Supporting scripts: `enforce_forgetting_curve.py` (90-day review flag, 180-day archive), `check_stale_adoptions.py` (adoption log staleness), `knowledge_dashboard.py` (8-section health report with 0-7 score), plus one-time backfill scripts.

## Alternatives Considered

### Alternative 1: On-demand extraction (no pipeline at closure)
- **Pros**: No closure latency increase, simpler close_discussion.py
- **Cons**: Findings are never extracted unless someone remembers to run the scripts; knowledge amplification never happens organically
- **Reason rejected**: The framework's value proposition depends on knowledge being amplified automatically. Manual-only extraction has the same failure mode as the current empty Layer 2/3.

### Alternative 2: Periodic batch extraction (cron-style)
- **Pros**: No per-closure overhead, can process in bulk
- **Cons**: Findings not available immediately after closure; no way to surface promotion candidates in real-time; requires external scheduler
- **Reason rejected**: Findings should be available for the next review/retro immediately. Batch processing introduces staleness.

### Alternative 3: Materialized views instead of separate tables
- **Pros**: No pipeline code needed; SQLite computes findings/patterns on query
- **Cons**: SQLite lacks full-text search and materialized views; regex extraction cannot be done in SQL; Jaccard similarity requires procedural code
- **Reason rejected**: The extraction logic (regex parsing of agent output, NLP-style phrase extraction) cannot be expressed in SQL.

## Consequences

### Positive
- Layer 2 populated with structured findings queryable by severity, category, agent
- Pattern detection (Rule of Three) identifies recurring issues across discussions automatically
- `/promote` now has a queue of candidates rather than requiring manual identification
- Agent effectiveness metrics enable data-driven agent calibration in retros and meta-reviews
- Knowledge dashboard provides pipeline health visibility

### Negative
- Closure latency increases by 1-3 seconds (4 additional script steps)
- Pipeline failures are silently swallowed (by design — non-blocking)
- 10 new Python scripts increase framework maintenance surface
- Stop words and normalization logic duplicated across scripts (consolidation recommended)
- Jaccard similarity threshold (0.4) is uncalibrated against real data and may produce false clusters

### Neutral
- Backfill scripts are one-time and can be removed after initial migration
- Dashboard trend log (JSONL) is append-only and orthogonal to the DB

## Known Limitations

- `unify_sightings.py` requires adoption-log `analysis_id` values to match `discussion_id` values in the SQLite database. External project analyses not captured via the pipeline are silently skipped.
- Forgetting curve uses file modification time (`st_mtime`) which is unreliable on Windows for git-tracked files. The `last_referenced_at` column in `promotion_candidates` partially compensates.
- Live forgetting curve execution (without `--dry-run`) should be preceded by human review of dry-run output, consistent with Principle #7 for demotions.

## Linked Discussion
See: discussions/2026-03-01/DISC-20260301-215431-review-knowledge-amplification-pipeline/
