"""Render the Telemetry Layer B dashboard (ADR-0020) — transport / IO layer.

The north-star Layer B surface: a single self-contained HTML infographic,
generated locally at read-time, that makes the already-captured A1/A2/A3
telemetry visible. This module is **render, not measurement** — it reads the
stored Layer-A outputs through the *read-side* assembly functions and never
forks a second computation path:

* **A1 cost** — ``analyze_cost.load_cost_rows`` -> ``cost.build_cost_report``.
* **A2 failures** — ``analyze_failures.load_failure_signals`` -> ``failures.rank_failures``
  (the full stored corpus, the CLI's post-run report shape).
* **A3 value** — ``analyze_value.assemble_value_inputs`` (the shared read-only A3
  assembler), which yields the same ``LeverageResult`` / ``DivergenceResult``
  objects the A3 CLI prints.

It **never** calls ``analyze_cost()`` / ``analyze_failures()`` / ``init_db()`` —
those mutate the database (spec R7/R8/C1). The database is opened **read-only**
(``file:...?mode=ro``); a missing telemetry table (fresh clone / analyzers never
run) is caught and mapped to the honest *analyzer-not-yet-run* absence state,
never a crash or a fabricated zero. The pure formatting / escaping / HTML lives
in ``src/telemetry/dashboard.py`` (the coverage-counted layer); this module owns
only the IO: open read-only, assemble, write to a temp file, open the browser,
print an ASCII summary.

The artifact is written to the OS temp dir (developer decision #6), so personal
cost/fee figures never enter the repo tree. The ntfy topic slug is never read,
imported, printed, or interpolated here (spec C2) — this generator imports no
``notify`` module and reads no environment.

Usage:
    python scripts/telemetry/dashboard.py
    python scripts/telemetry/dashboard.py --no-open
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
import webbrowser
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.telemetry.analyze_cost import load_cost_rows  # noqa: E402
from scripts.telemetry.analyze_failures import load_failure_signals  # noqa: E402
from scripts.telemetry.analyze_value import OTEL_EXPORT_PATH, assemble_value_inputs  # noqa: E402
from src.telemetry.cost import CostReport, build_cost_report  # noqa: E402
from src.telemetry.dashboard import (  # noqa: E402
    STATE_DATA,
    STATE_NOT_RUN,
    DashboardData,
    render_console_summary,
    render_dashboard_html,
)
from src.telemetry.drift import detect_config_drift  # noqa: E402
from src.telemetry.failures import rank_failures  # noqa: E402
from src.telemetry.pricing import PricingTable, load_pricing  # noqa: E402
from src.telemetry.value import load_subscription_fee  # noqa: E402
from src.telemetry.weekly import WeeklyTrends, aggregate_by_week  # noqa: E402

DB_PATH = _REPO_ROOT / "metrics" / "evaluation.db"
#: Conventional dashboard filename (also the defensive .gitignore entry).
DASHBOARD_FILENAME = "telemetry_dashboard.html"

#: Watermark keys that mark an analyzer as "has run" (distinguishes a true zero
#: from a not-yet-run panel — spec R3a / qa ADVISORY 7).
_COST_WATERMARK_KEY = "cost_last_analyzed_at"
_FAILURES_WATERMARK_KEY = "failures_last_analyzed_mtime"


def _watermark_present(conn: sqlite3.Connection, key: str) -> bool:
    """Return True iff ``telemetry_run_state`` carries a non-empty value for ``key``.

    Tolerant of a missing table (fresh DB): a ``sqlite3.OperationalError`` means
    the analyzer has never run, so the watermark is absent.
    """
    try:
        row = conn.execute(
            "SELECT value FROM telemetry_run_state WHERE key = ?", (key,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(row and row[0])


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Open ``db_path`` read-only via a ``file:...?mode=ro`` URI.

    Read-only at the driver level (spec R8/C1): the dashboard never writes,
    migrates, or creates tables. ``mode=ro`` raises if the file does not exist —
    callers handle that as the "no database yet" path.

    Consumed by two read-side surfaces in this module: :func:`assemble_dashboard_data`
    (static dashboard) and :func:`load_weekly_trends` (the live dashboard's
    weekly-trends chart panel). The helper stays module-private — external
    callers route through one of the public loaders instead, which keeps the
    read-only DB-open discipline localised here.
    """
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _parse_created_at(raw: str) -> datetime | None:
    """Parse a ``discussions.created_at`` cell into an aware :class:`datetime`.

    The DB carries two historical formats: ``"YYYY-MM-DD HH:MM:SS"`` (space
    separator, no zone — seen in the earliest discussions) and ISO 8601
    with a ``+00:00`` zone (current writer format). ``fromisoformat`` is
    tolerant of both since Python 3.11; assume UTC when no zone is present
    (the framework writes all timestamps in UTC). A malformed cell returns
    ``None`` and the aggregator skips that discussion with a warning.
    """
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def load_drift_inputs(
    conn: sqlite3.Connection,
) -> tuple[list[str], datetime | None, bool]:
    """Load the inputs the drift detector needs from an open read-only conn.

    **arch F1 fold (REV-20260609-060229)**: this helper takes an
    already-open ``sqlite3.Connection`` rather than opening one itself
    (unlike :func:`load_weekly_trends`). The reason is composition: it is
    called from inside :func:`assemble_dashboard_data`'s existing
    ``try:``/``finally:`` connection block, so opening a second connection
    would be wasteful. The "public loader" shape that wraps
    :func:`_connect_readonly` (the dead-helper rule pinned by
    REV-20260607-200447 arch F3) only applies when an EXTERNAL transport
    needs a read-side surface; this helper has no external caller and
    therefore does not need to mirror that shape. A future external
    caller should add a sibling ``load_drift_inputs_from_path(db_path)``
    that wraps this one, rather than reverse-engineering a
    ``_connect_readonly`` call site.

    Returns three values:

    * **distinct model ids** captured in ``discussion_model_tokens`` (sorted
      ascending so the detector's input ordering is deterministic across runs
      — the rule "what ordering is canonical for unknown ids" stays on the
      transport side, mirroring :func:`load_weekly_trends`).
    * **earliest captured ``discussions.created_at``** as a tz-aware
      :class:`datetime`, or ``None`` if the table is empty or the value cannot
      be parsed.
    * **corpus-present** flag — ``True`` iff the discussions table contains
      at least one row. The caller maps this to
      :attr:`DashboardData.config_drift_state` so the renderer can distinguish
      ``no-corpus-yet`` from ``corpus-checked-no-drift``.

    A missing telemetry table (fresh clone / analyzers never run) is the
    not-yet-corpus path: returns ``([], None, False)``. Same defensive shape as
    :func:`assemble_dashboard_data` so the renderer's honest-absence tile fires.

    Args:
        conn: An open read-only sqlite3 connection (caller closes it).

    Returns:
        ``(distinct_model_ids, earliest_discussion_at, corpus_present)``.
    """
    try:
        model_id_rows = conn.execute(
            "SELECT DISTINCT model_id FROM discussion_model_tokens ORDER BY model_id"
        ).fetchall()
    except sqlite3.OperationalError:
        model_id_rows = []
    distinct_model_ids = [row[0] for row in model_id_rows if isinstance(row[0], str)]

    try:
        created_at_row = conn.execute("SELECT MIN(created_at) FROM discussions").fetchone()
    except sqlite3.OperationalError:
        return distinct_model_ids, None, False

    raw_min = created_at_row[0] if created_at_row else None
    if raw_min is None:
        # The ``discussions.created_at`` column is ``NOT NULL`` (per
        # ``scripts/init_db.py``), so ``MIN(created_at) IS NULL`` is reachable
        # only when the table is empty. No row-count tiebreaker is required.
        return distinct_model_ids, None, False

    earliest_at = _parse_created_at(raw_min)
    return distinct_model_ids, earliest_at, True


