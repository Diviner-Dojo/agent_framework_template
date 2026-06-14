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

#: Default maximum gap (seconds) between consecutive retry_loop signals that may
#: be grouped into one :class:`RetryChain`. Tunable via ``group_retry_chains``'s
#: ``max_gap_seconds`` kwarg; 120s is wide enough to capture a typical cascade
#: (e.g. failed Read → fall back to Glob → fall back to Bash search) without
#: collapsing genuinely-independent loops separated by minutes of other work.
#: Named so a test can change the boundary deterministically (spec A11).
MAX_RETRY_CHAIN_GAP_SECONDS = 120

ORPHANED_SUBAGENT = "orphaned_subagent"
RETRY_LOOP = "retry_loop"

#: Error-class taxonomy (SPEC-20260607-183136 Phase 3 — failure intelligence).
#:
#: A coarse domain-vocabulary grouping over :class:`FailureSignal` rows so the
#: dashboard's A2 panel can attach a short, static remediation hint per class
#: and show the gatekeeper a triage view rather than a flat ranked list.
#:
#: The taxonomy carries the 7 classes named in the spec plus an explicit
#: ``"other"`` for signals the classifier cannot confidently place. ADR-0020
#: honesty discipline: an unclassifiable signal renders in the ``"other"``
#: group with a generic "does not fit a known class" hint — **never**
#: fabricated into a class to make the panel look tidier.
NOT_FOUND = "not_found"
PERMISSION = "permission"
ORPHAN = "orphan"
CONFIG = "config"
VALIDATION = "validation"
TIMEOUT = "timeout"
NETWORK = "network"
OTHER = "other"

#: Canonical ordering of error classes (used for stable group iteration when
#: two groups tie on cost). The 7 spec classes lead; ``other`` always comes
#: last so an honest-absence group does not preempt a real one.
ERROR_CLASSES: tuple[str, ...] = (
    NOT_FOUND,
    PERMISSION,
    ORPHAN,
    CONFIG,
    VALIDATION,
    TIMEOUT,
    NETWORK,
    OTHER,
)

#: Short, **static** remediation hint per class. One sentence each; no
#: fabricated root-cause claims, no dollar/ratio fabrications, no calls to
#: action that imply the analyzer knows more than it does. These are the only
#: guidance strings the dashboard renders for the failure groups — keeping
#: them static (not derived from the signal) is what makes the ADR-0020
#: honesty discipline straightforward to audit.
REMEDIATION_HINTS: dict[str, str] = {
    NOT_FOUND: (
        "These signals typically mean the agent was looking for a file, "
        "path, or pattern that does not exist. The Detail column shows "
        "what it was trying to find."
    ),
    PERMISSION: (
        "These signals typically mean a call was rejected at a boundary "
        "(filesystem, API, or sandbox). The Detail column shows which "
        "tool was being blocked."
    ),
    ORPHAN: (
        "A subagent was dispatched but never finished and returned to its "
        "main session. The Detail column names the subagent type; the "
        "transcript's last events show where it stopped."
    ),
    CONFIG: (
        "These signals typically point to a missing or invalid setting. "
        "Look for the related config file or environment variable in the "
        "Detail column."
    ),
    VALIDATION: (
        "The agent tried to apply an edit or write that the tool rejected. "
        "The Detail column may show which file or argument caused the "
        "mismatch."
    ),
    TIMEOUT: (
        "A call exceeded its time budget. Look in the Detail column for "
        "the tool that timed out; a long input or a slow downstream "
        "service is the usual cause."
    ),
    NETWORK: (
        "A network-dependent call failed. Look for a transient outage, a "
        "wrong endpoint, or a missing retry setting in the agent's "
        "configuration."
    ),
    OTHER: (
        "These signals do not fit a known class. Inspect the transcript "
        "for context before assigning a fix."
    ),
}

#: Tools whose retry loop most commonly indicates a missing target. Used by
#: :func:`classify_error` as a conservative heuristic — Bash and other
#: catch-all shells are deliberately NOT in this set because their retry
#: cause is genuinely ambiguous (honest ``other`` instead of a guess).
_NOT_FOUND_RETRY_TOOLS: frozenset[str] = frozenset({"Read", "Glob", "Grep", "LS"})

#: Tools whose retry loop most commonly indicates an input/contract mismatch
#: (``Edit`` rejects an ``old_string`` that does not match; ``Write`` /
#: ``NotebookEdit`` fail on a malformed payload). Distinct from
#: ``_NOT_FOUND_RETRY_TOOLS`` because the remediation differs.
_VALIDATION_RETRY_TOOLS: frozenset[str] = frozenset({"Edit", "Write", "NotebookEdit"})


