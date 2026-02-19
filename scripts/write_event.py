"""Append a single event to a discussion's events.jsonl file.

Usage:
    python scripts/write_event.py <discussion_id> <agent> <intent> <content> [--reply-to N] [--confidence 0.8] [--tags tag1,tag2]

This is the atomic capture operation — each call appends exactly one event line.
"""

import argparse
import json
from datetime import datetime, timezone
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


def get_next_turn_id(events_path: Path) -> int:
    """Get the next turn_id by counting existing events."""
    if not events_path.exists() or events_path.stat().st_size == 0:
        return 1
    count = 0
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count + 1


def write_event(
    discussion_id: str,
    agent: str,
    intent: str,
    content: str,
    reply_to: int | None = None,
    confidence: float = 0.8,
    tags: list[str] | None = None,
    risk_flags: list[str] | None = None,
) -> int:
    """Append an event to the discussion's events.jsonl.

    Args:
        discussion_id: The discussion this event belongs to.
        agent: Which specialist agent produced this turn.
        intent: One of: proposal, critique, question, evidence, synthesis, decision, reflection.
        content: The substantive content of the turn.
        reply_to: Which turn_id this responds to (None for initial turns).
        confidence: Agent's self-assessed confidence (0-1).
        tags: Topical tags for retrieval.
        risk_flags: Any risk signals detected.

    Returns:
        The turn_id assigned to this event.
    """
    valid_intents = {
        "proposal",
        "critique",
        "question",
        "evidence",
        "synthesis",
        "decision",
        "reflection",
    }
    if intent not in valid_intents:
        raise ValueError(f"Invalid intent '{intent}'. Must be one of: {valid_intents}")

    disc_dir = find_discussion_dir(discussion_id)
    events_path = disc_dir / "events.jsonl"
    turn_id = get_next_turn_id(events_path)

    event = {
        "discussion_id": discussion_id,
        "turn_id": turn_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "reply_to": reply_to,
        "intent": intent,
        "content": content,
        "tags": tags or [],
        "confidence": confidence,
        "risk_flags": risk_flags or [],
    }

    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return turn_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Write an event to a discussion")
    parser.add_argument("discussion_id", help="Discussion ID")
    parser.add_argument("agent", help="Agent name")
    parser.add_argument(
        "intent",
        choices=[
            "proposal",
            "critique",
            "question",
            "evidence",
            "synthesis",
            "decision",
            "reflection",
        ],
    )
    parser.add_argument("content", help="Event content")
    parser.add_argument("--reply-to", type=int, default=None)
    parser.add_argument("--confidence", type=float, default=0.8)
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--risk-flags", default="", help="Comma-separated risk flags")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    risk_flags = (
        [r.strip() for r in args.risk_flags.split(",") if r.strip()] if args.risk_flags else []
    )

    turn_id = write_event(
        args.discussion_id,
        args.agent,
        args.intent,
        args.content,
        reply_to=args.reply_to,
        confidence=args.confidence,
        tags=tags,
        risk_flags=risk_flags,
    )
    print(f"Turn {turn_id} written to {args.discussion_id}")


if __name__ == "__main__":
    main()
