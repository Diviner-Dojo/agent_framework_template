"""Tests for the Phase 2 weekly trends chart slice (REV-20260608-053032).

Three concerns covered here so the parent ``tests/test_telemetry.py`` does not
balloon further:

* :mod:`src.telemetry.weekly` aggregator — pure ISO-calendar bucket algebra,
  including the year-boundary edge case (Dec 28 -> ISO W53; Jan 4 -> next
  year's W01) and the defensive-skip + warning policy for rows whose
  ``discussion_id`` is missing from the ``created_at`` lookup.
* :func:`src.telemetry.dashboard._json_in_script` — the Rule-of-Three
  helper extracted at this slice. Its single test surface asserts ALL FOUR
  steps of the escape chain on a hostile payload.
* :func:`src.telemetry.dashboard.render_weekly_trends_chart_panel` — the
  absence-vs-populated paths, the prior-window delta-caption edge cases,
  WCAG fallback content, ``</script>`` injection resistance, non-finite
  cost rejection, and the panel-placement contract.

Reuses the regression-mark discipline from the parent test module.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import UTC, date, datetime

import pytest

from src.telemetry.cost import ModelTokenRow
from src.telemetry.dashboard import (
    LiveFragmentPanels,
    _json_in_script,
    _render_weekly_delta_caption,
    render_live_fragment,
    render_weekly_trends_chart_panel,
)
from src.telemetry.live import LiveState
from src.telemetry.pricing import PricingTable, TierRates
from src.telemetry.weekly import (
    WeeklyTierBucket,
    WeeklyTotal,
    WeeklyTrends,
    aggregate_by_week,
    iso_week_start,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _pricing() -> PricingTable:
    """Build a small two-tier pricing table for the aggregator tests.

    Mirrors the YAML shape: ``opus`` has rates, ``sonnet`` has rates, the
    literal ``unknown`` tier has no entry so its rows fall through to
    ``uncosted``. Keeping the table local keeps the tests deterministic and
    independent of any future change to ``config/model_pricing.yaml``.
    """
    return PricingTable(
        models={"claude-opus-4-7": "opus", "claude-sonnet-4-6": "sonnet"},
        tiers={
            "opus": TierRates(
                input=15.0,
                output=75.0,
                cache_read_multiplier=0.1,
                cache_create_multiplier=1.25,
            ),
            "sonnet": TierRates(
                input=3.0,
                output=15.0,
                cache_read_multiplier=0.1,
                cache_create_multiplier=1.25,
            ),
        },
    )


def _row(
    discussion_id: str,
    *,
    tier: str = "opus",
    tokens_in: int = 1_000,
    tokens_out: int = 1_000,
) -> ModelTokenRow:
    """One synthetic ``discussion_model_tokens`` row."""
    return ModelTokenRow(
        discussion_id=discussion_id,
        model_id={"opus": "claude-opus-4-7", "sonnet": "claude-sonnet-4-6"}.get(tier, "x"),
        tier=tier,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_read_tokens=0,
        cache_create_tokens=0,
        message_count=1,
    )


# --------------------------------------------------------------------------- #
# iso_week_start + aggregate_by_week
# --------------------------------------------------------------------------- #


def test_iso_week_start_returns_monday_of_iso_week() -> None:
    """Wednesday 2026-06-10 belongs to the week starting Monday 2026-06-08."""
    moment = datetime(2026, 6, 10, 14, 30, 0, tzinfo=UTC)
    assert iso_week_start(moment) == date(2026, 6, 8)


def test_iso_week_start_handles_sunday_boundary() -> None:
    """ISO week ends Sunday; Sunday belongs to the week starting that prior Monday."""
    sunday = datetime(2026, 6, 14, 23, 59, 0, tzinfo=UTC)
    monday = datetime(2026, 6, 15, 0, 0, 0, tzinfo=UTC)
    assert iso_week_start(sunday) == date(2026, 6, 8)
    assert iso_week_start(monday) == date(2026, 6, 15)


@pytest.mark.regression
def test_iso_week_start_handles_year_boundary_w53_to_w01() -> None:
    """Dec 28 2026 -> ISO 2026-W53; Jan 4 2027 -> ISO 2027-W01.

    The ISO 8601 year-boundary case is the subtlest one and the source of
    off-by-one bugs in January aggregations. Pinning both sides of the
    boundary is the regression guard against an iso-calendar refactor that
    accidentally moves to a Sunday-start week or to the Gregorian year.
    """
    dec_28 = datetime(2026, 12, 28, 12, 0, 0, tzinfo=UTC)  # Monday of 2026-W53
    jan_4 = datetime(2027, 1, 4, 12, 0, 0, tzinfo=UTC)  # Monday of 2027-W01
    assert iso_week_start(dec_28) == date(2026, 12, 28)
    assert iso_week_start(jan_4) == date(2027, 1, 4)
    # The 2026 -> 2027 boundary day itself (Thursday 2026-12-31) belongs to
    # ISO 2026-W53 (its Monday is 2026-12-28).
    boundary = datetime(2026, 12, 31, 23, 0, 0, tzinfo=UTC)
    assert iso_week_start(boundary) == date(2026, 12, 28)


def test_aggregate_by_week_empty_rows_returns_empty_trends() -> None:
    trends = aggregate_by_week([], {}, _pricing())
    assert trends == WeeklyTrends(weeks=())


def test_aggregate_by_week_single_row_single_week() -> None:
    row = _row("DISC-A")
    lookup = {"DISC-A": datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)}
    trends = aggregate_by_week([row], lookup, _pricing())
    assert len(trends.weeks) == 1
    week = trends.weeks[0]
    assert week.week_start == date(2026, 6, 8)
    assert week.priced_cost_usd > 0.0
    assert week.uncosted_tokens == 0
    assert len(week.by_tier) == 1
    assert week.by_tier[0].tier == "opus"


def test_aggregate_by_week_multiple_discussions_same_week_sum() -> None:
    rows = [
        _row("DISC-A", tier="opus", tokens_in=1_000, tokens_out=1_000),
        _row("DISC-B", tier="opus", tokens_in=2_000, tokens_out=2_000),
    ]
    lookup = {
        "DISC-A": datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC),
        "DISC-B": datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC),
    }
    trends = aggregate_by_week(rows, lookup, _pricing())
    assert len(trends.weeks) == 1
    week = trends.weeks[0]
    assert week.by_tier[0].total_tokens == 6_000
    assert week.total_tokens == 6_000


def test_aggregate_by_week_multiple_weeks_sorted_ascending() -> None:
    rows = [
        _row("DISC-EARLY", tier="opus"),
        _row("DISC-LATE", tier="opus"),
        _row("DISC-MID", tier="opus"),
    ]
    lookup = {
        "DISC-LATE": datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC),
        "DISC-EARLY": datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC),
        "DISC-MID": datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC),
    }
    trends = aggregate_by_week(rows, lookup, _pricing())
    week_starts = [w.week_start for w in trends.weeks]
    assert week_starts == [date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 22)]


def test_aggregate_by_week_unknown_tier_flows_to_uncosted_tokens() -> None:
    """A row with tier='unknown' contributes tokens to uncosted_tokens, cost stays None."""
    row = ModelTokenRow(
        discussion_id="DISC-U",
        model_id="some-future-model",
        tier="unknown",
        tokens_in=500,
        tokens_out=500,
        cache_read_tokens=0,
        cache_create_tokens=0,
        message_count=1,
    )
    lookup = {"DISC-U": datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)}
    trends = aggregate_by_week([row], lookup, _pricing())
    week = trends.weeks[0]
    assert week.priced_cost_usd == 0.0
    assert week.uncosted_tokens == 1_000
    unknown_bucket = next(b for b in week.by_tier if b.tier == "unknown")
    assert unknown_bucket.cost_usd is None


def test_aggregate_by_week_known_tier_missing_from_pricing_flows_to_uncosted() -> None:
    """A row with a known-string tier that the pricing table lacks is uncosted.

    Mirrors the ``cost_usd`` semantics: if ``pricing.cost_usd(tier, ...)``
    returns ``None`` (no rates for the tier), the row's tokens flow to
    ``WeeklyTotal.uncosted_tokens`` and the per-tier bucket carries
    ``cost_usd=None``. Honors ADR-0020 "uncosted ≠ $0".
    """
    pricing = _pricing()  # no 'haiku' entry
    row = _row("DISC-H", tier="haiku", tokens_in=300, tokens_out=300)
    lookup = {"DISC-H": datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)}
    trends = aggregate_by_week([row], lookup, pricing)
    week = trends.weeks[0]
    haiku_bucket = next(b for b in week.by_tier if b.tier == "haiku")
    assert haiku_bucket.cost_usd is None
    assert week.uncosted_tokens == 600
    assert week.priced_cost_usd == 0.0


def test_aggregate_by_week_skips_missing_created_at_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Row whose discussion_id is missing from the lookup is skipped + logged.

    Defensive-skip policy (REV-20260608-053032 qa L2 fold): the transport
    layer's JOIN should never produce orphan rows, but if a regression makes
    it possible, the aggregator skips the row and logs a WARNING — silent
    drop would hide the transport-layer regression.
    """
    rows = [_row("DISC-PRESENT"), _row("DISC-MISSING")]
    lookup = {"DISC-PRESENT": datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)}
    with caplog.at_level(logging.WARNING, logger="src.telemetry.weekly"):
        trends = aggregate_by_week(rows, lookup, _pricing())
    assert len(trends.weeks) == 1
    assert "DISC-MISSING" in caplog.text


