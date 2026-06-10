"""Tests for the model-cost donut panel (SPEC-20260610-015114, Phase 4 Unit 4.2).

Pure-model + render tests for :func:`src.telemetry.dashboard.render_model_cost_donut_panel`,
the :class:`~src.telemetry.dashboard.LiveFragmentPanels` composition fold, and
the ``_donut_slices`` deterministic ordering. The transport-loader tests
(``load_cost_report`` 4-state matrix) and the route/id-pin/SHA tests live in
``tests/test_dashboard_server.py`` (separate-file precedent mirrors
``test_telemetry_weekly.py``).
"""

from __future__ import annotations

import json
import re

import pytest

from src.telemetry.cost import CostReport, TierCost
from src.telemetry.dashboard import (
    LiveFragmentPanels,
    _donut_slices,
    render_live_fragment,
    render_model_cost_donut_panel,
)
from src.telemetry.live import LiveState

# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


def _tier(tier: str, *, cost: float | None = None, tokens: int = 0) -> TierCost:
    """Build a TierCost with all tokens lumped into tokens_in for brevity."""
    return TierCost(tier=tier, tokens_in=tokens, cost_usd=cost)


def _report(*tiers: TierCost) -> CostReport:
    by_tier = {tc.tier: tc for tc in tiers}
    priced = [tc for tc in tiers if tc.cost_usd is not None]
    return CostReport(
        by_tier=by_tier,
        total_cost_usd=sum(tc.cost_usd or 0.0 for tc in priced),
        known_tokens=sum(tc.total_tokens() for tc in priced),
        total_tokens=sum(tc.total_tokens() for tc in tiers),
    )


def _payload(panel: str) -> list[dict]:
    m = re.search(
        r'<script id="model-cost-donut-data" type="application/json">(.*?)</script>',
        panel,
        re.S,
    )
    assert m is not None, "donut data block missing from panel"
    return json.loads(m.group(1))


def _caption(panel: str) -> str:
    m = re.search(r'<p class="note">(.*?)</p>', panel, re.S)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------- #
# render_model_cost_donut_panel — data state (AC1, AC1b, AC2, AC7)
# --------------------------------------------------------------------------- #


def test_donut_panel_multi_tier_emits_canvas_and_payload_fields() -> None:
    # AC1: canvas + data block; one payload entry per tier with the four
    # _DonutSlice fields.
    panel = render_model_cost_donut_panel(
        _report(
            _tier("opus", cost=2.5, tokens=1000),
            _tier("sonnet", cost=0.5, tokens=2000),
            _tier("mystery", tokens=300),
        ),
        True,
    )
    assert 'canvas id="model-cost-donut-chart"' in panel
    entries = _payload(panel)
    assert len(entries) == 3
    for entry in entries:
        assert set(entry) == {"tier", "cost_usd", "tokens", "uncosted"}
    # ux F1 fold (REV this unit): the per-tier dollar figures are also
    # surfaced in an always-visible plain-text line (not hover-only), so
    # keyboard/screen-reader users can reach the numbers.
    assert "Per-tier cost:" in panel
    assert "opus $2.5000" in panel
    assert "sonnet $0.5000" in panel


def test_donut_payload_order_is_deterministic_and_ranked() -> None:
    # AC1 (qa F4 fold): identical reports -> identical JSON arrays (list
    # equality); priced first by cost descending then tier name, uncosted
    # after by tokens descending then tier name.
    report = _report(
        _tier("sonnet", cost=2.0, tokens=10),
        _tier("opus", cost=2.0, tokens=10),
        _tier("haiku", cost=0.5, tokens=10),
        _tier("xtier", tokens=100),
        _tier("atier", tokens=100),
    )
    first = _payload(render_model_cost_donut_panel(report, True))
    second = _payload(render_model_cost_donut_panel(report, True))
    assert first == second
    assert [e["tier"] for e in first] == ["opus", "sonnet", "haiku", "atier", "xtier"]


@pytest.mark.regression
def test_donut_single_priced_tier_has_one_entry_and_no_uncosted_caption() -> None:
    # AC1b (spec qa F3): single-slice donut — exactly one payload entry,
    # uncosted False, and NO uncosted caption rendered.
    panel = render_model_cost_donut_panel(_report(_tier("opus", cost=1.0, tokens=10)), True)
    entries = _payload(panel)
    assert len(entries) == 1
    assert entries[0]["uncosted"] is False
    assert '<p class="note">' not in panel


