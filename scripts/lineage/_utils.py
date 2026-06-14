"""Shared utilities for the lineage tracking package.

Provides file hashing and framework-file collection used by drift detection,
lineage initialization, and the distribute/apply routes.

The corpus enumerator respects git's exclusions (ADR-0025): when ``project_root``
is a git repository it lists TRACKED files via ``git ls-files`` — so gitignored
worktrees, ``__pycache__``, ``.pyc``, local state, ``settings.local.json``, etc.
never enter the framework corpus. When ``project_root`` is not a git repo it falls
back to a filesystem walk minus a denylist of framework-shaped junk. The root is
resolved to an absolute path before any git invocation (an absolute path cannot
begin with ``-``, which closes argument-injection into the subprocess).
"""

import hashlib
import subprocess
from pathlib import Path

from scripts.lineage.manifest import FRAMEWORK_PATHS

# Bound a hung git process so the corpus builder cannot block indefinitely.
_GIT_TIMEOUT = 15


def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file's contents.

    Args:
        path: Path to the file to hash.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_git_repo(project_root: Path) -> bool:
    """Return True if ``project_root`` is inside a git work tree.

    A non-zero exit or any OS/timeout error on this PROBE means "not a git repo"
    (legitimate — fall back to the filesystem walk). This is deliberately distinct
    from a failure of ``ls-files`` *after* a positive probe, which is a real error
    in a known repo and is raised rather than silently degraded (ADR-0025).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == b"true"


def _git_ls_files(project_root: Path, prefix: str, *, others: bool = False) -> list[str]:
    """List files under ``prefix`` via ``git ls-files`` (NUL-delimited).

    Args:
        project_root: Resolved, absolute repo top (must already be ``.resolve()``'d).
        prefix: A framework-path entry — a directory prefix or a single file.
        others: When True, list untracked-but-not-ignored files
            (``--others --exclude-standard``) instead of tracked files.

    Returns:
        Forward-slash relative paths (git already emits forward slashes).

    Raises:
        RuntimeError: if git fails here — the caller has already confirmed a git
            repo via :func:`_is_git_repo`, so a failure now is a real error and
            must fail loud, never silently degrade to the denylist fallback.
    """
    cmd = ["git", "-C", str(project_root), "ls-files", "-z"]
    if others:
        cmd += ["--others", "--exclude-standard"]
    cmd += ["--", prefix]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=_GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"git ls-files failed in a known repo ({type(exc).__name__})") from exc
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files exited {result.returncode} in a known repo")
    # NUL-split per the ``-z`` flag — NEVER splitlines(): a filename containing a
    # newline could otherwise smuggle a spurious entry into the corpus.
    return [e.decode("utf-8", errors="replace") for e in result.stdout.split(b"\x00") if e]


def _is_framework_junk(rel_path: str) -> bool:
    """Return True if a forward-slash relative path is framework-shaped junk.

    Consulted ONLY on the non-git fallback path. On a git repo, git's own ignore
    rules are the single source of truth and this denylist is never reached. It is
    a best-effort exclusion of *framework-shaped* junk for genuinely non-git roots,
    NOT a general ``.gitignore`` emulation (it cannot know a target's own ignores).

    Args:
        rel_path: A forward-slash-normalized relative path.
    """
    base = rel_path.rsplit("/", 1)[-1]
    return (
        rel_path.startswith(".claude/worktrees/")
        or "/__pycache__/" in rel_path
        or rel_path.endswith(".pyc")
        or rel_path.startswith(".claude/hooks/.state/")
        or rel_path.endswith("settings.local.json")
        or rel_path == ".claude/custodian/lineage-events.jsonl"
        or base.startswith("context-occupancy")
    )


def _rglob_corpus(project_root: Path, paths: list[str]) -> dict[str, str]:
    """Non-git fallback enumeration: filesystem walk minus the framework-junk denylist.

    The denylist predicate is applied to the forward-slash-normalized relative key in
    one place, never to the raw ``relative_to`` output (Windows backslash safety).
    """
    file_hashes: dict[str, str] = {}
    for prefix in paths:
        target = project_root / prefix
        if target.is_file():
            rel = str(target.relative_to(project_root)).replace("\\", "/")
            if not _is_framework_junk(rel):
                file_hashes[rel] = hash_file(target)
        elif target.is_dir():
            for file_path in sorted(target.rglob("*")):
                if file_path.is_file():
                    rel = str(file_path.relative_to(project_root)).replace("\\", "/")
                    if not _is_framework_junk(rel):
                        file_hashes[rel] = hash_file(file_path)
    return file_hashes


def collect_framework_files(
    project_root: Path,
    framework_paths: list[str] | None = None,
) -> dict[str, str]:
    """Collect framework files and their SHA-256 hashes, respecting git's exclusions.

    When ``project_root`` is a git repo, enumerates TRACKED files via ``git ls-files``
    so gitignored junk (worktrees, ``__pycache__``, local state) never enters the
    corpus. Otherwise falls back to a filesystem walk minus a framework-junk denylist.

    Args:
        project_root: Root directory of the project. Resolved to an absolute path
            internally before any git invocation.
        framework_paths: List of framework path prefixes to scan. Defaults to
            ``FRAMEWORK_PATHS`` from the manifest module.

    Returns:
        Dict mapping relative file paths (forward-slash separated) to SHA-256 hashes.
    """
    root = _resolve_root(project_root)
    paths = framework_paths or FRAMEWORK_PATHS

    if not _is_git_repo(root):
        return _rglob_corpus(root, paths)

    file_hashes: dict[str, str] = {}
    for prefix in paths:
        for rel in _git_ls_files(root, prefix):
            fp = root / rel
            if fp.is_file():
                file_hashes[rel] = hash_file(fp)
    return file_hashes


def list_untracked_framework_files(
    project_root: Path,
    framework_paths: list[str] | None = None,
) -> list[str]:
    """Untracked-but-not-ignored files under the framework paths (R3, ADR-0025).

    These are framework-shaped files git is neither tracking nor ignoring — i.e. new
    framework work that will NOT propagate via ``/apply-framework`` until committed.
    Detection lives here (the git information is cheap); the *decision to warn* lives
    in the apply layer, so drift/router/init_lineage do not pay for an apply concern.

    Args:
        project_root: Root directory of the project (resolved internally).
        framework_paths: Path prefixes to scan. Defaults to ``FRAMEWORK_PATHS``.

    Returns:
        Sorted forward-slash relative paths. Empty when ``project_root`` is not a
        git repo (no tracked/untracked distinction to make).
    """
    root = _resolve_root(project_root)
    paths = framework_paths or FRAMEWORK_PATHS
    if not _is_git_repo(root):
        return []
    untracked: set[str] = set()
    for prefix in paths:
        untracked.update(_git_ls_files(root, prefix, others=True))
    return sorted(untracked)


def _resolve_root(project_root: Path) -> Path:
    """Resolve to an absolute path and reject a flag-like root (SEC, ADR-0025).

    An absolute path cannot begin with ``-``, so resolving closes argument-injection
    into the ``git -C <root>`` subprocess; the explicit guard is belt-and-suspenders.
    """
    root = Path(project_root).resolve()
    # Platform note (security F1): on Windows ``resolve()`` prepends a drive letter
    # (e.g. ``C:\\...``), so this guard is vacuously never True on win32; it is the
    # load-bearing flag-injection check only on POSIX, where a resolved path can in
    # principle still be relative-looking. Kept as belt-and-suspenders on both.
    if str(root).startswith("-"):
        raise ValueError(f"project_root resolves to a flag-like path: {root!r}")
    return root
