---
discussion_id: DISC-20260301-215431-review-knowledge-amplification-pipeline
started: 2026-03-01T21:58:52.146463+00:00
ended: 2026-03-01T21:59:34.589712+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, independent-perspective, qa-specialist]
total_turns: 5
---

# Discussion: DISC-20260301-215431-review-knowledge-amplification-pipeline

## Turn 1 — qa-specialist (critique)
*2026-03-01T21:58:52.146463+00:00 | confidence: 0.82*
*tags: review, qa*

QA Review (confidence: 0.82). 11 findings: (High) FINDING_PATTERN regex false-positive risk; (High) sqlite3 connection leak on non-IntegrityError; (High) finding_id invariant untested; (Medium) greedy clustering order-dependent; (Medium) candidate_id collision within same second; (Medium) 30pct survival threshold fails on empty phrase sets; (Medium) shutil.move not atomic on Windows; (Medium) broad except Exception in backfill; (Medium) TOCTOU window between pipeline steps; (Low) naive datetime in check_stale; (Low) ALTER TABLE migration swallows errors. All 10 new scripts have zero test coverage. Strengths: graceful degradation, INSERT OR IGNORE dedup, dry-run universally implemented, WAL mode, CHECK constraints.

---

## Turn 2 — architecture-consultant (critique)
*2026-03-01T21:58:55.196430+00:00 | confidence: 0.87*
*tags: review, architecture*

Architecture Review (confidence: 0.87). 10 findings: (High) No ADR-0028 for Knowledge Amplification Pipeline - violates architectural gate; (Medium) STOP_WORDS duplicated with silent divergence in unify_sightings.py; (Medium) bare except Exception in close_discussion.py violates coding standards; (Medium) unify_sightings FK constraint prevents adoption-log entries from populating; (Medium) confidence_accuracy formula conflates independent properties; (Low) candidate_id collision risk; (Low) enforce_forgetting_curve auto-archives without human gate vs Principle 7; (Low) pattern_key sort instability; (Info) synthesis survival uses truncated content_excerpt; (Info) mtime unreliable on Windows. Strengths: layer boundaries maintained, Jaccard calibrated, dry-run universal, idempotent schema, dashboard architecture clean.

---

## Turn 3 — docs-knowledge (critique)
*2026-03-01T21:59:04.044817+00:00 | confidence: 0.88*
*tags: review, docs*

Docs Review (confidence: 0.88). 7 findings: (High) No ADR-0028 for pipeline architectural decision; (Medium) build_module.md Step 7b missing ingest_reflection call vs review.md Step 7c; (Medium) enforce_forgetting_curve live mode authorization model undocumented re Principle 7; (Medium) CLAUDE.md content_excerpt population description ambiguous; (Medium) unify_sightings known limitation undocumented; (Low) knowledge-health.md score scale vs section count confusion; (Low) review.md inline reflection tempfile pattern fragile. Strengths: consistent module docstrings, non-blocking semantics explicit, dry-run universal, CLAUDE.md well-structured, dashboard action items create feedback loops, command count updated correctly.

---

## Turn 4 — independent-perspective (critique)
*2026-03-01T21:59:10.271649+00:00 | confidence: 0.82*
*tags: review, independent*

Independent Review (confidence: 0.82). BLOCKING: mine_patterns.py not wired into close_discussion.py - v_rule_of_three will always return zero rows in normal operation. Core pattern detection mechanism does not execute automatically. Other findings: (Medium) Jaccard 0.4 threshold uncalibrated against real data; (Medium) synthesis survival metric incentivizes superficiality; (Medium) forgetting curve auto-archives without human gate vs Principle 7; (Medium) unify_sightings dead branch due to FK constraint; (Low) candidate_id collision risk; (Low) adoption-log entries without dates silently dropped. Pre-mortem: Rule of Three never fires due to missing wiring; Jaccard noise flood risk; agent effectiveness metrics become negative incentives. Strengths: additive not disruptive, dry-run universal, UNIQUE constraints and INSERT OR IGNORE, binary health score appropriately humble.

---

## Turn 5 — facilitator (synthesis)
*2026-03-01T21:59:34.589712+00:00 | confidence: 0.85*
*tags: blocking:2, advisory:14*

## Review Synthesis: Knowledge Amplification Pipeline

**Verdict: APPROVE-WITH-CHANGES**

### Panel
- qa-specialist (0.82), architecture-consultant (0.87), docs-knowledge (0.88), independent-perspective (0.82)

### Blocking Findings (2)

1. **Missing ADR-0028**: The Knowledge Amplification Pipeline is a significant architectural decision (4 new tables, pipeline in close_discussion.py, new observability layer). Per architectural gates: any architectural change requires an ADR. Create ADR-0028-knowledge-amplification-pipeline.md.

2. **mine_patterns.py not wired into close_discussion.py**: The v_rule_of_three view will always return zero rows because mine_patterns() is never called automatically. Add it to close_discussion.py Steps 4-6 pipeline. This is the core pattern detection mechanism.

### Advisory Findings (14)

HIGH:
- Regex false-positive risk in FINDING_PATTERN (natural-language severity words match without requiring bullet prefix)
- sqlite3.connect() not wrapped in context manager; connection leak on non-IntegrityError exceptions
- finding_id idempotency invariant untested

MEDIUM:
- STOP_WORDS divergence between unify_sightings.py (reduced set) and other 3 scripts defeats cross-source matching
- bare except Exception in close_discussion.py violates coding standards (should catch specific types)
- unify_sightings.py FK constraint prevents adoption-log entries from being inserted (synthetic IDs don't exist in discussions table)
- candidate_id timestamp collision within same second (INSERT OR IGNORE silently drops)
- build_module.md Step 7b missing ingest_reflection.py call (present in review.md Step 7c)
- Forgetting curve auto-archives without human gate (inconsistent with Principle #7)
- Jaccard 0.4 threshold uncalibrated against real discussion data
- Clustering compares only cluster[0]; order-dependent results
- CLAUDE.md content_excerpt population description ambiguous (ingest_events.py vs backfill)

LOW/INFO:
- Pattern key sort instability across documents
- mtime unreliable on Windows for git-tracked files
- Naive datetime in check_stale_adoptions vs UTC convention
- knowledge-health.md score scale vs section count confusion

### Strengths
- Pipeline is additive, not disruptive; failure isolation in close_discussion.py
- INSERT OR IGNORE / UNIQUE constraints ensure idempotency
- --dry-run on all 10 scripts
- Schema design with CHECK constraints and proper indexes
- Layer boundaries maintained; dashboard reads-only from DB
- Binary health score appropriately humble
- Consistent module-level docstrings

### Education Gate
Not recommended for this change — framework infrastructure, no product code affected.

---