def classify_error(signal: FailureSignal) -> str:
    """Map a :class:`FailureSignal` to one of :data:`ERROR_CLASSES`.

    Pure and deterministic: the same signal always returns the same class.
    The classifier reads ``failure_type`` and (for retry loops) the tool name
    at the head of the signature; it never inspects ``detail`` for
    natural-language phrases (those are transcript-shaped and would invite a
    drifting heuristic).

    Mapping rules (first match wins):

    * ``orphaned_subagent`` → ``"orphan"`` (structural — the spec class is
      the direct rename of the existing failure_type).
    * ``retry_loop`` of a read-style tool (``Read``/``Glob``/``Grep``/``LS``)
      → ``"not_found"`` (the dominant cause empirically: looking for a path
      or pattern that does not exist).
    * ``retry_loop`` of an edit-style tool (``Edit``/``Write``/``NotebookEdit``)
      → ``"validation"`` (the dominant cause: ``old_string`` mismatch or
      payload rejected by the tool's contract).
    * Anything else → ``"other"``. ``Bash`` retry loops fall here on purpose:
      the cause is genuinely ambiguous (permission, network, timeout, missing
      command, …) and guessing one would violate ADR-0020 honesty.

    Args:
        signal: One detected failure signal.

    Returns:
        One of the strings in :data:`ERROR_CLASSES`.
    """
    if signal.failure_type == ORPHANED_SUBAGENT:
        return ORPHAN
    if signal.failure_type == RETRY_LOOP:
        # ``signature`` is built as ``f"{tool_name}:{input_hash}"`` (see
        # ``_build_retry_signal``); split on the FIRST ``:`` so a hash that
        # happens to contain ``:`` does not corrupt the tool name.
        tool_name = signal.signature.split(":", 1)[0]
        if tool_name in _NOT_FOUND_RETRY_TOOLS:
            return NOT_FOUND
        if tool_name in _VALIDATION_RETRY_TOOLS:
            return VALIDATION
    return OTHER


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


@dataclass(frozen=True)
class RetryChain:
    """A temporally-adjacent cascade of one or more retry_loop failures.

    Phase 3 Unit 3 (SPEC-20260610-001134): one underlying cause (e.g. a missing
    path) often produces a CASCADE of retry loops as the agent flails — a
    ``Read`` retry loop followed shortly by a ``Glob`` retry loop chasing the
    same target. A :class:`RetryChain` groups those into one logical unit so
    the gatekeeper reads "one root cause, N reactions" rather than N
    independent failures.

    Honest-absence discipline (ADR-0020): ``total_cost_usd`` is ``None`` ONLY
    when every link is unpriced; a single priced link in a mixed chain
    contributes its cost and the unpriced links are excluded — never fabricated
    as ``$0``. A link with ``cost_usd == 0.0`` IS priced (genuinely free) and
    contributes ``0.0`` to the sum.

    Attributes:
        head: The earliest signal (by ``first_seen``) in the chain. Renders as
            the parent row in the dashboard.
        links: The remaining signals in the chain, in temporal order
            (ascending ``first_seen``). A chain of length 1 has an empty list.
        total_cost_usd: Sum of every link's ``cost_usd`` whose value is
            non-``None``. ``None`` iff EVERY link is unpriced.
        total_wasted_tokens: Sum of every link's
            :meth:`FailureSignal.wasted_total_tokens` (``None`` values count
            as 0 per the existing convention).
    """

    head: RankedFailure
    links: tuple[RankedFailure, ...]
    total_cost_usd: float | None
    total_wasted_tokens: int

    def size(self) -> int:
        """The number of signals in the chain (head + links)."""
        return 1 + len(self.links)

    def all_links(self) -> tuple[RankedFailure, ...]:
        """All signals in temporal order: head followed by links."""
        return (self.head, *self.links)


def _retry_pair_chains(prev: RankedFailure, nxt: RankedFailure, max_gap_seconds: int) -> bool:
    """Return True iff ``prev`` and ``nxt`` are temporally adjacent retries.

    Honest-absence rules (spec R3):

    * Both signals must be ``failure_type == RETRY_LOOP`` (non-retry signals
      are not chainable; the caller is responsible for filtering).
    * Both endpoints must have populated timestamps; ``None`` on either side
      means no chain (no fabricated adjacency).
    * If the ``datetime`` subtraction raises ``TypeError`` (tz-aware/naive
      mismatch from an alternate data source), the pair is treated as
      unchainable. The canonical analyzer transport emits tz-aware UTC, so
      this branch is defensive belt-and-braces for future importers.

    The boundary is **inclusive**: ``gap == max_gap_seconds`` chains.
    """
    if prev.signal.failure_type != RETRY_LOOP or nxt.signal.failure_type != RETRY_LOOP:
        return False
    prev_end = prev.signal.last_seen
    nxt_start = nxt.signal.first_seen
    if prev_end is None or nxt_start is None:
        return False
    try:
        gap_seconds = (nxt_start - prev_end).total_seconds()
    except TypeError:
        # tz-aware / naive mismatch — treat as missing-timestamp (no chain).
        return False
    return gap_seconds <= max_gap_seconds


