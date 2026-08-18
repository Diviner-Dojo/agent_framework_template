"""Print a text efficiency + yield-coverage report over captured protocol telemetry.

Reads ``metrics/evaluation.db`` and produces sliced views of protocol yield and
token spend. The primary efficiency ratio is ``blocking findings per 1K output
tokens`` — high values mean a workflow is producing more independently-found
blocking issues per unit of cost.

THE CENTRAL DISTINCTION THIS REPORT EXISTS TO MAKE
--------------------------------------------------
A bucket with no recorded blocking findings is in one of two states, and they are
NOT the same thing:

* **measured, caught nothing** — a protocol ran, yield was recorded, the count was 0.
* **never measured** — no ``protocol_yield`` row was ever written for that bucket.

Rendering both as ``0`` is how a live gate gets argued out of existence from
silence. Every numeric yield cell in this report is therefore rendered as
``NO_DATA`` (``-``) when its bucket has zero measured runs, and every table
carries an explicit ``measured`` column (``measured/total``). Absence of evidence
is reported as absence of evidence — never as evidence of absence.

Cost in dollars is intentionally NOT computed. The aggregated columns mix turns
across multiple model tiers (facilitator at opus, specialists mostly at sonnet,
etc.), so any single per-token rate would fabricate precision the data doesn't
have. ``config/model_pricing.yaml`` is the reference table for manual cost
estimation when a single-tier discussion is being analyzed.

EXIT CODES (a contract ``.claude/commands/retro.md`` and ``knowledge-health.md`` quote)
--------------------------------------------------------------------------------------
* ``0`` — the report rendered against a readable database.
* ``1`` — BROKEN INSTRUMENT: the database is absent or unreadable. Nothing was
  measured, so nothing may be concluded. This code exists because the alternative
  is the module's own thesis failing one level up: an agent that reads exit 0,
  finds no coverage table, and writes "no yield data" has rendered *absence of the
  instrument* as *absence of findings* — the exact collapse this report forbids.
* ``2`` — a malformed ``--since``.

A missing database is therefore NEVER a quiet success. ``main`` returns 1 before it
prints anything that could be mistaken for a report.

Usage:
    python scripts/efficiency_report.py
    python scripts/efficiency_report.py --since 2026-05-01
    python scripts/efficiency_report.py --top 20
    python scripts/efficiency_report.py --coverage-only
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

#: Rendered in any numeric yield cell whose bucket has ZERO measured runs.
#: Deliberately not "0": see the module docstring.
NO_DATA = "-"

#: Fallback list, used only if ``scripts/record_yield.py`` cannot be loaded.
#: Kept in sync via :func:`valid_protocol_types`, which prefers the writer's own
#: list so the reader cannot silently drift behind a newly-added protocol type.
_FALLBACK_PROTOCOL_TYPES = ("review", "checkpoint", "education_gate", "quality_gate", "retro")

#: Columns a slice may group by. Only names from this literal tuple are ever
#: interpolated into SQL (see security_baseline: no caller value reaches a statement).
GROUPABLE_COLUMNS = ("command_type", "collaboration_mode", "risk_level")

#: Below this share of findings marked false-positive, the recording discipline is
#: implausible rather than impressive — a flattering number here silently corrupts
#: every downstream precision metric.
FP_PLAUSIBILITY_FLOOR = 0.01
#: Minimum findings before the false-positive plausibility check is meaningful.
MIN_FINDINGS_FOR_FP_CHECK = 50

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T].*)?$")


def valid_protocol_types() -> tuple[str, ...]:
    """Return the protocol types the writer accepts, preferring the writer's own list.

    Loads ``VALID_PROTOCOL_TYPES`` from ``scripts/record_yield.py`` by file path so it
    resolves whether this module is run as a script or imported by a test. Falls back to
    :data:`_FALLBACK_PROTOCOL_TYPES` when the writer cannot be loaded.

    A reader that hardcodes its own enum reports a newly-added protocol type as
    "no rows" forever — which is precisely the absence-of-evidence failure this
    module exists to prevent.
    """
    target = PROJECT_ROOT / "scripts" / "record_yield.py"
    if not target.exists():
        return _FALLBACK_PROTOCOL_TYPES
    try:
        spec = importlib.util.spec_from_file_location("_record_yield_for_report", target)
        if spec is None or spec.loader is None:
            return _FALLBACK_PROTOCOL_TYPES
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        types = tuple(module.VALID_PROTOCOL_TYPES)
    except (ImportError, AttributeError, OSError, TypeError):
        return _FALLBACK_PROTOCOL_TYPES
    return types or _FALLBACK_PROTOCOL_TYPES


@dataclass
class BucketYield:
    """Yield + spend for one bucket, keeping "never measured" distinct from "zero"."""

    bucket: str
    runs: int
    measured_runs: int
    blocking: int
    advisory: int
    false_positive: int
    turns: int
    token_runs: int
    tokens_in: int
    tokens_out: int
    cache_tokens: int
    #: Output tokens from runs that were BOTH measured and token-instrumented — the
    #: only honest denominator for a per-token yield ratio.
    measured_tokens_out: int

    @property
    def unmeasured_runs(self) -> int:
        """Runs in this bucket with no ``protocol_yield`` row at all."""
        return self.runs - self.measured_runs

    @property
    def is_measured(self) -> bool:
        """True when at least one run in this bucket recorded yield."""
        return self.measured_runs > 0

    @property
    def coverage(self) -> float:
        """Share of runs in this bucket that recorded yield (0.0 when none)."""
        return self.measured_runs / self.runs if self.runs else 0.0

    @property
    def blocking_per_1k_out(self) -> float | None:
        """Blocking findings per 1K output tokens, or None when not computable.

        Returns None when the bucket was never measured or has no token-instrumented
        measured run — a ratio over an unmeasured denominator is fiction.
        """
        if not self.is_measured or self.measured_tokens_out <= 0:
            return None
        return round(self.blocking * 1000.0 / self.measured_tokens_out, 3)

    def yield_cell(self, value: int) -> str:
        """Render a yield count, or :data:`NO_DATA` when the bucket was never measured."""
        return str(value) if self.is_measured else NO_DATA


@dataclass
class ProtocolCoverage:
    """Recorded yield for one protocol type, including types with zero rows ever."""

    protocol_type: str
    rows: int
    discussions: int
    blocking: int
    advisory: int
    false_positive: int
    turns: int

    @property
    def ever_measured(self) -> bool:
        """True when this protocol type has at least one recorded row."""
        return self.rows > 0


@dataclass
class ReportData:
    """Everything the renderer needs, already separated into measured vs. unmeasured."""

    total_discussions: int
    measured_discussions: int
    token_discussions: int
    total_yield_rows: int
    slices: dict[str, list[BucketYield]]
    protocol_coverage: list[ProtocolCoverage]
    top_discussions: list[tuple[object, ...]]
    #: False on a pre-ADR-0013 schema with no token columns. Token sections degrade;
    #: the yield-coverage sections — the point of the report — remain fully available.
    token_telemetry_available: bool = True

    @property
    def unmeasured_discussions(self) -> int:
        """Discussions with no ``protocol_yield`` row at all."""
        return self.total_discussions - self.measured_discussions

    @property
    def yield_coverage(self) -> float:
        """Share of discussions that recorded any yield."""
        return (
            self.measured_discussions / self.total_discussions if self.total_discussions else 0.0
        )

    @property
    def total_findings(self) -> int:
        """All recorded findings across every protocol type."""
        return sum(p.blocking + p.advisory + p.false_positive for p in self.protocol_coverage)

    @property
    def false_positive_rate(self) -> float | None:
        """Share of recorded findings marked false-positive, or None with no findings."""
        total = self.total_findings
        return sum(p.false_positive for p in self.protocol_coverage) / total if total else None


def _is_numeric_cell(cell: str) -> bool:
    """True for a numeric cell or the :data:`NO_DATA` marker.

    NO_DATA counts as numeric for layout purposes so it right-justifies into the same
    column as the numbers it stands in for — a '-' drifting to the left margin reads as
    a formatting glitch rather than as the deliberate 'never measured' marker it is.
    """
    if cell == NO_DATA:
        return True
    try:
        float(cell)
    except (ValueError, TypeError):
        return False
    return True


def _format_table(rows: Sequence[Sequence[object]], headers: Sequence[str]) -> str:
    """Render rows as a fixed-width text table. Right-justify numeric cells."""
    cols = len(headers)
    str_rows: list[list[str]] = [list(headers)]
    for row in rows:
        str_rows.append(["" if v is None else str(v) for v in row])
    widths = [max(len(r[c]) for r in str_rows) for c in range(cols)]
    lines: list[str] = []
    for i, row in enumerate(str_rows):
        cells = []
        for c, cell in enumerate(row):
            if _is_numeric_cell(cell):
                cells.append(cell.rjust(widths[c]))
            else:
                cells.append(cell.ljust(widths[c]))
        lines.append("  ".join(cells))
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _validate_since(since: str | None) -> str | None:
    """Return ``since`` unchanged, or raise ValueError if it is not a YYYY-MM-DD date.

    ``since`` is bound as a SQL parameter (never interpolated), so this is a usability
    guard rather than an injection guard: a malformed date would otherwise silently
    filter out every row and be misread as "no data".
    """
    if since is None:
        return None
    if not _DATE_RE.match(since):
        raise ValueError(f"--since must be YYYY-MM-DD (got {since!r})")
    return since


#: Token-telemetry columns added to ``discussions`` by the ADR-0013 migration. A derived
#: project whose DB predates it has none of them.
TOKEN_COLUMNS = ("total_tokens_in", "total_tokens_out", "total_cache_tokens")


def _discussion_columns(conn: sqlite3.Connection) -> set[str]:
    """Return the column names actually present on ``discussions``."""
    return {row[1] for row in conn.execute("PRAGMA table_info(discussions)")}


def _tok(cols: set[str], name: str) -> str:
    """Return ``d.<name>`` if the column exists, else the literal ``NULL``.

    This module is CORE: it propagates to derived projects whose ``evaluation.db`` may
    predate the ADR-0013 token migration. Naming a missing column would raise
    OperationalError and make the WHOLE report unreadable — including the yield-coverage
    section, which needs no token data at all. Degrading the token columns to NULL keeps
    the measured/unmeasured answer available in exactly the projects that have the most
    recorded yield and the least token instrumentation.

    ``name`` is only ever a literal from :data:`TOKEN_COLUMNS`; no caller value is
    interpolated (see security_baseline).
    """
    if name not in TOKEN_COLUMNS:
        raise ValueError(f"not a token column: {name!r}")
    return f"d.{name}" if name in cols else "NULL"


_PY_AGG = """
    py_agg AS (
        SELECT discussion_id,
               COUNT(*)                        AS rows_n,
               SUM(findings_blocking)          AS blocking,
               SUM(findings_advisory)          AS advisory,
               SUM(findings_false_positive)    AS false_positive,
               SUM(agent_turns_used)           AS turns
        FROM protocol_yield
        GROUP BY discussion_id
    )
