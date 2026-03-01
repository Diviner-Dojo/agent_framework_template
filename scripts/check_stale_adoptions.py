"""Check for stale PENDING patterns in the adoption log.

Parses memory/lessons/adoption-log.md for PENDING patterns and reports
staleness. Returns exit code 2 if stale count exceeds threshold.

Usage:
    python scripts/check_stale_adoptions.py
    python scripts/check_stale_adoptions.py --threshold 10
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ADOPTION_LOG = PROJECT_ROOT / "memory" / "lessons" / "adoption-log.md"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Pattern to match adoption log entries
# Looks for lines like: | Pattern Name | Status | ... | YYYY-MM-DD | ...
ENTRY_PATTERN = re.compile(
    r"\|\s*(?P<pattern>[^|]+?)\s*\|"  # pattern name
    r"\s*(?P<status>[^|]+?)\s*\|"  # status
    r"(?:.*?\|)*?"  # skip middle columns
    r"\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|",  # date
    re.IGNORECASE,
)

# Alternative: match PENDING entries in various formats
STATUS_PATTERN = re.compile(r"\bPENDING\b", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_adoption_log(log_path: Path = ADOPTION_LOG) -> list[dict]:
    """Parse the adoption log for PENDING patterns.

    The adoption log uses markdown heading + list format:
        ### Pattern Name
        - **First seen**: project (YYYY-MM-DD)
        - **Status**: ADOPTED
        - **Adoption Status**: PENDING

    Returns:
        List of dicts with pattern name, date, and age in days.
    """
    if not log_path.exists():
        print(f"{RED}Adoption log not found: {log_path}{RESET}")
        return []

    text = log_path.read_text(encoding="utf-8")
    pending_entries = []

    # Parse entry by entry: each entry starts with ### heading
    current_name = None
    current_date = None
    is_pending = False

    for line in text.split("\n"):
        stripped = line.strip()

        # New entry starts with ### heading
        if stripped.startswith("### "):
            # Process previous entry if it was PENDING
            if current_name and is_pending and current_date:
                try:
                    entry_date = datetime.strptime(current_date, "%Y-%m-%d")
                    age_days = (datetime.now() - entry_date).days
                    pending_entries.append(
                        {
                            "pattern": current_name,
                            "date": current_date,
                            "age_days": age_days,
                        }
                    )
                except ValueError:
                    pass

            current_name = stripped[4:].strip()
            current_date = None
            is_pending = False
            continue

        # Look for "Adoption Status": PENDING (specific to adopted patterns)
        if "Adoption Status" in stripped and STATUS_PATTERN.search(stripped):
            is_pending = True

        # Look for dates in "First seen" or "Analysis" lines
        if ("First seen" in stripped or "Analysis" in stripped) and not current_date:
            date_match = DATE_PATTERN.search(stripped)
            if date_match:
                current_date = date_match.group()

    # Process last entry
    if current_name and is_pending and current_date:
        try:
            entry_date = datetime.strptime(current_date, "%Y-%m-%d")
            age_days = (datetime.now() - entry_date).days
            pending_entries.append(
                {
                    "pattern": current_name,
                    "date": current_date,
                    "age_days": age_days,
                }
            )
        except ValueError:
            pass

    return pending_entries


def check_stale_adoptions(threshold: int = 5) -> int:
    """Check for stale PENDING patterns and report.

    Args:
        threshold: Number of stale patterns that triggers exit code 2.

    Returns:
        Exit code: 0 if no action needed, 2 if stale count exceeds threshold.
    """
    entries = parse_adoption_log()

    if not entries:
        print(f"{GREEN}No PENDING patterns found in adoption log.{RESET}")
        return 0

    stale_entries = [e for e in entries if e["age_days"] > 14]

    print(f"\n{BOLD}Adoption Log Status{RESET}")
    print(f"  Total PENDING: {len(entries)}")
    print(f"  Stale (>14 days): {len(stale_entries)}")

    if entries:
        oldest = max(entries, key=lambda e: e["age_days"])
        print(f"  Oldest: {oldest['pattern']} ({oldest['age_days']} days)")

    if stale_entries:
        print(f"\n{YELLOW}Stale PENDING patterns:{RESET}")
        for entry in sorted(stale_entries, key=lambda e: -e["age_days"]):
            print(f"  - {entry['pattern']} ({entry['age_days']} days, since {entry['date']})")

    if len(stale_entries) > threshold:
        print(
            f"\n{RED}{BOLD}TRIGGER: {len(stale_entries)} stale patterns "
            f"exceed threshold of {threshold}.{RESET}"
        )
        print("  Recommendation: Run /batch-evaluate to clear the backlog.")
        return 2

    print(f"\n{GREEN}Stale count ({len(stale_entries)}) within threshold ({threshold}).{RESET}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check for stale PENDING adoption patterns")
    parser.add_argument(
        "--threshold",
        type=int,
        default=5,
        help="Stale count threshold for triggering alert (default: 5)",
    )
    args = parser.parse_args()
    exit_code = check_stale_adoptions(threshold=args.threshold)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
