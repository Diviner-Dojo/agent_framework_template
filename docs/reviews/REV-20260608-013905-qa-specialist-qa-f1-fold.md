---
id: REV-20260608-013905-qa-specialist-qa-f1-fold
date: 2026-06-08
agent: qa-specialist
branch: fix/c-gate-log-integrity
scope: tests/test_telemetry.py (qa F1 fold section, ~line 3072+), memory/bugs/regression-ledger.md (row 64)
source_advisory: REV-20260607-200447 qa F1
session: 10i
verdict: APPROVE-WITH-CHANGES
confidence: 0.88
---

# QA Specialist Review — qa F1 Fold (Session 10i)

## Verdict

**APPROVE-WITH-CHANGES** (confidence 0.88). The 23 tests are well-structured, meaningfully asserted,
and isolated. Two findings require in-session attention before commit: one weak assertion that
currently passes vacuously for any future `LANE_ORPHANED` rename and one missing unknown-status
fallback test for `_render_agent_lane_row`. Both are small additions, not rewrites.

---

## Test Adequacy

The fold correctly addresses the advisory premise: each of the 5 sub-renderers now has direct,
parameterized coverage independent of the fold layer. The `_lane()` helper is clean and
appropriately scoped. Isolation is complete — all tests are pure function calls over frozen
dataclasses with no shared mutable state, no IO, and no time.time() non-determinism.
Assertion quality is high overall; the ordering tests (dispatch order, most-recent-first) are
the best class of regression guard here.

---

## Findings

### F1 MED — Weak Badge Assertion Couples to Current Constant Values, Misses Future-Rename Gap

**Category**: weak-assertion
**Location**: `tests/test_telemetry.py` line 3344
**Fold-action**: Fix in-session

The parametrized `test_render_agent_lane_row_emits_status_class_and_badge_label` asserts:

```python
assert f'<span class="lane-badge">{status}</span>' in row
```

Where `status` is the raw constant value (`"active"` / `"complete"` / `"orphaned"`). The comment
on lines 3341-3344 acknowledges that "the raw constant value happens to match the label for these
three today" — and that is precisely the problem. The `_LANE_STATUS_LABEL` map exists BECAUSE the
constants and labels are allowed to diverge. The test asserts the rendered output equals
`{status}` (the constant), not `{label}` (what `_LANE_STATUS_LABEL` would return). If
`LANE_ORPHANED = "orphaned"` were renamed to `LANE_ORPHANED = "orphan"` for brevity while the
map kept `"orphaned"` as the gatekeeper label, the test would assert the wrong thing and pass
on the regression (it would look for `orphan`, which is gone from the output — but for the wrong
reason). The guard the comment says it provides ("guard against a future divergence between constant
and label") is not actually present: the test would fail on divergence for the wrong reason (not
because the label is wrong, but because the badge text changed).

**Fix**: Derive the expected badge text from `_LANE_STATUS_LABEL` directly in the test, not from
the raw constant. Since `_LANE_STATUS_LABEL` is a private symbol, the cleanest approach is to
parametrize with explicit `(status, expected_css_class, expected_badge_text)` triples. The
`"active"/"complete"/"orphaned"` badge texts are the contract being pinned — spell them out
explicitly in the parametrize table rather than deriving them from the constant that also changes:

```python
@pytest.mark.parametrize(
    ("status", "expected_label_class", "expected_badge_text"),
    [
        (LANE_ACTIVE, "lane--active", "active"),
        (LANE_COMPLETE, "lane--complete", "complete"),
        (LANE_ORPHANED, "lane--orphaned", "orphaned"),
    ],
)
def test_render_agent_lane_row_emits_status_class_and_badge_label(...):
    ...
    assert expected_label_class in row
    assert f'<span class="lane-badge">{expected_badge_text}</span>' in row
```

This pins the human-facing badge text as an explicit contract value, independent of whatever
the constant string happens to be.

---

### F2 MED — Unknown Lane Status Fallback Branch Has No Direct Test

**Category**: missing-edge-case
**Location**: `src/telemetry/dashboard.py` line 788 / `tests/test_telemetry.py`
**Fold-action**: Fix in-session

`_render_agent_lane_row` uses `_LANE_STATUS_LABEL.get(lane.status, lane.status)` — the fallback
is the raw constant, which also becomes the CSS class suffix (`f"lane--{status_label}"`). This
means an unknown status (e.g. a future `"pending"` state added to `live.py` before the dashboard
map is updated) does three things: (a) surfaces the raw constant as the badge text, (b) generates
`lane--pending` as the CSS class (which has no styling rule), and (c) generates `lane--pending` as
the row class modifier (same). These three behaviors are the contract of the fallback path and none
of the 23 tests exercise it. The advisory's coverage breakdown enumerates "active / complete /
orphaned status" explicitly but does not mention the fallback.

This is not a theoretical concern: the `_LANE_STATUS_LABEL` map comment at line 640 does not
document it as exhaustive, and a future `live.py` extension is the expected evolution path.

**Fix**: Add one test with an out-of-map status string (e.g. `"pending"`):

