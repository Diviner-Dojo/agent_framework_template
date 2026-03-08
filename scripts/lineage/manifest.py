"""Manifest CRUD operations for framework-lineage.yaml.

Provides reading, validation, and updating of the lineage manifest
that tracks a project's relationship to the canonical template.

Usage:
    python scripts/lineage/manifest.py [--validate] [path/to/framework-lineage.yaml]
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent

DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "framework-lineage.yaml"

FRAMEWORK_PATHS: list[str] = [
    ".claude/",
    "scripts/",
    "CLAUDE.md",
    "docs/templates/",
    "docs/adr/",
]

REQUIRED_FIELDS: list[str] = [
    "schema_version",
    "lineage_id",
    "serial",
    "instance",
    "drift",
]

REQUIRED_INSTANCE_FIELDS: list[str] = [
    "name",
    "version",
    "type",
    "created_at",
]

VALID_INSTANCE_TYPES: list[str] = [
    "template",
    "derived",
    "soft-fork",
    "hard-fork",
]

VALID_DRIFT_STATUSES: list[str] = [
    "current",
    "behind",
    "ahead",
    "diverged",
]


def manifest_read(path: Path | None = None) -> dict[str, Any]:
    """Parse framework-lineage.yaml and return its contents.

    Args:
        path: Path to the manifest file. Defaults to project root.

    Returns:
        Parsed manifest as a dictionary.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    manifest_path = path or DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path) as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Empty manifest: {manifest_path}")

    return data


def manifest_validate(data: dict[str, Any]) -> list[str]:
    """Validate a manifest dictionary and return a list of errors.

    Args:
        data: Parsed manifest dictionary.

    Returns:
        List of validation error strings. Empty list means valid.
    """
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "instance" in data:
        instance = data["instance"]
        if not isinstance(instance, dict):
            errors.append("'instance' must be a mapping")
        else:
            for field in REQUIRED_INSTANCE_FIELDS:
                if field not in instance:
                    errors.append(f"Missing required instance field: {field}")
            if instance.get("type") and instance["type"] not in VALID_INSTANCE_TYPES:
                errors.append(
                    f"Invalid instance type: {instance['type']}. "
                    f"Must be one of: {VALID_INSTANCE_TYPES}"
                )

    if "drift" in data:
        drift = data["drift"]
        if not isinstance(drift, dict):
            errors.append("'drift' must be a mapping")
        elif "status" in drift and drift["status"] not in VALID_DRIFT_STATUSES:
            errors.append(
                f"Invalid drift status: {drift['status']}. Must be one of: {VALID_DRIFT_STATUSES}"
            )

    if "serial" in data:
        if not isinstance(data["serial"], int) or data["serial"] < 0:
            errors.append("'serial' must be a non-negative integer")

    if "pinned_traits" in data:
        if not isinstance(data["pinned_traits"], list):
            errors.append("'pinned_traits' must be a list")

    return errors


def manifest_update_drift(
    path: Path | None = None,
    *,
    status: str | None = None,
    divergence_distance: int | None = None,
) -> dict[str, Any]:
    """Update the drift section of the manifest and bump the serial counter.

    Args:
        path: Path to the manifest file. Defaults to project root.
        status: New drift status (current, behind, ahead, diverged).
        divergence_distance: New divergence distance value.

    Returns:
        Updated manifest dictionary.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
        ValueError: If the provided status is invalid.
    """
    manifest_path = path or DEFAULT_MANIFEST_PATH
    data = manifest_read(manifest_path)

    if status is not None:
        if status not in VALID_DRIFT_STATUSES:
            raise ValueError(
                f"Invalid drift status: {status}. Must be one of: {VALID_DRIFT_STATUSES}"
            )
        data.setdefault("drift", {})["status"] = status

    if divergence_distance is not None:
        data.setdefault("drift", {})["divergence_distance"] = divergence_distance

    data["serial"] = data.get("serial", 0) + 1

    with open(manifest_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return data


def main() -> None:
    """CLI entry point for manifest operations."""
    parser = argparse.ArgumentParser(description="Manifest operations for framework-lineage.yaml")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to framework-lineage.yaml",
    )
    parser.add_argument("--validate", action="store_true", help="Validate the manifest")
    args = parser.parse_args()

    manifest_path = Path(args.path)

    try:
        data = manifest_read(manifest_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.validate:
        errors = manifest_validate(data)
        if errors:
            print("Validation FAILED:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)
        else:
            print("Validation passed.")
    else:
        instance = data.get("instance", {})
        drift = data.get("drift", {})
        pinned = data.get("pinned_traits", [])
        print(f"Project: {instance.get('name', 'unknown')}")
        print(f"Version: {instance.get('version', 'unknown')}")
        print(f"Type: {instance.get('type', 'unknown')}")
        print(f"Drift status: {drift.get('status', 'unknown')}")
        print(f"Divergence distance: {drift.get('divergence_distance', 0)}")
        print(f"Pinned traits: {len(pinned)}")
        print(f"Serial: {data.get('serial', 0)}")


if __name__ == "__main__":
    main()
