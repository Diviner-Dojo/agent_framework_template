"""Tests for scripts/education/ingest_walkthrough_session.py — the ingest chokepoint.

Every test is tmp_path-isolated: its own SQLite DB (init_db DDL), its own
``discussions/`` dir, and its own ``gates.yaml`` copy. The synthetic end-to-end
transcript exercises all five event shapes.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.education import gate_registry as reg
from scripts.education.ingest_walkthrough_session import (
    MAX_EVENTS,
    MAX_TEXT_LEN,
    MAX_TRANSCRIPT_BYTES,
    GateNotFoundError,
    TranscriptValidationError,
    build_parser,
    ingest_transcript,
    load_transcript,
    run,
    validate_transcript,
)
from scripts.init_db import init_db
from scripts.record_education import BLOOM_LEVELS, QUESTION_TYPES

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "education"
    / "fixtures"
    / "transcript_v1_valid.json"
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "education" / "ingest_walkthrough_session.py"
)

GATE_ID = "EDU-20260610-unit-4-1"


# --------------------------------------------------------------------------- #
# Fixtures + builders
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """A fresh SQLite DB with the framework schema."""
    path = tmp_path / "evaluation.db"
    init_db(path, quiet=True)
    return path


@pytest.fixture()
def discussions_dir(tmp_path: Path) -> Path:
    """An isolated discussions/ root with a dated subdir (write_event scans dates)."""
    root = tmp_path / "discussions"
    root.mkdir()
    return root


def _seed_gate(gate_id: str = GATE_ID, status: str = "open") -> dict[str, Any]:
    cleared_by = None
    if status == "cleared":
        cleared_by = {
            "session_id": "OTHER",
            "discussion_id": "DISC-OTHER",
            "cleared_at": "2026-07-01T00:00:00+00:00",
        }
    return {
        "gate_id": gate_id,
        "created_at": "2026-06-10",
        "origin": "REV-20260610-012629",
        "scope": {"files": ["src/telemetry/dashboard.py"], "adrs": ["ADR-0020"], "spec": None},
        "reason_deferred": "deferred to next interactive session",
        "status": status,
        "cleared_by": cleared_by,
    }


@pytest.fixture()
def registry_path(tmp_path: Path) -> Path:
    """A gates.yaml with a single open gate."""
    path = tmp_path / "gates.yaml"
    reg.save_registry({"version": 1, "gates": [_seed_gate()]}, path)
    return path


def _full_transcript(
    session_id: str = "GATE-20260715-abc",
    gate_id: str = GATE_ID,
    mode: str = "gate",
) -> dict[str, Any]:
    """A complete passing transcript containing all five event shapes.

    narration + Q&A exchange + quiz-miss-then-variant-pass + item-level deferral +
    explain-back + completion. Terminal quiz avg (variant 0.90) and explain-back
    0.85 both pass the 0.70 bar => outcome 'clear-eligible' (the registry is NOT
    flipped: clearing is the developer's explicit action — ADR-0035).
    """
    return {
        "contract_version": 1,
        "session_id": session_id,
        "gate_id": gate_id,
        "repo_slug": "owner/agent_framework_template",
        "mode": mode,
        "started_at": "2026-07-15T14:00:00+00:00",
        "completed_at": "2026-07-15T14:42:00+00:00",
        "events": [
            {"type": "narration", "chapter_id": "ch01", "text": "Chapter 1 walked."},
            {
                "type": "qa_exchange",
                "question": "What does clear_gate return?",
                "answer": "A (gate, changed) tuple.",
            },
            {
                "type": "quiz_item",
                "item_id": "q1",
                "question": "Why idempotent?",
                "answer": "no idea",
                "score": 0.30,
                "bloom": "understand",
                "question_type": "recall",
                "variant_of": None,
            },
            {
                "type": "quiz_item",
                "item_id": "q1v1",
                "question": "Re-teach: what makes a re-run safe?",
                "answer": "existing rows short-circuit it",
                "score": 0.90,
                "bloom": "understand",
                "question_type": "recall",
                "variant_of": "q1",
            },
            {"type": "deferral", "scope": "item", "reason": "save q2 for later"},
            {
                "type": "explain_back",
                "prompt": "Explain the write sequence.",
                "answer": "validate, discussion, events, rows, registry.",
                "score": 0.85,
            },
            {"type": "completion", "summary": "Session complete."},
        ],
        "outcome": {"status": "completed", "summary": "cleared"},
    }


def _write(path: Path, transcript: dict[str, Any]) -> Path:
    path.write_text(json.dumps(transcript), encoding="utf-8")
    return path


def _ingest(transcript: dict[str, Any], db_path: Path, registry_path: Path, discussions_dir: Path):
    return ingest_transcript(
        transcript,
        db_path=db_path,
        registry_path=registry_path,
        discussions_dir=discussions_dir,
    )


def _edu_rows(db_path: Path, session_id: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT bloom_level, question_type, score, passed "
            "FROM education_results WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()


def _events(discussions_dir: Path, discussion_id: str) -> list[dict[str, Any]]:
    for date_dir in discussions_dir.iterdir():
        candidate = date_dir / discussion_id / "events.jsonl"
        if candidate.exists():
            return [
                json.loads(line) for line in candidate.read_text(encoding="utf-8").splitlines()
            ]
    raise AssertionError(f"events.jsonl not found for {discussion_id}")


# --------------------------------------------------------------------------- #
# End-to-end happy path
# --------------------------------------------------------------------------- #
class TestEndToEnd:
    def test_full_transcript_is_clear_eligible_not_cleared(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript()
        result = _ingest(transcript, db_path, registry_path, discussions_dir)

        assert result.outcome == "clear-eligible"
        assert result.changed is True
        assert result.discussion_id is not None

        # --- events.jsonl: exact intent order + tags ---
        events = _events(discussions_dir, result.discussion_id)
        intents = [(e["agent"], e["intent"]) for e in events]
        assert intents == [
            ("tutor", "proposal"),  # narration
            ("learner", "question"),  # qa ask
            ("tutor", "evidence"),  # qa answer
            ("tutor", "question"),  # quiz q1 ask
            ("learner", "evidence"),  # quiz q1 answer
            ("tutor", "critique"),  # quiz q1 grade
            ("tutor", "question"),  # quiz q1v1 ask
            ("learner", "evidence"),  # quiz q1v1 answer
            ("tutor", "critique"),  # quiz q1v1 grade
            ("learner", "decision"),  # item deferral
            ("tutor", "question"),  # explain-back prompt
            ("learner", "evidence"),  # explain-back answer
            ("tutor", "critique"),  # explain-back grade
            ("tutor", "synthesis"),  # completion
        ]
        assert result.event_count == 14
        for event in events:
            assert "education" in event["tags"]
            assert "repocademy" in event["tags"]
            assert f"gate:{GATE_ID}" in event["tags"]

        # --- education_results rows per the locked map ---
        rows = _edu_rows(db_path, transcript["session_id"])
        assert rows == [
            ("understand", "walkthrough", 1.0, 1),  # narration
            ("understand", "recall", 0.30, 0),  # quiz miss
            ("understand", "recall", 0.90, 1),  # quiz variant pass
            ("evaluate", "explain-back", 0.85, 1),  # explain-back
        ]
        assert result.education_row_count == 4

        # --- registry NOT flipped: eligibility is not clearance (ADR-0035) ---
        gate = reg.get_gate(reg.load_registry(registry_path), GATE_ID)
        assert gate["status"] == "open"
        assert gate["cleared_by"] is None
        # ... but the DURABLE additive marker is written, so paid-but-unclaimed is
        # distinguishable from unpaid days later (F1).
        marker = gate["clear_eligible"]
        assert marker["session_id"] == transcript["session_id"]
        assert marker["discussion_id"] == result.discussion_id
        assert marker["eligible_at"]
        # The exact developer command is carried on the result. The tmp registry is
        # not the default one, so the command MUST pin it with --registry (F6) —
        # otherwise the paste would mutate the wrong file.
        assert result.clear_command == (
            f'python scripts/education/gate_registry.py --registry "{registry_path.resolve()}" '
            f"clear --gate-id {GATE_ID} --session-id {transcript['session_id']} "
            f"--discussion-id {result.discussion_id}"
        )

    def test_cli_success_summary(
        self,
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tpath = _write(tmp_path / "t.json", _full_transcript())
        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "outcome=clear-eligible" in out
        assert "education_rows=4" in out
        assert f"Ingested gate {GATE_ID}" in out
        # The developer-facing eligibility block: command printed, never run.
        assert "CLEAR-ELIGIBLE" in out
        assert f"clear --gate-id {GATE_ID}" in out
        # Non-default registry → the printed command pins it (F6).
        assert f'--registry "{registry_path.resolve()}"' in out


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #
class TestIdempotency:
    def test_double_run_is_noop(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript()
        first = _ingest(transcript, db_path, registry_path, discussions_dir)
        cleared_by_first = copy.deepcopy(
            reg.get_gate(reg.load_registry(registry_path), GATE_ID)["cleared_by"]
        )

        second = _ingest(transcript, db_path, registry_path, discussions_dir)
        assert second.changed is False
        assert second.outcome == "already-ingested"
        assert second.discussion_id is None

        # No duplicate education rows.
        assert len(_edu_rows(db_path, transcript["session_id"])) == 4
        # No duplicate events.jsonl lines (only the first discussion exists).
        assert len(_events(discussions_dir, first.discussion_id)) == 14
        # cleared_by untouched.
        cleared_by_second = reg.get_gate(reg.load_registry(registry_path), GATE_ID)["cleared_by"]
        assert cleared_by_second == cleared_by_first
        # Exactly one discussion row.
        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM discussions").fetchone()[0]
        finally:
            conn.close()
        assert count == 1


# --------------------------------------------------------------------------- #
# Session-level deferral -> re-defer
# --------------------------------------------------------------------------- #
class TestSessionDeferral:
    def test_session_deferral_re_defers(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-defer-1")
        transcript["events"].append(
            {"type": "deferral", "scope": "session", "reason": "out of time on the treadmill"}
        )
        transcript["outcome"] = {"status": "session-deferred"}

        result = _ingest(transcript, db_path, registry_path, discussions_dir)
        assert result.outcome == "re-deferred"
        assert result.changed is True

        gate = reg.get_gate(reg.load_registry(registry_path), GATE_ID)
        assert gate["status"] == "re-deferred"
        assert gate["reason_deferred"] == "out of time on the treadmill"
        assert gate["cleared_by"] is None

        # The session-level deferral is captured as a decision event.
        events = _events(discussions_dir, result.discussion_id)
        decisions = [e for e in events if e["intent"] == "decision"]
        assert any("out of time on the treadmill" in e["content"] for e in decisions)


# --------------------------------------------------------------------------- #
# Below-threshold completion -> recorded-open
# --------------------------------------------------------------------------- #
class TestBelowThreshold:
    def test_below_threshold_stays_open(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-low-1")
        # Drop the passing variant so the only terminal quiz score is the 0.30 miss.
        transcript["events"] = [e for e in transcript["events"] if e.get("item_id") != "q1v1"]
        # q1 no longer superseded -> terminal avg = 0.30 < 0.70.
        result = _ingest(transcript, db_path, registry_path, discussions_dir)
        assert result.outcome == "recorded-open"
        assert result.changed is True

        # Rows still recorded.
        assert len(_edu_rows(db_path, transcript["session_id"])) == 3
        # Gate NOT flipped.
        gate = reg.get_gate(reg.load_registry(registry_path), GATE_ID)
        assert gate["status"] == "open"
        assert gate["cleared_by"] is None

    def test_learn_mode_never_clears(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="LEARN-1", mode="learn")
        result = _ingest(transcript, db_path, registry_path, discussions_dir)
        assert result.outcome == "recorded-open"
        assert reg.get_gate(reg.load_registry(registry_path), GATE_ID)["status"] == "open"


# --------------------------------------------------------------------------- #
# Pass-threshold boundary (>= 0.70 makes the gate clear-eligible; exact boundary
# must pass — the registry flip itself is the developer's action, ADR-0035)
# --------------------------------------------------------------------------- #
class TestPassThresholdBoundary:
    def test_exact_070_passes_and_is_clear_eligible(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-boundary-1")
        # Pin every graded score to exactly the 0.70 threshold.
        for event in transcript["events"]:
            if event["type"] in ("quiz_item", "explain_back"):
                event["score"] = 0.70
        result = _ingest(transcript, db_path, registry_path, discussions_dir)

        assert result.outcome == "clear-eligible"
        rows = _edu_rows(db_path, transcript["session_id"])
        graded = [r for r in rows if r[2] == 0.70]
        assert len(graded) == 3, f"expected q1, q1v1, explain-back at 0.70, got {rows}"
        assert all(r[3] == 1 for r in graded), f"0.70 must record passed=1: {rows}"
        gate = reg.get_gate(reg.load_registry(registry_path), GATE_ID)
        assert gate["status"] == "open"
        assert result.clear_command is not None

    def test_just_below_070_fails_item_and_gate(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-boundary-2")
        for event in transcript["events"]:
            if event["type"] in ("quiz_item", "explain_back"):
                event["score"] = 0.69
        result = _ingest(transcript, db_path, registry_path, discussions_dir)

        assert result.outcome == "recorded-open"
        rows = _edu_rows(db_path, transcript["session_id"])
        graded = [r for r in rows if r[2] == 0.69]
        assert graded and all(r[3] == 0 for r in graded)
        assert reg.get_gate(reg.load_registry(registry_path), GATE_ID)["status"] == "open"


# --------------------------------------------------------------------------- #
# Score clamping
# --------------------------------------------------------------------------- #
class TestScoreClamping:
    def test_high_score_clamped_to_one(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-clamp-1")
        # Overwrite the variant score with an out-of-range 1.7.
        for event in transcript["events"]:
            if event.get("item_id") == "q1v1":
                event["score"] = 1.7
        _ingest(transcript, db_path, registry_path, discussions_dir)
        rows = _edu_rows(db_path, transcript["session_id"])
        variant = [r for r in rows if r[2] == 1.0]
        assert variant, f"expected a clamped 1.0 score, got {rows}"

    def test_negative_score_clamped_to_zero(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-clamp-2")
        for event in transcript["events"]:
            if event.get("item_id") == "q1":
                event["score"] = -5.0
        _ingest(transcript, db_path, registry_path, discussions_dir)
        rows = _edu_rows(db_path, transcript["session_id"])
        assert any(r[2] == 0.0 and r[3] == 0 for r in rows)


# --------------------------------------------------------------------------- #
# Atomic rejection of malformed input
# --------------------------------------------------------------------------- #
def _registry_bytes(registry_path: Path) -> bytes:
    return registry_path.read_bytes()


def _assert_zero_writes(
    db_path: Path, discussions_dir: Path, registry_path: Path, registry_before: bytes
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM discussions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM education_results").fetchone()[0] == 0
    finally:
        conn.close()
    # No discussion directory was created.
    created = [p for date in discussions_dir.iterdir() for p in date.iterdir()]
    assert created == []
    # Registry byte-identical.
    assert registry_path.read_bytes() == registry_before


class TestAtomicRejection:
    @pytest.mark.parametrize(
        "mutate",
        [
            pytest.param(lambda t: t["events"][2].update(bloom="wisdom"), id="bad-enum"),
            pytest.param(lambda t: t.update(session_id="../evil"), id="path-traversal-session"),
            pytest.param(
                lambda t: t["events"].append({"type": "sabotage", "x": 1}), id="unknown-event"
            ),
            pytest.param(lambda t: t.update(contract_version=2), id="wrong-contract-version"),
            pytest.param(
                lambda t: t["events"][2].update(score="not-a-number"), id="non-numeric-score"
            ),
            pytest.param(lambda t: t.update(gate_id="../../etc/passwd"), id="path-traversal-gate"),
            pytest.param(lambda t: t.pop("outcome"), id="missing-top-key"),
        ],
    )
    def test_malformed_input_rejected_atomically(
        self,
        mutate,
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        tmp_path: Path,
    ) -> None:
        transcript = _full_transcript(session_id="GATE-bad")
        mutate(transcript)
        tpath = _write(tmp_path / "bad.json", transcript)
        before = _registry_bytes(registry_path)

        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 2
        _assert_zero_writes(db_path, discussions_dir, registry_path, before)

    def test_missing_gate_in_registry_exit_2_zero_writes(
        self, db_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        # Registry that does NOT contain the transcript's gate.
        other_registry = tmp_path / "other.yaml"
        reg.save_registry(
            {"version": 1, "gates": [_seed_gate(gate_id="EDU-somethingelse")]}, other_registry
        )
        before = other_registry.read_bytes()
        tpath = _write(tmp_path / "t.json", _full_transcript())

        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(other_registry),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 2
        _assert_zero_writes(db_path, discussions_dir, other_registry, before)

    def test_missing_gate_raises_gate_not_found_from_library(
        self, db_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        other_registry = tmp_path / "other.yaml"
        reg.save_registry(
            {"version": 1, "gates": [_seed_gate(gate_id="EDU-somethingelse")]}, other_registry
        )
        with pytest.raises(GateNotFoundError):
            _ingest(_full_transcript(), db_path, other_registry, discussions_dir)

    def test_invalid_json_rejected(
        self, db_path: Path, registry_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        tpath = tmp_path / "corrupt.json"
        tpath.write_text("{not json", encoding="utf-8")
        before = _registry_bytes(registry_path)
        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 2
        _assert_zero_writes(db_path, discussions_dir, registry_path, before)


# --------------------------------------------------------------------------- #
# Validation unit coverage
# --------------------------------------------------------------------------- #
class TestValidation:
    def test_valid_transcript_returns_same_object(self) -> None:
        transcript = _full_transcript()
        assert validate_transcript(transcript) is transcript

    def test_root_not_object(self) -> None:
        with pytest.raises(TranscriptValidationError, match="root must be an object"):
            validate_transcript([1, 2, 3])

    def test_unknown_top_key(self) -> None:
        transcript = _full_transcript()
        transcript["bogus"] = 1
        with pytest.raises(TranscriptValidationError, match="unknown keys"):
            validate_transcript(transcript)

    def test_bool_contract_version_rejected(self) -> None:
        transcript = _full_transcript()
        transcript["contract_version"] = True
        with pytest.raises(TranscriptValidationError, match="contract_version"):
            validate_transcript(transcript)

    def test_bad_mode(self) -> None:
        transcript = _full_transcript()
        transcript["mode"] = "cram"
        with pytest.raises(TranscriptValidationError, match="mode"):
            validate_transcript(transcript)

    def test_unparseable_timestamp(self) -> None:
        transcript = _full_transcript()
        transcript["started_at"] = "yesterday"
        with pytest.raises(TranscriptValidationError, match="ISO-8601"):
            validate_transcript(transcript)

    def test_events_not_list(self) -> None:
        transcript = _full_transcript()
        transcript["events"] = {}
        with pytest.raises(TranscriptValidationError, match="events must be a list"):
            validate_transcript(transcript)

    def test_event_missing_key(self) -> None:
        transcript = _full_transcript()
        del transcript["events"][0]["text"]
        with pytest.raises(TranscriptValidationError, match="missing keys"):
            validate_transcript(transcript)

    def test_quiz_bad_question_type(self) -> None:
        transcript = _full_transcript()
        transcript["events"][2]["question_type"] = "trickery"
        with pytest.raises(TranscriptValidationError, match="question_type"):
            validate_transcript(transcript)

    def test_variant_of_bad_type(self) -> None:
        transcript = _full_transcript()
        transcript["events"][2]["variant_of"] = 5
        with pytest.raises(TranscriptValidationError, match="variant_of"):
            validate_transcript(transcript)

    def test_two_session_deferrals_rejected(self) -> None:
        transcript = _full_transcript()
        transcript["events"].append({"type": "deferral", "scope": "session", "reason": "a"})
        transcript["events"].append({"type": "deferral", "scope": "session", "reason": "b"})
        transcript["outcome"] = {"status": "session-deferred"}
        with pytest.raises(TranscriptValidationError, match="at most one session-level deferral"):
            validate_transcript(transcript)

    def test_outcome_status_inconsistent_with_events(self) -> None:
        transcript = _full_transcript()
        transcript["outcome"] = {"status": "session-deferred"}  # but no session deferral event
        with pytest.raises(TranscriptValidationError, match="session-deferred"):
            validate_transcript(transcript)

    def test_deferral_bad_scope(self) -> None:
        transcript = _full_transcript()
        transcript["events"][4]["scope"] = "galaxy"
        with pytest.raises(TranscriptValidationError, match="scope"):
            validate_transcript(transcript)

    def test_load_transcript_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(TranscriptValidationError, match="cannot read"):
            load_transcript(tmp_path / "nope.json")


# --------------------------------------------------------------------------- #
# CLI plumbing
# --------------------------------------------------------------------------- #
class TestCli:
    def test_build_parser_smoke(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["t.json", "--db", "x.db"])
        assert args.transcript == "t.json"
        assert args.db == "x.db"

    def test_cli_idempotent_noop_message(
        self,
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tpath = _write(tmp_path / "t.json", _full_transcript())
        argv = [
            str(tpath),
            "--db",
            str(db_path),
            "--registry",
            str(registry_path),
            "--discussions-dir",
            str(discussions_dir),
        ]
        assert run(argv) == 0
        capsys.readouterr()
        assert run(argv) == 0
        assert "already ingested" in capsys.readouterr().out

    def test_cli_via_subprocess(
        self, db_path: Path, registry_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        tpath = _write(tmp_path / "t.json", _full_transcript())
        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "outcome=clear-eligible" in result.stdout


# --------------------------------------------------------------------------- #
# Compensation (post-write failure rolls everything back)
# --------------------------------------------------------------------------- #
class TestCompensation:
    def test_registry_save_failure_rolls_back(
        self,
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The re-defer flip is the ONLY automatic registry write left (a passing
        # transcript no longer touches the registry — ADR-0035), so the
        # save-failure path is exercised with a session-level deferral.
        import scripts.education.ingest_walkthrough_session as mod

        def _boom(*_a: Any, **_k: Any) -> None:
            raise OSError("registry save failed")

        monkeypatch.setattr(mod._reg, "save_registry", _boom)
        transcript = _full_transcript(session_id="GATE-comp-1")
        transcript["events"].append(
            {"type": "deferral", "scope": "session", "reason": "compensation probe"}
        )
        transcript["outcome"] = {"status": "session-deferred"}
        with pytest.raises(OSError, match="registry save failed"):
            _ingest(transcript, db_path, registry_path, discussions_dir)

        # All-or-nothing: discussion + rows removed, registry untouched.
        conn = sqlite3.connect(str(db_path))
        try:
            assert conn.execute("SELECT COUNT(*) FROM discussions").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM education_results").fetchone()[0] == 0
        finally:
            conn.close()
        created = [p for date in discussions_dir.iterdir() for p in date.iterdir()]
        assert created == []
        assert reg.get_gate(reg.load_registry(registry_path), GATE_ID)["status"] == "open"


# --------------------------------------------------------------------------- #
# Review-fold additions (REV panel, 2026-07-15)
# --------------------------------------------------------------------------- #
def _deferral_only_transcript(session_id: str = "GATE-defer-only") -> dict[str, Any]:
    """A session-level deferral before ANY narration/quiz/explain-back.

    Produces ZERO education_results rows — the transcript shape that escaped the
    original row-based idempotency guard (arch finding A4).
    """
    return {
        "contract_version": 1,
        "session_id": session_id,
        "gate_id": GATE_ID,
        "repo_slug": "owner/agent_framework_template",
        "mode": "gate",
        "started_at": "2026-07-15T14:00:00+00:00",
        "completed_at": "2026-07-15T14:01:00+00:00",
        "events": [
            {"type": "deferral", "scope": "session", "reason": "phone rang immediately"},
        ],
        "outcome": {"status": "session-deferred"},
    }


class TestLearnModePrecedence:
    """[arch A2] mode == gate is a precondition for ANY registry action."""

    def test_learn_mode_session_deferral_never_touches_registry(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="LEARN-defer-1", mode="learn")
        transcript["events"].append(
            {"type": "deferral", "scope": "session", "reason": "learn-mode bail-out"}
        )
        transcript["outcome"] = {"status": "session-deferred"}
        registry_before = registry_path.read_bytes()

        result = _ingest(transcript, db_path, registry_path, discussions_dir)

        assert result.outcome == "recorded-open"
        # Registry byte-identical: learn-mode never re-defers, never clears.
        assert registry_path.read_bytes() == registry_before
        assert reg.get_gate(reg.load_registry(registry_path), GATE_ID)["status"] == "open"


class TestZeroRowIdempotency:
    """[arch A4] events-only sessions are caught by the discussion-slug guard."""

    def test_deferral_only_rerun_is_noop(
        self,
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        transcript = _deferral_only_transcript()
        tpath = _write(tmp_path / "defer.json", transcript)
        argv = [
            str(tpath),
            "--db",
            str(db_path),
            "--registry",
            str(registry_path),
            "--discussions-dir",
            str(discussions_dir),
        ]
        assert run(argv) == 0
        capsys.readouterr()

        # Zero education rows were produced — the A4 escape shape.
        assert _edu_rows(db_path, transcript["session_id"]) == []

        # Re-run: exit 0 no-op, no duplicate discussion.
        assert run(argv) == 0
        out = capsys.readouterr().out
        assert "already ingested" in out
        assert f"session_id={transcript['session_id']}" in out

        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM discussions").fetchone()[0]
        finally:
            conn.close()
        assert count == 1
        created = [p for date in discussions_dir.iterdir() for p in date.iterdir()]
        assert len(created) == 1


class TestBelowThresholdIdempotency:
    """[qa Q3] a recorded-open session is a no-op on re-run via the row guard."""

    def test_below_threshold_rerun_is_noop(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-low-rerun")
        transcript["events"] = [e for e in transcript["events"] if e.get("item_id") != "q1v1"]
        first = _ingest(transcript, db_path, registry_path, discussions_dir)
        assert first.outcome == "recorded-open"
        rows_after_first = _edu_rows(db_path, transcript["session_id"])

        second = _ingest(transcript, db_path, registry_path, discussions_dir)
        assert second.changed is False
        assert second.outcome == "already-ingested"
        # No duplicate rows.
        assert _edu_rows(db_path, transcript["session_id"]) == rows_after_first
        assert reg.get_gate(reg.load_registry(registry_path), GATE_ID)["status"] == "open"


class TestVariantChain:
    """[qa Q4] multi-level variant chains: only the terminal item counts."""

    def test_only_terminal_variant_counts(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-chain-1")

        def _quiz(item_id: str, score: float, variant_of: str | None) -> dict[str, Any]:
            return {
                "type": "quiz_item",
                "item_id": item_id,
                "question": f"ask {item_id}",
                "answer": f"answer {item_id}",
                "score": score,
                "bloom": "apply",
                "question_type": "change-impact",
                "variant_of": variant_of,
            }

        # Replace the default quiz pair with a 3-deep chain:
        # q1(0.2) <- q1v1(0.4) <- q1v2(0.9).
        transcript["events"] = [e for e in transcript["events"] if e.get("type") != "quiz_item"]
        transcript["events"][1:1] = [
            _quiz("q1", 0.2, None),
            _quiz("q1v1", 0.4, "q1"),
            _quiz("q1v2", 0.9, "q1v1"),
        ]

        result = _ingest(transcript, db_path, registry_path, discussions_dir)
        # Terminal average = 0.9 (q1 and q1v1 both superseded) -> clear-eligible.
        assert result.outcome == "clear-eligible"
        # All three attempts are still individually recorded.
        rows = _edu_rows(db_path, transcript["session_id"])
        chain_scores = [r[2] for r in rows if r[1] == "change-impact"]
        assert chain_scores == [0.2, 0.4, 0.9]


class TestResourceCaps:
    """[sec S1] resource caps on untrusted input -> exit-2 atomic rejection."""

    def _run_expect_reject(
        self,
        transcript: dict[str, Any],
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        tmp_path: Path,
    ) -> None:
        tpath = _write(tmp_path / "capped.json", transcript)
        before = registry_path.read_bytes()
        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 2
        _assert_zero_writes(db_path, discussions_dir, registry_path, before)

    def test_oversized_file_rejected(
        self, db_path: Path, registry_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        tpath = tmp_path / "huge.json"
        tpath.write_bytes(b"0" * (MAX_TRANSCRIPT_BYTES + 1))
        before = registry_path.read_bytes()
        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 2
        _assert_zero_writes(db_path, discussions_dir, registry_path, before)

    def test_too_many_events_rejected(
        self, db_path: Path, registry_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-flood")
        narration = {"type": "narration", "chapter_id": "chX", "text": "spam"}
        transcript["events"] = [dict(narration) for _ in range(MAX_EVENTS + 1)]
        transcript["outcome"] = {"status": "completed"}
        self._run_expect_reject(transcript, db_path, registry_path, discussions_dir, tmp_path)

    def test_oversized_string_field_rejected(
        self, db_path: Path, registry_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        transcript = _full_transcript(session_id="GATE-bigtext")
        transcript["events"][0]["text"] = "x" * (MAX_TEXT_LEN + 1)
        self._run_expect_reject(transcript, db_path, registry_path, discussions_dir, tmp_path)

    def test_oversized_id_rejected(
        self, db_path: Path, registry_path: Path, discussions_dir: Path, tmp_path: Path
    ) -> None:
        transcript = _full_transcript(session_id="a" * 129)  # charset-valid, too long
        self._run_expect_reject(transcript, db_path, registry_path, discussions_dir, tmp_path)


class TestEnumSingleSource:
    """[qa Q1] pin BLOOM_LEVELS/QUESTION_TYPES to the live education_results DDL."""

    @staticmethod
    def _check_values(ddl: str, column: str) -> set[str]:
        import re

        match = re.search(rf"CHECK\s*\(\s*{column}\s+IN\s*\(([^)]*)\)", ddl)
        assert match, f"no CHECK constraint found for {column}"
        return set(re.findall(r"'([^']+)'", match.group(1)))

    def test_enums_match_live_ddl(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='education_results'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert self._check_values(ddl, "bloom_level") == set(BLOOM_LEVELS)
        assert self._check_values(ddl, "question_type") == set(QUESTION_TYPES)


class TestConformanceFixture:
    """[ip IP3] the committed golden fixture validates and ingests successfully."""

    def test_fixture_exists_and_validates(self) -> None:
        transcript = load_transcript(FIXTURE_PATH)
        assert transcript["contract_version"] == 1
        assert transcript["gate_id"] == GATE_ID
        types = [e["type"] for e in transcript["events"]]
        # All five shapes present (the conformance guarantee).
        assert {"narration", "qa_exchange", "quiz_item", "explain_back", "deferral"} <= set(types)

    def test_fixture_ingests_and_is_clear_eligible(
        self, db_path: Path, registry_path: Path, discussions_dir: Path
    ) -> None:
        transcript = load_transcript(FIXTURE_PATH)
        result = _ingest(transcript, db_path, registry_path, discussions_dir)
        assert result.outcome == "clear-eligible"
        # The registry is NOT flipped by the ingest (ADR-0035): the fixture's
        # passing session leaves the gate open, with the developer command built.
        gate = reg.get_gate(reg.load_registry(registry_path), GATE_ID)
        assert gate["status"] == "open"
        assert gate["cleared_by"] is None
        assert transcript["session_id"] in (result.clear_command or "")


class TestStdoutDiscipline:
    """[sec S3] the CLI emits ONLY the ingest's own lines on success.

    The original pin was "exactly one line". Since ADR-0035 a clear-eligible run
    also prints the eligibility block and the developer's clear command — the
    ingest's own, deliberate output. What S3 actually guards is the FOREIGN leak
    (create_discussion printing its discussion id into the watcher's stdout), so
    that is what stays pinned: the machine summary line comes first, every line
    is one of the ingest's own, and no bare discussion id leaks.
    """

    def test_summary_line_first_and_no_foreign_output(
        self,
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tpath = _write(tmp_path / "t.json", _full_transcript(session_id="GATE-stdout-1"))
        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 0
        out_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
        # The machine-readable summary is still the first line, unchanged in shape.
        assert out_lines[0].startswith(f"Ingested gate {GATE_ID}:")
        # create_discussion's own print stays suppressed: no bare discussion-id line.
        assert not any(line.strip().startswith("DISC-") for line in out_lines)
        # Every line is the ingest's own known output, nothing foreign in between.
        own_prefixes = (
            f"Ingested gate {GATE_ID}:",
            f"Gate {GATE_ID} is CLEAR-ELIGIBLE",
            "Marked clear-eligible",
            "  python scripts/education/gate_registry.py",
        )
        for line in out_lines:
            assert line.startswith(own_prefixes), f"foreign stdout line leaked: {line!r}"

    def test_recorded_open_stays_single_line(
        self,
        db_path: Path,
        registry_path: Path,
        discussions_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A non-eligible run keeps the original one-line discipline exactly."""
        transcript = _full_transcript(session_id="GATE-stdout-2")
        transcript["events"] = [e for e in transcript["events"] if e.get("item_id") != "q1v1"]
        tpath = _write(tmp_path / "t2.json", transcript)
        rc = run(
            [
                str(tpath),
                "--db",
                str(db_path),
                "--registry",
                str(registry_path),
                "--discussions-dir",
                str(discussions_dir),
            ]
        )
        assert rc == 0
        out_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
        assert len(out_lines) == 1
        assert out_lines[0].startswith(f"Ingested gate {GATE_ID}:")
        assert "outcome=recorded-open" in out_lines[0]
