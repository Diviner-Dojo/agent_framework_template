"""Shared utilities for the lineage tracking package.

Provides file hashing and framework file collection used by
both drift detection and lineage initialization.
"""

import hashlib
from pathlib import Path

from scripts.lineage.manifest import FRAMEWORK_PATHS


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


def collect_framework_files(
    project_root: Path,
    framework_paths: list[str] | None = None,
) -> dict[str, str]:
    """Collect all framework files and their SHA-256 hashes.

    Args:
        project_root: Root directory of the project.
        framework_paths: List of framework path prefixes to scan.
            Defaults to FRAMEWORK_PATHS from manifest module.

    Returns:
        Dict mapping relative file paths (forward-slash separated)
        to their SHA-256 hashes.
    """
    paths = framework_paths or FRAMEWORK_PATHS
    file_hashes: dict[str, str] = {}

    for prefix in paths:
        target = project_root / prefix
        if target.is_file():
            rel = str(target.relative_to(project_root)).replace("\\", "/")
            file_hashes[rel] = hash_file(target)
        elif target.is_dir():
            for file_path in sorted(target.rglob("*")):
                if file_path.is_file():
                    rel = str(file_path.relative_to(project_root)).replace("\\", "/")
                    file_hashes[rel] = hash_file(file_path)

    return file_hashes
