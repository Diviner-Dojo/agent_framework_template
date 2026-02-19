"""Generate a human-readable transcript.md from events.jsonl.

Usage:
    python scripts/generate_transcript.py <discussion_id>
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"


def find_discussion_dir(discussion_id: str) -> Path:
    """Find the directory for a given discussion ID."""
    for date_dir in sorted(DISCUSSIONS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or date_dir.name.startswith("."):
            continue
        candidate = date_dir / discussion_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Discussion directory not found for {discussion_id}")


def generate_transcript(discussion_id: str) -> Path:
    """Generate transcript.md from events.jsonl.

    Args:
        discussion_id: The discussion to generate a transcript for.

    Returns:
        Path to the generated transcript.md file.
    """
    disc_dir = find_discussion_dir(discussion_id)
    events_path = disc_dir / "events.jsonl"
    transcript_path = disc_dir / "transcript.md"

    events = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    # Build transcript
    lines = []
    lines.append("---")
    lines.append(f"discussion_id: {discussion_id}")
    if events:
        lines.append(f"started: {events[0]['timestamp']}")
        lines.append(f"ended: {events[-1]['timestamp']}")
        agents = sorted(set(e["agent"] for e in events))
        lines.append(f"agents: [{', '.join(agents)}]")
        lines.append(f"total_turns: {len(events)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Discussion: {discussion_id}")
    lines.append("")

    for event in events:
        ts = event["timestamp"]
        agent = event["agent"]
        intent = event["intent"]
        confidence = event["confidence"]
        reply_to = event.get("reply_to")
        tags = event.get("tags", [])
        risk_flags = event.get("risk_flags", [])

        lines.append(f"## Turn {event['turn_id']} — {agent} ({intent})")
        lines.append(f"*{ts} | confidence: {confidence}*")
        if reply_to:
            lines.append(f"*replying to turn {reply_to}*")
        if tags:
            lines.append(f"*tags: {', '.join(tags)}*")
        if risk_flags:
            lines.append(f"*risk flags: {', '.join(risk_flags)}*")
        lines.append("")
        lines.append(event["content"])
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Transcript written to {transcript_path}")
    return transcript_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate transcript from events")
    parser.add_argument("discussion_id", help="Discussion ID")
    args = parser.parse_args()
    generate_transcript(args.discussion_id)


if __name__ == "__main__":
    main()
