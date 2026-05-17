---
review_id: REV-20260512-033416-token-telemetry-impl
discussion_id: DISC-20260512-032846-token-telemetry-impl-review
pr_id: ""
risk_level: medium
collaboration_mode: structured-dialogue
exploration_intensity: medium
agents_activated: [qa-specialist, architecture-consultant, performance-analyst, security-specialist, docs-knowledge]
reviewed_files:
  - scripts/init_db.py
  - scripts/close_discussion.py
  - scripts/ingest_token_usage.py
  - config/model_pricing.yaml
  - memory/lessons/adoption-log.md
  - docs/adr/ADR-0013-token-efficiency-telemetry.md
  - CLAUDE.md
rounds: 1
consensus_reached: true
verdict: request-changes
confidence: 0.86
review_duration_minutes: 8
---

## Summary

5-move implementation of ADR-0013 (token-efficiency telemetry). Specialists converge: the architecture is sound, the ADR commitments are honored, but four issues are blocking — a missing CLAUDE.md directory entry (convergent), a latent fan-out bias in `v_token_efficiency` (correctness, not yet surfaced), a missing symlink guard on the JSONL ingest path (REVIEW.md rule 18 violation), and zero test coverage for the new 600-line ingester (testing_requirements.md violation).

## Request Context

- **What was requested**: Multi-agent code review of the 5-move adoption path for ADR-0013 (token-efficiency telemetry).
- **Files/scope**: 7 files — `scripts/init_db.py`, `scripts/close_discussion.py`, `scripts/ingest_token_usage.py` (new), `config/model_pricing.yaml` (new), `memory/lessons/adoption-log.md`, `docs/adr/ADR-0013-token-efficiency-telemetry.md` (new), `CLAUDE.md`.
- **Developer-stated motivation**: About to start framework efficiency work; needs measurement infrastructure to A/B compare approaches by token cost.
- **Explicit constraints**: Do not overdesign. JSONL ingest is system of record. No live instrumentation. No cost stored. No backfill.

## Findings by Specialist

### QA Specialist
- Zero tests for new 600-line ingester (BLOCKING — `testing_requirements.md` `>=80%` rule).
- No boundary tests in `_attribute` for timestamp == window.start/end (BLOCKING — silent double-attribution risk).
- No regression test for the clobber-guard in `close_discussion.py:81-89` (BLOCKING — the guard is the entire safety contract of the ADR-0013 integration).
- Advisory: dedup first-wins policy undocumented; f-string DDL; migration list duplicated; `--discussion` silent no-op.
- Confidence: 0.88

### Architecture Consultant
- CLAUDE.md Directory Layout omits `config/` (BLOCKING — `framework_doc_sync.md` violation). 1-line fix.
- Advisory: `config/` as generic top-level namespace; migration list duplication.
- Verified ADR-0013 alignment on all 6 commitments. Parser isolation is real. Four-layer model intact.
- Confidence: 0.86

### Performance Analyst
- `v_token_efficiency` LEFT JOIN protocol_yield fan-out bias (BLOCKING — latent correctness, materializes on next `/build_module` with checkpoints; pre-aggregate via CTE).
- Advisory: `_attribute` is O(M×D), document complexity; full-scan every run; cache-field collapse loses 12.5x pricing precision; `claude-sonnet-4-7` missing from `model_pricing.yaml`.
- Confidence: 0.82

### Security Specialist
- Symlink traversal in `discover_session_dirs` and `_iter_jsonl_files` — no `.resolve()`, no prefix-validation against `CLAUDE_PROJECTS_ROOT` (BLOCKING — REVIEW.md rule 18 violation).
- f-string DDL pattern in `_ensure_token_columns` and `init_db.py` migration loop (medium — not exploitable today, hardcoded values only; whitelist guard recommended).
- Low: home path leakage in error message; unbounded `json.loads`.
- Verified clean: `_parse_message_line` never touches `message.content`; ADR-0013 privacy constraint architecturally enforced by absence.
- Confidence: 0.88

### Docs Knowledge
- CLAUDE.md Directory Layout omits `config/` (BLOCKING — convergent with architecture-consultant).
- Advisory: `state.json` shows `complete`, SQLite shows `closed` — two state systems, SQLite is authoritative (verified by query); divergence is by design but confusing. Adoption-log frontmatter stale (`patterns_adopted` should be 57, `patterns_deferred` 41). ADR-0013 propagation not queued.
- Confidence: 0.82

## Required Changes Before Merge