# --------------------------------------------------------------------------- #
# _json_in_script helper (Rule-of-Three extraction)
# --------------------------------------------------------------------------- #


def test_json_in_script_applies_all_four_escape_steps() -> None:
    """Hostile payload exercises ALL four steps: allow_nan + 3 string escapes.

    The helper consolidates the per-turn chart's prior 4-step inline chain
    (REV-20260608-025749 + REV-20260608-042729 folds). This single test is
    the spec for both chart consumers — if any one step regresses, both
    chart panels are affected.
    """
    payload = [
        {"text": "</script><script>alert(1)</script>"},
        {"comment": "<!--evil--><!--more-->"},
        {"closer": "-->trailing"},
    ]
    serialised = _json_in_script(payload)
    # </ MUST be escaped (HTML5 raw-text close tag).
    assert "</" not in serialised
    assert "<\\/" in serialised
    # <!-- and --> MUST be escaped (HTML5 comment mode).
    assert "<!--" not in serialised
    assert "-->" not in serialised
    assert "<\\!--" in serialised
    assert "--\\>" in serialised
    # The escaped form still round-trips through JSON.parse-equivalent.
    # Reverse the three replacements to feed json.loads.
    raw = serialised.replace("<\\/", "</").replace("<\\!--", "<!--").replace("--\\>", "-->")
    assert json.loads(raw) == payload


