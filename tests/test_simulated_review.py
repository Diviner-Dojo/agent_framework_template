"""Integration test simulating a full /review workflow.

This test follows the exact same sequence the /review command describes:
1. Create discussion
2. Write specialist proposals (3 agents in parallel)
3. Write critique round (2 responses)
4. Write facilitator synthesis
5. Close discussion
6. Verify ALL artifacts and SQLite state

This proves the plumbing works end-to-end — if Claude follows the
command correctly, the output will be right.
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT / "scripts"))

from init_db import init_db
from create_discussion import create_discussion
from write_event import write_event, find_discussion_dir
from generate_transcript import generate_transcript
from ingest_events import ingest_events


@pytest.fixture
def review_env(tmp_path, monkeypatch):
    """Set up an isolated environment for the simulated review."""
    discussions_dir = tmp_path / "discussions"
    discussions_dir.mkdir()
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    db_path = metrics_dir / "evaluation.db"

    init_db(db_path)

    import create_discussion as cd_mod
    import write_event as we_mod
    import generate_transcript as gt_mod
    import ingest_events as ie_mod

    monkeypatch.setattr(cd_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(cd_mod, "DB_PATH", db_path)
    monkeypatch.setattr(we_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(gt_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(ie_mod, "DISCUSSIONS_DIR", discussions_dir)
    monkeypatch.setattr(ie_mod, "DB_PATH", db_path)

    # Also monkeypatch close_discussion's imports (it imports siblings)
    import close_discussion as cls_mod
    monkeypatch.setattr(cls_mod, "DB_PATH", db_path)

    return {
        "tmp_path": tmp_path,
        "discussions_dir": discussions_dir,
        "db_path": db_path,
    }


class TestSimulatedReview:
    """Simulate the full /review command workflow and verify all outputs."""

    def test_full_review_pipeline(self, review_env):
        """
        Simulates: /review src/routes.py
        Risk: medium → structured-dialogue mode
        Team: qa-specialist, security-specialist, architecture-consultant
        Rounds: proposals → critiques → synthesis
        """
        db_path = review_env["db_path"]

        # ============================================================
        # Step 1: Create discussion (like the facilitator would)
        # ============================================================
        disc_id = create_discussion(
            slug="review-routes",
            risk_level="medium",
            collaboration_mode="structured-dialogue",
            exploration_intensity="medium",
        )

        # Verify: discussion created with open status
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT status, risk_level, collaboration_mode FROM discussions WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        assert row == ("open", "medium", "structured-dialogue")
        conn.close()

        # ============================================================
        # Step 2: Specialist proposals (round 1 — parallel in real usage)
        # ============================================================
        qa_content = (
            "Test coverage for routes.py is adequate with 15 tests covering "
            "all 5 endpoints. Edge cases for empty title and long title are covered. "
            "Missing: parameterized tests for boundary values, no test for concurrent "
            "creation of duplicate todos."
        )
        sec_content = (
            "Input validation via Pydantic models is good. No SQL injection risk due to "
            "parameterized queries in database.py. CORS not configured — should be added "
            "before production. No authentication on any endpoint."
        )
        arch_content = (
            "Module separation is clean: routes.py handles HTTP, database.py handles "
            "persistence, models.py defines contracts. Global mutable state in routes.py "
            "(module-level _db variable) violates dependency injection principle. "
            "Consider using FastAPI's dependency injection instead."
        )

        t1 = write_event(
            disc_id, "qa-specialist", "proposal", qa_content,
            confidence=0.82, tags=["testing", "coverage", "edge-cases"],
        )
        t2 = write_event(
            disc_id, "security-specialist", "proposal", sec_content,
            confidence=0.88, tags=["security", "cors", "auth"],
            risk_flags=["missing-auth", "no-cors"],
        )
        t3 = write_event(
            disc_id, "architecture-consultant", "proposal", arch_content,
            confidence=0.85, tags=["architecture", "dependency-injection", "coupling"],
        )

        assert t1 == 1
        assert t2 == 2
        assert t3 == 3

        # ============================================================
        # Step 3: Critique round (round 2 — structured dialogue)
        # ============================================================
        sec_critique = (
            "Agreeing with architecture-consultant: the global _db pattern also "
            "has security implications — it makes it harder to enforce per-request "
            "database isolation in multi-tenant scenarios."
        )
        qa_critique = (
            "Security-specialist raises a valid point about missing auth. "
            "This means we also need auth-related test cases: unauthorized access "
            "returns 401, invalid tokens return 403."
        )

        t4 = write_event(
            disc_id, "security-specialist", "critique", sec_critique,
            reply_to=3, confidence=0.85, tags=["security", "architecture"],
        )
        t5 = write_event(
            disc_id, "qa-specialist", "critique", qa_critique,
            reply_to=2, confidence=0.80, tags=["testing", "auth"],
        )

        assert t4 == 4
        assert t5 == 5

        # ============================================================
        # Step 4: Facilitator synthesis
        # ============================================================
        synthesis = (
            "Consensus on three required changes before merge:\n"
            "1. Replace global _db module variable with FastAPI Depends() pattern\n"
            "2. Add CORS middleware with explicit allowed origins\n"
            "3. Add authentication middleware (can be deferred with ADR documenting the decision)\n\n"
            "Recommended improvements (non-blocking):\n"
            "- Add parameterized boundary-value tests\n"
            "- Add concurrent access tests\n\n"
            "Verdict: approve-with-changes\n"
            "Overall confidence: 0.84"
        )

        t6 = write_event(
            disc_id, "facilitator", "synthesis", synthesis,
            confidence=0.84, tags=["synthesis", "verdict"],
        )

        assert t6 == 6

        # ============================================================
        # Step 5: Close discussion (seals everything)
        # ============================================================
        # We call the individual steps instead of close_discussion.py
        # to avoid cross-module import issues in test isolation.
        # This is exactly what close_discussion.py does internally.

        # 5a: Generate transcript
        transcript_path = generate_transcript(disc_id)

        # 5b: Ingest events to SQLite
        ingested_count = ingest_events(disc_id, db_path)

        # 5c: Mark closed in SQLite
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "UPDATE discussions SET status = 'closed' WHERE discussion_id = ?",
            (disc_id,),
        )
        conn.commit()
        conn.close()

        # ============================================================
        # VERIFICATION: Layer 1 — File System
        # ============================================================
        disc_dir = find_discussion_dir(disc_id)

        # events.jsonl: exactly 6 lines, all valid JSON
        events_path = disc_dir / "events.jsonl"
        assert events_path.exists()
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 6, f"Expected 6 events, got {len(lines)}"

        events = [json.loads(line) for line in lines]

        # Correct discussion_id on all events
        for event in events:
            assert event["discussion_id"] == disc_id

        # Sequential turn_ids
        turn_ids = [e["turn_id"] for e in events]
        assert turn_ids == [1, 2, 3, 4, 5, 6]

        # Correct agents
        agents = [e["agent"] for e in events]
        assert agents == [
            "qa-specialist", "security-specialist", "architecture-consultant",
            "security-specialist", "qa-specialist", "facilitator",
        ]

        # Correct intents
        intents = [e["intent"] for e in events]
        assert intents == [
            "proposal", "proposal", "proposal",
            "critique", "critique", "synthesis",
        ]

        # Reply-to references are valid
        assert events[0]["reply_to"] is None  # first proposal
        assert events[1]["reply_to"] is None  # second proposal
        assert events[2]["reply_to"] is None  # third proposal
        assert events[3]["reply_to"] == 3     # sec critiques arch (turn 3)
        assert events[4]["reply_to"] == 2     # qa critiques sec (turn 2)
        assert events[5]["reply_to"] is None  # synthesis

        # Tags preserved in events.jsonl
        assert "testing" in events[0]["tags"]
        assert "security" in events[1]["tags"]
        assert "missing-auth" in events[1]["risk_flags"]

        # transcript.md exists with correct metadata
        assert transcript_path.exists()
        transcript = transcript_path.read_text(encoding="utf-8")
        assert f"discussion_id: {disc_id}" in transcript
        assert "total_turns: 6" in transcript
        assert "qa-specialist" in transcript
        assert "security-specialist" in transcript
        assert "architecture-consultant" in transcript
        assert "facilitator" in transcript
        assert "Turn 1" in transcript
        assert "Turn 6" in transcript

        # ============================================================
        # VERIFICATION: Layer 2 — SQLite
        # ============================================================
        conn = sqlite3.connect(str(db_path))

        # Discussion row
        disc_row = conn.execute(
            "SELECT status, risk_level, collaboration_mode, agent_count "
            "FROM discussions WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        assert disc_row[0] == "closed"
        assert disc_row[1] == "medium"
        assert disc_row[2] == "structured-dialogue"
        assert disc_row[3] == 4  # qa, sec, arch, facilitator

        # Turns table: 6 rows
        turn_rows = conn.execute(
            "SELECT turn_id, agent, intent, confidence FROM turns "
            "WHERE discussion_id = ? ORDER BY turn_id",
            (disc_id,),
        ).fetchall()
        assert len(turn_rows) == 6

        # Verify specific turns
        assert turn_rows[0] == (1, "qa-specialist", "proposal", 0.82)
        assert turn_rows[1] == (2, "security-specialist", "proposal", 0.88)
        assert turn_rows[2] == (3, "architecture-consultant", "proposal", 0.85)
        assert turn_rows[3] == (4, "security-specialist", "critique", 0.85)
        assert turn_rows[4] == (5, "qa-specialist", "critique", 0.80)
        assert turn_rows[5] == (6, "facilitator", "synthesis", 0.84)

        # Content hashes are correct
        for i, event in enumerate(events):
            expected_hash = hashlib.sha256(event["content"].encode("utf-8")).hexdigest()
            stored_hash = conn.execute(
                "SELECT content_hash FROM turns WHERE discussion_id = ? AND turn_id = ?",
                (disc_id, event["turn_id"]),
            ).fetchone()[0]
            assert stored_hash == expected_hash, (
                f"Hash mismatch for turn {event['turn_id']}"
            )

        # No duplicate ingestion
        total_turns = conn.execute(
            "SELECT COUNT(*) FROM turns WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()[0]
        assert total_turns == 6

        conn.close()

    def test_minimal_review_two_agents(self, review_env):
        """Simulate a low-risk review with just 2 agents (minimum viable)."""
        db_path = review_env["db_path"]

        disc_id = create_discussion("mini-review", "low", "ensemble")

        write_event(disc_id, "qa-specialist", "proposal", "Tests look fine.", confidence=0.90)
        write_event(disc_id, "docs-knowledge", "proposal", "Docstrings present.", confidence=0.88)
        write_event(disc_id, "facilitator", "synthesis", "Approved.", confidence=0.90)

        generate_transcript(disc_id)
        ingest_events(disc_id, db_path)

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE discussions SET status = 'closed' WHERE discussion_id = ?",
            (disc_id,),
        )
        conn.commit()

        row = conn.execute(
            "SELECT status, agent_count FROM discussions WHERE discussion_id = ?",
            (disc_id,),
        ).fetchone()
        conn.close()

        assert row[0] == "closed"
        assert row[1] == 3  # qa, docs, facilitator
