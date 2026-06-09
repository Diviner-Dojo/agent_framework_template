"""Detect configuration-drift signals from the captured corpus + current config.

Layer B Phase 3 Unit 2 (SPEC-20260607-183136 §Phase 3 — failure intelligence).
Pure logic over already-loaded inputs: the SQLite read happens in the transport
layer (``scripts/telemetry/dashboard.py``); this module knows nothing about
files or the database, so every rule here is exhaustively unit-testable (the
"cook"; the transport layer is the "runner").

A *config-drift signal* surfaces a provenance mismatch between the **current**
configuration and the **captured discussion window** — a state where current
config is being used to interpret data that was generated under a possibly
different config. Three kinds are detected today:

* **UNKNOWN_MODEL** — a ``model_id`` appearing in
  ``discussion_model_tokens`` that the current
  :class:`~src.telemetry.pricing.PricingTable` cannot resolve (returns
  :data:`~src.telemetry.pricing.UNKNOWN_TIER`). The model was captured but is
  not priced today; those rows render as ``uncosted`` in the cost panel,
  understating the total. Remediation: add the id to ``models:`` in
  ``config/model_pricing.yaml``.
* **STALE_PRICING** — ``model_pricing.yaml``'s ``last_updated`` is **after**
  the earliest captured ``discussions.created_at``. Discussions that ran
  before the pricing change are now being re-priced at current rates, so the
  cost figure is a *hypothetical-at-current-rates* number rather than what
  was paid then. Honest framing per ADR-0013 compute-don't-store.
* **STALE_SUBSCRIPTION_FEE** — ``subscription.yaml``'s ``effective_date`` is
  **after** the earliest captured ``discussions.created_at``. The same
  re-interpretation applies to the A3 leverage denominator — the multiple is
  measured against the *current* fee even though some captured spend
  predates it.

Honesty rules (ADR-0020): a malformed/missing input is the typed
*honest-absence* path (no signal emitted) rather than a fabricated drift; a
drift kind whose detector cannot determine its premise (e.g. no
``last_updated`` line in the YAML) is reported as ``not-determined``, not
``no-drift``. Remediation hints are **static** strings keyed by drift kind —
never derived from the observed values — so the renderer cannot smuggle a
fabricated root cause into a hint string.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from src.telemetry.pricing import UNKNOWN_TIER, PricingTable
from src.telemetry.value import SubscriptionFee

#: Drift kind: a captured ``model_id`` the current pricing config cannot resolve.
UNKNOWN_MODEL = "unknown_model"

#: Drift kind: pricing YAML was updated after the earliest captured discussion.
STALE_PRICING = "stale_pricing"

#: Drift kind: subscription fee took effect after the earliest captured discussion.
STALE_SUBSCRIPTION_FEE = "stale_subscription_fee"

#: Canonical ordering of drift kinds (used for stable row iteration). The
#: ordering surfaces UNKNOWN_MODEL first because it has the most direct
#: effect on the cost figure (uncosted rows), then the two temporal drifts
#: in pricing-then-subscription order to mirror the static dashboard's
#: cost-then-leverage layout.
DRIFT_KINDS: tuple[str, ...] = (
    UNKNOWN_MODEL,
    STALE_PRICING,
    STALE_SUBSCRIPTION_FEE,
)

#: Short, **static** remediation hint per drift kind. One sentence each; no
#: fabricated root-cause claims, no calls to action that imply more knowledge
#: than the detector has. Keeping these static (not derived from the signal)
#: is what makes the ADR-0020 honesty discipline straightforward to audit.
REMEDIATION_HINTS: dict[str, str] = {
    UNKNOWN_MODEL: (
        "This model id appears in the captured corpus but the current "
        "pricing config does not resolve it. Add the id (or its family) to "
        "the `models:` map in config/model_pricing.yaml so its rows are "
        "no longer rendered as uncosted."
    ),
    STALE_PRICING: (
        "The current pricing config was last updated after the earliest "
        "captured discussion. Older discussions are being re-priced at "
        "current rates — the cost figure reflects what those sessions "
        "would cost at today's rates, not what was billed at the time."
    ),
    STALE_SUBSCRIPTION_FEE: (
        "The configured subscription fee took effect after the earliest "
        "captured discussion. The leverage multiple for sessions before "
        "that date is measured against a fee that was not yet in effect — "
        "the multiple is approximate for the older portion of the corpus."
    ),
}


@dataclass(frozen=True)
class ConfigDriftSignal:
    """One detected config-drift row, ready for the dashboard.

    Attributes:
        kind: One of :data:`DRIFT_KINDS`.
        observed: The value that triggered the signal — a model id for
            :data:`UNKNOWN_MODEL`, an ISO date string for the two temporal
            drifts. Always a string so the renderer never has to format
            heterogeneous types at the boundary.
        detail: A short, factual sentence describing the observation. Must
            **never** include a fabricated root-cause claim or a fix
            prescription (those live in the static :data:`REMEDIATION_HINTS`).
    """

    kind: str
    observed: str
    detail: str


def _is_unknown(pricing: PricingTable, model_id: str) -> bool:
    """Return True iff ``model_id`` cannot be resolved by ``pricing``.

    Mirrors :meth:`PricingTable.resolve_tier` so the drift detector and the
    cost-path's "this is uncosted" decision use the same rule. A blank string
    is treated as resolvable (the cost path uses :data:`UNKNOWN_TIER` as its
    sentinel for missing-id rows; the drift detector does NOT flag the
    sentinel because it is not a captured id at all).
    """
    if not model_id or model_id == UNKNOWN_TIER:
        return False
    return pricing.resolve_tier(model_id) == UNKNOWN_TIER


def detect_unknown_model_drift(
    model_ids: Iterable[str], pricing: PricingTable
) -> list[ConfigDriftSignal]:
    """Flag captured ``model_id``s the current pricing table cannot resolve.

    The detector takes the **distinct** captured ids (the transport layer
    deduplicates with ``SELECT DISTINCT model_id``) and emits one signal per
    unresolved id, in input order. Stable iteration is the transport's
    responsibility (it sorts the SELECT result); this module preserves whatever
    order it receives so a deterministic input yields a deterministic output.

    Args:
        model_ids: Distinct model ids captured in ``discussion_model_tokens``.
        pricing: The resolved current pricing table.

    Returns:
        One :class:`ConfigDriftSignal` per unresolved id, ``kind`` ==
        :data:`UNKNOWN_MODEL`.
    """
    signals: list[ConfigDriftSignal] = []
    seen: set[str] = set()
    for model_id in model_ids:
        if not isinstance(model_id, str):
            continue
        if model_id in seen:
            continue
        seen.add(model_id)
        if _is_unknown(pricing, model_id):
            signals.append(
                ConfigDriftSignal(
                    kind=UNKNOWN_MODEL,
                    observed=model_id,
                    detail=(
                        f"model id '{model_id}' appears in the captured corpus "
                        "but is not in the current pricing config"
                    ),
                )
            )
    return signals


def _parse_iso_date(value: str | None) -> date | None:
    """Parse an ISO date string into a :class:`date`, or ``None``.

    Tolerant of an empty string, ``None``, or a malformed value: returns
    ``None`` rather than raising, so the caller's typed honest-absence path
    fires (no signal emitted) instead of crashing the renderer.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def detect_stale_pricing_drift(
    pricing: PricingTable, earliest_discussion_at: datetime | None
) -> list[ConfigDriftSignal]:
    """Flag pricing config updated after the earliest captured discussion.

    Returns at most one signal (this is a window-level observation, not a
    per-row one). Honest-absence paths (no signal emitted):

    * Pricing config carries no parseable ``last_updated`` date — the detector
      cannot determine the premise, so it does not invent one.
    * No discussions are captured yet — there is no window to compare against.
    * The pricing date is on or before the earliest discussion — no drift.

    Args:
        pricing: The resolved current pricing table (carries ``last_updated``).
        earliest_discussion_at: The oldest ``discussions.created_at`` in the
            corpus, or ``None`` if the corpus is empty.

    Returns:
        Zero or one :class:`ConfigDriftSignal` with ``kind`` ==
        :data:`STALE_PRICING`.
    """
    pricing_date = _parse_iso_date(pricing.last_updated)
    if pricing_date is None or earliest_discussion_at is None:
        return []
    earliest_date = earliest_discussion_at.date()
    if pricing_date <= earliest_date:
        return []
    return [
        ConfigDriftSignal(
            kind=STALE_PRICING,
            observed=pricing_date.isoformat(),
            detail=(
                f"pricing config last updated {pricing_date.isoformat()}, "
                f"after the earliest captured discussion on {earliest_date.isoformat()}"
            ),
        )
    ]


