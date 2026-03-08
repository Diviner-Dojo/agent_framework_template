"""Unify pattern sightings from adoption log and discussion-derived patterns.

Merges patterns tracked in `memory/lessons/adoption-log.md` with
discussion-derived patterns in the `pattern_sightings` table, ensuring
the Rule of Three counts both sources.

Usage:
    python scripts/unify_sightings.py
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pipeline_utils import pattern_hash as _pattern_hash

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
ADOPTION_LOG = PROJECT_ROOT / "memory" / "lessons" / "adoption-log.md"


def _parse_adoption_log() -> list[dict]:
    """Parse the adoption log for pattern entries.

    Looks for table rows in the adoption log with pattern information.
    Expected format: | Pattern Name | Source | Category | Status | ... |
    """
    if not ADOPTION_LOG.exists():
        return []

    text = ADOPTION_LOG.read_text(encoding="utf-8")
    patterns: list[dict] = []

    # Find table rows (skip header and separator rows)
    in_table = False
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            in_table = False
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 3:
            continue

        # Skip header/separator rows
        if all(c.startswith("-") or c.startswith("=") for c in cells if c):
            in_table = True
            continue
        if any(c.lower() in ("pattern", "name", "source", "category") for c in cells[:3]):
            in_table = True
            continue

        if not in_table:
            # First data-like row enables the table flag
            in_table = True

        # Extract pattern data
        if len(cells) >= 3:
            name = cells[0].strip()
            source = cells[1].strip() if len(cells) > 1 else ""
            category = cells[2].strip() if len(cells) > 2 else "general"

            if name and not name.startswith("-"):
                patterns.append(
                    {
                        "name": name,
                        "source": source,
                        "category": category.lower() if category else "general",
                    }
                )

    return patterns


def unify_sightings() -> int:
    """Merge adoption-log patterns into the pattern_sightings table.

    Returns:
        Number of new sightings inserted from the adoption log.
    """
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 0

    adoption_patterns = _parse_adoption_log()
    if not adoption_patterns:
        print("No patterns found in adoption log")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(UTC).isoformat()
    new_count = 0

    for pattern in adoption_patterns:
        p_hash = _pattern_hash(pattern["category"], pattern["name"])

        # Check if already recorded from adoption-log source
        existing = conn.execute(
            "SELECT id FROM pattern_sightings WHERE pattern_hash = ? AND source = 'adoption-log'",
            (p_hash,),
        ).fetchone()

        if not existing:
            # Adoption-log patterns have no discussion provenance — use NULL.
            # One sighting per source project for Rule of Three counting.
            conn.execute(
                """INSERT INTO pattern_sightings
                   (pattern_hash, discussion_id, category, summary, source, created_at)
                   VALUES (?, NULL, ?, ?, 'adoption-log', ?)""",
                (p_hash, pattern["category"], pattern["name"], now),
            )
            new_count += 1

    conn.commit()
    conn.close()
    print(
        f"Unified {new_count} new sightings from adoption log ({len(adoption_patterns)} patterns parsed)"
    )
    return new_count


def main() -> None:
    unify_sightings()


if __name__ == "__main__":
    main()