def test_json_in_script_rejects_non_finite_floats() -> None:
    """``allow_nan=False`` converts NaN/Inf into a loud ValueError."""
    with pytest.raises(ValueError):
        _json_in_script([{"v": math.nan}])
    with pytest.raises(ValueError):
        _json_in_script([{"v": math.inf}])
    with pytest.raises(ValueError):
        _json_in_script([{"v": -math.inf}])


def test_json_in_script_uses_compact_separators() -> None:
    """``separators=(",", ":")`` keeps the payload small (no whitespace)."""
    out = _json_in_script([{"a": 1, "b": 2}])
    assert ", " not in out
    assert ": " not in out


# --------------------------------------------------------------------------- #
# render_weekly_trends_chart_panel + _render_weekly_delta_caption
# --------------------------------------------------------------------------- #


def _trends(*weeks_data: tuple[date, float, int, int, list[WeeklyTierBucket]]) -> WeeklyTrends:
    """Build a :class:`WeeklyTrends` from compact tuples for test ergonomics."""
    weeks = tuple(
        WeeklyTotal(
            week_start=ws,
            priced_cost_usd=priced,
            total_tokens=total,
            uncosted_tokens=uncosted,
            by_tier=tuple(by_tier),
        )
        for ws, priced, total, uncosted, by_tier in weeks_data
    )
    return WeeklyTrends(weeks=weeks)


