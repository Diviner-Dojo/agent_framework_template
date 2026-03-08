"""Initialize lineage tracking for a project.

Creates the framework-lineage.yaml manifest, .claude/custodian/ directory,
initial FORK event, and SQLite lineage_nodes entry.

Usage:
    python scripts/lineage/init_lineage.py --project-name NAME --template-version VERSION
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

# Ensure project root is on sys.path for both CLI and module usage
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.lineage._utils import collect_framework_files  # noqa: E402

PROJECT_ROOT = _PROJECT_ROOT
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "framework-lineage.yaml"
CUSTODIAN_DIR = PROJECT_ROOT / ".claude" / "custodian"
EVENTS_PATH = CUSTODIAN_DIR / "lineage-events.jsonl"


def _write_lineage_event(
    events_path: Path,
    event_type: str,
    data: dict,
) -> int:
    """Append a lineage event to the JSONL log.

    Args:
        events_path: Path to lineage-events.jsonl.
        event_type: Type of event (FORK, PIN, DRIFT_CHECK, etc.).
        data: Event payload data.

    Returns:
        The index of the written event.
    """
    events_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine next index
    index = 0
    if events_path.exists():
        with open(events_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    index += 1

    event = {
        "index": index,
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
        "content_hash": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
    }

    with open(events_path, "a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")

    return index


def lineage_init(
    project_root: Path | None = None,
    template_version: str = "2.1.0",
    project_name: str = "unnamed-project",
    project_type: str = "template",
    db_path: Path | None = None,
    manifest_path: Path | None = None,
    custodian_dir: Path | None = None,
) -> dict:
    """Initialize lineage tracking for a project.

    Creates the manifest file, custodian directory, initial FORK event,
    and SQLite entries.

    Args:
        project_root: Root directory of the project.
        template_version: Version of the template being forked from.
        project_name: Human-readable project name.
        project_type: Instance type (template, derived, soft-fork, hard-fork).
        db_path: Path to the SQLite database.
        manifest_path: Path for the manifest file.
        custodian_dir: Path for the custodian directory.

    Returns:
        The created manifest dictionary.

    Raises:
        FileExistsError: If a manifest already exists at the target path.
    """
    root = project_root or PROJECT_ROOT
    db = db_path or DB_PATH
    m_path = manifest_path or DEFAULT_MANIFEST_PATH
    c_dir = custodian_dir or CUSTODIAN_DIR
    events_path = c_dir / "lineage-events.jsonl"

    if m_path.exists():
        raise FileExistsError(f"Manifest already exists: {m_path}")

    now = datetime.now(UTC)
    lineage_id = str(uuid.uuid4())

    # Build manifest
    manifest = {
        "schema_version": "1.0",
        "lineage_id": lineage_id,
        "serial": 0,
        "instance": {
            "name": project_name,
            "version": f"1.0.0+upstream.{template_version}",
            "type": project_type,
            "created_at": now.isoformat(),
        },
        "upstream": {
            "locked": {
                "url": None,
                "commit_hash": None,
                "synced_at": now.isoformat(),
            },
        },
        "drift": {
            "status": "current",
            "divergence_distance": 0,
        },
        "pinned_traits": [],
        "custodian": {
            "primary_human": None,
            "approval_required_for": [
                "template_modification",
                "principle_change",
                "agent_restructuring",
            ],
        },
    }

    # Write manifest
    m_path.parent.mkdir(parents=True, exist_ok=True)
    with open(m_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    # Create custodian directory
    c_dir.mkdir(parents=True, exist_ok=True)

    # Compute and store framework file hashes
    file_hashes = collect_framework_files(root)

    # Write FORK event
    _write_lineage_event(
        events_path,
        "FORK",
        {
            "lineage_id": lineage_id,
            "project_name": project_name,
            "template_version": template_version,
            "project_type": project_type,
            "framework_files_count": len(file_hashes),
        },
    )

    # Insert into SQLite
    if db.exists():
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON")

        # Insert lineage node
        conn.execute(
            "INSERT OR IGNORE INTO lineage_nodes "
            "(id, name, type, created_at, current_version, upstream_version, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                lineage_id,
                project_name,
                project_type,
                now.isoformat(),
                f"1.0.0+upstream.{template_version}",
                template_version,
                json.dumps({"fork_source": "init"}),
            ),
        )

        # Insert file drift baselines
        for file_path, file_hash in file_hashes.items():
            conn.execute(
                "INSERT OR REPLACE INTO lineage_file_drift "
                "(lineage_id, file_path, drift_status, is_intentional, "
                "template_hash, local_hash, last_checked) "
                "VALUES (?, ?, 'current', FALSE, ?, ?, ?)",
                (lineage_id, file_path, file_hash, file_hash, now.isoformat()),
            )

        conn.commit()
        conn.close()

    print(f"Lineage initialized: {lineage_id}")
    print(f"Manifest: {m_path}")
    print(f"Events log: {events_path}")
    print(f"Framework files tracked: {len(file_hashes)}")

    return manifest


def main() -> None:
    """CLI entry point for lineage initialization."""
    parser = argparse.ArgumentParser(description="Initialize lineage tracking")
    parser.add_argument("--project-name", required=True, help="Human-readable project name")
    parser.add_argument(
        "--template-version", default="2.1.0", help="Template version to fork from"
    )
    parser.add_argument(
        "--project-type",
        default="template",
        choices=["template", "derived", "soft-fork", "hard-fork"],
        help="Instance type",
    )
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="Project root directory")
    args = parser.parse_args()

    try:
        lineage_init(
            project_root=Path(args.project_root),
            template_version=args.template_version,
            project_name=args.project_name,
            project_type=args.project_type,
        )
    except FileExistsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
