"""Weekly aggregation of stored cost rows for the Layer B trends chart.

Pure aggregation algebra over already-loaded :class:`ModelTokenRow` values
plus a discussion-id → ``created_at`` lookup. The transport layer
(``scripts/telemetry/dashboard_server.py``) owns the SQLite read and supplies
both inputs; this module performs no IO, imports no ``scripts.*`` module, and
takes no YAML / DB / environment dependency (AC14 purity — the live model and
the weekly aggregator share the same purity contract so the read-only DB
invariant is enforced one layer up).

The weekly view answers two questions the per-turn cost chart cannot:

1. **Where is API-equivalent spend trending over the longer arc?** The per-turn
   chart's rolling event window (capped at :data:`~src.telemetry.live.RECENT_EVENTS_CAP`
   events) shows only the most recent activity; the weekly chart shows the
   stored corpus aggregated by ISO calendar week.
2. **How much of that spend is uncosted?** The :class:`WeeklyTotal` carries
   ``uncosted_tokens`` alongside ``priced_cost_usd`` so the chart can show
   uncosted activity as a distinct stack slice rather than collapsing it to
   ``$0`` (ADR-0020 honesty discipline: "uncosted ≠ $0").

Discussion identifiers are used **only as grouping keys** here — they are
never returned in the public dataclasses and never reach the JSON payload
the renderer bakes into the fragment. If a future iteration adds a per-
discussion breakdown to the weekly chart, the discussion id text becomes part
of the serialisation surface and must route through
:func:`~src.telemetry.dashboard._json_in_script` (security advisory L1 from
REV-20260608-053032).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.telemetry.cost import ModelTokenRow
from src.telemetry.pricing import UNKNOWN_TIER, PricingTable

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeeklyTierBucket:
    """Per-tier token + cost accumulation for a single ISO week.

    ``cost_usd`` is ``None`` for an unpriced tier (the ``unknown`` tier or a
    known model that has no entry in ``config/model_pricing.yaml``) — never
    ``0.0``, because a zero would silently fabricate a free observation. The
    renderer uses the ``None`` signal to route the slice into the chart's
    uncosted treatment (distinct color + named "(model tier unpriced)" label).
    """

    week_start: date
    tier: str
    total_tokens: int
    cost_usd: float | None


@dataclass(frozen=True)
class WeeklyTotal:
    """All tiers for a single ISO week, plus the priced-vs-uncosted split.

    ``priced_cost_usd`` is the sum of every priced tier's cost; uncosted tiers
    contribute their tokens to ``uncosted_tokens`` and their entry to
    ``by_tier`` (with ``cost_usd=None``) but do **not** contribute to
    ``priced_cost_usd``. The prior-window-delta caption in the renderer is
    keyed on ``priced_cost_usd`` for week-over-week percentage change.
    """

    week_start: date
    priced_cost_usd: float
    total_tokens: int
    uncosted_tokens: int
    by_tier: tuple[WeeklyTierBucket, ...]


@dataclass(frozen=True)
class WeeklyTrends:
    """The aggregated weekly time series, in chronological order.

    Outer container so a single value carries the whole chart payload through
    the renderer without re-sorting at every call site. ``weeks`` is sorted
    ascending by :attr:`WeeklyTotal.week_start`; an empty tuple is the
    honest absence signal (no stored rows yet) and routes the renderer into
    the absence tile rather than fabricating an empty chart.
    """

    weeks: tuple[WeeklyTotal, ...]


def iso_week_start(moment: datetime) -> date:
    """Return the Monday of ``moment``'s ISO calendar week (UTC date).

    Implementation note: Python's ``datetime.isocalendar()`` returns a
    ``(year, week, weekday)`` triple where ``weekday`` is 1 for Monday and 7
    for Sunday — subtracting ``weekday - 1`` days from the date yields that
    week's Monday. This is the standard ISO 8601 algorithm and correctly
    handles the year-boundary edge cases (e.g. 2026-12-28 is in ISO
    2026-W53; 2027-01-04 is in ISO 2027-W01). The returned ``date`` is the
    naive calendar date of the Monday — comparisons across timezones must be
    normalised by the caller before invoking.
    """
    return (moment.date() - timedelta(days=moment.isocalendar().weekday - 1)).replace()


def aggregate_by_week(
    rows: Iterable[ModelTokenRow],
    created_at_lookup: Mapping[str, datetime],
    pricing: PricingTable,
) -> WeeklyTrends:
    """Aggregate stored token rows into a chronological weekly trend series.

    Args:
        rows: Per-discussion, per-model token bundles (the same rows the
            cost report consumes).
        created_at_lookup: ``discussion_id`` → ``created_at`` datetime. The
            transport layer JOINs ``discussion_model_tokens`` with
            ``discussions.created_at`` to supply this map.
        pricing: Resolved pricing table. Used to compute per-row dollar cost
            via the same algebra as :func:`~src.telemetry.cost.build_cost_report`,
            so the live weekly view cannot diverge from the retrospective
            cost report.

    Returns:
        The aggregated :class:`WeeklyTrends`. ``weeks`` is sorted ascending
        by :attr:`WeeklyTotal.week_start`. Rows whose ``discussion_id`` is
        missing from ``created_at_lookup`` are skipped with a warning logged
        to ``src.telemetry.weekly`` — they cannot be assigned to a week
        without a timestamp, and a silent drop would hide a transport-layer
        regression. The defensive skip matches the existing "tolerant of
        missing rows" pattern in the read-side dashboard.
    """
    buckets: dict[tuple[date, str], _MutableTierBucket] = {}
    for row in rows:
        created_at = created_at_lookup.get(row.discussion_id)
        if created_at is None:
            _LOG.warning(
                "weekly aggregate: skipping row for discussion %s (no created_at)",
                row.discussion_id,
            )
            continue
        week_start = iso_week_start(created_at)
        tier = row.tier or UNKNOWN_TIER
        key = (week_start, tier)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = _MutableTierBucket(week_start=week_start, tier=tier)
            buckets[key] = bucket
        bucket.total_tokens += row.total_tokens()
        row_cost = pricing.cost_usd(
            tier,
            tokens_in=row.tokens_in,
            tokens_out=row.tokens_out,
            cache_read_tokens=row.cache_read_tokens,
            cache_create_tokens=row.cache_create_tokens,
        )
        if row_cost is not None:
            bucket.cost_usd = (bucket.cost_usd or 0.0) + row_cost

    by_week: dict[date, list[WeeklyTierBucket]] = {}
    for (week_start, _tier), bucket in buckets.items():
        by_week.setdefault(week_start, []).append(
            WeeklyTierBucket(
                week_start=bucket.week_start,
                tier=bucket.tier,
                total_tokens=bucket.total_tokens,
                cost_usd=bucket.cost_usd,
            )
        )

    weeks: list[WeeklyTotal] = []
    for week_start in sorted(by_week.keys()):
        tier_rows = sorted(by_week[week_start], key=lambda b: b.tier)
        priced_cost = sum(b.cost_usd for b in tier_rows if b.cost_usd is not None)
        total_tokens = sum(b.total_tokens for b in tier_rows)
        uncosted_tokens = sum(b.total_tokens for b in tier_rows if b.cost_usd is None)
        weeks.append(
            WeeklyTotal(
                week_start=week_start,
                priced_cost_usd=priced_cost,
                total_tokens=total_tokens,
                uncosted_tokens=uncosted_tokens,
                by_tier=tuple(tier_rows),
            )
        )
    return WeeklyTrends(weeks=tuple(weeks))


@dataclass
class _MutableTierBucket:
    """Internal mutable accumulator used during a single aggregation pass.

    Not exported — exists only to keep the public :class:`WeeklyTierBucket`
    frozen while still allowing in-place token / cost accumulation as rows
    stream through :func:`aggregate_by_week`.
    """

    week_start: date
    tier: str
    total_tokens: int = 0
    cost_usd: float | None = None
