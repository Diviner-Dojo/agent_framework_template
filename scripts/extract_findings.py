"""Extract structured findings from discussion events.

Parses events.jsonl for critique/proposal events and extracts individual
findings with severity, category, summary, and content excerpt.

Usage:
    python scripts/extract_findings.py <discussion_id>
    python scripts/extract_findings.py <discussion_id> --dry-run
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# Agent name → default finding category mapping
AGENT_CATEGORY_MAP = {
    "security-specialist": "security",
    "architecture-consultant": "architecture",
    "performance-analyst": "performance",
    "qa-specialist": "testing",
    "docs-knowledge": "documentation",
    "independent-perspective": "process",
    "ux-evaluator": "ux",
    "educator": "process",
    "facilitator": "process",
}

# Severity aliases (normalize various formats)
SEVERITY_ALIASES = {
    "critical": "critical",
    "crit": "critical",
    "high": "high",
    "medium": "medium",
    "med": "medium",
    "low": "low",
    "info": "info",
    "informational": "info",
    "note": "info",
}

# Finding patterns to match in event content
# Matches lines like: "- (High) description", "(1) MEDIUM: description",
# "- HIGH: description", "* (Medium) description"
FINDING_PATTERN = re.compile(
    r"^[\s]*[-*]?\s*"  # optional bullet
    r"(?:\(\d+\)\s*)?"  # optional numbered prefix like (1)
    r"\(?\s*"  # optional open paren
    r"(critical|crit|high|medium|med|low|info|informational|note)"  # severity
    r"\s*\)?\s*[:—–-]?\s*"  # close paren, separator
    r"(.+)",  # finding description
    re.IGNORECASE,
)

# Section header patterns
BLOCKING_HEADER = re.compile(r"^#+\s*BLOCKING|^BLOCKING\s*[:—]|^BLOCKING\s*$", re.IGNORECASE)
ADVISORY_HEADER = re.compile(r"^#+\s*ADVISORY|^ADVISORY\s*[:—]|^ADVISORY\s*$", re.IGNORECASE)


def find_discussion_dir(discussion_id: str) -> Path:
    """Find the directory for a given discussion ID."""
    for date_dir in sorted(DISCUSSIONS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or date_dir.name.startswith("."):
            continue
        candidate = date_dir / discussion_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Discussion directory not found for {discussion_id}")


def _infer_category(agent: str, tags: list[str]) -> str:
    """Infer finding category from agent name and tags."""
    # Check tags first for explicit category hints
    tag_category_map = {
        "security": "security",
        "architecture": "architecture",
        "performance": "performance",
        "qa": "testing",
        "testing": "testing",
        "docs": "documentation",
        "ux": "ux",
    }
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in tag_category_map:
            return tag_category_map[tag_lower]

    # Fall back to agent name
    return AGENT_CATEGORY_MAP.get(agent, "process")


def _parse_severity_from_section(line: str, current_section: str | None) -> str | None:
    """Infer severity from section context if not explicit in the line."""
    if current_section == "blocking":
        return "high"
    elif current_section == "advisory":
        return "medium"
    return None


def extract_findings_from_content(
    content: str, agent: str, tags: list[str], turn_id: int, discussion_id: str
) -> list[dict]:
    """Extract individual findings from a single event's content.

    Args:
        content: The event content text.
        agent: Agent that produced this event.
        tags: Tags from the event.
        turn_id: Turn ID of the event.
        discussion_id: Discussion this event belongs to.

    Returns:
        List of finding dictionaries.
    """
    findings = []
    category = _infer_category(agent, tags)
    current_section = None  # 'blocking' or 'advisory'
    finding_counter = 0

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section headers
        if BLOCKING_HEADER.search(stripped):
            current_section = "blocking"
            continue
        if ADVISORY_HEADER.search(stripped):
            current_section = "advisory"
            continue

        # Try to match finding pattern
        match = FINDING_PATTERN.match(stripped)
        if match:
            finding_counter += 1
            raw_severity = match.group(1).strip().lower()
            summary = match.group(2).strip()

            severity = SEVERITY_ALIASES.get(raw_severity, "medium")

            # Truncate summary for content_excerpt
            excerpt = summary[:500] if len(summary) > 500 else summary

            timestamp = datetime.now(UTC).isoformat()
            finding_id = f"F-{discussion_id}-T{turn_id}-{finding_counter}"

            findings.append(
                {
                    "finding_id": finding_id,
                    "discussion_id": discussion_id,
                    "turn_id": turn_id,
                    "agent": agent,
                    "severity": severity,
                    "category": category,
                    "summary": summary,
                    "content_excerpt": excerpt,
                    "disposition": "open",
                    "tags": json.dumps(tags) if tags else None,
                    "created_at": timestamp,
                }
            )

    return findings


def extract_findings(
    discussion_id: str, db_path: Path = DB_PATH, dry_run: bool = False
) -> list[dict]:
    """Extract findings from all events in a discussion.

    Args:
        discussion_id: The discussion to extract findings from.
        db_path: Path to the SQLite database.
        dry_run: If True, don't write to database.

    Returns:
        List of all findings extracted.
    """
    disc_dir = find_discussion_dir(discussion_id)
    events_path = disc_dir / "events.jsonl"

    if not events_path.exists():
        print(f"No events.jsonl found for {discussion_id}")
        return []

    all_findings = []

    with open(events_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            event = json.loads(line)

            # Only extract from critique and proposal events (where findings live)
            if event.get("intent") not in ("critique", "proposal"):
                continue

            # Skip facilitator synthesis (those summarize, not originate)
            agent = event.get("agent", "")
            if agent == "facilitator":
                continue

            findings = extract_findings_from_content(
                content=event["content"],
                agent=agent,
                tags=event.get("tags", []),
                turn_id=event["turn_id"],
                discussion_id=discussion_id,
            )
            all_findings.extend(findings)

    if dry_run:
        print(f"[DRY RUN] {discussion_id}: {len(all_findings)} findings found")
        for f in all_findings:
            print(f"  [{f['severity'].upper()}] ({f['category']}) {f['summary'][:80]}")
        return all_findings

    if not all_findings:
        print(f"No findings extracted for {discussion_id}")
        return []

    # Write to database
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    inserted = 0
    for finding in all_findings:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO findings
                   (finding_id, discussion_id, turn_id, agent, severity,
                    category, summary, content_excerpt, disposition, tags, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    finding["finding_id"],
                    finding["discussion_id"],
                    finding["turn_id"],
                    finding["agent"],
                    finding["severity"],
                    finding["category"],
                    finding["summary"],
                    finding["content_excerpt"],
                    finding["disposition"],
                    finding["tags"],
                    finding["created_at"],
                ),
            )
            if conn.total_changes > inserted:
                inserted += 1
        except sqlite3.IntegrityError:
            pass  # Duplicate finding_id, skip

    conn.commit()
    conn.close()

    print(f"Extracted {len(all_findings)} findings for {discussion_id} ({inserted} new)")
    return all_findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract findings from discussion events")
    parser.add_argument("discussion_id", help="Discussion ID to extract findings from")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show findings without writing to database",
    )
    args = parser.parse_args()
    extract_findings(args.discussion_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
