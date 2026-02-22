---
id: SPEC-20260222-framework-measurement-enhancements
title: "Framework Measurement Enhancements: Effort Tracking + Protocol Value"
status: draft
created: 2026-02-22
estimated_tasks: 12
autonomous_execution: false
adr_refs: [ADR-0009, ADR-0010, ADR-0011]
triggered_by: Framework self-improvement evidence review (2026-02-22)
---

# Framework Measurement Enhancements

## Goal

Close the framework's measurement gaps: add quantitative effort tracking, protocol value assessment, and batch evaluation of pending pattern adoptions. Enable retros and meta-reviews to answer "is the overhead worth it?" with data instead of intuition.

## Context

A comprehensive evidence review (2026-02-22) confirmed the framework demonstrates genuine self-improvement across 10 dimensions with three closing feedback loops. However, the loops capture *what happened* but not *how long it took* or *whether each protocol's findings justified its cost*. Three retros have raised the overhead question; none could answer it with data.

### Evidence Summary

The framework operates three feedback loops that close within 24-48 hours:

**Loop 1 — Internal Gap Detection**: ADR-0009 → ADR-0010 → ADR-0011, each triggered by the previous one revealing the next gap.

**Loop 2 — External Pattern Mining**: 59 patterns evaluated → 20 adopted → 5 confirmed with evidence → 2 reverted with reasons. Rule of Three achieved on 2 patterns.

**Loop 3 — Retrospective Calibration**: Agent miscalibration detected and corrected. Rule staleness detected and corrected same session.

### Gaps Identified

1. **No quantitative effort/velocity data** — Can't answer "is the overhead worth it?"
2. **No protocol value tracking** — Which protocols catch real issues vs. add ceremony?
3. **16 PENDING pattern adoptions** with no batch evaluation mechanism
4. **No counterfactual reasoning** — Improvements measured against prior self only
5. **Education gate debt** — Phases 3 and 4 walkthroughs/quizzes still owed

## Requirements

### Functional
- Retros must include quantitative effort analysis (protocol duration, overhead ratio)
- Retros must include protocol yield assessment (blocking findings per invocation, yield trend)
- Meta-reviews must include a Protocol Overhead Audit section
- Independent-perspective must assess marginal value of protocols (counterfactual reasoning)
- Review/build events must capture finding severity counts (blocking vs. advisory)
- PENDING adoption age must be tracked and surfaced at retro time
- Discussions must capture command_type and duration
- Quality gate outcomes must be logged for trend analysis
- A batch evaluation command must exist for clearing stale PENDING adoptions

