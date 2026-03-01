"""Read and bump the semantic version in pubspec.yaml.

Supports --read, --patch, --minor, --major, and --build flags.
Build number always increments on any bump.
Regex-based to preserve YAML comments and formatting.

Usage:
    python scripts/bump_version.py --read          # print current version
    python scripts/bump_version.py --patch         # 0.14.0+1 → 0.14.1+2
    python scripts/bump_version.py --minor         # 0.14.1+2 → 0.15.0+3
    python scripts/bump_version.py --major         # 0.15.0+3 → 1.0.0+4
    python scripts/bump_version.py --build         # 0.14.0+1 → 0.14.0+2
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PUBSPEC = PROJECT_ROOT / "pubspec.yaml"

# Matches the version line in pubspec.yaml: version: X.Y.Z+B
VERSION_RE = re.compile(r"^(version:\s*)(\d+)\.(\d+)\.(\d+)\+(\d+)(.*)$", re.MULTILINE)


def read_version(pubspec_path: Path = PUBSPEC) -> str:
    """Read the current version string from pubspec.yaml."""
    content = pubspec_path.read_text(encoding="utf-8")
    match = VERSION_RE.search(content)
    if not match:
        print("ERROR: No version line found in pubspec.yaml", file=sys.stderr)
        sys.exit(1)
    major, minor, patch, build = (
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
        int(match.group(5)),
    )
    return f"{major}.{minor}.{patch}+{build}"


def bump_version(
    bump_type: str,
    pubspec_path: Path = PUBSPEC,
) -> str:
    """Bump the version in pubspec.yaml and return the new version string.

    Args:
        bump_type: One of 'major', 'minor', 'patch', 'build'.
        pubspec_path: Path to pubspec.yaml.

    Returns:
        The new version string (e.g. '0.14.1+2').
    """
    content = pubspec_path.read_text(encoding="utf-8")
    match = VERSION_RE.search(content)
    if not match:
        print("ERROR: No version line found in pubspec.yaml", file=sys.stderr)
        sys.exit(1)

    prefix = match.group(1)  # "version: " (preserves spacing)
    major = int(match.group(2))
    minor = int(match.group(3))
    patch = int(match.group(4))
    build = int(match.group(5))
    suffix = match.group(6)  # trailing comment, if any

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    # build-only: no semver change

    # Build number always increments
    build += 1

    new_version = f"{major}.{minor}.{patch}+{build}"
    new_line = f"{prefix}{new_version}{suffix}"

    new_content = VERSION_RE.sub(new_line, content, count=1)
    pubspec_path.write_text(new_content, encoding="utf-8")

    return new_version


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Read or bump the version in pubspec.yaml",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--read", action="store_true", help="Print current version")
    group.add_argument("--patch", action="store_true", help="Bump patch version")
    group.add_argument("--minor", action="store_true", help="Bump minor version")
    group.add_argument("--major", action="store_true", help="Bump major version")
    group.add_argument("--build", action="store_true", help="Bump build number only")

    args = parser.parse_args()

    if args.read:
        print(read_version())
        return 0

    if args.patch:
        bump_type = "patch"
    elif args.minor:
        bump_type = "minor"
    elif args.major:
        bump_type = "major"
    else:
        bump_type = "build"

    new_version = bump_version(bump_type)
    print(new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
