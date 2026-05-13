# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-05-12 (Phase 4 substrate APPROVED via re-review REV-20260512-195841; pending commit + push)

## Current Task

**Status:** Phase 4 sourced-assertion substrate complete end-to-end. Two reviews: REV-20260512-132622 (request-changes, 10 blocking findings) → 5-step fix sequence → REV-20260512-195841 (approve, 0 blocking, 8 low advisories). 27 tests at 97% coverage, all passing. ADR-0014 written. CLAUDE.md updated (Directory Layout + Memory Substrate section + Known Limitations). FRAMEWORK_CHANGELOG.md propagation entry added. Substrate class refactor unlocked transport-agnosticism for Howie / Insight Journal / future CLI use. Quality gate passes 5/5 excluding pre-existing notify test failure (unrelated to Phase 4). **Next**: commit (in progress) → ask developer before push.
**Branch:** `feature/sourced-assertion-substrate` (off `feature/project-analysis-backport` HEAD)

### In Progress

- **Memory architecture exploration (Phases 1–4)**
  - Phase 1 (broad survey) — complete; report at `docs/research/phase1-connection-facilitators.md`
  - Phase 2 (sanity check on alternatives) — complete; integrated into the architecture framing memory
  - Phase 3 (tooling research + decision brief) — complete; report at `docs/research/phase3-tooling-decision-brief.md`
  - Phase 4 (build) — **substrate built; canonical MCP test ROUND-TRIP VALIDATED 2026-05-12.**
    - Files created: `assertion_store/__init__.py`, `assertion_store/substrate.py`, `assertion_store/embeddings.py`, `mcp_server/__init__.py`, `mcp_server/server.py`. Modified: `requirements.txt`, `.mcp.json`, `mcp_server/server.py` (thread-local fix this session — uncommitted).
    - Smoke test (direct Python calls bypassing MCP) PASSED end-to-end: 3× `assert_fact`, semantic match on paraphrased query (distance 0.762 vs 1.2+ for unrelated), `get_source` round-trip via portable URI, scope rejection, bad URI rejection.
    - All three Phase 4 modifications validated under BOTH smoke test AND MCP transport: project_id flows through writes + filters reads; source_ref canonicalised to `project://<id>/<rel>#L<a>-L<b>` URI; scope parameter present in MCP signature with shared/list rejection.
    - Real transcript staged at `sources/2026-05-12_discussion.md` (copied from DISC-20260512-025323-token-efficiency-telemetry).
    - Canonical test handoff at `docs/dispatches/phase4-canonical-test-handoff.md`.
    - **Canonical test outcome (2026-05-12):**
      - Step 0 ✓ Three MCP tools loaded; schemas match handoff spec; docstrings carry the substrate's framing (sourced assertion, suchness primitive, scope futurity).
      - Step 1 ✓ Three claims identified with line ranges (recorded below).
      - Step 2 ✗ initial / ✓ after fix — three writes failed under MCP transport with `SQLite objects created in a thread can only be used in that same thread`; thread-local fix applied to `mcp_server/server.py` mid-test; all three writes succeeded after `/mcp` reconnect. fact_ids = 1, 2, 3. URI canonicalisation verified (bare path-with-fragment rewritten to full `project://agentic-framework-template/...` on the server).
      - Step 3 ✓ `search_semantic` on a deliberately abstract paraphrase of Claim 2 returned the correct top hit at distance **1.113**, gap-to-runner-up **0.20**. Moderate band (1.0–1.4), not strong (<1.0) — paraphrase used minimal lexical overlap. Ordering correct.
      - Step 4 ✓ `get_source` returned [sources/2026-05-12_discussion.md:156](sources/2026-05-12_discussion.md#L156) verbatim with markdown emphasis preserved (texture-preservation working).
      - Step 5 ✓ Suchness gap analysed: symbolic form preserved core fact + grouping qualifier + framework attribution; lost "all three converge" consensus framing, the secondary-metric structural pair, numbered-list context, typographic emphasis, "ratio" vs "signal" type-noun distinction. Architecture commitment validated: locate → resurface → see-the-gap.
    - **Three claims recorded (audit trail + future-query test data):**
      1. fact_id=1: `ccusage, token-dashboard, and Claudetop` → `all parse` → `Claude Code transcript JSONL to compute token usage` @ L54-L56
      2. fact_id=2: `blocking findings per 1K output tokens` → `is` → `the framework's primary efficiency signal, grouped by command_type` @ L156
      3. fact_id=3: `facilitator synthesis` → `recommends` → `adding tokens_in, tokens_out, cache_read_tokens, and cache_create_tokens columns to the turns table` @ L183-L187
    - **Fix applied to `mcp_server/server.py` (uncommitted, included in /review scope)**: replaced module-level `db = init(DB_PATH)` with `_get_db()` helper using `threading.local()`. Each FastMCP worker thread opens its own SQLite connection on first use; `substrate.init()` is idempotent (`CREATE … IF NOT EXISTS`), so per-thread opens are safe. Three call-site edits in `assert_fact` / `search_semantic` bodies; module docstring updated. Validated end-to-end by Step 2 retry succeeding.
    - **Next**: developer confirms → `python scripts/quality_gate.py` → `/review feature/sourced-assertion-substrate` → address blocking findings → commit.

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

### From the Phase 4 re-review (REV-20260512-195841, 2026-05-12)
All 10 prior blocking findings from REV-20260512-132622 verified resolved. 8 low-severity advisories remain (none block commit):

**New this round (4 low)**:
1. `get_source` with reversed line-range (`#L10-L3`) silently returns empty string via Python slicing — undocumented (qa).
2. ADR-0014 Consequences claim a `# TODO(phase5)` comment exists in code for the vector search post-filter; code lacks it — small ADR/code drift (perf).
3. `mcp_server/__init__.py` docstring still single-line vs `assertion_store/__init__.py`'s 10-line — adopter import-discovery impoverished (docs).
4. Semantic-distance calibration insight (ordering matters more than absolute distance) captured only in `docs/dispatches/phase4-canonical-test-handoff.md`, not durably in ADR/CLAUDE.md/memory (docs).
5. Micro: `embed("")` warm-up may be marginally safer as `embed("warmup")` if `all-MiniLM-L6-v2` has degenerate behaviour on empty input (perf).

**Carry-forward (3 low, deferred)**:
6. f-string DDL pattern in `substrate.py` — not exploitable today (`EMBEDDING_DIM` is a literal int), but pattern violates REVIEW.md Rule 10 (security).
7. Three new deps still using `>=` not `==` (`sqlite-vec`, `sentence-transformers`, `fastmcp`) — deferred to ship per prior review (security).
8. `from __future__ import annotations` × FastMCP introspection still unverified post-refactor (arch).

### Pre-existing defects flagged this session (NOT Phase 4)
1. **`tests/test_notify.py::TestSendNotification::test_no_topic_returns_false` fails under full-suite ordering** — `notify.py` calls `_load_env()` at module import, loading `NTFY_TOPIC` from `.env` into `os.environ` before `setup_method`/`@patch.dict` run. Test passes in isolation. Pre-existing (test untouched since v3.4.0). Workaround used this session: `quality_gate.py --skip-tests --skip-coverage` (Phase 4 tests verified independently). **Fix needed**: either move `_load_env()` into the function bodies (lazy) or have the test force-reimport `notify` with `sys.modules.pop` before `@patch.dict`.
2. **`scripts/quality_gate.py` regression-guard parser was off by one column** (expected 5; ledger format has 6: File, Bug Description, Root Cause Class, Fix Date, Test File, Test Function). My Phase 4 entries are the first real ledger entries this project has ever had — the drift had never been exercised. **FIXED** in this commit (one-line fix to `_parse_regression_ledger`).

### From the Phase 3 / Phase 4 deliberation
1. ~~The new `memory/` Python package name may collide with the existing `memory/` markdown directory.~~ **Resolved 2026-05-12**: Python package will be named `assertion_store/`. Phase 3 brief code references must be adapted (`from memory.substrate import …` → `from assertion_store.substrate import …`).

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

- **2026-05-12 (Phase 4 canonical test)**: Substrate connection model = one SQLite connection per worker thread via `threading.local()` (not `check_same_thread=False`+lock). Rationale: thread-local is more correct under FastMCP's thread model; `substrate.init()` is already idempotent so per-thread DDL is a no-op; no lock contention path to reason about. Validated by post-reload Step 2 retry succeeding and Steps 3–5 completing cleanly.
- **2026-05-12 (Phase 4 pre-build)**: Python package name = `assertion_store/` (not `memory/`, to avoid collision with the curated-knowledge directory). Phase 4 work to live on a new branch off `feature/project-analysis-backport` to isolate substrate work from v3.4.0 sync residue and the now-merged ADR-0013 telemetry.
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
