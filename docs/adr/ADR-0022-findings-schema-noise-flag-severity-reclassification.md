---
adr_id: ADR-0022
title: "findings.is_noise flag and severity reclassification — closing the write-only knowledge loop"
status: accepted
date: 2026-06-12
decision_makers: [facilitator, qa-specialist, architecture-consultant, docs-knowledge]
discussion_id: DISC-20260612-004557-t4a-knowledge-loop-spec-review
spec_id: SPEC-20260612-004321
supersedes:
scope: framework
risk_level: medium
confidence: 0.91
tags: [knowledge-loop, findings, severity, extract_findings, mine_patterns, promote, schema-migration, backfill]
---

## Context

The framework's knowledge loop is write-only. An audit of the live `metrics/evaluation.db`
(2026-06-12, 396 findings rows) found two root causes. (Provenance note for derived
projects: the audit ran with a top-tier orchestrator, but the classification defect is
deterministic — a regex over stored rows, not model-dependent — so the severity skew
reproduces regardless of the model tier that produced the findings.)

**Root cause A — severity histogram is meaningless.** `_classify_severity` in
`scripts/extract_findings.py` matches keyword patterns against the **full event body**,
critical-tier first, first-match-wins. Any event body mentioning `injection` (even in the
phrase "no injection risk was found") is classified `critical`. The result: 53 `critical`
rows vs. 1 `high` row — the opposite of what the distribution should look like.
**This defect is deterministic** (a regex design error, not a model-output artifact) and
reproduces regardless of model tier or agent configuration.

**Root cause B — boilerplate fills the findings table.** `_is_verdict_boilerplate` (added
2026-05-29) catches verdict headers and confidence-only lines but not review-scaffold summaries
(section headers like `## Findings`, count summaries like `8 findings (1 HIGH blocking…)`,
per-agent headers like `Security Review: 5 findings`, process scaffolds like `Validation pass
complete`). These scaffold lines pass the filter and land as findings, polluting the pattern-mining
token sets and generating phantom promotion candidates with opaque `pattern_hash={fp[:12]}…` display.

The net effect: 19 pending promotion candidates with 0 ever promoted, `decisions`=0, all 12
reflections unpromoted. The read path never fires: `searching-prior-art` checks only
`memory/{projects,patterns}`, `memory/bugs/regression-ledger.md`, and `docs/adr/` — never the 113
transcripts or the 396-row `findings` table. `/review` has no "prior findings on these files"
pre-read. The entire four-month capture investment is not being consumed.

## Decision

Add `findings.is_noise INTEGER NOT NULL DEFAULT 0` to the schema and rework the severity
classifier. Both changes are implemented in SPEC-20260612-004321 (T4-A, three sub-units):

1. **P1 — Read-path reconnect.** Extend `searching-prior-art` with two new search locations
   (captured findings via sqlite3, discussion transcripts via grep). Add a "prior findings on
   these files" pre-read step to `/review`. Both degrade gracefully on absent/pre-migration DB.

2. **P2 — Capture stream + severity calibration.** `is_noise` column added to `findings` via
   guarded idempotent migration. `_is_verdict_boilerplate` broadened with four principled
   scaffold categories. `_classify_severity` reworked to: (a) honor explicit `Severity:` markers
   first; (b) scan only the topical first sentence (not the full body); (c) use word-boundary
   highest-tier-wins rather than dict-order first-match; (d) require qualified phrases
   (`injection vulnerability`, `sql injection`) for `critical`. One-time backfill script flags
   existing noise rows and recalibrates severity in place (never deletes). New
   `severity-calibration` skill for prompt-level rubric so specialists emit honest severity
   markers at the source.

3. **P3 — Usable /promote.** Step 1 query joins a representative `pattern_sightings.summary`
   per candidate (correlated LIMIT 1 subquery) so candidates display as human-readable text
   rather than opaque hex prefixes. New `check_promotion_backlog` advisory in
   `scripts/quality_gate.py` warns when the backlog exceeds 5 pending candidates or 30 days
   without promotion activity.

## Alternatives Considered

**Delete noise rows instead of flagging.** Rejected: deletes destroy the audit trail. The 396-row
corpus represents four months of captures; even scaffold rows carry the original `raw_excerpt`
and `created_at` that contextualise when and where a discussion ran. A `is_noise` flag preserves
the data while excluding it from downstream consumers.

**Filter at query time only (no schema change).** Rejected: every consumer would need to independently
re-implement the `_is_verdict_boilerplate` logic and run it over every row on every query — CPU
wasted on a stable classification, and consistency not guaranteed. A persisted flag is computed
once at extract or backfill time and trusted thereafter.

**Broad `content` scan for severity (old approach).** The prior `_classify_severity` scanned the
full event body with substring matching. Any event body mentioning `injection` produced a `critical`
finding — even negations like "no injection risk found". Replaced with: explicit marker > topical
summary heuristics with word-boundary regex > default-medium. The qualification threshold for
`critical` now requires a specific phrase (`injection vulnerability`, `sql injection`, etc.).

## Consequences

**Persistent schema change.** `findings.is_noise` is a new NOT NULL column with DEFAULT 0.
All downstream consumers must honor it:
- `mine_patterns.py` excludes noise findings from both query branches (discussion_id and --all).
- `knowledge_dashboard.py` counts and severity-buckets only non-noise findings.
- Future scripts reading `findings` must filter `WHERE is_noise = 0` (or handle noise rows
  explicitly).
- Derived projects' existing DBs gain the column on the next `init_db` run (idempotent ALTER).

**Invariant — flag, never delete (C2).** Existing finding rows are never deleted. The backfill
sets `is_noise=1` and recalibrates `severity` in place, preserving the full audit trail
(`raw_excerpt`, original insert timestamp). This invariant applies to all future noise-handling
code in this framework.

**Severity histogram semantics change.** After backfill, `critical` in `findings` means a
finding where the topical first sentence carries a qualified critical-tier phrase
(`injection vulnerability`, `data loss`, `authentication bypass`). Historical findings will
read differently after backfill. The pre-backfill distribution (53/1 critical/high) had no
diagnostic value; the post-backfill distribution does.

**Cross-import boundary.** `backfill_finding_noise.py` imports `_is_verdict_boilerplate` and
`_classify_severity` from `extract_findings.py` (single source of truth, per C2). These are
private-symbol cross-imports; their definitions carry a comment noting the intentional
cross-import to prevent future refactors from silently breaking the dependency.
