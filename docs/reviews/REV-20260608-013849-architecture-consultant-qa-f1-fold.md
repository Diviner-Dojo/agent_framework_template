---
id: REV-20260608-013849-architecture-consultant-qa-f1-fold
reviewer: architecture-consultant
target: qa F1 fold (session 10i) on REV-20260607-200447 — Layer B live dashboard
branch: fix/c-gate-log-integrity
scope: tests-only (23 new @pytest.mark.regression tests + _lane helper in tests/test_telemetry.py); regression-ledger entry at line 64
date: 2026-06-08
---

# Architecture review — qa F1 fold (session 10i)

**Verdict**: APPROVE-WITH-CHANGES (one MED defer-as-advisory; two LOW info-only)
**Confidence**: 0.82

The fold lands a coherent renderer-as-pure-function contract layer that genuinely complements the existing fold-driven integration tests — the construct-synthetically-no-`fold_events` decision is principled, not redundant. The one architectural concern worth tracking is the import-of-privates surface (5 `_render_*` symbols now consumed across a module boundary), which is the correct test-only choice today but cements a coupling that future seam-shifts (arch F2 / Phase 2) will need to be aware of. The `_lane` helper, ordering, and ledger classification are all sound.

## Architectural alignment

- **ADR-0020 (telemetry + honest-absence)**: tests pin the C4 anti-pattern guards (no fabricated 0% bar; no fabricated 0-turn cold-start; no empty `<table>` shell masquerading as data). Direct alignment.
- **Principle #4 (independence prevents confirmation loops)**: synthetic-construction-not-fold breaks the renderer↔fold confirmation loop the prior composition tests had (a renderer that quietly relied on a fold-side invariant would have hidden in the integration path). Strong alignment.
- **Principle #8 (least-complex intervention first)**: 23 unit tests are the *right* size for "5 sub-renderers, 4-5 branches each" — no helper class, no fixture machinery beyond a builder, no parametrize-of-parametrize. Aligned.
- **Spec C6 (escape seam)**: the 3-cell + 2-cell XSS guards are the seam check this surface was missing. Aligned.

## Boundary analysis

Imports flow correctly (`tests/` → `src/telemetry/{dashboard,live}`). No new cross-module coupling in production code. The new test-side dependency on **5 underscore-prefixed symbols** (`_render_runway_panel`, `_render_runway_estimate`, `_render_agent_lanes_panel`, `_render_agent_lane_row`, `_render_live_stream_panel`) is the architectural seam worth naming — see F1.

## Findings

### F1 MED — defer-as-advisory — Test surface imports 5 PRIVATE renderers across a module boundary

