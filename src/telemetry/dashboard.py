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
from datetime import UTC
from typing import TypedDict

from src.telemetry.cost import CostReport
from src.telemetry.drift import DRIFT_KINDS, ConfigDriftSignal
from src.telemetry.drift import REMEDIATION_HINTS as DRIFT_REMEDIATION_HINTS
from src.telemetry.failures import (
    ERROR_CLASSES,
    REMEDIATION_HINTS,
    RankedFailure,
    RetryChain,
    classify_error,
    group_retry_chains,
)
from src.telemetry.hooks_health import (
    HOOK_STATUS_MISSING_SCRIPTS,
    HOOK_STATUS_NOT_CONFIGURED,
    HOOK_STATUS_OK,
    HookHealthReport,
)
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
from src.telemetry.weekly import WeeklyTotal, WeeklyTrends

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
        config_drift: Detected config-drift rows (Phase 3 Unit 2 — empty tuple
            when no drift is detected; the renderer distinguishes a true zero
            from the not-yet-known state via ``config_drift_state``).
        config_drift_state: ``"data"`` once the drift detector has inputs to
            reason about (any captured discussion exists), else ``"not_run"``.
            Mirrors :attr:`failures_state`'s true-zero-vs-absence contract.
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
    config_drift: tuple[ConfigDriftSignal, ...] = ()
    config_drift_state: str = STATE_NOT_RUN
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
    """Render the A2 Failure & Waste panel (true-zero vs not-run are distinct).

    Phase 3 Unit 1 (SPEC-20260607-183136): failures are grouped by error class
    with a static remediation hint per group. The ranking order from
    :func:`rank_failures` is preserved *within* each group, and groups are
    ordered by their summed cost (priced groups first, then unpriced by
    wasted tokens, then the canonical class order as the final tiebreaker —
    mirrors the priced-before-unpriced policy in :func:`rank_failures`).
    """
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
    groups_html = "".join(
        _render_failure_class_group(cls, rfs) for cls, rfs in _group_failures_by_class(failures)
    )
    return (
        '<div class="tile tile--data" data-state="data">'
        "<h3>Failure &amp; Waste</h3>"
        f'<div class="headline">{_esc(len(failures))} signal(s) detected</div>'
        '<p class="sub">The most costly class appears first — start there. '
        "Within each group, signals are ranked by wasted API-equivalent cost.</p>"
        f"{groups_html}"
        "</div>"
    )


def _group_failures_by_class(
    failures: list[RankedFailure],
) -> list[tuple[str, list[RankedFailure]]]:
    """Bucket ranked failures by :func:`classify_error`, preserving input order.

    Returns ``(class_name, [ranked_failures])`` pairs in the display order: the
    class with the highest summed priced cost first, then unpriced classes
    ordered by wasted-token total, with :data:`ERROR_CLASSES` providing the
    final tiebreaker so the layout is deterministic across runs.

    Args:
        failures: Already-ranked failures from :func:`rank_failures`.

    Returns:
        Display-ordered list of ``(class, rows)`` tuples. Each ``rows`` keeps
        the inbound rank order (the dollar-weighted ranking is preserved
        within a class).
    """
    buckets: dict[str, list[RankedFailure]] = {}
    for rf in failures:
        buckets.setdefault(classify_error(rf.signal), []).append(rf)
    class_index = {cls: i for i, cls in enumerate(ERROR_CLASSES)}

    def sort_key(item: tuple[str, list[RankedFailure]]) -> tuple[bool, float, int, int]:
        cls, rfs = item
        # ``has_priced`` is ``any(...)`` (not ``all(...)``): a MIXED group with
        # at least one priced row still ranks before a pure-unpriced group, so
        # a small measured cost is not preempted by a large unpriced waste.
        # For a pure-unpriced group ``priced_total`` is 0.0 and the comparison
        # falls through to ``-unpriced_tokens`` — do not add an ``if has_priced``
        # branch here, the third tuple slot already handles it structurally.
        priced_total = sum(rf.cost_usd for rf in rfs if rf.cost_usd is not None)
        unpriced_tokens = sum(rf.signal.wasted_total_tokens() for rf in rfs if rf.cost_usd is None)
        has_priced = any(rf.cost_usd is not None for rf in rfs)
        return (
            not has_priced,
            -priced_total,
            -unpriced_tokens,
            class_index.get(cls, len(ERROR_CLASSES)),
        )

    return sorted(buckets.items(), key=sort_key)


def _render_failure_class_group(cls: str, rfs: list[RankedFailure]) -> str:
    """Render one error-class group: class header + remediation hint + rows.

    Honesty discipline (ADR-0020): the ``other`` group renders with the same
    visual treatment as a real class and surfaces its "does not fit a known
    class" hint — never collapsed away to hide unclassified signals.

    Phase 3 Unit 3 (SPEC-20260610-001134): within each class, consecutive
    retry-loops within ``MAX_RETRY_CHAIN_GAP_SECONDS`` are folded into
    :class:`RetryChain` objects by :func:`group_retry_chains`. Each chain
    renders through :func:`_render_retry_chain`, which short-circuits a
    length-1 chain to the same flat ``<tr>`` shape used before chaining
    (structural-absence invariant A8 — no ``data-chain-size`` attribute,
    no ``retry-chain-link`` child rows for non-chained signals). Non-retry
    signals (today, orphans in the ORPHAN class) bypass the chain layer
    and render directly via :func:`_render_failure_row`.

    Args:
        cls: One of :data:`ERROR_CLASSES`.
        rfs: The ranked failures in this group, already in display order.

    Returns:
        An escaped HTML ``<div class="failure-class-group">`` fragment.
    """
    # Compose chains for retry-loops in this class; non-retry signals are
    # dropped by group_retry_chains and rendered directly below. The skip-set
    # is keyed by ``id(rf.signal)`` (identity, not signature equality) so a
    # future failure type whose signature scheme could collide with a
    # retry-loop signature still composes correctly — arch F1 fold from
    # REV-20260610-003237. ``id()`` is safe here because ``rfs`` and the
    # chains both hold the same ``RankedFailure`` references (the chain
    # walker does not clone signals).
    chains = group_retry_chains(rfs)
    chained_signal_ids: set[int] = set()
    for chain in chains:
        for rf_in_chain in chain.all_links():
            chained_signal_ids.add(id(rf_in_chain.signal))

    body_parts: list[str] = []
    chain_iter = iter(chains)
    next_chain: RetryChain | None = next(chain_iter, None)
    for rf in rfs:
        if id(rf.signal) in chained_signal_ids:
            # This row belongs to a chain — emit the chain when we hit its
            # head, then skip its links as we encounter them.
            if next_chain is not None and rf is next_chain.head:
                body_parts.append(_render_retry_chain(next_chain))
                next_chain = next(chain_iter, None)
            # links are emitted as part of the chain block; skip them here.
            continue
        body_parts.append(_render_failure_row(rf))

    # No ``.get(cls, fallback)``: a missing hint is a programmer error (a new
    # class added to ERROR_CLASSES without a paired entry in REMEDIATION_HINTS).
    # The taxonomy + symmetric-key tests pin both sides; let a future drift
    # surface as a loud KeyError rather than be silently masked by ``other``.
    hint = REMEDIATION_HINTS[cls]
    label = cls.replace("_", " ").capitalize()
    return (
        f'<div class="failure-class-group" data-class="{_esc(cls)}">'
        f'<h4 class="failure-class-header">{_esc(label)} '
        f'<span class="failure-class-count">({_esc(len(rfs))} signal(s))</span></h4>'
        f'<p class="hint">{_esc(hint)}</p>'
        '<table class="data-table">'
        "<thead><tr><th>Type</th><th>Cost</th><th>Wasted tok</th>"
        "<th>Tier</th><th>Detail</th></tr></thead>"
        f"<tbody>{''.join(body_parts)}</tbody></table>"
        "</div>"
    )


