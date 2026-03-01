"""Unify sightings from adoption log into pattern_sightings table.

Parses memory/lessons/adoption-log.md and inserts sightings with
source_type='adoption_log' so v_rule_of_three counts cross-source patterns.

Usage:
    python scripts/unify_sightings.py
    python scripts/unify_sightings.py --dry-run
"""

import argparse
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
ADOPTION_LOG = PROJECT_ROOT / "memory" / "lessons" / "adoption-log.md"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Date pattern in adoption log
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
# Analysis ID pattern
ANALYSIS_PATTERN = re.compile(r"ANALYSIS-\d{8}-\d{6}[-\w]*")

# Stop words for pattern key generation
STOP_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "not",
    "no",
    "but",
    "or",
    "and",
    "if",
    "then",
    "else",
    "when",
    "all",
    "each",
    "every",
    "some",
    "other",
    "this",
    "that",
    "it",
}


def _normalize_pattern_name(name: str) -> str:
    """Normalize a pattern name for pattern_key generation."""
    name = name.lower().strip()
    for ch in "—–-:;,.!?()[]{}\"'":
        name = name.replace(ch, " ")
    words = [w for w in name.split() if w not in STOP_WORDS and len(w) > 2]
    return "-".join(sorted(words[:5]))


def parse_adoption_log(log_path: Path = ADOPTION_LOG) -> list[dict]:
    """Parse adoption log for patterns with analysis sources.

    Returns:
        List of dicts with pattern name, status, source analysis, date, sighting count.
    """
    if not log_path.exists():
        print(f"Adoption log not found: {log_path}")
        return []

    text = log_path.read_text(encoding="utf-8")
    entries = []

    for line in text.split("\n"):
        # Skip headers and separators
        if not line.strip().startswith("|") or line.strip().startswith("|--"):
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 3:
            continue
        # Skip header row
        if "Pattern" in cells[0] and ("Status" in cells[1] or "Score" in cells[1]):
            continue

        pattern_name = cells[0]
        # Look for analysis references and dates in the cells
        analysis_id = None
        date_str = None
        sighting_count = 1

        for cell in cells:
            analysis_match = ANALYSIS_PATTERN.search(cell)
            if analysis_match:
                analysis_id = analysis_match.group()
            date_match = DATE_PATTERN.search(cell)
            if date_match:
                date_str = date_match.group()
            # Look for sighting counts like "3 sightings"
            count_match = re.search(r"(\d+)\s*sighting", cell, re.IGNORECASE)
            if count_match:
                sighting_count = int(count_match.group(1))

        if pattern_name and date_str:
            entries.append(
                {
                    "pattern_name": pattern_name,
                    "analysis_id": analysis_id,
                    "date": date_str,
                    "sighting_count": sighting_count,
                }
            )

    return entries


def unify_sightings(db_path: Path = DB_PATH, dry_run: bool = False) -> int:
    """Parse adoption log and insert sightings into pattern_sightings.

    Args:
        db_path: Path to the SQLite database.
        dry_run: If True, report without writing.

    Returns:
        Number of sightings inserted.
    """
    entries = parse_adoption_log()

    if not entries:
        print("No adoption log entries found")
        return 0

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    inserted = 0
    timestamp = datetime.now(UTC).isoformat()

    for entry in entries:
        pattern_key = f"adoption:{_normalize_pattern_name(entry['pattern_name'])}"
        discussion_id = entry.get("analysis_id") or f"adoption-log-{entry['date']}"

        if dry_run:
            print(f"  Would insert: {pattern_key} from {discussion_id}")
            inserted += 1
            continue

        # Check for existing sighting
        existing = conn.execute(
            """SELECT id FROM pattern_sightings
               WHERE pattern_key = ? AND discussion_id = ? AND source_type = 'adoption_log'""",
            (pattern_key, discussion_id),
        ).fetchone()

        if not existing:
            # Use a synthetic discussion_id for adoption log entries
            # First check if a discussion exists with this ID
            disc_exists = conn.execute(
                "SELECT 1 FROM discussions WHERE discussion_id = ?",
                (discussion_id,),
            ).fetchone()

            if disc_exists:
                conn.execute(
                    """INSERT INTO pattern_sightings
                       (pattern_key, finding_id, discussion_id, agent,
                        source_type, sighted_at)
                       VALUES (?, NULL, ?, 'adoption-log', 'adoption_log', ?)""",
                    (pattern_key, discussion_id, entry["date"]),
                )
                inserted += 1
            else:
                # Log that we skipped due to missing discussion reference
                print(
                    f"  {YELLOW}Skipping {entry['pattern_name']}: "
                    f"no discussion {discussion_id} in DB{RESET}"
                )

    if not dry_run:
        conn.commit()

    conn.close()

    print(f"\n{BOLD}Unified Sightings{RESET}")
    print(f"  Adoption log entries: {len(entries)}")
    action = "Would insert" if dry_run else "Inserted"
    print(f"  {action}: {inserted} sightings")

    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unify adoption log sightings into pattern_sightings table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report without writing to database",
    )
    args = parser.parse_args()
    unify_sightings(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