"""


def _slice_yields(
    conn: sqlite3.Connection, group_col: str, since: str | None
) -> list[BucketYield]:
    """Aggregate yield + spend per bucket of ``group_col``.

    ``protocol_yield`` is pre-aggregated in a CTE so the LEFT JOIN is 1:1 (same fix as
    ``v_token_efficiency`` — ADR-0013). Unlike the previous version of this report,
    discussions WITHOUT token telemetry are included: filtering them out discarded the
    large majority of recorded yield rows and made measured protocols look unmeasured.
    """
    if group_col not in GROUPABLE_COLUMNS:  # literal-whitelist guard before interpolation
        raise ValueError(f"ungroupable column: {group_col!r}")
    cols = _discussion_columns(conn)
    t_in, t_out, t_cache = (_tok(cols, c) for c in TOKEN_COLUMNS)
    sql = f"""
        WITH {_PY_AGG}
        SELECT
            COALESCE(d.{group_col}, '(none)')                              AS bucket,
            COUNT(*)                                                       AS runs,
            SUM(CASE WHEN py.rows_n IS NULL THEN 0 ELSE 1 END)             AS measured_runs,
            SUM(COALESCE(py.blocking, 0))                                  AS blocking,
            SUM(COALESCE(py.advisory, 0))                                  AS advisory,
            SUM(COALESCE(py.false_positive, 0))                            AS false_positive,
            SUM(COALESCE(py.turns, 0))                                     AS turns,
            SUM(CASE WHEN {t_out} IS NULL THEN 0 ELSE 1 END)               AS token_runs,
            SUM(COALESCE({t_in}, 0))                                       AS tokens_in,
            SUM(COALESCE({t_out}, 0))                                      AS tokens_out,
            SUM(COALESCE({t_cache}, 0))                                    AS cache_tokens,
            SUM(CASE WHEN py.rows_n IS NOT NULL AND {t_out} IS NOT NULL
                     THEN {t_out} ELSE 0 END)                              AS measured_tokens_out
        FROM discussions d
        LEFT JOIN py_agg py ON py.discussion_id = d.discussion_id
        WHERE (:since IS NULL OR d.created_at >= :since)
        GROUP BY bucket
    """
    rows = conn.execute(sql, {"since": since}).fetchall()
    buckets = [BucketYield(*row) for row in rows]
    # Rank by measured yield, then by coverage: an unmeasured bucket must never sort as
    # if it were a zero-yield bucket, so it sinks on coverage rather than on a fake 0.
    buckets.sort(key=lambda b: (b.blocking_per_1k_out or -1.0, b.coverage), reverse=True)
    return buckets


def _protocol_coverage(conn: sqlite3.Connection, since: str | None) -> list[ProtocolCoverage]:
    """Return one row per VALID protocol type, including those with zero rows ever.

    Enumerating the writer's full enum (rather than only the types present in the
    table) is what makes "this protocol has never been measured" visible at all.
    """
    sql = """
        SELECT py.protocol_type,
               COUNT(*)                             AS rows_n,
               COUNT(DISTINCT py.discussion_id)     AS discussions,
               SUM(py.findings_blocking)            AS blocking,
               SUM(py.findings_advisory)            AS advisory,
               SUM(py.findings_false_positive)      AS false_positive,
               SUM(py.agent_turns_used)             AS turns
        FROM protocol_yield py
        JOIN discussions d ON d.discussion_id = py.discussion_id
        WHERE (:since IS NULL OR d.created_at >= :since)
        GROUP BY py.protocol_type
    """
    seen = {row[0]: row for row in conn.execute(sql, {"since": since}).fetchall()}
    coverage: list[ProtocolCoverage] = []
    for ptype in valid_protocol_types():
        row = seen.pop(ptype, None)
        if row is None:
            coverage.append(ProtocolCoverage(ptype, 0, 0, 0, 0, 0, 0))
        else:
            coverage.append(ProtocolCoverage(ptype, *row[1:]))
    # Any type present in the data but absent from the writer's enum is itself a signal.
    for ptype, row in seen.items():
        coverage.append(ProtocolCoverage(f"{ptype} (not in writer enum)", *row[1:]))
    return coverage


def _top_discussions(
    conn: sqlite3.Connection, top: int, since: str | None
) -> list[tuple[object, ...]]:
    """Return the N most token-expensive discussions, each flagged measured or not.

    Returns an empty list on a pre-ADR-0013 schema: without token telemetry there is no
    "most expensive" to rank. That is a missing SECTION, not a missing report — the
    yield-coverage sections above it do not depend on token columns.
    """
    cols = _discussion_columns(conn)
    if "total_tokens_out" not in cols:
        return []
    t_out, t_cache = _tok(cols, "total_tokens_out"), _tok(cols, "total_cache_tokens")
    sql = f"""
        WITH py_agg AS (
            SELECT discussion_id, COUNT(*) AS rows_n, SUM(findings_blocking) AS blocking
            FROM protocol_yield GROUP BY discussion_id
        )
        SELECT
            substr(d.discussion_id, 1, 36)  AS discussion_id,
            d.command_type                  AS cmd,
            d.collaboration_mode            AS mode,
            d.risk_level                    AS risk,
            {t_out}                         AS out_tokens,
            {t_cache}                       AS cache,
            CASE WHEN py.rows_n IS NULL THEN 'no' ELSE 'yes' END AS measured,
            CASE WHEN py.rows_n IS NULL THEN :nodata
                 ELSE CAST(COALESCE(py.blocking, 0) AS TEXT) END AS blocking
        FROM discussions d
        LEFT JOIN py_agg py ON py.discussion_id = d.discussion_id
        WHERE {t_out} IS NOT NULL
          AND (:since IS NULL OR d.created_at >= :since)
        ORDER BY {t_out} DESC
        LIMIT :top
    """
    params = {"since": since, "top": max(0, int(top)), "nodata": NO_DATA}
    return [tuple(row) for row in conn.execute(sql, params).fetchall()]


def collect(db_path: Path = DB_PATH, since: str | None = None, top: int = 10) -> ReportData:
    """Gather every figure the report renders. Read-only on the database."""
    since = _validate_since(since)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cols = _discussion_columns(conn)
        t_out = _tok(cols, "total_tokens_out")
        totals = conn.execute(
            f"""
            WITH {_PY_AGG}
            SELECT COUNT(*),
                   SUM(CASE WHEN py.rows_n IS NULL THEN 0 ELSE 1 END),
                   SUM(CASE WHEN {t_out} IS NULL THEN 0 ELSE 1 END),
                   SUM(COALESCE(py.rows_n, 0))
            FROM discussions d
            LEFT JOIN py_agg py ON py.discussion_id = d.discussion_id
            WHERE (:since IS NULL OR d.created_at >= :since)
            """,
            {"since": since},
        ).fetchone()
        slices = {col: _slice_yields(conn, col, since) for col in GROUPABLE_COLUMNS}
        return ReportData(
            total_discussions=totals[0] or 0,
            measured_discussions=totals[1] or 0,
            token_discussions=totals[2] or 0,
            total_yield_rows=totals[3] or 0,
            slices=slices,
            protocol_coverage=_protocol_coverage(conn, since),
            top_discussions=_top_discussions(conn, top, since),
            token_telemetry_available="total_tokens_out" in cols,
        )
    finally:
        conn.close()


GUARD_TEXT = """\
HOW TO READ A BLANK CELL
  '-' means NEVER MEASURED: no protocol_yield row exists for that bucket.
  '0' means MEASURED AND CAUGHT NOTHING: a protocol ran and recorded zero findings.
  These look identical if you collapse them, and they are not the same.
  A gate with no recorded yield may be worthless, or may simply never have been
  measured. NEVER propose deleting or relaxing a gate on absence of evidence --
  instrument it first, then argue from what it records."""


def _render_slice(title: str, buckets: Sequence[BucketYield]) -> str:
    """Render one grouped slice with explicit measured/unmeasured columns."""
    headers = [
        "bucket",
        "runs",
        "measured",
        "blocking",
        "advisory",
        "false_pos",
        "avg_out",
        "blocking_per_1k_out",
    ]
    rows = []
    for b in buckets:
        avg_out = round(b.tokens_out / b.token_runs) if b.token_runs else NO_DATA
        ratio = b.blocking_per_1k_out
        rows.append(
            [
                b.bucket,
                b.runs,
                f"{b.measured_runs}/{b.runs}",
                b.yield_cell(b.blocking),
                b.yield_cell(b.advisory),
                b.yield_cell(b.false_positive),
                avg_out,
                NO_DATA if ratio is None else ratio,
            ]
        )
    return f"## {title}\n{_format_table(rows, headers)}"


def _render_coverage(data: ReportData) -> str:
    """Render the headline coverage section — the part that answers 'was this measured?'."""
    headers = [
        "protocol_type",
        "rows",
        "discussions",
        "blocking",
        "advisory",
        "false_pos",
        "turns",
    ]
    rows = []
    never: list[str] = []
    for p in data.protocol_coverage:
        if p.ever_measured:
            rows.append(
                [
                    p.protocol_type,
                    p.rows,
                    p.discussions,
                    p.blocking,
                    p.advisory,
                    p.false_positive,
                    p.turns,
                ]
            )
        else:
            rows.append([p.protocol_type, 0, 0, NO_DATA, NO_DATA, NO_DATA, NO_DATA])
            never.append(p.protocol_type)

    out = [f"## Yield coverage by protocol type\n{_format_table(rows, headers)}"]
    if never:
        out.append(
            "NEVER MEASURED: "
            + ", ".join(never)
            + "\n  These protocols have ZERO recorded yield rows. That is a statement about the\n"
            "  INSTRUMENT, not about the protocol's value. Their worth is currently unknown --\n"
            "  wire record_yield.py into them before drawing any conclusion about them."
        )
    return "\n\n".join(out)


def _render_integrity(data: ReportData) -> str:
    """Render recording-discipline figures, including the false-positive honesty check."""
    lines = [
        "## Recording integrity",
        f"discussions:            {data.total_discussions}",
        f"  with recorded yield:  {data.measured_discussions} ({data.yield_coverage:.0%})",
        f"  never measured:       {data.unmeasured_discussions}",
        f"  with token telemetry: {data.token_discussions}",
        f"protocol_yield rows:    {data.total_yield_rows}",
    ]
    if not data.token_telemetry_available:
        lines.append(
            "\nDEGRADED: this database predates the ADR-0013 token migration, so the\n"
            "  discussions table has no token columns. Every token/cost figure is omitted --\n"
            "  omitted, NOT zero. Yield coverage above is unaffected and fully readable.\n"
            "  Run scripts/init_db.py to add the columns."
        )
    fp_rate = data.false_positive_rate
    total = data.total_findings
    if fp_rate is None:
        lines.append("false-positive rate:    " + NO_DATA + " (no findings recorded)")
    else:
        lines.append(f"false-positive rate:    {fp_rate:.2%} of {total} recorded findings")
    if (
        fp_rate is not None
        and total >= MIN_FINDINGS_FOR_FP_CHECK
        and fp_rate < FP_PLAUSIBILITY_FLOOR
    ):
        lines.append(
            "\nHONESTY WARNING: the recorded false-positive rate is implausibly low.\n"
            "  This almost certainly means false positives are not being recorded, not that\n"
            "  the panel is nearly perfect. Record them. A flattering number here silently\n"
            "  corrupts every downstream precision, calibration, and yield metric that reads\n"
            "  this table -- and it corrupts them in the direction that flatters the gate."
        )
    return "\n".join(lines)


def broken_instrument_message(db_path: Path) -> str:
    """The single wording used whenever the database cannot be read at all.

    Shared by :func:`render_report` and :func:`main` so the text a human sees and the
    text the exit code stands for can never drift apart. It states the conclusion the
    reader must NOT draw, because the failure mode here is not a crash — it is a
    plausible-looking empty report being written up as "the gates caught nothing".
    """
    return (
        f"BROKEN INSTRUMENT: no readable database at {db_path}.\n"
        "  This is the ABSENCE OF THE INSTRUMENT, not an absence of findings.\n"
        "  Nothing was measured, so nothing may be concluded about any protocol's value.\n"
        "  Do NOT record 'no yield data', 'zero blocking findings', or any relaxation or\n"
        "  deletion recommendation from this run. Run scripts/init_db.py, then re-run."
    )


def render_report(
    since: str | None = None,
    top: int = 10,
    coverage_only: bool = False,
    db_path: Path | None = None,
) -> str:
    """Build the full report as a single text string.

    ``db_path`` defaults to None rather than to :data:`DB_PATH` so the module global is
    resolved at CALL time — a ``= DB_PATH`` default would bind at def time and silently
    ignore a monkeypatched destination.
    """
    db_path = db_path if db_path is not None else DB_PATH
    if not db_path.exists():
        return broken_instrument_message(db_path)
    data = collect(db_path, since=since, top=top)

    header = "# Efficiency + Yield Coverage Report"
    if since:
        header += f" (since {since})"

    sections = [_render_coverage(data), _render_integrity(data)]
    if not coverage_only:
        titles = {
            "command_type": "By command_type",
            "collaboration_mode": "By collaboration_mode",
            "risk_level": "By risk_level",
        }
        for col in GROUPABLE_COLUMNS:
            sections.append(_render_slice(titles[col], data.slices[col]))
        top_headers = [
            "discussion_id",
            "cmd",
            "mode",
            "risk",
            "out_tokens",
            "cache",
            "measured",
            "blocking",
        ]
        sections.append(
            f"## Top {top} most expensive discussions (by output tokens)\n"
            f"{_format_table(data.top_discussions, top_headers)}"
        )

    note = (
        "Note: cost in dollars is NOT computed -- token aggregates mix model tiers.\n"
        "See config/model_pricing.yaml for rates if estimating a single-tier discussion."
    )
    return f"{header}\n\n{GUARD_TEXT}\n\n{note}\n\n" + "\n\n".join(sections) + "\n"


def main() -> int:
    """CLI entry point. Returns a process exit code.

    0 = report rendered; 1 = BROKEN INSTRUMENT (database absent or unreadable);
    2 = malformed ``--since``. See the module docstring: the missing-database case
    returns 1 rather than 0 so that "the instrument was not available" can never be
    read off this process as "the protocols produced nothing".
    """
    parser = argparse.ArgumentParser(
        description="Print a protocol yield-coverage and token-efficiency report."
    )
    parser.add_argument(
        "--since", default=None, help="Only include discussions created on/after YYYY-MM-DD."
    )
    parser.add_argument(
        "--top", type=int, default=10, help="How many most-expensive discussions to list."
    )
    parser.add_argument(
        "--coverage-only",
        action="store_true",
        help="Print only the coverage + integrity sections (the measured/unmeasured answer).",
    )
    args = parser.parse_args()
    # Checked HERE, not by sniffing the rendered string for a phrase: the exit code is
    # the contract the command files quote, so it is decided by the filesystem fact, not
    # by prose that a later edit could reword out from under it.
    if not DB_PATH.exists():
        print(broken_instrument_message(DB_PATH))
        return 1
    try:
        print(render_report(since=args.since, top=args.top, coverage_only=args.coverage_only))
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    except sqlite3.Error as exc:
        # Never expose raw DB internals (Always-On invariant).
        print(f"ERROR: efficiency report unavailable — database error ({type(exc).__name__}).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
