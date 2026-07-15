"""Tests for scripts/education/ingest_walkthrough_session.py.

The ingest boundary is safety-relevant (untrusted transcripts → capture
pipeline + gate flips), so per testing_requirements the guards ship with the
capability: every rejection path, the end-to-end synthetic ingest, idempotency,
and no-partial-write-on-reject are covered here.
"""

import copy
import json
import sqlite3

import pytest
import yaml

from scripts.education import ingest_walkthrough_session as ingest_module
from scripts.education.gate_registry import RegistryError, load_registry
from scripts.education.ingest_walkthrough_session import (
    TranscriptError,
    ingest,
    validate_transcript,
)
from scripts.init_db import init_db


def make_transcript(**overrides) -> dict:
    """A valid gate-mode transcript covering every event type."""
    transcript = {
        "contract_version": 1,
        "session_id": "VWALK-20260715-063000",
        "client": "phone",
        "mode": "gate",
        "gate_id": "GATE-0001",
        "repo": "example/repo",
        "course_id": "CURR-test",
        "chapter": {"number": 6, "slug": "education-system", "title": "The education system"},
        "narration_completed": True,
        "quiz_summary": {"pass_threshold": 0.70, "average": 0.9},
        "events": [
            {"type": "narration", "section": "01", "text": "Welcome to chapter six."},
            {"type": "question", "text": "Why no education row from /walkthrough?"},
            {"type": "answer", "text": "Only /quiz records rows today."},
            {"type": "parked_question", "text": "Show me the CHECK constraint SQL."},
            {
                "type": "quiz_question",
                "qid": "q1",
                "bloom_level": "understand",
                "question_type": "recall",
                "text": "Where do quiz results land?",
            },
            {"type": "quiz_answer", "qid": "q1", "text": "education_results."},
            {"type": "quiz_grade", "qid": "q1", "score": 1.0, "feedback": "Right."},
            {
                "type": "quiz_question",
                "qid": "q2",
                "bloom_level": "analyze",
                "question_type": "debug-scenario",
                "text": "A quiz row violates the CHECK — what happened?",
            },
            {"type": "quiz_answer", "qid": "q2", "text": "Score out of range."},
            {"type": "quiz_grade", "qid": "q2", "score": 0.8, "feedback": "Mostly."},
            {"type": "explain_back_prompt", "text": "Why does a human stay in the loop?"},
            {"type": "explain_back_answer", "text": "Unmediated promotion is extraction."},
            {"type": "explain_back_grade", "score": 0.9, "feedback": "Pass."},
        ],
    }
    transcript.update(overrides)
    return transcript


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated DB + discussions dir + registry, with capture modules repointed."""
    db_path = tmp_path / "evaluation.db"
    init_db(db_path)
    discussions = tmp_path / "discussions"
    discussions.mkdir()
    registry_path = tmp_path / "gates.yaml"
    registry = {
        "version": 1,
        "gates": [
            {
                "gate_id": "GATE-0001",
                "title": "Test gate",
                "created_at": "2026-07-15T00:00:00+00:00",
                "origin": "build",
                "scope": {"files": [], "adrs": [], "spec": None},
                "reason_deferred": "test",
                "status": "open",
                "deferrals": [],
                "attempts": [],
                "cleared_by": None,
                "cleared_at": None,
                "discussion_id": None,
            }
        ],
    }
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(registry, f)

    monkeypatch.setattr(ingest_module.create_discussion_module, "DISCUSSIONS_DIR", discussions)
    monkeypatch.setattr(ingest_module.create_discussion_module, "DB_PATH", db_path)
    monkeypatch.setattr(ingest_module.write_event_module, "DISCUSSIONS_DIR", discussions)
    return {"db": db_path, "discussions": discussions, "registry": registry_path}


def run_ingest(env, transcript):
    return ingest(transcript, db_path=env["db"], registry_path=env["registry"], close=False)


def education_rows(db_path):
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT session_id, bloom_level, question_type, score, passed FROM education_results"
    ).fetchall()
    conn.close()
    return rows


def read_events(env):
    dirs = [d for date in env["discussions"].iterdir() for d in date.iterdir()]
    assert len(dirs) == 1
    with open(dirs[0] / "events.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestValidation:
    def test_valid_transcript_passes(self):
        validate_transcript(make_transcript())

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"contract_version": 2}, "contract_version"),
            ({"session_id": "WALK-1"}, "session_id"),
            ({"client": "watch"}, "client"),
            ({"mode": "cram"}, "mode"),
            ({"mode": "gate", "gate_id": "gate-1"}, "gate_id"),
            ({"narration_completed": False}, "narration_completed"),
            ({"chapter": "six"}, "chapter"),
            ({"events": []}, "events"),
            ({"quiz_summary": {"pass_threshold": 1.5}}, "pass_threshold"),
        ],
    )
    def test_top_level_rejections(self, overrides, message):
        with pytest.raises(TranscriptError, match=message):
            validate_transcript(make_transcript(**overrides))

    def test_unknown_event_type_rejected(self):
        transcript = make_transcript()
        transcript["events"].append({"type": "exploit", "text": "x"})
        with pytest.raises(TranscriptError, match="unknown type"):
            validate_transcript(transcript)

    def test_bad_bloom_level_rejected(self):
        transcript = make_transcript()
        transcript["events"][4]["bloom_level"] = "memorize"
        with pytest.raises(TranscriptError, match="bloom_level"):
            validate_transcript(transcript)

    def test_bad_question_type_rejected(self):
        transcript = make_transcript()
        transcript["events"][4]["question_type"] = "gotcha"
        with pytest.raises(TranscriptError, match="question_type"):
            validate_transcript(transcript)

    def test_score_out_of_range_rejected(self):
        transcript = make_transcript()
        transcript["events"][6]["score"] = 1.2
        with pytest.raises(TranscriptError, match=r"\[0, 1\]"):
            validate_transcript(transcript)

    def test_grade_for_unknown_qid_rejected(self):
        transcript = make_transcript()
        transcript["events"].append({"type": "quiz_grade", "qid": "q9", "score": 1.0})
        with pytest.raises(TranscriptError, match="unknown qid"):
            validate_transcript(transcript)

    def test_duplicate_qid_rejected(self):
        transcript = make_transcript()
        transcript["events"].append(
            {
                "type": "quiz_question",
                "qid": "q1",
                "bloom_level": "understand",
                "question_type": "recall",
                "text": "A second question reusing q1.",
            }
        )
        with pytest.raises(TranscriptError, match="duplicate qid"):
            validate_transcript(transcript)

    def test_boolean_score_rejected(self):
        # isinstance(True, int) is True in Python; the explicit bool exclusion
        # in _require_score is the only thing stopping score:true from passing.
        transcript = make_transcript()
        transcript["events"][6]["score"] = True
        with pytest.raises(TranscriptError, match="must be a number"):
            validate_transcript(transcript)

    def test_negative_score_rejected(self):
        transcript = make_transcript()
        transcript["events"][6]["score"] = -0.1
        with pytest.raises(TranscriptError, match=r"\[0, 1\]"):
            validate_transcript(transcript)

    def test_event_cap_rejected(self):
        transcript = make_transcript()
        transcript["events"] = [
            {"type": "narration", "text": f"chunk {i}"}
            for i in range(ingest_module.MAX_EVENTS + 1)
        ]
        with pytest.raises(TranscriptError, match="event cap"):
            validate_transcript(transcript)

    def test_empty_text_rejected(self):
        transcript = make_transcript()
        transcript["events"][0]["text"] = "  "
        with pytest.raises(TranscriptError, match="non-empty"):
            validate_transcript(transcript)

    def test_oversized_text_rejected(self):
        transcript = make_transcript()
        transcript["events"][0]["text"] = "x" * (ingest_module.MAX_TEXT_LEN + 1)
        with pytest.raises(TranscriptError, match="exceeds"):
            validate_transcript(transcript)

    def test_threshold_floor_not_client_nullable(self):
        # A client must not be able to nullify the bar (review finding):
        # pass_threshold below MIN_PASS_THRESHOLD is rejected.
        transcript = make_transcript(quiz_summary={"pass_threshold": 0.01})
        with pytest.raises(TranscriptError, match="pass_threshold"):
            validate_transcript(transcript)

    def test_claimed_average_cross_checked(self):
        # Grades are 1.0 and 0.8 (avg 0.9); a claimed average of 0.5 is inconsistent.
        transcript = make_transcript(quiz_summary={"pass_threshold": 0.7, "average": 0.5})
        with pytest.raises(TranscriptError, match="inconsistent"):
            validate_transcript(transcript)

    def test_chapter_number_type_confusion_rejected(self):
        transcript = make_transcript()
        transcript["chapter"]["number"] = "6; rm -rf"
        with pytest.raises(TranscriptError, match="chapter.number"):
            validate_transcript(transcript)

    def test_total_text_cap_rejected(self):
        transcript = make_transcript()
        chunk = "x" * ingest_module.MAX_TEXT_LEN
        needed = ingest_module.MAX_TOTAL_TEXT // ingest_module.MAX_TEXT_LEN + 1
        transcript["events"] = [{"type": "narration", "text": chunk} for _ in range(needed)]
        with pytest.raises(TranscriptError, match="total transcript text"):
            validate_transcript(transcript)

    def test_ansi_and_control_chars_stripped_before_write(self, env):
        # Terminal-injection guard (security review): ANSI CSI/OSC sequences and
        # control chars in any free-text field must never reach events.jsonl or
        # gates.yaml. Removing sanitize_transcript from ingest() fails this test.
        transcript = make_transcript()
        transcript["events"] = [
            {
                "type": "narration",
                "text": "clean \x1b[31mred\x1b[0m bell\x07 null\x00 keep\nnewline",
            },
            {"type": "deferral", "text": "defer \x1b]0;spoof\x07 reason"},
        ]
        run_ingest(env, transcript)
        events = read_events(env)
        narration = events[0]["content"]
        assert "\x1b" not in narration and "\x07" not in narration and "\x00" not in narration
        assert "clean red bell null keep\nnewline" == narration
        gate = load_registry(env["registry"])["gates"][0]
        assert gate["deferrals"][-1]["reason"] == "defer  reason"

    def test_all_defects_listed(self):
        transcript = make_transcript(contract_version=9, client="watch")
        with pytest.raises(TranscriptError) as excinfo:
            validate_transcript(transcript)
        assert "contract_version" in str(excinfo.value)
        assert "client" in str(excinfo.value)


class TestEndToEnd:
    def test_gate_mode_full_ingest(self, env):
        result = run_ingest(env, make_transcript())
        assert result["skipped"] is False
        assert result["gate_cleared"] is True
        assert result["quiz_average"] == pytest.approx(0.9)
        assert result["parked_questions"] == ["Show me the CHECK constraint SQL."]

        # education_results: 2 quiz + 1 explain-back + 1 narration = 4 rows
        rows = education_rows(env["db"])
        assert len(rows) == 4
        assert result["rows_recorded"] == 4
        kinds = {(r[1], r[2]) for r in rows}
        assert ("understand", "recall") in kinds
        assert ("analyze", "debug-scenario") in kinds
        assert ("evaluate", "explain-back") in kinds
        assert ("understand", "walkthrough") in kinds
        assert all(r[0] == "VWALK-20260715-063000" for r in rows)

        # Layer-1 events: mapping spot-checks
        events = read_events(env)
        narration = events[0]
        assert (narration["agent"], narration["intent"]) == ("educator", "proposal")
        assert "walkthrough" in narration["tags"] and "chapter-06" in narration["tags"]
        question = events[1]
        assert (question["agent"], question["intent"]) == ("developer", "question")
        answer = events[2]
        assert answer["reply_to"] == question["turn_id"]
        assert events[-1]["intent"] == "synthesis"
        assert any("parked" in e["tags"] for e in events)

        # Registry flipped with evidence pointers
        registry = load_registry(env["registry"])
        gate = registry["gates"][0]
        assert gate["status"] == "cleared"
        assert gate["cleared_by"] == "VWALK-20260715-063000"
        assert gate["discussion_id"] == result["discussion_id"]
        assert gate["attempts"][-1]["passed"] is True

    def test_idempotent_rerun(self, env):
        transcript = make_transcript()
        # Re-open the gate scenario: first run clears it; use a learn re-run check
        # on the same session instead — rows must not double.
        run_ingest(env, transcript)
        result = run_ingest(env, copy.deepcopy(transcript))
        assert result["skipped"] is True
        assert "already" in result["reason"]
        assert len(education_rows(env["db"])) == 4

    def test_learn_mode_never_touches_registry(self, env):
        before = env["registry"].read_bytes()
        transcript = make_transcript(mode="learn")
        transcript.pop("gate_id")
        result = run_ingest(env, transcript)
        assert result["skipped"] is False
        assert result["gate_cleared"] is None
        assert env["registry"].read_bytes() == before

    def test_failing_quiz_records_attempt_but_keeps_gate_open(self, env):
        transcript = make_transcript(quiz_summary={"pass_threshold": 0.7})
        for event in transcript["events"]:
            if event["type"] == "quiz_grade":
                event["score"] = 0.4
        result = run_ingest(env, transcript)
        assert result["gate_cleared"] is False
        gate = load_registry(env["registry"])["gates"][0]
        assert gate["status"] == "open"
        assert gate["attempts"][-1]["passed"] is False
        # Failed items recorded honestly (passed=0)
        rows = education_rows(env["db"])
        failed = [r for r in rows if r[2] in ("recall", "debug-scenario")]
        assert all(r[4] == 0 for r in failed)

    def test_deferral_redefers_gate(self, env):
        transcript = make_transcript()
        transcript["events"] = [
            {"type": "narration", "text": "Chapter narration."},
            {"type": "deferral", "text": "Quiz saved for the next walk."},
        ]
        result = run_ingest(env, transcript)
        assert result["gate_cleared"] is False
        gate = load_registry(env["registry"])["gates"][0]
        assert gate["status"] == "re-deferred"
        assert gate["deferrals"][-1]["reason"] == "Quiz saved for the next walk."

    def test_already_cleared_gate_skips(self, env):
        run_ingest(env, make_transcript())
        second = make_transcript(session_id="VWALK-20260715-070000")
        result = run_ingest(env, second)
        assert result["skipped"] is True
        assert "already cleared" in result["reason"]
        assert len(education_rows(env["db"])) == 4  # no new rows

    def test_unknown_gate_rejects_before_any_write(self, env):
        transcript = make_transcript(gate_id="GATE-9999")
        with pytest.raises(RegistryError, match="not found"):
            run_ingest(env, transcript)
        assert education_rows(env["db"]) == []
        assert not any(env["discussions"].iterdir())

    def test_invalid_transcript_writes_nothing(self, env):
        transcript = make_transcript()
        transcript["events"][6]["score"] = 5.0
        before = env["registry"].read_bytes()
        with pytest.raises(TranscriptError):
            run_ingest(env, transcript)
        assert education_rows(env["db"]) == []
        assert not any(env["discussions"].iterdir())
        assert env["registry"].read_bytes() == before

    def test_cli_missing_file_exits_1(self, tmp_path, monkeypatch, capsys):
        import sys

        monkeypatch.setattr(sys, "argv", ["ingest", str(tmp_path / "missing.json")])
        with pytest.raises(SystemExit) as excinfo:
            ingest_module.main()
        assert excinfo.value.code == 1
        assert "Could not read" in capsys.readouterr().out

    def test_cli_invalid_json_exits_1(self, tmp_path, monkeypatch, capsys):
        import sys

        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["ingest", str(bad)])
        with pytest.raises(SystemExit) as excinfo:
            ingest_module.main()
        assert excinfo.value.code == 1

    def test_cli_invalid_transcript_exits_1_before_writes(self, tmp_path, monkeypatch, capsys):
        import sys

        transcript = make_transcript(contract_version=9)
        path = tmp_path / "t.json"
        path.write_text(json.dumps(transcript), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["ingest", str(path), "--no-close"])
        with pytest.raises(SystemExit) as excinfo:
            ingest_module.main()
        assert excinfo.value.code == 1
        assert "contract_version" in capsys.readouterr().out

    def test_close_failure_does_not_fail_ingest(self, env, monkeypatch, capsys):
        def boom(_):
            raise RuntimeError("sealing exploded")

        monkeypatch.setattr(ingest_module, "seal_discussion", boom)
        result = ingest(
            make_transcript(), db_path=env["db"], registry_path=env["registry"], close=True
        )
        assert result["skipped"] is False
        assert "sealing failed" in capsys.readouterr().out
