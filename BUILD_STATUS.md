# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-05-12T03:35Z

## Current Task

**Status:** Phase 3 deliberation complete. Build handoff prepared for next session.
**Branch:** `feature/project-analysis-backport`

### In Progress

- **Memory architecture exploration (Phases 1–4)**
  - Phase 1 (broad survey) — complete; report at `docs/research/phase1-connection-facilitators.md`
  - Phase 2 (sanity check on alternatives) — complete; integrated into the architecture framing memory
  - Phase 3 (tooling research + decision brief) — complete; report at `docs/research/phase3-tooling-decision-brief.md`
  - Phase 4 (build) — **handoff prompt ready** at `docs/dispatches/phase4-build-handoff.md`; not yet started

### Architecture (settled this session — see `~/.claude/projects/<slug>/memory/project_memory_architecture_framing.md` for full detail)

**Philosophical commitments:**
- Sources are canonical. Everything else (graph, wiki, summary, index) is a vehicle for engaging with them.
- Suchness preservation is load-bearing. Source-resurfacing is a first-class user action.
- Working terminology: **sourced assertion** (atomic unit), **source binding** (the link), *"the source asserts X"* (verb form).

**Substrate decision:**
- **Per-project (Layer 2)**: SQLite + sqlite-vec, indefinitely. Stack A′ from the Phase 3 brief.
- **Shared knowledge (future, Layer 3+)**: separate substrate (same schema, different DB file) at user-level location. Promotion is the bridge. Build after Howie.
- The "replace SQLite with graph" commitment has SOFTENED to "extend SQLite; migrate the shared layer later only if traversal performance bites."

**Build order:**
1. Framework memory substrate (Phase 4 — handoff ready)
2. Apply to Howie project (Howie validates the framework)
3. Cross-project shared knowledge layer (after Howie)

**Out of scope:**
- A2A protocols (settled out)
- Replacing per-project SQLite (no longer planned)
- Building shared layer this round (deferred to after Howie)

### Next Up (Phase 4)

- Open new session, paste handoff prompt from `docs/dispatches/phase4-build-handoff.md`
- Build Stack A′ (SQLite + sqlite-vec + sentence-transformers + FastMCP) with three design-for-future additions:
  - `project_id` field on every sourced assertion
  - Portable `source_ref` URI form: `project://<project_id>/<path>#L<start>-L<end>`
  - `scope` parameter in MCP tool signatures (only `"local"` implemented this round)
- Acceptance test: 5-step round-trip with `assert_fact`, `search_semantic`, `get_source` against a real transcript
- ~2 hours of focused work

### Files created/modified this session

**New durable artifacts:**
- `docs/dispatches/phase1-connection-facilitators-prompt.md` (this session resumed pre-existing work)
- `docs/dispatches/phase3-tooling-prompt.md`
- `docs/dispatches/phase4-build-handoff.md`
- `docs/research/phase1-connection-facilitators.md`
- `docs/research/phase3-tooling-decision-brief.md`

**Auto-memory updates (in `~/.claude/projects/<slug>/memory/`):**
- `project_memory_architecture_framing.md` — substantially expanded across this session
- `project_a2a_out_of_scope.md` — created
- `MEMORY.md` — index updated

## Open Advisories

### From the Phase 3 / Phase 4 deliberation
1. The new `memory/` Python package name may collide with the existing `memory/` markdown directory (Layer 3 curated knowledge). Phase 4 session should confirm and possibly rename to `framework_memory/` or `assertion_store/`.

### From the ADR-0013 implementation review (REV-20260512-033416)
1. f-string DDL pattern in `init_db.py:290` and `ingest_token_usage.py:_ensure_token_columns` — not exploitable today (hardcoded values); whitelist guard is hygiene.
2. Cache field split: `discussions.total_cache_tokens` collapses cache_read (0.10× input rate) and cache_create (1.25× input rate). Add `total_cache_read_tokens` + `total_cache_create_tokens` if cost analysis at the discussion grain matters.
3. `_attribute` is O(M×D), undocumented; emit warning on multi-window match.
4. `--since` filters AFTER parsing; mtime fast-path possible.
5. Migration list duplicated between `init_db.py` and `ingest_token_usage.py:_ensure_token_columns` — silent-drift risk on future column adds.
6. `state.json` shows `status=complete` while SQLite is authoritative (`status=closed`). Two state systems; reconcile or document.
7. ADR-0013 (framework scope) is a propagation candidate for `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md` — not queued.
8. `tests/test_close_discussion_rollup.py` replicates Step 3b SQL locally rather than driving `close_discussion()` end-to-end. A future SQL refactor would not break the tests; higher-fidelity test is a follow-up.