def _render_failure_row(rf: RankedFailure) -> str:
    """Render one ranked failure as a flat ``<tr>`` row.

    The pre-Phase-3-Unit-3 row shape, extracted as a helper so the
    length-1 chain short-circuit in :func:`_render_retry_chain` and the
    non-retry rows in :func:`_render_failure_class_group` share one
    source of truth. Length-1 chains emit through this helper directly
    — that is the structural-absence invariant (A8): no chain scaffold
    when there is no cascade to display.
    """
    s = rf.signal
    return (
        "<tr>"
        f"<td>{_esc(s.failure_type)}</td>"
        f'<td class="num">{_esc(_fmt_usd(rf.cost_usd, places=4))}</td>'
        f'<td class="num">{_fmt_int(s.wasted_total_tokens())}</td>'
        f"<td>{_esc(s.tier)}</td>"
        f'<td class="detail">{_esc(s.detail)}'
        f'<span class="sig">{_esc(s.signature)}</span></td>'
        "</tr>"
    )


def _render_retry_chain(chain: RetryChain) -> str:
    """Render one :class:`RetryChain` as a parent ``<tr>`` + N-1 link rows.

    Two shapes (single seam — A8 invariant local to this function):

    * **Length 1** — short-circuit to :func:`_render_failure_row` so the
      output is structurally identical to today's flat row: no
      ``data-chain-size`` attribute, no ``retry-chain-link`` sibling rows,
      no parent-row ``aria-label``. A regression test pins this invariant
      so a future "always render the chain wrapper" refactor surfaces here.
    * **Length ≥ 2** — parent row carries the head's display fields
      replaced by the CHAIN TOTALS (chain-total cost, chain-total wasted
      tokens, chain-size badge in the Detail column) and a
      ``data-chain-size="N"`` attribute + an ``aria-label`` for screen
      readers. N-1 indented link rows follow (CSS class
      ``retry-chain-link``) in temporal order. Honest-absence carried from
      :class:`RetryChain`: a chain whose links are all unpriced renders
      its total as ``uncosted`` (never ``$0``).
    """
    if chain.size() == 1:
        return _render_failure_row(chain.head)

    s_head = chain.head.signal
    chain_size = chain.size()
    aria_label = f"Retry chain ({chain_size} consecutive retries)"
    chain_badge = f" &middot; chain of {chain_size}"
    # Visually-hidden sr-only span carries the chain announcement INSIDE the
    # parent row's first cell as the AUTHORITATIVE screen-reader cue (ux F1
    # MED fold REV-20260610-003237). ``aria-label`` on a ``<tr>`` is
    # documented but inconsistently announced by NVDA / JAWS in
    # table-navigation mode (which reads cell content, not row labels). The
    # sr-only span makes the announcement reliable across ATs because the
    # screen reader WILL read the first cell's text. The ``aria-label`` on
    # the ``<tr>`` is retained as belt-and-braces for ATs that DO announce
    # it (and for any future grid-navigation mode). The "sr-only" CSS class
    # convention (position:absolute;clip-path) is the established
    # Bootstrap/Tailwind pattern; a future stylesheet pass will add the
    # rule (no inline stylesheet on this fragment).
    sr_announce = f'<span class="sr-only">{_esc(aria_label)}: </span>'
    parent_row = (
        f'<tr data-chain-size="{_esc(chain_size)}" '
        f'class="retry-chain-parent" aria-label="{_esc(aria_label)}">'
        f"<td>{sr_announce}{_esc(s_head.failure_type)}</td>"
        f'<td class="num">{_esc(_fmt_usd(chain.total_cost_usd, places=4))}</td>'
        f'<td class="num">{_fmt_int(chain.total_wasted_tokens)}</td>'
        f"<td>{_esc(s_head.tier)}</td>"
        f'<td class="detail">{_esc(s_head.detail)}{chain_badge}'
        f'<span class="sig">{_esc(s_head.signature)}</span></td>'
        "</tr>"
    )
    link_rows: list[str] = []
    for link in chain.links:
        sl = link.signal
        # The leading "↳ " glyph is a NON-COLOR structural cue (WCAG 1.4.1
        # — ux F1 fold T2 checkpoint): a user who overrides background color
        # or cannot perceive the CSS-side indent still sees that link rows
        # are continuation of the parent. ``aria-hidden`` on the glyph wrapper
        # so screen readers (which already get the parent row's aria-label)
        # don't double-announce "right arrow hook" for every link.
        link_rows.append(
            '<tr class="retry-chain-link">'
            f'<td><span class="chain-glyph" aria-hidden="true">&#x21B3; </span>'
            f"{_esc(sl.failure_type)}</td>"
            f'<td class="num">{_esc(_fmt_usd(link.cost_usd, places=4))}</td>'
            f'<td class="num">{_fmt_int(sl.wasted_total_tokens())}</td>'
            f"<td>{_esc(sl.tier)}</td>"
            f'<td class="detail">{_esc(sl.detail)}'
            f'<span class="sig">{_esc(sl.signature)}</span></td>'
            "</tr>"
        )
    return parent_row + "".join(link_rows)


