---
review_id: REV-20260607-200447
discussion_id: DISC-20260607-200447-review-telemetry-layer-b-dashboard-server-phase1
pr_id: ""
risk_level: high
collaboration_mode: structured-dialogue
exploration_intensity: medium
agents_activated: [qa-specialist, security-specialist, architecture-consultant, ux-evaluator, docs-knowledge, independent-perspective]
reviewed_files:
  - scripts/telemetry/dashboard_server.py
  - src/telemetry/live.py
  - src/telemetry/dashboard.py
  - src/telemetry/static/htmx.min.js
  - src/telemetry/static/README.md
  - scripts/ingest_token_usage.py
  - scripts/telemetry/analyze_cost.py
  - scripts/telemetry/analyze_failures.py
  - scripts/telemetry/analyze_value.py
  - tests/test_dashboard_server.py
  - tests/test_telemetry.py
  - tests/test_ingest_token_usage.py
  - docs/adr/ADR-0020-telemetry-oversight-component.md
  - memory/bugs/regression-ledger.md
rounds: 1
consensus_reached: true
verdict: approve-with-changes
confidence: 0.85
review_duration_minutes: 30
---

## Request Context
- **What was requested**: /review of Phase 1 of SPEC-20260607-183136 (Layer B live dashboard daemon) per the autonomous workflow before commit. No push.
- **Files/scope**: NEW `scripts/telemetry/dashboard_server.py` (~470 lines FastAPI app); NEW `src/telemetry/live.py` (~620 lines pure event-fold); extended `src/telemetry/dashboard.py` (+220 lines live-panel renderers); NEW `src/telemetry/static/htmx.min.js` (vendored 1.9.12, SHA384 recorded) + README; A-ARCH1 promotion in `scripts/ingest_token_usage.py` (rename 3 privates to public) + 5 call-site updates; NEW `tests/test_dashboard_server.py` (30 invariant tests); +29 tests in `tests/test_telemetry.py`; ADR-0020 amended; `memory/bugs/regression-ledger.md` +4 entries.
- **Developer-stated motivation**: First telemetry component that binds a port = network-attack surface. Steward APPROVE 0.86 form-factor gate overturns DISC-20260607-063709 with 9 binding conditions = AC1-AC9.
- **Explicit constraints**: NO push; NO auto-merge; 9 Steward conditions; HARDCODED_HOST literal + no `--host` flag + no `HOST` env read + runtime guard; CORS same-origin only + Host header validation; `html.escape` via `_esc` seam; vendored frontend assets (NO CDN); read-only DB; live.py pure; generic errors; no outbound HTTP client; ASCII-safe console; Phase 1 explicitly defers AC11/AC12/AC13.

## Verdict: APPROVE-WITH-CHANGES (consensus across 6 specialists)

**0 BLOCKING / 21 advisory findings.** Five high-convergence advisory items were applied pre-commit (see below). Sixteen remaining items track as advisory for Phase 2 / follow-up.