- **Category**: coupling
- **Rule**: Coding standard ("Private members: single leading underscore"); cross-module reach into `_name` is a convention break that signals "tests own this surface contract."
- **Location**: `tests/test_telemetry.py:26-39` (imports), 23 tests in the new section.
- **Description**: The FRICTION-5 fold deliberately routed through `render_live_fragment` "so the test also catches a transport-layer swap." This fold deliberately does NOT. Both choices are defensible — they test different contracts (composition+transport vs. per-renderer-pure-function). The cost: any future refactor that moves a `_render_*` into a sibling module, inlines it, or splits a panel into 2 helpers will cascade into ~15 test fixups. Today there is exactly one consumer of each `_render_*` (the public `render_live_fragment` composition + this test file). Rule of Three says they should remain private until a second production consumer appears.
- **Recommendation**: Keep the tests as-is for this fold (they ARE the right level for the qa F1 finding), but add a SHORT comment at the top of the new section (around line 3076) naming the tradeoff explicitly: "These imports reach across the private-prefix boundary deliberately. If a future split moves a `_render_*` to a sibling module, update both the import and any callers — do NOT promote these to a public surface to satisfy the test (Rule of Three: one production consumer + one test consumer is not promotion-worthy)." Defer the in-code expression to the next-session fold to avoid touching tests post-quality-gate.
- **Exceptions**: If Phase 2's per-turn-cost chart promotes one of these to public for legitimate reuse (Rule of Three crossed), this finding evaporates for that symbol.
- **ADR Reference**: ADR-0020 (telemetry surfaces; the public/private distinction matters for the dashboard's eventual API).

### F2 LOW — info — Fold-renderer seam is tested only at the composition boundary

- **Category**: coupling
- **Rule**: Principle #4 (independence) + the test-the-seam-not-just-the-sides heuristic.
- **Location**: composition test at `tests/test_telemetry.py:3576` and the existing fold-driven tests above 3072.
- **Description**: The fold (`apply_event` / `fold_events`) is tested standalone. The renderers are now tested standalone. The SEAM — "does the renderer correctly consume every field the fold actually emits, in every shape the fold actually emits them?" — is covered only by the existing composition tests above (FRICTION-2 etc.). That's adequate coverage TODAY, but worth a note: a future field added to `LiveState` / `AgentLane` (`tool_count` extension, a new lane status) could be set by the fold and silently ignored by the renderer, and neither side's tests would catch it. This is not a finding against the fold — it's an observation about the test pyramid shape after this fold lands.
- **Recommendation**: No change. If Phase 2 (per-turn cost chart) adds a new field, ensure the field has at least one composition-path test exercising it end-to-end (`fold_events(...)` → `render_live_fragment(state)`).
- **Exceptions**: Inherent to the layered test pyramid; not actionable without a contract test.

### F3 LOW — info — Phase 2 prerequisite alignment

- **Category**: pattern-consistency
- **Rule**: Door policy (close doors you don't need; keep open doors you do).
- **Location**: the new section as a whole.
- **Description**: arch F2 (event-source seam) and Phase 2 (per-turn cost chart) will likely (a) introduce a new `LiveCostEvent` field or kind, and (b) introduce a new sub-renderer or a chart helper. These tests do NOT box that future in — they pin the *current* renderers' contracts, not the panel taxonomy. The `_lane` helper is module-local and won't fight a future fixture promotion. Door correctly open.
- **Recommendation**: None. Aligned.

### F4 INFO — Regression-ledger classification

- **Category**: pattern-consistency
- **Rule**: Ledger taxonomy.
- **Location**: `memory/bugs/regression-ledger.md:64`.
- **Description**: "Missing Null/Empty Case" is defensible — the centerpiece of the fold IS the honest-absence guards (empty context window, `est_turns_remaining=None`, empty agents, empty events). However, ~7 of the 23 tests are XSS-escape / clamping / ordering / class-emission guards, which fit "Trust Boundary Gap" or "Schema/Serialization Drift" better. The honest-absence guards are the *most distinctive* contribution, so the single-class entry is fine — the ledger never demanded perfect partition. Info-only.
- **Recommendation**: None. The existing classification matches the fold's primary signal.

### F5 INFO — `_lane` helper placement

- **Category**: pattern-consistency
- **Rule**: Test fixture promotion threshold.
- **Location**: `tests/test_telemetry.py:3091`.
- **Description**: Module-local is correct. Promoting to `conftest.py` or a pytest fixture would (a) make the helper available to tests that don't need it, and (b) couple test files via fixture discovery. The helper has 1 caller file and is named with a leading underscore — both signal "private to this section." If a future test file (`tests/test_live_renderers.py`) ever extracts these tests into a dedicated module, the helper moves with them.
- **Recommendation**: None. Aligned with Rule of Three.

## Strengths

- **Synthetic construction is principled** — the comment block at lines 3072-3088 names the architectural rationale (renderer-as-pure-function contract distinct from the fold contract). This is exactly the documentation an architecture reviewer wants to see before reading 23 tests.
- **Parametrize where it earns its keep** — 3 statuses (runway), 3 statuses (lane), no `parametrize`-for-parametrize's-sake.
- **Intent-over-markup discipline** — tests pin "class appears" / "label appears" rather than full HTML fragment equality, so a CSS-restyle won't cascade into broken tests.
- **Negative assertions are explicit and named** — `'data-state="data"' not in panel`, `<table not in panel`, `lane--primary not in row` — each pinned the corresponding C4 anti-pattern, not just the happy path.
- **Composition tests at the bottom** complete the inverted pyramid (unit → composition → fold-driven → server integration).