1. **Add `config/` to CLAUDE.md Directory Layout** (CLAUDE.md:108-144). Insert between `scripts/` and `src/`: `config/         — Runtime configuration (model_pricing.yaml for token cost computation)`. Convergent finding from architecture-consultant + docs-knowledge.

2. **Fix `v_token_efficiency` fan-out bias** (scripts/init_db.py:248-266). Pre-aggregate `protocol_yield` in a CTE before LEFT JOIN. Today's bias is 0 (verified — no discussion currently has multiple yield rows), but `/build_module` discussions with checkpoint reviews will silently inflate `avg_tokens_out`. Cheap to fix now; expensive to discover after decisions are made on wrong numbers.

3. **Add symlink guard to JSONL discovery** (scripts/ingest_token_usage.py:119-124 and 202-209). After constructing each candidate path, `.resolve()` and verify `str(resolved).startswith(str(CLAUDE_PROJECTS_ROOT.resolve()))`. Apply in both `discover_session_dirs` and `_iter_jsonl_files`. REVIEW.md rule 18.

4. **Add tests for `scripts/ingest_token_usage.py`** (new file `tests/test_ingest_token_usage.py`). At minimum cover: (a) `_parse_message_line` valid/missing-id/missing-timestamp/malformed; (b) `_attribute` boundary cases (`timestamp == window.start`, `== window.end`, `< start`, `> end`); (c) dedup first-wins; (d) idempotency (run twice, assert same totals); (e) clobber-guard regression — assert `discussions.total_tokens_in` is preserved when `turns` has no token data. The clobber-guard test guards against the future refactor that silently destroys ingester data.

## Recommended Improvements (Non-Blocking)

1. **Whitelist guard for DDL f-strings** (init_db.py:290, ingest_token_usage.py:259). Add `_ALLOWED_TABLES` / `_ALLOWED_TYPES` assertions. Pattern hygiene; not exploitable today.
2. **Document `_attribute` complexity** (ingest_token_usage.py:307-312). O(M×D), newest-first first-match-wins. Log warning when multiple windows match.
3. **`--since` mtime fast-path**. Skip session directories whose mtime predates the filter date before opening files.
4. **Cache-field split in `discussions` rollup**. Add `total_cache_read_tokens` and `total_cache_create_tokens` columns to mirror the per-turn schema; the collapsed `total_cache_tokens` makes cost computation impossible at the discussion grain.
5. **Add `claude-sonnet-4-7` to `config/model_pricing.yaml` models map** (the model that ran this review).
6. **Reconcile migration list duplication** (init_db.py:281-287 vs ingester:248-262). Either extract to shared constant or have the ingester call `init_db.init_db()`. If keeping duplication, add cross-reference comments in both files.
7. **Document `config/` scope in CLAUDE.md** when adding it to Directory Layout — what does and does not belong there.
8. **Update adoption-log.md frontmatter**: `last_updated: 2026-05-12`, `patterns_adopted: 57`, `patterns_deferred: 41`.
9. **ADR-0013 propagation note**: Add a Consequences line that the framework-scope ADR is a propagation candidate per `documentation_policy.md`.
10. **Resolve adoption-log status vocabulary**: replace `DEFERRED-AS-PATTERN-BUT-ADOPTED-AS-INFRASTRUCTURE` with `DEFERRED` plus an `Infrastructure adoption:` sub-field, OR formally define the hybrid status in the log's header.
11. **Document dedup first-wins policy** in `_collect_messages` docstring.
12. **Warning on unknown `--discussion` filter** that resolves to zero windows.
13. **Home-path redaction in stderr message** (ingest_token_usage.py:483-487).
14. **Line-length guard before `json.loads`** in `_parse_message_line` — `if len(line) > 1_000_000: return None`.
15. **Reconcile state.json/SQLite status divergence**: workflow state vs seal state. Either harmonize or document the distinction in CLAUDE.md.
16. **Verify `docs/FRAMEWORK_SPECIFICATION.md`** for capture-pipeline accuracy per `framework_doc_sync.md`.

## Speculative Findings — Lower Confidence

None. All findings had confidence >= 0.80.

## Developer Assessment (Counterfactual)

To be filled in by developer at review time.

## Education Gate

- **Required**: yes (light)
- **Scope**: clobber-guard reasoning in `close_discussion.py:81-89` and parser-isolation contract in `ingest_token_usage.py`
- **Bloom's levels**: Understand + Apply
- **Mastery tier**: Tier 1
- **Justification**: Developer authored the ADR and orchestrated the build, so architectural model is internalized. Walkthrough should focus on the two specific traps a future maintainer might hit: re-running close on attributed data (clobber-guard) and reaching into `~/.claude/projects/` (path isolation). No quiz needed.
