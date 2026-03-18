"""Bump the project version in pyproject.toml.

Reads and updates the `version` key under the `[project]` section using
regex-based matching to preserve TOML formatting. Only modifies the
version line under `[project]`, not version keys in other sections.

Usage:
    python scripts/bump_version.py --read
    python scripts/bump_version.py --patch
    python scripts/bump_version.py --minor
    python scripts/bump_version.py --major
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

# Strict semver validation
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Match version = "X.Y.Z" line (with flexible whitespace and quoting)
_VERSION_LINE_RE = re.compile(r'^(version\s*=\s*["\'])(\d+\.\d+\.\d+)(["\'].*)$')


class VersionNotFoundError(Exception):
    """Raised when no version line is found under [project] in pyproject.toml."""


def _find_project_version(lines: list[str]) -> tuple[int, str]:
    """Find the version line index under [project] section.

    Args:
        lines: Lines of the pyproject.toml file.

    Returns:
        Tuple of (line_index, current_version_string).

    Raises:
        VersionNotFoundError: If no version line is found under [project].
    """
    in_project_section = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track which TOML section we're in
        if stripped.startswith("["):
            in_project_section = stripped == "[project]"
            continue

        if in_project_section:
            match = _VERSION_LINE_RE.match(stripped)
            if match:
                return i, match.group(2)

    raise VersionNotFoundError(
        "No 'version = \"X.Y.Z\"' line found under [project] section in pyproject.toml"
    )


def read_version(pyproject_path: Path | None = None) -> str:
    """Read the current version from pyproject.toml.

    Args:
        pyproject_path: Override path to pyproject.toml (for testing).

    Returns:
        Current version string.

    Raises:
        FileNotFoundError: If pyproject.toml does not exist.
        VersionNotFoundError: If no version line is found under [project].
    """
    path = pyproject_path or PYPROJECT_PATH
    if not path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    _, version = _find_project_version(lines)
    return version


def bump_version(
    bump_type: str,
    pyproject_path: Path | None = None,
) -> tuple[str, str]:
    """Bump the version in pyproject.toml.

    Args:
        bump_type: One of 'patch', 'minor', 'major'.
        pyproject_path: Override path to pyproject.toml (for testing).

    Returns:
        Tuple of (old_version, new_version).

    Raises:
        FileNotFoundError: If pyproject.toml does not exist.
        VersionNotFoundError: If no version line is found under [project].
        ValueError: If the computed version fails semver validation.
    """
    path = pyproject_path or PYPROJECT_PATH
    if not path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {path}")

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # Find version line (use non-keepends lines for matching)
    clean_lines = text.splitlines()
    line_idx, old_version = _find_project_version(clean_lines)

    # Compute new version
    parts = old_version.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(
            f"Invalid bump_type: {bump_type!r}. Must be 'major', 'minor', or 'patch'."
        )

    new_version = f"{major}.{minor}.{patch}"

    # Validate output against strict semver
    if not _SEMVER_RE.match(new_version):
        raise ValueError(f"Computed version '{new_version}' is not valid semver")

    # Replace version in the specific line, preserving formatting
    old_line = lines[line_idx]
    new_line = _VERSION_LINE_RE.sub(
        lambda m: f"{m.group(1)}{new_version}{m.group(3)}",
        old_line.rstrip("\n"),
    )
    # Preserve original line ending
    if old_line.endswith("\n"):
        new_line += "\n"

    lines[line_idx] = new_line
    path.write_text("".join(lines), encoding="utf-8")

    return old_version, new_version


def main() -> None:
    """CLI entrypoint for bump_version."""
    parser = argparse.ArgumentParser(description="Bump version in pyproject.toml")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--read", action="store_true", help="Print current version")
    group.add_argument("--patch", action="store_true", help="Bump patch version (X.Y.Z+1)")
    group.add_argument("--minor", action="store_true", help="Bump minor version (X.Y+1.0)")
    group.add_argument("--major", action="store_true", help="Bump major version (X+1.0.0)")

    args = parser.parse_args()

    try:
        if args.read:
            version = read_version()
            print(version)
        else:
            bump_type = "patch" if args.patch else "minor" if args.minor else "major"
            old, new = bump_version(bump_type)
            print(f"{old} → {new}")
    except (FileNotFoundError, VersionNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