The 4-stage approval cascade leading into this review (Steward gate → spec review → 2 build checkpoints) surfaced security + purity invariants correctly — those are clean and well-tested. The independent-perspective panellist correctly identified one structural concern the cascade missed (lazy-per-request fold reads all 94MB of this repo's transcript root every 3s) and a UX-correctness concern (htmx default-drops-on-non-2xx makes the honest-error fragment unreachable). Both were addressable with one-line fixes; both are now in.

The form-factor reversal itself — from static HTML to standing daemon — was actively probed by independent-perspective for confirmation bias and found sound (the deep-dive's structural-gap analysis is rigorous; no alternative form factor is better).

## Specialist Verdicts

| Specialist | Model | Verdict | Confidence | Top finding |
|---|---|---|---|---|
| qa-specialist | sonnet | APPROVE-WITH-CHANGES | 0.87 | F1 (HIGH): 6 live-panel renderers have zero direct render tests; escape test only verifies HTTP route output, not amber/red runway class emission or lane-class row classes. |
| security-specialist | sonnet | APPROVE-WITH-CHANGES | 0.91 | F1 (LOW): vendored htmx SHA384 is README-documented but not machine-verified — a backdoored swap-in passes the existing test. **(FIXED pre-commit)** |
| architecture-consultant | sonnet | APPROVE-WITH-CHANGES | 0.86 | F1 (MED): A-ARCH1 public surface is internally inconsistent — `parse_timestamp` + `coerce_int` are also consumed by the daemon but lack the promotion docstring footer the other 4 carry. |
| ux-evaluator | sonnet | APPROVE-WITH-CHANGES | 0.82 | FRICTION-1 (HIGH): loading state is visually IDENTICAL to honest-absence tile (no `.tile[data-state="loading"]` CSS rule); if htmx fails to load, user sees a dashed tile indistinguishable from "analyzer not run". |
| docs-knowledge | sonnet | APPROVE-WITH-CHANGES | 0.87 | F1 (MED): FRAMEWORK_SPECIFICATION changelog has no entry for ADR-0020 — the entire Telemetry & Oversight component is invisible to the spec. |
| independent-perspective | opus | APPROVE-WITH-CHANGES | 0.74 | Lazy-per-request fold reads all 94MB of this repo's transcript root every 3s with NO `since` cutoff — the `since` parameter is plumbed through 3 functions UNUSED (Chekhov's gun). **(FIXED pre-commit)** |

## Pre-commit Fixes Applied (5)

These fixes address findings where 2+ specialists converged on the same root concern, OR independent-perspective marked the item "Required":

1. **`since` parameter wired** (independent-perspective Required #1, arch F2 anticipatory) — `LIVE_FOLD_LOOKBACK_MINUTES = 10` constant; the live route handler now passes `since = now - 10min` to `_extract_live_events`; the helper additionally short-circuits on file `mtime < since` so the 94MB walk is replaced by a recent-files walk. Phase 2's background watcher replaces the cutoff with an incremental tail.
2. **`_RUNWAY_LABEL` dict** (qa F2 semantic + ux FRICTION-3 accessibility) — runway statuses (`ok`/`amber`/`red`) and lane statuses (`active`/`complete`/`orphaned`) are now distinct lookup tables; the gatekeeper-facing sub-line carries `"OK"`/`"warning"`/`"critical"` instead of leaking the raw constant names.
3. **htmx SHA-384 regression test** (security F1) — `@pytest.mark.regression test_vendored_htmx_sha384_matches_readme_pin` reads the vendored bytes, computes SHA-384, base64-encodes, asserts equality with the README pin. A backdoored swap-in fails immediately; an intentional version bump must update both the file AND the test pin.
4. **ADR linked-discussion paths** (docs F2) — added `discussions/2026-06-07/` prefix to the new Steward gate + spec-review entries so a future contributor can navigate them.
5. **`hx-swap-error="outerHTML"` on shell** (independent-perspective Required #2 / Pre-Mortem 2) — htmx default drops the swap on non-2xx, which would leave the honest-error fragment unreachable; the explicit `hx-swap-error` means a 500 with the error tile is rendered to the user.

Quality gate after fixes: **7/7** (230 tests pass; ledger 25 guards).

## Required Changes (none — all fixes applied pre-commit)

## Advisory Findings — track in BUILD_STATUS for Phase 2 / follow-up

### From qa-specialist (5 advisory)
- **qa F1 (HIGH missing-test)** — `render_live_fragment` and its 5 sub-renderers (`_render_runway_panel`, `_render_agent_lanes_panel`, `_render_agent_lane_row`, `_render_live_stream_panel`, `_render_runway_estimate`) have zero direct render tests. Add parameterized fixture-driven tests covering: empty state (3 absence tiles), amber/red runway, complete subagent lane, orphaned subagent lane, populated live stream, cold-start `est=None`.
- **qa F3 (MED missing-test)** — `_parse_main_session` / `_parse_subagent` have only one integration test. Add tests for: `tool_use/Agent` block → dispatch event; `tool_result` block → result event; `since` cutoff filter; subagent JSONL path; OSError on unreadable file; non-dict items in `content`.
- **qa F4 (MED CI portability)** — `test_routes_leave_hooks_and_settings_byte_unchanged` skips when `.claude/hooks` is absent; create a minimal stub fixture in `tmp_path` so the behavioral AC3 guard runs unconditionally.
- **qa F5 (MED missing-test)** — CORS same-origin-only is configured but not asserted by any test; add an OPTIONS preflight test with a foreign `Origin` and assert no `Access-Control-Allow-Origin: *`.
- **qa F6 (LOW missing-edge-case)** — the `since` parameter boundary (strict `<` vs `<=`) is now load-bearing because the route uses it. Add a parametrized test: events at `t-1`, `t`, `t+1` with `since=t`; assert only `t` and `t+1` are returned.
- **qa F7 (LOW missing-test)** — `retrospective_fragment`'s general `Exception` branch is untested (only `OperationalError` covered).

### From security-specialist (1 advisory)
- **security F2 (LOW observation)** — no `Content-Security-Policy` header on responses. Given the aggressive `_esc` seam + vendored assets, this is low priority for a loopback-only tool. Add `default-src 'self'; script-src 'self'; style-src 'unsafe-inline'` as defense-in-depth.

### From architecture-consultant (3 advisory)
- **arch F1 (MED pattern-inconsistency)** — A-ARCH1 public surface is internally inconsistent: `parse_timestamp` + `coerce_int` are also consumed by the daemon (lines 200, 215-218, 259, 274-277) but lack the "Promoted to public in the A-ARCH1 promotion" docstring footer the other 4 carry. Add the footer + include in the contract test in `test_dashboard_server.py`; optional `__all__` entry to make the public surface one grep-able spot.
- **arch F2 (MED drift, anticipatory)** — lazy-per-request fold has NO event-source seam. Phase 2's background watcher will require route-handler rewrite. Add `event_source: Callable[[], list[LiveEvent]] | None = None` parameter to `create_app`, default to current behavior; Phase 2 swap = one constructor arg.
- **arch F3 (LOW dead-code)** — `dashboard_server.py:128` `_connect_readonly` is duplicated from `scripts/telemetry/dashboard.py:88` and UNUSED in current routes (daemon delegates to `assemble_dashboard_data`). Delete now per Principle #8; promote when 2nd actual consumer appears.

### From ux-evaluator (5 advisory)
- **FRICTION-1 (HIGH dead-end)** — first-paint loading state visually IDENTICAL to honest-absence tile; add `.tile[data-state="loading"]` CSS rule with pulsing-opacity animation + change copy to "Connecting to live session data — updates every 3 s".
- **FRICTION-2 (HIGH visual-hierarchy)** — main session row has zero visual differentiation from dispatched subagent rows; add `primary` badge + subtle green tint on first active row (color + position, WCAG-safe).
- **FRICTION-4 (MED dead-end)** — `/fragments/retrospective` is a live route but NOT reachable from the shell UI; add nav link or embed below live section via second polling section.
- **FRICTION-5 (LOW)** — Live stream "Kind" column shows raw `message`/`dispatch`/`result` internal event names; add 1-line legend mapping.
- **FRICTION-6 (LOW platform)** — `_otel_link` opens new tab without warning; change label to `"enable OpenTelemetry (opens in new tab)"`.

### From docs-knowledge (3 advisory)
- **docs F1 (MED missing-adr/undiscoverable)** — FRAMEWORK_SPECIFICATION changelog has no entry for ADR-0020 (entire Telemetry & Oversight component invisible). Add 2 changelog rows (2026-06-05 for ADR-0020 / 2026-06-07 for Layer B live daemon form-factor).
- **docs F3 (LOW claude-md)** — CLAUDE.md Pointers section has no entry for Telemetry & Oversight; add: "Telemetry & Oversight (ADR-0020): cost (A1), failure signals (A2), value-vs-subscription (A3), Layer B live dashboard → `scripts/telemetry/dashboard_server.py`; pure model → `src/telemetry/`".
- **docs F4 (LOW promotion candidate)** — leverage fabricated-zero bug is a generalizable display-surface honesty pattern; promote to `memory/lessons/` with developer approval per Principle #7.

### From independent-perspective (3 advisory)
- **indep #3 (Recommended)** — resolve dual-existence of `scripts/telemetry/dashboard.py` (the old static script is still present + functional after Phase 1; spec arch F5 said it "retires INTO --render-static mode" which is Phase 5).
- **indep #4 (Nice-to-have)** — monkeypatch `sqlite3.connect` regression test asserting every connect URI carries `?mode=ro`.
- **indep #5 (Documentation honesty)** — edit `_extract_live_events` docstring to drop "the polling interval bounds load" (the interval bounds frequency, not cost-per-call).

## Speculative Findings — Lower Confidence

| Finding | Specialist | Confidence | Why retained |
|---|---|---|---|
| Lazy-fold-on-94MB usability concern | independent-perspective | 0.74 | Below the 0.80 speculative threshold, but the finding led directly to the most impactful pre-commit fix; retained in main findings because the concrete repo measurement (255 subagent JSONLs / 94MB) is observable and reproducible. |

## Strengths (consensus across specialists)

- **Defense-in-depth on the bind invariant** is real: three independent layers (CLI absence of `--host`, runtime guard before socket open, `uvicorn.Config` post-normalization check). Security-specialist verified each.
- **Middleware ordering is correct and verified by test** — `HostHeaderGuard` is added last = runs first in Starlette's reverse-order. A future refactor that reverses registration fails the test.
- **`live.py` purity is genuinely OBVIOUS** — small module, frozen dataclasses everywhere, explicit docstring contract, import-graph regression test. AC14 is load-bearing, not ceremonial.
- **`_esc` seam is consistent** — every dynamic interpolation site across both static and live renderers passes through one function. A future raw f-string interpolation would be visible.
- **`_connect_readonly` uses `file:...?mode=ro`** — driver-level read-only, not convention. AC5 enforced at the SQLite layer.
- **Honest-absence visual state preserved in live panels** — cold-start runway renders "not enough data yet" rather than a fabricated 0; the C4 anti-pattern (ADR-0020) is consistently honored.
- **The `mark_orphans` non-call comment** correctly names Phase 2's prerequisite — restraint that distinguishes a thoughtful phase boundary from a corner cut.
- **Regression-ledger entries are exemplary** — each one explains the *why* (what the test would catch if violated) + names canary tests.

## Education Gate

**Recommendation**: walkthrough + quiz on the *invariant story* (not the implementation). The 9 Steward conditions encode the binding contract — a developer who can name AC2 / AC3 / AC5 / AC6 / AC8 + describe what would break if each were relaxed is the right Bloom's-level understand-and-explain mastery. The implementation specifics (HostHeaderGuard, `_RUNWAY_LABEL`, `LIVE_FOLD_LOOKBACK_MINUTES`) are walkthrough territory; the invariants are quiz territory.

Run: `/walkthrough scripts/telemetry/dashboard_server.py src/telemetry/live.py` then `/quiz` on the AC1-AC9 invariants.
