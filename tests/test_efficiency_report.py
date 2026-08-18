"""Tests for scripts/efficiency_report.py — the yield-coverage read-out.

The load-bearing property under test is a single distinction:

    "this gate ran and caught nothing"  !=  "this gate was never measured"

Collapsing those two states into a rendered ``0`` is what lets a live gate be argued
out of existence from silence. Every test below either locks that distinction, or
locks a filter/ordering/integrity behaviour that previously erased it.

The final section extends the same distinction one level up, to the INSTRUMENT
itself, and covers BOTH scripts that ``/retro`` and ``/knowledge-health`` wire in
(``efficiency_report.py`` and ``audit_calibration.py``). The two command files
publish an exit-code contract for each; these tests are what make that contract
true rather than merely documented. They live here, alongside the thesis they
defend, rather than in ``tests/test_audit_calibration.py``, which belongs to
another slice — see the section header for the full rationale.

All artifacts are written under ``tmp_path``. Nothing here touches the real
``metrics/evaluation.db``, ``metrics/calibration_log.jsonl``,
``memory/calibration-proposals/``, or writes anywhere into the repository — the
``sandboxed_calibration`` fixture asserts that rather than assuming it.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import audit_calibration as ac  # noqa: E402
import efficiency_report as er  # noqa: E402

_DISCUSSIONS_DDL = """
CREATE TABLE discussions (
    discussion_id      TEXT PRIMARY KEY,
    created_at         DATETIME NOT NULL,
    closed_at          DATETIME,
    risk_level         TEXT NOT NULL CHECK(risk_level IN ('low','medium','high','critical')),
    collaboration_mode TEXT NOT NULL CHECK(collaboration_mode IN (
        'ensemble','yes-and','structured-dialogue','dialectic','adversarial')),
    status             TEXT NOT NULL DEFAULT 'closed',
    agent_count        INTEGER NOT NULL DEFAULT 0,
    command_type       TEXT,
    total_tokens_in    INTEGER,
    total_tokens_out   INTEGER,
    total_cache_tokens INTEGER
)
"""

_YIELD_DDL = """
CREATE TABLE protocol_yield (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id TEXT NOT NULL REFERENCES discussions(discussion_id),
    protocol_type TEXT NOT NULL CHECK(protocol_type IN (
        'review','checkpoint','education_gate','quality_gate','retro')),
    findings_blocking       INTEGER NOT NULL DEFAULT 0,
    findings_advisory       INTEGER NOT NULL DEFAULT 0,
    findings_false_positive INTEGER NOT NULL DEFAULT 0,
    agent_turns_used        INTEGER NOT NULL DEFAULT 0,
    outcome       TEXT NOT NULL,
    timestamp     DATETIME NOT NULL
)
"""


def _make_db(
    path: Path,
    discussions: list[dict[str, object]],
    yields: list[dict[str, object]],
) -> Path:
    """Build a minimal but schema-faithful evaluation.db under tmp_path."""
    conn = sqlite3.connect(str(path))
    conn.executescript(_DISCUSSIONS_DDL + ";" + _YIELD_DDL)
    for d in discussions:
        conn.execute(
            """INSERT INTO discussions (discussion_id, created_at, risk_level,
                   collaboration_mode, command_type, total_tokens_in, total_tokens_out,
                   total_cache_tokens)
               VALUES (:discussion_id, :created_at, :risk_level, :collaboration_mode,
                   :command_type, :total_tokens_in, :total_tokens_out, :total_cache_tokens)""",
            {
                "created_at": "2026-06-01T00:00:00",
                "risk_level": "medium",
                "collaboration_mode": "structured-dialogue",
                "command_type": None,
                "total_tokens_in": None,
                "total_tokens_out": None,
                "total_cache_tokens": None,
                **d,
            },
        )
    for y in yields:
        conn.execute(
            """INSERT INTO protocol_yield (discussion_id, protocol_type, findings_blocking,
                   findings_advisory, findings_false_positive, agent_turns_used, outcome,
                   timestamp)
               VALUES (:discussion_id, :protocol_type, :findings_blocking, :findings_advisory,
                   :findings_false_positive, :agent_turns_used, :outcome, :timestamp)""",
            {
                "protocol_type": "review",
                "findings_blocking": 0,
                "findings_advisory": 0,
                "findings_false_positive": 0,
                "agent_turns_used": 0,
                "outcome": "approve",
                "timestamp": "2026-06-01T01:00:00",
                **y,
            },
        )
    conn.commit()
    conn.close()
    return path


def _bucket(buckets: list[er.BucketYield], name: str) -> er.BucketYield:
    """Fetch one bucket by name, failing loudly if the slice did not produce it."""
    matches = [b for b in buckets if b.bucket == name]
    assert matches, f"bucket {name!r} missing from {[b.bucket for b in buckets]}"
    return matches[0]


# --------------------------------------------------------------------------------------
# THE CENTRAL DISTINCTION
# --------------------------------------------------------------------------------------


def test_measured_zero_and_never_measured_render_differently(tmp_path: Path) -> None:
    """A gate that ran and found nothing must not render like a gate never measured.

    This is the whole point of the module. If both render '0', the report cannot
    support any honest deletion argument.
    """
    db = _make_db(
        tmp_path / "e.db",
        [
            {"discussion_id": "D-measured", "command_type": "review"},
            {"discussion_id": "D-unmeasured", "command_type": "deliberate"},
        ],
        # 'review' ran and recorded a genuine zero. 'deliberate' recorded nothing at all.
        [{"discussion_id": "D-measured", "findings_blocking": 0}],
    )
    buckets = er.collect(db).slices["command_type"]

    measured = _bucket(buckets, "review")
    unmeasured = _bucket(buckets, "deliberate")

    assert measured.is_measured is True
    assert unmeasured.is_measured is False
    assert measured.yield_cell(measured.blocking) == "0"
    assert unmeasured.yield_cell(unmeasured.blocking) == er.NO_DATA
    assert measured.yield_cell(measured.blocking) != unmeasured.yield_cell(unmeasured.blocking)


def test_unmeasured_bucket_reports_no_yield_ratio(tmp_path: Path) -> None:
    """An unmeasured bucket yields None, never a fabricated 0.0 efficiency ratio."""
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1", "command_type": "deliberate", "total_tokens_out": 50_000}],
        [],
    )
    bucket = _bucket(er.collect(db).slices["command_type"], "deliberate")
    assert bucket.blocking_per_1k_out is None, "a never-measured bucket has no ratio, not 0.0"


def test_measured_zero_bucket_reports_a_real_zero_ratio(tmp_path: Path) -> None:
    """The mirror case: measured-and-empty legitimately scores 0.0, and must say so."""
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1", "command_type": "review", "total_tokens_out": 50_000}],
        [{"discussion_id": "D1", "findings_blocking": 0}],
    )
    bucket = _bucket(er.collect(db).slices["command_type"], "review")
    assert bucket.blocking_per_1k_out == 0.0


def test_rendered_report_shows_measured_fraction_per_bucket(tmp_path: Path) -> None:
    """Every slice row carries measured/total so coverage is never implicit."""
    db = _make_db(
        tmp_path / "e.db",
        [
            {"discussion_id": "D1", "command_type": "plan"},
            {"discussion_id": "D2", "command_type": "plan"},
            {"discussion_id": "D3", "command_type": "plan"},
        ],
        [{"discussion_id": "D1", "findings_blocking": 4}],
    )
    bucket = _bucket(er.collect(db).slices["command_type"], "plan")
    assert (bucket.measured_runs, bucket.runs) == (1, 3)
    assert bucket.unmeasured_runs == 2
    assert bucket.coverage == pytest.approx(1 / 3)


# --------------------------------------------------------------------------------------
# THE REGRESSION THAT HID 62 OF 77 ROWS
# --------------------------------------------------------------------------------------


def test_yield_is_counted_without_token_telemetry(tmp_path: Path) -> None:
    """Yield rows on token-less discussions must still be read.

    The previous report filtered on ``total_tokens_out IS NOT NULL``, which discarded
    the large majority of recorded yield and made measured protocols look unmeasured.
    """
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1", "command_type": "review", "total_tokens_out": None}],
        [{"discussion_id": "D1", "findings_blocking": 7, "findings_advisory": 3}],
    )
    data = er.collect(db)
    bucket = _bucket(data.slices["command_type"], "review")

    assert bucket.is_measured is True
    assert bucket.blocking == 7
    assert bucket.advisory == 3
    assert data.measured_discussions == 1
    # No token telemetry means no ratio — but the FINDINGS are still reported.
    assert bucket.token_runs == 0
    assert bucket.blocking_per_1k_out is None


def test_ratio_denominator_excludes_unmeasured_runs(tmp_path: Path) -> None:
    """Per-token yield divides by tokens from MEASURED runs only.

    Dividing real findings by tokens burned in never-measured runs understates the
    gate's yield — the same direction of error as reporting unmeasured as zero.
    """
    db = _make_db(
        tmp_path / "e.db",
        [
            {"discussion_id": "D1", "command_type": "review", "total_tokens_out": 1_000},
            {"discussion_id": "D2", "command_type": "review", "total_tokens_out": 9_000},
        ],
        [{"discussion_id": "D1", "findings_blocking": 2}],
    )
    bucket = _bucket(er.collect(db).slices["command_type"], "review")
    assert bucket.tokens_out == 10_000
    assert bucket.measured_tokens_out == 1_000
    # 2 blocking per 1000 measured output tokens == 2.0, not 0.2.
    assert bucket.blocking_per_1k_out == 2.0


def test_unmeasured_bucket_does_not_outrank_a_measured_zero(tmp_path: Path) -> None:
    """Ordering must not let an unmeasured bucket sit among real zero-yield buckets."""
    db = _make_db(
        tmp_path / "e.db",
        [
            {"discussion_id": "D1", "command_type": "measured", "total_tokens_out": 1_000},
            {"discussion_id": "D2", "command_type": "unmeasured", "total_tokens_out": 1_000},
        ],
        [{"discussion_id": "D1", "findings_blocking": 0}],
    )
    names = [b.bucket for b in er.collect(db).slices["command_type"]]
    assert names.index("measured") < names.index("unmeasured")


# --------------------------------------------------------------------------------------
# PROTOCOL COVERAGE — making "never measured" visible at all
# --------------------------------------------------------------------------------------


def test_protocol_coverage_includes_types_with_zero_rows(tmp_path: Path) -> None:
    """Every valid protocol type appears, including those never recorded."""
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1"}],
        [{"discussion_id": "D1", "protocol_type": "review", "findings_blocking": 1}],
    )
    coverage = {p.protocol_type: p for p in er.collect(db).protocol_coverage}

    assert coverage["review"].ever_measured is True
    for absent in ("education_gate", "quality_gate", "retro"):
        assert absent in coverage, f"{absent} vanished from the report because it had no rows"
        assert coverage[absent].ever_measured is False
        assert coverage[absent].rows == 0


def test_report_names_never_measured_protocols(tmp_path: Path, monkeypatch) -> None:
    """The rendered report calls out never-measured protocols BY NAME, not just with a dash.

    The assertions deliberately target the coverage banner's own line rather than any
    substring that also appears in GUARD_TEXT: an earlier version of this test passed
    purely off the guard boilerplate and stayed green when the banner was deleted.
    """
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1"}],
        [{"discussion_id": "D1", "protocol_type": "review", "findings_blocking": 1}],
    )
    monkeypatch.setattr(er, "DB_PATH", db)
    text = er.render_report(coverage_only=True)

    banner = [ln for ln in text.splitlines() if ln.startswith("NEVER MEASURED:")]
    assert banner, "the coverage banner naming unmeasured protocols is missing"
    for absent in ("education_gate", "quality_gate", "retro"):
        assert absent in banner[0], f"{absent} is unmeasured but is not named in the banner"
    assert "review" not in banner[0], "a measured protocol must not be listed as unmeasured"
    assert "ZERO recorded yield rows" in text
    assert "INSTRUMENT" in text


def test_protocol_type_outside_writer_enum_is_surfaced(tmp_path: Path) -> None:
    """A recorded type the writer no longer accepts is reported, not silently dropped."""
    db = _make_db(tmp_path / "e.db", [{"discussion_id": "D1"}], [])
    conn = sqlite3.connect(str(db))
    # Bypass the CHECK by inserting through a table without it would be artificial;
    # instead narrow the writer enum so 'checkpoint' becomes the unknown type.
    conn.execute(
        "INSERT INTO protocol_yield (discussion_id, protocol_type, outcome, timestamp)"
        " VALUES ('D1','checkpoint','pass','2026-06-01T01:00:00')"
    )
    conn.commit()
    conn.close()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(er, "valid_protocol_types", lambda: ("review",))
        names = [p.protocol_type for p in er.collect(db).protocol_coverage]
    assert any("checkpoint" in n and "not in writer enum" in n for n in names)


def test_valid_protocol_types_tracks_the_writer(tmp_path: Path, monkeypatch) -> None:
    """The reader takes its enum from record_yield.py, and falls back if absent."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import record_yield

    assert er.valid_protocol_types() == tuple(record_yield.VALID_PROTOCOL_TYPES)

    monkeypatch.setattr(er, "PROJECT_ROOT", tmp_path)  # no scripts/record_yield.py here
    assert er.valid_protocol_types() == er._FALLBACK_PROTOCOL_TYPES


