"""Regression: scripts/close_discussion.py promotion-pipeline canary.

Phase 0 of the framework memory evolution (SPEC-20260515-053533) fixed two
silently-swallowed defects at the seam between Layer 1 closure and Layer 3
promotion candidacy:

1. close_discussion.py called ``surface_candidates(discussion_id=discussion_id)``
   against a function whose signature was ``def surface_candidates(threshold=3)``.
   Every closure raised TypeError, caught by the broad ``except Exception`` at
   close_discussion.py:145, printed as a warning, swallowed.
2. close_discussion.py imported ``compute_effectiveness`` from
   ``compute_agent_effectiveness``. The actual exported name is
   ``compute_agent_effectiveness``. Every closure raised ImportError, swallowed
   the same way.

These tests are the structural canary for the swallow-and-warn pattern at
close_discussion.py:140-155. Do not remove or weaken without an ADR addressing
the swallowed-exception pattern.

Tests cover:
- The two canary cases (one per original defect).
- R4.a — surface_candidates INSERT branch (new candidate row emitted).
- R4.b — surface_candidates UPDATE branch (existing candidate row refreshed).

Isolation strategy: each test uses ``tmp_path`` with ``init_db()`` to build a
fresh canonical-schema DB, then monkeypatches ``DB_PATH`` on the module under
test. ``surface_candidates`` and ``compute_agent_effectiveness`` resolve
``DB_PATH`` at call time via the module attribute, so monkeypatching the
module-level constant takes effect immediately (verified against the patched
``scripts/surface_candidates.py`` and ``scripts/compute_agent_effectiveness.py``).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# Add project root to path so we can import scripts.*
TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))

from scripts import compute_agent_effectiveness as cae_module  # noqa: E402
from scripts import surface_candidates as sc_module  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from scripts.pipeline_utils import pattern_hash  # noqa: E402
from scripts.surface_candidates import surface_candidates  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a fresh canonical-schema DB and route the pipeline scripts at it."""
    path = tmp_path / "evaluation.db"
    init_db(path)
    monkeypatch.setattr(sc_module, "DB_PATH", path)
    monkeypatch.setattr(cae_module, "DB_PATH", path)
    return path


def _seed_discussion(db: Path, discussion_id: str) -> None:
    """Insert a closed discussion row (the minimum needed for foreign keys)."""
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO discussions "
        "(discussion_id, created_at, closed_at, risk_level, collaboration_mode, "
        "status, agent_count) "
        "VALUES (?, '2026-01-01T00:00:00+00:00', '2026-01-01T01:00:00+00:00', "
        "'low', 'ensemble', 'closed', 0)",
        (discussion_id,),
    )
    conn.commit()
    conn.close()


def _seed_pattern_sighting(
    db: Path,
    discussion_id: str,
    category: str,
    summary: str,
    *,
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> str:
    """Insert one pattern_sightings row. Returns the pattern_hash used."""
    p_hash = pattern_hash(category, summary)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO pattern_sightings "
        "(pattern_hash, discussion_id, category, summary, source, created_at) "
        "VALUES (?, ?, ?, ?, 'discussion', ?)",
        (p_hash, discussion_id, category, summary, created_at),
    )
    conn.commit()
    conn.close()
    return p_hash


def _candidate_rows(db: Path) -> list[tuple]:
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT id, finding_pattern, category, sighting_count, "
        "first_seen, last_seen, promoted, evidence_ids "
        "FROM promotion_candidates ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Canary tests — one per original defect
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_canary_surface_candidates_accepts_discussion_id_kwarg() -> None:
    """Canary for Defect 1: close_discussion.py called surface_candidates(discussion_id=...)
    against signature def surface_candidates(threshold=3), TypeError swallowed.

    This test invokes the function with the exact kwarg call-pattern close_discussion uses.
    Failure means the signature drift has been re-introduced.
    """
    # No DB-state assertions here — the canary is that the call returns without TypeError.
    # The empty-DB fast-path early-returns 0; that is the observable signal that the
    # kwarg was accepted rather than rejected at function entry.
    result = surface_candidates(threshold=3, discussion_id="DISC-NONEXISTENT")
    assert result == 0


