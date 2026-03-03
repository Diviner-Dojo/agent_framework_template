"""Generate a knowledge pipeline health dashboard.

Reports on all 5 pipeline layers: raw events, findings, patterns,
promotion candidates, and curated memory. Appends a JSONL record
to `metrics/knowledge_pipeline_log.jsonl`.

Usage:
    python scripts/knowledge_dashboard.py [--json]
"""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
MEMORY_DIR = PROJECT_ROOT / "memory"
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"
PIPELINE_LOG = PROJECT_ROOT / "metrics" / "knowledge_pipeline_log.jsonl"

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _count_memory_files() -> dict[str, int]:
    """Count files in each memory subdirectory."""
    counts: dict[str, int] = {}
    for subdir in ["decisions", "lessons", "patterns", "reflections", "rules", "bugs"]:
        path = MEMORY_DIR / subdir
        if path.is_dir():
            counts[subdir] = len(list(path.glob("*.md")))
        else:
            counts[subdir] = 0
    # Archive
    archive = MEMORY_DIR / "archive"
    if archive.is_dir():
        counts["archive"] = sum(1 for _ in archive.rglob("*.md"))
    else:
        counts["archive"] = 0
    return counts


def _count_discussions() -> int:
    """Count total discussion directories."""
    if not DISCUSSIONS_DIR.is_dir():
        return 0
    count = 0
    for date_dir in DISCUSSIONS_DIR.iterdir():
        if date_dir.is_dir() and not date_dir.name.startswith("."):
            count += sum(1 for d in date_dir.iterdir() if d.is_dir())
    return count