# --------------------------------------------------------------------------------------
# GUARD TEXT + RECORDING HONESTY
# --------------------------------------------------------------------------------------


def test_report_carries_the_anti_deletion_guard(tmp_path: Path, monkeypatch) -> None:
    """The rule travels with the data, so a reader cannot get the numbers without it."""
    db = _make_db(tmp_path / "e.db", [{"discussion_id": "D1"}], [])
    monkeypatch.setattr(er, "DB_PATH", db)
    text = er.render_report()

    assert "NEVER MEASURED" in text
    assert "never have been" in text and "measured" in text
    assert "absence of evidence" in text


def test_false_positive_honesty_warning_fires_on_implausible_rate(
    tmp_path: Path, monkeypatch
) -> None:
    """A near-zero false-positive rate over a large sample is flagged, not celebrated."""
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1"}],
        [{"discussion_id": "D1", "findings_blocking": 100, "findings_false_positive": 0}],
    )
    monkeypatch.setattr(er, "DB_PATH", db)
    data = er.collect(db)
    assert data.total_findings == 100
    assert data.false_positive_rate == 0.0

    text = er.render_report(coverage_only=True)
    assert "HONESTY WARNING" in text
    assert "corrupts" in text


def test_no_honesty_warning_on_a_small_sample(tmp_path: Path, monkeypatch) -> None:
    """Below the sample floor the rate is too noisy to call implausible."""
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1"}],
        [{"discussion_id": "D1", "findings_blocking": 3, "findings_false_positive": 0}],
    )
    monkeypatch.setattr(er, "DB_PATH", db)
    assert "HONESTY WARNING" not in er.render_report(coverage_only=True)