@pytest.mark.regression
def test_canary_compute_agent_effectiveness_import_name() -> None:
    """Canary for Defect 2: close_discussion.py imported ``compute_effectiveness``
    from ``compute_agent_effectiveness``; the actual exported name is
    ``compute_agent_effectiveness``. ImportError swallowed.

    Strategy: source-inspect close_discussion.py to find the ``from
    compute_agent_effectiveness import <name>`` line, then verify the imported
    name is actually defined in compute_agent_effectiveness.py. This catches
    both the historical drift (``compute_effectiveness`` was never exported)
    AND any future rename that desynchronises the two files.

    A pure ``from compute_agent_effectiveness import compute_agent_effectiveness``
    test in this file would not catch close_discussion.py reverting to the
    wrong name — it would only verify the symbol exists in the source module.
    """
    import re

    cd_source = (TEMPLATE_ROOT / "scripts" / "close_discussion.py").read_text(encoding="utf-8")
    # Capture the full import list (handles single-name, multi-name comma-separated,
    # and parenthesised forms). The qa-F1 finding from REV-20260515-221223 noted that
    # a single-token \w+ capture would miss the correct name on a multi-name line.
    match = re.search(
        r"from\s+compute_agent_effectiveness\s+import\s+([\w,\s()]+)",
        cd_source,
    )
    assert match, (
        "close_discussion.py must contain a `from compute_agent_effectiveness "
        "import <name>` line — the auto-invoke contract relies on it."
    )
    imported_names = re.findall(r"\b\w+\b", match.group(1))
    assert "compute_agent_effectiveness" in imported_names, (
        f"close_discussion.py must import 'compute_agent_effectiveness' from "
        f"compute_agent_effectiveness; saw {imported_names}. "
        "This was the original Defect 2: import name 'compute_effectiveness' "
        "did not match the exported 'compute_agent_effectiveness'."
    )

    cae_source = (TEMPLATE_ROOT / "scripts" / "compute_agent_effectiveness.py").read_text(
        encoding="utf-8"
    )
    assert re.search(r"^def compute_agent_effectiveness\b", cae_source, re.MULTILINE), (
        "compute_agent_effectiveness.py must define a function named "
        "'compute_agent_effectiveness' that close_discussion.py imports. "
        "This guards against the inverse drift: caller updated but source renamed."
    )


