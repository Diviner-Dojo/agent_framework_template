# Capture Pipeline

> How discussions are created, captured, and sealed across the four-layer stack.
> Referenced from CLAUDE.md (kept slim per ADR-0016).

When a `/review`, `/deliberate`, `/build_module`, `/plan`, `/retro`, `/meta-review`, or `/lineage` command runs:

1. `scripts/create_discussion.py` creates the discussion directory and registers it in SQLite (with `command_type` inferred from slug prefix).
2. Each agent turn is captured via `scripts/write_event.py` to events.jsonl.
   - 2a. After `/review` checkpoints, specialists who gave REVISE verdicts are dispatched for reflections; results ingested via `scripts/ingest_reflection.py`. Education-gate results recorded via `scripts/record_education.py`.
3. `scripts/close_discussion.py` seals the discussion:
   - `scripts/generate_transcript.py` converts events.jsonl → transcript.md
   - `scripts/ingest_events.py` inserts events into SQLite (Layer 2), including searchable `content_excerpt` and `tags`
   - Updates discussion status to `closed` (with `duration_minutes`)
   - Rolls up per-turn token counts into `discussions.total_tokens_*` when present (skipped otherwise — the JSONL ingester is authoritative, ADR-0013)
   - `scripts/extract_findings.py` parses events for structured findings (severity, category, summary)
   - `scripts/mine_patterns.py` clusters similar findings using Jaccard similarity
   - `scripts/surface_candidates.py` identifies recurring patterns for the promotion queue
   - `scripts/compute_agent_effectiveness.py` computes per-agent uniqueness/survival metrics
   - Sets the discussion directory to read-only
4. `scripts/record_yield.py` records protocol-yield metrics into `protocol_yield`. Called at synthesis time in `/review`, `/build_module`, `/retro`.
5. `scripts/ingest_token_usage.py` (post-hoc) parses Claude Code's transcript JSONL at `~/.claude/projects/`, dedupes by `message.id`, attributes token usage to discussions by timestamp. Authoritative cost-side telemetry per ADR-0013.
6. Each `python scripts/quality_gate.py` run appends a JSONL record to `metrics/quality_gate_log.jsonl`.
7. `/knowledge-health` runs `scripts/knowledge_dashboard.py` and appends to `metrics/knowledge_pipeline_log.jsonl`.

**Context-brief events** (turn_id=1, agent="facilitator", tags="context-brief") are emitted by: /review, /deliberate, /build_module, /plan, /retro. Excluded: /analyze-project, /meta-review.

## SQLite schema additions
- **Tables**: `findings`, `promotion_candidates`, `pattern_sightings`, `agent_effectiveness`, `lineage_nodes`, `lineage_file_drift`
- **Views**: `v_rule_of_three`, `v_agent_dashboard`, `v_token_efficiency`
- **Columns**: `turns.content_excerpt`, `turns.tags`, `turns.tokens_in/out`, `turns.cache_read_tokens`, `turns.cache_create_tokens`, `discussions.command_type`, `discussions.duration_minutes`, `discussions.related_discussion_id`, `discussions.total_tokens_in/out`, `discussions.total_cache_tokens`

## Cost computation
Cost is never stored — derive at analysis time from raw token counts using `config/model_pricing.yaml`. Pricing changes are a YAML edit, not a schema migration.