def testrender_weekly_trends_chart_panel_empty_renders_absence_tile() -> None:
    panel = render_weekly_trends_chart_panel(WeeklyTrends(weeks=()))
    assert 'data-state="absent"' in panel
    assert "No stored cost rows yet." in panel
    assert "<canvas" not in panel
    assert 'type="application/json"' not in panel


def testrender_weekly_trends_chart_panel_populated_emits_canvas_and_data_block() -> None:
    trends = _trends(
        (
            date(2026, 6, 8),
            1.23,
            5_000,
            0,
            [WeeklyTierBucket(date(2026, 6, 8), "opus", 5_000, 1.23)],
        ),
    )
    panel = render_weekly_trends_chart_panel(trends)
    assert 'data-state="loading"' in panel
    assert "tile--loading" in panel
    assert 'id="weekly-trends-chart"' in panel
    assert 'id="weekly-trends-data"' in panel
    assert 'type="application/json"' in panel
    assert "chart-rendering-target" in panel
    assert "Weekly cost trends" in panel


def testrender_weekly_trends_chart_panel_json_payload_carries_required_fields() -> None:
    trends = _trends(
        (
            date(2026, 6, 8),
            1.23,
            5_000,
            500,
            [
                WeeklyTierBucket(date(2026, 6, 8), "opus", 4_500, 1.23),
                WeeklyTierBucket(date(2026, 6, 8), "unknown", 500, None),
            ],
        ),
    )
    panel = render_weekly_trends_chart_panel(trends)
    start_marker = '<script id="weekly-trends-data" type="application/json">'
    start = panel.index(start_marker) + len(start_marker)
    end = panel.index("</script>", start)
    raw = panel[start:end].replace("<\\/", "</").replace("<\\!--", "<!--").replace("--\\>", "-->")
    points = json.loads(raw)
    assert len(points) == 1
    assert points[0]["week_start"] == "2026-06-08"
    assert points[0]["priced_cost_usd"] == pytest.approx(1.23)
    assert points[0]["total_tokens"] == 5_000
    assert points[0]["uncosted_tokens"] == 500
    tiers = points[0]["by_tier"]
    assert {t["tier"] for t in tiers} == {"opus", "unknown"}
    unknown = next(t for t in tiers if t["tier"] == "unknown")
    assert unknown["cost_usd"] is None
    assert unknown["tokens"] == 500


def testrender_weekly_trends_chart_panel_canvas_has_accessible_name_and_fallback() -> None:
    """WCAG SC 1.1.1 / 4.1.2 — canvas carries role + aria-label + fallback child."""
    trends = _trends(
        (date(2026, 6, 8), 1.0, 1, 0, [WeeklyTierBucket(date(2026, 6, 8), "opus", 1, 1.0)]),
    )
    panel = render_weekly_trends_chart_panel(trends)
    assert 'role="img"' in panel
    assert "aria-label=" in panel
    # The fallback <p> inside the canvas is the textual alternative for
    # assistive tech / users without JS — pin its content.
    assert "Weekly cost trends chart (data available" in panel


def testrender_weekly_trends_chart_panel_rejects_non_finite_cost() -> None:
    """Non-finite priced_cost_usd surfaces as a ValueError at render time."""
    trends = _trends(
        (
            date(2026, 6, 8),
            math.inf,
            1_000,
            0,
            [WeeklyTierBucket(date(2026, 6, 8), "opus", 1_000, math.inf)],
        ),
    )
    with pytest.raises(ValueError):
        render_weekly_trends_chart_panel(trends)


def testrender_weekly_trends_chart_panel_resists_script_close_injection_in_tier_name() -> None:
    """A transcript-shaped string in tier name cannot close the data block."""
    hostile = "</script><script>alert(1)</script>"
    trends = _trends(
        (
            date(2026, 6, 8),
            0.0,
            10,
            10,
            [WeeklyTierBucket(date(2026, 6, 8), hostile, 10, None)],
        ),
    )
    panel = render_weekly_trends_chart_panel(trends)
    # The data-block contains the escaped form, not the live tag pair.
    start = panel.index('id="weekly-trends-data"')
    end = panel.index("</script>", start)
    data_block = panel[start:end]
    assert "</script>" not in data_block