# ---------------------------------------------------------------------------
# R4.a — INSERT branch (new candidate emitted on Rule-of-Three crossing)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestPromotionPipelineInsertBranch:
    """R4.a: surface_candidates emits a new promotion_candidates row when a pattern
    crosses the Rule-of-Three threshold and the closing discussion is one of the
    contributors."""

    def _seed_three_discussions_sharing_pattern(self, db: Path) -> str:
        """Common setup: three discussions, each sighting the same pattern_hash."""
        # Same category + same tokenized summary → identical pattern_hash.
        category = "weak-assertion"
        summary = "test asserts presence but not value, failing to detect regressions"
        for i, ts in enumerate(
            (
                "2026-01-01T00:00:00+00:00",
                "2026-01-02T00:00:00+00:00",
                "2026-01-03T00:00:00+00:00",
            )
        ):
            disc_id = f"DISC-INSERT-{i + 1}"
            _seed_discussion(db, disc_id)
            phash = _seed_pattern_sighting(db, disc_id, category, summary, created_at=ts)
        return phash

    def test_insert_branch_emits_candidate(self, db_path: Path) -> None:
        """Three distinct discussions sight the same pattern → INSERT one candidate."""
        phash = self._seed_three_discussions_sharing_pattern(db_path)

        new_count = surface_candidates(threshold=3, discussion_id="DISC-INSERT-3")

        assert new_count == 1, "Expected one new candidate to be inserted"
        rows = _candidate_rows(db_path)
        assert len(rows) == 1
        _id, finding_pattern, category, sightings, first_seen, last_seen, promoted, evidence = (
            rows[0]
        )
        assert finding_pattern == phash
        assert category == "weak-assertion"
        assert sightings == 3
        assert promoted == 0
        # evidence_ids is JSON-serialised list of discussion ids
        assert "DISC-INSERT-1" in evidence
        assert "DISC-INSERT-2" in evidence
        assert "DISC-INSERT-3" in evidence

    def test_insert_branch_filtered_to_closing_discussion(self, db_path: Path) -> None:
        """Per-discussion scoping: a Rule-of-Three pattern unrelated to the
        closing discussion is NOT emitted.

        Confirms the auto-invoke contract: closing DISC-X surfaces only patterns
        sighted in DISC-X, even if other patterns globally qualify.
        """
        # Pattern A: sighted in three discussions, including the closing one.
        cat_a = "weak-assertion"
        sum_a = "test asserts presence but not value, failing to detect regressions"
        for i in range(3):
            disc_id = f"DISC-A-{i + 1}"
            _seed_discussion(db_path, disc_id)
            _seed_pattern_sighting(db_path, disc_id, cat_a, sum_a)
        # Pattern B: sighted in three discussions, NONE of which are the closing one.
        cat_b = "missing-edge-case"
        sum_b = "function does not handle empty input collection edge condition properly"
        for i in range(3):
            disc_id = f"DISC-B-{i + 1}"
            _seed_discussion(db_path, disc_id)
            _seed_pattern_sighting(db_path, disc_id, cat_b, sum_b)

        # Close DISC-A-3. Only Pattern A should emit (Pattern B has no sighting here).
        new_count = surface_candidates(threshold=3, discussion_id="DISC-A-3")

        assert new_count == 1, "Only Pattern A should surface for DISC-A-3 closure"
        rows = _candidate_rows(db_path)
        assert len(rows) == 1
        assert rows[0][2] == cat_a

    def test_insert_branch_manual_all_path_unchanged(self, db_path: Path) -> None:
        """``discussion_id=None`` (manual --all path) preserves the original
        project-wide behaviour: every Rule-of-Three pattern surfaces."""
        # Seed two unrelated patterns, each over threshold.
        for i in range(3):
            disc_id = f"DISC-X-{i + 1}"
            _seed_discussion(db_path, disc_id)
            _seed_pattern_sighting(
                db_path, disc_id, "weak-assertion", "test asserts presence but not value"
            )
        for i in range(3):
            disc_id = f"DISC-Y-{i + 1}"
            _seed_discussion(db_path, disc_id)
            _seed_pattern_sighting(
                db_path, disc_id, "missing-edge-case", "function does not handle empty"
            )

        new_count = surface_candidates(threshold=3, discussion_id=None)
        # Both patterns surface under project-wide behaviour.
        assert new_count == 2
        rows = _candidate_rows(db_path)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# R4.b — UPDATE branch (existing candidate refreshed, no duplicate row)
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestPromotionPipelineUpdateBranch:
    """R4.b: surface_candidates updates an existing promotion_candidates row
    (rather than inserting a duplicate) when the pattern_hash is already present."""

    def test_update_branch_refreshes_existing_candidate(self, db_path: Path) -> None:
        """A 4th sighting after a 3-sighting candidate already exists →
        the same row's sighting_count, last_seen, and evidence_ids advance.
        No second row inserted."""
        # Phase 1: seed three discussions and produce the candidate via INSERT.
        category = "weak-assertion"
        summary = "test asserts presence but not value, failing to detect regressions"
        for i, ts in enumerate(
            (
                "2026-01-01T00:00:00+00:00",
                "2026-01-02T00:00:00+00:00",
                "2026-01-03T00:00:00+00:00",
            )
        ):
            disc_id = f"DISC-UPD-{i + 1}"
            _seed_discussion(db_path, disc_id)
            _seed_pattern_sighting(db_path, disc_id, category, summary, created_at=ts)
        new_count = surface_candidates(threshold=3, discussion_id="DISC-UPD-3")
        assert new_count == 1
        rows = _candidate_rows(db_path)
        assert len(rows) == 1
        candidate_id_before = rows[0][0]
        sighting_count_before = rows[0][3]
        last_seen_before = rows[0][5]
        evidence_before = rows[0][7]
        assert sighting_count_before == 3
        assert "DISC-UPD-4" not in evidence_before

        # Phase 2: add a 4th discussion sighting the same pattern, then re-run.
        _seed_discussion(db_path, "DISC-UPD-4")
        _seed_pattern_sighting(
            db_path,
            "DISC-UPD-4",
            category,
            summary,
            created_at="2026-01-04T00:00:00+00:00",
        )
        update_count = surface_candidates(threshold=3, discussion_id="DISC-UPD-4")

        # No NEW inserts (existing row was UPDATEd in place).
        assert update_count == 0
        rows_after = _candidate_rows(db_path)
        assert len(rows_after) == 1
        candidate_id_after = rows_after[0][0]
        sighting_count_after = rows_after[0][3]
        last_seen_after = rows_after[0][5]
        evidence_after = rows_after[0][7]

        # Same row (id unchanged), refreshed columns.
        assert candidate_id_after == candidate_id_before
        assert sighting_count_after == 4
        assert last_seen_after > last_seen_before
        assert "DISC-UPD-4" in evidence_after
