"""Telemetry Layer A3 — value-vs-subscription leverage + estimate cross-check.

Pure, side-effect-free logic (the only side effect is reading the subscription
YAML when a caller asks for the default fee). Two honest, locally-computed
metrics that turn A1's bottom-up dollar cost into something a developer can
reason about, **without any billing API or credential**:

* **Leverage** — A1's API-equivalent cost vs the developer's flat monthly
  subscription fee. Reports a *labelled* time basis (cumulative over the cost
  window **and** a per-month figure) so a multi-month cumulative cost is never
  silently compared to one month's fee (ADR-0013 / Steward condition: an
  over-confident leverage number is a Prime-Objective honesty failure).
* **Cross-check** — A1's bottom-up estimate vs an *independent* estimate of the
  same tokens. Divergence is a first-class honesty signal: it means our own
  pricing/attribution model is wrong somewhere. Absence of an independent
  estimate is a **typed** state (``available=False`` / ``divergence_pct=None``),
  never a misleading ``0.0``.

Compute-don't-store (ADR-0013): every figure here is derived at read time from
already-non-persisted inputs (a :class:`~src.telemetry.cost.CostReport` and the
subscription fee config input). Nothing in this module writes to the database.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.telemetry.cost import CostReport

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SUBSCRIPTION_PATH = PROJECT_ROOT / "config" / "subscription.yaml"

#: Flaw class a divergence implicates, by which independence the source provides.
FLAW_ATTRIBUTION = "attribution"
FLAW_PRICING = "pricing"


@dataclass(frozen=True)
class SubscriptionFee:
    """The developer's flat subscription fee, a config input (never persisted).

    Attributes:
        monthly_fee_usd: Flat monthly fee in ``currency``. Always > 0 — a
            zero/negative/unparseable fee is reported as *not configured* by
            :func:`load_subscription_fee` (which returns ``None``), so a
            ``SubscriptionFee`` instance always carries a usable denominator.
        currency: ISO currency label (informational; no conversion is done).
        plan_label: Human label for the plan (e.g. ``"Claude Max"``).
        effective_date: ISO date the fee took effect (informational).
    """

    monthly_fee_usd: float
    currency: str = "USD"
    plan_label: str = ""
    effective_date: str = ""


@dataclass(frozen=True)
class LeverageResult:
    """Value-vs-subscription leverage with an explicit, labelled time basis.

    Honest absence: when leverage cannot be computed (no fee configured, or a
    non-finite cost total) ``configured`` is ``False`` and both ratios are
    ``None`` with a ``reason`` — never a fabricated denominator.

    Attributes:
        configured: True iff leverage was computed (a usable positive fee was
            supplied *and* the cost total is finite). ``reason`` is non-empty
            only when this is ``False``.
        total_cost_usd: The A1 priced total this leverage is measured against
            (priced tokens only — see ``coverage_pct``).
        coverage_pct: Share of billable tokens that were priced (carried from
            the :class:`CostReport`), so the figure is never read as more
            complete than it is.
        monthly_fee_usd: The configured monthly fee, or ``None`` if unconfigured.
        window_months: Duration the cost spans, in months, or ``None`` if the
            transport could not determine it.
        fee_period: The fee's period label (always ``"monthly"`` here).
        leverage_cumulative: ``total_cost_usd / monthly_fee_usd`` — the
            cumulative-over-the-window multiple. ``None`` if unconfigured.
        leverage_per_month: ``(total_cost_usd / window_months) / monthly_fee_usd``
            — the per-month multiple. ``None`` if unconfigured or the window is
            unknown/zero.
        reason: Why leverage is absent, when ``configured`` is ``False``; empty
            otherwise.
        note: Secondary advisory for a *configured* result whose per-month
            figure is nonetheless absent (e.g. the cost window is unknown);
            empty when fully derivable. Distinct from ``reason`` so a consumer
            keys on ``configured`` for the primary state.
    """

    configured: bool
    total_cost_usd: float
    coverage_pct: float
    monthly_fee_usd: float | None
    window_months: float | None
    fee_period: str
    leverage_cumulative: float | None
    leverage_per_month: float | None
    reason: str = ""
    note: str = ""


@dataclass(frozen=True)
class IndependentEstimate:
    """An independent, locally-computed estimate of the same tokens A1 priced.

    This is the single pinned seam (architecture F2) — there is no source
    registry; the two sources (an attribution baseline and the OTel export) both
    produce this shape.

    Attributes:
        present: True iff a usable independent estimate exists for the scope.
        cost_usd: The independent dollar estimate, or ``None`` if the source had
            data but it could not be costed.
        token_basis: Billable tokens the independent estimate covers.
        source_label: Human label for the source (e.g. ``"attribution-baseline"``
            / ``"otel"``).
        scope_coverage_pct: Fraction (0-100) of A1's scope the source covers; a
            divergence against a partial estimate is labelled partial.
        flaw_class: Which flaw a divergence from this source implicates —
            :data:`FLAW_ATTRIBUTION` (same pricing, different attribution) or
            :data:`FLAW_PRICING` (same tokens, independent pricing).
    """

    present: bool
    cost_usd: float | None
    token_basis: int
    source_label: str
    scope_coverage_pct: float
    flaw_class: str


@dataclass(frozen=True)
class DivergenceResult:
    """Structured divergence between A1's estimate and an independent estimate.

    Honest absence is typed: when no independent estimate exists (or it cannot
    be costed, or its denominator is zero), ``available`` is ``False`` and
    ``divergence_pct`` is ``None`` — never ``0.0`` (which a consumer would
    misread as an exact match).

    Attributes:
        available: True iff a usable independent estimate was compared.
        our_cost_usd: A1's bottom-up priced total.
        independent_cost_usd: The independent estimate, or ``None`` if absent.
        delta_usd: ``our_cost_usd - independent_cost_usd``, or ``None`` if absent.
        divergence_pct: ``delta / independent * 100``, or ``None`` on absence or
            a zero independent denominator.
        direction: ``"ours_higher"`` / ``"ours_lower"`` / ``None`` (exact match
            or absent).
        flaw_class: What a non-zero divergence implicates (carried from the
            source), or ``None`` when absent.
        scope_coverage_pct: Fraction of A1's scope the comparison covered, or
            ``None`` when absent.
        source_label: The independent source's label, or ``None`` when absent.
        reason: Why the cross-check is unavailable, when ``available`` is False.
    """

    available: bool
    our_cost_usd: float
    independent_cost_usd: float | None
    delta_usd: float | None
    divergence_pct: float | None
    direction: str | None
    flaw_class: str | None
    scope_coverage_pct: float | None
    source_label: str | None
    reason: str = ""


def _coerce_fee(value: Any) -> float | None:
    """Coerce a YAML scalar to a strictly-positive fee, or ``None``.

    Mirrors :func:`src.telemetry.pricing._coerce_rate`'s discipline: a
    non-numeric, zero, or negative value is *not configured* (``None``) rather
    than a crash or a fabricated/negative denominator. A boolean is rejected too
    (``float(True)`` would otherwise silently become a ``$1.00`` fee).
    """
    if isinstance(value, bool):
        return None
    try:
        fee = float(value)
    except (TypeError, ValueError):
        return None
    return fee if fee > 0.0 else None


def parse_subscription_fee(data: dict[str, Any]) -> SubscriptionFee | None:
    """Build a :class:`SubscriptionFee` from already-loaded YAML data.

    Returns ``None`` (not configured) when the fee is missing, zero, negative,
    or unparseable — the honest-absence path. Defensive against a non-mapping
    input.

    Args:
        data: Parsed YAML mapping (e.g. from ``yaml.safe_load``).

    Returns:
        A usable fee, or ``None`` if none is configured.
    """
    if not isinstance(data, dict):
        return None
    fee = _coerce_fee(data.get("monthly_fee_usd"))
    if fee is None:
        return None
    currency = data.get("currency")
    plan_label = data.get("plan_label")
    effective_date = data.get("effective_date")
    return SubscriptionFee(
        monthly_fee_usd=fee,
        currency=str(currency) if isinstance(currency, str) else "USD",
        plan_label=str(plan_label) if isinstance(plan_label, str) else "",
        effective_date=str(effective_date) if isinstance(effective_date, str) else "",
    )


def load_subscription_fee(path: Path | None = None) -> SubscriptionFee | None:
    """Load the subscription fee from a YAML config input.

    Args:
        path: Config path; defaults to ``config/subscription.yaml``.

    Returns:
        A :class:`SubscriptionFee`, or ``None`` when the file is missing,
        unreadable, malformed, or carries no usable (positive) fee. A missing
        file is the normal fresh-clone case (the real file is gitignored).
    """
    fee_path = path or DEFAULT_SUBSCRIPTION_PATH
    try:
        text = fee_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None
    return parse_subscription_fee(data)


def leverage(
    report: CostReport,
    fee: SubscriptionFee | None,
    *,
    window_months: float | None = None,
) -> LeverageResult:
    """Compute value-vs-subscription leverage from an A1 cost report and a fee.

    Pure: the cost total is taken from ``report`` (a parameter) — this function
    never recomputes cost, so a second cost path is impossible to fork here
    (architecture F1).

    The time basis is explicit and labelled (Steward binding condition): the
    result carries both a cumulative multiple (``total / fee``) and, when the
    cost window is known, a per-month multiple (``(total / months) / fee``).
    A multi-month cumulative cost is therefore never silently presented as if it
    were one month's spend.

    Args:
        report: The A1 :class:`CostReport`; ``report.total_cost_usd`` (priced
            tokens only) is the numerator.
        fee: The subscription fee, or ``None`` for the not-configured path.
        window_months: Duration the cost spans, in months, supplied by the
            transport; ``None`` if unknown.

    Returns:
        A :class:`LeverageResult`. When ``fee`` is ``None`` the result is the
        honest not-configured state (ratios ``None`` with a reason).
    """
    total = report.total_cost_usd
    coverage = report.coverage_pct
    # Honest-absence path: no usable fee, or a non-finite cost total (a
    # data-integrity problem) — never crash, never a fabricated denominator.
    if fee is None or not math.isfinite(total):
        reason = (
            "subscription fee not configured"
            if fee is None
            else "cost total is not a finite number"
        )
        return LeverageResult(
            configured=False,
            total_cost_usd=total,
            coverage_pct=coverage,
            monthly_fee_usd=fee.monthly_fee_usd if fee is not None else None,
            window_months=window_months,
            fee_period="monthly",
            leverage_cumulative=None,
            leverage_per_month=None,
            reason=reason,
        )
    cumulative = total / fee.monthly_fee_usd
    per_month: float | None = None
    if window_months is not None and window_months > 0.0:
        per_month = (total / window_months) / fee.monthly_fee_usd
    return LeverageResult(
        configured=True,
        total_cost_usd=total,
        coverage_pct=coverage,
        monthly_fee_usd=fee.monthly_fee_usd,
        window_months=window_months,
        fee_period="monthly",
        leverage_cumulative=cumulative,
        leverage_per_month=per_month,
        note="" if per_month is not None else "cost window unknown; per-month not derivable",
    )


def cross_check(report: CostReport, independent: IndependentEstimate | None) -> DivergenceResult:
    """Compare A1's bottom-up estimate against an independent estimate.

    Honest absence is typed (Steward binding condition): when ``independent`` is
    ``None`` / not present / uncosted, or its denominator is zero, the result is
    ``available=False`` with ``divergence_pct=None`` — never ``0.0``. Identical
    estimates yield ``available=True``, ``divergence_pct=0.0``, ``direction=None``.

    Args:
        report: A1's :class:`CostReport`; ``report.total_cost_usd`` is our side.
        independent: The independent estimate, or ``None``.

    Returns:
        A :class:`DivergenceResult`.
    """
    our = report.total_cost_usd
    indep = independent.cost_usd if independent is not None else None
    # Typed honest absence — a divergence is only "available" when an
    # independent estimate exists, is finite, AND has a usable (positive)
    # denominator. Zero/negative/non-finite is reported as absent (never
    # available=True with a None divergence, which no consumer could read), and
    # a non-finite our-cost is a data-integrity absence too. The independent
    # cost (even when unusable) is still surfaced so a consumer can see the
    # source ran; a zero independent estimate hints at an attribution gap (said
    # so in ``reason``), but ``flaw_class`` stays ``None`` on the absent path.
    usable_indep = indep is not None and math.isfinite(indep) and indep > 0.0
    if (
        independent is None
        or not independent.present
        or indep is None
        or not usable_indep
        or not math.isfinite(our)
    ):
        if independent is None or not independent.present:
            reason = "no independent estimate available"
        elif indep is None:
            reason = "independent source present but could not be costed"
        elif not math.isfinite(indep):
            reason = "independent cost is not a finite number"
        elif indep <= 0.0:
            reason = "independent cost is zero or negative; denominator unusable"
        else:
            reason = "our cost total is not a finite number"
        return DivergenceResult(
            available=False,
            our_cost_usd=our,
            independent_cost_usd=indep if (indep is not None and math.isfinite(indep)) else None,
            delta_usd=None,
            divergence_pct=None,
            direction=None,
            flaw_class=None,
            scope_coverage_pct=independent.scope_coverage_pct if independent is not None else None,
            source_label=independent.source_label if independent is not None else None,
            reason=reason,
        )

    delta = our - indep
    divergence_pct = round(delta / indep * 100.0, 2)
    if delta > 0.0:
        direction: str | None = "ours_higher"
    elif delta < 0.0:
        direction = "ours_lower"
    else:
        direction = None  # exact match
    return DivergenceResult(
        available=True,
        our_cost_usd=our,
        independent_cost_usd=indep,
        delta_usd=delta,
        divergence_pct=divergence_pct,
        direction=direction,
        flaw_class=independent.flaw_class,
        scope_coverage_pct=independent.scope_coverage_pct,
        source_label=independent.source_label,
        reason="",
    )
