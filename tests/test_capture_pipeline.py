"""Unit tests for the capture pipeline scripts.

Tests all Layer 1 (file) and Layer 2 (SQLite) capture operations
independently from Claude Code. Proves the plumbing works correctly.
"""

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

# Add scripts directory to path so we can import the modules
TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT / "scripts"))

from create_discussion import create_discussion
from generate_transcript import generate_transcript
from ingest_events import ingest_events
from init_db import init_db
from record_education import record_education
from write_event import find_discussion_dir, write_event


@pytest.fixture
def pipeline_env(tmp_path, monkeypatch):
    """Set up an isolated environment with discussions dir and SQLite DB."""
    discussions_dir = tmp_path / "discussions"
    discussions_dir.mkdir()
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    db_path = metrics_dir / "evaluation.db"

    # Initialize the database
    init_db(db_path)

    # Monkeypatch the module-level constants in all scripts
    import create_discussion as cd_mod
    import generate_transcript as gt_mod
    import ingest_events as ie_mod
    import record_education as re_mod
    import write_event as we_mod

    monkeypatch.setattr(cd_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(cd_mod, "DB_PATH", db_path)
    monkeypatch.setattr(we_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(gt_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(ie_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(ie_mod, "DB_PATH", db_path)
    monkeypatch.setattr(re_mod, "DB_PATH", db_path)

    return {
        "tmp_path": tmp_path,
        "discussions_dir": discussions_dir,
        "db_path": db_path,
    }


# ============================================================
# init_db tests
# ============================================================


class TestInitDb:
    """Tests for scripts/init_db.py."""

    def test_creates_all_tables(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()

        expected = {"discussions", "turns", "decisions", "reflections", "education_results"}
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_creates_indexes(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        conn.close()

        expected_indexes = {
            "idx_turns_discussion",
            "idx_turns_agent",
            "idx_turns_timestamp",
            "idx_decisions_discussion",
            "idx_reflections_discussion",
            "idx_reflections_agent",
            "idx_education_session",
            "idx_education_discussion",
            "idx_discussions_status",
            "idx_discussions_created",
        }
        assert expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}"

    def test_idempotent(self, tmp_path):
        """Running init_db twice should not fail."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        init_db(db_path)  # Should not raise

        conn = sqlite3.connect(str(db_path))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        assert len(tables) >= 5


# ============================================================
# create_discussion tests
# ============================================================


class TestCreateDiscussion:
    """Tests for scripts/create_discussion.py."""

    def test_produces_correct_structure(self, pipeline_env):
        disc_id = create_discussion("test-topic", "medium", "structured-dialogue")

        disc_dir = find_discussion_dir(disc_id)
        assert disc_dir.exists()
        assert (disc_dir / "events.jsonl").exists()
        assert (disc_dir / "events.jsonl").stat().st_size == 0
        assert (disc_dir / "artifacts").exists()

    def test_id_format(self, pipeline_env):
        disc_id = create_discussion("my-feature")
        pattern = r"^DISC-\d{8}-\d{6}-my-feature$"
        assert re.match(pattern, disc_id), f"ID '{disc_id}' doesn't match expected format"

    def test_registers_in_sqlite(self, pipeline_env):
        disc_id = create_discussion("db-test", "high", "dialectic", "high")

        conn = sqlite3.connect(str(pipeline_env["db_path"]))
        row = conn.execute(
            "SELECT discussion_id, status, risk_level, collaboration_mode, exploration_intensity "
            "FROM discussions WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == disc_id
        assert row[1] == "open"
        assert row[2] == "high"
        assert row[3] == "dialectic"
        assert row[4] == "high"

    def test_directory_under_date_folder(self, pipeline_env):
        disc_id = create_discussion("date-test")
        disc_dir = find_discussion_dir(disc_id)
        # Parent should be a date-formatted directory
        date_dir = disc_dir.parent
        assert re.match(r"\d{4}-\d{2}-\d{2}", date_dir.name)


# ============================================================
# write_event tests
# ============================================================


class TestWriteEvent:
    """Tests for scripts/write_event.py."""

    def test_appends_valid_jsonl(self, pipeline_env):
        disc_id = create_discussion("jsonl-test")
        write_event(disc_id, "qa-specialist", "proposal", "Test finding.")

        disc_dir = find_discussion_dir(disc_id)
        events_path = disc_dir / "events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()

        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["discussion_id"] == disc_id
        assert event["agent"] == "qa-specialist"
        assert event["intent"] == "proposal"
        assert event["content"] == "Test finding."
        assert event["turn_id"] == 1
        assert event["reply_to"] is None

    def test_increments_turn_id(self, pipeline_env):
        disc_id = create_discussion("turn-test")
        t1 = write_event(disc_id, "agent-a", "proposal", "First.")
        t2 = write_event(disc_id, "agent-b", "proposal", "Second.")
        t3 = write_event(disc_id, "agent-c", "critique", "Third.", reply_to=1)

        assert t1 == 1
        assert t2 == 2
        assert t3 == 3

    def test_preserves_reply_to(self, pipeline_env):
        disc_id = create_discussion("reply-test")
        write_event(disc_id, "agent-a", "proposal", "Original.")
        write_event(disc_id, "agent-b", "critique", "Response.", reply_to=1)

        disc_dir = find_discussion_dir(disc_id)
        lines = (disc_dir / "events.jsonl").read_text().strip().splitlines()
        event2 = json.loads(lines[1])
        assert event2["reply_to"] == 1

    def test_validates_intent(self, pipeline_env):
        disc_id = create_discussion("intent-test")
        with pytest.raises(ValueError, match="Invalid intent"):
            write_event(disc_id, "agent", "invalid-intent", "Content.")

    def test_preserves_tags_and_risk_flags(self, pipeline_env):
        disc_id = create_discussion("tags-test")
        write_event(
            disc_id,
            "security-specialist",
            "proposal",
            "Finding.",
            tags=["auth", "owasp"],
            risk_flags=["injection-risk"],
        )

        disc_dir = find_discussion_dir(disc_id)
        lines = (disc_dir / "events.jsonl").read_text().strip().splitlines()
        event = json.loads(lines[0])
        assert event["tags"] == ["auth", "owasp"]
        assert event["risk_flags"] == ["injection-risk"]

    def test_confidence_stored(self, pipeline_env):
        disc_id = create_discussion("conf-test")
        write_event(disc_id, "agent", "proposal", "Content.", confidence=0.92)

        disc_dir = find_discussion_dir(disc_id)
        lines = (disc_dir / "events.jsonl").read_text().strip().splitlines()
        event = json.loads(lines[0])
        assert event["confidence"] == 0.92

    def test_special_characters_in_content(self, pipeline_env):
        disc_id = create_discussion("special-test")
        content = 'Unicode: ñ ü 🚀 | Quotes: "hello" | JSON: {"key": "value"}'
        write_event(disc_id, "agent", "proposal", content)

        disc_dir = find_discussion_dir(disc_id)
        lines = (disc_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        event = json.loads(lines[0])
        assert event["content"] == content

    def test_newline_in_content(self, pipeline_env):
        """Verify content with actual newlines survives JSON round-trip."""
        disc_id = create_discussion("newline-test")
        content = "line1\nline2\nline3"
        write_event(disc_id, "agent", "proposal", content)

        disc_dir = find_discussion_dir(disc_id)
        raw = (disc_dir / "events.jsonl").read_text(encoding="utf-8").strip()
        # JSONL should be a single line (newlines escaped inside JSON string)
        assert raw.count("\n") == 0, "JSONL event should be a single line"
        event = json.loads(raw)
        assert event["content"] == content

    def test_nonexistent_discussion_raises(self, pipeline_env):
        with pytest.raises(FileNotFoundError):
            write_event("DISC-99999999-999999-nonexistent", "agent", "proposal", "Content.")


# ============================================================
# generate_transcript tests
# ============================================================


class TestGenerateTranscript:
    """Tests for scripts/generate_transcript.py."""

    def test_produces_valid_markdown(self, pipeline_env):
        disc_id = create_discussion("transcript-test")
        write_event(disc_id, "qa-specialist", "proposal", "Coverage needs improvement.")
        write_event(disc_id, "facilitator", "synthesis", "Agreed on coverage targets.")

        transcript_path = generate_transcript(disc_id)

        assert transcript_path.exists()
        content = transcript_path.read_text(encoding="utf-8")

        # Check YAML frontmatter
        assert content.startswith("---\n")
        assert f"discussion_id: {disc_id}" in content
        assert "total_turns: 2" in content
        assert "qa-specialist" in content
        assert "facilitator" in content

        # Check turns are present
        assert "Turn 1" in content
        assert "Turn 2" in content
        assert "Coverage needs improvement." in content
        assert "Agreed on coverage targets." in content

    def test_empty_events_produces_minimal_transcript(self, pipeline_env):
        disc_id = create_discussion("empty-test")
        transcript_path = generate_transcript(disc_id)
        content = transcript_path.read_text()
        assert f"discussion_id: {disc_id}" in content


# ============================================================
# ingest_events tests
# ============================================================


class TestIngestEvents:
    """Tests for scripts/ingest_events.py."""

    def test_populates_turns_table(self, pipeline_env):
        disc_id = create_discussion("ingest-test")
        write_event(disc_id, "qa-specialist", "proposal", "Finding 1.", confidence=0.85)
        write_event(
            disc_id, "security-specialist", "critique", "Response.", reply_to=1, confidence=0.80
        )

        count = ingest_events(disc_id, pipeline_env["db_path"])
        assert count == 2

        conn = sqlite3.connect(str(pipeline_env["db_path"]))
        rows = conn.execute(
            "SELECT turn_id, agent, intent, confidence FROM turns "
            "WHERE discussion_id = ? ORDER BY turn_id",
            (disc_id,),
        ).fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0] == (1, "qa-specialist", "proposal", 0.85)
        assert rows[1] == (2, "security-specialist", "critique", 0.80)

    def test_computes_correct_content_hash(self, pipeline_env):
        disc_id = create_discussion("hash-test")
        content = "This is the content to hash."
        write_event(disc_id, "agent", "proposal", content)
        ingest_events(disc_id, pipeline_env["db_path"])

        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        conn = sqlite3.connect(str(pipeline_env["db_path"]))
        row = conn.execute(
            "SELECT content_hash FROM turns WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        conn.close()

        assert row[0] == expected_hash

    def test_updates_agent_count(self, pipeline_env):
        disc_id = create_discussion("count-test")
        write_event(disc_id, "agent-a", "proposal", "A.")
        write_event(disc_id, "agent-b", "proposal", "B.")
        write_event(disc_id, "agent-c", "critique", "C.", reply_to=1)
        # agent-a appears twice should still count as 1 unique
        write_event(disc_id, "agent-a", "evidence", "More from A.")
        ingest_events(disc_id, pipeline_env["db_path"])

        conn = sqlite3.connect(str(pipeline_env["db_path"]))
        row = conn.execute(
            "SELECT agent_count FROM discussions WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        conn.close()

        assert row[0] == 3  # agent-a, agent-b, agent-c

    def test_is_idempotent(self, pipeline_env):
        disc_id = create_discussion("idempotent-test")
        write_event(disc_id, "agent", "proposal", "Content.")
        ingest_events(disc_id, pipeline_env["db_path"])
        ingest_events(disc_id, pipeline_env["db_path"])  # Should not raise or duplicate

        conn = sqlite3.connect(str(pipeline_env["db_path"]))
        rows = conn.execute(
            "SELECT COUNT(*) FROM turns WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        conn.close()

        assert rows[0] == 1  # Not duplicated


# ============================================================
# record_education tests
# ============================================================


class TestRecordEducation:
    """Tests for scripts/record_education.py."""

    def test_stores_results(self, pipeline_env):
        disc_id = create_discussion("edu-test")
        record_education(
            "QUIZ-20260218-143000",
            disc_id,
            "understand",
            "walkthrough",
            0.85,
            True,
            pipeline_env["db_path"],
        )

        conn = sqlite3.connect(str(pipeline_env["db_path"]))
        row = conn.execute(
            "SELECT session_id, bloom_level, question_type, score, passed "
            "FROM education_results WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        conn.close()

        assert row[0] == "QUIZ-20260218-143000"
        assert row[1] == "understand"
        assert row[2] == "walkthrough"
        assert row[3] == 0.85
        assert row[4] == 1  # True stored as 1