### Non-Functional
- All changes follow Principle #8 ordering: prompt → script → command
- No new agents (measurement gaps ≠ specialist gaps)
- No automated protocol relaxation (human decides per Principle #7)
- Solo-developer proportional — no new recurring ceremonies

## Constraints

- Must use existing capture infrastructure (write_event.py, SQLite, events.jsonl)
- Must not add process overhead — these are analytical enhancements to existing flows
- Schema changes must be additive (new columns/tables, no breaking changes)

## Acceptance Criteria

- [ ] `/retro` produces an "Effort Analysis" section with computed durations
- [ ] `/retro` produces a "Protocol Value Assessment" table with yield metrics
- [ ] `/retro` reports PENDING adoption age and recommends batch-evaluate when count > 5
- [ ] `/meta-review` produces a "Protocol Overhead Audit" section
- [ ] `independent-perspective` includes counterfactual assessment in retro/meta-review contexts
- [ ] Review and build events include `blocking:N,advisory:N` tags
- [ ] `discussions` table has `command_type` and `duration_minutes` columns
- [ ] `protocol_yield` table exists and is populated during review/build synthesis
- [ ] `metrics/quality_gate_log.jsonl` is appended on each quality gate run
- [ ] `/batch-evaluate` command processes PENDING patterns and presents assessment
- [ ] All existing `python scripts/quality_gate.py` checks still pass after changes

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Schema migration breaks existing queries | Low | Medium | Additive columns only; test existing queries after migration |
| Prompt changes make commands too long | Low | Low | Keep additions concise; use query references not inline SQL |
| Effort metrics create perverse incentives | Low | Medium | Present as analysis input, never as targets |
| Batch-evaluate auto-confirms prematurely | Low | High | Require developer approval for all status changes (Principle #7) |

## Affected Components

| Component | Change Type |
|-----------|-------------|
| `.claude/commands/retro.md` | Prompt enhancement (3 additions) |
| `.claude/commands/meta-review.md` | Prompt enhancement (1 addition) |
| `.claude/agents/independent-perspective.md` | Prompt enhancement (1 new responsibility) |
| `.claude/commands/review.md` | Prompt enhancement (severity tag instructions) |
| `.claude/commands/build_module.md` | Prompt enhancement (severity tag instructions) |
| `scripts/init_db.py` | Schema additions (columns + tables) |
| `scripts/create_discussion.py` | command_type inference |
| `scripts/close_discussion.py` | duration_minutes computation |
| `scripts/quality_gate.py` | JSONL outcome logging |
| `scripts/record_yield.py` (new) | ~40-line yield recording script |
| `.claude/commands/batch-evaluate.md` (new) | New command |

## Dependencies

- Depends on: existing capture pipeline (scripts/write_event.py, scripts/init_db.py, scripts/close_discussion.py)
- Depends on: existing SQLite schema in metrics/evaluation.db
- Blocked by: nothing (all phases are independent of product code)
- Blocks: nothing (framework-only changes)

---

## Tasks

### Task 1: Enrich `/retro` with effort analysis (A1)
**Files**: `.claude/commands/retro.md`
- Add duration query to Step 1 using existing `created_at`/`closed_at` from SQLite
- Add "Effort Analysis" section to retro draft template with: total protocol time, overhead ratio, highest-cost protocol, value-per-minute assessment
- Query: `SELECT discussion_id, ROUND((julianday(closed_at) - julianday(created_at)) * 24 * 60, 1) as duration_minutes FROM discussions WHERE status = 'closed'`
- **Checkpoint**: exempt (prompt-only change, no production code)

### Task 2: Add protocol yield assessment to `/retro` (A2)
**Files**: `.claude/commands/retro.md`
- Add "Protocol Value Assessment" table to retro template
- Per protocol type: invocations, blocking findings, agent turns, yield per turn, trend
- Note: before Phase B, yield data must be manually estimated from discussion transcripts; after Phase B, it can be queried from `protocol_yield` table
- **Checkpoint**: exempt (prompt-only change)

### Task 3: Add PENDING adoption age tracking to `/retro` (A6)
**Files**: `.claude/commands/retro.md`
- Add age computation for PENDING patterns in Step 4 (adoption log review)
- Report stale-pending count (>14 days since adoption date)
- Recommend `/batch-evaluate` if stale count > 5
- **Checkpoint**: exempt (prompt-only change)

### Task 4: Add Protocol Overhead Audit to `/meta-review` (A3)
**Files**: `.claude/commands/meta-review.md`
- New section in meta-review template: per-protocol yield, cost, efficiency trend, redundancy check, solo-dev calibration
- Include explicit question: "Which protocols should be relaxed for solo development?"
- **Checkpoint**: exempt (prompt-only change)

### Task 5: Add counterfactual reasoning to `independent-perspective` (A4)
**Files**: `.claude/agents/independent-perspective.md`
- New responsibility: assess marginal value of protocols
- Prompt: "If this protocol had not been in place, would the issue have been caught by another mechanism?"
- "What is the marginal value of this protocol over the next-cheapest alternative?"
- Ground analysis in protocol_yield data when available
- **Checkpoint**: trigger → Architecture choice (architecture-consultant, independent-perspective) — modifying an agent's analytical mandate

### Task 6: Add finding severity tags to review/build capture (A5)
**Files**: `.claude/commands/review.md`, `.claude/commands/build_module.md`
- Add instruction for facilitator to tag events with `blocking:N,advisory:N` counts
- Uses existing `--tags` field in `write_event.py` — no schema change needed
- **Checkpoint**: exempt (prompt-only change)

### Task 7: Add `command_type` and `duration_minutes` to discussions (B1)
**Files**: `scripts/init_db.py`, `scripts/create_discussion.py`, `scripts/close_discussion.py`
- Add columns to `discussions` table: `command_type TEXT`, `duration_minutes REAL`
- `create_discussion.py`: auto-infer command type from slug (build-→build_module, review-→review, retro-→retro, etc.) + accept `--command-type` flag
- `close_discussion.py`: compute `duration_minutes = ROUND((julianday(closed_at) - julianday(created_at)) * 24 * 60, 1)` at seal time
- Use `ALTER TABLE ADD COLUMN` for migration safety (SQLite supports this without data loss)
- **Checkpoint**: trigger → Database schema (performance-analyst, security-specialist)

### Task 8: Add `protocol_yield` table + recording script (B2)
**Files**: `scripts/init_db.py`, new `scripts/record_yield.py`
- New table with columns: `discussion_id`, `protocol_type`, `findings_blocking`, `findings_advisory`, `findings_false_positive`, `agent_turns_used`, `outcome`, `timestamp`
- `protocol_type` CHECK constraint: 'review', 'checkpoint', 'education_gate', 'quality_gate', 'retro'
- `outcome` CHECK constraint: 'approve', 'approve-with-changes', 'request-changes', 'reject', 'pass', 'fail', 'revise-resolved', 'revise-unresolved'
- `record_yield.py` (~40 lines): CLI script taking discussion_id + counts as arguments, inserts into table
- **Checkpoint**: trigger → Database schema (performance-analyst, security-specialist)

### Task 9: Add quality gate outcome logging (B3)
**Files**: `scripts/quality_gate.py`
- After computing results, append JSONL record to `metrics/quality_gate_log.jsonl`
- Record: timestamp, pass/fail per check (format, lint, tests, coverage, adrs, reviews), total, passed_count
- Append-only — no reads during gate execution, no performance impact
- **Checkpoint**: exempt (logging addition to existing script)

### Task 10: Create `/batch-evaluate` command (C1)
**Files**: new `.claude/commands/batch-evaluate.md`
- Step 1: Read `memory/lessons/adoption-log.md`, extract all PENDING patterns
- Step 2: For each PENDING pattern, check if artifact at `Location` field exists
- Step 3: Search discussions and retros for usage evidence (mentions, confirmed findings)
- Step 4: Group into: CONFIRMED-ready (artifact exists + usage evidence), REVERTED-ready (artifact deleted or tech-stack invalidated), needs-more-data
- Step 5: Present batch assessment to developer for approval
- Step 6: Update adoption-log.md with approved verdicts
- Expected cadence: quarterly at meta-review, or when retro flags stale-pending > 5
- **Checkpoint**: trigger → New module (architecture-consultant, qa-specialist)

### Task 11: Wire yield recording into existing commands (D)
**Files**: `.claude/commands/review.md`, `.claude/commands/build_module.md`, `.claude/commands/retro.md`
- Add `python scripts/record_yield.py` calls to synthesis/close steps of each command
- Review: record after verdict synthesis
- Build: record after each checkpoint round
- Retro: record with retro's own finding counts
- **Checkpoint**: exempt (prompt-only wiring, 2-4 lines per command)

### Task 12: Validate end-to-end data flow
- Run `python scripts/init_db.py` to verify schema migration
- Run `python scripts/quality_gate.py` to verify existing checks still pass
- Run `/retro` to verify new template sections produce useful output
- Verify `metrics/quality_gate_log.jsonl` was created by quality gate run
- **Checkpoint**: exempt (verification only)

---

## Key Reuse Points

| Existing Code | Reuse In |
|---|---|
| `scripts/write_event.py --tags` | Task 6: severity tags use existing tag field |
| `discussions.created_at / closed_at` | Task 1, 7: duration derived from existing timestamps |
| `scripts/init_db.py` schema pattern | Tasks 7, 8: follow existing table creation pattern |
| `scripts/create_discussion.py` slug argument | Task 7: command_type inferred from existing slug |
| Adoption log PENDING/CONFIRMED/REVERTED lifecycle | Task 10: batch-evaluate uses existing status model |

## What NOT to Build

1. **No new agent** — measurement gaps ≠ specialist gaps
2. **No counterfactual simulation engine** — proxy metrics via independent-perspective are cheaper and more honest
3. **No real-time dashboard** — retro/meta-review cadence is sufficient for solo dev
4. **No automated protocol relaxation** — system surfaces data, human decides (Principle #7)
5. **No effort_markers table (B4)** — deferred unless B1's discussion-level duration proves insufficient

## Verification

1. `python scripts/init_db.py` — schema migration succeeds without data loss
2. `python scripts/quality_gate.py` — all existing checks pass
3. `/retro` — new Effort Analysis and Protocol Value Assessment sections produce output
4. `/meta-review` — Protocol Overhead Audit section renders correctly
5. `/batch-evaluate` — processes PENDING patterns and presents structured assessment
6. `metrics/quality_gate_log.jsonl` — populated after quality gate run
