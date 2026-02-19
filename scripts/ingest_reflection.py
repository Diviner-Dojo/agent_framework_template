"""Ingest a reflection markdown file into the SQLite reflections table.

Usage:
    python scripts/ingest_reflection.py <reflection_file_path>

Parses the YAML frontmatter and content sections from a reflection file.
"""

import argparse
import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


def parse_reflection(filepath: Path) -> dict:
    """Parse a reflection markdown file with YAML frontmatter.

    Args:
        filepath: Path to the reflection .md file.

    Returns:
        Dictionary with reflection fields.
    """
    text = filepath.read_text(encoding="utf-8")

    # Extract YAML frontmatter
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {filepath}")

    frontmatter_text = match.group(1)
    body = match.group(2)

    # Simple YAML parsing (key: value pairs)
    frontmatter = {}
    for line in frontmatter_text.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    # Extract sections from body
    sections = {}
    current_section = None
    current_content = []
    for line in body.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[3:].strip().lower().replace(" ", "_")
            current_content = []
        elif current_section:
            current_content.append(line)
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # Parse confidence calibration
    confidence_delta = None
    cal = sections.get("confidence_calibration", "")
    delta_match = re.search(r"Delta:\s*([+-]?\d+\.?\d*)", cal)
    if delta_match:
        confidence_delta = float(delta_match.group(1))

    return {
        "reflection_id": frontmatter.get("reflection_id", ""),
        "discussion_id": frontmatter.get("discussion_id", ""),
        "agent": frontmatter.get("agent", ""),
        "timestamp": frontmatter.get("timestamp", ""),
        "missed_signal": sections.get("what_i_missed", ""),
        "improvement_rule": sections.get("candidate_improvement_rule", ""),
        "confidence_delta": confidence_delta,
    }


def ingest_reflection(filepath: Path, db_path: Path = DB_PATH) -> None:
    """Parse and insert a reflection into SQLite.

    Args:
        filepath: Path to the reflection .md file.
        db_path: Path to the SQLite database.
    """
    data = parse_reflection(filepath)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """INSERT OR IGNORE INTO reflections
           (reflection_id, discussion_id, agent, missed_signal,
            improvement_rule, confidence_delta, promoted, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
        (
            data["reflection_id"],
            data["discussion_id"],
            data["agent"],
            data["missed_signal"],
            data["improvement_rule"],
            data["confidence_delta"],
            data["timestamp"],
        ),
    )
    conn.commit()
    conn.close()

    print(f"Reflection {data['reflection_id']} ingested")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a reflection into SQLite")
    parser.add_argument("filepath", help="Path to the reflection .md file")
    args = parser.parse_args()
    ingest_reflection(Path(args.filepath))


if __name__ == "__main__":
    main()
