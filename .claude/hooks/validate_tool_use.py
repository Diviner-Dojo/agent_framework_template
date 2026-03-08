"""PreToolUse validator: file locking, protected files, and secret detection.

Reads JSON tool input from stdin. Outputs hook response JSON to stdout.
Exit code 0 always (hook errors should not block work).

File Locking:
  - Atomic lock acquisition via directory creation (race-condition safe)
  - Locks auto-expire after 120 seconds
  - Session-based: locks tied to the session that created them

Secret Detection:
  - Scans content for 12 secret patterns (API keys, AWS keys, JWT, Slack, Bearer, Anthropic, OpenAI, GCP, etc.)
  - Skips test files to reduce false positives
  - Uses "ask" permission to flag without hard-blocking

Protected Files:
  - Blocks edits to .git/, .env, evaluation.db, .claude/settings.json
"""

import json
import os
import re
import sys
import time
from pathlib import Path


def deny(reason: str) -> None:
    """Output a deny decision and exit."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def ask(reason: str) -> None:
    """Output an ask decision and exit."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


# --- Secret patterns ---
SECRET_PATTERNS = [
    (
        "generic secret",
        re.compile(
            r"(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*[\"']\s*[a-zA-Z0-9+/]{20,}"
        ),
    ),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "JWT token",
        re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
    ),
    ("GitHub personal access token", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    (
        "private key",
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "exported secret",
        re.compile(
            r"(?i)export\s+(API_KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|AWS_|PRIVATE_KEY)=[\"']\s*[a-zA-Z0-9+/]{20,}"
        ),
    ),
    ("Slack token", re.compile(r"xox[bpsa]-[a-zA-Z0-9-]{10,}")),
    (
        "Bearer token",
        re.compile(r"(?i)(?:bearer|authorization)\s*[=:]\s*(?:bearer\s+)?[a-zA-Z0-9_.+/=-]{20,}"),
    ),
    ("Anthropic API key", re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}")),
    ("OpenAI API key", re.compile(r"sk-proj-[a-zA-Z0-9_-]{20,}")),
    ("GCP API key", re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}")),
    ("GCP OAuth token", re.compile(r"ya29\.[a-zA-Z0-9_-]{50,}")),
]

# --- Protected file patterns ---
PROTECTED_PATTERNS = [".git/", ".env", "metrics/evaluation.db", ".claude/settings.json"]

# --- Test file patterns (skip secret detection) ---
TEST_FILE_PATTERNS = re.compile(
    r"(test_.*\.py|.*_test\.py|.*/tests/.*\.py|.*\.test\.[tj]sx?|.*\.spec\.[tj]sx?)$"
)


def is_protected(file_path: str) -> bool:
    """Check if file is protected from modification."""
    normalized = file_path.replace("\\", "/")
    if normalized.endswith("/.env") or normalized.endswith(".env"):
        return True
    for pattern in PROTECTED_PATTERNS:
        if pattern in normalized:
            return True
    return False


def detect_secret(content: str) -> str | None:
    """Return the type of secret found in content, or None."""
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(content):
            return name
    return None


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file (skip secret detection)."""
    return bool(TEST_FILE_PATTERNS.search(file_path.replace("\\", "/")))


def lock_file_path(lock_dir: Path, rel_path: str) -> Path:
    """Generate a safe lock file path from a relative file path."""
    safe_name = rel_path.replace("/", "_").replace("\\", "_")
    return lock_dir / f"{safe_name}.lock"


def try_acquire_lock(lock_dir: Path, rel_path: str, session_id: str) -> str | None:
    """Try to acquire a file lock. Returns error message or None on success."""
    lock_file = lock_file_path(lock_dir, rel_path)

    # Check for existing lock from another session
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text())
            lock_session = lock_data.get("session_id", "")
            lock_time = lock_data.get("timestamp", 0)
            time_diff = int(time.time()) - lock_time

            # Lock expires after 120 seconds
            if time_diff < 120 and lock_session != session_id and lock_session:
                return (
                    f"File '{rel_path}' is being edited by another agent. "
                    "Wait for completion or coordinate."
                )
        except (json.JSONDecodeError, OSError):
            pass  # Stale/corrupt lock, overwrite it

    # Acquire lock atomically using directory creation
    acquiring_dir = lock_file.parent / f"{lock_file.name}.acquiring"
    try:
        acquiring_dir.mkdir(exist_ok=False)
    except FileExistsError:
        return (
            "Failed to acquire file lock — another agent may be editing this file. Wait and retry."
        )

    try:
        lock_data = {
            "session_id": session_id,
            "timestamp": int(time.time()),
            "file": rel_path,
        }
        lock_file.write_text(json.dumps(lock_data))
    finally:
        try:
            acquiring_dir.rmdir()
        except OSError:
            pass

    return None


def main() -> None:
    """Main entry point for PreToolUse validation."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    session_id = data.get("session_id", "")
    tool_name = data.get("tool_name", "")

    if not file_path:
        return

    # --- Protected Files ---
    if is_protected(file_path):
        deny("Cannot modify protected file. Use appropriate commands or escalate.")

    # --- File Locking ---
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    lock_dir = Path(project_dir) / ".claude" / "hooks" / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)

    # Compute relative path
    normalized_file = file_path.replace("\\", "/")
    normalized_project = project_dir.replace("\\", "/")
    if normalized_file.startswith(normalized_project):
        rel_path = normalized_file[len(normalized_project) :].lstrip("/")
    else:
        rel_path = normalized_file

    lock_error = try_acquire_lock(lock_dir, rel_path, session_id)
    if lock_error:
        deny(lock_error)

    # --- Secret Detection ---
    if is_test_file(file_path):
        return

    if tool_name in ("Write", "Edit"):
        content = tool_input.get("content", tool_input.get("new_string", ""))
        if content:
            secret_type = detect_secret(content)
            if secret_type:
                ask(
                    f"Potential {secret_type} detected in content being "
                    "written. Please verify this is not sensitive data."
                )


if __name__ == "__main__":
    main()