def test_no_honesty_warning_when_false_positives_are_recorded(tmp_path: Path, monkeypatch) -> None:
    """A plausible rate over a large sample passes clean — the check is not unconditional."""
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1"}],
        [{"discussion_id": "D1", "findings_blocking": 90, "findings_false_positive": 10}],
    )
    monkeypatch.setattr(er, "DB_PATH", db)
    assert "HONESTY WARNING" not in er.render_report(coverage_only=True)


# --------------------------------------------------------------------------------------
# SAFETY: read-only, parameterised, honest about bad input
# --------------------------------------------------------------------------------------


def test_collect_does_not_mutate_the_database(tmp_path: Path) -> None:
    """The reader is read-only in fact, not merely by intention."""
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1", "command_type": "review"}],
        [{"discussion_id": "D1", "findings_blocking": 2}],
    )
    before = (tmp_path / "e.db").read_bytes()
    shutil.copy(db, tmp_path / "copy.db")
    er.collect(db)
    assert (tmp_path / "e.db").read_bytes() == before


def test_since_rejects_non_date_input(tmp_path: Path) -> None:
    """A malformed --since fails loudly instead of filtering everything out silently."""
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        er._validate_since("2026-01-01' OR 1=1--")
    with pytest.raises(ValueError):
        er._validate_since("last tuesday")
    assert er._validate_since("2026-06-01") == "2026-06-01"
    assert er._validate_since(None) is None


