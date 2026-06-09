"""Model-tier resolution and per-token dollar-cost math (ADR-0013, amended).

Pure logic: the only side effect is reading the pricing YAML when a caller asks
for the default table. Dollar cost is **computed at analysis time** from raw
token counts and ``config/model_pricing.yaml`` — it is never stored in the
database (ADR-0013 compute-don't-store). Tier resolution is honest: a model id
that resolves to no known family yields ``UNKNOWN_TIER`` and is never silently
priced at zero by callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PRICING_PATH = PROJECT_ROOT / "config" / "model_pricing.yaml"

#: Sentinel tier for a model id that resolves to no known pricing family.
UNKNOWN_TIER = "unknown"

#: Model family substrings used as the second-chance tier resolver. Tier is the
#: stable analytical dimension over time (ADR-0013 §2); full model ids churn.
_FAMILIES: tuple[str, ...] = ("opus", "sonnet", "haiku")

_PER_MILLION = 1_000_000.0


@dataclass(frozen=True)
class TierRates:
    """USD-per-million-token rates for one model tier.

    Attributes:
        input: Dollars per 1M input tokens.
        output: Dollars per 1M output tokens.
        cache_read_multiplier: Multiplier on the input rate for cache reads.
        cache_create_multiplier: Multiplier on the input rate for cache writes.
    """

    input: float
    output: float
    cache_read_multiplier: float
    cache_create_multiplier: float


@dataclass(frozen=True)
class PricingTable:
    """Resolved pricing table: tier rates plus a model-id-to-tier map.

    Attributes:
        tiers: Tier name to :class:`TierRates`.
        models: Full model id to tier name.
        last_updated: ISO date string from the YAML's top-level
            ``last_updated`` key (empty string when the YAML omits it).
            Used by the Layer B Phase 3 Unit 2 config-drift detector
            (:mod:`src.telemetry.drift`) to compare against the earliest
            captured discussion; never affects cost computation.
    """

    tiers: dict[str, TierRates]
    models: dict[str, str]
    last_updated: str = ""

    def resolve_tier(self, model_id: str | None) -> str:
        """Resolve a model id to a pricing tier.

        Resolution order: exact match in the ``models`` map, then a model-family
        substring match (``opus``/``sonnet``/``haiku``), else ``UNKNOWN_TIER``.
        Family matching is not fabrication — the family *is* the stable tier
        dimension; only a genuinely unrecognizable id becomes ``unknown``.

        Args:
            model_id: Full model identifier, or ``None``.

        Returns:
            A tier key present in ``tiers``, or ``UNKNOWN_TIER``.
        """
        if not model_id:
            return UNKNOWN_TIER
        mapped = self.models.get(model_id)
        if mapped is not None:
            return mapped
        lowered = model_id.lower()
        for family in _FAMILIES:
            if family in lowered and family in self.tiers:
                return family
        return UNKNOWN_TIER

    def cost_usd(
        self,
        tier: str,
        *,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cache_read_tokens: int | None = None,
        cache_create_tokens: int | None = None,
    ) -> float | None:
        """Compute the dollar cost of a token bundle at a tier's rates.

        Args:
            tier: A tier key. ``UNKNOWN_TIER`` (or any tier absent from the
                table) returns ``None`` — the caller must treat this as
                uncosted, never as ``0.0``.
            tokens_in: Input tokens (``None`` treated as 0 for the sum).
            tokens_out: Output tokens.
            cache_read_tokens: Cache-read tokens (priced at the read multiplier).
            cache_create_tokens: Cache-create tokens (priced at the write
                multiplier).

        Returns:
            Total USD cost, or ``None`` if the tier has no known rates.
        """
        rates = self.tiers.get(tier)
        if rates is None:
            return None
        ti = tokens_in or 0
        to = tokens_out or 0
        cr = cache_read_tokens or 0
        cc = cache_create_tokens or 0
        cost = (
            ti * rates.input
            + to * rates.output
            + cr * rates.input * rates.cache_read_multiplier
            + cc * rates.input * rates.cache_create_multiplier
        )
        return cost / _PER_MILLION


def _coerce_rate(value: Any) -> float:
    """Coerce a YAML scalar to a non-negative float, or 0.0 if unusable."""
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return 0.0
    return rate if rate >= 0.0 else 0.0


def parse_pricing(data: dict[str, Any]) -> PricingTable:
    """Build a :class:`PricingTable` from already-loaded YAML data.

    Defensive against malformed input: missing/!dict ``tiers`` or ``models``
    sections degrade to empty mappings rather than raising, so a bad pricing
    file yields all-``unknown`` tiers (honest) instead of a crash.

    Args:
        data: Parsed YAML mapping (e.g. from ``yaml.safe_load``).

    Returns:
        A resolved pricing table.
    """
    raw_tiers = data.get("tiers") if isinstance(data, dict) else None
    raw_models = data.get("models") if isinstance(data, dict) else None
    tiers: dict[str, TierRates] = {}
    if isinstance(raw_tiers, dict):
        for name, spec in raw_tiers.items():
            if not isinstance(spec, dict):
                continue
            tiers[str(name)] = TierRates(
                input=_coerce_rate(spec.get("input")),
                output=_coerce_rate(spec.get("output")),
                cache_read_multiplier=_coerce_rate(spec.get("cache_read_multiplier")),
                cache_create_multiplier=_coerce_rate(spec.get("cache_create_multiplier")),
            )
    models: dict[str, str] = {}
    if isinstance(raw_models, dict):
        for model_id, tier in raw_models.items():
            if isinstance(tier, str):
                models[str(model_id)] = tier
    raw_last_updated = data.get("last_updated") if isinstance(data, dict) else None
    last_updated = ""
    if isinstance(raw_last_updated, str):
        last_updated = raw_last_updated
    elif isinstance(raw_last_updated, date):
        # PyYAML deserializes an ISO date scalar as a :class:`date` object.
        # Render it as an ISO string so the drift detector's single-shape
        # parse (:func:`src.telemetry.drift._parse_iso_date`) is the only
        # date-handling seam downstream.
        last_updated = raw_last_updated.isoformat()
    return PricingTable(tiers=tiers, models=models, last_updated=last_updated)


def load_pricing(path: Path | None = None) -> PricingTable:
    """Load and parse the pricing table from a YAML file.

    Args:
        path: Pricing YAML path; defaults to ``config/model_pricing.yaml``.

    Returns:
        A resolved pricing table. A missing or unreadable file yields an empty
        table (all tiers ``unknown``) rather than raising.
    """
    pricing_path = path or DEFAULT_PRICING_PATH
    try:
        text = pricing_path.read_text(encoding="utf-8")
    except OSError:
        return PricingTable(tiers={}, models={})
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return PricingTable(tiers={}, models={})
    if not isinstance(data, dict):
        return PricingTable(tiers={}, models={})
    return parse_pricing(data)