def load_weekly_trends(db_path: Path, pricing: PricingTable) -> WeeklyTrends:
    """Build a :class:`WeeklyTrends` from the stored cost rows.

    Opens the DB read-only (``?mode=ro`` URI — the same C1 invariant as
    :func:`assemble_dashboard_data`) and JOINs ``discussion_model_tokens``
    with ``discussions.created_at`` to feed
    :func:`~src.telemetry.weekly.aggregate_by_week`. A missing telemetry
    table (fresh clone / analyzer never run) is mapped to an empty
    :class:`WeeklyTrends`, which the renderer turns into the honest
    not-yet-run absence tile.

    Public read-side surface so the live dashboard's transport layer
    (``scripts/telemetry/dashboard_server.py``) does NOT need to reach into
    :func:`_connect_readonly` directly — the read-only DB-open discipline
    stays localised in this module alongside :func:`assemble_dashboard_data`.
    Adding a second consumer of ``_connect_readonly`` outside this module
    would cross the dead-helper rule pinned by
    ``test_server_uses_a_arch1_public_helpers_not_underscored`` (REV-20260607-200447
    arch F3); routing through this public loader is the option (b) resolution
    (least-complex per Principle #8) for that constraint.

    **Per-poll DB-IO decision (arch H2 from REV-20260608-053032)**: this
    function is called from the ``/fragments/live`` route handler, which
    htmx polls every 3 s. The DB IO is bounded today (~73 rows aggregated
    in well under one millisecond) and intentionally **not** cached — at
    this row count, a cache adds latency-of-measurement and complexity
    without benefit. **Caching trigger** to revisit: introduce a TTL or
    move the loader behind an ``app.state.weekly_loader`` seam when EITHER
    (a) the median row count exceeds ~1,000 (months of captured sessions),
    OR (b) the median aggregation latency exceeds ~10 ms (measured at the
    route handler). The seam itself is intentionally absent now per
    Principle #8 (least-complex first); naming the triggers above is the
    door so a future slice can add it without re-arguing the decision.
    """
    try:
        conn = _connect_readonly(db_path)
    except sqlite3.OperationalError:
        return WeeklyTrends(weeks=())
    try:
        try:
            cost_rows = load_cost_rows(conn)
        except sqlite3.OperationalError:
            return WeeklyTrends(weeks=())
        try:
            created_at_rows = conn.execute(
                "SELECT discussion_id, created_at FROM discussions"
            ).fetchall()
        except sqlite3.OperationalError:
            return WeeklyTrends(weeks=())
        created_at_lookup: dict[str, datetime] = {}
        for discussion_id, raw in created_at_rows:
            if raw is None:
                continue
            parsed = _parse_created_at(raw)
            if parsed is not None:
                created_at_lookup[discussion_id] = parsed
        return aggregate_by_week(cost_rows, created_at_lookup, pricing)
    finally:
        conn.close()