def _render_config_drift_panel(data: DashboardData) -> str:
    """Render the Config drift panel (Phase 3 Unit 2 — sibling of Failure & Waste).

    Three visual states, matching the failures panel's discipline (qa A7):

    * ``not_run`` — the drift detector has no captured corpus to compare
      against. Honest-absence tile.
    * ``data`` + no signals — a true zero. The detector ran and found no
      drift; this is GOOD news, rendered as a normal data tile with explicit
      copy (not the absence style — that distinction matters per spec R3a).
    * ``data`` + signals — group rows by :data:`drift.DRIFT_KINDS`, mirror
      the failure-class-group layout, attach one static remediation hint
      per kind. No cost/wasted-tok column: drift is qualitative; forcing a
      dollar slot here would invite a fabricated ``$0`` (the C4 anti-pattern
      this panel exists to flag in the cost path, ironically).

    Args:
        data: Assembled dashboard data. Reads ``config_drift_state`` and
            ``config_drift`` only — nothing else.
    """
    if data.config_drift_state == STATE_NOT_RUN:
        # qa F2 + ux F1 CONVERGENT fold (REV-20260609-060229): the prior copy
        # pointed at ``analyze_cost.py``, which reads the discussions table but
        # does NOT create it — a user following that hint would loop. Capture
        # is automatic via the framework's command pipeline; the right action
        # is "use the framework" not "run an analyzer."
        return _absence_tile(
            "Config drift",
            "No corpus to compare against yet.",
            "The drift detector needs at least one captured discussion to scan.",
            action_html=(
                "Use the framework (any "
                f"{_code('/plan')}, {_code('/review')}, {_code('/build_module')}, "
                "etc.) — captured discussions appear here automatically."
            ),
        )
    signals = data.config_drift
    if not signals:
        return (
            '<div class="tile tile--data" data-state="data">'
            "<h3>Config drift</h3>"
            '<div class="headline headline--ok">No drift detected</div>'
            '<p class="sub">The current pricing config and subscription fee '
            "match the captured corpus.</p>"
            "</div>"
        )
    groups_html = "".join(
        _render_drift_kind_group(kind, sigs) for kind, sigs in _group_drift_by_kind(signals)
    )
    # ux F2 fold (REV-20260609-060229): the prior sub-copy ended with "tells
    # you how to read it" but left the gatekeeper without a triage anchor —
    # drift has no cost dimension so cannot copy the failures-panel "most
    # costly class" cue. The unknown-model group is canonically first BECAUSE
    # it has the most direct effect on the cost figure (it makes uncosted
    # rows appear), so the start-here cue points there in a multi-group case.
    return (
        '<div class="tile tile--data" data-state="data">'
        "<h3>Config drift</h3>"
        f'<div class="headline">{_esc(len(signals))} drift row(s) detected</div>'
        '<p class="sub">Each group flags where the current config differs from '
        "what was in effect when the corpus was captured. Drift does not invalidate "
        "the cost figure — it tells you how to read it. The first group has the "
        "most direct effect on the cost figure — start there.</p>"
        f"{groups_html}"
        "</div>"
    )


def _group_drift_by_kind(
    signals: tuple[ConfigDriftSignal, ...],
) -> list[tuple[str, list[ConfigDriftSignal]]]:
    """Bucket drift signals by kind, in :data:`drift.DRIFT_KINDS` order.

    Returns ``(kind, [signals])`` pairs in canonical order so a deterministic
    detector input yields a deterministic layout across runs. Within a kind,
    the input order is preserved (the detector module pins the rule for what
    that ordering is, mirroring the failures-panel discipline).

    Args:
        signals: Detected drift signals.

    Returns:
        Display-ordered list of ``(kind, signals)`` tuples.
    """
    buckets: dict[str, list[ConfigDriftSignal]] = {}
    for s in signals:
        buckets.setdefault(s.kind, []).append(s)
    return [(k, buckets[k]) for k in DRIFT_KINDS if k in buckets]


#: Manager-facing label per drift kind. **ux F4 fold (REV-20260609-060229)**:
#: the prior renderer derived labels from ``kind.replace("_", " ").capitalize()``
#: which produced "Unknown model" — readable but missed the chance to name the
#: consequence in the header (the failures-panel labels already do this).
#: Mirrors the ``_LANE_STATUS_LABEL`` / ``_RUNWAY_LABEL`` map pattern earlier
#: in this file; the renderer reads from this map with NO ``.get()`` fallback so
#: a future drift kind added without a paired label surfaces as a loud
#: ``KeyError`` rather than a silent kebab-case header (same fail-loud
#: discipline as the symmetric-key ``DRIFT_REMEDIATION_HINTS`` test).
_DRIFT_KIND_LABEL: dict[str, str] = {
    "unknown_model": "Unpriced model id",
    "stale_pricing": "Stale pricing config",
    "stale_subscription_fee": "Stale subscription fee",
}


def _render_drift_kind_group(kind: str, signals: list[ConfigDriftSignal]) -> str:
    """Render one drift-kind group: kind header + remediation hint + rows.

    Mirrors :func:`_render_failure_class_group`'s shape so the two panels read
    the same — gatekeeper learns one layout, not two. No ``.get(kind, ...)``
    fallback: a missing hint is a programmer error (a new kind added to
    :data:`drift.DRIFT_KINDS` without a paired entry in
    :data:`drift.REMEDIATION_HINTS`); let the drift surface as a loud
    ``KeyError`` rather than be silently masked.

    Args:
        kind: One of :data:`drift.DRIFT_KINDS`.
        signals: The signals in this group, already in display order.
    """
    rows = []
    for s in signals:
        rows.append(
            f'<tr><td>{_esc(s.observed)}</td><td class="detail">{_esc(s.detail)}</td></tr>'
        )
    hint = DRIFT_REMEDIATION_HINTS[kind]
    label = _DRIFT_KIND_LABEL[kind]
    return (
        f'<div class="failure-class-group" data-drift-kind="{_esc(kind)}">'
        f'<h4 class="failure-class-header">{_esc(label)} '
        f'<span class="failure-class-count">({_esc(len(signals))} row(s))</span></h4>'
        f'<p class="hint">{_esc(hint)}</p>'
        '<table class="data-table">'
        "<thead><tr><th>Observed</th><th>Detail</th></tr></thead>"
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
.failure-class-group{margin-top:14px;padding-top:10px;border-top:1px solid var(--line);}
.failure-class-group:first-of-type{margin-top:10px;border-top:none;padding-top:0;}
.failure-class-header{margin:0 0 4px;font-size:14px;}
.failure-class-count{color:var(--muted);font-weight:500;font-size:12.5px;}
.hint{color:var(--muted);font-size:12.5px;margin:0 0 8px;font-style:italic;}
.detail{font-size:12px;}
.sig{display:block;color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
font-size:11px;margin-top:3px;word-break:break-all;}
/* Retry-chain nesting (Phase 3 Unit 3 — ux F1 + F2 fold REV-20260610-003237).
   .sr-only: visually-hidden span carrying the chain announcement inside the
   parent row's first cell — reliable screen-reader cue across NVDA/JAWS/VO
   in table-navigation mode (where aria-label on a <tr> is inconsistently
   announced). .retry-chain-parent: slight font weight to signal the row
   leads its group. .retry-chain-link td:first-child: left padding stacks
   with the U+21B3 glyph so the indent survives CJK font fallback. */
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;
overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;}
.retry-chain-parent td:first-child{font-weight:500;}
.retry-chain-link td:first-child{padding-left:22px;}
.chain-glyph{color:var(--muted);}
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
        f"{_render_config_drift_panel(data)}"
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

    if data.config_drift_state == STATE_NOT_RUN:
        lines.append("Config drift: not yet checked (no captured corpus)")
    elif not data.config_drift:
        lines.append("Config drift: none detected")
    else:
        lines.append(f"Config drift: {len(data.config_drift)} row(s) detected")

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
    if data.config_drift_state == STATE_NOT_RUN:
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