@pytest.mark.regression
def test_donut_uncosted_tier_is_null_in_payload_and_named_in_caption() -> None:
    # AC2 (ADR-0020): uncosted tier carries cost_usd null + uncosted true in
    # the payload, is named with its token count in the caption, and the
    # caption carries NO dollar figure (uncosted is never rendered as $0 —
    # the only "$0" in the panel is the legend's meta-copy about the
    # discipline itself).
    panel = render_model_cost_donut_panel(
        _report(_tier("opus", cost=1.5, tokens=100), _tier("mystery", tokens=4200)),
        True,
    )
    entries = _payload(panel)
    uncosted = [e for e in entries if e["uncosted"]]
    assert len(uncosted) == 1
    assert uncosted[0]["tier"] == "mystery"
    assert uncosted[0]["cost_usd"] is None
    assert uncosted[0]["tokens"] == 4200
    caption = _caption(panel)
    assert "mystery" in caption
    assert "4,200" in caption
    assert "$" not in caption
    assert "uncosted, not free" in caption


def test_donut_zero_token_uncosted_tier_still_emitted_and_captioned() -> None:
    # Spec R3 (qa F5 fold): a zero-token uncosted tier is emitted with
    # tokens: 0 and named in the caption — never silently dropped.
    # (Reachable here by direct construction; build_cost_report only creates
    # entries for rows it sees, but the renderer must not assume that.)
    panel = render_model_cost_donut_panel(
        _report(_tier("opus", cost=1.0, tokens=10), _tier("ghost")), True
    )
    entries = _payload(panel)
    ghost = [e for e in entries if e["tier"] == "ghost"]
    assert ghost == [{"tier": "ghost", "cost_usd": None, "tokens": 0, "uncosted": True}]
    assert "ghost" in _caption(panel)


def test_donut_zero_cost_priced_tier_stays_a_real_slice() -> None:
    # Spec R3: a genuinely zero-priced tier is a real priced slice
    # (uncosted False, cost_usd 0.0) — distinct from uncosted-null.
    panel = render_model_cost_donut_panel(_report(_tier("haiku", cost=0.0, tokens=10)), True)
    entries = _payload(panel)
    assert entries == [{"tier": "haiku", "cost_usd": 0.0, "tokens": 10, "uncosted": False}]
    assert 'canvas id="model-cost-donut-chart"' in panel


def test_donut_canvas_is_accessible_with_static_aria_label() -> None:
    # AC7: role="img", non-empty aria-label honestly describing the
    # priced-only constraint + caption handling, fallback <p> inside canvas.
    panel = render_model_cost_donut_panel(_report(_tier("opus", cost=1.0, tokens=10)), True)
    assert 'role="img"' in panel
    m = re.search(r'aria-label="([^"]+)"', panel)
    assert m is not None
    assert "priced tiers" in m.group(1)
    assert "caption" in m.group(1)
    assert re.search(r"<canvas[^>]*>\s*<p>", panel)


def test_donut_data_tile_renders_loading_state_with_hidden_wrapper() -> None:
    # Established chart-tile lifecycle: tile--loading + hidden wrapper until
    # the init script's first successful draw.
    panel = render_model_cost_donut_panel(_report(_tier("opus", cost=1.0, tokens=10)), True)
    assert 'class="tile tile--loading"' in panel
    assert 'data-state="loading"' in panel
    assert 'class="chart-rendering-target" hidden' in panel
    assert "loading-copy" in panel


# --------------------------------------------------------------------------- #
# absence + nothing-priced states (AC3, AC4)
# --------------------------------------------------------------------------- #


def test_donut_not_run_renders_absence_tile_without_chart_scaffolding() -> None:
    # AC3: has_run False -> absence tile; no canvas, no data block, no "[]"
    # JSON scaffolding.
    panel = render_model_cost_donut_panel(_report(), False)
    assert "No stored cost rows yet." in panel
    assert "model-cost-donut-chart" not in panel
    assert "model-cost-donut-data" not in panel
    assert "[]" not in panel


def test_donut_not_run_absence_wins_even_with_tiers_present() -> None:
    # has_run is authoritative: a populated report with has_run False still
    # renders the absence tile (the loader never produces this combination,
    # but the renderer must not invent a chart from it).
    panel = render_model_cost_donut_panel(_report(_tier("opus", cost=1.0, tokens=10)), False)
    assert "No stored cost rows yet." in panel
    assert "model-cost-donut-chart" not in panel


@pytest.mark.regression
def test_donut_all_uncosted_renders_nothing_priced_tile_naming_tiers() -> None:
    # AC4 (ADR-0020): zero priced tiers -> honest "nothing priced to chart"
    # data tile naming the uncosted tiers + token counts; no canvas, no
    # fabricated slices, no dollar figure.
    panel = render_model_cost_donut_panel(
        _report(_tier("mystery", tokens=500), _tier("other", tokens=300)), True
    )
    assert 'data-state="data"' in panel
    assert "no priced cost to chart" in panel
    assert "mystery" in panel and "other" in panel
    assert "500" in panel and "300" in panel
    assert "model-cost-donut-chart" not in panel
    assert "$" not in panel


def test_donut_true_zero_empty_report_renders_honest_data_tile() -> None:
    # AC4 sub-case: analyzer ran, zero rows -> true-zero data tile, no canvas.
    panel = render_model_cost_donut_panel(_report(), True)
    assert 'data-state="data"' in panel
    assert "found no stored cost rows yet" in panel
    assert "model-cost-donut-chart" not in panel