def load_cost_report(db_path: Path, pricing: PricingTable) -> tuple[CostReport, bool]:
    """Load the stored per-tier cost report for the live dashboard's donut panel.

    Opens the DB read-only (``?mode=ro`` — the same C1 invariant as
    :func:`assemble_dashboard_data`), reads the stored A1 cost rows, and
    returns ``(report, has_run)``.

    **Why a tuple here when** :func:`load_weekly_trends` **returns a bare**
    :class:`~src.telemetry.weekly.WeeklyTrends`: the donut renderer must
    distinguish *analyzer ran with zero rows* (true-zero data tile) from
    *analyzer never ran* (absence tile pointing at the pipeline), and
    :class:`~src.telemetry.cost.CostReport` carries no has-run bit — the
    distinction lives in the ``telemetry_run_state`` watermark. The weekly
    case self-signals via emptiness (both states render the same absence
    tile), so it does not need the extra bit. A future loader should pick
    its shape from this rationale, not by normalising the two signatures
    (SPEC-20260610-015114 arch F1).

    **Keep in lockstep**: the ``has_run`` computation (rows present OR cost
    watermark present) mirrors :func:`assemble_dashboard_data`'s
    ``cost_state`` logic above — change both together. Deliberately NOT
    extracted into a shared helper at N=2 call sites (SPEC arch F2,
    Principle #8).

    The four-state contract (SPEC-20260610-015114 AC10):

    * DB file absent (``mode=ro`` raises at connect) -> ``(empty, False)``.
    * Telemetry table missing (analyzer never ran) -> ``(empty, False)``.
    * Watermark present, zero rows -> ``(empty, True)`` (true zero).
    * Rows present -> ``(populated, True)``.

    The per-poll DB-IO decision + caching triggers recorded in
    :func:`load_weekly_trends`'s docstring apply to this loader too (same
    3 s ``/fragments/live`` poll, same bounded row scale).
    """
    try:
        conn = _connect_readonly(db_path)
    except sqlite3.OperationalError:
        return build_cost_report([], pricing), False
    try:
        try:
            cost_rows = load_cost_rows(conn)
        except sqlite3.OperationalError:
            return build_cost_report([], pricing), False
        report = build_cost_report(cost_rows, pricing)
        has_run = bool(cost_rows) or _watermark_present(conn, _COST_WATERMARK_KEY)
        return report, has_run
    finally:
        conn.close()