#: Manager-facing label per hook-health status (SPEC-20260610-005602 arch F5:
#: the status *constants* live in ``src/telemetry/hooks_health.py`` — the pure
#: model owns the vocabulary — while this map carries the human-readable copy
#: and is the only renderer-side translation, co-located with the other live
#: label maps above). Lookups are fail-loud ``[status]`` (the Unit 1
#: discipline): an unmapped status is a render-layer bug, not a silent default.
_HOOK_HEALTH_STATUS_LABEL = {
    HOOK_STATUS_OK: "OK",
    HOOK_STATUS_MISSING_SCRIPTS: "missing",
    HOOK_STATUS_NOT_CONFIGURED: "not configured",
}


def render_hook_health_chip(report: HookHealthReport) -> str:
    """Render the read-only hook-health chip (SPEC-20260610-005602 R-4.1.3).

    A compact full-width strip summarizing whether the framework's enforcement
    hooks are configured and their script files present, plus narrowly-labelled
    recency evidence. Two honesty rules are load-bearing here (R-4.1.4):

    * The recency copy names the **quality gate** specifically ("quality gate
      last ran ..." / "no quality-gate run observed") — the gate log evidences
      exactly ONE hook's underlying gate, so the copy must never widen the
      claim to "hooks last fired".
    * ``not_configured`` is the typed honest-absence state and renders as an
      explicit chip (dashed border, "not configured" label), never an error
      and never silence.

    Args:
        report: The pure health report assembled by
            :func:`src.telemetry.hooks_health.assess_hook_health` from facts
            the transport layer resolved read-only.

    Returns:
        One ``<div class="hook-chip ...">`` element. Every dynamic string
        field is ``_esc``'d HERE, inside the helper (spec security F3) — the
        caller contract on :func:`render_live_fragment` relies on it.
    """
    status_label = _HOOK_HEALTH_STATUS_LABEL[report.status]
    missing_html = ""
    if report.status == HOOK_STATUS_NOT_CONFIGURED:
        summary = f"Hooks: {status_label}"
        title = "No hook entries were found in .claude/settings.json."
    elif report.status == HOOK_STATUS_MISSING_SCRIPTS:
        missing_names = ", ".join(report.scripts_missing)
        summary = (
            f"Hooks: {len(report.scripts_missing)} of {report.hooks_configured} "
            f"hook scripts {status_label}"
        )
        title = f"Missing under .claude/hooks/: {missing_names}"
        # The missing basenames are the actionable detail — they must be
        # VISIBLE text, not title-attribute-only (ux checkpoint fold: a
        # title attribute is unreachable for keyboard/touch users and most
        # screen-reader browse modes; WCAG 1.3.1). The title stays as a
        # convenience layer.
        missing_html = f'<span class="hook-chip__missing">Missing: {_esc(missing_names)}</span>'
    else:
        summary = f"Hooks: {report.hooks_configured} configured — {status_label}"
        title = "All hook scripts referenced by .claude/settings.json are present."
    if report.last_gate_run is None:
        recency = "no quality-gate run observed"
    else:
        stamp = report.last_gate_run.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
        recency = f"quality gate last ran {stamp}"
    return (
        f'<div class="hook-chip hook-chip--{_esc(report.status)}" '
        f'data-hook-health="{_esc(report.status)}" title="{_esc(title)}">'
        f'<span class="hook-chip__label">{_esc(summary)}</span>'
        f"{missing_html}"
        f'<span class="hook-chip__recency">{_esc(recency)}</span>'
        "</div>"
    )


@dataclass(frozen=True)
class LiveFragmentPanels:
    """Pre-rendered HTML panels the transport layer passes into the live fragment.

    Rule-of-Three fold (SPEC-20260610-015114, discharging the watchpoint
    pinned in SPEC-20260610-005602): the model-cost donut would have been
    the THIRD additive pre-rendered-HTML keyword param on
    :func:`render_live_fragment`, so the params folded into this single
    container instead.

    **Additive-only evolution rule (spec arch F3)**: a future fourth panel
    adds a field here with an empty-string default — never a new
    positional/keyword parameter on :func:`render_live_fragment` itself.
    An empty-string field means "panel absent"; existing callers are
    unaffected by new fields.

    **Caller contract (SPEC-20260610-005602 security F3)**: every field
    MUST carry only HTML produced by a ``src.telemetry.dashboard`` render
    helper (:func:`render_hook_health_chip`,
    :func:`render_weekly_trends_chart_panel`,
    :func:`render_model_cost_donut_panel`) — those helpers apply ``_esc``
    to every dynamic field internally. Passing raw or hand-built strings
    bypasses all escaping and is an injection bug.

    Attributes:
        hook_health_chip_html: Hook-health chip strip, rendered FIRST
            (above the runway) — a precondition banner framing how much to
            trust everything below it (SPEC-20260610-005602).
        weekly_panel_html: Weekly trends chart panel (persisted-corpus
            derived view; transport owns the DB IO).
        model_cost_donut_html: Model-cost donut panel, rendered LAST — the
            broadest derived view (whole stored corpus, no time axis) per
            the broader-after-narrower hierarchy.
    """

    hook_health_chip_html: str = ""
    weekly_panel_html: str = ""
    model_cost_donut_html: str = ""