def test_since_actually_filters(tmp_path: Path) -> None:
    """The date filter is bound as a parameter and still filters correctly."""
    db = _make_db(
        tmp_path / "e.db",
        [
            {"discussion_id": "OLD", "created_at": "2026-01-01T00:00:00"},
            {"discussion_id": "NEW", "created_at": "2026-07-01T00:00:00"},
        ],
        [{"discussion_id": "OLD", "findings_blocking": 5}],
    )
    assert er.collect(db).total_discussions == 2
    recent = er.collect(db, since="2026-06-01")
    assert recent.total_discussions == 1
    assert recent.measured_discussions == 0


def test_ungroupable_column_is_refused(tmp_path: Path) -> None:
    """Only whitelisted column names reach the SQL string."""
    db = _make_db(tmp_path / "e.db", [{"discussion_id": "D1"}], [])
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        with pytest.raises(ValueError, match="ungroupable"):
            er._slice_yields(conn, "discussion_id; DROP TABLE discussions", None)
    finally:
        conn.close()


def _make_pre_migration_db(path: Path) -> Path:
    """Build a DB with NO token columns — the pre-ADR-0013 derived-project schema."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE discussions (
            discussion_id      TEXT PRIMARY KEY,
            created_at         DATETIME NOT NULL,
            risk_level         TEXT NOT NULL,
            collaboration_mode TEXT NOT NULL,
            command_type       TEXT
        );
        """
        + _YIELD_DDL
    )
    conn.execute(
        "INSERT INTO discussions VALUES ('D1','2026-06-01T00:00:00','medium',"
        "'structured-dialogue','review')"
    )
    conn.execute(
        "INSERT INTO discussions VALUES ('D2','2026-06-01T00:00:00','medium',"
        "'structured-dialogue','deliberate')"
    )
    conn.execute(
        "INSERT INTO protocol_yield (discussion_id, protocol_type, findings_blocking,"
        " findings_advisory, outcome, timestamp)"
        " VALUES ('D1','review',12,30,'approve','2026-06-01T01:00:00')"
    )
    conn.commit()
    conn.close()
    return path