def detect_stale_subscription_drift(
    fee: SubscriptionFee | None, earliest_discussion_at: datetime | None
) -> list[ConfigDriftSignal]:
    """Flag subscription fee that took effect after the earliest captured discussion.

    Returns at most one signal (a window-level observation). Honest-absence
    paths (no signal emitted): fee not configured / no parseable effective
    date / no discussions / effective date on or before the earliest
    discussion.

    Args:
        fee: The configured subscription fee, or ``None`` (not configured).
        earliest_discussion_at: The oldest ``discussions.created_at`` in the
            corpus, or ``None`` if the corpus is empty.

    Returns:
        Zero or one :class:`ConfigDriftSignal` with ``kind`` ==
        :data:`STALE_SUBSCRIPTION_FEE`.
    """
    if fee is None or earliest_discussion_at is None:
        return []
    effective = _parse_iso_date(fee.effective_date)
    if effective is None:
        return []
    earliest_date = earliest_discussion_at.date()
    if effective <= earliest_date:
        return []
    return [
        ConfigDriftSignal(
            kind=STALE_SUBSCRIPTION_FEE,
            observed=effective.isoformat(),
            detail=(
                f"subscription fee effective {effective.isoformat()}, "
                f"after the earliest captured discussion on {earliest_date.isoformat()}"
            ),
        )
    ]


def detect_config_drift(
    model_ids: Iterable[str],
    pricing: PricingTable,
    fee: SubscriptionFee | None,
    earliest_discussion_at: datetime | None,
) -> list[ConfigDriftSignal]:
    """Run all drift detectors and return the merged signal list.

    Signals are emitted in :data:`DRIFT_KINDS` order so the dashboard's
    rendered table has a deterministic layout across runs. Within the
    ``UNKNOWN_MODEL`` kind, model ids retain the input order (the transport
    layer's ``SELECT DISTINCT`` is the sort surface — keeping it there means
    the rule "what ordering is canonical for unknown ids" is owned by one
    place, not split between detector and renderer).

    Args:
        model_ids: Distinct model ids from ``discussion_model_tokens``.
        pricing: The resolved current pricing table.
        fee: The configured subscription fee, or ``None``.
        earliest_discussion_at: The oldest ``discussions.created_at``, or
            ``None`` if the corpus is empty.

    Returns:
        All :class:`ConfigDriftSignal`s in :data:`DRIFT_KINDS` order.
    """
    return [
        *detect_unknown_model_drift(model_ids, pricing),
        *detect_stale_pricing_drift(pricing, earliest_discussion_at),
        *detect_stale_subscription_drift(fee, earliest_discussion_at),
    ]