def group_retry_chains(
    ranked: list[RankedFailure],
    *,
    max_gap_seconds: int = MAX_RETRY_CHAIN_GAP_SECONDS,
) -> list[RetryChain]:
    """Group temporally-adjacent retry_loop signals into :class:`RetryChain`s.

    Pure read-time fold over the existing :class:`RankedFailure` list — no
    DB read, no mutation, no IO (ADR-0013 compute-don't-store). Public (called
    from ``dashboard.py``); the sibling failures-/drift-grouping helpers
    ``_group_failures_by_class`` / ``_group_drift_by_kind`` live in
    ``dashboard.py`` and are private because they don't cross a module boundary.

    The TEMPORAL heuristic: two consecutive ``retry_loop`` signals chain iff
    ``next.first_seen - prev.last_seen <= max_gap_seconds`` (boundary
    inclusive). Non-retry-loop signals are **skipped over** by the chain
    walker — they do NOT reset the chain-candidate pointer. Rationale: the
    caller composes ``_group_failures_by_class`` before this function, so a
    per-class group today contains only retry-loops (orphans go to ORPHAN
    class); the skip-over rule preserves the "one root cause, N reactions"
    semantic for future heterogeneous classes (an unrelated failure between
    two retries does not undo their temporal adjacency).

    The head of each chain is the earliest retry-loop in the run (preserving
    inbound rank order on ``first_seen`` ties via Python's stable sort);
    links are the rest in ascending ``first_seen`` order.

    Honest-absence (spec R2/A6, ADR-0020):

    * ``total_cost_usd = None`` iff EVERY link has ``cost_usd is None``.
      A single priced link in a mixed chain contributes its cost; unpriced
      links are silently excluded (never fabricated as ``$0``).
    * A link with ``cost_usd == 0.0`` IS priced (genuinely free) and
      contributes ``0.0`` to the sum — guards against a future ``if cost_usd``
      truthy guard accidentally excluding zero-cost rows.

    Args:
        ranked: Inbound list (typically the per-class slice from
            :func:`_group_failures_by_class`). Non-retry signals pass through
            invisibly and produce no chain.
        max_gap_seconds: Override for :data:`MAX_RETRY_CHAIN_GAP_SECONDS`.

    Returns:
        Zero or more :class:`RetryChain` objects in inbound order (the head's
        rank-list position determines chain order). A retry-loop with no
        eligible neighbour produces a chain of length 1 (empty ``links``).
        Non-retry signals produce no chain — they are dropped from the result.
    """
    chains: list[RetryChain] = []
    current_links: list[RankedFailure] = []
    for rf in ranked:
        if rf.signal.failure_type != RETRY_LOOP:
            # Skipped over: does NOT close the current chain (the next retry,
            # if within the window of the previous retry's last_seen, still
            # joins it). Rationale documented above.
            continue
        if not current_links:
            current_links.append(rf)
            continue
        if _retry_pair_chains(current_links[-1], rf, max_gap_seconds):
            current_links.append(rf)
        else:
            chains.append(_build_retry_chain(current_links))
            current_links = [rf]
    if current_links:
        chains.append(_build_retry_chain(current_links))
    return chains


def _build_retry_chain(members: list[RankedFailure]) -> RetryChain:
    """Construct a :class:`RetryChain` from an ordered list of retry-loop members.

    Members arrive in inbound (rank-list) order, which equals temporal order
    for chained members (Python's stable sort + the chain walker's
    front-to-back pass preserve ``first_seen`` order). The first element is
    the head; the rest are links.

    ``total_cost_usd`` and ``total_wasted_tokens`` are computed here per the
    honest-absence rule documented on :class:`RetryChain`.
    """
    head = members[0]
    links = tuple(members[1:])
    priced_costs = [m.cost_usd for m in members if m.cost_usd is not None]
    total_cost: float | None = sum(priced_costs) if priced_costs else None
    total_wasted = sum(m.signal.wasted_total_tokens() for m in members)
    return RetryChain(
        head=head,
        links=links,
        total_cost_usd=total_cost,
        total_wasted_tokens=total_wasted,
    )