def test_pre_migration_schema_still_reports_yield(tmp_path: Path) -> None:
    """A DB with no token columns must still yield a full coverage answer.

    Regression: naming ``d.total_tokens_out`` unconditionally raised OperationalError and
    made the ENTIRE report unreadable on the derived project holding the largest corpus of
    recorded yield — the one project whose ground truth mattered most.
    """
    db = _make_pre_migration_db(tmp_path / "old.db")
    data = er.collect(db)

    assert data.token_telemetry_available is False
    assert data.total_discussions == 2
    assert data.measured_discussions == 1
    assert data.total_yield_rows == 1

    measured = _bucket(data.slices["command_type"], "review")
    unmeasured = _bucket(data.slices["command_type"], "deliberate")
    assert measured.blocking == 12
    assert measured.advisory == 30
    # The central distinction survives the degraded schema.
    assert measured.yield_cell(measured.blocking) == "12"
    assert unmeasured.yield_cell(unmeasured.blocking) == er.NO_DATA
    # Token figures are absent, not fabricated as zero-spend.
    assert measured.token_runs == 0
    assert measured.blocking_per_1k_out is None
    assert data.top_discussions == []


def test_pre_migration_report_says_degraded_not_empty(tmp_path: Path, monkeypatch) -> None:
    """The rendered report names the degradation instead of implying zero spend."""
    db = _make_pre_migration_db(tmp_path / "old.db")
    monkeypatch.setattr(er, "DB_PATH", db)
    text = er.render_report()

    assert "DEGRADED" in text
    assert "omitted, NOT zero" in text
    assert "12" in text, "the recorded yield must still be printed"


def test_token_column_helper_rejects_arbitrary_names(tmp_path: Path) -> None:
    """Only literal token-column names may be interpolated into the SQL."""
    with pytest.raises(ValueError, match="not a token column"):
        er._tok(set(), "discussion_id; DROP TABLE discussions")
    assert er._tok({"total_tokens_out"}, "total_tokens_out") == "d.total_tokens_out"
    assert er._tok(set(), "total_tokens_out") == "NULL"


