---
discussion_id: DISC-20260716-174913-review-cost-cache-instrument
started: 2026-07-16T17:49:39.332672+00:00
ended: 2026-07-16T18:04:44.376762+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist, security-specialist]
total_turns: 9
---

# Discussion: DISC-20260716-174913-review-cost-cache-instrument

## Turn 1 — facilitator (evidence)
*2026-07-16T17:49:39.332672+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Full multi-agent /review of the uncommitted wave-1 cost/cache instrument (SPEC-20260716-093231) on feat/cost-cache-instrument before commit.
- **Files/scope**: scripts/telemetry/call_log.py (NEW), tests/test_call_log.py (NEW), scripts/ingest_token_usage.py, src/telemetry/cost.py, scripts/stop_hook.py (security-sensitive hook), tests/test_stop_hook.py, .gitignore, docs/adr/ADR-0020 implementation note.
- **Developer-stated motivation**: 2026-07-14 perf review P1#3 — all cost telemetry NULL; cache_read/total is the blind-spot leading indicator; unblocks triage items 5/7 and the frozen dashboard.
- **Explicit constraints**: sensor only (dashboard FROZEN); no DB DDL; stop_hook ADR-0023 invariants untouchable; no .claude/settings.json edit by agent; no push. Known flagged carve-out for the panel: corrupt dedup-state degrades to a one-time full re-log (rare, documented; readers dedup by message_id) vs AC2's 'never logs twice'.

---

## Turn 2 — qa-specialist (proposal)
*2026-07-16T17:57:52.175644+00:00 | confidence: 0.8*
*tags: review, qa, Severity: medium*

VERDICT: approve-with-changes (0.80). 0 blocking. AC-by-AC verification: AC1-AC4, AC6-AC12 all genuinely covered (named test per AC); AC5 partially — combined matched-reply-intent + FAILING-kick path untested (F1, Medium). F2 (Medium): subagent transcript flushing later than FLUSH_LAG_SECONDS after watermark advance = SILENT PERMANENT DROP — a 4th risk class the docstring's 'never silent loss' claim omits; test + docstring bullet needed. F3 (Medium): tests/test_ingest_token_usage.py has zero direct coverage of source_kind/deadline (only transitive via test_call_log). F4 (Low): call_log's own no-projects-root / no-sessions early returns untested. F5 (Low): in-new_records same-run cross-path dedup branch uncovered. F6 (Medium): throttle-stamp WRITE failure falls through to run subprocess every stop — silently defeats once-per-floor; untested + undocumented. F7 (Info): AC2 text lacks the corrupt-state carve-out cross-ref. CARVE-OUT VERDICT: acceptable as shipped (bounded, self-heals, documented, duplicate-not-loss). Strengths: write-side isolation exemplary; byte-identical stdout proof; honest-null split into two parametrized cases; mocks assert real args (rule 15).

---

## Turn 3 — security-specialist (proposal)
*2026-07-16T17:57:52.288649+00:00 | confidence: 0.91*
*tags: review, security, Severity: info*

VERDICT: approve (0.91). 0 blocking. All ADR-0023 invariants verified byte-identical (git diff main: _handle_intent body moved, not changed, save one ruff isinstance modernization). Subprocess: fixed list argv, sys.executable, no shell, no interpolation; capture_output makes decision-channel pollution structurally impossible (byte-identical stdout test proves it). Symlink guard REUSED not re-implemented in the deadline-aware path. No secrets in JSONL/console (type-only exceptions; slug-in-exception regression test). Findings: INFO — JSONL opaque-fields rule enforced by comment only; first real consumer should land with a /review + typed read model. LOW — throttle stamp tamperable by a local-write actor (strictly smaller foothold than they already have; no action). INFO — unbounded growth documented/deferred. Prime Objective surface untouched.

---

## Turn 4 — architecture-consultant (proposal)
*2026-07-16T17:57:52.410705+00:00 | confidence: 0.88*
*tags: review, architecture, Severity: info*

VERDICT: approve (0.88). 0 blocking. All 8 checklist items pass: deps scripts->src only; parser one-file-patch isolation held (source_kind structural in _iter_jsonl_files); signature change contained (exactly one caller, verified by grep; frozen-dataclass additive field backward-compatible); ADR-0013 honored (ratio recomputable from same line; report ratios read-time properties); ADR-0020 note accurate line-for-line incl. FLUSH_LAG detail; watermark substrate reused with richer payload where granularity demands; call_log uses ONLY public itu surface (better than analyze_cost precedent — no private reach); dashboard-frozen verified. INFO-1: spec R2 prose narrower than the stronger implemented design (trailing window) — ADR is the load-bearing record and is correct; optional spec clause. INFO-2: tests landed in new test_call_log.py vs spec's stated files — cleaner choice, spec Affected-Components mildly stale. Strengths: ratio de-dup across two consumers earns its keep; divergence documented not smuggled; stdout protection by construction.

---

## Turn 5 — docs-knowledge (proposal)
*2026-07-16T17:57:52.523819+00:00 | confidence: 0.85*
*tags: review, docs-knowledge, Severity: high*