def render_live_fragment(state: LiveState, panels: LiveFragmentPanels | None = None) -> str:
    """Render the htmx live fragment (agent lanes + runway + cost/failure stream + charts).

    Returned as ONE root ``<section>`` so an htmx ``hx-swap="outerHTML"`` swap
    replaces the previous fragment cleanly. The server polls this endpoint on
    a server-specified interval (spec R2 — htmx polling, not SSE in Phase 1).

    Composition order is the visual-hierarchy contract: hook-health chip
    (precondition banner) → runway (highest-stakes "how much headroom do I
    have?") → lanes (operational state) → stream (per-event trail) →
    per-turn cost chart (recent-window derived view) → weekly trends chart
    (broader-window derived view) → model-cost donut (broadest derived
    view: the whole stored corpus, no time axis). Charts appear LAST
    because they are derived views of the stream data above them, ordered
    narrower-to-broader so the reader's eye travels from "what just
    happened" to "what's the longer arc". A future chart slotting in must
    respect this broader-after-narrower hierarchy.

    Args:
        state: The pure live model snapshot. The persisted-corpus panels
            (weekly chart, donut) do NOT read it — their data comes from
            the DB at the transport layer, which passes pre-rendered HTML
            via ``panels`` so the live model (``src/telemetry/live.py``)
            stays pure (AC14).
        panels: Optional pre-rendered panel container. ``None`` (the
            default) renders no extra panels — the backward-compatible
            shape for tests and callers without a transport layer in
            scope. See :class:`LiveFragmentPanels` for the caller contract
            and the additive-only evolution rule.
    """
    panels = panels or LiveFragmentPanels()
    return (
        '<section id="live-section" class="live-section" data-state="live">'
        f"{panels.hook_health_chip_html}"
        f"{_render_runway_panel(state.runway)}"
        f"{_render_agent_lanes_panel(state)}"
        f"{_render_live_stream_panel(state.recent_events)}"
        f"{_render_per_turn_cost_chart_panel(state.recent_events)}"
        f"{panels.weekly_panel_html}"
        f"{panels.model_cost_donut_html}"
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


def _json_in_script(payload: object) -> str:
    """Serialise ``payload`` to JSON safe to bake inside a ``<script>`` block.

    Rule-of-Three extraction (REV-20260608-053032): when the per-turn cost
    chart shipped (REV-20260608-025749), the inline escape chain was pinned
    with an explicit "extract when a second consumer lands" docstring promise.
    The weekly trends chart (Phase 2 second consumer) is that moment, so the
    chain is now a single function call site.

    The four-step contract (each step is load-bearing — silently dropping any
    one of them re-opens a different injection surface):

    * ``json.dumps(..., separators=(",", ":"), allow_nan=False)`` — compact
      separators keep the payload small; ``allow_nan=False`` converts a
      non-finite numeric (``NaN`` / ``Infinity``) from a silent invalid token
      (per RFC 8259 §3) into a loud :class:`ValueError` at render time
      (security F1 + qa F3 from REV-20260608-025749). Without this flag, the
      browser's ``JSON.parse`` crashes on the rendered fragment.
    * ``"</"`` → ``"<\\/"`` — HTML5 parses ``<script>`` bodies in raw-text
      mode and ends the block on the byte sequence ``</`` followed by a name
      match. A transcript-shaped string carrying ``"</script><script>"`` in a
      payload field could otherwise close the data block and inject arbitrary
      script. The escaped form is valid JSON per RFC 8259 §7 and round-trips
      through ``JSON.parse`` unchanged.
    * ``"<!--"`` → ``"<\\!--"`` and ``"-->"`` → ``"--\\>"`` (security F1 fold
      from REV-20260608-042729) — HTML5 raw-text-mode also recognises HTML
      comment delimiters inside a ``<script>`` body and can swallow the
      intervening bytes, breaking ``JSON.parse``. Both escaped forms are
      valid JSON per RFC 8259 §7.

    The helper does **not** know which consumer is calling — it is the single
    chokepoint for *every* ``<script type="application/json">`` data block
    in this codebase. A future third consumer (e.g. a runway-history chart)
    must route through this function, not re-inline the chain.

    Args:
        payload: Any JSON-serialisable Python value (typically a list of
            ``TypedDict`` rows). Non-finite ``float`` values raise
            :class:`ValueError` per ``allow_nan=False``.

    Returns:
        The serialised JSON string with the three HTML5-defensive escapes
        applied.

    Raises:
        ValueError: If ``payload`` contains a non-finite ``float``.
        TypeError: If ``payload`` contains a non-serialisable value (standard
            ``json.dumps`` semantics).
    """
    return (
        json.dumps(payload, separators=(",", ":"), allow_nan=False)
        .replace("</", "<\\/")
        .replace("<!--", "<\\!--")
        .replace("-->", "--\\>")
    )


#: Data-block element id for the per-turn cost chart's JSON payload.
#:
#: The Phase 2 init script at ``/static/dashboard-chart.js`` looks this id up
#: with ``document.getElementById`` and parses its ``textContent`` as JSON.
#: Pulling the id out as a module constant keeps the renderer + the init
#: script + the regression tests pointing at one source of truth (the
#: integration-points regression test in tests/test_dashboard_server.py
#: asserts the literal string appears in the JS file).
_PER_TURN_COST_DATA_ELEMENT_ID = "per-turn-cost-data"

#: Canvas element id for the per-turn cost chart.
_PER_TURN_COST_CANVAS_ID = "per-turn-cost-chart"

#: Wrapper element class for the canvas + data block. The init script at
#: ``/static/dashboard-chart.js`` removes the ``hidden`` attribute on this
#: wrapper + flips the parent tile's ``data-state`` from ``"loading"`` to
#: ``"data"`` (and removes the ``tile--loading`` class) on first successful
#: draw. Until then the wrapper is HTML5-``hidden`` so the user sees the
#: loading copy, not a blank canvas — the brief visible window for this
#: state is between page load and the first ``htmx:afterSwap`` event.
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
      init script at ``/static/dashboard-chart.js`` routes priced and uncosted
      turns into two Chart.js datasets so uncosted turns appear as distinct
      cross markers at the y=0 baseline (no connecting line), preserving the
      "uncosted ≠ \\$0" honesty discipline of the static cost report
      (ADR-0020) — uncosted points are MARKED, not HIDDEN. Always ``False``
      for ``"failure"`` events, which the renderer filters out before the
      payload is built.

    **Schema evolution rule:** adding a field is non-breaking IFF the init script
    treats unknown fields as opaque. Removing or renaming an existing field is
    a breaking change that requires updating the init script in the same commit.
    The init script at ``/static/dashboard-chart.js`` honors this contract:
    it reads only ``t``, ``cost``, and ``uncosted`` (``lane_id`` is part of
    the payload but the JS consumer ignores it — it stays in the JSON because
    the live-stream panel surfaces it elsewhere and consistency of the payload
    shape across panels matters more than minimising JS-side use). A future
    5th field is therefore non-breaking.
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

    **Interim visual state** (ux F1 from REV-20260608-025749): the Python
    renderer emits the data-present path as ``tile--loading`` with the canvas
    + data block in an HTML5-``hidden`` wrapper. The first-party init script
    at ``/static/dashboard-chart.js`` (Phase 2 step 4 — landed in the same
    cohort) is what removes the ``hidden`` attribute + flips the tile's
    ``data-state`` to ``"data"`` + drops the ``tile--loading`` class on first
    successful draw. The wrapper-hidden + loading-pulse state is therefore
    only visible during the brief window before the first ``htmx:afterSwap``
    has fired (and again on any rare frame where the JS bails — Chart global
    unavailable, no payload, JSON parse failure — in which case the loading
    copy is the honest fallback). Server-side tests still assert the
    ``tile--loading`` emission because the Python renderer is what writes
    that markup; the JS-side reveal is exercised by the integration tests
    that pin the init script's `<script src=...>` tag is wired into the
    shell head AFTER the Chart.js library tag (load order matters).

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

    **Rule-of-Three pin** (arch F3 from REV-20260608-025749 — RESOLVED at
    REV-20260608-053032): the JSON-in-script escape was inlined here as the
    sole consumer until the weekly trends chart shipped (Phase 2 second
    consumer). The chain is now consolidated in :func:`_json_in_script`; this
    panel and the weekly trends panel both route through it, and any future
    third consumer must call the helper rather than re-inlining the chain.
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
    payload = _json_in_script(points)
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


#: Data-block element id for the weekly trends chart's JSON payload (mirror of
#: ``_PER_TURN_COST_DATA_ELEMENT_ID``). The integration-points regression test
#: in ``tests/test_dashboard_server.py`` pins this literal in the Python
#: source AND the JS init script AND at least one test file (the id-string
#: pin extended at REV-20260608-053032 when the chart became the second
#: consumer in the codebase).
_WEEKLY_TRENDS_DATA_ELEMENT_ID = "weekly-trends-data"

#: Canvas element id for the weekly trends chart.
_WEEKLY_TRENDS_CANVAS_ID = "weekly-trends-chart"

#: The two chart panels share the same render-target class — the JS init
#: script's reveal logic (``.chart-rendering-target`` + ``hidden`` removal +
#: ``tile--loading`` → ``tile--data`` flip) is parameterless on the wrapper
#: class, so both charts use one class. Each chart still has its own canvas
#: + data-block ids, which is what the per-chart init function discriminates
#: on.


class _WeeklyChartTier(TypedDict):
    """One stack slice (per tier) inside one week's bar in the weekly chart.

    Schema:
      * ``tier`` — tier key (``"opus"`` / ``"sonnet"`` / ``"haiku"`` / ``"unknown"``).
      * ``tokens`` — total tokens this tier contributed this week.
      * ``cost_usd`` — API-equivalent USD for the tier this week, or ``None``
        when the tier is uncosted (the ``unknown`` tier or a known model
        absent from ``config/model_pricing.yaml``). The JS init script keys
        on the ``null`` value to route the slice into the uncosted stack
        treatment (``COLOR_MUTED`` + the "(model tier unpriced)" legend).
    """

    tier: str
    tokens: int
    cost_usd: float | None


class _WeeklyChartPoint(TypedDict):
    """One week's entry in the weekly trends chart payload.

    Schema:
      * ``week_start`` — ISO calendar date (``YYYY-MM-DD``) of the Monday of
        the ISO week.
      * ``priced_cost_usd`` — sum of every priced tier's cost for the week.
        Carried in the payload for tooltip / future use; the bar height is
        the sum of ``by_tier[*].tokens`` (token units, not USD).
      * ``total_tokens`` — sum of every tier's tokens (priced + uncosted).
      * ``uncosted_tokens`` — subset of ``total_tokens`` that was uncosted.
      * ``by_tier`` — chronologically deterministic list of per-tier
        stack slices.

    **Schema evolution rule** (mirrors :class:`_ChartPoint`): adding a field
    is non-breaking iff the JS init script treats unknown fields as opaque;
    removing or renaming an existing field requires updating the init script
    in the same commit.
    """

    week_start: str
    priced_cost_usd: float
    total_tokens: int
    uncosted_tokens: int
    by_tier: list[_WeeklyChartTier]


def _render_weekly_delta_caption(weeks: tuple[WeeklyTotal, ...]) -> str:
    """Render the prior-window delta caption shown under the weekly chart.

    Compares the most recent week's ``priced_cost_usd`` against the
    immediately previous week's. The caption is **omitted** (returned as the
    empty string) when:

    * Fewer than two weeks of data exist — no delta can be computed; or
    * The prior week's ``priced_cost_usd`` is exactly ``0.0`` — a percentage
      change against a zero denominator is undefined, and a fabricated
      "+∞%" / "+N/A" caption would violate the ADR-0020 honest-absence
      discipline. The chart bars still show the change visually; the
      caption is just suppressed for that one week.

    The caption is server-rendered HTML (escaped via :func:`_esc`) so the
    JS layer carries no copy-formatting logic. R6 in
    SPEC-20260607-183136 calls for prior-window deltas as part of the
    weekly trends surface; this is the surface.
    """
    if len(weeks) < 2:
        return ""
    current = weeks[-1]
    prior = weeks[-2]
    if prior.priced_cost_usd == 0.0:
        return ""
    delta_pct = (current.priced_cost_usd - prior.priced_cost_usd) / prior.priced_cost_usd * 100.0
    sign = "+" if delta_pct >= 0 else ""
    rounded = _esc(round(delta_pct, 1))
    return (
        '<p class="src weekly-delta">'
        f"Most recent week vs prior week: <strong>{_esc(sign)}{rounded}%</strong> "
        f"in API-equivalent USD ({_esc(_fmt_usd(current.priced_cost_usd, places=2))} vs "
        f"{_esc(_fmt_usd(prior.priced_cost_usd, places=2))})."
        "</p>"
    )


def render_weekly_trends_chart_panel(trends: WeeklyTrends) -> str:
    """Render the weekly trends chart panel (spec R6 weekly trends + prior-window deltas).

    Second chart consumer in the codebase, slotted **after** the per-turn
    cost chart in :func:`render_live_fragment`. The visual-hierarchy contract
    is "broader window after broader window" — the per-turn chart shows the
    rolling event window (capped at :data:`~src.telemetry.live.RECENT_EVENTS_CAP`),
    the weekly chart shows the stored corpus aggregated by ISO calendar week.
    A reader who has scanned the upstream panels (runway → lanes → stream →
    per-turn chart) reaches the weekly chart with the recent context already
    loaded, and the weekly chart contextualises that recent activity against
    the longer arc. Pinning this placement in the docstring closes the door
    on a future third chart silently inverting the hierarchy.

    **Honesty contract** (ADR-0020 / spec R3/R3a): the visual unit is
    *tokens*, not USD, because the uncosted slice has no USD figure to
    plot — choosing tokens lets the uncosted slice stack into the same bar
    as the priced tiers without a fabricated zero. Cost-per-tier is carried
    in the payload for the JS tooltip ("Cost: $1.23" for priced tiers;
    "Uncosted (no list price)" for the unknown slice). The "uncosted ≠ $0"
    discipline is preserved: uncosted tokens are MARKED (their own stack
    slice with a distinctive color + named label), NOT hidden.

    **Interim visual state** (mirror of the per-turn chart's ux F1 fold):
    the data-present path emits ``tile--loading`` with the canvas + data
    block in an HTML5-``hidden`` wrapper, the same way the per-turn chart
    does. The JS init script's ``renderWeeklyChart()`` removes ``hidden`` +
    flips the tile to ``data-state="data"`` on first successful draw.

    **Security contract** (REV-20260608-053032 _json_in_script extraction):
    the payload routes through :func:`_json_in_script` — the same helper
    the per-turn chart now uses. Both consumers share one auditable escape
    chain (``json.dumps + allow_nan=False`` + the three HTML5-defensive
    replacements). Any third consumer must route through the helper too,
    not re-inline the chain.

    Honest absence: an empty :class:`~src.telemetry.weekly.WeeklyTrends`
    renders the visually-distinct absence tile, never an empty chart with
    fabricated axes. The "no stored rows yet" message matches the
    cost-report absence tile's vocabulary (the weekly chart is a longer-arc
    derived view of the same stored corpus).
    """
    if not trends.weeks:
        return _absence_tile(
            "Weekly cost trends",
            "No stored cost rows yet.",
            "The weekly trends chart aggregates the stored cost rows by ISO "
            "calendar week. Run scripts/telemetry/analyze_cost.py against the "
            "captured discussions to populate this panel.",
        )
    points: list[_WeeklyChartPoint] = [
        {
            "week_start": week.week_start.isoformat(),
            "priced_cost_usd": week.priced_cost_usd,
            "total_tokens": week.total_tokens,
            "uncosted_tokens": week.uncosted_tokens,
            "by_tier": [
                {"tier": t.tier, "tokens": t.total_tokens, "cost_usd": t.cost_usd}
                for t in week.by_tier
            ],
        }
        for week in trends.weeks
    ]
    payload = _json_in_script(points)
    aria_label = (
        "Weekly cost trends — stacked bar chart of token volume per ISO "
        "week, broken down by model tier; uncosted tiers are marked as a "
        "distinct stack slice so the priced-vs-uncosted split is visible."
    )
    delta_caption = _render_weekly_delta_caption(trends.weeks)
    return (
        '<div class="tile tile--loading tile--wide" data-state="loading">'
        "<h3>Weekly cost trends</h3>"
        '<p class="legend">Token volume per ISO calendar week, stacked by '
        "model tier. Y-axis is total tokens (input + output + cache); X-axis "
        "is ISO week start (Monday). Hover a stack for cost in API-equivalent "
        "USD. The <em>uncosted</em> slice is tokens from model tiers without "
        "a known price — marked, never collapsed to $0 (per ADR-0020).</p>"
        '<p class="loading-copy">Chart visualization layer initializing &mdash; '
        "the stacked-bar chart will draw once the rendering layer is ready. "
        "Per-tier figures are also shown in the retrospective cost panel.</p>"
        f'<div class="{_PER_TURN_COST_RENDER_TARGET_CLASS}" hidden>'
        f'<canvas id="{_WEEKLY_TRENDS_CANVAS_ID}" width="800" height="260"'
        f' role="img" aria-label="{_esc(aria_label)}">'
        "<p>Weekly cost trends chart (data available; chart rendering "
        "requires a visual display).</p>"
        "</canvas>"
        f'<script id="{_WEEKLY_TRENDS_DATA_ELEMENT_ID}" type="application/json">'
        f"{payload}"
        "</script>"
        "</div>"
        f"{delta_caption}"
        "</div>"
    )


#: Data-block element id for the model-cost donut's JSON payload (id-pin
#: convention: the literal also appears in ``/static/dashboard-chart.js`` and
#: the integration-points regression test in tests/test_dashboard_server.py
#: asserts it is present there).
_MODEL_COST_DONUT_DATA_ELEMENT_ID = "model-cost-donut-data"

#: Canvas element id for the model-cost donut chart.
_MODEL_COST_DONUT_CANVAS_ID = "model-cost-donut-chart"


class _DonutSlice(TypedDict):
    """The chart-data contract baked into the model-cost donut's JSON block.

    One entry per tier in :attr:`~src.telemetry.cost.CostReport.by_tier` —
    priced AND uncosted (the JS draws slices only for ``uncosted: false``
    entries; uncosted entries stay in the payload so the data block is the
    complete honest record, ADR-0020):

    * ``tier`` — tier key string (DB-origin, untrusted; escaped at the JSON
      boundary by :func:`_json_in_script` and at the HTML boundary by
      ``_esc`` in the caption).
    * ``cost_usd`` — API-equivalent USD as a finite float for a priced tier;
      ``None`` (JSON ``null``) for an uncosted tier — never ``0.0``.
    * ``tokens`` — all billable tokens accumulated for the tier.
    * ``uncosted`` — ``True`` iff the tier has no list price.

    **Schema evolution rule** (mirrors ``_ChartPoint``): adding a field is
    non-breaking IFF the init script treats unknown fields as opaque;
    removing or renaming a field requires updating
    ``/static/dashboard-chart.js`` in the same commit.
    """

    tier: str
    cost_usd: float | None
    tokens: int
    uncosted: bool


def _donut_slices(report: CostReport) -> list[_DonutSlice]:
    """Order the report's tiers into the donut payload deterministically.

    Priced tiers first (cost descending), then uncosted tiers (tokens
    descending), tier name as the final tiebreaker — the same
    priced-first discipline as ``rank_failures``. Sorting (rather than
    relying on ``by_tier`` dict insertion order) pins the payload order
    against future ``build_cost_report`` refactors (spec qa F4).
    """
    priced = [tc for tc in report.by_tier.values() if tc.cost_usd is not None]
    uncosted = [tc for tc in report.by_tier.values() if tc.cost_usd is None]
    # ``or 0.0`` is unreachable at runtime (priced is pre-filtered to
    # ``cost_usd is not None``); it exists only to give the type checker a
    # plain ``float`` to negate. A genuine 0.0-cost tier sorts by tier name
    # (-0.0 == 0.0), which is correct and deterministic.
    priced.sort(key=lambda tc: (-(tc.cost_usd or 0.0), tc.tier))
    uncosted.sort(key=lambda tc: (-tc.total_tokens(), tc.tier))
    return [
        {
            "tier": tc.tier,
            "cost_usd": tc.cost_usd,
            "tokens": tc.total_tokens(),
            "uncosted": tc.cost_usd is None,
        }
        for tc in priced + uncosted
    ]


def _render_donut_uncosted_caption(uncosted: list[_DonutSlice]) -> str:
    """Render the explicit uncosted-tiers caption (ADR-0020: marked, never $0).

    Empty input renders nothing — a fully-priced corpus needs no caveat
    (and the absence of the caption is itself pinned by the single-slice
    test, spec AC1b).
    """
    if not uncosted:
        return ""
    names = ", ".join(s["tier"] for s in uncosted)
    total = sum(s["tokens"] for s in uncosted)
    return (
        f'<p class="note">Uncosted: {_esc(_fmt_int(total))} tokens across '
        f"tier(s) {_esc(names)} have no known list price and are not drawn "
        "in the donut &mdash; uncosted, not free (ADR-0020).</p>"
    )


def _render_donut_cost_breakdown(priced: list[_DonutSlice]) -> str:
    """Render the always-visible per-tier dollar line (ux F1, REV this unit).

    The donut's dollar figures are otherwise hover-tooltip-only — a
    pointer-gated interaction that keyboard and screen-reader users cannot
    reach (WCAG 1.1.1 / 2.1.1). This plain-text line surfaces the same
    numbers without hover, rendered server-side so no JS is involved.
    Empty input renders nothing (the chart tile is only emitted when at
    least one priced tier exists, so this is defensive).
    """
    if not priced:
        return ""
    items = "; ".join(
        f"{_esc(s['tier'])} {_esc(_fmt_usd(s['cost_usd'], places=4))}" for s in priced
    )
    return f'<p class="src">Per-tier cost: {items}.</p>'


def render_model_cost_donut_panel(report: CostReport, has_run: bool) -> str:
    """Render the model-cost donut panel (SPEC-20260610-015114, Phase 4 Unit 4.2).

    Third chart consumer, composed LAST in :func:`render_live_fragment`
    (the broadest derived view: whole stored corpus, no time axis — the
    pinned broader-after-narrower hierarchy). Public so Phase 5's
    ``--render-static`` export reuses the same helper (R15 single render
    path); callable without a server.

    **Honesty contract (ADR-0020 / spec R3)**: the visual unit is USD, so
    an uncosted tier has no honest slice size — uncosted tiers are NEVER
    drawn as $0 slices. They stay in the JSON payload flagged
    ``uncosted: true`` and are named in an explicit caption with their
    token count (the inverse resolution of the weekly chart, whose
    token-unit choice let uncosted stack honestly). Three data states:

    * ``has_run`` False — analyzer never ran: honest absence tile.
    * ``has_run`` True, no priced tier: "nothing priced to chart" data
      tile naming any uncosted tiers — never an empty donut.
    * Priced tiers present: the chart tile (``tile--loading`` + ``hidden``
      wrapper until the init script's first successful draw).

    The canvas ``aria-label`` is fully static copy (no tier names
    interpolated — spec sec F1); dynamic strings in the caption route
    through ``_esc`` and the payload through :func:`_json_in_script`.

    Args:
        report: The per-tier cost breakdown (read-side, from
            ``load_cost_report`` at the transport layer).
        has_run: True iff the cost analyzer has run (rows or watermark
            present) — distinguishes true-zero from not-yet-run.
    """
    if not has_run:
        return _absence_tile(
            "Model cost split",
            "No stored cost rows yet.",
            "This panel fills in once the cost analyzer "
            "(scripts/telemetry/analyze_cost.py) has processed the captured "
            "session data — ask your developer to run it, or run it from "
            "the repository root.",
        )
    slices = _donut_slices(report)
    priced = [s for s in slices if not s["uncosted"]]
    uncosted = [s for s in slices if s["uncosted"]]
    if not priced:
        # sec F1 fold (REV, this unit): tier names are escaped PER-SITE at
        # the interpolation point (the caption helper's discipline), not
        # deferred to a wrapping _esc at emission — a deferred escape is a
        # refactor trap (hoisting the f-string out of the wrapper would
        # silently open the seam). ``body`` is therefore emitted raw below:
        # it contains only static copy + the pre-escaped listing.
        if uncosted:
            listing = "; ".join(
                f"{_esc(s['tier'])} ({_esc(_fmt_int(s['tokens']))} tokens)" for s in uncosted
            )
            body = (
                "All stored cost rows belong to tiers without a known list "
                "price, so there is no priced cost to chart. Uncosted tiers: "
                f"{listing}. Uncosted is not free — your developer can add "
                "prices for these tiers in config/model_pricing.yaml."
            )
        else:
            body = (
                "The cost analyzer has run but found no stored cost rows "
                "yet. The chart will fill in once the framework has "
                "captured session data and the analyzer has processed it."
            )
        return (
            '<div class="tile tile--data" data-state="data">'
            "<h3>Model cost split</h3>"
            f'<p class="sub">{body}</p>'
            "</div>"
        )
    payload = _json_in_script(slices)
    aria_label = (
        "Model cost split — doughnut chart of API-equivalent USD cost per "
        "model tier across the stored corpus; only priced tiers are drawn "
        "as slices, and tiers without a known list price are listed in a "
        "caption instead of being charted as zero."
    )
    return (
        '<div class="tile tile--loading" data-state="loading">'
        "<h3>Model cost split</h3>"
        '<p class="legend">What each model tier would cost at standard API '
        "prices (API-equivalent USD), across all captured sessions. Slices "
        "are priced tiers only; hover a slice for its dollar figure. Tiers "
        "without a known list price are named below the chart &mdash; "
        "marked, never collapsed to $0 (per ADR-0020).</p>"
        '<p class="loading-copy">Chart visualization layer initializing '
        "&mdash; the doughnut will draw once the rendering layer is ready. "
        "Per-tier figures are also shown in the retrospective cost panel.</p>"
        f'<div class="{_PER_TURN_COST_RENDER_TARGET_CLASS}" hidden>'
        f'<canvas id="{_MODEL_COST_DONUT_CANVAS_ID}" width="400" height="260"'
        f' role="img" aria-label="{_esc(aria_label)}">'
        "<p>Model cost split chart (data available; chart rendering "
        "requires a visual display).</p>"
        "</canvas>"
        f'<script id="{_MODEL_COST_DONUT_DATA_ELEMENT_ID}" type="application/json">'
        f"{payload}"
        "</script>"
        "</div>"
        f"{_render_donut_cost_breakdown(priced)}"
        f"{_render_donut_uncosted_caption(uncosted)}"
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

    The first-party ``dashboard-chart.js`` init script is loaded ``defer``
    AFTER the Chart.js library tag: with ``defer``, the browser executes the
    two scripts in document order so the ``Chart`` global is guaranteed
    available when the init script's IIFE runs (CSP fork DECIDED 2026-06-07,
    option (a) VENDORED-INIT — same-origin under the existing
    ``script-src 'self'`` policy, NO ``'unsafe-inline'`` relaxation). The
    script listens for ``htmx:afterSwap`` on ``#live-section`` so it
    re-initialises the chart on every 3-second poll (the swap destroys the
    previous canvas DOM node).

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
        '<script src="/static/dashboard-chart.js" defer></script>'
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
.hook-chip{grid-column:1 / -1;display:flex;gap:14px;align-items:baseline;
flex-wrap:wrap;padding:6px 12px;border:1px solid var(--line);border-radius:8px;
font-size:13px;color:var(--muted);}
.hook-chip__label{font-weight:600;}
.hook-chip--ok{border-color:var(--ok);}
.hook-chip--ok .hook-chip__label{color:var(--ok);}
.hook-chip--missing_scripts{border-color:#d29922;}
.hook-chip--missing_scripts .hook-chip__label{color:#d29922;}
.hook-chip__missing{color:#d29922;}
.hook-chip--not_configured{border-style:dashed;}
.hook-chip--not_configured .hook-chip__label{color:var(--ink);}
.shell-nav{margin-top:6px;}
.nav-link{color:var(--accent);font-size:13px;text-decoration:none;
border-bottom:1px dotted var(--accent);padding-bottom:1px;}
.nav-link:hover{border-bottom-style:solid;}
"""