def test_no_data_marker_right_aligns_with_numbers() -> None:
    """The dash sits in the numeric column, so it reads as a marker not a glitch."""
    table = er._format_table([[er.NO_DATA], [12345]], ["blocking"])
    lines = table.splitlines()
    assert lines[-2].rstrip().endswith(er.NO_DATA)
    assert len(lines[-2]) == len(lines[-1])


# ======================================================================================
# THE WIRED EXIT-CODE CONTRACT — both instruments
# ======================================================================================
#
# The module thesis is "absence of evidence is not evidence of absence". These tests
# apply it to the INSTRUMENT LAYER, where it previously failed silently in both scripts
# that /retro and /knowledge-health wire in:
#
#   * efficiency_report.py printed "Database not found ..." and exited 0.
#   * audit_calibration.py swallowed a database error into a note, printed "classifier
#     calibration looks healthy", and exited 0.
#
# Both command files documented exit 1 for exactly that case. So an agent following the
# wiring would read exit 0, find no coverage table, and write "no yield data" — rendering
# ABSENCE OF THE INSTRUMENT as ABSENCE OF FINDINGS. That is the report's own named
# failure mode, occurring one level above the data it guards.
#
# The audit_calibration cases live in this module rather than in
# tests/test_audit_calibration.py because that file belongs to another slice; keeping
# them here keeps the contract and the thesis it serves in one place. If that file's
# owner would rather host them, they move wholesale — nothing here depends on this
# module's fixtures except `sandboxed_calibration`.


@pytest.fixture
def sandboxed_calibration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, Path]]:
    """Point every audit_calibration write target inside tmp_path, and PROVE it held.

    ``audit_calibration.main()`` now always persists a run-log line, so a test that
    forgot one of these globals would write into the real repository. The teardown
    asserts the real paths were not created, so that mistake fails loudly here instead
    of quietly contaminating ``metrics/`` — tests in this repo have done exactly that.
    """
    real_log, real_queue = ac.LOG_PATH, ac.QUEUE_DIR
    log_existed, queue_existed = real_log.exists(), real_queue.exists()
    queue_before = {p.name for p in real_queue.iterdir()} if queue_existed else set()

    paths = {
        "db": tmp_path / "evaluation.db",
        "log": tmp_path / "calibration_log.jsonl",
        "queue": tmp_path / "queue",
    }
    monkeypatch.setattr(ac, "DB_PATH", paths["db"])
    monkeypatch.setattr(ac, "LOG_PATH", paths["log"])
    monkeypatch.setattr(ac, "QUEUE_DIR", paths["queue"])
    yield paths

    assert real_log.exists() == log_existed, (
        f"a test created or removed the REAL run log at {real_log} — writes must stay in tmp_path"
    )
    queue_after = {p.name for p in real_queue.iterdir()} if real_queue.exists() else set()
    assert queue_after == queue_before, (
        f"a test wrote into the REAL proposal queue at {real_queue}: "
        f"{sorted(queue_after - queue_before)}"
    )


def _log_lines(path: Path) -> list[dict[str, object]]:
    """Parse the JSONL run log, failing loudly on a malformed line."""
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _calibration_db(path: Path) -> Path:
    """A schema-faithful, well-calibrated evaluation.db that yields ZERO proposals."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE findings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            severity   TEXT,
            category   TEXT,
            summary    TEXT,
            is_noise   INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME
        );
        CREATE TABLE agent_effectiveness (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            agent                  TEXT,
            confidence_calibration REAL
        );
        """
    )
    # Plain summaries with no severity keywords classify to the heuristic default
    # 'medium', so recording 'medium' is genuine agreement, not a rigged match.
    conn.executemany(
        "INSERT INTO findings (severity, category, summary, is_noise, created_at)"
        " VALUES ('medium','testing',?,0,'2026-06-01T00:00:00')",
        [(f"ok {i}",) for i in range(10)],
    )
    conn.executemany(
        "INSERT INTO agent_effectiveness (agent, confidence_calibration) VALUES ('qa', ?)",
        [(0.05,) for _ in range(8)],
    )
    conn.commit()
    conn.close()
    return path


# --- efficiency_report.py ------------------------------------------------------------


