"""Unify pattern sightings from adoption log and discussion-derived patterns.

Merges patterns tracked in `memory/lessons/adoption-log.md` with
discussion-derived patterns in the `pattern_sightings` table, ensuring
the Rule of Three counts both sources.

Includes pattern_key normalization with stop-word removal, duplicate
detection, and discussion validation.

Usage:
    python scripts/unify_sightings.py [--dry-run]
"""

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pipeline_utils import pattern_hash as _pattern_hash

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
ADOPTION_LOG = PROJECT_ROOT / "memory" / "lessons" / "adoption-log.md"

# Stop words to remove during pattern_key normalization
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "use",
        "using",
        "used",
    }
)


def normalize_pattern_key(name: str) -> str:
    """Normalize a pattern name into a canonical key for deduplication.

    Lowercases, removes stop words, and sorts remaining tokens to produce
    a stable key regardless of word order or phrasing.

    Args:
        name: The pattern name or summary text.

    Returns:
        Normalized key string with sorted tokens joined by colons.
    """
    tokens = name.lower().replace("-", " ").replace("_", " ").split()
    filtered = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]
    return ":".join(sorted(filtered))


def _parse_adoption_log(log_path: Path | None = None) -> list[dict]:
    """Parse the adoption log for pattern entries.

    Looks for table rows in the adoption log with pattern information.
    Expected format: | Pattern Name | Source | Category | Status | ... |

    Args:
        log_path: Override adoption log path (for testing).

    Returns:
        List of pattern dicts with name, source, category fields.
    """
    path = log_path or ADOPTION_LOG
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    patterns: list[dict] = []
    seen_keys: set[str] = set()

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
            in_table = True

        # Extract pattern data
        if len(cells) >= 3:
            name = cells[0].strip()
            source = cells[1].strip() if len(cells) > 1 else ""
            category = cells[2].strip() if len(cells) > 2 else "general"

            if name and not name.startswith("-"):
                # Deduplicate using normalized key
                norm_key = normalize_pattern_key(name)
                if norm_key in seen_keys:
                    print(f"  Duplicate detected (skipping): {name} → key={norm_key}")
                    continue
                seen_keys.add(norm_key)

                patterns.append(
                    {
                        "name": name,
                        "source": source,
                        "category": category.lower() if category else "general",
                    }
                )

    return patterns


def _validate_discussion_refs(conn: sqlite3.Connection) -> list[str]:
    """Check for pattern_sightings referencing non-existent discussions.

    Args:
        conn: Active SQLite connection.

    Returns:
        List of warning messages for orphaned references.
    """
    warnings: list[str] = []
    try:
        rows = conn.execute(
            "SELECT ps.id, ps.discussion_id FROM pattern_sightings ps "
            "WHERE ps.discussion_id IS NOT NULL "
            "AND ps.discussion_id NOT IN (SELECT id FROM discussions)"
        ).fetchall()
        for row_id, disc_id in rows:
            warnings.append(f"  Orphaned reference: sighting {row_id} → discussion {disc_id}")
    except sqlite3.OperationalError:
        # discussions table may not exist yet
        pass
    return warnings


def unify_sightings(
    dry_run: bool = False,
    db_path: Path | None = None,
    log_path: Path | None = None,
) -> int:
    """Merge adoption-log patterns into the pattern_sightings table.

    Args:
        dry_run: If True, report what would change without writing to DB.
        db_path: Override database path (for testing).
        log_path: Override adoption log path (for testing).

    Returns:
        Number of new sightings inserted (or would-be-inserted in dry-run).
    """
    database = db_path or DB_PATH
    if not database.exists():
        print(f"Database not found at {database}")
        return 0

    adoption_patterns = _parse_adoption_log(log_path)
    if not adoption_patterns:
        print("No patterns found in adoption log")
        return 0

    conn = sqlite3.connect(str(database))
    conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(UTC).isoformat()
    new_count = 0

    # Validate discussion references
    warnings = _validate_discussion_refs(conn)
    if warnings:
        print("Discussion reference warnings:")
        for w in warnings:
            print(w)

    for pattern in adoption_patterns:
        p_hash = _pattern_hash(pattern["category"], pattern["name"])

        # Check if already recorded from adoption-log source
        existing = conn.execute(
            "SELECT id FROM pattern_sightings WHERE pattern_hash = ? AND source = 'adoption-log'",
            (p_hash,),
        ).fetchone()

        if not existing:
            if dry_run:
                print(f"  [DRY RUN] Would insert: {pattern['name']} (hash={p_hash})")
            else:
                conn.execute(
                    """INSERT INTO pattern_sightings
                       (pattern_hash, discussion_id, category, summary, source, created_at)
                       VALUES (?, NULL, ?, ?, 'adoption-log', ?)""",
                    (p_hash, pattern["category"], pattern["name"], now),
                )
            new_count += 1

    if not dry_run:
        conn.commit()
    conn.close()

    mode = "[DRY RUN] " if dry_run else ""
    print(
        f"{mode}Unified {new_count} new sightings from adoption log "
        f"({len(adoption_patterns)} patterns parsed)"
    )
    return new_count


def main() -> None:
    """CLI entrypoint for unify_sightings."""
    parser = argparse.ArgumentParser(
        description="Unify pattern sightings from adoption log and discussions"
    )
    parser.add_argument("--dry-run", action="store_true", help="Report without modifying database")
    args = parser.parse_args()
    unify_sightings(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
