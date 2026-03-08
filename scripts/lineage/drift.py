"""Drift detection and reporting for framework lineage.

Compares current framework files against stored template hashes
to detect modifications, additions, and deletions.

Usage:
    python scripts/lineage/drift.py [path/to/framework-lineage.yaml]
"""

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for both CLI and module usage
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.lineage._utils import collect_framework_files  # noqa: E402
from scripts.lineage.manifest import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    FRAMEWORK_PATHS,
    manifest_read,
)

PROJECT_ROOT = _PROJECT_ROOT
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


@dataclass
class FileDrift:
    """Represents the drift status of a single framework file."""

    file_path: str
    drift_status: str  # current, modified, pinned, deleted, added
    is_intentional: bool
    template_hash: str | None
    local_hash: str | None
    pin_reason: str | None = None
    adr_reference: str | None = None


def _load_pinned_traits(manifest_data: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Extract pinned traits from manifest, keyed by file path pattern.

    Args:
        manifest_data: Parsed manifest dictionary.

    Returns:
        Dict mapping file path patterns to pin metadata.
    """
    pinned: dict[str, dict[str, str]] = {}
    for trait in manifest_data.get("pinned_traits", []):
        if isinstance(trait, dict) and "path" in trait:
            pinned[trait["path"]] = {
                "reason": trait.get("reason", ""),
                "adr": trait.get("adr_reference", ""),
            }
    return pinned


def _is_pinned(file_path: str, pinned_traits: dict[str, dict[str, str]]) -> dict[str, str] | None:
    """Check if a file path matches any pinned trait pattern.

    Args:
        file_path: Relative file path to check.
        pinned_traits: Dict of pinned path patterns to metadata.

    Returns:
        Pin metadata dict if pinned, None otherwise.
    """
    for pattern, metadata in pinned_traits.items():
        if file_path == pattern or file_path.startswith(pattern):
            return metadata
    return None


def drift_scan(
    manifest_path: Path | None = None,
    project_root: Path | None = None,
    db_path: Path | None = None,
) -> list[FileDrift]:
    """Scan framework files for drift against stored template hashes.

    Compares current file hashes against the template baselines stored
    in the lineage_file_drift SQLite table.

    Args:
        manifest_path: Path to framework-lineage.yaml.
        project_root: Root directory of the project.
        db_path: Path to the SQLite database.

    Returns:
        List of FileDrift objects describing each file's status.
    """
    root = project_root or PROJECT_ROOT
    db = db_path or DB_PATH
    m_path = manifest_path or DEFAULT_MANIFEST_PATH

    manifest_data = manifest_read(m_path)
    lineage_id = manifest_data.get("lineage_id", "")
    pinned_traits = _load_pinned_traits(manifest_data)

    # Get tracked paths from manifest or use defaults
    tracked_paths = manifest_data.get("tracked_paths", FRAMEWORK_PATHS)

    # Collect current file hashes
    current_files = collect_framework_files(root, tracked_paths)

    # Load stored template hashes from SQLite
    template_hashes: dict[str, str] = {}
    pinned_files: dict[str, dict[str, str | None]] = {}
    if db.exists():
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT file_path, template_hash, is_intentional, pin_reason, adr_reference "
            "FROM lineage_file_drift WHERE lineage_id = ?",
            (lineage_id,),
        ).fetchall()
        conn.close()
        for row in rows:
            template_hashes[row[0]] = row[1] or ""
            if row[2]:
                pinned_files[row[0]] = {"reason": row[3], "adr": row[4]}

    results: list[FileDrift] = []
    all_paths = set(current_files.keys()) | set(template_hashes.keys())

    for file_path in sorted(all_paths):
        current_hash = current_files.get(file_path)
        template_hash = template_hashes.get(file_path)

        pin_meta = _is_pinned(file_path, pinned_traits) or pinned_files.get(file_path)

        if current_hash is None and template_hash is not None:
            # File was in template but deleted locally
            results.append(
                FileDrift(
                    file_path=file_path,
                    drift_status="pinned" if pin_meta else "deleted",
                    is_intentional=pin_meta is not None,
                    template_hash=template_hash,
                    local_hash=None,
                    pin_reason=pin_meta.get("reason") if pin_meta else None,
                    adr_reference=pin_meta.get("adr") if pin_meta else None,
                )
            )
        elif current_hash is not None and template_hash is None:
            # File added locally, not in template
            results.append(
                FileDrift(
                    file_path=file_path,
                    drift_status="added",
                    is_intentional=False,
                    template_hash=None,
                    local_hash=current_hash,
                )
            )
        elif current_hash != template_hash:
            # File modified from template
            results.append(
                FileDrift(
                    file_path=file_path,
                    drift_status="pinned" if pin_meta else "modified",
                    is_intentional=pin_meta is not None,
                    template_hash=template_hash,
                    local_hash=current_hash,
                    pin_reason=pin_meta.get("reason") if pin_meta else None,
                    adr_reference=pin_meta.get("adr") if pin_meta else None,
                )
            )
        else:
            # File unchanged
            results.append(
                FileDrift(
                    file_path=file_path,
                    drift_status="current",
                    is_intentional=False,
                    template_hash=template_hash,
                    local_hash=current_hash,
                )
            )

    return results


def compute_divergence_distance(scan_results: list[FileDrift]) -> int:
    """Compute the divergence distance from scan results.

    Counts files that are modified, added, or deleted (not current or pinned).

    Args:
        scan_results: List of FileDrift objects from drift_scan.

    Returns:
        Number of unintentionally drifted files.
    """
    return sum(1 for f in scan_results if f.drift_status in ("modified", "added", "deleted"))


def drift_report(scan_results: list[FileDrift]) -> str:
    """Generate a human-readable drift report.

    Args:
        scan_results: List of FileDrift objects from drift_scan.

    Returns:
        Formatted drift report string.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    distance = compute_divergence_distance(scan_results)

    current = [f for f in scan_results if f.drift_status == "current"]
    modified = [f for f in scan_results if f.drift_status == "modified"]
    added = [f for f in scan_results if f.drift_status == "added"]
    deleted = [f for f in scan_results if f.drift_status == "deleted"]
    pinned = [f for f in scan_results if f.drift_status == "pinned"]

    lines = [
        f"# Drift Report — {now}",
        "",
        f"**Total files tracked**: {len(scan_results)}",
        f"**Divergence distance**: {distance}",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| Current | {len(current)} |",
        f"| Modified | {len(modified)} |",
        f"| Added | {len(added)} |",
        f"| Deleted | {len(deleted)} |",
        f"| Pinned | {len(pinned)} |",
    ]

    if modified:
        lines.extend(["", "## Modified Files"])
        for f in modified:
            lines.append(f"- `{f.file_path}`")

    if added:
        lines.extend(["", "## Added Files"])
        for f in added:
            lines.append(f"- `{f.file_path}`")

    if deleted:
        lines.extend(["", "## Deleted Files"])
        for f in deleted:
            lines.append(f"- `{f.file_path}`")

    if pinned:
        lines.extend(["", "## Pinned Files (Intentional Divergence)"])
        for f in pinned:
            reason = f" — {f.pin_reason}" if f.pin_reason else ""
            adr = f" (see {f.adr_reference})" if f.adr_reference else ""
            lines.append(f"- `{f.file_path}`{reason}{adr}")

    return "\n".join(lines)


def main() -> None:
    """CLI entry point for drift scanning."""
    parser = argparse.ArgumentParser(description="Scan framework files for drift")
    parser.add_argument(
        "manifest",
        nargs="?",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to framework-lineage.yaml",
    )
    parser.add_argument(
        "--project-root",
        default=str(PROJECT_ROOT),
        help="Project root directory",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    project_root = Path(args.project_root)

    try:
        results = drift_scan(manifest_path, project_root)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(drift_report(results))


if __name__ == "__main__":
    main()
