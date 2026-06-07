"""Pure event-fold model for the Layer B live dashboard (SPEC-20260607-183136 R14).

The dashboard daemon (``scripts/telemetry/dashboard_server.py``) parses session
and subagent transcripts into a sequence of :class:`LiveEvent` values, then folds
them into a :class:`LiveState` using :func:`fold_events` / :func:`apply_event`.
This module is **pure**: it imports no transcript IO and no ``scripts.*`` module
(R14 / AC14). All statefulness lives in the transport process; the model itself
persists nothing (R10 read-only / compute-don't-store).

The acceptance-criteria invariants this enforces are:

* **AC14 (purity seam):** the test guard asserts the import graph of this module
  is free of ``scripts.*`` and any transcript-IO module. This lets the no-inject
  guards (AC3) and read-only DB guards (AC5) treat the live layer as a black
  box that touches nothing measurable.
* **R3 / AC11 (live view shape):** the :class:`LiveState` exposes the *shape*
  Phase 1 promises — agent lanes (active/complete/orphaned with model + cost +
  tool/failure counts), a context-window runway gauge with amber/red thresholds,
  and a recent live cost/failure stream. Authored fixture-transcript tests at the
  transport layer drive end-to-end coverage; this module's unit tests cover the
  fold algebra (idempotence, monotonicity, orphan transition).

Design choices kept deliberately small:

* No ``Agent``-tool-name string is parsed here — the transport layer hands us a
  ``LiveEvent`` already classified by kind, so a future change to Claude Code's
  tool naming is one transport-layer edit, not a model change.
* Cost is computed from already-resolved token counts × :mod:`src.telemetry.pricing`
  tier prices, matching the A1 read-side computation so the live view cannot
  diverge from the retrospective panel.
* The runway gauge accepts thresholds as parameters (defaults ``0.55`` amber,
  ``0.70`` red) so the transport layer can pass the active model's profile
  (``config/model_context_profiles.yaml``) without this module taking a YAML
  dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from src.telemetry.pricing import PricingTable

#: Lane status markers. ``orphaned`` means the main session dispatched a
#: subagent that produced output but its tool-result was never seen on the main
#: side — the failure-intelligence analogue of A2 ``orphaned_subagent``, but
#: computed live from the in-memory state, not from a DB query.
LANE_ACTIVE = "active"
LANE_COMPLETE = "complete"
LANE_ORPHANED = "orphaned"

#: Runway gauge status thresholds (as fractions of the context window). The
#: amber/red boundaries match ``soft_wrapup_fraction`` / ``hard_wrapup_fraction``
#: from ``config/model_context_profiles.yaml`` — a deliberate echo so the
#: dashboard's "amber" lines up with the session-wrap-up nudge (ADR-0018).
RUNWAY_AMBER_DEFAULT = 0.55
RUNWAY_RED_DEFAULT = 0.70

RUNWAY_OK = "ok"
RUNWAY_AMBER = "amber"
RUNWAY_RED = "red"


@dataclass(frozen=True)
class LiveEvent:
    """One parsed unit of live activity, produced by the transport layer.

    The transport layer (``scripts/telemetry/dashboard_server.py``) walks the
    session JSONL files and emits one :class:`LiveEvent` per parseable line.
    The fields are deliberately a *flat* projection of what the transcripts
    carry — the model does not re-parse anything.

    Attributes:
        kind: One of ``message`` (assistant message with token usage),
            ``dispatch`` (the main session called the ``Agent`` tool),
            ``result`` (a tool-result back to the main session — matched to a
            dispatch by ``ref_id``), ``context`` (a context-window occupancy
            snapshot, e.g. from the statusLine sensor).
        timestamp: When this event was recorded (UTC).
        lane_id: The lane this event belongs to. The main session lane is
            ``"main"``; a dispatched subagent lane is the dispatch's ``tool_id``.
        ref_id: For a ``result`` event, the ``tool_id`` of the dispatch it
            answers. ``None`` for other kinds.
        agent_type: For a ``dispatch`` or new-lane ``message``, the
            ``subagent_type`` (e.g. ``security-specialist``). ``None`` for the
            main lane.
        model: The model ID for a ``message`` (e.g. ``claude-opus-4-7``). The
            tier is resolved at fold-time via :func:`resolve_tier`.
        input_tokens: Input tokens for a ``message`` event (``None`` otherwise).
        output_tokens: Output tokens for a ``message`` event.
        cache_read_tokens: Cache-read tokens (priced separately by tier).
        cache_create_tokens: Cache-create tokens (priced separately by tier).
        context_tokens: For a ``context`` event, the resident-context occupancy.
        context_window: For a ``context`` event, the model's context-window size
            (lets one fold cover sessions on multiple models / windows).
        tool_name: For a ``dispatch`` event, the tool name (always ``"Agent"``
            in current Claude Code; captured so a future tool family can be
            distinguished without a model change).
    """

    kind: str
    timestamp: datetime
    lane_id: str
    ref_id: str | None = None
    agent_type: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_create_tokens: int | None = None
    context_tokens: int | None = None
    context_window: int | None = None
    tool_name: str | None = None


@dataclass(frozen=True)
class AgentLane:
    """The live state of one agent lane (main session OR a dispatched subagent).

    A lane starts ``active`` on its first event; transitions to ``complete``
    when a matching tool-result lands (for a subagent) or when the main session
    sees a terminal turn; transitions to ``orphaned`` when the surrounding
    state declares it so (e.g. the main session ended without a matching
    result).
    """

    lane_id: str
    kind: str  # "main" | "agent"
    agent_type: str | None
    model: str | None
    status: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_create_tokens: int = 0
    cost_usd: float = 0.0
    tool_count: int = 0
    failure_count: int = 0
    started_at: datetime | None = None
    last_event_at: datetime | None = None


@dataclass(frozen=True)
class RunwayGauge:
    """Context-window runway gauge state (R2 / AC11).

    Attributes:
        current_tokens: The most recent ``context_tokens`` snapshot, or ``0``.
        context_window: The model's full context window in tokens.
        fill_pct: ``current_tokens / context_window * 100`` (0 when window is 0).
        status: One of :data:`RUNWAY_OK` / :data:`RUNWAY_AMBER` / :data:`RUNWAY_RED`.
        est_turns_remaining: A rough integer estimate, computed from the
            window's remaining tokens divided by the rolling average
            *output*-tokens per assistant turn seen so far. ``None`` until at
            least one priced turn has landed (no fabrication on cold start).
    """

    current_tokens: int = 0
    context_window: int = 0
    fill_pct: float = 0.0
    status: str = RUNWAY_OK
    est_turns_remaining: int | None = None


@dataclass(frozen=True)
class LiveCostEvent:
    """One entry in the rolling live cost/failure stream (R2)."""

    timestamp: datetime
    lane_id: str
    kind: str  # "turn" | "failure"
    cost_usd: float
    tokens: int
    detail: str = ""


@dataclass(frozen=True)
class LiveState:
    r"""The full live state of one session, as a frozen value.

    A pure fold: :func:`apply_event` returns a new :class:`LiveState` for every
    event, so a transport-layer test can replay events without mutating shared
    state and the renderer can snapshot the state for a fragment response
    without worrying about a concurrent mutation.

    Attributes:
        main: The main session's lane, or ``None`` until its first event.
        agents: Dispatched subagent lanes in dispatch order.
        runway: The current context-window runway gauge.
        total_cost_usd: The sum of every lane's ``cost_usd`` (single source of
            truth — never re-derived in the renderer).
        recent_events: The rolling live stream (most recent last, capped at
            :data:`RECENT_EVENTS_CAP`).
        main_turns_seen: The number of priced *main-lane* assistant turns folded
            so far. The runway gauge uses ONLY the main lane's rolling average
            (arch F2): a Haiku subagent's much-cheaper turn would otherwise pull
            the average down and overstate the main-Opus runway.
        main_turn_output_tokens: Sum of output tokens across the main lane's
            priced turns. With ``main_turns_seen`` it gives the rolling avg used
            by the runway gauge.
        uncosted_turns: Count of folded turns whose tier was ``unknown`` (or
            had no pricing entry). Tokens still accumulate on the lane (so the
            developer sees activity), but cost is NOT added to
            ``total_cost_usd`` — the dashboard can render "partial coverage"
            (arch F1, matching ``CostReport.is_fully_covered``'s honesty:
            "uncosted ≠ \$0").
    """

    main: AgentLane | None = None
    agents: tuple[AgentLane, ...] = ()
    runway: RunwayGauge = field(default_factory=RunwayGauge)
    total_cost_usd: float = 0.0
    recent_events: tuple[LiveCostEvent, ...] = ()
    main_turns_seen: int = 0
    main_turn_output_tokens: int = 0
    uncosted_turns: int = 0


#: Cap on the live cost/failure stream so a long session does not balloon
#: in-memory state. The dashboard polls fragments; deeper history comes from the
#: retrospective DB views (R3).
RECENT_EVENTS_CAP = 100


def empty_state() -> LiveState:
    """Return an empty :class:`LiveState` — the identity of the fold."""
    return LiveState()


def fold_events(
    events: list[LiveEvent],
    pricing: PricingTable,
    *,
    amber_threshold: float = RUNWAY_AMBER_DEFAULT,
    red_threshold: float = RUNWAY_RED_DEFAULT,
) -> LiveState:
    """Fold a chronological event sequence into a :class:`LiveState`.

    A repeated fold over the same event sequence is byte-equivalent to a single
    fold (idempotent on the *sequence*, not on individual events — the model
    is event-driven, not snapshot-driven).

    Args:
        events: Events in chronological order (transport-layer guarantee).
        pricing: Resolved pricing table; passed in so callers can substitute a
            test-only table without re-loading YAML.
        amber_threshold: Runway-gauge amber boundary, as a fraction of the
            context window. Defaults to :data:`RUNWAY_AMBER_DEFAULT`.
        red_threshold: Runway-gauge red boundary. Defaults to :data:`RUNWAY_RED_DEFAULT`.

    Returns:
        The resulting :class:`LiveState`.
    """
    state = empty_state()
    for event in events:
        state = apply_event(
            state,
            event,
            pricing,
            amber_threshold=amber_threshold,
            red_threshold=red_threshold,
        )
    return state


def apply_event(
    state: LiveState,
    event: LiveEvent,
    pricing: PricingTable,
    *,
    amber_threshold: float = RUNWAY_AMBER_DEFAULT,
    red_threshold: float = RUNWAY_RED_DEFAULT,
) -> LiveState:
    """Apply one :class:`LiveEvent` to a :class:`LiveState` and return the next.

    The fold is dispatched on ``event.kind``:

    * ``"message"`` — credit tokens + cost to the lane; if the lane does not
      yet exist, create it. Update the rolling per-turn estimate for the
      runway gauge.
    * ``"dispatch"`` — start a new subagent lane in ``active`` status.
    * ``"result"`` — transition the matching lane to ``complete``; increment
      the main lane's ``tool_count``.
    * ``"context"`` — refresh the runway gauge from the new occupancy snapshot
      + window size; recompute amber/red status and the est-turns-remaining
      rolling-average estimate.

    An unknown ``kind`` is a no-op (forward-compat: a future transport-layer
    event we have not yet modelled won't crash the fold).
    """
    if event.kind == "message":
        return _apply_message(state, event, pricing)
    if event.kind == "dispatch":
        return _apply_dispatch(state, event)
    if event.kind == "result":
        return _apply_result(state, event)
    if event.kind == "context":
        return _apply_context(state, event, amber_threshold, red_threshold)
    return state


# --------------------------------------------------------------------------- #
# Per-kind handlers — small + pure.
# --------------------------------------------------------------------------- #


def _apply_message(state: LiveState, event: LiveEvent, pricing: PricingTable) -> LiveState:
    """Fold an assistant-message event into the lane it belongs to."""
    tokens_in = event.input_tokens or 0
    tokens_out = event.output_tokens or 0
    cache_read = event.cache_read_tokens or 0
    cache_create = event.cache_create_tokens or 0

    cost, uncosted = _price_message(
        event.model, tokens_in, tokens_out, cache_read, cache_create, pricing
    )

    if event.lane_id == "main":
        main = state.main or AgentLane(
            lane_id="main",
            kind="main",
            agent_type=None,
            model=event.model,
            status=LANE_ACTIVE,
            started_at=event.timestamp,
        )
        main = replace(
            main,
            model=event.model or main.model,
            input_tokens=main.input_tokens + tokens_in,
            output_tokens=main.output_tokens + tokens_out,
            cache_read_tokens=main.cache_read_tokens + cache_read,
            cache_create_tokens=main.cache_create_tokens + cache_create,
            cost_usd=main.cost_usd + cost,
            last_event_at=event.timestamp,
        )
        new_state = replace(state, main=main)
    else:
        existing = _find_lane(state.agents, event.lane_id)
        if existing is None:
            lane = AgentLane(
                lane_id=event.lane_id,
                kind="agent",
                agent_type=event.agent_type,
                model=event.model,
                status=LANE_ACTIVE,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                cache_read_tokens=cache_read,
                cache_create_tokens=cache_create,
                cost_usd=cost,
                started_at=event.timestamp,
                last_event_at=event.timestamp,
            )
            new_agents = state.agents + (lane,)
        else:
            lane = replace(
                existing,
                model=event.model or existing.model,
                agent_type=existing.agent_type or event.agent_type,
                input_tokens=existing.input_tokens + tokens_in,
                output_tokens=existing.output_tokens + tokens_out,
                cache_read_tokens=existing.cache_read_tokens + cache_read,
                cache_create_tokens=existing.cache_create_tokens + cache_create,
                cost_usd=existing.cost_usd + cost,
                last_event_at=event.timestamp,
            )
            new_agents = _replace_lane(state.agents, lane)
        new_state = replace(state, agents=new_agents)

    cost_event = LiveCostEvent(
        timestamp=event.timestamp,
        lane_id=event.lane_id,
        kind="turn",
        cost_usd=cost,
        tokens=tokens_in + tokens_out,
    )
    return _bump_totals(
        new_state,
        cost,
        tokens_out,
        cost_event,
        is_main=(event.lane_id == "main"),
        uncosted=uncosted,
    )


def _apply_dispatch(state: LiveState, event: LiveEvent) -> LiveState:
    """Start a new agent lane in ``active`` status, indexed by ``lane_id``.

    If the lane already exists (a duplicate dispatch event in the transcript),
    leave it alone — the fold is idempotent on resubmission.
    """
    if _find_lane(state.agents, event.lane_id) is not None:
        return state
    lane = AgentLane(
        lane_id=event.lane_id,
        kind="agent",
        agent_type=event.agent_type,
        model=None,
        status=LANE_ACTIVE,
        started_at=event.timestamp,
        last_event_at=event.timestamp,
    )
    new_agents = state.agents + (lane,)
    main = state.main
    if main is not None:
        main = replace(main, tool_count=main.tool_count + 1)
    return replace(state, agents=new_agents, main=main)


def _apply_result(state: LiveState, event: LiveEvent) -> LiveState:
    """Mark the lane referenced by ``ref_id`` as ``complete``.

    A result without a matching dispatch is ignored (a malformed transcript
    cannot demote a live state into garbage). A result on an already-completed
    lane is also a no-op.
    """
    target_id = event.ref_id or event.lane_id
    lane = _find_lane(state.agents, target_id)
    if lane is None:
        return state
    if lane.status == LANE_COMPLETE:
        return state
    completed = replace(lane, status=LANE_COMPLETE, last_event_at=event.timestamp)
    return replace(state, agents=_replace_lane(state.agents, completed))


def _apply_context(
    state: LiveState, event: LiveEvent, amber_threshold: float, red_threshold: float
) -> LiveState:
    """Refresh the runway gauge from a context-occupancy snapshot."""
    current = max(event.context_tokens or 0, 0)
    window = max(event.context_window or 0, 0)
    fill_pct = (current / window * 100.0) if window > 0 else 0.0
    status = _runway_status(fill_pct, amber_threshold, red_threshold)
    est = _estimate_turns_remaining(state, current, window)
    runway = RunwayGauge(
        current_tokens=current,
        context_window=window,
        fill_pct=round(fill_pct, 1),
        status=status,
        est_turns_remaining=est,
    )
    return replace(state, runway=runway)


# --------------------------------------------------------------------------- #
# Mark-orphaned helper — called by the transport layer when a session ends.
# --------------------------------------------------------------------------- #


def mark_orphans(state: LiveState) -> LiveState:
    """Transition any still-``active`` subagent lanes to ``orphaned``.

    Called by the transport layer once a session is considered closed (the main
    JSONL has not been written to within a quiet-window, or the developer
    explicitly stops the daemon's "follow" for a session). Idempotent.
    """
    if not state.agents:
        return state
    updated = []
    changed = False
    for lane in state.agents:
        if lane.status == LANE_ACTIVE:
            updated.append(replace(lane, status=LANE_ORPHANED))
            changed = True
        else:
            updated.append(lane)
    if not changed:
        return state
    return replace(state, agents=tuple(updated))


# --------------------------------------------------------------------------- #
# Small pure helpers.
# --------------------------------------------------------------------------- #


def _price_message(
    model: str | None,
    tokens_in: int,
    tokens_out: int,
    cache_read: int,
    cache_create: int,
    pricing: PricingTable,
) -> tuple[float, bool]:
    r"""Compute the API-equivalent USD cost of one assistant message.

    Delegates to :meth:`PricingTable.cost_usd` so the live and stored cost
    figures agree (single source of truth — ADR-0013). An unknown tier (no
    model, or a model not resolvable to a priced family) returns
    ``(0.0, True)``: the caller treats this as an uncosted turn — tokens still
    accumulate on the lane (so the developer sees activity) but the cost is
    NOT added to ``total_cost_usd`` (arch F1, matching the static report's
    ``cost_usd=None`` "uncosted ≠ \$0" honesty).

    Returns:
        A tuple ``(cost_usd, is_uncosted)``. ``is_uncosted=True`` iff the tier
        is unknown / unpriced; in that case ``cost_usd=0.0``.
    """
    tier = pricing.resolve_tier(model)
    cost = pricing.cost_usd(
        tier,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_read_tokens=cache_read,
        cache_create_tokens=cache_create,
    )
    if cost is None:
        return 0.0, True
    return cost, False


def _find_lane(lanes: tuple[AgentLane, ...], lane_id: str) -> AgentLane | None:
    """Return the lane with this ``lane_id``, or ``None``."""
    for lane in lanes:
        if lane.lane_id == lane_id:
            return lane
    return None


def _replace_lane(lanes: tuple[AgentLane, ...], updated: AgentLane) -> tuple[AgentLane, ...]:
    """Return ``lanes`` with the lane sharing ``updated.lane_id`` replaced."""
    return tuple(updated if lane.lane_id == updated.lane_id else lane for lane in lanes)


def _bump_totals(
    state: LiveState,
    cost: float,
    output_tokens: int,
    cost_event: LiveCostEvent,
    *,
    is_main: bool,
    uncosted: bool,
) -> LiveState:
    """Update the rolling totals + recent-events stream after a message.

    The runway gauge's rolling average uses ONLY main-lane turns (arch F2): a
    subagent on a cheaper tier produces fewer output tokens per turn at a much
    faster rate, which would otherwise pull the average down and overstate the
    main-Opus runway. The ``main_turn_*`` counters update only when
    ``is_main`` is true.

    Uncosted turns (arch F1): cost stays ``0.0`` and the lane's token totals
    update (in the caller), but ``total_cost_usd`` is NOT bumped and
    ``uncosted_turns`` is — so the dashboard can render "partial cost coverage"
    rather than treating an unknown tier as free.
    """
    recent = (state.recent_events + (cost_event,))[-RECENT_EVENTS_CAP:]
    new_total = state.total_cost_usd if uncosted else state.total_cost_usd + cost
    new_uncosted = state.uncosted_turns + (1 if uncosted else 0)
    new_main_turns = state.main_turns_seen + (1 if is_main else 0)
    new_main_output = state.main_turn_output_tokens + (output_tokens if is_main else 0)
    return replace(
        state,
        total_cost_usd=new_total,
        recent_events=recent,
        main_turns_seen=new_main_turns,
        main_turn_output_tokens=new_main_output,
        uncosted_turns=new_uncosted,
    )


def _runway_status(fill_pct: float, amber: float, red: float) -> str:
    """Classify a fill-fraction into the runway status enum."""
    fraction = fill_pct / 100.0
    if fraction >= red:
        return RUNWAY_RED
    if fraction >= amber:
        return RUNWAY_AMBER
    return RUNWAY_OK


def _estimate_turns_remaining(state: LiveState, current: int, window: int) -> int | None:
    """Estimate remaining turns from the main lane's rolling output-tokens average.

    Uses ONLY the main lane's turns (arch F2): mixing a fast Haiku subagent's
    rate into the average would overstate the main-Opus runway by pulling avg
    output-tokens-per-turn down.

    Returns ``None`` when no priced main turn has landed yet — the dashboard
    renders this honest absence rather than fabricating a number from a
    denominator of zero (the C4 honest-absence pattern, ADR-0020).
    """
    if state.main_turns_seen <= 0 or window <= 0:
        return None
    avg = state.main_turn_output_tokens / state.main_turns_seen
    if avg <= 0:
        return None
    remaining = max(window - current, 0)
    return int(remaining // avg)
