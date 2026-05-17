---
spec_id: SPEC-20260516-045622
title: "Phase 1 — Wire substrate into /review synthesis (first in-framework consumer)"
type: spec
status: deferred
risk_level: medium
intake_ids: []
discussion_id: DISC-20260516-045815-phase1-substrate-review-consumer-spec-review
reviewed_by:
  - qa-specialist
  - architecture-consultant
  - security-specialist
deferred_at: 2026-05-16
deferred_reason: |
  Baseline measurement (Track B, 2026-05-16) showed cache utilization at
  99.973% and discovery cost <5% of output tokens. The cost-reduction
  rationale that originally justified Phase 1 does not survive the data.
  The quality-grounds reframe (semantic retrieval with provenance) is
  plausible but speculative — no evidence yet that it would measurably
  improve review quality. Building Phase 1 against synthetic /review
  consumption would land the substrate's first integration in a low-stakes
  context that doesn't exercise the design under real load.

  Deferred until a real consumer with genuine workload drives the
  requirements. Most likely driver: Howie (family-wiki research project,
  primary derived-project roadmap per project_active_landscape memory).
  When Howie spawns and starts accumulating sourced assertions about
  Scots Worthies, that is the real Phase 1.

  The substrate itself remains validated; ADR-0014 stands. The Prime
  Objective (ADR-0015) sets the constraint that whatever consumer drives
  Phase 1 must satisfy. The propagation seam through shared-memory works.
  Deferring is "park the gun loaded," not "throw it away."
completed_at:
completed_commit:
---

## Goal

Give the sourced-assertion substrate (`assertion_store/` + `mcp_server/`, built in Phase 4 / ADR-0014) its first real in-framework consumer: at `/review` closure, emit a sourced assertion to the substrate for every **blocking** finding, cited to the review report's exact location. After this lands, the framework's own multi-agent review process leaves a queryable trail of decisions that future reviews (and Howie) can semantically retrieve and resurface.

This is Phase 1 of the framework memory evolution plan. It is the validation phase before Phase 2 commits to designing more primitives.

## Context

### What's in place

- The substrate is built and unit-tested (Phase 4, ADR-0014). Three primitives: `assert_fact`, `search_semantic`, `get_source`. Schema: `(project_id, subject, predicate, object, source_ref, framing, …)` with vector index on assertions.
- The MCP transport (`mcp_server/server.py`) exposes those primitives as MCP tools registered under `agent-memory` in `.mcp.json`.
- Phase 0 (SPEC-20260515-053533, committed at `a57f3c1`) restored the Layer 1 → Layer 3 promotion pipeline. Phase 1 stacks on top of that commit on `feature/sourced-assertion-substrate`.

### Why now

The substrate has no in-framework consumer. The architectural commitment is *"memory primitives only prove themselves through consumption"* (see `docs/plans/framework-memory-evolution-2026-05.md`). Continuing to Phase 2 (design four Howie primitives) without exercising the substrate under real workflow load means accumulating design assumptions on top of untested foundations.

### Real-world signal already surfaced

In the current Claude Code session that drafted this spec, the `agent-memory` MCP server registered in `.mcp.json` reported "still connecting" at session start and its tools (`assert_fact`, `search_semantic`, `get_source`) never loaded into the toolset. The substrate IS reachable in-process via the `Substrate` class. This is itself a Phase 1 finding: **MCP availability is intermittent across Claude Code sessions and cannot be assumed at runtime**. ADR-0015 (new in this spec) records the consumer transport-selection contract.

### Spec-review revisions (DISC-20260516-045815)

