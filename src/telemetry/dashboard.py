"""Pure render layer for the Telemetry Layer B dashboard (ADR-0020).

This module is the *pure*, IO-free presentation logic for the north-star Layer B
dashboard. It takes an already-assembled :class:`DashboardData` (built by the
transport layer in ``scripts/telemetry/dashboard.py`` from the read-side Layer-A
functions) and formats it into one self-contained HTML string plus an ASCII
console summary. It performs **no measurement, no IO, and no DB access** — every
figure is carried in from the Layer-A dataclasses unchanged, so the page can
never drift from the CLIs (the fidelity discipline, spec R5).

Two honesty disciplines are enforced here at the presentation boundary:

* **Escaping (spec C6).** Every dynamic *string* field is ``html.escape``-d in
  Python before interpolation — failure signatures/detail are transcript-shaped,
  so a raw interpolation would be an injection vector. This is a deliberate
  divergence from the ``/status`` precedent (``git_visualize.py``), which
  interpolates raw git-plumbing output; transcript-shaped data is not trusted.
* **Honest absence as first-class visual state (spec R3/R3a, C4).** A
  not-yet-run / not-configured / unavailable panel renders in a *visually
  distinct* absence container (dashed border + an icon + a plain-language
  sentence — distinction by shape/icon, not color alone, WCAG 1.4.1), never as a
  fabricated ``0`` bar. A genuine zero (the analyzer ran and found nothing) uses
  the **normal data tile** with explicit copy, distinct from the absence style.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import TypedDict

from src.telemetry.cost import CostReport
from src.telemetry.failures import RankedFailure
from src.telemetry.live import (
    LANE_ACTIVE,
    LANE_COMPLETE,
    LANE_ORPHANED,
    RUNWAY_AMBER,
    RUNWAY_OK,
    RUNWAY_RED,
    AgentLane,
    LiveCostEvent,
    LiveState,
    RunwayGauge,
)
from src.telemetry.value import DivergenceResult, LeverageResult

#: Panel data-state markers (also used as testable copy tokens).
STATE_DATA = "data"
STATE_NOT_RUN = "not_run"

#: Docs URL for the OTel "enable" affordance (rendered as a live link, not a
#: dead "unavailable" row — matches the A3 CLI behaviour).
OTEL_DOCS_URL = "https://code.claude.com/docs/en/monitoring-usage"

#: Plain-language legends for the manager-gatekeeper (spec R2a, ux BLOCKING).
A1_LEGEND = (
    "These figures show what the same tokens would cost at API pay-per-use "
    "prices — not what you paid on your subscription."
)
A3_PRIMARY_LABEL = "List-price-equivalent multiple"
A3_LEGEND = (
    "How many times your flat monthly subscription fee the same usage would cost "
    "at API list prices. Leads with the per-month figure because that is the "
    "apples-to-apples comparison against a monthly fee; the cumulative multiple "
    "(which grows with the time window) is shown second as context."
)


@dataclass(frozen=True)
class DashboardData:
    """The fully-assembled, render-ready Layer-A telemetry for one dashboard.

    Carries the read-side Layer-A dataclasses unchanged plus a per-panel
    *state* marker so the renderer can tell a true zero from a not-yet-run
    analyzer without re-deriving anything (the transport layer owns that
    classification; the renderer only presents it).

    Attributes:
        cost_report: A1 :class:`CostReport` (per-tier tokens + USD + coverage).
        cost_state: ``"data"`` once the cost analyzer has run, else ``"not_run"``.
        failures: A2 ranked failures (may be empty — a true zero when the
            analyzer ran, the not-run absence when it has not).
        failures_state: ``"data"`` (incl. a true zero) or ``"not_run"``.
        leverage: A3 :class:`LeverageResult` (carries its own configured/absent
            typed state).
        attribution: A3 attribution-coverage :class:`DivergenceResult`.
        pricing_check: A3 OTel-pricing :class:`DivergenceResult`.
        generated_label: A human label for when the page was generated, injected
            by the transport layer (kept out of this pure module so the renderer
            stays deterministic for tests).
    """

    cost_report: CostReport
    cost_state: str
    failures: list[RankedFailure]
    failures_state: str
    leverage: LeverageResult
    attribution: DivergenceResult
    pricing_check: DivergenceResult
    generated_label: str = ""


# --------------------------------------------------------------------------- #
# Escaping + formatting helpers (pure)
# --------------------------------------------------------------------------- #


def _esc(value: object) -> str:
    """HTML-escape any value's string form (including quotes) for interpolation.

    The single escaping seam (spec C6): every dynamic string reaching the HTML
    passes through here. ``quote=True`` so a value interpolated into an attribute
    is safe too. Numeric values are formatted by the ``_fmt_*`` helpers and need
    no escaping, but passing one here is harmless.
    """
    return html.escape(str(value), quote=True)


def _fmt_usd(value: float | None, *, places: int = 2) -> str:
    """Format a dollar figure, or the honest ``uncosted`` marker for ``None``.

    ``None`` means an unpriced/unknown tier or an uncosted waste bundle — it is
    rendered ``uncosted``, **never** ``$0.00`` (which would fabricate a free
    cost out of an unknown one).
    """
    if value is None:
        return "uncosted"
    return f"${value:,.{places}f}"


def _fmt_ratio(value: float | None) -> str:
    """Format a leverage multiple as ``N.NNx`` (ASCII), or ``n/a`` when absent."""
    return f"{value:,.2f}x" if value is not None else "n/a"


def _fmt_int(value: int) -> str:
    """Format an integer token count with thousands separators.

    Takes a concrete ``int`` (never ``None``): the callers pass token totals that
    are always present (``TierCost.total_tokens`` / ``wasted_total_tokens`` sum
    ``None`` as 0). The signature is deliberately non-optional so a future
    ``None`` caller is a type error rather than a silently-fabricated ``0`` — the
    C4 anti-pattern (ux review A1). An unknown *cost* is "uncosted" via
    :func:`_fmt_usd`; a token count is genuinely a number.
    """
    return f"{value:,}"


# --------------------------------------------------------------------------- #
# Tile builders (pure; return escaped HTML fragments)
# --------------------------------------------------------------------------- #


def _absence_tile(title: str, what: str, why: str, *, action_html: str = "") -> str:
    """Build a visually-distinct honest-absence tile (spec R3a).

    Distinction is by shape/icon + a plain-language ``[what]. [why]. [action]``
    sentence, not color alone (WCAG 1.4.1): the ``tile--absent`` class carries a
    dashed border + muted background, and a leading icon glyph reinforces it.

    Args:
        title: Panel/sub-panel heading.
        what: What is absent (a sentence).
        why: Why it is absent (a sentence).
        action_html: Optional pre-built, already-safe HTML for the action (e.g. a
            live link or a ``<code>`` span). Callers must pass escaped/trusted
            HTML here — plain strings should go through ``_esc`` first.
    """
    action = f" {action_html}" if action_html else ""
    return (
        '<div class="tile tile--absent" data-state="absent">'
        '<div class="tile__icon" aria-hidden="true">○</div>'
        f"<h3>{_esc(title)}</h3>"
        f'<p class="absence-copy">{_esc(what)} {_esc(why)}{action}</p>'
        "</div>"
    )


def _code(text: str) -> str:
    """Render a literal (e.g. a script path) as an escaped inline code span."""
    return f"<code>{_esc(text)}</code>"


def _otel_link(label: str = "enable OpenTelemetry (opens in new tab)") -> str:
    """Render the OTel docs URL as a live new-tab hyperlink (spec R3a/ADVISORY 1).

    The default label spells out "OpenTelemetry" and announces the new-tab
    behavior so the gatekeeper knows the context shift before clicking
    (ux FRICTION-6 fold from REV-20260607-200447).
    """
    return f'<a href="{_esc(OTEL_DOCS_URL)}" target="_blank" rel="noopener">{_esc(label)}</a>'


# --------------------------------------------------------------------------- #
# Panel renderers (pure)
# --------------------------------------------------------------------------- #


def _render_cost_panel(data: DashboardData) -> str:
    """Render the A1 Cost & Coverage panel (data tile or not-run absence)."""
    if data.cost_state == STATE_NOT_RUN:
        return _absence_tile(
            "Cost & Coverage",
            "No cost data yet.",
            "The cost analyzer has not run for this database.",
            action_html=(
                f"Run {_code('scripts/telemetry/analyze_cost.py')} to populate this panel."
            ),
        )
    report = data.cost_report
    rows = []
    for tier in sorted(report.by_tier):
        tc = report.by_tier[tier]
        cost = _fmt_usd(tc.cost_usd, places=4)
        # An unknown/unpriced tier carries cost_usd=None -> "uncosted", flagged so
        # the reader sees it is excluded from the total, never zero-rated.
        cls = ' class="uncosted"' if tc.cost_usd is None else ""
        rows.append(
            f"<tr><td>{_esc(tier)}</td>"
            f'<td class="num">{_fmt_int(tc.total_tokens())}</td>'
            f'<td class="num"{cls}>{_esc(cost)}</td></tr>'
        )
    remainder = ""
    if not report.is_fully_covered and report.total_tokens > 0:
        remainder = (
            '<p class="note">'
            f"{_esc(round(100.0 - report.coverage_pct, 1))}% of tokens are an unknown "
            "tier and are shown <strong>uncosted</strong> (excluded from the total, "
            "not zero-rated)."
            "</p>"
        )
    return (
        '<div class="tile tile--data" data-state="data">'
        "<h3>Cost &amp; Coverage</h3>"
        f'<p class="legend">{_esc(A1_LEGEND)}</p>'
        f'<div class="headline">{_esc(_fmt_usd(report.total_cost_usd))}</div>'
        f'<p class="sub">known API-equivalent cost &middot; '
        f"{_esc(report.coverage_pct)}% of billable tokens priced</p>"
        '<table class="data-table">'
        "<thead><tr><th>Tier</th><th>Tokens</th><th>API-equivalent</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        f"{remainder}"
        "</div>"
    )


def _render_failures_panel(data: DashboardData) -> str:
    """Render the A2 Failure & Waste panel (true-zero vs not-run are distinct)."""
    if data.failures_state == STATE_NOT_RUN:
        return _absence_tile(
            "Failure & Waste",
            "No failure data yet.",
            "The failure analyzer has not run for this database.",
            action_html=(
                f"Run {_code('scripts/telemetry/analyze_failures.py')} to populate this panel."
            ),
        )
    failures = data.failures
    if not failures:
        # True zero: the analyzer ran and found nothing -> a normal DATA tile with
        # explicit copy, NOT the absence style (spec R3a).
        return (
            '<div class="tile tile--data" data-state="data">'
            "<h3>Failure &amp; Waste</h3>"
            '<div class="headline headline--ok">No failure signals detected</div>'
            '<p class="sub">No retry loops or orphaned subagents were found.</p>'
            "</div>"
        )
    rows = []
    for rf in failures:
        s = rf.signal
        rows.append(
            "<tr>"
            f"<td>{_esc(s.failure_type)}</td>"
            f'<td class="num">{_esc(_fmt_usd(rf.cost_usd, places=4))}</td>'
            f'<td class="num">{_fmt_int(s.wasted_total_tokens())}</td>'
            f"<td>{_esc(s.tier)}</td>"
            f'<td class="detail">{_esc(s.detail)}'
            f'<span class="sig">{_esc(s.signature)}</span></td>'
            "</tr>"
        )
    return (
        '<div class="tile tile--data" data-state="data">'
        "<h3>Failure &amp; Waste</h3>"
        f'<div class="headline">{_esc(len(failures))} signal(s) detected</div>'
        '<p class="sub">Ranked by wasted API-equivalent cost (most wasteful first).</p>'
        '<table class="data-table">'
        "<thead><tr><th>Type</th><th>Cost</th><th>Wasted tok</th>"
        "<th>Tier</th><th>Detail</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</div>"
    )


def _render_leverage_block(lev: LeverageResult, *, cost_measured: bool) -> str:
    """Render the A3 leverage sub-block (configured data vs honest absence).

    Honest absence has TWO causes, both rendered as absence tiles, not a ``0.00x``
    headline (review BLOCKING B1 — the C4 fabricated-zero the build + both
    checkpoints missed):

    * **cost not measured** (``cost_measured`` is ``False``): the cost analyzer
      has not run, so ``total_cost_usd`` is an un-measured ``0.0`` — finite, so
      ``leverage()`` would report ``configured=True`` with a ``0.00x`` multiple.
      The leverage *numerator* was never measured, so we must not present a
      multiple. This is checked FIRST: it holds even when a fee IS configured (a
      returning user who set their fee but has not re-run ``analyze_cost``).
    * **fee not configured** (``lev.configured`` is ``False``): no denominator.

    Args:
        lev: The A3 leverage result.
        cost_measured: Whether the A1 cost analyzer has run (``cost_state`` is
            ``data``). When ``False`` the numerator is unmeasured.
    """
    if not cost_measured:
        return _absence_tile(
            A3_PRIMARY_LABEL,
            "Not shown.",
            "The cost analyzer has not run, so there is no measured spend to compare.",
            action_html=(
                f"Run {_code('scripts/telemetry/analyze_cost.py')} first, then set a fee."
            ),
        )
    if not lev.configured:
        return _absence_tile(
            A3_PRIMARY_LABEL,
            "Not shown.",
            _esc_reason(lev.reason),
            action_html=(
                f"Set a monthly fee in {_code('config/subscription.yaml')} to enable it."
            ),
        )
    # ``basis`` may carry the transcript-influenced ``lev.note`` raw here; it is
    # raw ONLY at assignment and is escaped at emission via ``_esc(basis)`` below.
    # A future refactor must keep that emission-point escape if ``basis`` is ever
    # inlined into a raw f-string (security checkpoint, REV pass).
    if lev.leverage_per_month is not None and lev.window_months is not None:
        primary = f"{_fmt_ratio(lev.leverage_per_month)}/mo"
        basis = f"over ~{lev.window_months:.1f} months"
    else:
        primary = _fmt_ratio(lev.leverage_cumulative)
        basis = lev.note or "cost window unknown; per-month not derivable"
    # Under-coverage caveat (review A3 / independent Scenario 2): when not every
    # billable token was priced, the multiple is computed on the priced subset and
    # silently understates value — surface that prominently, mirroring the cost
    # panel's uncosted-remainder note, rather than only in the kv list.
    coverage_note = ""
    if lev.coverage_pct < 100.0:
        coverage_note = (
            f'<p class="note">Computed on {_esc(lev.coverage_pct)}% of billable tokens '
            "(the rest are an unknown, uncosted tier); the real multiple is at least this.</p>"
        )
    return (
        '<div class="subtile" data-state="data">'
        f"<h4>{_esc(A3_PRIMARY_LABEL)}</h4>"
        f'<p class="legend">{_esc(A3_LEGEND)}</p>'
        f'<div class="headline">{_esc(primary)}</div>'
        f'<p class="sub">{_esc(basis)}</p>'
        f"{coverage_note}"
        '<ul class="kv">'
        f"<li>cumulative over the window: <strong>{_esc(_fmt_ratio(lev.leverage_cumulative))}"
        "</strong></li>"
        f"<li>API-equivalent compute: <strong>{_esc(_fmt_usd(lev.total_cost_usd))}</strong> "
        f"(coverage {_esc(lev.coverage_pct)}%)</li>"
        f"<li>subscription fee: <strong>{_esc(_fmt_usd(lev.monthly_fee_usd))}</strong>/"
        f"{_esc(lev.fee_period)}</li>"
        "</ul></div>"
    )


def _esc_reason(reason: str) -> str:
    """Normalise an empty reason to a generic sentence.

    Returns a **raw** string (escaping happens downstream where the value is
    interpolated — e.g. ``_absence_tile`` applies ``_esc(why)``). The name
    normalises a reason; it does not escape (security review A9 — the prior
    docstring's "escaped upstream" was backwards).
    """
    return reason or "not available"


def _render_attribution_block(dv: DivergenceResult) -> str:
    """Render the A3 attribution-coverage cross-check (coverage frame, not a flaw)."""
    if not dv.available:
        return _absence_tile(
            "Attribution cross-check",
            "Not available.",
            _esc_reason(dv.reason),
        )
    indep = dv.independent_cost_usd
    # Defense in depth (review A2): ``value.cross_check`` already reports
    # ``available=False`` on a zero/None denominator, so this should be
    # unreachable — but enforce the honest absence at the render boundary too, so
    # a future change upstream cannot produce a fabricated "0.0% covered" data
    # tile (the C4 anti-pattern).
    if not indep:
        return _absence_tile(
            "Attribution cross-check",
            "Not available.",
            "The independent cost total is zero or missing, so a coverage share "
            "cannot be computed.",
        )
    coverage = dv.our_cost_usd / indep * 100.0
    return (
        '<div class="subtile" data-state="data">'
        "<h4>Attribution cross-check</h4>"
        '<p class="legend">What share of your total measured AI cost was logged inside a '
        "named discussion session.</p>"
        f'<p class="sub">{_esc(_fmt_usd(dv.our_cost_usd))} of measured spend is attributed to '
        f"captured discussions, out of {_esc(_fmt_usd(dv.independent_cost_usd))} total.</p>"
        f'<div class="headline">{_esc(round(coverage, 1))}% covered</div>'
        '<p class="note">Captured discussions cover this share of measured AI spend; the rest '
        "is activity outside any discussion window, not an error.</p>"
        f'<p class="src">source: {_esc(dv.source_label)}</p>'
        "</div>"
    )


def _render_pricing_block(dv: DivergenceResult) -> str:
    """Render the A3 OTel-pricing cross-check (live enable affordance when off)."""
    if not dv.available:
        if (dv.source_label or "").startswith("otel"):
            return _absence_tile(
                "Pricing cross-check (OpenTelemetry)",
                "Not yet active.",
                "Turn on Claude Code's OpenTelemetry export to enable this independent "
                "pricing cross-check.",
                action_html=_otel_link(),
            )
        return _absence_tile(
            "Pricing cross-check",
            "Not available.",
            _esc_reason(dv.reason),
        )
    arrow = {
        "ours_higher": "higher than",
        "ours_lower": "lower than",
        None: "exactly matches",
    }[dv.direction]
    pct = "0.00%" if dv.divergence_pct == 0.0 else f"{dv.divergence_pct:+.2f}%"
    return (
        '<div class="subtile" data-state="data">'
        "<h4>Pricing cross-check (OpenTelemetry)</h4>"
        f'<p class="sub">Our estimate {_esc(_fmt_usd(dv.our_cost_usd))} is {_esc(arrow)} the '
        f"independent {_esc(_fmt_usd(dv.independent_cost_usd))} ({_esc(pct)}).</p>"
        f'<p class="src">source: {_esc(dv.source_label)}</p>'
        "</div>"
    )


def _render_value_panel(data: DashboardData) -> str:
    """Render the A3 Value vs Subscription panel (leverage + two cross-checks)."""
    cost_measured = data.cost_state == STATE_DATA
    return (
        '<div class="tile tile--data tile--wide" data-state="data">'
        "<h3>Value vs Subscription</h3>"
        f"{_render_leverage_block(data.leverage, cost_measured=cost_measured)}"
        f"{_render_attribution_block(data.attribution)}"
        f"{_render_pricing_block(data.pricing_check)}"
        "</div>"
    )


# --------------------------------------------------------------------------- #
# Top-level render
# --------------------------------------------------------------------------- #

_CSS = """
:root{--bg:#0f1419;--card:#1a2029;--ink:#e6edf3;--muted:#8b949e;--accent:#58a6ff;
--ok:#3fb950;--absent:#6e7681;--line:#30363d;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
line-height:1.5;}
header{padding:28px 32px 8px;}
header h1{margin:0;font-size:22px;}
header .gen{color:var(--muted);font-size:13px;margin-top:4px;}
main{display:grid;grid-template-columns:repeat(2,1fr);gap:18px;padding:18px 32px 40px;}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;}
.tile--wide{grid-column:1 / -1;display:grid;grid-template-columns:repeat(3,1fr);gap:16px;
align-items:start;}
.tile--wide>h3{grid-column:1 / -1;margin:0 0 4px;}
.tile h3{margin:0 0 10px;font-size:16px;}
.tile h4{margin:0 0 8px;font-size:14px;}
.tile--absent{border-style:dashed;border-color:var(--absent);background:repeating-linear-gradient(
45deg,#161b22,#161b22 10px,#1a2029 10px,#1a2029 20px);}
.tile__icon{font-size:22px;color:var(--absent);line-height:1;margin-bottom:6px;}
.subtile{background:#161b22;border:1px solid var(--line);border-radius:10px;padding:14px;}
.subtile.tile--absent,.tile--absent .subtile{border-style:dashed;}
.headline{font-size:30px;font-weight:700;letter-spacing:-.5px;margin:6px 0;}
.headline--ok{color:var(--ok);font-size:22px;}
.legend{color:var(--muted);font-size:12.5px;margin:0 0 10px;}
.sub{color:var(--muted);font-size:13px;margin:2px 0;}
.note{color:var(--muted);font-size:12.5px;margin-top:10px;}
.src{color:var(--muted);font-size:12px;margin-top:8px;}
.absence-copy{color:var(--muted);font-size:13.5px;margin:0;}
.data-table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px;}
.data-table th,.data-table td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);}
.data-table th{color:var(--muted);font-weight:600;}
.data-table td.num{text-align:right;font-variant-numeric:tabular-nums;}
td.uncosted{color:var(--absent);font-style:italic;}
.detail{font-size:12px;}
.sig{display:block;color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
font-size:11px;margin-top:3px;word-break:break-all;}
.kv{list-style:none;padding:0;margin:10px 0 0;font-size:13px;color:var(--muted);}
.kv li{margin:3px 0;}
code{background:#0d1117;border:1px solid var(--line);border-radius:5px;padding:1px 5px;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;}
a{color:var(--accent);}
"""


def render_dashboard_html(data: DashboardData) -> str:
    """Render a :class:`DashboardData` into one self-contained HTML document.

    Pure and deterministic: given the same ``data`` it returns byte-identical
    HTML. All dynamic strings are escaped (spec C6); honest-absence panels render
    in their distinct absence container (spec R3/R3a). The document inlines its
    CSS and references no network assets (spec R1), and declares
    ``<meta charset="utf-8">`` so its UTF-8 glyphs render correctly (the
    console summary stays ASCII — that boundary is in ``render_console_summary``).

    Args:
        data: The assembled, render-ready telemetry.

    Returns:
        A complete ``<!DOCTYPE html>`` string.
    """
    gen = f"Generated {_esc(data.generated_label)}" if data.generated_label else ""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Telemetry Dashboard</title>"
        f"<style>{_CSS}</style></head><body>"
        "<header><h1>Telemetry &amp; Oversight — your AI use at a glance</h1>"
        f'<div class="gen">{gen}</div></header>'
        "<main>"
        f"{_render_cost_panel(data)}"
        f"{_render_failures_panel(data)}"
        f"{_render_value_panel(data)}"
        "</main></body></html>"
    )


def render_console_summary(data: DashboardData, *, output_path: str) -> list[str]:
    """Build the 5-6 line ASCII console summary (spec R4, C7).

    Every line is pure ASCII so it round-trips through Windows cp1252 without a
    ``UnicodeEncodeError`` (the 4th guard of that class — statusLine, ntfy title,
    quality_gate summary precede it). The visual carries the detail; this is the
    at-a-glance text echo. No raw internal field names; no figure that needs
    jargon to read.

    Args:
        data: The assembled telemetry.
        output_path: Where the HTML was written (line 1).

    Returns:
        A list of ASCII summary lines (5 always, plus an optional 6th advisory).
    """
    lines = [f"Dashboard: {output_path}"]

    if data.cost_state == STATE_NOT_RUN:
        lines.append("Cost: analyzer not yet run (run scripts/telemetry/analyze_cost.py)")
    else:
        r = data.cost_report
        lines.append(
            f"Cost: {_fmt_usd(r.total_cost_usd)} API-equivalent "
            f"({r.coverage_pct}% of billable tokens covered)"
        )

    if data.failures_state == STATE_NOT_RUN:
        lines.append("Failures: analyzer not yet run (run scripts/telemetry/analyze_failures.py)")
    elif not data.failures:
        lines.append("Failures: none detected")
    else:
        lines.append(f"Failures: {len(data.failures)} signal(s) detected")

    lev = data.leverage
    if data.cost_state == STATE_NOT_RUN:
        # B1: never print a 0.00x multiple when the numerator was never measured.
        lines.append("List-price-equivalent: cost not yet measured (run analyze_cost.py)")
    elif not lev.configured:
        lines.append("List-price-equivalent: subscription fee not configured")
    elif lev.leverage_per_month is not None:
        lines.append(
            f"List-price-equivalent: {_fmt_ratio(lev.leverage_per_month)}/mo "
            f"(cumulative {_fmt_ratio(lev.leverage_cumulative)})"
        )
    else:
        lines.append(f"List-price-equivalent: {_fmt_ratio(lev.leverage_cumulative)} cumulative")

    if data.pricing_check.available:
        lines.append("OTel cross-check: active")
    else:
        lines.append("OTel cross-check: not yet active (enable OpenTelemetry export)")

    absences = _count_absences(data)
    if absences:
        lines.append(
            f"Note: {absences} panel(s) show an honest-absence state "
            "(not-yet-run / not-configured) - see the page."
        )
    return lines


def _count_absences(data: DashboardData) -> int:
    """Count panels/sub-panels currently in an honest-absence state (ASCII-safe)."""
    count = 0
    if data.cost_state == STATE_NOT_RUN:
        count += 1
    if data.failures_state == STATE_NOT_RUN:
        count += 1
    # Leverage is absent when the fee is unconfigured OR the cost numerator was
    # never measured (B1) — match the render gate so the count is honest.
    if data.cost_state == STATE_NOT_RUN or not data.leverage.configured:
        count += 1
    if not data.attribution.available:
        count += 1
    if not data.pricing_check.available:
        count += 1
    return count


# --------------------------------------------------------------------------- #
# Live-panel renderers (R15 — same panel helpers as the static doc).
# --------------------------------------------------------------------------- #
#
# These compose the live section that ``scripts/telemetry/dashboard_server.py``
# polls into the page via htmx. They reuse the existing ``_esc`` / ``_fmt_*`` /
# ``_absence_tile`` helpers above so the static and live paths share one
# escaping seam (spec C6) and one absence vocabulary (spec R3a). Each helper is
# pure: it accepts a :class:`LiveState` (or one of its fields) and returns an
# escaped HTML fragment. No IO; no global state.
#
# The runway gauge's amber/red colors live in the inline CSS at the top of this
# module so the live HTML fragment never needs to ship a second stylesheet.

#: Human-facing label for each lane status (also used as a CSS modifier suffix).
_LANE_STATUS_LABEL = {
    LANE_ACTIVE: "active",
    LANE_COMPLETE: "complete",
    LANE_ORPHANED: "orphaned",
}

#: Plain-language status copy for the runway gauge.
_RUNWAY_STATUS_COPY = {
    RUNWAY_OK: "Plenty of headroom",
    RUNWAY_AMBER: "Approaching wrap-up window — consider checkpointing soon",
    RUNWAY_RED: "Inside the wrap-up window — handoff recommended",
}

#: Manager-facing label for each runway status (qa F2 + ux FRICTION-3). The
#: runway statuses are NOT lane statuses — using ``_LANE_STATUS_LABEL`` for
#: them would leak the raw constant name (``amber`` / ``red``) into the
#: gatekeeper's reading; this map carries the human-readable label and is
#: the only renderer-side translation of the constants.
_RUNWAY_LABEL = {
    RUNWAY_OK: "OK",
    RUNWAY_AMBER: "warning",
    RUNWAY_RED: "critical",
}


def render_live_fragment(state: LiveState) -> str:
    """Render the htmx live fragment (agent lanes + runway + cost/failure stream + chart).

    Returned as ONE root ``<section>`` so an htmx ``hx-swap="outerHTML"`` swap
    replaces the previous fragment cleanly. The server polls this endpoint on
    a server-specified interval (spec R2 — htmx polling, not SSE in Phase 1).

    Composition order is the visual-hierarchy contract: runway (highest-stakes
    "how much headroom do I have?") → lanes (operational state) → stream (per-event
    trail) → per-turn cost chart (the trend visualisation that sits on top of the
    stream's raw events). The chart appears LAST because it is a derived view of
    the stream data above it; a reader who has not yet scanned the stream can
    still read the chart, but the stream is the source of truth.
    """
    return (
        '<section id="live-section" class="live-section" data-state="live">'
        f"{_render_runway_panel(state.runway)}"
        f"{_render_agent_lanes_panel(state)}"
        f"{_render_live_stream_panel(state.recent_events)}"
        f"{_render_per_turn_cost_chart_panel(state.recent_events)}"
        "</section>"
    )


def _render_runway_panel(runway: RunwayGauge) -> str:
    """Render the context-window runway gauge (spec R2: fill %, amber/red, est turns).

    Honest absence (spec R3a / ADR-0020): when the model's context-window size
    is zero (no ``context`` event has landed yet), render the not-yet-available
    absence tile, never a fabricated ``0%`` bar. Once snapshots arrive, the
    estimated-turns-remaining stays ``None`` until at least one main turn has
    landed — :func:`_render_runway_estimate` keeps that honest in copy.
    """
    if runway.context_window <= 0:
        return _absence_tile(
            "Context runway",
            "No live context snapshot yet.",
            "The dashboard has not received a context-occupancy event from the active session.",
        )
    # The CSS class suffix uses the raw status constant (``amber`` / ``red``
    # match the existing ``runway--amber`` / ``runway--red`` rules in _LIVE_CSS);
    # the gatekeeper-facing sub-line uses the human-readable _RUNWAY_LABEL.
    status_class = f"runway--{runway.status}"
    status_copy = _RUNWAY_STATUS_COPY.get(runway.status, "")
    status_label = _RUNWAY_LABEL.get(runway.status, runway.status)
    bar_width = max(0.0, min(100.0, runway.fill_pct))
    return (
        f'<div class="tile tile--data runway {status_class}" data-state="data">'
        "<h3>Context runway</h3>"
        f'<div class="runway__bar" role="progressbar" aria-valuenow="{_esc(runway.fill_pct)}" '
        'aria-valuemin="0" aria-valuemax="100">'
        f'<div class="runway__fill" style="width:{_esc(bar_width)}%"></div>'
        "</div>"
        f'<div class="headline">{_esc(runway.fill_pct)}%</div>'
        f'<p class="sub">{_esc(_fmt_int(runway.current_tokens))} of '
        f"{_esc(_fmt_int(runway.context_window))} tokens used &middot; "
        f"{_esc(status_label)}</p>"
        f'<p class="note">{_esc(status_copy)}</p>'
        f"{_render_runway_estimate(runway)}"
        "</div>"
    )


def _render_runway_estimate(runway: RunwayGauge) -> str:
    """Render the est-turns-remaining line, honoring the cold-start ``None``.

    A ``None`` estimate means no main turn has landed yet — we render an honest
    "not enough data yet" sentence, NOT ``0`` or ``unknown turns``. This mirrors
    the C4 honest-absence pattern (ADR-0020).
    """
    if runway.est_turns_remaining is None:
        return (
            '<p class="src">Estimated turns remaining: not enough data yet '
            "(needs at least one main-lane turn).</p>"
        )
    return (
        f'<p class="src">Estimated turns remaining: '
        f"<strong>{_esc(_fmt_int(runway.est_turns_remaining))}</strong> "
        "(rolling avg of main-lane output tokens per turn).</p>"
    )


def _render_agent_lanes_panel(state: LiveState) -> str:
    """Render the agent-lane panel (R2: active/completed/orphaned).

    The main lane renders first, then dispatched subagent lanes in dispatch
    order. When no session is active yet (no main lane), the panel renders the
    honest absence tile rather than an empty data tile.
    """
    if state.main is None and not state.agents:
        return _absence_tile(
            "Agent lanes",
            "No active session yet.",
            "The dashboard has not seen a live session. Launch a Claude Code session "
            "(or run the analyzers) to populate this panel.",
        )
    rows = []
    if state.main is not None:
        rows.append(_render_agent_lane_row(state.main))
    for lane in state.agents:
        rows.append(_render_agent_lane_row(lane))
    return (
        '<div class="tile tile--data tile--wide" data-state="data">'
        "<h3>Agent lanes</h3>"
        '<p class="legend">One row per lane (main + each dispatched subagent). '
        "Status is computed from in-flight transcript events.</p>"
        '<table class="data-table">'
        "<thead><tr><th>Lane</th><th>Agent</th><th>Model</th><th>Status</th>"
        '<th class="num">Tokens</th><th class="num">Cost</th>'
        '<th class="num">Tools</th><th class="num">Failures</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</div>"
    )


def _render_agent_lane_row(lane: AgentLane) -> str:
    """Render one row of the agent-lanes table — fully escaped.

    The main session lane carries an extra ``lane--primary`` class plus a
    ``primary`` badge next to the agent label (ux FRICTION-2): the previous
    row treatment made the main session indistinguishable from a dispatched
    subagent, which broke the gatekeeper's "is the top-level session
    healthy?" read at a glance. The badge is the **load-bearing**
    differentiator — its literal text label ("primary") carries the signal
    for any reader (including with colour-deficiency or on dim displays).
    The row's green left-border + 4% green tint are **decorative
    reinforcement** for users who can see them, not the WCAG-1.4.1
    accessibility contract.
    """
    total_tokens = lane.input_tokens + lane.output_tokens + lane.cache_read_tokens
    status_label = _LANE_STATUS_LABEL.get(lane.status, lane.status)
    is_primary = lane.kind == "main"
    classes = [f"lane--{status_label}"]
    if is_primary:
        classes.append("lane--primary")
    primary_badge = (
        '<span class="lane-badge lane-badge--primary">primary</span>' if is_primary else ""
    )
    agent = lane.agent_type or ("main" if is_primary else "—")
    model = lane.model or "—"
    return (
        f'<tr class="{" ".join(classes)}">'
        f"<td>{_esc(lane.lane_id)}</td>"
        f"<td>{_esc(agent)}{primary_badge}</td>"
        f"<td>{_esc(model)}</td>"
        f'<td><span class="lane-badge">{_esc(status_label)}</span></td>'
        f'<td class="num">{_fmt_int(total_tokens)}</td>'
        f'<td class="num">{_esc(_fmt_usd(lane.cost_usd, places=4))}</td>'
        f'<td class="num">{_fmt_int(lane.tool_count)}</td>'
        f'<td class="num">{_fmt_int(lane.failure_count)}</td>'
        "</tr>"
    )


def _render_live_stream_panel(events: tuple[LiveCostEvent, ...]) -> str:
    """Render the rolling live cost/failure stream (R2).

    Empty stream renders an honest "no live events yet" absence tile. Otherwise
    we render the most-recent-first list of events; each row is fully escaped.
    """
    if not events:
        return _absence_tile(
            "Live stream",
            "No live events yet.",
            "Per-turn costs and failure events will appear here as the active session emits them.",
        )
    rows = []
    for ev in reversed(events):
        rows.append(
            "<tr>"
            f"<td>{_esc(ev.timestamp.isoformat())}</td>"
            f"<td>{_esc(ev.lane_id)}</td>"
            f"<td>{_esc(ev.kind)}</td>"
            f'<td class="num">{_esc(_fmt_usd(ev.cost_usd, places=4))}</td>'
            f'<td class="num">{_fmt_int(ev.tokens)}</td>'
            "</tr>"
        )
    return (
        '<div class="tile tile--data tile--wide" data-state="data">'
        "<h3>Live stream</h3>"
        '<p class="legend">Most recent first; capped at the latest 100 events. '
        "<strong>Kind:</strong> <code>turn</code> = assistant turn "
        "(cost shown when the model tier is priced; 0.0000 when uncosted); "
        "<code>failure</code> = error or non-2xx event.</p>"
        '<table class="data-table">'
        "<thead><tr><th>Time</th><th>Lane</th><th>Kind</th>"
        '<th class="num">Cost</th><th class="num">Tokens</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</div>"
    )


#: Data-block element id for the per-turn cost chart's JSON payload.
#:
#: The Chart.js init script (Phase 2 next slice, pending the CSP fork) will look
#: up this id with ``document.getElementById`` and parse its ``textContent`` as
#: JSON. Pulling the id out as a module constant keeps the renderer + the future
#: init script + the regression tests pointing at one source of truth.
_PER_TURN_COST_DATA_ELEMENT_ID = "per-turn-cost-data"

#: Canvas element id for the per-turn cost chart.
_PER_TURN_COST_CANVAS_ID = "per-turn-cost-chart"

#: Wrapper element class for the canvas + data block. The Phase 2 init script
#: removes the ``hidden`` attribute on this wrapper + flips the parent tile's
#: ``data-state`` from ``"loading"`` to ``"data"`` (and removes the
#: ``tile--loading`` class) once the chart is drawn. Until then the wrapper
#: is HTML5-``hidden`` so the user sees the loading copy, not a blank canvas.
_PER_TURN_COST_RENDER_TARGET_CLASS = "chart-rendering-target"


class _ChartPoint(TypedDict):
    """The chart-data contract baked into the per-turn cost panel's JSON block.

    This is the API between the Python renderer (this slice) and the Phase 2
    init script (next slice, JS). The shape is intentionally minimal:

    * ``t`` — ISO-8601 UTC timestamp string (``LiveCostEvent.timestamp.isoformat()``)
    * ``cost`` — API-equivalent USD as a finite float (NaN/Inf rejected at
      ``json.dumps`` time — see ``allow_nan=False`` below)
    * ``lane_id`` — string identifier of the originating lane
    * ``uncosted`` — ``True`` iff the originating turn's model tier was unknown
      or unpriced; ``cost`` is then ``0.0`` because the tier is unpriced, NOT
      because the turn was free (arch F1 fold from REV-20260608-025749). The
      Phase 2 init script consumes this to mark uncosted turns distinctly
      (e.g. dashed line / different marker) so the chart preserves the
      "uncosted ≠ \\$0" honesty discipline of the static cost report
      (ADR-0020). Always ``False`` for ``"failure"`` events, which the
      renderer filters out before the payload is built.

    **Schema evolution rule:** adding a field is non-breaking IFF the init script
    treats unknown fields as opaque. Removing or renaming an existing field is
    a breaking change that requires updating the init script in the same commit.
    (The Phase 2 init script that consumes this payload MUST treat unknown
    fields as opaque so the IFF condition is satisfied — this is a forward
    obligation on the init script slice, currently CSP-blocked. Until that
    slice lands the rule is vacuously satisfied because no JS consumer exists.)
    """

    t: str
    cost: float
    lane_id: str
    uncosted: bool


def _render_per_turn_cost_chart_panel(events: tuple[LiveCostEvent, ...]) -> str:
    """Render the per-turn cost chart panel (spec R2/R11/R11a — chart data baked).

    Filters ``events`` to ``kind == "turn"`` only (failure-kind events carry no
    per-turn cost dimension to chart) and bakes the resulting time series as a
    single JSON literal in a ``<script type="application/json">`` block — per
    spec R11a, the page never opens an outbound JSON endpoint, all chart data
    travels inline with the fragment. The Chart.js init that consumes this
    payload lands in a separate slice (the CSP design fork).

    **Interim visual state** (ux F1 from REV-20260608-025749 fold): until the
    Phase 2 init script ships, the data-present path renders as ``tile--loading``
    with the canvas + data block in an HTML5-``hidden`` wrapper — NOT as a
    bare ``tile--data`` panel with a visible-but-blank canvas, which would read
    as a broken component. The hidden wrapper preserves the integration surface
    for the future init script (``document.getElementById`` still finds the
    canvas + data block); the init script removes the ``hidden`` attribute +
    flips the tile's ``data-state`` to ``"data"`` + drops the ``tile--loading``
    class when it draws the chart.

    Honesty contract (spec R3/R3a / C4): empty turn-events render the distinct
    honest-absence tile, NEVER an empty chart with fabricated axes. The
    distinction-by-shape vocabulary is shared with the runway/lanes/stream
    panels above.

    Security contract (spec R11 / C6 / security F2): ``html.escape`` is
    intentionally NOT applied to the JSON body — it would corrupt the JSON and
    break ``JSON.parse``. The correct seam is ``json.dumps`` followed by a
    ``</`` → ``<\\/`` replacement so a transcript-shaped string field carrying
    ``</script><script>`` cannot close the data block (HTML5 parses ``<script>``
    bodies in raw-text mode and ends the block on the literal byte sequence
    ``</`` followed by a name match — the escaped ``\\/`` form is valid JSON
    per RFC 8259 §7 and round-trips through ``JSON.parse`` unchanged).

    ``allow_nan=False`` (security F1 / qa F3 fold from REV-20260608-025749):
    converts a non-finite ``cost_usd`` (NaN/Infinity) from a silent
    ``"NaN"``/``"Infinity"`` token in the data block (invalid per RFC 8259 §3,
    crashes ``JSON.parse`` in every browser) into a loud ``ValueError`` at
    render time, which the FastAPI error middleware catches and serves as a
    generic 500. ``LiveCostEvent.cost_usd`` admits non-finite values today (no
    field validator on the frozen dataclass), so this is defense-in-depth.

    **Rule-of-Three pin** (arch F3 from REV-20260608-025749): the JSON-in-script
    escape (``json.dumps`` + ``</`` → ``<\\/``) is inline here as the SOLE
    consumer in this codebase. When a second consumer lands (e.g., a runway
    history chart, an A2 failure-trends panel), THAT is the moment to extract
    a ``_json_in_script(payload: object) -> str`` helper so all consumers unify
    under one escape — not before.
    """
    turn_events = tuple(ev for ev in events if ev.kind == "turn")
    if not turn_events:
        return _absence_tile(
            "Per-turn cost over time",
            "No priced turns yet.",
            "The per-turn cost chart will appear here once the active session "
            "emits a priced assistant turn.",
        )
    points: list[_ChartPoint] = [
        {
            "t": ev.timestamp.isoformat(),
            "cost": ev.cost_usd,
            "lane_id": ev.lane_id,
            "uncosted": ev.uncosted,
        }
        for ev in turn_events
    ]
    payload = json.dumps(points, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    aria_label = (
        "Per-turn cost over time — line chart of API-equivalent USD per "
        "priced assistant turn in the recent event window."
    )
    return (
        '<div class="tile tile--loading tile--wide" data-state="loading">'
        "<h3>Per-turn cost over time</h3>"
        '<p class="legend">Cost per priced assistant turn over the recent event '
        "window. Y-axis is API-equivalent USD per turn; X-axis is wall-clock "
        "time. Data is baked into the fragment (no separate JSON endpoint, "
        "spec R11a). Turns from model tiers without a known price appear at "
        "<code>0.0000</code> (uncosted — excluded from totals, not "
        "zero-rated).</p>"
        '<p class="loading-copy">Chart visualization layer initializing &mdash; '
        "the line chart will draw once the rendering layer is ready. Turn "
        "data is also listed in the Live stream panel above.</p>"
        # Hidden wrapper preserves the integration surface for the Phase 2 init
        # script (canvas + data block ids unchanged); init script removes
        # ``hidden`` + flips the tile to data-state="data" on first draw.
        f'<div class="{_PER_TURN_COST_RENDER_TARGET_CLASS}" hidden>'
        f'<canvas id="{_PER_TURN_COST_CANVAS_ID}" width="800" height="240"'
        f' role="img" aria-label="{_esc(aria_label)}">'
        "<p>Per-turn cost chart (data available; chart rendering requires "
        "a visual display).</p>"
        "</canvas>"
        f'<script id="{_PER_TURN_COST_DATA_ELEMENT_ID}" type="application/json">'
        f"{payload}"
        "</script>"
        "</div>"
        "</div>"
    )


def render_live_shell_html(*, generated_label: str = "") -> str:
    """Render the htmx shell page that polls the live fragment.

    The shell embeds htmx + Chart.js (both loaded from the local static mount,
    NOT a CDN — spec R11a / AC6) and one ``<section>`` placeholder that htmx
    swaps via a server-specified polling interval. The retrospective panels
    live above this shell and continue to render server-side from
    :func:`render_dashboard_html`'s helpers — the same panel renderers, no
    duplication (spec R15).

    Chart.js is loaded ``defer`` so it is ready in the global ``Chart`` symbol
    by the time the first ``/fragments/live`` swap lands, but never blocks the
    initial paint. The chart's data payload is baked INTO the live fragment as
    a JSON literal (see :func:`_render_per_turn_cost_chart_panel`), so the shell
    itself carries no chart-specific markup beyond the script-tag load.

    **CSP scope note** (security F2 from REV-20260608-025749 fold): the shell's
    ``Content-Security-Policy`` header (set by ``ContentSecurityPolicyMiddleware``
    in ``scripts/telemetry/dashboard_server.py``) is the OPERATIVE policy for all
    htmx-swapped fragment content. The fragment's own response header is consumed
    by the htmx XHR path, NOT the document parser. Relaxing the shell's
    ``script-src 'self'`` to ``'unsafe-inline'`` for the Phase 2 init script would
    REMOVE the XSS backstop for the chart data block — even with the
    ``</`` → ``<\\/`` guard in place. Any such relaxation must come with a
    reviewer ADR and matching tests on the trust boundary.

    The header carries a "retrospective view" link to ``/fragments/retrospective``
    (ux FRICTION-4): that route returns a full HTML document (not an htmx
    swap-target), so a plain ``<a href>`` is the correct affordance; without
    it the route is live but unreachable from the UI.

    The first-paint placeholder uses a distinct ``tile--loading`` class (NOT
    ``tile--absent``) so a transient htmx delay does not present as an
    honest-absence tile to the gatekeeper — the visual states are different
    (pulsing opacity vs the dashed-border absence container) and the copy
    explicitly says "Connecting…" rather than "Not yet…" (ux FRICTION-1).

    Args:
        generated_label: A human-readable timestamp for when the page was first
            served (transport owns the clock).
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Telemetry Dashboard (live)</title>"
        '<script src="/static/htmx.min.js" defer></script>'
        '<script src="/static/chart.umd.min.js" defer></script>'
        f"<style>{_CSS}{_LIVE_CSS}</style></head><body>"
        "<header><h1>Telemetry &amp; Oversight — live</h1>"
        f'<div class="gen">{_esc(generated_label)}</div>'
        '<nav class="shell-nav">'
        '<a href="/fragments/retrospective" class="nav-link"'
        ' aria-label="Retrospective view">'
        "Retrospective view &rarr;</a>"
        "</nav></header>"
        "<main>"
        # hx-swap-error="outerHTML" so non-2xx (e.g. the 500 honest-error fragment)
        # still swaps the body — htmx's default is to drop the swap, which would
        # leave a stale fragment indefinitely after a transient failure
        # (independent-perspective Pre-Mortem 2).
        '<section id="live-section" class="live-section" data-state="loading"'
        ' hx-get="/fragments/live" hx-trigger="load, every 3s"'
        ' hx-swap="outerHTML" hx-swap-error="outerHTML">'
        '<div class="tile tile--loading" data-state="loading">'
        "<h3>Live state</h3>"
        '<p class="loading-copy">'
        "Connecting to live session data &mdash; updates every 3 s."
        "</p></div>"
        "</section>"
        "</main></body></html>"
    )


#: Live-panel CSS extension (appended after the shared ``_CSS``).
#
# ``.tile--loading`` (ux FRICTION-1) — distinct from ``.tile--absent``: solid
# border + a subtle accent left-border + a pulsing opacity animation, so a
# first-paint placeholder reads as "we are connecting" rather than the
# dashed-border "not yet run" honest-absence vocabulary.
#
# ``.lane--primary`` + ``.lane-badge--primary`` (ux FRICTION-2) — the main
# session row gets a green left-border and a small "primary" pill next to
# the agent label, so the gatekeeper can find the top-level session at a
# glance even with several dispatched subagents in flight. The visual
# differentiation is dual-channel (position + color), WCAG 1.4.1.
#
# ``.shell-nav`` / ``.nav-link`` (ux FRICTION-4) — header link to the
# retrospective view; reachable from the live shell without typing a URL.
_LIVE_CSS = """
.live-section{grid-column:1 / -1;display:grid;grid-template-columns:repeat(2,1fr);gap:18px;}
.live-section>.tile--wide{grid-column:1 / -1;}
canvas{max-width:100%;height:auto;}
.runway__bar{height:10px;background:#0d1117;border:1px solid var(--line);border-radius:6px;
overflow:hidden;margin:8px 0;}
.runway__fill{height:100%;background:var(--accent);transition:width .25s ease;}
.runway--amber .runway__fill{background:#d29922;}
.runway--red .runway__fill{background:#f85149;}
.runway--amber .headline{color:#d29922;}
.runway--red .headline{color:#f85149;}
.lane-badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;
border:1px solid var(--line);color:var(--muted);}
tr.lane--active .lane-badge{color:var(--ok);border-color:var(--ok);}
tr.lane--orphaned .lane-badge{color:#f85149;border-color:#f85149;}
tr.lane--complete .lane-badge{color:var(--muted);}
tr.lane--primary>td:first-child{border-left:3px solid var(--ok);}
tr.lane--primary>td{background:rgba(63,185,80,.04);}
.lane-badge--primary{margin-left:8px;color:var(--ok);border-color:var(--ok);
background:rgba(63,185,80,.08);font-weight:600;text-transform:uppercase;
letter-spacing:.4px;font-size:11px;}
.tile--loading{border-style:solid;border-color:var(--accent);
background:linear-gradient(180deg,#161b22,#1a2029);
animation:tile-loading-pulse 1.4s ease-in-out infinite;}
.loading-copy{color:var(--accent);font-size:13.5px;margin:0;}
@keyframes tile-loading-pulse{0%,100%{opacity:1;}50%{opacity:.55;}}
@media (prefers-reduced-motion: reduce){
.tile--loading{animation:none;}
}
.shell-nav{margin-top:6px;}
.nav-link{color:var(--accent);font-size:13px;text-decoration:none;
border-bottom:1px dotted var(--accent);padding-bottom:1px;}
.nav-link:hover{border-bottom-style:solid;}
"""
