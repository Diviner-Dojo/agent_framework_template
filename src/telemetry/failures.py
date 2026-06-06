"""Detect agent failure / token-waste signals from parsed transcript events.

Pure logic over already-parsed events — the SQLite read and the transcript walk
happen in ``scripts/telemetry/analyze_failures.py``. This module knows nothing
about files or the database, so every rule here is exhaustively unit-testable
(the "cook"; the transport layer is the "runner").

Layer A2 (ADR-0020) detects two **grounded** failure classes (a third,
stop-loop / forced-continuation, is deferred to A2.1 — no reliable transcript
signal was found, and a guessed detector would violate the smoke-test-fidelity
lesson):

* **retry_loop** — the same ``(tool name, canonical-input hash)`` issued in an
  unbroken run of ``threshold`` or more calls within one session. The wasted
  tokens are the generations that produced the *redundant* repeats (calls 2..N),
  deduplicated by message id.
* **orphaned_subagent** — an ``Agent`` dispatch that never received a
  ``tool_result`` (the subagent never returned to its parent), or a subagent
  transcript that did not terminate on a clean assistant turn.

Honesty rules carried from A1: a wasted-token tier may be ``unknown`` and is
never silently zero-rated; the dollar weight used for ranking is computed at read
time from token counts (compute-don't-store, ADR-0013), never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.telemetry.pricing import UNKNOWN_TIER, PricingTable

#: Default number of identical consecutive calls that constitutes a retry loop.
#: Conservative (3, not 2) to avoid flagging a legitimate retry-after-failure as
#: a loop — a single retry is normal; three identical calls in a row is stuck.
DEFAULT_RETRY_THRESHOLD = 3

ORPHANED_SUBAGENT = "orphaned_subagent"
RETRY_LOOP = "retry_loop"


@dataclass(frozen=True)
class ToolCall:
    """One ``tool_use`` block in a session's call stream (transport-parsed).

    ``tier`` is resolved by the transport layer (it owns the pricing table) so
    this module stays pricing-agnostic for *detection*. Token counts are the
    issuing assistant message's usage; ``message_id`` lets the detector avoid
    double-counting when one message emits several identical calls.
    """

    name: str
    input_hash: str
    message_id: str
    tier: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read_tokens: int | None = None
    cache_create_tokens: int | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class SubagentDispatch:
    """An ``Agent`` tool_use in the parent session (a subagent was launched).

    ``run_in_background`` dispatches return asynchronously, so a missing
    synchronous ``tool_result`` is normal for them — the no-result orphan rule
    skips them to avoid a false positive (a hung background agent is still
    caught via its own transcript's non-clean terminal).
    """

    tool_use_id: str
    subagent_type: str
    timestamp: datetime | None = None
    run_in_background: bool = False


@dataclass(frozen=True)
class SubagentRun:
    """A subagent transcript (``agent-<id>.jsonl``) summarised by the transport.

    Attributes:
        agent_id: The subagent instance id (the ``agent-<id>`` filename stem).
        source_tool_use_id: The parent ``Agent`` dispatch id this run came from,
            if the transcript recorded one (links a run back to its dispatch).
        completed: True iff the transcript's last record is a clean assistant
            turn (a returned subagent), False if it ends mid-flight.
        tier/tokens_*: the run's own token usage (the cost of the wasted work).
    """

    agent_id: str
    source_tool_use_id: str | None
    completed: bool
    tier: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read_tokens: int | None = None
    cache_create_tokens: int | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


@dataclass
class FailureSignal:
    """One detected failure, with the wasted-token bundle (the cost input)."""

    failure_type: str
    signature: str
    occurrence_count: int
    tier: str
    wasted_tokens_in: int | None = None
    wasted_tokens_out: int | None = None
    wasted_cache_read_tokens: int | None = None
    wasted_cache_create_tokens: int | None = None
    detail: str = ""
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    def wasted_total_tokens(self) -> int:
        """Sum of every wasted billable token kind (``None`` counts as 0)."""
        return (
            (self.wasted_tokens_in or 0)
            + (self.wasted_tokens_out or 0)
            + (self.wasted_cache_read_tokens or 0)
            + (self.wasted_cache_create_tokens or 0)
        )


@dataclass(frozen=True)
class RankedFailure:
    """A failure signal paired with its derived dollar weight (``None`` if the
    tier is unpriced — rendered as 'uncosted', never ``$0``)."""

    signal: FailureSignal
    cost_usd: float | None


def _sum_optional(values: list[int | None]) -> int | None:
    """Sum optional ints, returning ``None`` only if every entry is ``None``."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _dominant_tier(tiers: list[str]) -> str:
    """Return the most common tier in a run (ties broken by first occurrence)."""
    if not tiers:
        return UNKNOWN_TIER
    counts: dict[str, int] = {}
    for tier in tiers:
        counts[tier] = counts.get(tier, 0) + 1
    # max() is stable over dict insertion order, so ties favour the earliest.
    return max(counts, key=lambda t: counts[t])


def detect_retry_loops(
    calls: list[ToolCall], *, threshold: int = DEFAULT_RETRY_THRESHOLD
) -> list[FailureSignal]:
    """Find unbroken runs of an identical ``(name, input_hash)`` call.

    A run of length ``L >= threshold`` is one retry loop. Wasted tokens are the
    usage of the *redundant* repeats (the 2nd..Lth calls), deduplicated by
    ``message_id`` so a single assistant message emitting two identical calls is
    not counted twice. ``occurrence_count`` is the full run length ``L``.

    Args:
        calls: The session's tool calls in chronological order.
        threshold: Minimum run length to flag (default 3).

    Returns:
        One :class:`FailureSignal` per detected loop, in order of appearance.
    """
    if threshold < 2:
        threshold = 2
    signals: list[FailureSignal] = []
    i = 0
    n = len(calls)
    while i < n:
        j = i + 1
        key = (calls[i].name, calls[i].input_hash)
        while j < n and (calls[j].name, calls[j].input_hash) == key:
            j += 1
        run = calls[i:j]
        if len(run) >= threshold:
            signals.append(_build_retry_signal(run))
        i = j
    return signals


def _build_retry_signal(run: list[ToolCall]) -> FailureSignal:
    """Build a retry_loop signal from one run of identical calls."""
    repeats = run[1:]  # the redundant calls (the first call is legitimate work)
    seen: set[str] = set()
    t_in: list[int | None] = []
    t_out: list[int | None] = []
    c_read: list[int | None] = []
    c_create: list[int | None] = []
    for call in repeats:
        if call.message_id in seen:
            continue
        seen.add(call.message_id)
        t_in.append(call.tokens_in)
        t_out.append(call.tokens_out)
        c_read.append(call.cache_read_tokens)
        c_create.append(call.cache_create_tokens)
    timestamps = [c.timestamp for c in run if c.timestamp is not None]
    first = run[0]
    return FailureSignal(
        failure_type=RETRY_LOOP,
        signature=f"{first.name}:{first.input_hash}",
        occurrence_count=len(run),
        tier=_dominant_tier([c.tier for c in run]),
        wasted_tokens_in=_sum_optional(t_in),
        wasted_tokens_out=_sum_optional(t_out),
        wasted_cache_read_tokens=_sum_optional(c_read),
        wasted_cache_create_tokens=_sum_optional(c_create),
        detail=f"{first.name} called {len(run)}x identically in a row",
        first_seen=min(timestamps) if timestamps else None,
        last_seen=max(timestamps) if timestamps else None,
    )


def detect_orphaned_subagents(
    dispatches: list[SubagentDispatch],
    result_ids: set[str],
    runs: list[SubagentRun],
) -> list[FailureSignal]:
    """Flag subagent dispatches that never returned, or runs that hung.

    Two complementary conditions, de-duplicated so one orphan is reported once:

    1. A dispatch whose ``tool_use_id`` never appears as a ``tool_result`` — the
       parent launched a subagent and got nothing back. Wasted tokens are taken
       from the linked subagent run when one can be matched by
       ``source_tool_use_id``.
    2. A subagent run that did not terminate cleanly (``completed is False``) and
       was not already flagged via its dispatch — its transcript ends mid-flight.

    Args:
        dispatches: ``Agent`` tool_use blocks from the parent session.
        result_ids: tool_use_ids that received a ``tool_result``.
        runs: summarised subagent transcripts.

    Returns:
        One :class:`FailureSignal` per orphan, dispatches first.
    """
    runs_by_source = {r.source_tool_use_id: r for r in runs if r.source_tool_use_id}
    flagged_run_ids: set[str] = set()
    signals: list[FailureSignal] = []

    for dispatch in dispatches:
        if dispatch.tool_use_id in result_ids or dispatch.run_in_background:
            continue
        run = runs_by_source.get(dispatch.tool_use_id)
        if run is not None:
            flagged_run_ids.add(run.agent_id)
        signals.append(
            FailureSignal(
                failure_type=ORPHANED_SUBAGENT,
                signature=dispatch.tool_use_id,
                occurrence_count=1,
                tier=run.tier if run is not None else UNKNOWN_TIER,
                wasted_tokens_in=run.tokens_in if run is not None else None,
                wasted_tokens_out=run.tokens_out if run is not None else None,
                wasted_cache_read_tokens=run.cache_read_tokens if run is not None else None,
                wasted_cache_create_tokens=run.cache_create_tokens if run is not None else None,
                detail=f"subagent '{dispatch.subagent_type}' dispatched but no result returned",
                first_seen=dispatch.timestamp,
                last_seen=run.last_seen if run is not None else dispatch.timestamp,
            )
        )

    for run in runs:
        if run.agent_id in flagged_run_ids or run.completed:
            continue
        signals.append(
            FailureSignal(
                failure_type=ORPHANED_SUBAGENT,
                signature=run.agent_id,
                occurrence_count=1,
                tier=run.tier,
                wasted_tokens_in=run.tokens_in,
                wasted_tokens_out=run.tokens_out,
                wasted_cache_read_tokens=run.cache_read_tokens,
                wasted_cache_create_tokens=run.cache_create_tokens,
                detail=f"subagent transcript '{run.agent_id}' did not terminate cleanly",
                first_seen=run.first_seen,
                last_seen=run.last_seen,
            )
        )
    return signals


def rank_failures(signals: list[FailureSignal], pricing: PricingTable) -> list[RankedFailure]:
    """Cost-weight and rank failures, most-expensive first.

    The dollar weight is derived from the wasted-token bundle at read time
    (compute-don't-store). An unpriced tier yields ``cost_usd=None`` and sorts
    *last* (we never fabricate a ``$0`` to make an unknown look free); ties and
    unpriced rows fall back to a wasted-token ordering so a big unknown waste
    still ranks above a small one.

    Args:
        signals: Detected failures.
        pricing: Resolved pricing table.

    Returns:
        ``RankedFailure`` values sorted by descending cost, then wasted tokens.
    """
    ranked = [
        RankedFailure(
            signal=s,
            cost_usd=pricing.cost_usd(
                s.tier,
                tokens_in=s.wasted_tokens_in,
                tokens_out=s.wasted_tokens_out,
                cache_read_tokens=s.wasted_cache_read_tokens,
                cache_create_tokens=s.wasted_cache_create_tokens,
            ),
        )
        for s in signals
    ]
    # Sort key: priced rows before unpriced (False < True), then cost desc, then
    # wasted-token desc as the tiebreaker / unpriced ordering.
    ranked.sort(
        key=lambda r: (
            r.cost_usd is None,
            -(r.cost_usd or 0.0),
            -r.signal.wasted_total_tokens(),
        )
    )
    return ranked
