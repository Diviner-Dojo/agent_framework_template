"""Tests for scripts/record_yield.py — the WRITER whose silence is not evidence.

``protocol_yield`` is the ground truth every later "is this gate worth keeping?" argument
has to be settled against. That makes two properties load-bearing:

* **A recorded zero must be a real zero.** The writer must persist an explicit
  ``findings_blocking=0`` row, because a recorded zero ("ran, caught nothing") is the only
  thing that distinguishes a gate from one that was never measured at all.
* **False positives must round-trip.** ``findings_false_positive`` is the honesty column.
  If it silently drops, every downstream precision and yield number is flattered — in the
  direction that makes the gate look better than it is.

Every test points ``record_yield.DB_PATH`` at ``tmp_path``. Nothing here writes to the
real ``metrics/evaluation.db`` or anywhere inside the repository.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import record_yield as ry  # noqa: E402

_DDL = """
CREATE TABLE discussions (
    discussion_id TEXT PRIMARY KEY,
    created_at    DATETIME NOT NULL
);
CREATE TABLE protocol_yield (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id TEXT NOT NULL REFERENCES discussions(discussion_id),
    protocol_type TEXT NOT NULL CHECK(protocol_type IN (
        'review','checkpoint','education_gate','quality_gate','retro')),
    findings_blocking       INTEGER NOT NULL DEFAULT 0,
    findings_advisory       INTEGER NOT NULL DEFAULT 0,
    findings_false_positive INTEGER NOT NULL DEFAULT 0,
    agent_turns_used        INTEGER NOT NULL DEFAULT 0,
    outcome       TEXT NOT NULL CHECK(outcome IN (
        'approve','approve-with-changes','request-changes','reject',
        'pass','fail','revise-resolved','revise-unresolved')),
    timestamp     DATETIME NOT NULL
);
"""


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway evaluation.db with one discussion, wired in as the writer's target."""
    path = tmp_path / "evaluation.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(_DDL)
    conn.execute("INSERT INTO discussions VALUES ('DISC-1', '2026-06-01T00:00:00')")
    conn.execute("INSERT INTO discussions VALUES ('DISC-2', '2026-06-01T00:00:00')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(ry, "DB_PATH", path)
    return path


def _rows(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM protocol_yield ORDER BY id").fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------------------
# A RECORDED ZERO IS EVIDENCE
# --------------------------------------------------------------------------------------


def test_zero_findings_still_writes_a_row(db: Path) -> None:
    """A gate that caught nothing must leave a row behind.

    If the writer skipped "boring" zero-yield runs, the table could never distinguish
    a gate that ran clean from one nobody ever measured — the exact ambiguity that
    turns silence into a deletion argument.
    """
    ry.record_yield("DISC-1", "review", "approve", findings_blocking=0, findings_advisory=0)

    rows = _rows(db)
    assert len(rows) == 1, "a zero-yield run must be recorded, not skipped"
    assert rows[0]["findings_blocking"] == 0
    assert rows[0]["outcome"] == "approve"


def test_all_count_fields_round_trip(db: Path) -> None:
    """Every count the caller supplies is persisted exactly — including false positives."""
    ry.record_yield(
        "DISC-1",
        "review",
        "request-changes",
        findings_blocking=3,
        findings_advisory=7,
        findings_false_positive=2,
        agent_turns_used=11,
    )

    row = _rows(db)[0]
    assert row["findings_blocking"] == 3
    assert row["findings_advisory"] == 7
    assert row["findings_false_positive"] == 2, "the honesty column must not be dropped"
    assert row["agent_turns_used"] == 11
    assert row["protocol_type"] == "review"


def test_defaults_are_zero_not_null(db: Path) -> None:
    """Unsupplied counts record as 0 — a real measurement, not a missing one."""
    ry.record_yield("DISC-1", "checkpoint", "pass")

    row = _rows(db)[0]
    for col in (
        "findings_blocking",
        "findings_advisory",
        "findings_false_positive",
        "agent_turns_used",
    ):
        assert row[col] == 0
        assert row[col] is not None


def test_timestamp_is_recorded_as_utc_iso(db: Path) -> None:
    """Rows are timestamped so a yield figure can be tied back to a period."""
    ry.record_yield("DISC-1", "review", "approve")

    ts = _rows(db)[0]["timestamp"]
    assert ts.startswith("20")
    assert "T" in ts
    assert ts.endswith("+00:00"), f"expected a UTC-qualified timestamp, got {ts!r}"


# --------------------------------------------------------------------------------------
# DUPLICATE GUARD
# --------------------------------------------------------------------------------------


def test_duplicate_same_protocol_is_skipped(db: Path, capsys: pytest.CaptureFixture) -> None:
    """Re-recording the same discussion+protocol must not double-count the yield."""
    ry.record_yield("DISC-1", "review", "approve", findings_blocking=2)
    ry.record_yield("DISC-1", "review", "approve", findings_blocking=99)

    rows = _rows(db)
    assert len(rows) == 1, "duplicate recording would inflate every downstream total"
    assert rows[0]["findings_blocking"] == 2, "the first record stands; the retry is discarded"
    assert "WARNING" in capsys.readouterr().out


def test_different_protocol_on_same_discussion_is_allowed(db: Path) -> None:
    """One discussion legitimately carries a review AND a checkpoint measurement."""
    ry.record_yield("DISC-1", "review", "approve", findings_blocking=2)
    ry.record_yield("DISC-1", "checkpoint", "pass", findings_blocking=1)

    rows = _rows(db)
    assert len(rows) == 2
    assert {r["protocol_type"] for r in rows} == {"review", "checkpoint"}


def test_same_protocol_on_different_discussions_is_allowed(db: Path) -> None:
    """The duplicate guard is keyed on the pair, not on protocol type alone."""
    ry.record_yield("DISC-1", "review", "approve")
    ry.record_yield("DISC-2", "review", "approve")

    assert len(_rows(db)) == 2


# --------------------------------------------------------------------------------------
# INTEGRITY OF THE EVIDENCE
# --------------------------------------------------------------------------------------


def test_yield_for_unknown_discussion_is_rejected(db: Path) -> None:
    """A yield row must attach to a real discussion, or it is unattributable evidence."""
    with pytest.raises(sqlite3.IntegrityError):
        ry.record_yield("DISC-DOES-NOT-EXIST", "review", "approve", findings_blocking=5)

    assert _rows(db) == []


def test_invalid_protocol_type_is_rejected(db: Path) -> None:
    """The schema CHECK is real: an unknown protocol type cannot be recorded."""
    with pytest.raises(sqlite3.IntegrityError):
        ry.record_yield("DISC-1", "not-a-protocol", "approve")

    assert _rows(db) == []


def test_invalid_outcome_is_rejected(db: Path) -> None:
    """Outcome is a closed vocabulary; free text would break every outcome rollup."""
    with pytest.raises(sqlite3.IntegrityError):
        ry.record_yield("DISC-1", "review", "sort-of-fine")

    assert _rows(db) == []


def test_missing_database_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing DB fails loudly — a silently-dropped measurement is unrecoverable."""
    monkeypatch.setattr(ry, "DB_PATH", tmp_path / "absent.db")
    with pytest.raises(SystemExit) as exc:
        ry.record_yield("DISC-1", "review", "approve", findings_blocking=4)
    assert exc.value.code == 1


# --------------------------------------------------------------------------------------
# CLI SURFACE — the form the command files actually invoke
# --------------------------------------------------------------------------------------


def test_cli_maps_flags_onto_the_right_columns(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--false-positive` and `--turns` must land in their own columns, not be swallowed."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "record_yield.py",
            "DISC-1",
            "review",
            "approve-with-changes",
            "--blocking",
            "4",
            "--advisory",
            "6",
            "--false-positive",
            "1",
            "--turns",
            "9",
        ],
    )
    ry.main()

    row = _rows(db)[0]
    assert row["findings_blocking"] == 4
    assert row["findings_advisory"] == 6
    assert row["findings_false_positive"] == 1
    assert row["agent_turns_used"] == 9
    assert row["outcome"] == "approve-with-changes"


def test_cli_rejects_a_protocol_type_outside_the_enum(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """argparse enforces the same vocabulary the schema does, before touching the DB."""
    monkeypatch.setattr(sys, "argv", ["record_yield.py", "DISC-1", "bogus", "approve"])
    with pytest.raises(SystemExit) as exc:
        ry.main()
    assert exc.value.code == 2
    assert _rows(db) == []


def test_writer_enum_matches_the_schema_check(db: Path) -> None:
    """Every type the CLI advertises is actually insertable.

    A writer offering a protocol type the schema rejects would produce a type that can
    never be measured — permanently indistinguishable from one that is merely unused.
    """
    for i, ptype in enumerate(ry.VALID_PROTOCOL_TYPES):
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO protocol_yield (discussion_id, protocol_type, outcome, timestamp)"
            " VALUES ('DISC-1', ?, 'pass', '2026-06-01T00:00:00')",
            (ptype,),
        )
        conn.commit()
        conn.close()
        assert len(_rows(db)) == i + 1
