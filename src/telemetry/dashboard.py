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
from dataclasses import dataclass

from src.telemetry.cost import CostReport
from src.telemetry.failures import RankedFailure
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


def _otel_link(label: str = "enable OTel") -> str:
    """Render the OTel docs URL as a live new-tab hyperlink (spec R3a/ADVISORY 1)."""
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