```python
@pytest.mark.regression
def test_render_agent_lane_row_unknown_status_falls_back_to_raw_constant() -> None:
    lane = _lane("sub-test", "agent", "pending", agent_type="qa-specialist")
    row = _render_agent_lane_row(lane)
    # Fallback: raw constant becomes both the CSS class suffix and the badge text.
    assert "lane--pending" in row
    assert '<span class="lane-badge">pending</span>' in row
```

---

### F3 LOW — `_render_runway_panel` RUNWAY_OK Negative-Label Check Is Skipped

**Category**: weak-assertion
**Location**: `tests/test_telemetry.py` line 3180
**Fold-action**: Defer-as-advisory

The `if status != RUNWAY_OK` guard on the "raw constant must NOT leak" assertion means the
RUNWAY_OK case (`status = "ok"`, `label = "OK"`) has no negative guard. RUNWAY_OK is the
lowest-risk path (the label IS different from the constant: `"ok"` vs `"OK"`) so the existing
`assert f"&middot; {label}" in panel` would catch a regression that leaked `"ok"` as the label
instead of `"OK"` anyway. The risk is low and the asymmetry is defensible given the amber/red
constants are the ones that actually caused the FRICTION-3 bug. Defer.

---

### F4 LOW — `_render_runway_estimate` Assertion on `<strong>` Is Intent-Over-Markup in Comment Only

**Category**: intent-vs-markup-pinning
**Location**: `tests/test_telemetry.py` line 3251-3253
**Fold-action**: Defer-as-advisory

`test_render_runway_estimate_with_value_renders_strong_int_and_method_note` asserts
`"<strong>42</strong>"` directly. The docstring at line 3245-3249 explicitly justifies this as
load-bearing: a restyle away from `<strong>` to CSS-only weight would silently break the
typographic emphasis that distinguishes a rolling-average estimate from surrounding prose. This is
a deliberate, documented exception to the intent-over-markup principle, not an oversight.
The past-session pattern of folding these is applicable here only if there is a concrete design
intent to allow CSS rewrites; absent that signal, the current pinning is correct. Mark advisory
only.

---

### F5 INFO — `render_live_fragment` Composition Test Does Not Pin Section Count = 1 for Non-Empty State

**Category**: missing-edge-case
**Location**: `tests/test_telemetry.py` line 3575
**Fold-action**: Defer-as-advisory

`test_render_live_fragment_composes_runway_then_lanes_then_stream` asserts panel ordering and
`data-state="data"` count = 3 for a fully-populated state, but does not assert
`html.count('<section id="live-section"') == 1`. The empty-state composition test (line 3563)
DOES assert this. Adding it to the non-empty case would make the htmx swap-target shape contract
symmetric. Extremely low risk given the `render_live_fragment` wrapper is 8 lines — defer.

---

### F6 INFO — Ledger Entry Correct and Complete

**Category**: regression-ledger
**Location**: `memory/bugs/regression-ledger.md` row 64
**Fold-action**: No action needed

The ledger entry is crisp. The "why each branch matters" is documented at the right level of
specificity for each of the 6 sub-renderer coverage categories. The 19-test function name list in
the `Test Function` column is accurate against the tests present in the file. No gaps.

---

## Strengths

- **Isolation is perfect**: All 23 tests operate on frozen dataclasses with no IO, no shared
  mutable state, and no time-dependent values (the `datetime` fixtures are constructed with
  explicit UTC values).
- **Ordering tests are the strongest guards**: `test_render_agent_lanes_panel_orders_main_first_then_subagents_in_dispatch_order`
  and `test_render_live_stream_panel_emits_rows_most_recent_first` use `str.index()` comparisons
  that would fail on any scramble, not just a full reversal.
- **XSS escape guards are well-designed**: Both escape tests (`_render_agent_lane_row` 3-cell
  and `_render_live_stream_panel` 2-cell) pin the exact escaped-occurrence count, which catches
  a partial de-escaping regression that would slip past `"<script>" not in row` alone.
- **Absence tile negative pinning is thorough**: Every absence-path test negates both `<table`
  AND `<tbody>` (a renderer that emitted the shell without rows would slip past a single guard).
- **Intent-over-markup applied correctly to copy fragments**: The runway status copy assertions
  use fragment substrings (`"Plenty of headroom"`) rather than full-string matches, so they
  survive punctuation tweaks without false-positives.
- **The `_lane()` helper has the right defaults**: Defaulting `model` to `"claude-opus-4-7"`
  rather than `None` prevents the em-dash branch from triggering unexpectedly in tests that
  are not about the absence path.

---

## Summary

Two findings require in-session fixes before commit:

- **F1 MED (in-session)**: Parametrize `test_render_agent_lane_row_emits_status_class_and_badge_label`
  with explicit badge-text values, not the raw constant variable.
- **F2 MED (in-session)**: Add one `test_render_agent_lane_row_unknown_status_falls_back_to_raw_constant`
  test for the `_LANE_STATUS_LABEL.get(..., lane.status)` fallback branch.

Four advisory findings (F3/F4/F5 LOW/INFO) can defer without blocking the commit.
