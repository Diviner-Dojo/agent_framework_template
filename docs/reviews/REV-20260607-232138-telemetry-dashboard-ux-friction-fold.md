---
review_id: REV-20260607-232138
discussion_id: DISC-20260607-232138-review-telemetry-dashboard-ux-friction-fold
date: 2026-06-07
risk_level: low
verdict: APPROVE-WITH-CHANGES (all changes applied in-session)
panel: [ux-evaluator, qa-specialist]
scope: src/telemetry/dashboard.py + tests/test_telemetry.py + tests/test_dashboard_server.py — UX polish folding REV-20260607-200447 ux FRICTION-1 / FRICTION-2 / FRICTION-4 (Layer B live dashboard daemon, Phase 1 follow-up)
---

# Review — Telemetry Layer B dashboard, UX friction fold (FRICTION-1 / 2 / 4)

## Change under review
Focused UX polish on the Phase 1 live dashboard daemon (`94928ab`) addressing three
ux-evaluator advisories from REV-20260607-200447:

- **FRICTION-1 (HIGH dead-end)** — first-paint loading state was visually identical
  to the honest-absence tile (both used `tile--absent` dashed-border vocabulary), so
  a transient htmx delay or a brief 5xx read as "the analyzer hasn't run." Fix: new
  distinct `tile--loading` class (solid accent border + pulsing-opacity animation +
  `prefers-reduced-motion` guard) plus copy `"Connecting to live session data —
  updates every 3 s"`.
- **FRICTION-2 (HIGH visual-hierarchy)** — the main session row was indistinguishable
  from dispatched subagent rows in the agent-lanes panel. Fix: `lane--primary` class
  + a `primary` text badge for main-lane rows. The badge text is the load-bearing
  differentiator (WCAG 1.4.1 compliant for colourblind / dim-display readers); the
  green left-border + 4% green tint are decorative reinforcement only.
- **FRICTION-4 (MED dead-end)** — `/fragments/retrospective` is a live route but had
  no UI affordance. Fix: a `<nav>` link in the shell header (outside the htmx swap
  target so a poll cannot replace it).

Six new direct-render tests (5 in `tests/test_telemetry.py`, 1 in
`tests/test_dashboard_server.py`); all six tagged `@pytest.mark.regression`. Also
a partial bite of qa F1 from REV-20260607-200447 (first direct render tests for
`render_live_fragment` / `render_live_shell_html`).

Files:
- `src/telemetry/dashboard.py` — `_render_agent_lane_row` branches on
  `lane.kind == "main"`; `render_live_shell_html` adds `<nav>` + uses `tile--loading`;
  `_LIVE_CSS` adds 6 rules (loading tile + reduced-motion guard + lane-primary tint +
  primary badge + nav styling).
- `tests/test_telemetry.py` — 5 regression tests.
- `tests/test_dashboard_server.py` — 1 end-to-end regression test.

## Verdicts
- **ux-evaluator — APPROVE-WITH-CHANGES (0.91).** All three advisories substantively
  resolved; no UX regressions. One Required item (dual-channel intent at the row level)
  + 2 Advisory polish notes.
- **qa-specialist — APPROVE-WITH-CHANGES (0.88).** Tests are meaningful and behavioural;
  escaping discipline (spec C6) intact; the fold layer already prevents the
  "subagent coincidentally has `lane_id == 'main'`" scenario by construction. 2 Low
  advisories (missing regression markers, fragile sub-row split, weaker server-test
  negative guard).

## Findings & resolution
| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| ux-1 | Required (MED) | `tr.lane--primary` row tint is colour-only; the badge is the load-bearing dual channel. Code comment overstated the row's role. | **Applied** — docstring at `_render_agent_lane_row` reworded: badge is load-bearing; row tint is decorative reinforcement (`src/telemetry/dashboard.py:775-783`). |
| ux-2 | Advisory (LOW) | `&rarr;` arrow may be announced "right arrow" by screen readers. | **Applied** — `aria-label="Retrospective view"` on the nav link. |
| ux-3 | Advisory (LOW) | Hardcoded `"3 s"` in copy could rot if `LIVE_POLL_INTERVAL_S` changes. | **Accepted, no action** — Phase 2 will revisit if the interval becomes runtime-configurable. |
| ux-4 | Advisory (LOW) | `lane--active` green badge + `lane--primary` green left-border coexist; reviewer self-resolved (visually distinct semantics). | No action needed. |
| qa-1 | Low | `sub_row = html.split("sub-1", 1)[1]…` is a fragile boundary if the literal `"sub-1"` ever appears outside the lane-id cell. | **Applied** — robust row isolation: locate the `<td>sub-rowA</td>` literal, walk back to the enclosing `<tr `, and slice to the next `</tr>`. Fixture renamed to `sub-rowA` so the anchor is unambiguous. |
| qa-2 | Low | None of the 6 new tests carried `@pytest.mark.regression` — they guard a formal review's advisories. | **Applied** — `@pytest.mark.regression` on all 6 tests. |
| qa-3 | Low | `test_root_exposes_retrospective_link_and_distinct_loading_tile` lacked a negative `tile--absent not in placeholder` guard mirroring the unit test. | **Applied** — added the negative guard at the server boundary. |
| qa-4 | Answered | Tile-loading negative-guard false-positive risk if future JS embeds `tile--absent` in the loading section. | No action — placeholder is pure HTML; revisit if Phase 2 adds inline JS. |
| qa-5 | Answered | "Subagent coincidentally has `lane_id == 'main'`" scenario. | No action — fold layer (`src/telemetry/live.py:318-321`) routes any `lane_id == "main"` event into `state.main`, never `state.agents`; architecturally impossible. |

## Outcome
214 telemetry+server tests green (6 new regression tests, all pass); full quality
gate **7/7** (formatting, lint, tests, coverage ≥80%, ADR completeness, review-existence,
ledger, BUILD_STATUS freshness). All folded changes are in the working tree.

This commit moves 3 advisories from REV-20260607-200447's "16 tracked for follow-up"
list to "closed"; 13 advisories remain open for Phase 2 / future polish (qa F1 partial,
qa F3-F7, security F2, arch F1-F3, ux FRICTION-5/6, docs F1/F3/F4, indep #3/#4/#5).

Approved to commit on `fix/c-gate-log-integrity` (no push).
