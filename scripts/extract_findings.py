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

# Severity patterns for heuristic classification (scanned against the topical
# summary, not the full body — prevents body-mention pollution of critical tier).
# Qualified phrases required for critical; bare terms map to high/medium.
# Word-boundary matches (\\b) prevent substring-only false positives.
# See ADR-0022 and severity-calibration skill for tier definitions.
_SEVERITY_PATTERNS: dict[str, list[str]] = {
    "critical": [
        r"\binjection vulnerability\b",
        r"\bsql injection\b",
        r"\bcommand injection\b",
        r"\bcode injection\b",
        r"\bsecurity vulnerability\b",
        r"\bdata loss\b",
        r"\bauthentication bypass\b",
        r"\bremote code execution\b",
        r"\bprivilege escalation\b",
    ],
    "high": [
        r"\bbreaking change\b",
        r"\brace condition\b",
        r"\bmemory leak\b",
        r"\bunhandled error\b",
        r"\binjection\b",
        r"\bauth\b",
        r"\bcorruption\b",
        r"\bdata integrity\b",
    ],
    "medium": [
        r"\bmissing validation\b",
        r"\bmissing test\b",
        r"\berror handling\b",
        r"\bperformance\b",
        r"\bsecurity\b",
    ],
    "low": [r"\bstyle\b", r"\bnaming\b", r"\bdocumentation\b", r"\breadability\b", r"\btypo\b"],
    "info": [
        r"\bsuggestion\b",
        r"\bconsider\b",
        r"\bnice to have\b",
        r"\boptional\b",
        r"\bminor\b",
    ],
}

# Explicit severity marker — parse and trust over keyword heuristics.
# Matches "Severity: HIGH", "[CRITICAL]", "**HIGH**:", "(severity: medium)",
# "Severity: high," etc. The closing class accepts common trailing punctuation
# so a sentence-final tier word still parses (REV DISC-20260612-144008 fold:
# the prior class rejected ')' '.' ',' — "(severity: medium)" was documented
# here as supported but silently fell through to keyword heuristics).
_EXPLICIT_SEVERITY_RE = re.compile(
    r"(?:severity\s*[:=]\s*|"  # "Severity: X" or "Severity=X"
    r"\[|\*{1,2})"  # "[X]" or "**X**" or "*X*"
    r"(critical|high|medium|low|info)"
    r"(?:\]|\*{0,2}(?:[:\s.,;)]|$))",  # closing: ], or stars then punct/space/EOL
    re.IGNORECASE,
)

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


# Verdict / round-marker boilerplate patterns (ADR-0022, BUILD_STATUS 2026-05-28).
# Synthesis verdict headers and round/confidence markers are NOT code findings. When they
# leak into the findings table their summaries pollute the severity histogram and the token
# sets fed to mine_patterns (pattern_hash consumes the summary), producing phantom
# verdict-header promotion candidates. These match against the *extracted summary* (the first
# line/sentence) so that verdict-PREFIXED lines carrying substantive text — e.g.
# "REVISE: tests/ classification gap ..." — are kept, while pure boilerplate is dropped.
_VERDICT_TOKENS = "approve[- ]with[- ]changes|request[- ]changes|approve|reject|revise|pass|fail"
# A "Verdict:"/"Verdict." header line, with optional leading markdown hashes.
_VERDICT_HEADER_RE = re.compile(r"^\s*#*\s*verdict\s*[:.]", re.IGNORECASE)
# A round-marker line, e.g. "round 2: approve" or "(Round 2)".
_ROUND_MARKER_RE = re.compile(r"^\s*\(?\s*round\s+\d", re.IGNORECASE)
# A confidence-only line, e.g. "Confidence 0.91".
_CONFIDENCE_ONLY_RE = re.compile(r"^\s*confidence[\s:]*[\d.]+\s*$", re.IGNORECASE)
# A bare verdict marker: just the verdict word, optionally annotated with a round and/or
# confidence note and trailing punctuation, with no substantive text following.
# Conservative by design (REVIEW.md REV-20260529-054131 A3): a verdict token followed by a
# colon and prose — e.g. "Approve: the implementation looks correct" — is intentionally KEPT
# (the terminal $ anchor fails), since under-dropping a borderline finding is preferable to
# silently discarding a real one. events.jsonl is framework-agent-written, so the residual
# evasion is a quality, not a security, concern.
_BARE_VERDICT_RE = re.compile(
    rf"^\s*(?:{_VERDICT_TOKENS})"
    r"\s*(?:\(?\s*round\s*\d+\s*\)?)?"  # optional round annotation
    r"\s*(?:\(?\s*confidence[:\s]*[\d.]+\s*\)?)?"  # optional confidence annotation
    r"\s*[.:]?\s*$",
    re.IGNORECASE,
)
# (a) Markdown section headers that are pure review scaffolding — no content of their own.
# Verified not to match "Missing validation…" or "pass" as ordinary English (anchor+word-boundary).
_SCAFFOLD_HEADER_RE = re.compile(
    r"^\s*#{1,6}\s*"
    r"(findings|verdict|summary|recommendations?|blocking|advisori?e?s?)\s*$",
    re.IGNORECASE,
)
# (b) Finding-count summary lines, e.g. "8 findings (1 HIGH blocking…)", "3 findings".
_FINDING_COUNT_RE = re.compile(r"^\s*\d+\s+findings?\b", re.IGNORECASE)
# (c) Per-agent review header lines, e.g. "Security Review: 5 findings", "QA Review (0.91):".
_AGENT_REVIEW_HEADER_RE = re.compile(
    r"^\s*(qa|security|architecture|performance|ux|docs?|independent[- ]perspective)"
    r"[\w /\-]*\breview\b\s*[:(]",
    re.IGNORECASE,
)
# (d) Process-scaffold lines. Anchored with start-of-line to avoid matching ordinary prose
# containing "validation" (e.g. "Missing validation on the…" starts with "Missing", not these).
_PROCESS_SCAFFOLD_RE = re.compile(
    r"^\s*(validation pass complete|guided walkthrough\b|walkthrough for\b|scan complete\b"
    r"|scanning\b|analysis complete\b)",
    re.IGNORECASE,
)