This spec was reviewed by qa-specialist (0.84), architecture-consultant (0.86), and security-specialist (0.87). Five blocking findings were folded in:
- **arch-B1**: emission moved from `.claude/agents/facilitator.md` (agent instruction) to `scripts/emit_assertions_from_review.py` (script invoked by `close_discussion.py`). Rationale: matches the existing closure-pipeline pattern (`extract_findings.py`, `mine_patterns.py`, etc.), unit-testable, no agent-substrate coupling.
- **arch-B2**: extend the seal — `close_discussion.py` now chmods `docs/reviews/REV-*.md` read-only after emission completes, alongside the existing seal of `events.jsonl` and `transcript.md`.
- **qa-F1**: distance threshold relaxed to `< 2.0` (canonical-test parity) plus a rank-based assertion (`hits[0]["subject"] == expected`) for stability.
- **qa-F2**: synthetic secret fixture specified as `AKIAIOSFODNN7EXAMPLE` (AWS's documented example key — matches `AKIA[0-9A-Z]{16}`, publicly known, not a real secret).
- **qa-F3**: discussion-ID-to-frontmatter ordering pinned — the discussion ID is written to the report frontmatter BEFORE emission, so emission always sees final line layout.
- **security-F1+F2**: sanitisation happens at the `assert_fact` call site in `scripts/emit_assertions_from_review.py`, scanning subject/predicate/object independently against the 12-pattern set. On any match, refuse the emission and log metadata only (severity, file:line, pattern-class — no triple content).

### Prior art

- `memory/projects/_self.md` — one Solution Path: `[framework/promotion-pipeline]` (Phase 0). No prior `[framework/substrate-consumer]` entries.
- `memory/bugs/regression-ledger.md` — three substrate-side regressions on the MCP transport (thread-local, path traversal, URI canonicalisation, all 2026-05-12) and Phase 0 (2026-05-15). The substrate has a track record of caught security/lifecycle issues; Phase 1 should not weaken those guards.
- `docs/adr/ADR-0014-sourced-assertion-memory-substrate.md` — substrate adoption ADR. Source-ref URI format, project-id tagging, `scope="local"` commitment.
- `docs/adr/ADR-0006-review-md-rules.md` — REVIEW.md rule injection ADR. Sets the precedent that `/review` is a legitimate hook point for cross-cutting concerns.
- `docs/reviews/REV-20260515-221223.md` — Phase 0 review. Open advisories carry forward (arch-F2 `/promote --list-promoted`, arch-F3 canary content-hash, arch-F5 swallow-and-warn ADR). Phase 1 review must include these in its "Open Advisories from Prior Phase" section.

## Requirements

### R1 — Substrate emission at closure
After the facilitator writes the synthesis event in `/review`, `close_discussion.py` invokes `scripts/emit_assertions_from_review.py` as a new closure-pipeline step. The script reads the review report, parses blocking findings, and writes one sourced assertion per blocking finding via the substrate.

The emission step runs **before** the seal step (Step 9 in close_discussion.py). The seal step extends to include `docs/reviews/REV-*.md` for this review.

### R2 — Source-ref shape and durability
Each assertion's `source_ref` must point at the review report file with a line range covering the finding's location in the report:

```
project://<project_id>/docs/reviews/REV-YYYYMMDD-HHMMSS.md#L<a>-L<b>
```

The review report is canonical. The events.jsonl is internal capture and is NOT the source ref. After emission, the review report is sealed read-only (per the close-discussion seal extension in R1), enforcing Suchness preservation — `get_source` always returns the exact text emitted assertions cited.

### R3 — Blocking-only filter
Only findings classified as blocking (severity=critical/high/blocking per the review report's "Required Changes Before Merge" section) are emitted. Advisory, info, and speculative findings stay in the review report only.

### R4 — Sanitisation at the assert_fact call site
`scripts/emit_assertions_from_review.py` MUST scan each assertion's `subject`, `predicate`, and `object` strings independently against the 12-pattern set from `.claude/hooks/pre-tool-use-validator.sh` / `validate_tool_use.py` BEFORE invoking `assert_fact`. The PreToolUse hook only fires on Write/Edit tool calls and does NOT protect in-process SQLite writes — therefore the scan must happen at the call site.

On any pattern match in any of the three triple fields:
- The assertion is NOT written to the substrate.
- A captured event with intent `evidence` and tag `assertion-refused,pattern-class:<class>` is appended to the discussion's events.jsonl.
- The event content is metadata only: severity, file:line, the matched pattern class. NO triple content, NO matched substring, NO finding text.

This is the refuse policy (not mask). Justification: mask risks incomplete redaction (partial token leakage) which, for structured token formats like `AKIA*`/`ghp_*`/`sk-ant-*`, can identify issuer and account tier even with 80% redacted. In the single-user local-DB context, refuse is correct.

### R5 — Hook location: wrapper script invoked by close_discussion.py
The substrate-emission step lives in a new script `scripts/emit_assertions_from_review.py`, invoked by `close_discussion.py` as a new closure-pipeline step (between current Step 8 "Check for pending promotion candidates" and Step 9 "Set files to read-only"). The facilitator agent definition is NOT modified.

Rationale (per arch-B1):
- Matches existing pattern (extract_findings.py, mine_patterns.py, surface_candidates.py, compute_agent_effectiveness.py are all scripts invoked deterministically by close_discussion.py).
- Unit-testable as a callable function in addition to the closure-pipeline integration test.
- No coupling between facilitator agent and substrate API — derived projects that fork the facilitator inherit no substrate dependency.
- Failure of the emission step is non-fatal (consistent with other closure-pipeline steps); a swallow-and-warn pattern is acceptable here per Phase 0 C5 because the regression test is the structural canary.

### R6 — Transport-selection contract (codified in ADR-0015)
`scripts/emit_assertions_from_review.py` resolves the substrate transport at runtime:
1. If the `agent-memory` MCP server is reachable, use it (call `assert_fact` via MCP).
2. Otherwise, construct a `Substrate` instance in-process and call its `assert_fact` method directly.

Either path produces an identical end-state in the substrate DB. The route taken is tagged on the captured emission event (`route:mcp` or `route:substrate-direct`), making the choice observable and queryable.

ADR-0015 ("Substrate consumer transport-selection contract") records this as a framework-scoped commitment that derived projects (Howie, Insight Journal) inherit.

### R7 — Test coverage
A regression test (`tests/test_review_substrate_emission.py`) tagged `@pytest.mark.regression`. Test cases:

**R7.a — Two blocking findings emit two assertions (happy path)**
- Fixture: review report with 2 blocking + 1 advisory finding.
- Invoke `emit_assertions_from_review(report_path, substrate)` with an in-process Substrate against `tmp_path`.
- Assert: exactly 2 assertions in the substrate (advisory excluded).

**R7.b — Semantic retrieval works**
- After R7.a, call `Substrate.search_semantic(paraphrased_query_for_finding_1, k=5, scope="local")`.
- Assert: at least 1 result, `hits[0]["subject"] == expected_subject_for_finding_1`, and `hits[0]["distance"] < 2.0` (canonical-test parity per `tests/test_mcp_server.py:TestRoundtrip`).

**R7.c — get_source returns verbatim text**
- For each emitted assertion's `source_ref`, call `Substrate.get_source(source_ref)`.
- Assert byte-equality with the review report file contents at the cited line range. Includes markdown emphasis (Suchness preservation per ADR-0014).

**R7.d — Sanitisation refusal path**
- Fixture: review report with 2 blocking findings, one of which contains `AKIAIOSFODNN7EXAMPLE` (AWS's documented example key, matches `AKIA[0-9A-Z]{16}`, not a real secret) in its description.
- Invoke emission.
- Assert: 1 assertion in the substrate (the clean one), refused-event captured for the secret-containing one with tag `assertion-refused,pattern-class:aws-access-key`, captured-event content does NOT include the matched substring.

**R7.e — Zero-blocking-findings edge case**
- Fixture: review report with 0 blocking + 2 advisory findings.
- Invoke emission.
- Assert: 0 assertions in substrate, no error, no refused-event (nothing was attempted).

**R7.f — Fallback transport tag is captured**
- Mock the MCP dispatch to raise `ConnectionError`.
- Invoke emission against the R7.a fixture.
- Assert: assertions still land via Substrate-direct fallback; captured event has tag `route:substrate-direct`.

Test isolation: each test uses `tmp_path` + `Substrate(db_path=tmp_path/"test.db", project_id="test", source_roots=[tmp_path])`. Pattern established in `tests/test_substrate.py` and `tests/test_mcp_server.py`.

### R8 — Knowledge persistence
- `docs/adr/ADR-0015-substrate-consumer-transport-selection.md` (NEW) — records R6's transport-selection contract.
- `memory/projects/_self.md` Solution Path tagged `[framework/substrate-consumer]` — captures the wrapper-script decision (arch-B1), the sealed-report decision (arch-B2), the refuse policy (security-F1+F2), and the rough-edges-surfaced section requirement (arch-A3).
- `CLAUDE.md` Capture Pipeline section — names the substrate emission step.
- `memory/bugs/regression-ledger.md` — only updated if Phase 1 surfaces a regression. Phase 1 itself is not adding a bug-fix entry.

### R9 — BUILD_STATUS.md discipline
Updated at session start, before any compaction, and after the commit (per `.claude/rules/autonomous_workflow.md`). Phase 0 education-gate deferral carries forward — trigger to complete is *before merging the Phase 0 + Phase 1 stack to main*.

### R10 — Surfaced edges (Phase 1 cure-in-vivo commitment)
The Phase 1 build summary MUST include a "Surfaced Edges" section enumerating at least **3 substrate or consumer-side concerns discovered during build**. Examples of qualifying findings (the MCP-availability fork is already one):
- MCP availability gaps across sessions
- Source-ref drift mechanics
- Sanitisation surface gaps (pattern set against prose vs raw source)
- (subject, predicate, object) extraction quality
- `project_id` resolution edge cases (e.g., source code copied from another repo)

Zero surfaced edges blocks Phase 2 start until investigation explains why. Rationale: Phase 1 is the plan's "cure in vivo" step. A consumer that finds zero rough edges is too trivial to exercise the substrate, and proceeding to Phase 2 (design four more primitives) on top of an unexercised foundation defeats the sequencing principle.

## Constraints

### C1 — Scope = local only
Per ADR-0014, all Phase 1 assertions use `scope="local"`. Cross-project assertions remain out of scope.

### C2 — Substrate API compatibility
The substrate's primitives (`assert_fact`, `search_semantic`, `get_source`) MUST NOT be modified. If a Phase 1 use case requires a new primitive or signature change, that becomes a separate ADR and a separate spec. Phase 1 is consumption, not substrate extension.

### C3 — Additive emission
The new emission MUST NOT replace, alter, or otherwise interfere with the existing capture pipeline. It is strictly additional output written to a different durable store.

### C4 — No backfill
Existing review reports are NOT retroactively converted into substrate assertions. Phase 1 validates the forward path only.

### C5 — Test isolation
The integration test must not pollute the project's real substrate DB. Use `tmp_path + Substrate(db_path=tmp_path/"test.db", project_id="test", source_roots=[tmp_path])`.

### C6 — Refuse-on-secret is a hard line
If any of the 12 patterns match in any of (subject, predicate, object) triple fields, the assertion is refused (not written, not masked). The captured refusal event contains metadata only (severity, file:line, pattern-class). NO triple content. NO matched substring. NO finding text. Silent acceptance of secret-containing assertions would corrupt the substrate's trust model.

### C7 — Sealed review reports
After emission completes, `close_discussion.py` chmods the review report (`docs/reviews/REV-YYYYMMDD-HHMMSS.md`) read-only alongside the existing seal of `events.jsonl` and `transcript.md`. This enforces the source-ref durability assumption that emitted assertions' line ranges remain valid (Suchness preservation per ADR-0014).

## Acceptance Criteria

- [ ] A `/review` run produces sourced assertions visible via `Substrate.search_semantic` (in-process) AND via the MCP `search_semantic` tool when reachable (manual smoke).
- [ ] Semantic query on a paraphrased blocking finding returns the original at rank position 1 (`hits[0]["subject"] == expected`) with `distance < 2.0` (canonical-test parity).
- [ ] `get_source` on the returned assertion's `source_ref` returns the original review report text byte-equal at the cited line range (Suchness preservation).
- [ ] The new regression test passes; covers R7.a–R7.f (happy path, semantic retrieval, get_source verbatim, sanitisation refusal with `AKIAIOSFODNN7EXAMPLE`, zero-blocking edge, fallback-tag).
- [ ] Quality gate passes 7/7.
- [ ] No existing `/review` cycle behaviour breaks; existing `tests/test_mcp_server.py` and `tests/test_substrate.py` continue to pass.
- [ ] `docs/adr/ADR-0015-substrate-consumer-transport-selection.md` exists, status `accepted`, records the transport-selection contract.
- [ ] `memory/projects/_self.md` has a new Solution Path entry tagged `[framework/substrate-consumer]`.
- [ ] `CLAUDE.md` Capture Pipeline section names the substrate emission step.
- [ ] `close_discussion.py` seal step extended to include `docs/reviews/REV-*.md`.
- [ ] Build summary includes a "Surfaced Edges" section with at least 3 entries (R10).
- [ ] Build summary includes Phase 0 advisory carry-forward (REV-20260515-221223 arch-F2, arch-F3, arch-F5) with current state (deferred / accepted / resolved / declined).
- [ ] BUILD_STATUS.md is current at every required gate.
- [ ] **End-of-build manual smoke**: developer manually runs `/review` in a session where the `agent-memory` MCP server is loaded, confirms the MCP path also produces assertions. Captured as a build summary note.

## Risk Assessment

### R-1 — MCP-availability fallback semantics (resolved via ADR-0015)
Soft-fail with explicit `route:` tag is the right architectural answer (per arch-A1). MCP and Substrate-direct are two transports to the same logical store; hard-failing when MCP is unavailable conflates transport health with substrate health. This differs from arch-F5's swallow-and-warn (capture failure = end-of-line, signal lost forever); MCP-vs-direct is route selection among equivalent endpoints, both of which preserve the data. ADR-0015 codifies the contract.

### R-2 — Sanitisation false negatives
The 12-pattern scan is conservative for prose-quoted code. Multi-line PEM key fragments, tokens broken across line wraps, paraphrased secrets, and truncated quotes may not match. Mitigation: refuse policy (C6) keeps any match a clean reject; partial-matching gaps are documented as known limitation. A deeper architectural fix (e.g., never quoting code > N tokens in finding text) is beyond Phase 1 scope.

### R-3 — Source-ref durability (resolved via C7 / arch-B2)
Extending `close_discussion.py`'s seal to include the review report enforces the read-only assumption that emitted assertions depend on. Implementation: add the report filename to the `for filename in [...]` loop at close_discussion.py:175.

### R-4 — Hook location coupling (resolved via R5 / arch-B1)
Wrapper script (`scripts/emit_assertions_from_review.py`) eliminates the agent-substrate coupling. Facilitator agent definition is unchanged; close_discussion.py orchestrates as it does for the other closure-pipeline steps.

### R-5 — Assertion (subject, predicate, object) extraction quality
Constructing (s, p, o) from finding prose is a small extraction task done inside `emit_assertions_from_review.py`. The script parses the review report's "Required Changes Before Merge" section and applies a deterministic extraction rule (TBD: spec to specify in the build phase based on inspection of recent review reports, or fall back to a simple template like `subject=<file:line>, predicate=<category>, object=<description>`). The acceptance criterion (rank-1 retrieval on paraphrase) is the empirical bar.

### R-6 — MCP server lifecycle (pre-existing, no Phase 1 amplification)
Three regressions in `tests/test_mcp_server.py` attest the MCP layer is fragile. Phase 1's fallback path sidesteps MCP for in-process tests, so Phase 1 doesn't *add* MCP risk. The fallback path's existence does add a new consumer that may exercise transports' rough edges — surfacing those is a Phase 1 success criterion per R10.

### R-7 — Discussion ID ordering (resolved via qa-F3)
The facilitator writes the review report's frontmatter — including the `discussion_id` field — at synthesis time, BEFORE `close_discussion.py` is invoked. Therefore `close_discussion.py`'s call to the new emission script always sees the report at its final line layout. No drift window between emission and seal.

### R-8 — MCP-vs-Substrate-direct canonicalisation parity
`mcp_server/server.py:_build_source_uri` performs additional canonicalisation beyond what `Substrate.assert_fact` does internally (per the 2026-05-12 regression-ledger entry on URI canonicalisation). The build must verify parity: read `_build_source_uri` and either (a) confirm `Substrate.assert_fact` already canonicalises equivalently, OR (b) replicate the canonicalisation in `emit_assertions_from_review.py` before constructing the source_ref. Acceptance test R7.b indirectly verifies this — if the canonicalisation differs, the assertions written via fallback won't match assertions written via MCP, and the search would not return them.

## Affected Components

- `scripts/emit_assertions_from_review.py` (NEW) — the emission script
- [scripts/close_discussion.py](scripts/close_discussion.py) — add new closure-pipeline step invoking the emission script; extend Step 9 seal to include the review report
- `docs/adr/ADR-0015-substrate-consumer-transport-selection.md` (NEW) — MCP-fallback contract
- `tests/test_review_substrate_emission.py` (NEW) — regression test covering R7.a–R7.f
- [.claude/agents/facilitator.md](.claude/agents/facilitator.md) — UNCHANGED. Emission is now scripted, not agent-driven (arch-B1 resolution).
- [.claude/commands/review.md](.claude/commands/review.md) — small Step 8 note pointing to the new closure-pipeline step. No behavioural change.
- [CLAUDE.md](CLAUDE.md) — Capture Pipeline section updated
- [memory/projects/_self.md](memory/projects/_self.md) — Solution Path entry
- [BUILD_STATUS.md](BUILD_STATUS.md) — updated at standard gates

Not affected (per C2/C3): `assertion_store/substrate.py`, `mcp_server/server.py`, existing tests for substrate/MCP, the capture pipeline scripts other than `close_discussion.py`, the four-layer capture stack boundaries.

## Dependencies

### Depends on
- ADR-0014 substrate primitives (in place since Phase 4)
- Phase 0 promotion-pipeline fix (commit `a57f3c1`)
- `tests/test_substrate.py` and `tests/test_mcp_server.py` patterns for test isolation
- `pyproject.toml` `[project].name` (resolved as project_id)

### Depended on by
- Phase 2 ADR design work — those ADRs are designed against a substrate that HAS been consumed
- Howie's eventual `/review` workflows — Phase 1 establishes the pattern Howie inherits
- Any future emission consumer (e.g., `/deliberate`, `/retro`) — Phase 1 sets the script-invoked-from-closure pattern

## Out of Scope

- Cross-project assertions (`scope="shared"`) per C1
- Backfilling existing review reports per C4
- A user-facing UI for browsing the substrate (Phase 2 ADR-0017)
- Promotion of substrate assertions to Layer 3 `memory/` (substrate IS storage; promotion is separate)
- Emission from `/deliberate`, `/retro`, `/build_module` synthesis (future Phase 1.5+ consumers; one consumer is enough)
- Editing the substrate primitives, schema, or transport (per C2)
- A general fix to the swallow-and-warn pattern at `scripts/close_discussion.py:118-194` (Phase 0 architectural debt, captured for a future ADR per REV-20260515-221223 arch-F5)
- Tightening sanitisation beyond the 12-pattern set (deeper architectural fix is beyond Phase 1 scope; documented as known limitation)
- An automated MCP-vs-Substrate-direct A/B test (the manual smoke is the right level of coverage given MCP availability is itself intermittent)

## What happens after this lands

After Phase 1 merges to main, Phase 2 (design the four Howie primitives) begins. Phase 2 has a 1-week hard cap. Phase 1's "Surfaced Edges" section (R10) feeds Phase 2's design inputs — every rough edge becomes a Phase 2 design constraint or a Phase 1.5 follow-up ticket.