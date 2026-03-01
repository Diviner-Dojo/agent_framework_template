"""Knowledge pipeline dashboard — reports on all pipeline layers.

Provides visibility into:
1. Capture stats (Layer 1)
2. Extraction coverage (findings)
3. Pattern mining health
4. Layer 3 health (memory/)
5. Promotion throughput
6. Agent effectiveness
7. Adoption log status

Appends a trend record to metrics/knowledge_pipeline_log.jsonl.

Usage:
    python scripts/knowledge_dashboard.py
    python scripts/knowledge_dashboard.py --no-log
"""

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
MEMORY_DIR = PROJECT_ROOT / "memory"
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"
KNOWLEDGE_LOG = PROJECT_ROOT / "metrics" / "knowledge_pipeline_log.jsonl"
ADOPTION_LOG = MEMORY_DIR / "lessons" / "adoption-log.md"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"
CYAN = "\033[96m"

# Knowledge subdirectories
KNOWLEDGE_DIRS = ["patterns", "decisions", "reflections", "rules", "lessons"]


def _count_files(directory: Path, skip: set[str] | None = None) -> int:
    """Count non-hidden files in a directory."""
    if not directory.exists():
        return 0
    skip = skip or {".gitkeep"}
    return sum(1 for f in directory.iterdir() if f.is_file() and f.name not in skip)


def _count_discussions() -> int:
    """Count total discussion directories."""
    if not DISCUSSIONS_DIR.exists():
        return 0
    count = 0
    for date_dir in DISCUSSIONS_DIR.iterdir():
        if date_dir.is_dir() and not date_dir.name.startswith("."):
            count += sum(1 for d in date_dir.iterdir() if d.is_dir())
    return count


def _parse_adoption_pending() -> int:
    """Count PENDING entries in adoption log (Adoption Status: PENDING)."""
    if not ADOPTION_LOG.exists():
        return 0
    import re

    text = ADOPTION_LOG.read_text(encoding="utf-8")
    # Count lines with "Adoption Status" + PENDING (not documentation text)
    return len(re.findall(r"Adoption Status.*?PENDING", text, re.IGNORECASE))