@pytest.mark.regression
def test_missing_database_exits_1_not_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing DB is a BROKEN INSTRUMENT (exit 1), never a clean run (exit 0).

    Regression: main() printed "Database not found ..." and fell through to `return 0`,
    contradicting the exit-1 contract both command files publish. An agent following the
    documented wiring would have logged "no yield data" from a report that never ran.
    """
    monkeypatch.setattr(er, "DB_PATH", tmp_path / "absent.db")
    monkeypatch.setattr(sys, "argv", ["efficiency_report.py"])

    assert er.main() == 1

    out = capsys.readouterr().out
    assert "BROKEN INSTRUMENT" in out
    # It must actively forbid the wrong conclusion, not merely fail to state it.
    assert "ABSENCE OF THE INSTRUMENT" in out
    assert "not an absence of findings" in out
    # And it must not look like a report that simply found nothing.
    assert "Yield coverage by protocol type" not in out


@pytest.mark.regression
def test_unreadable_database_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file that exists but is not a database also exits 1, with no raw DB error."""
    bad = tmp_path / "corrupt.db"
    bad.write_bytes(b"this is not a database" * 50)
    monkeypatch.setattr(er, "DB_PATH", bad)
    monkeypatch.setattr(sys, "argv", ["efficiency_report.py"])

    assert er.main() == 1

    out = capsys.readouterr().out
    assert "database error" in out
    assert "file is not a database" not in out, "raw DB internals must never surface"


def test_readable_database_still_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other arm: a real DB exits 0 and renders. Guards against a blanket exit 1.

    Without this, a fixer could satisfy the test above by always returning 1 — the
    "returned the same answer for both arms" failure this repo has already shipped once.
    """
    db = _make_db(
        tmp_path / "e.db",
        [{"discussion_id": "D1", "command_type": "review"}],
        [{"discussion_id": "D1", "findings_blocking": 3}],
    )
    monkeypatch.setattr(er, "DB_PATH", db)
    monkeypatch.setattr(sys, "argv", ["efficiency_report.py"])

    assert er.main() == 0

    out = capsys.readouterr().out
    assert "Yield coverage by protocol type" in out
    assert "BROKEN INSTRUMENT" not in out


def test_malformed_since_still_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The third documented arm stays distinct from the broken-instrument arm."""
    db = _make_db(tmp_path / "e.db", [{"discussion_id": "D1"}], [])
    monkeypatch.setattr(er, "DB_PATH", db)
    monkeypatch.setattr(sys, "argv", ["efficiency_report.py", "--since", "last tuesday"])

    assert er.main() == 2
    assert "ERROR" in capsys.readouterr().out


def test_render_report_resolves_db_path_at_call_time(tmp_path: Path) -> None:
    """render_report(db_path=...) is honoured, so the guard is testable without globals."""
    assert "BROKEN INSTRUMENT" in er.render_report(db_path=tmp_path / "absent.db")


# --- audit_calibration.py ------------------------------------------------------------