def generate_dashboard(output_json: bool = False) -> dict:
    """Generate a knowledge pipeline health report.

    Args:
        output_json: If True, output raw JSON instead of formatted text.

    Returns:
        Dashboard data dictionary.
    """
    dashboard: dict = {
        "timestamp": datetime.now(UTC).isoformat(),
        "layers": {},
    }

    # Layer 1: Raw discussions
    disc_count = _count_discussions()
    dashboard["layers"]["L1_discussions"] = {"count": disc_count}

    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))

        # Layer 2: Relational index
        try:
            turns_count = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            disc_db_count = conn.execute("SELECT COUNT(*) FROM discussions").fetchone()[0]
            closed_count = conn.execute(
                "SELECT COUNT(*) FROM discussions WHERE status = 'closed'"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            turns_count = disc_db_count = closed_count = 0

        dashboard["layers"]["L2_relational"] = {
            "discussions_indexed": disc_db_count,
            "discussions_closed": closed_count,
            "total_turns": turns_count,
        }

        # Knowledge pipeline tables
        try:
            findings_count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            findings_by_severity = dict(
                conn.execute(
                    "SELECT severity, COUNT(*) FROM findings GROUP BY severity"
                ).fetchall()
            )
        except sqlite3.OperationalError:
            findings_count = 0
            findings_by_severity = {}

        dashboard["layers"]["findings"] = {
            "total": findings_count,
            "by_severity": findings_by_severity,
        }

        try:
            sightings_count = conn.execute("SELECT COUNT(*) FROM pattern_sightings").fetchone()[0]
            unique_patterns = conn.execute(
                "SELECT COUNT(DISTINCT pattern_hash) FROM pattern_sightings"
            ).fetchone()[0]
            rule_of_three = conn.execute(
                """SELECT COUNT(DISTINCT pattern_hash) FROM pattern_sightings
                   GROUP BY pattern_hash
                   HAVING COUNT(DISTINCT discussion_id) >= 3"""
            ).fetchall()
        except sqlite3.OperationalError:
            sightings_count = unique_patterns = 0
            rule_of_three = []

        dashboard["layers"]["pattern_sightings"] = {
            "total_sightings": sightings_count,
            "unique_patterns": unique_patterns,
            "rule_of_three_qualified": len(rule_of_three),
        }

        try:
            candidates_count = conn.execute(
                "SELECT COUNT(*) FROM promotion_candidates"
            ).fetchone()[0]
            promoted_count = conn.execute(
                "SELECT COUNT(*) FROM promotion_candidates WHERE promoted = 1"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            candidates_count = promoted_count = 0

        dashboard["layers"]["promotion_candidates"] = {
            "total": candidates_count,
            "promoted": promoted_count,
            "pending": candidates_count - promoted_count,
        }

        # Agent effectiveness summary
        try:
            agent_stats = conn.execute(
                """SELECT agent,
                          SUM(findings_unique) as unique_f,
                          SUM(findings_duplicate) as dup_f,
                          ROUND(AVG(confidence_avg), 3) as avg_conf
                   FROM agent_effectiveness
                   GROUP BY agent
                   ORDER BY unique_f DESC"""
            ).fetchall()
            dashboard["layers"]["agent_effectiveness"] = {
                "agents_tracked": len(agent_stats),
                "by_agent": {
                    row[0]: {"unique": row[1], "duplicate": row[2], "avg_confidence": row[3]}
                    for row in agent_stats
                },
            }
        except sqlite3.OperationalError:
            dashboard["layers"]["agent_effectiveness"] = {"agents_tracked": 0, "by_agent": {}}

        conn.close()
    else:
        dashboard["layers"]["L2_relational"] = {"status": "database not found"}

    # Layer 3: Curated memory
    memory_counts = _count_memory_files()
    dashboard["layers"]["L3_curated_memory"] = memory_counts

    # Output
    if output_json:
        print(json.dumps(dashboard, indent=2))
    else:
        print(f"\n{BOLD}Knowledge Pipeline Dashboard{RESET}")
        print("=" * 50)

        l1 = dashboard["layers"].get("L1_discussions", {})
        print(f"\n{CYAN}Layer 1 — Immutable Discussions{RESET}")
        print(f"  Total discussions: {l1.get('count', 0)}")

        l2 = dashboard["layers"].get("L2_relational", {})
        print(f"\n{CYAN}Layer 2 — Relational Index{RESET}")
        print(f"  Discussions indexed: {l2.get('discussions_indexed', 0)}")
        print(f"  Discussions closed: {l2.get('discussions_closed', 0)}")
        print(f"  Total turns: {l2.get('total_turns', 0)}")

        findings = dashboard["layers"].get("findings", {})
        print(f"\n{CYAN}Findings Pipeline{RESET}")
        print(f"  Total findings: {findings.get('total', 0)}")
        for sev, count in findings.get("by_severity", {}).items():
            print(f"    {sev}: {count}")

        ps = dashboard["layers"].get("pattern_sightings", {})
        print(f"\n{CYAN}Pattern Sightings{RESET}")
        print(f"  Total sightings: {ps.get('total_sightings', 0)}")
        print(f"  Unique patterns: {ps.get('unique_patterns', 0)}")
        print(f"  Rule of Three qualified: {ps.get('rule_of_three_qualified', 0)}")

        pc = dashboard["layers"].get("promotion_candidates", {})
        print(f"\n{CYAN}Promotion Candidates{RESET}")
        print(f"  Total: {pc.get('total', 0)}")
        print(f"  Promoted: {pc.get('promoted', 0)}")
        print(f"  Pending: {pc.get('pending', 0)}")

        ae = dashboard["layers"].get("agent_effectiveness", {})
        print(f"\n{CYAN}Agent Effectiveness{RESET}")
        print(f"  Agents tracked: {ae.get('agents_tracked', 0)}")
        for agent, stats in ae.get("by_agent", {}).items():
            print(
                f"    {agent}: unique={stats['unique']}, dup={stats['duplicate']}, conf={stats['avg_confidence']}"
            )

        l3 = dashboard["layers"].get("L3_curated_memory", {})
        print(f"\n{CYAN}Layer 3 — Curated Memory{RESET}")
        for subdir, count in l3.items():
            print(f"  {subdir}: {count}")

        print("=" * 50)

    # Log to JSONL
    PIPELINE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PIPELINE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(dashboard) + "\n")

    return dashboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge pipeline health dashboard")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    generate_dashboard(output_json=args.json)


if __name__ == "__main__":
    main()