def run_dashboard(log: bool = True) -> dict:
    """Run the knowledge pipeline dashboard.

    Args:
        log: If True, append trend record to JSONL log.

    Returns:
        Dict with all dashboard metrics.
    """
    metrics = {
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # ── Section 1: Capture Stats (Layer 1) ──
    total_discussions = _count_discussions()
    metrics["capture"] = {"total_discussions": total_discussions}

    db_available = DB_PATH.exists()
    conn = None
    if db_available:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA foreign_keys=ON")

        row = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) FROM discussions"
        ).fetchone()
        metrics["capture"]["db_discussions"] = row[0]
        metrics["capture"]["closed"] = row[1]
        metrics["capture"]["open"] = row[0] - row[1]

        turns_count = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        metrics["capture"]["total_turns"] = turns_count

    print(f"\n{BOLD}{CYAN}=== Knowledge Pipeline Dashboard ==={RESET}\n")

    print(f"{BOLD}1. Capture (Layer 1){RESET}")
    print(f"   Discussion directories: {total_discussions}")
    if db_available:
        print(
            f"   DB discussions: {metrics['capture']['db_discussions']} "
            f"(closed: {metrics['capture']['closed']}, open: {metrics['capture']['open']})"
        )
        print(f"   Total turns: {metrics['capture']['total_turns']}")

    # ── Section 2: Extraction Coverage ──
    if conn:
        findings_count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        findings_discussions = conn.execute(
            "SELECT COUNT(DISTINCT discussion_id) FROM findings"
        ).fetchone()[0]

        # Coverage = discussions with findings / total closed discussions
        closed_count = metrics["capture"].get("closed", 0)
        coverage_pct = (
            round(findings_discussions / closed_count * 100, 1) if closed_count > 0 else 0.0
        )

        by_severity = conn.execute(
            "SELECT severity, COUNT(*) FROM findings GROUP BY severity ORDER BY COUNT(*) DESC"
        ).fetchall()

        by_category = conn.execute(
            "SELECT category, COUNT(*) FROM findings GROUP BY category ORDER BY COUNT(*) DESC"
        ).fetchall()

        metrics["extraction"] = {
            "total_findings": findings_count,
            "discussions_with_findings": findings_discussions,
            "coverage_pct": coverage_pct,
            "by_severity": {r[0]: r[1] for r in by_severity},
            "by_category": {r[0]: r[1] for r in by_category},
        }

        print(f"\n{BOLD}2. Extraction Coverage{RESET}")
        print(f"   Total findings: {findings_count}")
        print(
            f"   Discussions with findings: {findings_discussions}/{closed_count} ({coverage_pct}%)"
        )
        if by_severity:
            severity_str = ", ".join(f"{s}: {c}" for s, c in by_severity)
            print(f"   By severity: {severity_str}")
        if by_category:
            category_str = ", ".join(f"{c}: {n}" for c, n in by_category[:5])
            print(f"   Top categories: {category_str}")
    else:
        metrics["extraction"] = {"total_findings": 0}
        print(f"\n{BOLD}2. Extraction Coverage{RESET}")
        print(f"   {YELLOW}Database not available{RESET}")

    # ── Section 3: Pattern Mining ──
    if conn:
        sightings_count = conn.execute("SELECT COUNT(*) FROM pattern_sightings").fetchone()[0]
        unique_patterns = conn.execute(
            "SELECT COUNT(DISTINCT pattern_key) FROM pattern_sightings"
        ).fetchone()[0]

        # Rule of Three hits
        try:
            r3_rows = conn.execute("SELECT * FROM v_rule_of_three").fetchall()
            r3_count = len(r3_rows)
        except sqlite3.OperationalError:
            r3_count = 0
            r3_rows = []

        metrics["pattern_mining"] = {
            "total_sightings": sightings_count,
            "unique_patterns": unique_patterns,
            "rule_of_three_hits": r3_count,
        }

        print(f"\n{BOLD}3. Pattern Mining{RESET}")
        print(f"   Total sightings: {sightings_count}")
        print(f"   Unique patterns: {unique_patterns}")
        print(f"   Rule of Three hits: {r3_count}")
        if r3_rows:
            for row in r3_rows[:5]:
                print(f"     - {row[0]}: {row[1]} discussions, {row[2]} agents")
    else:
        metrics["pattern_mining"] = {"total_sightings": 0}
        print(f"\n{BOLD}3. Pattern Mining{RESET}")
        print(f"   {YELLOW}Database not available{RESET}")

    # ── Section 4: Layer 3 Health ──
    layer3_counts = {}
    total_promoted = 0
    for subdir_name in KNOWLEDGE_DIRS:
        count = _count_files(MEMORY_DIR / subdir_name)
        layer3_counts[subdir_name] = count
        total_promoted += count

    archive_count = 0
    if (MEMORY_DIR / "archive").exists():
        for subdir in (MEMORY_DIR / "archive").iterdir():
            if subdir.is_dir():
                archive_count += _count_files(subdir)

    metrics["layer3"] = {
        "by_directory": layer3_counts,
        "total_promoted": total_promoted,
        "archived": archive_count,
    }

    print(f"\n{BOLD}4. Layer 3 Health (memory/){RESET}")
    print(f"   Total promoted artifacts: {total_promoted}")
    for name, count in layer3_counts.items():
        status = GREEN if count > 0 else YELLOW
        print(f"   {status}  {name}/: {count}{RESET}")
    print(f"   Archived: {archive_count}")

    # ── Section 5: Promotion Throughput ──
    if conn:
        try:
            candidates = conn.execute(
                "SELECT status, COUNT(*) FROM promotion_candidates GROUP BY status"
            ).fetchall()
            candidates_dict = {r[0]: r[1] for r in candidates}
            total_candidates = sum(r[1] for r in candidates)
        except sqlite3.OperationalError:
            candidates_dict = {}
            total_candidates = 0

        metrics["promotion"] = {
            "total_candidates": total_candidates,
            "by_status": candidates_dict,
        }

        print(f"\n{BOLD}5. Promotion Throughput{RESET}")
        print(f"   Total candidates: {total_candidates}")
        for status, count in candidates_dict.items():
            color = GREEN if status == "approved" else YELLOW if status == "pending" else RESET
            print(f"   {color}  {status}: {count}{RESET}")
    else:
        metrics["promotion"] = {"total_candidates": 0}

    # ── Section 6: Agent Effectiveness ──
    if conn:
        try:
            agent_rows = conn.execute("SELECT * FROM v_agent_dashboard").fetchall()
        except sqlite3.OperationalError:
            agent_rows = []

        metrics["agent_effectiveness"] = {
            "agents_tracked": len(agent_rows),
        }

        print(f"\n{BOLD}6. Agent Effectiveness{RESET}")
        if agent_rows:
            for row in agent_rows:
                agent, discussions, total, unique, uniq_pct, surv_pct, avg_conf, avg_cal = row
                print(
                    f"   {agent}: {discussions} disc, {total} findings, "
                    f"{uniq_pct or 0}% unique, {surv_pct or 0}% survived"
                )
        else:
            print(f"   {YELLOW}No agent effectiveness data yet{RESET}")
    else:
        metrics["agent_effectiveness"] = {"agents_tracked": 0}

    # ── Section 7: Adoption Log Status ──
    pending_count = _parse_adoption_pending()
    metrics["adoption"] = {"pending_count": pending_count}

    print(f"\n{BOLD}7. Adoption Log{RESET}")
    color = RED if pending_count > 10 else YELLOW if pending_count > 5 else GREEN
    print(f"   {color}PENDING patterns: {pending_count}{RESET}")

    # ── Section 8: Reflections ──
    if conn:
        refl_count = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
        refl_promoted = conn.execute(
            "SELECT COUNT(*) FROM reflections WHERE promoted = 1"
        ).fetchone()[0]

        metrics["reflections"] = {
            "total": refl_count,
            "promoted": refl_promoted,
        }

        print(f"\n{BOLD}8. Reflections{RESET}")
        print(f"   Total: {refl_count}")
        print(f"   Promoted: {refl_promoted}")
    else:
        metrics["reflections"] = {"total": 0}

    # ── Overall Health Score ──
    health_score = 0
    max_score = 7

    if metrics["capture"].get("closed", 0) > 0:
        health_score += 1  # Capture working
    if metrics["extraction"].get("total_findings", 0) > 0:
        health_score += 1  # Extraction working
    if metrics.get("pattern_mining", {}).get("total_sightings", 0) > 0:
        health_score += 1  # Mining working
    if total_promoted > 0:
        health_score += 1  # Layer 3 populated
    if metrics.get("promotion", {}).get("total_candidates", 0) > 0:
        health_score += 1  # Pipeline feeding candidates
    if metrics.get("agent_effectiveness", {}).get("agents_tracked", 0) > 0:
        health_score += 1  # Effectiveness tracked
    if metrics.get("reflections", {}).get("total", 0) > 0:
        health_score += 1  # Reflections flowing

    color = GREEN if health_score >= 5 else YELLOW if health_score >= 3 else RED
    print(f"\n{BOLD}Overall Pipeline Health: {color}{health_score}/{max_score}{RESET}")

    metrics["health_score"] = health_score
    metrics["health_max"] = max_score

    if conn:
        conn.close()

    # ── Append to trend log ──
    if log:
        KNOWLEDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(KNOWLEDGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        print(
            f"\n{GREEN}Trend record appended to {KNOWLEDGE_LOG.relative_to(PROJECT_ROOT)}{RESET}"
        )

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge pipeline dashboard")
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Skip appending trend record to JSONL log",
    )
    args = parser.parse_args()
    run_dashboard(log=not args.no_log)


if __name__ == "__main__":
    main()