@pytest.mark.regression
def test_calibration_missing_db_exits_1(
    sandboxed_calibration: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing DB exits 1 — the signal main() previously could not emit at all.

    Regression: main() contained exactly one `return 0`, so the "a non-zero exit means
    the audit itself failed to run" sentence in both command files was unreachable.
    """
    monkeypatch.setattr(sys, "argv", ["audit_calibration.py", "--report-only"])

    assert ac.main() == 1

    out = capsys.readouterr().out
    assert "BROKEN INSTRUMENT" in out
    # The dangerous rendering: a failed audit must NOT report a clean bill of health.
    assert "looks healthy" not in out


@pytest.mark.regression
def test_calibration_corrupt_db_exits_1_without_leaking_internals(
    sandboxed_calibration: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-sqlite file exits 1, and still never surfaces the raw DB error."""
    sandboxed_calibration["db"].write_bytes(b"this is not a database" * 50)
    monkeypatch.setattr(sys, "argv", ["audit_calibration.py", "--report-only"])

    assert ac.main() == 1

    out = capsys.readouterr().out
    assert "database error" in out
    assert "file is not a database" not in out
    assert "looks healthy" not in out


def test_calibration_clean_run_exits_0(
    sandboxed_calibration: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The other arm: a readable DB with zero drift exits 0.

    Zero proposals must never be conflated with a failed audit — that is the whole
    reason the exit code gates on `instrument_ok` and not on `proposals`.
    """
    _calibration_db(sandboxed_calibration["db"])
    monkeypatch.setattr(sys, "argv", ["audit_calibration.py", "--report-only"])

    assert ac.main() == 0

    out = capsys.readouterr().out
    assert "looks healthy" in out
    assert "BROKEN INSTRUMENT" not in out


@pytest.mark.regression
def test_zero_proposal_run_still_appends_exactly_one_log_line(
    sandboxed_calibration: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean audit leaves a durable trace. This is the finding's core.

    Regression: the write was gated `if write and result.proposals`, so an audit that
    ran and found nothing wrote NOTHING — making "measured, no drift" indistinguishable
    from "never measured". That is the exact ambiguity this slice exists to abolish,
    reproduced inside the instrument meant to abolish it.
    """
    _calibration_db(sandboxed_calibration["db"])
    monkeypatch.setattr(sys, "argv", ["audit_calibration.py", "--report-only"])

    assert ac.main() == 0

    lines = _log_lines(sandboxed_calibration["log"])
    assert len(lines) == 1, f"expected exactly one run-log line, got {lines}"
    assert lines[0]["proposals"] == 0
    assert lines[0]["ok"] is True
    assert lines[0]["ts"]


@pytest.mark.regression
def test_report_only_writes_the_log_but_not_the_queue(
    sandboxed_calibration: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """--report-only suppresses the QUEUE artifact, never the run-log line.

    Regression: both wired invocations pass --report-only and main() mapped that to
    `write=False`, so `metrics/calibration_log.jsonl` could never be created by any
    reachable caller — `_append_log` had no live call site at all.
    """
    db = sandboxed_calibration["db"]
    conn = sqlite3.connect(str(_calibration_db(db)))
    # Force a proposal so "queue suppressed" is a real suppression, not an empty result.
    conn.executemany(
        "INSERT INTO agent_effectiveness (agent, confidence_calibration) VALUES (?, 0.9)",
        [(f"drifter{i}",) for i in range(2) for _ in range(8)],
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(sys, "argv", ["audit_calibration.py", "--report-only"])
    assert ac.main() == 0

    assert not sandboxed_calibration["queue"].exists(), "--report-only must not queue"
    lines = _log_lines(sandboxed_calibration["log"])
    assert len(lines) == 1
    assert lines[0]["proposals"] >= 1, "the log must record what the run found"
    assert "agent-calibration-drift" in lines[0]["signals"]


def test_each_run_appends_rather_than_overwrites(
    sandboxed_calibration: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two invocations leave two lines — the log is a history, not a latest-value cell."""
    _calibration_db(sandboxed_calibration["db"])
    monkeypatch.setattr(sys, "argv", ["audit_calibration.py", "--report-only"])

    assert ac.main() == 0
    assert ac.main() == 0

    assert len(_log_lines(sandboxed_calibration["log"])) == 2


def test_write_false_still_writes_absolutely_nothing(
    sandboxed_calibration: dict[str, Path],
) -> None:
    """`write=False` remains the master off switch, so library callers stay side-effect free.

    Every test in tests/test_audit_calibration.py relies on this; the run-log change must
    not turn those calls into repository writes.
    """
    _calibration_db(sandboxed_calibration["db"])

    result = ac.audit_calibration(sandboxed_calibration["db"], write=False)

    assert result.instrument_ok is True
    assert not sandboxed_calibration["log"].exists()
    assert not sandboxed_calibration["queue"].exists()


def test_broken_instrument_is_a_structured_field_not_a_note_substring(
    sandboxed_calibration: dict[str, Path],
) -> None:
    """The exit code reads `instrument_ok`, so re-wording a note cannot silently flip it."""
    missing = ac.audit_calibration(sandboxed_calibration["db"], write=False)
    assert missing.instrument_ok is False

    ok = ac.audit_calibration(_calibration_db(sandboxed_calibration["db"]), write=False)
    assert ok.instrument_ok is True
