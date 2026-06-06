---
discussion_id: DISC-20260606-041937-telemetry-oversight-spec-review
started: 2026-06-06T04:19:51.987810+00:00
ended: 2026-06-06T04:28:52.817214+00:00
agents: [architecture-consultant, facilitator, performance-analyst, qa-specialist, security-specialist]
total_turns: 6
---

# Discussion: DISC-20260606-041937-telemetry-oversight-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-06T04:19:51.987810+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Add a telemetry & oversight component to the framework, starting from toolbeltross/rh-telemetry + rh-claude-framework and ~10 comparable projects, baked into the template to help improve the framework. Center of gravity refined with the developer to: VISIBILITY (the telemetry is captured but not visible; Ross's dashboard is the inspiration) + catching where AGENTS FAIL or WASTE TOKENS.
- **Files/scope**: New Telemetry & Oversight component (3 layers: A=failure/waste analyzer over existing evaluation.db + sealed transcripts, B=unified viewer with tech deferred, C=ntfy oversight digest feeding /meta-review). Builds on ingest_token_usage.py, model_pricing.yaml, evaluation.db views, notify.py, init_db.py migrations. Spec: SPEC-20260605-211756-telemetry-oversight.md.
- **Developer-stated motivation**: 'I know I have telemetry baked, but it isn't super visible.' Wants to SEE it and catch agent failures/token waste; bake into the template hub so derived projects inherit it; feed a framework self-improvement loop.
- **Explicit constraints**: Compute per-tier dollar cost (developer approved) as a REFINEMENT of ADR-0013 (compute-not-store), not a reversal. Dashboard technology deliberately deferred until the signal layer exists. Framework evolution → Steward gate + developer approval (Principle #7). Keep lightweight (ADR-0013 rejected building an observability platform; a prior /status dashboard scored 16/25 DEFER). KNOWN-BROKEN: never inject changing metrics into agent context (KV-cache invalidation, per self-improving-coding-agent memory). Attribution required (rh-telemetry MIT, credit Ross); do NOT bundle Phoenix (ELv2).

---

## Turn 2 — architecture-consultant (critique)
*2026-06-06T04:24:38.815580+00:00 | confidence: 0.84*
*tags: architecture, blocking, adr-0013, cost-attribution, reuse*

VERDICT: APPROVE-WITH-CHANGES (0.84).
BLOCKING - per-turn tier data gap: R-A2 per-turn dollar cost depends on per-turn model-tier tags that NO code populates today. ingest_token_usage parses message.model then DISCARDS it; _update_tagged_turns is a dormant hook returning 0; only discussion-level totals are written. Coverage would be ~0pct on real data, contradicting R-A4 day-one value. Resolve before build: (i) re-scope to discussion/agent-inferred tier (least complex), or (ii) extend pipeline to persist per-turn model from the already-parsed JSONL message.model field (the real fix, own acceptance criterion).
ADVISORY: failure signals R-A1.1-1.3 actually live in transcript JSONL, not events.jsonl/turns - reorder the source list to lead with transcripts for failures, reserve events/turns for cost; degrade gracefully when transcript absent; keep trigger batch-only in Phase 1. Migration ALTER list already duplicated across init_db and ingest_token_usage - analyzer should call init_db() rather than add a 3rd copy. Make transcript-parser reuse (discover_session_dirs/parse_session_dir) a HARD constraint, not optional.
STRENGTHS: refine-not-reverse ADR-0013 framing is architecturally correct - an amendment, not a superseding ADR (note ADR-0013 is still status=proposed, so build ADR should ratify or cleanly reference it); KV-cache constraint correctly elevated to hard constraint; coverage-pct honesty is the right antidote to fabricated precision; 3-layer boundaries clean with correct dependency direction; phasing disciplined.

---

## Turn 3 — security-specialist (critique)
*2026-06-06T04:24:53.156355+00:00 | confidence: 0.87*
*tags: security, blocking, prompt-injection, ntfy, trust-boundary*

VERDICT: APPROVE-WITH-CHANGES (0.87). Developer-local tool; main threats: analyzer ingests attacker-influenceable transcript content; ntfy.sh is a public relay with topic slug as only auth; a future FastAPI viewer must stay local.
BLOCKING 1 - prompt-injection via /meta-review (R-C2): transcript text can be adversarially shaped (tool output, pasted content, web fetches). Content flowing to /meta-review must be limited to schema-constrained fields (failure-class enum, counts, cost numbers) - NEVER free-text excerpts. This is a SEPARATE control from the KV-cache rule (which the spec covers); the meta-review consumption path is not covered.
BLOCKING 2 - ntfy digest content (R-C1): redaction alone is insufficient. Add a STRUCTURAL constraint: digest body assembled from DB-level aggregates only (enum + counts + estimated spend + coverage pct); no string sourced from transcript/event content. Otherwise transcript data can transit ntfy.sh in cleartext.
ADVISORY: DDL uses f-string in init_db (safe only while names hardcoded) - mandate hardcoded table/column names, never config/runtime-derived. Reuse the _is_inside_projects_root symlink/traversal guard for any new file ingestion. If FastAPI viewer is built: bind 127.0.0.1 only (not 0.0.0.0), no wildcard CORS (same-origin avoids CORS entirely), generic errors only, auth if any non-read endpoint - carry into the R-B3 ADR. Pin Chart.js to exact version or vendor it (no /latest CDN float). Add a redact_secrets test for short tokens and NTFY_TOPIC-shaped strings.
STRENGTHS: notify.py topic-slug confidentiality is exemplary (never logged even on error, strict regex); KV-cache constraint correctly load-bearing; compute-not-store removes cost-at-rest risk; redact-before-surface is the right location; idempotency limits replay DoS.

---

## Turn 4 — qa-specialist (critique)
*2026-06-06T04:25:08.854046+00:00 | confidence: 0.87*
*tags: qa, blocking, testability, determinism, injectable-seam*

VERDICT: APPROVE-WITH-CHANGES (0.87). Blocking items are spec gaps, not design flaws - each fixable with 1-3 sentences in acceptance criteria. Reference model already in repo: test_ingest_token_usage.py (monkeypatched CLAUDE_PROJECTS_ROOT/PROJECT_ROOT/DB_PATH, deterministic fixtures, honest-NULL asserts).
BLOCKING 1 - injectable seam: ~/.claude/projects path must be an injectable constant/param (like CLAUDE_PROJECTS_ROOT) so no test reads the live dir; without it the transcript path is uncoverable and 80pct is unreachable. Declare the transport-fidelity boundary explicitly (unit tests cover parsing; live path discovery not under pytest).
BLOCKING 2 - migration test strength: criterion must assert columns EXIST after migrate via PRAGMA table_info (not merely no-raise; the broad except swallows real failures). Add a 4th scenario: existing table missing one new field (partial prior migration).
BLOCKING 3 - undefined contracts: retry-loop hash normalization is undefined (whitespace/JSON key order/tool-version suffix); dedupe key unspecified (INSERT OR IGNORE vs UPDATE, assert stable row count across 2 runs); ranking behavior for tier-unknown failures unspecified (must appear with marked unknown/zero cost, not silently absent).
BLOCKING 4 - determinism: time thresholds for orphan/retry detection must be injectable params; tests use synthetic timestamps, NO time.sleep, NO global datetime mock.
ADVISORY: fixture inventory (retry pattern; dispatch-without-completion; corrupt/truncated JSONL line; empty events.jsonl; fresh empty DB; sparse 1-discussion DB). Coverage-pct denominator should be TOKENS not turns. Add parameterized-SQL injection test. Window-boundary tests (T, T-1, T+1). Add init_db regression-ledger entry at commit time.
STRENGTHS: viewer deferral keeps Layer A independently testable; compute-not-store makes cost testing pure-functional; graceful-no-op explicit; 3-scenario migration is the right base set.

---

## Turn 5 — performance-analyst (critique)
*2026-06-06T04:25:23.513482+00:00 | confidence: 0.88*
*tags: performance, blocking, watermark, incremental, scalability*

VERDICT: APPROVE-WITH-CHANGES (0.88). Current scale fine (57 events.jsonl/644KB; 1429 transcript JSONL/430MB). SQLite is the right store at projected scale.
BLOCKING - watermark/incremental: R-A4 idempotency dedupes WRITES but not READS - full re-scan is O(corpus) every run, so cost grows with total history not with what changed (430MB read each run today, GBs for larger derived projects). Add a high-water-mark: store last_analyzed per discussion (a telemetry_run_state row or a column on discussions; discussions already has closed_at+status) and query WHERE closed_at > watermark. Keep a --full-rescan flag for the one-time retroactive run (mirrors the existing --since flag). Decide this BEFORE build.
ADVISORY: for cost attribution, JOIN the already-attributed turns table + model tag rather than re-parsing raw JSONL (avoids the O(messages x discussions) scan that ingest_token_usage._attribute hints at); if per-turn model tags are sparse, document the coverage limit rather than re-parsing everything. Stream transcript JSONL line-by-line (follow parse_session_dir), do NOT load-all like ingest_events.py - matters for large transcript files. DECLINE the close_discussion seal-time trigger (adds latency to a 7-step synchronous hot path); the watermark makes the next batch pick it up anyway - close Open Decision 2 as batch+watermark. Compute coverage-pct in the SAME single-pass SQL aggregation (conditional COUNT), not a 2nd pass.
STRENGTHS: compute-not-store avoids volatile-pricing schema coupling and makes recompute free; reuse-dont-duplicate prevents a parallel cost DB; model_pricing.yaml as in-memory lookup is cheap; isolating the parser behind one function gives one-file-patch resilience.

---

## Turn 6 — facilitator (synthesis)
*2026-06-06T04:28:52.817214+00:00 | confidence: 0.86*

## Request Context
- **What was requested**: Add a Telemetry and Oversight component to the framework template - make already-captured telemetry VISIBLE and catch where agents FAIL or WASTE TOKENS - inspired by toolbeltross/rh-telemetry + ~10 comparable projects, baked into the hub to feed framework self-improvement.
- **Files/scope**: SPEC-20260605-211756-telemetry-oversight.md. 3 layers: A=failure/waste analyzer + per-tier dollar cost over existing evaluation.db + sealed transcripts; B=unified viewer (tech deferred); C=ntfy oversight digest feeding /meta-review.
- **Developer-stated motivation**: telemetry is captured but not visible; wants to see it and catch agent failures/token waste; template-is-the-hub so derived projects inherit; feed a self-improvement loop.
- **Explicit constraints**: per-tier dollar cost as a REFINEMENT of ADR-0013 (compute-not-store), not reversal; dashboard tech deferred; keep lightweight (no observability platform; prior /status dashboard 16/25 DEFER); KNOWN-BROKEN never inject changing metrics into agent context (KV-cache); attribution required (rh-telemetry MIT, credit Ross), no Phoenix (ELv2).

## Synthesis
Four-specialist panel (architecture, security, qa, performance) unanimously APPROVE-WITH-CHANGES on the spec. 8 BLOCKING findings, all spec gaps rather than design flaws, all resolved in this revision (status draft->reviewed):

1. ARCH (deepest): R-A2 per-turn dollar cost assumed per-turn tier tags that NO code populates today - ingest_token_usage parses message.model then discards it. Resolved via R-A2.0: extend the pipeline to persist per-turn model (the already-parsed field); coverage starts low and rises honestly; day-one value carried by the R-A1 failure signals, not by dollar coverage.
2-3. SECURITY: two distinct prompt-injection/exfiltration paths beyond the KV-cache rule - the /meta-review hand-off (R-C2.1) and the ntfy digest (R-C1.1) must both be limited to schema-constrained aggregates, never free-text transcript content. Structural constraint, additional to redaction.
4-7. QA: injectable transcript seam (reuse discover_session_dirs/parse_session_dir, no live ~/.claude in tests); migration test must PRAGMA-assert columns + partial-migration scenario; define retry-hash normalization, dedupe key, and unknown-tier ranking behavior; injectable time thresholds (no sleep/global mock). All folded into R-A5 + strengthened acceptance criteria.
8. PERF: full re-scan is O(corpus) (430MB/1429 files today) - R-A4 adds a watermark + --full-rescan; Open Decision 2 resolved by DECLINING the close_discussion seal-time trigger (7-step synchronous hot path).

Strong cross-panel agreement on the spec's instincts: refine-not-reverse ADR-0013 is the correct, least-complex instrument (amendment, not superseding ADR; note ADR-0013 is still status=proposed); KV-cache constraint correctly load-bearing; coverage-pct honesty mirrors the log-skipped-runs-honestly ethic; reuse-dont-duplicate and the 3-layer boundaries are clean; phasing keeps Layer A independently shippable.

Recommendation: spec is approvable for building Layer A now, with the viewer (R-B3) technology decided after Layer A defines the data. Advisories carried to /build_module are recorded in the spec Spec Review Summary. Next gate after developer approval: Steward review (framework evolution / Principle #7) before /build_module.

---