### Pre-existing defects (separate scope)
1. `scripts/close_discussion.py` has two non-fatal pipeline warnings: `surface_candidates()` kwarg drift, `compute_effectiveness` import. Surfaced in DISC-20260512-025323; not addressed in the ADR-0013 work.

### Carried from v3.4.0 work (still relevant)
1. Monitor homogenization via uniqueness scores over next 5–10 reviews
2. Consider varying Domain Lens framing verb per agent
3. Pipeline scripts: `surface_candidates()` and `compute_effectiveness()` have API drift (deferred R5.4) — same as Pre-existing defects #1 above

## Key Decisions (Recent)

- **2026-05-12**: ADR-0013 (Token-efficiency telemetry via post-hoc JSONL ingest) — implemented, reviewed (REV-20260512-033416, verdict request-changes → 4 blocking findings addressed → ready to commit). JSONL ingester is system of record; per-turn columns + view `v_token_efficiency`; cost computed at analysis time via `config/model_pricing.yaml`.
- **2026-05-11**: Memory architecture stabilized. Sources canonical, sourced assertions as atomic unit, Stack A′ as substrate, cross-project sharing via promotion-to-shared-layer.
- **2026-05-10**: A2A protocols dismissed for internal framework coordination (see `~/.claude/projects/<slug>/memory/project_a2a_out_of_scope.md`).

## Coordination Notes

- **ADR-0013 work landed in this session** (telemetry stack: `metrics/evaluation.db` schema, `scripts/close_discussion.py` Step 3b, new `scripts/ingest_token_usage.py`, `config/model_pricing.yaml`). Phase 4 memory-substrate build work is architecturally orthogonal (touches `data/memory.db`, NOT `metrics/evaluation.db`) — no coordination required for the next Phase 4 session.

## Blockers

- (none)

---

## Previous Session (2026-04-11 22:00Z)

**Status:** Framework cross-project sync complete. Pending /review and commit.
**Branch:** `feature/project-analysis-backport`

### Completed in v3.4.0 build (DISC-20260405-235356-build-v340-release)
- W1: Push Notifications section in CLAUDE.md + scripts/notify.py + .env.example
- W2: Solution-path KB — pre_build_search.md rule, project-profile-template.md, TAXONOMY.md, _self.md, ADR-0011, command/rule edits
- W3: Known-Broken Approaches section in regression-ledger.md
- W4: Educator agent reframe for decision-maker audience (ADR-0012)
- W5: Advisory resolution — PHILOSOPHY.md Values+Domain Lens terminology, facilitator section ordering, extract_findings.py verified
- W6: Version bump to 3.4.0, doc sync (FRAMEWORK_SPECIFICATION.md, both HTML presentations)

### Backported from agentic-journal
- facilitator.md: "How you dispatch matters" framing, suppress confirmations, domain reframe, UI dispatch trigger, multi-instance pattern analysis
- docs-knowledge.md: Cross-domain discovery chains, tool use protocol, Future Reader Impact, newcomer advocacy, documentation-not-a-gate
- educator.md: Three-Layer Knowledge Model, two-dimensional mastery tiers, strategic knowledge emphasis, regression ledger integration
- review.md: Step 7d PR comment posting (--comment flag)
- build_module.md: Expanded Pre-Build Enrichment, spec completion timing note
- plan.md: Restructured Prior Art Lookup with fallback logic, spec completion tracking fields

### Outstanding from that session
- `/review` all changed files (still uncommitted as of 2026-05-11)
- Address blocking findings
- Commit and push the v3.4.0 sync work
- Phase 2 items from journal port (capability protection, UX review protocol, /status command)

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
