"""Shared git subprocess helper for the distribution package.

A single call site so ``repo_safety_check`` and ``stage_branch`` cannot silently diverge in how
they invoke git. Always list-form (never ``shell=True``) — no shell-injection surface.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_cmd(
    target: Path | str,
    *args: str,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a git command against the target repository.

    Args:
        target: Repository working directory (passed via ``git -C``).
        *args: git arguments (e.g. ``"status", "--porcelain"``).
        check: If True, raise ``CalledProcessError`` on a non-zero exit.

    Returns:
        The completed process (inspect ``returncode`` and ``stdout``).
    """
    return subprocess.run(
        ["git", "-C", str(target), *args],
        capture_output=True,
        text=True,
        check=check,
    )