def _is_verdict_boilerplate(summary: str) -> bool:
    """Return True if a summary is scaffold boilerplate rather than a real finding.

    Intentionally imported by ``scripts/backfill_finding_noise.py`` (single source of truth).

    Args:
        summary: The extracted summary (first line/sentence of finding content).

    Returns:
        True if the summary is verdict/round/confidence/scaffold boilerplate that should not be
        recorded as a finding.
    """
    return bool(
        _VERDICT_HEADER_RE.match(summary)
        or _ROUND_MARKER_RE.match(summary)
        or _CONFIDENCE_ONLY_RE.match(summary)
        or _BARE_VERDICT_RE.match(summary)
        or _SCAFFOLD_HEADER_RE.match(summary)
        or _FINDING_COUNT_RE.match(summary)
        or _AGENT_REVIEW_HEADER_RE.match(summary)
        or _PROCESS_SCAFFOLD_RE.match(summary)
    )


def _classify_severity(content: str, summary: str | None = None) -> str:
    """Classify finding severity based on content keywords.

    Intentionally imported by ``scripts/backfill_finding_noise.py`` (single source of truth).

    Args:
        content: Full event body; scanned for explicit severity markers.
        summary: Topical first sentence. Keyword heuristics scan this instead of the
            full body to prevent body-mention pollution. Derived from *content* if absent.

    Returns:
        Severity string: 'critical', 'high', 'medium', 'low', or 'info'.
    """
    # (1) Explicit marker wins — specialist-stated severity is authoritative.
    match = _EXPLICIT_SEVERITY_RE.search(content)
    if match:
        return match.group(1).lower()

    # (2) Keyword heuristics on the topical summary only (not the full body), using
    # word-boundary regex matches. Scan all tiers in severity order; return the
    # highest tier that matches (first-match in severity order == highest-tier-wins).
    scan_text = (summary if summary is not None else _extract_summary(content)).lower()
    _TIER_ORDER = ("critical", "high", "medium", "low", "info")
    for tier in _TIER_ORDER:
        if any(re.search(p, scan_text) for p in _SEVERITY_PATTERNS.get(tier, [])):
            return tier

    # (3) Default medium when nothing matches.
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

        summary = _extract_summary(content)

        # Drop empty/whitespace summaries (e.g. an event with no content) and synthesis
        # verdict / round-marker boilerplate before they are recorded as findings (F2).
        # Both pollute the severity histogram and the pattern-mining token sets.
        if not summary or _is_verdict_boilerplate(summary):
            continue

        severity = _classify_severity(content, summary)
        category = _classify_category(content)

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
