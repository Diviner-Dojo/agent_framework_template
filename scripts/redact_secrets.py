"""Redact secrets from text before sending to AI agents.

This module provides read-time secret redaction — applied before external file
content is assembled into prompts sent to specialist agents (e.g., during
/analyze-project). This is DISTINCT from the PreToolUse write-time detection
in .claude/hooks/validate_tool_use.py, which prevents writing secrets to disk.

Pattern source: daegwang/self-learning-agent (context-builder.ts)
Adopted: ANALYSIS-20260219-042113-self-learning-agent
"""

import re

# Compiled regex patterns for secret detection.
# Each tuple: (secret_type, pattern, preserves_key_name)
# Key-name preservation: shows "API_KEY= [REDACTED]" not just "[REDACTED]"
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Generic secrets with key=value format (preserves key name)
    (
        "generic secret",
        re.compile(
            r"(?i)((?:api[_-]?key|secret[_-]?key|password|token|credential|auth)"
            r"\s*[=:]\s*)"
            r"""(['"]?)([a-zA-Z0-9+/_.@:!-]{16,})\2"""
        ),
    ),
    # AWS access key ID
    ("AWS access key", re.compile(r"((?:aws[_-]?)?)(AKIA[0-9A-Z]{16})")),
    # AWS secret access key (preserves key name)
    (
        "AWS secret key",
        re.compile(
            r"(?i)((?:aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*)"
            r"""(['"]?)([a-zA-Z0-9+/]{40})\2"""
        ),
    ),
    # JWT tokens
    (
        "JWT token",
        re.compile(r"()(eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)"),
    ),
    # GitHub personal access tokens
    ("GitHub PAT", re.compile(r"()(ghp_[a-zA-Z0-9]{36})")),
    # GitHub fine-grained tokens
    ("GitHub fine-grained token", re.compile(r"()(github_pat_[a-zA-Z0-9_]{60,})")),
    # Slack tokens (xoxb-, xoxp-, xoxs-, xoxa-)
    ("Slack token", re.compile(r"()(xox[bpsa]-[a-zA-Z0-9-]{10,})")),
    # Bearer authorization headers
    (
        "Bearer token",
        re.compile(
            r"(?i)((?:bearer|authorization)\s*[=:]\s*(?:bearer\s+)?)([a-zA-Z0-9_.+/=-]{20,})"
        ),
    ),
    # PEM private keys (multi-line — redacts just the marker)
    (
        "private key",
        re.compile(
            r"(-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----)"
            r"([\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----)"
        ),
    ),
    # Connection strings with embedded credentials
    (
        "connection string",
        re.compile(
            r"((?:mongodb|postgres|mysql|redis|amqp|mssql)(?:\+\w+)?://)"
            r"([^@\s]+@)"
        ),
    ),
    # Exported secrets in shell (preserves variable name)
    (
        "exported secret",
        re.compile(
            r"(?i)(export\s+(?:API_KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|AWS_\w+|PRIVATE_KEY)\s*=\s*)"
            r"""(['"]?)([a-zA-Z0-9+/_.@:!-]{16,})\2"""
        ),
    ),
    # Anthropic API key
    ("Anthropic API key", re.compile(r"()(sk-ant-[a-zA-Z0-9_-]{20,})")),
    # OpenAI API key
    ("OpenAI API key", re.compile(r"()(sk-proj-[a-zA-Z0-9_-]{20,})")),
    # GCP API key
    ("GCP API key", re.compile(r"()(AIzaSy[a-zA-Z0-9_-]{33})")),
    # GCP OAuth token
    ("GCP OAuth token", re.compile(r"()(ya29\.[a-zA-Z0-9_-]{50,})")),
]


def redact_secrets(text: str) -> str:
    """Redact secrets from text while preserving key names for debugging context.

    Args:
        text: The text content to redact.

    Returns:
        Text with secret values replaced by [REDACTED] markers, but with
        key/variable names preserved for debugging context.

    Example:
        >>> redact_secrets("API_KEY= sk-abc123def456ghi789")
        'API_KEY= [REDACTED]'
    """
    result = text
    for secret_type, pattern in _SECRET_PATTERNS:
        if secret_type == "private key":
            # Special handling: keep the BEGIN marker, redact the key body
            result = pattern.sub(r"\1\n[REDACTED PRIVATE KEY]", result)
        elif secret_type in ("generic secret", "AWS secret key", "exported secret"):
            # Three-group patterns: prefix, optional quote, value
            result = pattern.sub(r"\1[REDACTED]", result)
        elif secret_type == "connection string":
            # Keep the protocol, redact credentials
            result = pattern.sub(r"\1[REDACTED]@", result)
        else:
            # Two-group patterns: optional prefix, value
            result = pattern.sub(r"\1[REDACTED]", result)
    return result
