"""Aggregate per-model token rows into a per-tier dollar-cost report.

Pure logic over already-loaded rows (the SQLite read happens in
``scripts/telemetry``). The two honesty rules from the spec live here:

* **Coverage is on a token denominator** — ``known_tokens / total_tokens`` —
  not a row/turn count, because cost is proportional to tokens.
* **Unknown tiers are never zero-rated** — a row whose tier has no rates
  contributes its tokens to ``total_tokens`` but not to ``known_tokens`` and
  not to ``total_cost_usd``; its ``TierCost.cost_usd`` is ``None``.
* **Cache-read ratio is a pure token-count derivation** — never a stored
  dollar or ratio; honest-``None`` on a zero denominator or any unknown
  component (``compute_cache_read_ratio`` + the per-tier/overall properties,
  SPEC-20260716-093231).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from src.telemetry.pricing import UNKNOWN_TIER, PricingTable


def compute_cache_read_ratio(
    tokens_in: int | None,
    cache_read_tokens: int | None,
    cache_create_tokens: int | None,
) -> float | None:
    """Return ``cache_read / (input + cache_read + cache_creation)``, or ``None``.

    The cache-read ratio is the leading cache-health indicator adopted by
    SPEC-20260716-093231 (triage item #1). Honest-absence rules:

    * Any ``None`` component means the ratio is **unknown** — ``None`` is never
      silently treated as 0 (repo convention: ``None`` = unknown, ``0`` =
      known-zero).
    * A zero denominator yields ``None``, never a fabricated ``0.0``.

    The ratio is a pure token-count derivation — unlike a dollar figure it can
    never go stale on repricing (ADR-0013 compute-don't-store exemption).
    """
    if tokens_in is None or cache_read_tokens is None or cache_create_tokens is None:
        return None
    denominator = tokens_in + cache_read_tokens + cache_create_tokens
    if denominator <= 0:
        return None
    return cache_read_tokens / denominator


@dataclass(frozen=True)
class ModelTokenRow:
    """A per-discussion, per-model token bundle (one ``discussion_model_tokens`` row)."""

    discussion_id: str
    model_id: str
    tier: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read_tokens: int | None = None
    cache_create_tokens: int | None = None
    message_count: int = 0

    def total_tokens(self) -> int:
        """Sum of every billable token kind in this row (``None`` counts as 0)."""
        return (
            (self.tokens_in or 0)
            + (self.tokens_out or 0)
            + (self.cache_read_tokens or 0)
            + (self.cache_create_tokens or 0)
        )


@dataclass
class TierCost:
    """Accumulated tokens and cost for a single tier across rows.

    ``cost_usd`` is ``None`` for an unpriced/unknown tier — callers must render
    that as 'uncosted', never as ``$0``.
    """

    tier: str
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read_tokens: int = 0
    cache_create_tokens: int = 0
    message_count: int = 0
    cost_usd: float | None = None

    def total_tokens(self) -> int:
        """Sum of every billable token kind accumulated for this tier."""
        return self.tokens_in + self.tokens_out + self.cache_read_tokens + self.cache_create_tokens

    @property
    def cache_read_ratio(self) -> float | None:
        """Cache-read share of this tier's input-side tokens (``None`` if none)."""
        return compute_cache_read_ratio(
            self.tokens_in, self.cache_read_tokens, self.cache_create_tokens
        )


@dataclass
class CostReport:
    """Per-tier cost breakdown plus an honest coverage figure.

    Attributes:
        by_tier: Tier key -> accumulated :class:`TierCost`.
        total_cost_usd: Sum of costs for *priced* tiers only.
        known_tokens: Tokens belonging to priced tiers.
        total_tokens: All billable tokens, priced or not.
    """

    by_tier: dict[str, TierCost] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    known_tokens: int = 0
    total_tokens: int = 0

    @property
    def coverage_pct(self) -> float:
        """Share of billable tokens that resolved to a priced tier (0-100).

        Returns ``0.0`` when there are no tokens at all — there is nothing to be
        confident about, so coverage is reported as 0 rather than a misleading
        100.
        """
        if self.total_tokens <= 0:
            return 0.0
        return round(self.known_tokens / self.total_tokens * 100.0, 1)

    @property
    def is_fully_covered(self) -> bool:
        """True iff every billable token was priced (coverage is 100%)."""
        return self.total_tokens > 0 and self.known_tokens == self.total_tokens

    @property
    def cache_read_ratio(self) -> float | None:
        """Overall cache-read share of input-side tokens across every tier.

        ``None`` (honest absence) when there are no input-side tokens at all —
        never a fabricated ``0.0``.
        """
        tokens_in = sum(t.tokens_in for t in self.by_tier.values())
        cache_read = sum(t.cache_read_tokens for t in self.by_tier.values())
        cache_create = sum(t.cache_create_tokens for t in self.by_tier.values())
        return compute_cache_read_ratio(tokens_in, cache_read, cache_create)


def build_cost_report(rows: Iterable[ModelTokenRow], pricing: PricingTable) -> CostReport:
    """Aggregate model-token rows into a :class:`CostReport` in a single pass.

    Args:
        rows: Per-model token bundles (e.g. one ``discussion_model_tokens`` row
            each, or pre-filtered to a date window / discussion).
        pricing: Resolved pricing table used to cost each tier.

    Returns:
        A cost report whose ``total_cost_usd`` and ``known_tokens`` exclude any
        unpriced/unknown tier, and whose ``coverage_pct`` is token-weighted.
    """
    report = CostReport()
    for row in rows:
        tier = row.tier or UNKNOWN_TIER
        acc = report.by_tier.get(tier)
        if acc is None:
            acc = TierCost(tier=tier)
            report.by_tier[tier] = acc
        acc.tokens_in += row.tokens_in or 0
        acc.tokens_out += row.tokens_out or 0
        acc.cache_read_tokens += row.cache_read_tokens or 0
        acc.cache_create_tokens += row.cache_create_tokens or 0
        acc.message_count += row.message_count or 0

        row_tokens = row.total_tokens()
        report.total_tokens += row_tokens

        row_cost = pricing.cost_usd(
            tier,
            tokens_in=row.tokens_in,
            tokens_out=row.tokens_out,
            cache_read_tokens=row.cache_read_tokens,
            cache_create_tokens=row.cache_create_tokens,
        )
        if row_cost is None:
            # Unknown/unpriced tier: tokens count toward the denominator only.
            continue
        report.known_tokens += row_tokens
        report.total_cost_usd += row_cost
        acc.cost_usd = (acc.cost_usd or 0.0) + row_cost
    return report
