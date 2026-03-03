"""Extract structured findings from discussion events.

Parses critique and proposal events from a discussion's events.jsonl,
identifies findings with severity and category, and inserts them into
the `findings` table in the SQLite database.

Usage:
    python scripts/extract_findings.py <discussion_id>
"""

import argparse
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"

# Severity keywords used for heuristic classification
_SEVERITY_PATTERNS: dict[str, list[str]] = {
    "critical": ["security vulnerability", "data loss", "injection", "authentication bypass"],
    "high": [
        "breaking change",
        "race condition",
        "memory leak",
        "unhandled error",
        "sql injection",
    ],
    "medium": ["missing validation", "missing test", "error handling", "performance"],
    "low": ["style", "naming", "documentation", "readability", "typo"],
    "info": ["suggestion", "consider", "nice to have", "optional", "minor"],
}

# Category keywords for classification
_CATEGORY_PATTERNS: dict[str, list[str]] = {
    "security": ["security", "auth", "injection", "xss", "csrf", "secret", "credential", "token"],
    "correctness": ["bug", "error", "incorrect", "wrong", "broken", "fail", "crash"],
    "performance": ["performance", "slow", "latency", "memory", "cache", "optimization", "n+1"],
    "architecture": ["architecture", "coupling", "cohesion", "boundary", "dependency", "pattern"],
    "testing": ["test", "coverage", "assertion", "mock", "fixture", "edge case"],
    "documentation": ["docstring", "documentation", "comment", "readme", "adr"],
    "maintainability": ["readability", "complexity", "refactor", "duplicate", "naming"],
}


def _classify_severity(content: str) -> str:
    """Classify finding severity based on content keywords."""
    content_lower = content.lower()
    for severity, patterns in _SEVERITY_PATTERNS.items():
        if any(p in content_lower for p in patterns):
            return severity
    return "medium"


def _classify_category(content: str) -> str:
    """Classify finding category based on content keywords."""
    content_lower = content.lower()
    best_category = "general"
    best_score = 0
    for category, patterns in _CATEGORY_PATTERNS.items():
        score = sum(1 for p in patterns if p in content_lower)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


def _extract_summary(content: str) -> str:
    """Extract a concise summary from finding content."""
    # Take first sentence or first 200 chars
    first_sentence = re.split(r"[.!?\n]", content)[0].strip()
    if len(first_sentence) > 200:
        return first_sentence[:197] + "..."
    return first_sentence


def find_discussion_dir(discussion_id: str) -> Path:
    """Find the directory for a given discussion ID."""
    for date_dir in sorted(DISCUSSIONS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or date_dir.name.startswith("."):
            continue
        candidate = date_dir / discussion_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Discussion directory not found for {discussion_id}")


def extract_findings(discussion_id: str) -> int:
    """Extract findings from a discussion's events and insert into the database.

    Args:
        discussion_id: The discussion to extract findings from.

    Returns:
        Number of findings extracted.
    """
    disc_dir = find_discussion_dir(discussion_id)
    events_path = disc_dir / "events.jsonl"

    if not events_path.exists():
        print(f"No events.jsonl found for {discussion_id}")
        return 0

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 0

    # Read events that contain findings (critique and proposal intents)
    finding_intents = {"critique", "proposal"}
    events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("intent") in finding_intents:
                events.append(event)

    if not events:
        print(f"No critique/proposal events in {discussion_id}")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(UTC).isoformat()
    count = 0

    for event in events:
        content = event.get("content", "")
        agent = event.get("agent", "unknown")
        turn_id = event.get("turn_id", 0)

        # Skip facilitator synthesis/context events
        if agent == "facilitator" and event.get("intent") == "proposal":
            tags = event.get("tags", [])
            if any(t in tags for t in ["context-brief", "build-plan"]):
                continue

        severity = _classify_severity(content)
        category = _classify_category(content)
        summary = _extract_summary(content)

        # Extract a raw excerpt (first 500 chars)
        raw_excerpt = content[:500] if len(content) > 500 else content

        conn.execute(
            """INSERT INTO findings
               (discussion_id, turn_id, agent, severity, category, summary, raw_excerpt, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (discussion_id, turn_id, agent, severity, category, summary, raw_excerpt, now),
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"Extracted {count} findings from {discussion_id}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract findings from discussion events")
    parser.add_argument("discussion_id", help="Discussion ID to extract findings from")
    args = parser.parse_args()
    extract_findings(args.discussion_id)


if __name__ == "__main__":
    main()
