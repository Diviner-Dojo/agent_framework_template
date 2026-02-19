"""PostToolUse lock release: releases file locks after Write/Edit completes.

Companion to validate_tool_use.py file locking.
"""

import json
import os
import sys
from pathlib import Path


def main() -> None:
    """Release file lock if we own it."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    session_id = data.get("session_id", "")

    if not file_path:
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    lock_dir = Path(project_dir) / ".claude" / "hooks" / ".locks"

    # Compute relative path
    normalized_file = file_path.replace("\\", "/")
    normalized_project = project_dir.replace("\\", "/")
    if normalized_file.startswith(normalized_project):
        rel_path = normalized_file[len(normalized_project) :].lstrip("/")
    else:
        rel_path = normalized_file

    safe_name = rel_path.replace("/", "_").replace("\\", "_")
    lock_file = lock_dir / f"{safe_name}.lock"

    if not lock_file.exists():
        return

    # Release lock only if we own it
    try:
        lock_data = json.loads(lock_file.read_text())
        if lock_data.get("session_id") == session_id:
            lock_file.unlink()
    except (json.JSONDecodeError, OSError):
        pass


if __name__ == "__main__":
    main()
