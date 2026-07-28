"""PreToolUse validator: protected files and secret detection.

Reads JSON tool input from stdin, writes a hook response to stdout.
Always exits 0 — a hook failure must never block work.

Two checks, both chosen because instruction alone cannot guarantee them:

Protected files
  Hard-denies edits to .git/, .env, evaluation.db, and .claude/settings.json.
  Settings changes are a developer action by design.

Secret detection
  Scans written content for known credential shapes. Uses "ask" rather than
  "deny" so a false positive costs a keystroke, not a workflow. Test files
  are skipped — fixtures legitimately contain key-shaped strings.

v4 removed the file-locking subsystem: it coordinated concurrent agents
against a 120-second lease, and its unlock counterpart no longer exists.
See ADR-0029.
"""

import json
import re
import sys


def deny(reason: str) -> None:
    """Emit a deny decision and exit."""
    _emit("deny", reason)


def ask(reason: str) -> None:
    """Emit an ask decision and exit."""
    _emit("ask", reason)


def _emit(decision: str, reason: str) -> None:
    """Emit a PreToolUse hook decision and exit."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


SECRET_PATTERNS = [
    (
        "generic secret",
        re.compile(
            r"(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*[\"']\s*[a-zA-Z0-9+/]{20,}"
        ),
    ),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("JWT token", re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")),
    ("GitHub personal access token", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    ("private key", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
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

PROTECTED_PATTERNS = [".git/", ".env", "metrics/evaluation.db", ".claude/settings.json"]

TEST_FILE_PATTERNS = re.compile(
    r"(test_.*\.py|.*_test\.py|.*/tests/.*\.py|.*\.test\.[tj]sx?|.*\.spec\.[tj]sx?)$"
)


def is_protected(file_path: str) -> bool:
    """Check whether a path is protected from modification."""
    normalized = file_path.replace("\\", "/")
    if normalized.endswith(".env"):
        return True
    return any(pattern in normalized for pattern in PROTECTED_PATTERNS)


def detect_secret(content: str) -> str | None:
    """Return the name of the first secret shape found, or None."""
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(content):
            return name
    return None


def is_test_file(file_path: str) -> bool:
    """Check whether a path is a test file (secret detection is skipped there)."""
    return bool(TEST_FILE_PATTERNS.search(file_path.replace("\\", "/")))


def main() -> None:
    """Validate a pending Write/Edit against protected paths and secret shapes."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    tool_name = data.get("tool_name", "")

    if not file_path:
        return

    if is_protected(file_path):
        deny("Cannot modify protected file. This is a developer action by design.")

    if is_test_file(file_path):
        return

    if tool_name in ("Write", "Edit"):
        content = tool_input.get("content", tool_input.get("new_string", ""))
        if content:
            secret_type = detect_secret(content)
            if secret_type:
                ask(
                    f"Potential {secret_type} detected in content being written. "
                    "Confirm this is not sensitive data."
                )


if __name__ == "__main__":
    main()