# --------------------------------------------------------------------------- #
# injection + non-finite (AC5, AC6)
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_donut_rejects_non_finite_cost() -> None:
    # AC5: allow_nan=False (via _json_in_script) raises rather than baking
    # an invalid NaN token into the payload.
    with pytest.raises(ValueError):
        render_model_cost_donut_panel(_report(_tier("opus", cost=float("nan"), tokens=10)), True)


@pytest.mark.regression
def test_donut_resists_script_close_injection_in_tier_name() -> None:
    # AC6: a tier name carrying a script-close sequence cannot break out of
    # the JSON data block; it round-trips through json.loads unchanged.
    evil = "</script><script>alert(1)</script>"
    panel = render_model_cost_donut_panel(_report(_tier(evil, cost=1.0, tokens=10)), True)
    assert "</script><script>" not in panel
    entries = _payload(panel)
    assert entries[0]["tier"] == evil


@pytest.mark.regression
def test_donut_caption_escapes_uncosted_tier_name() -> None:
    # AC6 caption seam: an HTML-shaped uncosted tier name is _esc'd in the
    # caption, never emitted as markup.
    evil = '<img src=x onerror="alert(1)">'
    panel = render_model_cost_donut_panel(
        _report(_tier("opus", cost=1.0, tokens=10), _tier(evil, tokens=5)), True
    )
    # The raw markup may appear INSIDE the JSON data block (a JSON string
    # value is inert there — only `</`, `<!--`, `-->` need escaping, which
    # _json_in_script applies); the HTML caption seam must escape it.
    caption = _caption(panel)
    assert "<img" not in caption
    assert "&lt;img" in caption


def test_donut_nothing_priced_tile_escapes_tier_names() -> None:
    # Same escape discipline on the nothing-priced listing path.
    evil = "<b>sneaky</b>"
    panel = render_model_cost_donut_panel(_report(_tier(evil, tokens=5)), True)
    assert "<b>" not in panel
    assert "&lt;b&gt;" in panel


# --------------------------------------------------------------------------- #
# _donut_slices unit coverage
# --------------------------------------------------------------------------- #


def test_donut_slices_orders_priced_then_uncosted() -> None:
    slices = _donut_slices(
        _report(
            _tier("uncosted-big", tokens=999),
            _tier("cheap", cost=0.1, tokens=1),
            _tier("dear", cost=9.9, tokens=1),
        )
    )
    assert [s["tier"] for s in slices] == ["dear", "cheap", "uncosted-big"]
    assert [s["uncosted"] for s in slices] == [False, False, True]


def test_donut_slices_empty_report_is_empty_list() -> None:
    assert _donut_slices(_report()) == []


# --------------------------------------------------------------------------- #
# LiveFragmentPanels composition (AC8, AC9)
# --------------------------------------------------------------------------- #


def test_render_live_fragment_default_renders_no_extra_panels() -> None:
    # AC8: the bare call renders WITHOUT donut/weekly/chip.
    html = render_live_fragment(LiveState())
    assert "Model cost split" not in html
    assert "Weekly cost trends" not in html
    assert "hook-chip" not in html


@pytest.mark.regression
def test_render_live_fragment_six_position_composition_chain() -> None:
    # AC9 (qa F2 BLOCKING fold): the FULL six-position index chain —
    # chip < runway < per-turn chart < weekly panel < donut < </section>.
    # A silent inversion of any pair (e.g. weekly/donut) fails here even
    # though both panels would still be "present".
    panels = LiveFragmentPanels(
        hook_health_chip_html='<div class="hook-chip">CHIPMARK</div>',
        weekly_panel_html='<div class="tile"><h3>Weekly cost trends</h3></div>',
        model_cost_donut_html='<div class="tile"><h3>Model cost split</h3></div>',
    )
    html = render_live_fragment(LiveState(), panels)
    indices = [
        html.index("CHIPMARK"),
        html.index("<h3>Context runway</h3>"),
        html.index("<h3>Per-turn cost over time</h3>"),
        html.index("<h3>Weekly cost trends</h3>"),
        html.index("<h3>Model cost split</h3>"),
        html.rindex("</section>"),
    ]
    assert indices == sorted(indices)
    assert html.count("<h3>Model cost split</h3>") == 1


def test_live_fragment_panels_is_frozen_and_additive_only() -> None:
    # The dataclass is frozen (caller cannot mutate panels after build) and
    # all fields default to empty strings (additive-only evolution contract).
    panels = LiveFragmentPanels()
    assert panels.hook_health_chip_html == ""
    assert panels.weekly_panel_html == ""
    assert panels.model_cost_donut_html == ""
    with pytest.raises(AttributeError):
        panels.model_cost_donut_html = "<div></div>"  # type: ignore[misc]