def test_render_weekly_delta_caption_omitted_when_only_one_week() -> None:
    """Caption omitted when there is no prior week to compare against."""
    weeks = (
        WeeklyTotal(
            week_start=date(2026, 6, 8),
            priced_cost_usd=1.0,
            total_tokens=10,
            uncosted_tokens=0,
            by_tier=(WeeklyTierBucket(date(2026, 6, 8), "opus", 10, 1.0),),
        ),
    )
    assert _render_weekly_delta_caption(weeks) == ""
    # qa F4 fold (REV-20260608-053507): empty tuple also returns "". The
    # function's len(weeks) < 2 guard covers both 0 and 1 — pin the 0 case
    # so a future refactor that tightens the guard to len(weeks) != 1 is
    # caught.
    assert _render_weekly_delta_caption(()) == ""


def test_render_weekly_delta_caption_omitted_on_zero_prior_denominator() -> None:
    """qa H1 (REV-20260608-053032): zero prior priced_cost omits caption, no ZeroDivisionError."""
    weeks = (
        WeeklyTotal(
            week_start=date(2026, 6, 8),
            priced_cost_usd=0.0,  # all uncosted in the prior week
            total_tokens=1_000,
            uncosted_tokens=1_000,
            by_tier=(WeeklyTierBucket(date(2026, 6, 8), "unknown", 1_000, None),),
        ),
        WeeklyTotal(
            week_start=date(2026, 6, 15),
            priced_cost_usd=2.5,
            total_tokens=2_000,
            uncosted_tokens=0,
            by_tier=(WeeklyTierBucket(date(2026, 6, 15), "opus", 2_000, 2.5),),
        ),
    )
    assert _render_weekly_delta_caption(weeks) == ""


def test_render_weekly_delta_caption_present_with_percent_when_prior_priced() -> None:
    weeks = (
        WeeklyTotal(
            week_start=date(2026, 6, 8),
            priced_cost_usd=1.0,
            total_tokens=10,
            uncosted_tokens=0,
            by_tier=(WeeklyTierBucket(date(2026, 6, 8), "opus", 10, 1.0),),
        ),
        WeeklyTotal(
            week_start=date(2026, 6, 15),
            priced_cost_usd=1.5,
            total_tokens=15,
            uncosted_tokens=0,
            by_tier=(WeeklyTierBucket(date(2026, 6, 15), "opus", 15, 1.5),),
        ),
    )
    caption = _render_weekly_delta_caption(weeks)
    assert 'class="src weekly-delta"' in caption
    assert "+50.0%" in caption  # (1.5 - 1.0) / 1.0 = +50%


# --------------------------------------------------------------------------- #
# render_live_fragment composition with weekly panel
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_render_live_fragment_includes_weekly_panel_when_supplied() -> None:
    """5-panel composition: runway -> lanes -> stream -> per-turn chart -> weekly chart.

    Pins the broader-after-narrower hierarchy. A future third chart slot
    that placed the weekly chart BEFORE the per-turn chart would fail the
    index-ordering check here.
    """
    weekly_panel = '<div class="tile" data-state="data"><h3>Weekly cost trends</h3></div>'
    html = render_live_fragment(LiveState(), LiveFragmentPanels(weekly_panel_html=weekly_panel))
    assert "Weekly cost trends" in html
    # The weekly panel sits AFTER the per-turn-cost-chart panel — broader
    # window after narrower window.
    per_turn_idx = html.index("<h3>Per-turn cost over time</h3>")
    weekly_idx = html.index("<h3>Weekly cost trends</h3>")
    assert per_turn_idx < weekly_idx


def test_render_live_fragment_omits_weekly_panel_when_kwarg_default() -> None:
    """Backward-compat: callers without weekly_panel_html get the 4-panel composition."""
    html = render_live_fragment(LiveState())
    assert "Weekly cost trends" not in html
