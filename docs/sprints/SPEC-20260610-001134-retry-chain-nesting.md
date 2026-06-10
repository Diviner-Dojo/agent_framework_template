---
spec_id: SPEC-20260610-001134
title: "Retry-chain nesting in the A2 Failure & Waste panel (TEMPORAL)"
type: spec
status: complete
risk_level: medium
parent_spec: SPEC-20260607-183136
reviewed_by: [architecture-consultant, qa-specialist]
discussion_id: DISC-20260610-001234-retry-chain-nesting-spec-review
intake_ids: []
completed_at: 2026-06-10
completed_commit:
---

## Goal
Group consecutive `retry_loop` `FailureSignal`s that occur within a short time
window into ONE nested "retry chain" row in the A2 Failure & Waste panel, so
the gatekeeper reads cascades like *"one root cause, four reactions"* rather
than as N uncorrelated retry-loop rows. Completes Phase 3 of SPEC-20260607-183136
("Failure intelligence — error-class grouping + remediation hints; config-drift
rows; **retry-chain nesting**.").

## Context
Phase 3 Unit 1 (`6efdf8b`) bucketed failure rows by error class. Phase 3 Unit 2
(`c50f2fd`) surfaced config drift as a sibling tile. Today the A2 panel still
shows one row per detected retry-loop signal: a missing path that produced 3x
`Read` retries + 2x `Glob` retries chasing the same target is rendered as
*two independent rows of equal weight*, which inflates the visual count of
failures and obscures the single underlying cause.

The **TEMPORAL** heuristic groups consecutive retry-loop signals whose
`first_seen`/`last_seen` timestamps fall within a bounded gap (default 120s).
This was the developer-decided fork resolution (per HANDOFF-supervisor-rolling
2026-06-09): it is **read-time pure** over existing `first_seen`/`last_seen`
fields populated by `_build_retry_signal`, and respects ADR-0013
compute-don't-store (no new DB columns, no analyzer transport changes).

Prior-art notes (from session 19 ledger entry for `src/telemetry/drift.py`,
`memory/bugs/regression-ledger.md`):
- Unit 2 explicitly anticipated Unit 3 as the **Rule-of-Three trigger** for a
  `_group_by_key(items, key_fn, canonical_order)` helper (Unit 1's
  `_group_failures_by_class` + Unit 2's `_group_drift_by_kind` were the first
  two). Defer or extract per Principle #8 (least-complex first): if the third
  grouping function in Unit 3 shares structure with the first two, extract;
  otherwise document the trigger and defer.
- The fail-loud-`[key]`-not-silent-`.get()` lookup pattern (from Unit 1's
  `REMEDIATION_HINTS[cls]` fold) is the load-bearing honesty discipline; any
  new map-based lookup in Unit 3 must follow the same fail-loud rule.
- Regression-ledger parser hazard: no raw `|` characters inside backticks in
  ledger prose (the parser cell-splits on them); no multi-path Test File cell.

## Requirements
- **R1** Pure helper `group_retry_chains(ranked, *, max_gap_seconds=120)` in
  `src/telemetry/failures.py` returns `list[RetryChain]` from a ranked failure
  list. Read-only over the existing dataclasses; no DB read; no mutation.
- **R2** `RetryChain` dataclass exposes `head: RankedFailure`,
  `links: list[RankedFailure]`, `total_cost_usd: float | None`,
  `total_wasted_tokens: int`. `total_cost_usd` honors the honest-absence rule
  (`None` if EVERY link has `cost_usd is None`; otherwise the sum of the
  priced links — never fabricate `$0` for an unpriced link).
- **R3** Two consecutive `retry_loop` signals chain iff `next.first_seen - prev.last_seen <= max_gap_seconds`
  (the boundary is **inclusive** — gap equal to the window chains).
  Non-retry-loop signals (`orphaned_subagent` today) NEVER participate AND are
  **SKIPPED OVER** by the chain walker (qa F1 fold) — they do NOT reset the
  chain-candidate pointer. Rationale: today the per-class restriction (R7)
  means a non-retry signal cannot share a class with a retry-loop, so the
  skip-over rule is observationally a no-op; for future heterogeneous classes,
  skip-over preserves the "one root cause, N retry reactions" semantic
  (an unrelated failure happening between two retries does not undo the
  fact that the retries are temporally adjacent reactions to the same
  underlying cause).
  Signals lacking timestamps (`first_seen is None` OR `last_seen is None`)
  NEVER chain (no fabricated adjacency from missing data).
  Tz-aware/naive mismatch on the subtraction is caught and treated identically
  to a missing timestamp (qa F3 fold — `TypeError` on `datetime` subtraction
  becomes "no chain" rather than a render-time crash); the canonical analyzer
  transport always emits tz-aware UTC, so this path is defensive belt-and-braces
  against an alternate data source feeding the renderer.
- **R4** A retry-loop signal with no neighbour in the window = a chain of length 1.
  The renderer MUST emit the same HTML shape it does today for that case (no parent/child
  scaffold for length-1 chains). No visual regression for non-chained signals.
- **R5** A chain of length ≥ 2 renders as one *parent row* (the head signal,
  carrying the chain total cost + chain total wasted tokens + a chain-size
  badge) followed by N-1 indented *link rows* (CSS class `retry-chain-link`)
  for the cascade members. The parent row carries an explicit `data-chain-size`
  attribute and an accessible label so screen readers announce the grouping.
  A new private helper `_render_retry_chain(chain: RetryChain) -> str` in
  `src/telemetry/dashboard.py` is the single render seam for both the
  length-1 short-circuit and the length-≥2 chain shape (arch F1 fold —
  keeps `_render_failure_class_group` under the ~50-line guideline and
  makes A8's structural-absence invariant local to one function).
- **R6** Within-group ranked order from `rank_failures` is preserved for the
  *chains* (chains sort by their head's rank slot), and within a chain the
  links are in temporal order (head = earliest by `first_seen`, then links
  by `first_seen` ascending). This MUST be deterministic across runs.
- **R7** The chain grouping happens AFTER `_group_failures_by_class` so it
  operates per error class (a cascade across class boundaries is rare and
  conceptually a different signal — leave it as multiple chains, one per class).
- **R8** No DB schema change. No analyzer transport change. No new HTTP route.
  Module `failures.py` stays IO-free.

## Constraints
- **C1** ADR-0013 compute-don't-store: detect at read time only.
- **C2** ADR-0020 honesty discipline: never fabricate a chain link; a missing
  timestamp = no chain. Mixed priced/unpriced chain totals = `None` only when
  EVERY link is unpriced; otherwise sum the priced.
- **C3** `_render_failure_class_group` continues to be the single render path
  for an error-class group (R15 single render path).
- **C4** Module-level `MAX_RETRY_CHAIN_GAP_SECONDS = 120` constant, not a magic
  number; tunable + testable.
- **C5** Coding standards: type-annotated public function + dataclass; Google-style
  docstrings; no bare `except`; pure (no IO).
- **C6** Render-path escaping: every dynamic string interpolated through `_esc`,
  same C6 discipline as today.
- **C7** No raw `|` in regression-ledger prose; single primary test file in
  the Test File column.
- **C8** (qa F3 fold) `datetime` subtraction in `group_retry_chains` MUST be
  guarded against `TypeError` (tz-aware/naive mismatch) and treated identically
  to a missing timestamp — no chain, no render-time crash. This is defensive
  in depth: the canonical analyzer transport emits tz-aware UTC and shouldn't
  produce mixed shapes, but a future alternate data source (CLI exporter,
  JSON import) might.
- **C9** (arch F2 fold) The Rule-of-Three trigger for a generic
  `_group_by_key(items, key_fn, canonical_order)` helper is **explicitly
  declined** this unit; the three grouping functions
  (`_group_failures_by_class`, `_group_drift_by_kind`, `group_retry_chains`)
  have substantively divergent shapes (sort-key-driven bucket / canonical-order
  bucket / temporal-window fold). Document the decline in the regression-ledger
  entry so future readers see the trigger was considered and closed, not missed.

## Acceptance Criteria
- [ ] **A1** `group_retry_chains([])` returns `[]`.
- [ ] **A2** Two retry-loops with gap **strictly less than** the window chain
      (chain length 2); gap **exactly equal to** the window (qa F2 fold —
      `<= MAX_RETRY_CHAIN_GAP_SECONDS`, boundary inclusive) chains.
- [ ] **A3** Two retry-loops with gap of `MAX_RETRY_CHAIN_GAP_SECONDS + 1`
      seconds do NOT chain (two chains, length 1).
- [ ] **A4** A retry-loop adjacent to an orphaned-subagent signal does NOT chain
      with the orphan. (Per R7, orphans live in the `ORPHAN` class and
      retry-loops in NOT_FOUND/VALIDATION/OTHER, so the two never share a
      per-class group; this criterion pins the structural guarantee at the
      helper layer regardless of class.)
- [ ] **A4b** (qa F1 fold) A non-retry signal interleaved in time between two
      retry-loops (`retry @ t=0, orphan @ t=60, retry @ t=80`) does NOT
      prevent the two retries from chaining — the orphan is skipped over,
      not used as a chain reset (R3).
- [ ] **A5** A signal with `last_seen=None` or `first_seen=None` NEVER chains.
- [ ] **A5b** (qa F3 fold) A retry-loop pair where one has tz-aware timestamps
      and the other tz-naive does NOT chain and does NOT raise (the
      `TypeError` on subtraction is caught and treated as "no chain").
- [ ] **A6** `RetryChain.total_cost_usd` is `None` when every link is unpriced
      (`cost_usd is None` for every link); otherwise the sum of priced links
      (an unpriced link in a mixed chain does NOT contribute and does NOT
      cause `None`). Sub-cases:
      - **A6a** Single priced link + N-1 unpriced links → `total_cost_usd` is
        the priced link's `cost_usd`.
      - **A6b** (qa F6 fold) A link with `cost_usd == 0.0` IS priced and
        contributes `0.0` to the sum (guards against a future `if cost_usd`
        truthy guard accidentally excluding genuinely-zero priced links).
- [ ] **A7** `RetryChain.total_wasted_tokens` sums every link's `wasted_total_tokens()`.
- [ ] **A7b** (qa F5 fold) Two retry-loops with `first_seen == last_seen`
      (zero-duration signals) and gap of 0s DO chain (gap 0 ≤ window).
- [ ] **A8** (qa F4 fold — structural-absence framing) The rendered HTML for a
      length-1 chain emits the same flat `<tr>` shape used today:
      the row carries NO `data-chain-size` attribute, no `retry-chain-link`
      sibling rows are emitted, and no parent-row aria-label is added.
      (Property assertions, not byte equality — resilient to legitimate
      whitespace/attribute-order refactors.)
- [ ] **A9** A length-≥2 chain renders with `data-chain-size="N"`, an
      `aria-label` on the parent row naming the chain (e.g.
      `"Retry chain (N consecutive retries)"`), and exactly N-1
      `retry-chain-link` child rows in temporal order.
- [ ] **A10** Chains sort within their class by the head's inbound rank slot
      (parent ordering preserved); links inside a chain are in temporal order
      (head = earliest by `first_seen`, then links by `first_seen` ascending);
      Python's stable sort preserves inbound order on `first_seen` ties.
- [ ] **A10b** (qa F8 fold) Calling `group_retry_chains()` on the same input
      twice produces identical chain output (determinism probe).
- [ ] **A11** `MAX_RETRY_CHAIN_GAP_SECONDS = 120` is a module-level named constant;
      changing it changes the chain boundary in a test that passes `max_gap_seconds=60`.
- [ ] **A11b** (qa F7 fold) `group_retry_chains([orphan, orphan])` returns
      `[]` (an all-non-retry-loop input yields no chains — orphans are never
      wrapped in a RetryChain).
- [ ] **A12** Quality gate 7/7; regression-ledger entry added.

## Risk Assessment
- **Visual regression for non-chained signals (HIGH)** — mitigated by A8 (byte-identical
  shape pin for length-1 chains).
- **Cross-class chain elision (MED)** — a cascade where one signal classified as
  `not_found` is followed within the window by a signal classified as `validation`
  will NOT chain across classes (R7). Acceptable for Phase 3 (cross-class cascades
  are rare, ambiguous, and would muddy the per-class hint contract); documented as
  a follow-up if user evidence shows it matters.
- **Rule-of-Three temptation (LOW)** — extracting `_group_by_key` now adds an
  abstraction with three slightly different callers. Decision in the build phase
  per Principle #8 ("three similar lines is better than a premature abstraction");
  document trigger either way.

## Affected Components
- `src/telemetry/failures.py` (add `RetryChain`, `group_retry_chains`, `MAX_RETRY_CHAIN_GAP_SECONDS`)
- `src/telemetry/dashboard.py` (extend `_render_failure_class_group` or add
  `_render_retry_chain_row`; emit parent-row + link-row scaffold ONLY for chains ≥2)
- `tests/test_telemetry.py` (helper-level chain tests + render tests mirroring Unit 1)
- `memory/bugs/regression-ledger.md` (one entry naming the new guards)

## Dependencies
- Depends on: Phase 3 Unit 1 (`6efdf8b` — `_render_failure_class_group` is the
  insertion point) and Unit 2 (`c50f2fd` — Rule-of-Three trigger context).
- Depended on by: completes Phase 3 of SPEC-20260607-183136. After this commit,
  the Phase 3 cohort is closed.

## Out of scope (explicit)
- Cross-class cascade detection (per R7 / Risk Assessment).
- ARGUMENT-SHAPE heuristic (developer-rejected fork resolution).
- Analyzer transport changes; new DB columns; new HTTP routes.
- `_group_by_key` extraction unless the third caller's structure makes it the
  least-complex intervention (Principle #8 decision in build phase).