VERDICT: approve-with-changes (0.85). 0 blocking. Chain spec->ADR->docstrings verified accurate line-for-line (constants/env/timeout 680 all match). F1 (High, undiscoverable): docs/HOOKS.md has NO Stop section at all (pre-dates this build, ADR-0023 gap) — CLAUDE.md's own pointer dead-ends for an operator asking 'why is my cache ratio not logging'; add ## Stop section covering intent flow, kick, both kill-switches, throttle/budget numbers, and the INERT-until-settings-paste fact. F2 (Med-High, knowledge-stuck): BUILD_STATUS.md untouched — the spec's own mitigation ('BUILD_STATUS carrying the wiring obligation') unfulfilled; must land at commit. F3 (Medium): THIRD occurrence of the autoformat-strips-early-import class (ledger lines ~79/81 = sessions 22/23; this build = stop_hook subprocess import) — Rule-of-Three exceeded: add ledger row for this occurrence + propose (developer-gated) a one-line running-build-checkpoints skill addition. F4 (Low): cost.py module docstring omits the new ratio capability. F5 (Info): no model-tier tags on events — systemic, out of scope. Strengths: call_log docstring is a model artifact; gitignore rationale self-contained; build transcript strong Layer-3 material.

---

## Turn 6 — facilitator (critique)
*2026-07-16T18:03:15.386605+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 12 verified (all file:line refs confirmed against code), 2 inconclusive (judgment-dependent: qa F2 flush-lag plausibility, docs F3 promote-now-vs-watch), 0 discarded. Facilitator folded all actionable advisories in-session: docs/HOOKS.md Stop section (docs F1); cost.py module docstring (docs F4); regression-ledger row for the 3rd autoformat-import-strip occurrence (docs F3a); spec AC2 carve-out cross-ref + R2 as-built clause + Affected Components correction (qa F7, arch INFO-1/2); call_log docstring 4th risk class (qa F2); stop_hook throttle-degradation bound (qa F6); 9 new tests (qa F1/F2/F3/F4/F5/F6) — affected suites re-run green (89 tests). Remaining developer-gated: running-build-checkpoints skill one-liner (Principle #7); BUILD_STATUS obligation lands at commit.

---

## Turn 7 — facilitator (synthesis)
*2026-07-16T18:03:15.557465+00:00 | confidence: 0.86*
*tags: blocking:0, advisory:14, speculative:0, model-tiers:qa-default+sec-default+arch-default+docs-default*

## Request Context
- **What was requested**: Full /review of the uncommitted wave-1 cost/cache instrument (SPEC-20260716-093231) before commit.
- **Files/scope**: 12 files (see REV-20260716-181500 reviewed_files).
- **Developer-stated motivation**: perf review P1#3 — all cost telemetry NULL; ratio = blind-spot indicator; unblocks triage 5/7 + dashboard un-freeze.
- **Explicit constraints**: sensor only; no DDL; ADR-0023 invariants untouchable; settings wiring = developer manual edit; no push.

## Synthesis
VERDICT: approve-with-changes (0.86 weighted), ALL CHANGES FOLDED IN-SESSION. 0 blocking / 14 advisory (5 Medium, 1 High-docs, rest Low/Info) / 0 speculative (<0.80) / 0 unscored. Panel convergence: the subprocess+capture_output design makes the stdout decision-channel invariant hold BY CONSTRUCTION (security verified intent flow byte-identical via git diff; qa proved byte-identical stdout by test). qa's AC-by-AC audit found AC5's combined-failure path and a genuine 4th risk class (late-flush silent drop beyond FLUSH_LAG) — both now tested+documented. docs-knowledge (non-participating, Principle #4) surfaced the highest finding: docs/HOOKS.md had NO Stop section (pre-existing ADR-0023 gap) — fixed; and named the autoformat-import-strip class as Rule-of-Three-exceeded — ledger row added, skill one-liner left developer-gated. Carve-out ruling: corrupt-state one-time re-log ACCEPTED (bounded, self-healing, duplicate-not-loss). Model tiers: qa-specialist:default(sonnet-class), security-specialist:default, architecture-consultant:default, docs-knowledge:default; facilitator exempt. Report: docs/reviews/REV-20260716-181500.md. Education gate: REQUIRED, Tier 1.

---

## Turn 8 — qa-specialist (reflection)
*2026-07-16T18:04:44.260954+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Flagged the subagent flush-lag risk (F2) from plausibility, not observed transcript timing; and did not cross-check whether analyze_cost's older watermark carries the same exposure (would have sharpened severity: precedented-Low vs novel-Medium).
## Candidate Improvement Rule
When flagging a silent-loss edge in an incremental/watermark pipeline, first grep sibling modules using the same pattern for whether the risk is already accepted/documented — converts speculative Medium into precedented-Low or better-justified Medium/High.
## Confidence Calibration
Original: 0.80, Revised: 0.80, Delta: +0.0 (all 7 findings accepted and folded without pushback).

---

## Turn 9 — docs-knowledge (reflection)
*2026-07-16T18:04:44.376762+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Found the recurring import-strip class (F3) only by reading the full build transcript; the reliable tell — a checkpoint REVISE->APPROVE cycle — should have triggered an immediate regression-ledger grep for the root-cause class. Also did not check whether the HOOKS.md Stop-section gap was an aged carried advisory from the ADR-0023 build rather than a fresh find.
## Candidate Improvement Rule
When a build transcript contains any checkpoint REVISE, grep the regression ledger for the defect's root-cause class BEFORE writing findings — caught-and-fixed defects are the highest-yield place stuck Layer-1 knowledge hides.
## Confidence Calibration
Original: 0.85, Revised: 0.85, Delta: +0.0 (findings concrete and grep-verified; the miss is process-ordering, not conclusions).

---