def assemble_dashboard_data(
    db_path: Path = DB_PATH,
    *,
    pricing: PricingTable | None = None,
    subscription_path: Path | None = None,
    otel_path: Path = OTEL_EXPORT_PATH,
    project_root: Path | None = None,
    generated_label: str = "",
) -> DashboardData:
    """Assemble the render-ready :class:`DashboardData` from the read-side outputs.

    Read-only and side-effect-free with respect to the database: it opens
    ``db_path`` with ``?mode=ro``, reads the stored Layer-A outputs, and returns
    the assembled dataclasses. It performs **no** DB writes and never calls
    ``init_db`` / ``analyze_cost`` / ``analyze_failures`` (spec R7, acceptance
    "read-side-only"). A missing telemetry table is mapped to the analyzer-not-
    yet-run absence state, not a crash.

    Args:
        db_path: SQLite database path (opened read-only).
        pricing: Resolved pricing table (defaults to loading the YAML).
        subscription_path: Subscription-fee config path (A3 leverage).
        otel_path: OTel export path (A3 pricing cross-check).
        project_root: Project whose transcripts feed the A3 attribution baseline.
        generated_label: Human label for when the page was generated (transport
            owns the clock so this module stays render-deterministic).

    Returns:
        A :class:`DashboardData` ready for :func:`render_dashboard_html`.
    """
    pricing = pricing or load_pricing()
    conn = _connect_readonly(db_path)
    try:
        # A1 cost — read stored breakdown rows; a missing table => not-yet-run.
        try:
            cost_rows = load_cost_rows(conn)
        except sqlite3.OperationalError:
            cost_rows = []
        cost_report = build_cost_report(cost_rows, pricing)
        # Keep in lockstep with load_cost_report's has_run computation (the
        # live donut loader mirrors this exact rows-or-watermark logic;
        # SPEC-20260610-015114 arch F2) — change both together.
        cost_has_run = bool(cost_rows) or _watermark_present(conn, _COST_WATERMARK_KEY)
        cost_state = STATE_DATA if cost_has_run else STATE_NOT_RUN

        # A2 failures — full stored corpus; empty + watermark = true zero (data
        # tile), empty + no watermark = not-yet-run (absence tile).
        try:
            signals = load_failure_signals(conn)
        except sqlite3.OperationalError:
            signals = []
        ranked = rank_failures(signals, pricing)
        failures_has_run = bool(signals) or _watermark_present(conn, _FAILURES_WATERMARK_KEY)
        failures_state = STATE_DATA if failures_has_run else STATE_NOT_RUN

        # A3 value — the shared read-only assembler (reuses the A1 report so the
        # cost figure is a single source of truth; never re-parses for cost).
        # When cost is not-yet-run the report is an honest empty one (total $0.00,
        # coverage 0%). leverage() would call that finite-zero "configured" if a
        # fee is set — so the RENDER layer keys the leverage absence on cost_state
        # (B1 review fix), not on the fee alone: a not-measured numerator renders
        # the honest "run analyze_cost.py" absence tile, never a fabricated 0.00x.
        value = assemble_value_inputs(
            conn,
            pricing=pricing,
            project_root=project_root,
            since=None,
            subscription_path=subscription_path,
            otel_path=otel_path,
            a1_report=cost_report,
        )

        # Phase 3 Unit 2 — config-drift rows. Reads two thin queries from the
        # same read-only connection (no second open, no second loader) and
        # feeds the pure detector. The subscription fee is read separately
        # from disk because A3's ``assemble_value_inputs`` already accepts
        # the path but only returns the leverage/attribution/pricing shapes
        # — keeping the fee load right here means the drift detector does not
        # have to dig into the A3 inputs dict.
        distinct_model_ids, earliest_at, corpus_present = load_drift_inputs(conn)
        # arch F2 fold (REV-20260609-060229): the subscription YAML is parsed
        # TWICE in this assemble pass — once inside ``assemble_value_inputs``
        # for the leverage result, and once here for the drift detector.
        # Acceptable at N=2 (Rule of Two): the inline cost is a single small
        # YAML read, and the alternative (returning the parsed fee from
        # ``assemble_value_inputs``) would broaden the A3 inputs dict shape
        # for one extra consumer. **Rule-of-Three trigger**: when a THIRD
        # consumer of ``SubscriptionFee`` lands in this assemble pass,
        # refactor: either return the fee from ``assemble_value_inputs`` or
        # parse it ONCE at the top of ``assemble_dashboard_data`` and thread
        # the result through both call sites.
        fee = load_subscription_fee(subscription_path)
        config_drift = tuple(
            detect_config_drift(
                model_ids=distinct_model_ids,
                pricing=pricing,
                fee=fee,
                earliest_discussion_at=earliest_at,
            )
        )
        config_drift_state = STATE_DATA if corpus_present else STATE_NOT_RUN
    finally:
        conn.close()

    return DashboardData(
        cost_report=cost_report,
        cost_state=cost_state,
        failures=ranked,
        failures_state=failures_state,
        leverage=value["leverage"],
        attribution=value["attribution"],
        pricing_check=value["pricing"],
        config_drift=config_drift,
        config_drift_state=config_drift_state,
        generated_label=generated_label,
    )


def main() -> None:
    """CLI entry point: generate the HTML, open it, and print the ASCII summary."""
    parser = argparse.ArgumentParser(
        description="Render the Telemetry Layer B dashboard (static HTML, read-only)."
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Generate the file without opening a browser."
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"No telemetry database at {DB_PATH}. Run scripts/init_db.py first.")
        return

    label = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    try:
        data = assemble_dashboard_data(DB_PATH, generated_label=label)
    except sqlite3.OperationalError as exc:
        # Path only in the message; never any environment/secret (spec C2/C5).
        print(f"Could not open the telemetry database read-only at {DB_PATH}: {exc}")
        return

    out_path = Path(tempfile.gettempdir()) / DASHBOARD_FILENAME
    out_path.write_text(render_dashboard_html(data), encoding="utf-8")

    for line in render_console_summary(data, output_path=str(out_path)):
        print(line)

    if not args.no_open:
        webbrowser.open(out_path.as_uri())


if __name__ == "__main__":
    main()
