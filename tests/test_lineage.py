"""Unit tests for lineage tracking (Steward Phase 1).

Tests manifest CRUD, drift detection, lineage initialization,
and SQLite lineage table operations.
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# Add project root to path for imports
TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))

from scripts.init_db import init_db  # noqa: E402
from scripts.lineage._utils import (  # noqa: E402
    collect_framework_files,
    hash_file,
    list_untracked_framework_files,
)
from scripts.lineage.drift import (  # noqa: E402
    FileDrift,
    compute_divergence_distance,
    drift_report,
    drift_scan,
)
from scripts.lineage.init_lineage import _write_lineage_event, lineage_init  # noqa: E402
from scripts.lineage.manifest import (  # noqa: E402
    VALID_DRIFT_STATUSES,
    VALID_INSTANCE_TYPES,
    manifest_read,
    manifest_update_drift,
    manifest_validate,
)


@pytest.fixture
def lineage_env(tmp_path):
    """Set up an isolated environment for lineage tests."""
    # Create project structure
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create framework files
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()
    agents_dir = claude_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "test-agent.md").write_text("# Test Agent\nSome content.")
    (claude_dir / "rules").mkdir()
    (claude_dir / "rules" / "test-rule.md").write_text("# Test Rule")

    scripts_dir = project_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "test_script.py").write_text("print('hello')")

    (project_root / "CLAUDE.md").write_text("# Project Constitution\nTest project.")

    docs_dir = project_root / "docs"
    docs_dir.mkdir()
    (docs_dir / "adr").mkdir()
    (docs_dir / "templates").mkdir()

    # Initialize SQLite
    metrics_dir = project_root / "metrics"
    metrics_dir.mkdir()
    db_path = metrics_dir / "evaluation.db"
    init_db(db_path)

    return {
        "project_root": project_root,
        "db_path": db_path,
        "claude_dir": claude_dir,
        "scripts_dir": scripts_dir,
    }


# ── Manifest CRUD Tests ─────────────────────────────────────────────


class TestManifestRead:
    """Tests for manifest_read()."""

    def test_read_valid_manifest(self, tmp_path):
        """manifest_read returns parsed YAML with all sections."""
        manifest = {
            "schema_version": "1.0",
            "lineage_id": "test-uuid",
            "serial": 0,
            "instance": {
                "name": "test-project",
                "version": "1.0.0+upstream.2.1.0",
                "type": "derived",
                "created_at": "2026-03-07T00:00:00",
            },
            "drift": {"status": "current", "divergence_distance": 0},
            "pinned_traits": [],
        }
        path = tmp_path / "framework-lineage.yaml"
        with open(path, "w") as f:
            yaml.dump(manifest, f)

        result = manifest_read(path)
        assert result["schema_version"] == "1.0"
        assert result["lineage_id"] == "test-uuid"
        assert result["instance"]["name"] == "test-project"
        assert result["drift"]["status"] == "current"

    def test_read_missing_manifest_raises(self, tmp_path):
        """manifest_read raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            manifest_read(tmp_path / "nonexistent.yaml")

    def test_read_empty_manifest_raises(self, tmp_path):
        """manifest_read raises ValueError for empty file."""
        path = tmp_path / "framework-lineage.yaml"
        path.write_text("")
        with pytest.raises(ValueError, match="Empty manifest"):
            manifest_read(path)


class TestManifestValidate:
    """Tests for manifest_validate()."""

    def test_validate_complete_manifest(self):
        """Valid manifest returns no errors."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test-uuid",
            "serial": 0,
            "instance": {
                "name": "test",
                "version": "1.0.0",
                "type": "template",
                "created_at": "2026-03-07",
            },
            "drift": {"status": "current"},
            "pinned_traits": [],
        }
        errors = manifest_validate(data)
        assert errors == []

    def test_validate_missing_required_fields(self):
        """Missing required fields are reported."""
        errors = manifest_validate({})
        assert any("schema_version" in e for e in errors)
        assert any("lineage_id" in e for e in errors)
        assert any("serial" in e for e in errors)
        assert any("instance" in e for e in errors)
        assert any("drift" in e for e in errors)

    def test_validate_invalid_instance_type(self):
        """Invalid instance type is reported."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "instance": {
                "name": "test",
                "version": "1.0.0",
                "type": "invalid-type",
                "created_at": "2026-03-07",
            },
            "drift": {"status": "current"},
        }
        errors = manifest_validate(data)
        assert any("Invalid instance type" in e for e in errors)

    def test_validate_invalid_drift_status(self):
        """Invalid drift status is reported."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "instance": {
                "name": "test",
                "version": "1.0.0",
                "type": "template",
                "created_at": "2026-03-07",
            },
            "drift": {"status": "unknown"},
        }
        errors = manifest_validate(data)
        assert any("Invalid drift status" in e for e in errors)

    def test_validate_negative_serial(self):
        """Negative serial is reported."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": -1,
            "instance": {
                "name": "test",
                "version": "1.0.0",
                "type": "template",
                "created_at": "2026-03-07",
            },
            "drift": {"status": "current"},
        }
        errors = manifest_validate(data)
        assert any("serial" in e for e in errors)

    def test_validate_pinned_traits_not_list(self):
        """Non-list pinned_traits is reported."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "instance": {
                "name": "test",
                "version": "1.0.0",
                "type": "template",
                "created_at": "2026-03-07",
            },
            "drift": {"status": "current"},
            "pinned_traits": "not-a-list",
        }
        errors = manifest_validate(data)
        assert any("pinned_traits" in e for e in errors)

    def test_validate_all_instance_types_accepted(self):
        """All valid instance types pass validation."""
        for inst_type in VALID_INSTANCE_TYPES:
            data = {
                "schema_version": "1.0",
                "lineage_id": "test",
                "serial": 0,
                "instance": {
                    "name": "test",
                    "version": "1.0.0",
                    "type": inst_type,
                    "created_at": "2026-03-07",
                },
                "drift": {"status": "current"},
            }
            errors = manifest_validate(data)
            assert not any("instance type" in e.lower() for e in errors)

    def test_validate_all_drift_statuses_accepted(self):
        """All valid drift statuses pass validation."""
        for status in VALID_DRIFT_STATUSES:
            data = {
                "schema_version": "1.0",
                "lineage_id": "test",
                "serial": 0,
                "instance": {
                    "name": "test",
                    "version": "1.0.0",
                    "type": "template",
                    "created_at": "2026-03-07",
                },
                "drift": {"status": status},
            }
            errors = manifest_validate(data)
            assert not any("drift status" in e.lower() for e in errors)

    def test_validate_instance_not_dict(self):
        """Non-dict instance field is reported."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "instance": "not-a-dict",
            "drift": {"status": "current"},
        }
        errors = manifest_validate(data)
        assert any("instance" in e and "mapping" in e for e in errors)

    def test_validate_drift_not_dict(self):
        """Non-dict drift field is reported."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "instance": {
                "name": "test",
                "version": "1.0.0",
                "type": "template",
                "created_at": "2026-03-07",
            },
            "drift": "not-a-dict",
        }
        errors = manifest_validate(data)
        assert any("drift" in e and "mapping" in e for e in errors)

    def test_validate_missing_instance_fields(self):
        """Missing instance sub-fields are reported."""
        data = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "instance": {"name": "test"},
            "drift": {"status": "current"},
        }
        errors = manifest_validate(data)
        assert any("version" in e for e in errors)
        assert any("type" in e for e in errors)
        assert any("created_at" in e for e in errors)


class TestManifestUpdateDrift:
    """Tests for manifest_update_drift()."""

    def test_update_drift_bumps_serial(self, tmp_path):
        """Updating drift increments the serial counter."""
        manifest = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 5,
            "instance": {
                "name": "test",
                "version": "1.0.0",
                "type": "template",
                "created_at": "2026-03-07",
            },
            "drift": {"status": "current", "divergence_distance": 0},
        }
        path = tmp_path / "framework-lineage.yaml"
        with open(path, "w") as f:
            yaml.dump(manifest, f)

        result = manifest_update_drift(path, status="diverged", divergence_distance=5)
        assert result["serial"] == 6
        assert result["drift"]["status"] == "diverged"
        assert result["drift"]["divergence_distance"] == 5

        # Verify persistence
        reloaded = manifest_read(path)
        assert reloaded["serial"] == 6

    def test_update_drift_invalid_status_raises(self, tmp_path):
        """Invalid drift status raises ValueError."""
        manifest = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "drift": {"status": "current"},
        }
        path = tmp_path / "framework-lineage.yaml"
        with open(path, "w") as f:
            yaml.dump(manifest, f)

        with pytest.raises(ValueError, match="Invalid drift status"):
            manifest_update_drift(path, status="bad-status")

    def test_update_drift_partial_update(self, tmp_path):
        """Can update just status without divergence_distance."""
        manifest = {
            "schema_version": "1.0",
            "lineage_id": "test",
            "serial": 0,
            "drift": {"status": "current", "divergence_distance": 0},
        }
        path = tmp_path / "framework-lineage.yaml"
        with open(path, "w") as f:
            yaml.dump(manifest, f)

        result = manifest_update_drift(path, status="behind")
        assert result["drift"]["status"] == "behind"
        assert result["drift"]["divergence_distance"] == 0


# ── Drift Detection Tests ───────────────────────────────────────────


class TestDriftDetection:
    """Tests for drift scanning and reporting."""

    def test_hash_file_deterministic(self, tmp_path):
        """Hashing the same file twice gives identical results."""
        path = tmp_path / "test.txt"
        path.write_text("hello world")
        assert hash_file(path) == hash_file(path)

    def test_hash_file_different_content(self, tmp_path):
        """Different content produces different hashes."""
        path1 = tmp_path / "a.txt"
        path2 = tmp_path / "b.txt"
        path1.write_text("hello")
        path2.write_text("world")
        assert hash_file(path1) != hash_file(path2)

    def test_collect_framework_files(self, lineage_env):
        """Collects files from configured framework paths."""
        root = lineage_env["project_root"]
        files = collect_framework_files(root, [".claude/", "CLAUDE.md"])
        assert "CLAUDE.md" in files
        assert any(f.startswith(".claude/") for f in files)
        assert all(isinstance(h, str) and len(h) == 64 for h in files.values())

    def test_drift_scan_detects_modified_file(self, lineage_env):
        """Modified file is detected as 'modified'."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        # Initialize lineage
        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        # Modify a framework file
        (root / "CLAUDE.md").write_text("Modified content!")

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )

        modified = [f for f in results if f.file_path == "CLAUDE.md"]
        assert len(modified) == 1
        assert modified[0].drift_status == "modified"

    def test_drift_scan_detects_added_file(self, lineage_env):
        """New framework file is detected as 'added'."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        # Add a new framework file
        (root / ".claude" / "agents" / "new-agent.md").write_text("# New Agent")

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )

        added = [f for f in results if f.drift_status == "added"]
        assert any(f.file_path == ".claude/agents/new-agent.md" for f in added)

    def test_drift_scan_detects_deleted_file(self, lineage_env):
        """Deleted framework file is detected as 'deleted'."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        # Delete a framework file
        (root / ".claude" / "agents" / "test-agent.md").unlink()

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )

        deleted = [f for f in results if f.drift_status == "deleted"]
        assert any(f.file_path == ".claude/agents/test-agent.md" for f in deleted)

    def test_drift_scan_current_when_unchanged(self, lineage_env):
        """Unchanged files show as 'current'."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )

        # All files that existed at init should be current
        # (excluding custodian files which were created during init)
        original_files = [
            f
            for f in results
            if not f.file_path.startswith(".claude/custodian/")
            and not f.file_path.startswith("scripts/lineage/")
            and f.file_path != "framework-lineage.yaml"
        ]
        for f in original_files:
            assert f.drift_status == "current", (
                f"Expected {f.file_path} to be current, got {f.drift_status}"
            )

    def test_drift_scan_respects_pinned_traits(self, lineage_env):
        """Pinned files show as 'pinned' not 'modified'."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        # Modify a file and pin it
        (root / "CLAUDE.md").write_text("Intentionally modified!")
        manifest_data = manifest_read(root / "framework-lineage.yaml")
        manifest_data["pinned_traits"] = [
            {
                "path": "CLAUDE.md",
                "reason": "Project-specific constitution",
                "adr_reference": "ADR-0001",
            }
        ]
        manifest_data["serial"] += 1
        with open(root / "framework-lineage.yaml", "w") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )

        claude_md = [f for f in results if f.file_path == "CLAUDE.md"]
        assert len(claude_md) == 1
        assert claude_md[0].drift_status == "pinned"
        assert claude_md[0].is_intentional is True
        assert claude_md[0].pin_reason == "Project-specific constitution"

    @pytest.mark.regression
    def test_drift_scan_excludes_gitignored_worktrees(self, tmp_path):
        # T5: caller-level coverage (ADR-0025). Gitignored clutter must not reach the drift
        # scan's stored hashes via lineage_init -> collect_framework_files. Makes the
        # exclusion deliberate at the caller, not just incidental in the enumerator. Would
        # fail under the old unfiltered rglob, which swept .claude/worktrees/* into drift.
        root = tmp_path / "hub"
        _cg_init_repo(root)
        _cg_write(root, ".gitignore", ".claude/worktrees/\n")
        _cg_write(root, ".claude/agents/a.md", "# agent")
        _cg_write(root, "CLAUDE.md", "# constitution")
        _cg_commit(root, "init")
        _cg_write(root, ".claude/worktrees/ext/clone.py", "junk")  # gitignored, untracked

        db_path = root / "metrics" / "evaluation.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(db_path)
        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )
        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )
        assert not any(f.file_path.startswith(".claude/worktrees/") for f in results)

    def test_compute_divergence_distance(self):
        """Divergence distance counts modified, added, and deleted files."""
        results = [
            FileDrift("a.md", "current", False, "h1", "h1"),
            FileDrift("b.md", "modified", False, "h2", "h3"),
            FileDrift("c.md", "added", False, None, "h4"),
            FileDrift("d.md", "deleted", False, "h5", None),
            FileDrift("e.md", "pinned", True, "h6", "h7"),
        ]
        assert compute_divergence_distance(results) == 3

    def test_drift_report_format(self):
        """Drift report contains expected sections."""
        results = [
            FileDrift("a.md", "current", False, "h1", "h1"),
            FileDrift("b.md", "modified", False, "h2", "h3"),
            FileDrift("c.md", "pinned", True, "h4", "h5", "Intentional", "ADR-0001"),
        ]
        report = drift_report(results)
        assert "Drift Report" in report
        assert "Divergence distance" in report
        assert "Modified Files" in report
        assert "`b.md`" in report
        assert "Pinned Files" in report
        assert "Intentional" in report
        assert "ADR-0001" in report


# ── Lineage Initialization Tests ────────────────────────────────────


class TestLineageInit:
    """Tests for lineage_init()."""

    def test_init_creates_valid_manifest(self, lineage_env):
        """lineage_init creates a parseable manifest with required fields."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]
        manifest_path = root / "framework-lineage.yaml"

        manifest = lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test-project",
            db_path=db_path,
            manifest_path=manifest_path,
            custodian_dir=root / ".claude" / "custodian",
        )

        assert manifest["schema_version"] == "1.0"
        assert manifest["serial"] == 0
        assert manifest["instance"]["name"] == "test-project"
        assert manifest["instance"]["version"] == "1.0.0+upstream.2.1.0"
        assert manifest["instance"]["type"] == "template"
        assert manifest["drift"]["status"] == "current"
        assert manifest["drift"]["divergence_distance"] == 0
        assert manifest["pinned_traits"] == []

        # Validate it passes validation
        errors = manifest_validate(manifest)
        assert errors == []

    def test_init_creates_custodian_dir(self, lineage_env):
        """lineage_init creates the .claude/custodian/ directory."""
        root = lineage_env["project_root"]
        custodian_dir = root / ".claude" / "custodian"

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=lineage_env["db_path"],
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=custodian_dir,
        )

        assert custodian_dir.is_dir()
        assert (custodian_dir / "lineage-events.jsonl").exists()

    def test_init_writes_fork_event(self, lineage_env):
        """lineage_init writes a FORK event to lineage-events.jsonl."""
        root = lineage_env["project_root"]
        custodian_dir = root / ".claude" / "custodian"
        events_path = custodian_dir / "lineage-events.jsonl"

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test-project",
            db_path=lineage_env["db_path"],
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=custodian_dir,
        )

        with open(events_path) as f:
            events = [json.loads(line) for line in f if line.strip()]

        assert len(events) == 1
        event = events[0]
        assert event["index"] == 0
        assert event["event_type"] == "FORK"
        assert event["data"]["project_name"] == "test-project"
        assert event["data"]["template_version"] == "2.1.0"
        assert "content_hash" in event
        assert "timestamp" in event

    def test_init_inserts_lineage_node(self, lineage_env):
        """lineage_init creates a lineage_nodes row in SQLite."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        manifest = lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test-project",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT name, type, current_version, upstream_version FROM lineage_nodes WHERE id = ?",
            (manifest["lineage_id"],),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "test-project"
        assert row[1] == "template"
        assert row[2] == "1.0.0+upstream.2.1.0"
        assert row[3] == "2.1.0"

    def test_init_stores_file_baselines(self, lineage_env):
        """lineage_init stores template file hashes in lineage_file_drift."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        manifest = lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT file_path, drift_status, template_hash "
            "FROM lineage_file_drift WHERE lineage_id = ?",
            (manifest["lineage_id"],),
        ).fetchall()
        conn.close()

        assert len(rows) > 0
        file_paths = [r[0] for r in rows]
        assert "CLAUDE.md" in file_paths
        assert all(r[1] == "current" for r in rows)
        assert all(r[2] is not None and len(r[2]) == 64 for r in rows)

    def test_init_raises_if_manifest_exists(self, lineage_env):
        """lineage_init raises FileExistsError if manifest already exists."""
        root = lineage_env["project_root"]
        manifest_path = root / "framework-lineage.yaml"
        manifest_path.write_text("existing content")

        with pytest.raises(FileExistsError):
            lineage_init(
                project_root=root,
                template_version="2.1.0",
                project_name="test",
                db_path=lineage_env["db_path"],
                manifest_path=manifest_path,
                custodian_dir=root / ".claude" / "custodian",
            )


# ── Lineage Event Log Tests ─────────────────────────────────────────


class TestLineageEvents:
    """Tests for lineage event logging."""

    def test_event_append_creates_file(self, tmp_path):
        """Writing an event creates the JSONL file if missing."""
        events_path = tmp_path / "events.jsonl"
        index = _write_lineage_event(events_path, "TEST", {"key": "value"})
        assert events_path.exists()
        assert index == 0

    def test_event_monotonic_indices(self, tmp_path):
        """Events have sequential indices."""
        events_path = tmp_path / "events.jsonl"
        idx0 = _write_lineage_event(events_path, "A", {"n": 1})
        idx1 = _write_lineage_event(events_path, "B", {"n": 2})
        idx2 = _write_lineage_event(events_path, "C", {"n": 3})

        assert idx0 == 0
        assert idx1 == 1
        assert idx2 == 2

    def test_event_structure(self, tmp_path):
        """Events have required fields."""
        events_path = tmp_path / "events.jsonl"
        _write_lineage_event(events_path, "FORK", {"project": "test"})

        with open(events_path) as f:
            event = json.loads(f.readline())

        assert event["index"] == 0
        assert event["event_type"] == "FORK"
        assert event["data"]["project"] == "test"
        assert "timestamp" in event
        assert "content_hash" in event
        assert len(event["content_hash"]) == 64

    def test_event_append_only(self, tmp_path):
        """Multiple events are appended, not overwritten."""
        events_path = tmp_path / "events.jsonl"
        _write_lineage_event(events_path, "A", {})
        _write_lineage_event(events_path, "B", {})

        with open(events_path) as f:
            lines = [line for line in f if line.strip()]

        assert len(lines) == 2
        assert json.loads(lines[0])["event_type"] == "A"
        assert json.loads(lines[1])["event_type"] == "B"


# ── SQLite Integration Tests ────────────────────────────────────────


class TestSQLiteLineage:
    """Tests for lineage SQLite tables."""

    def test_init_db_creates_lineage_tables(self, tmp_path):
        """init_db creates lineage_nodes and lineage_file_drift tables."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'lineage%'"
        ).fetchall()
        conn.close()

        table_names = [t[0] for t in tables]
        assert "lineage_nodes" in table_names
        assert "lineage_file_drift" in table_names

    def test_init_db_idempotent(self, tmp_path):
        """Running init_db twice does not error."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        init_db(db_path)  # Should not raise

    def test_lineage_node_crud(self, tmp_path):
        """Can insert and query lineage_nodes."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "INSERT INTO lineage_nodes (id, name, type, created_at, current_version) "
            "VALUES (?, ?, ?, ?, ?)",
            ("uuid-1", "test-project", "derived", "2026-03-07", "1.0.0"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT name, type FROM lineage_nodes WHERE id = ?", ("uuid-1",)
        ).fetchone()
        conn.close()

        assert row == ("test-project", "derived")

    def test_lineage_node_type_constraint(self, tmp_path):
        """Invalid node type is rejected by CHECK constraint."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lineage_nodes (id, name, type, created_at, current_version) "
                "VALUES (?, ?, ?, ?, ?)",
                ("uuid-1", "test", "invalid-type", "2026-03-07", "1.0.0"),
            )
        conn.close()

    def test_file_drift_crud(self, tmp_path):
        """Can insert and query lineage_file_drift."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=OFF")  # Skip FK for isolated test
        conn.execute(
            "INSERT INTO lineage_file_drift "
            "(lineage_id, file_path, drift_status, template_hash, local_hash, last_checked) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("uuid-1", "CLAUDE.md", "modified", "hash1", "hash2", "2026-03-07"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT drift_status, template_hash, local_hash FROM lineage_file_drift "
            "WHERE lineage_id = ? AND file_path = ?",
            ("uuid-1", "CLAUDE.md"),
        ).fetchone()
        conn.close()

        assert row == ("modified", "hash1", "hash2")

    def test_file_drift_status_constraint(self, tmp_path):
        """Invalid drift status is rejected by CHECK constraint."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=OFF")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lineage_file_drift "
                "(lineage_id, file_path, drift_status, last_checked) "
                "VALUES (?, ?, ?, ?)",
                ("uuid-1", "test.md", "invalid-status", "2026-03-07"),
            )
        conn.close()


# ── Additional Review-Required Tests ───────────────────────────────


class TestDriftEdgeCases:
    """Tests for drift edge cases identified in review."""

    def test_db_persisted_pinned_files(self, lineage_env):
        """Files with is_intentional=TRUE in DB are classified as 'pinned'."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        # Modify a file
        (root / "CLAUDE.md").write_text("DB-pinned modification")

        # Set is_intentional=TRUE in DB (simulating a PIN event)
        manifest_data = manifest_read(root / "framework-lineage.yaml")
        lineage_id = manifest_data["lineage_id"]
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE lineage_file_drift SET is_intentional = 1, "
            "pin_reason = 'DB pin test', adr_reference = 'ADR-0099' "
            "WHERE lineage_id = ? AND file_path = 'CLAUDE.md'",
            (lineage_id,),
        )
        conn.commit()
        conn.close()

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )

        claude_md = [f for f in results if f.file_path == "CLAUDE.md"]
        assert len(claude_md) == 1
        assert claude_md[0].drift_status == "pinned"
        assert claude_md[0].is_intentional is True

    def test_prefix_match_pinning(self, lineage_env):
        """Pinning a directory prefix pins all files under it."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        # Modify a file under .claude/
        (root / ".claude" / "agents" / "test-agent.md").write_text("Modified agent")

        # Pin the entire .claude/ directory
        manifest_data = manifest_read(root / "framework-lineage.yaml")
        manifest_data["pinned_traits"] = [
            {"path": ".claude/", "reason": "Project agents", "adr_reference": "ADR-0001"}
        ]
        manifest_data["serial"] += 1
        with open(root / "framework-lineage.yaml", "w") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=db_path,
        )

        agent_file = [f for f in results if f.file_path == ".claude/agents/test-agent.md"]
        assert len(agent_file) == 1
        assert agent_file[0].drift_status == "pinned"
        assert agent_file[0].is_intentional is True

    def test_drift_report_added_and_deleted_sections(self):
        """Drift report includes Added Files and Deleted Files sections."""
        results = [
            FileDrift("a.md", "current", False, "h1", "h1"),
            FileDrift("b.md", "added", False, None, "h2"),
            FileDrift("c.md", "deleted", False, "h3", None),
        ]
        report = drift_report(results)
        assert "## Added Files" in report
        assert "`b.md`" in report
        assert "## Deleted Files" in report
        assert "`c.md`" in report
        assert "Divergence distance**: 2" in report

    def test_drift_scan_without_db(self, lineage_env):
        """drift_scan works when DB does not exist (no template baselines)."""
        root = lineage_env["project_root"]
        db_path = lineage_env["db_path"]

        lineage_init(
            project_root=root,
            template_version="2.1.0",
            project_name="test",
            db_path=db_path,
            manifest_path=root / "framework-lineage.yaml",
            custodian_dir=root / ".claude" / "custodian",
        )

        # Point to a non-existent DB
        missing_db = root / "nonexistent" / "evaluation.db"

        results = drift_scan(
            manifest_path=root / "framework-lineage.yaml",
            project_root=root,
            db_path=missing_db,
        )

        # Without DB baselines, all files should be "added"
        assert len(results) > 0
        assert all(f.drift_status == "added" for f in results)


# ── Corpus respects .gitignore (ADR-0025, SPEC-20260613-191445) ──────


def _cg_git(repo: Path, *args: str) -> None:
    """Run a git command against a test repo."""
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _cg_init_repo(repo: Path) -> None:
    """Initialise a deterministic git repo on branch main."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    _cg_git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _cg_git(repo, "config", "user.email", "test@example.com")
    _cg_git(repo, "config", "user.name", "Test User")
    _cg_git(repo, "config", "commit.gpgsign", "false")


def _cg_write(root: Path, rel: str, content: str) -> None:
    """Write a file under root, creating parent directories."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _cg_commit(repo: Path, message: str) -> None:
    """Stage and commit everything, no hooks."""
    _cg_git(repo, "add", "-A")
    _cg_git(repo, "commit", "--no-verify", "-m", message)


class TestCorpusRespectsGitignore:
    """The framework corpus enumerator respects git's exclusions (ADR-0025).

    Root cause it guards: ``collect_framework_files`` used an unfiltered ``rglob`` that
    swept gitignored clutter (worktree clones, ``__pycache__``, local state) into the
    corpus, exhausting the greenfield cap before ``scripts/``/``docs/`` were reached.
    """

    @pytest.mark.regression
    def test_gitignored_junk_excluded_from_git_path(self, tmp_path):
        # Regression: gitignored content under .claude/ must never enter the corpus.
        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, ".gitignore", ".claude/worktrees/\n")
        _cg_write(repo, "scripts/sentinel.py", "print('value')")
        _cg_write(repo, ".claude/agents/a.md", "# agent")
        _cg_commit(repo, "init")
        # gitignored clutter (untracked + ignored), as /analyze-project leaves behind
        _cg_write(repo, ".claude/worktrees/ext/clone.py", "junk")

        corpus = collect_framework_files(repo)
        assert "scripts/sentinel.py" in corpus
        assert not any(p.startswith(".claude/worktrees/") for p in corpus)

    @pytest.mark.regression
    def test_cap_not_reachable_by_gitignored_content(self, tmp_path):
        # Regression: under the old rglob, .claude/worktrees/* (sorts first) would fill
        # a small cap and bury scripts/. With the fix the offer set excludes them, so the
        # sentinel under scripts/ is reachable within the cap.
        from scripts.distribute.change_package import greenfield_offer_set

        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, ".gitignore", ".claude/worktrees/\n")
        _cg_write(repo, "scripts/sentinel.py", "print('value')")
        _cg_write(repo, ".claude/agents/a.md", "# a")
        _cg_commit(repo, "init")
        for i in range(50):  # gitignored clutter that would otherwise bury the cap
            _cg_write(repo, f".claude/worktrees/ext/junk_{i}.py", "x")

        offer = greenfield_offer_set(repo, cap=5)
        assert "scripts/sentinel.py" in offer
        assert len(offer) <= 5
        assert not any(p.startswith(".claude/worktrees/") for p in offer)

    def test_file_type_framework_path_collected(self, tmp_path):
        # A file-type framework path (CLAUDE.md) is collected exactly once on the git path.
        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, "CLAUDE.md", "# constitution")
        _cg_commit(repo, "init")
        corpus = collect_framework_files(repo, ["CLAUDE.md"])
        assert list(corpus.keys()) == ["CLAUDE.md"]

    def test_empty_repo_returns_empty(self, tmp_path):
        # A git repo with no tracked framework-path files yields an empty corpus (no crash).
        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, "README.md", "not a framework path")
        _cg_commit(repo, "init")
        assert collect_framework_files(repo, ["scripts/"]) == {}

    def test_non_git_dir_falls_back_and_excludes_junk(self, tmp_path):
        # A non-git root (no .git) uses the rglob fallback minus the junk denylist.
        root = tmp_path / "plain"
        _cg_write(root, "scripts/keep.py", "ok")
        _cg_write(root, "scripts/__pycache__/keep.cpython-311.pyc", "bytecode")
        corpus = collect_framework_files(root, ["scripts/"])
        assert "scripts/keep.py" in corpus
        assert not any("__pycache__" in p for p in corpus)

    @pytest.mark.parametrize(
        "rel",
        [
            ".claude/worktrees/ext/clone.py",
            ".claude/agents/__pycache__/x.pyc",
            "scripts/foo.pyc",
            ".claude/hooks/.state/context-guard.json",
            ".claude/settings.local.json",
            ".claude/custodian/lineage-events.jsonl",
            ".claude/hooks/.state/context-occupancy-123.json",
        ],
    )
    def test_non_git_fallback_excludes_each_junk_shape(self, tmp_path, rel):
        # Every framework-shaped junk pattern is excluded on the non-git fallback path.
        root = tmp_path / "plain"
        _cg_write(root, ".claude/agents/keep.md", "keep")
        _cg_write(root, rel, "junk")
        corpus = collect_framework_files(root, [".claude/"])
        assert ".claude/agents/keep.md" in corpus
        assert rel not in corpus

    def test_git_not_on_path_falls_back(self, tmp_path, monkeypatch):
        # If the git binary is missing (FileNotFoundError, not a non-zero exit), the
        # builder must fall back to rglob without crashing.
        import scripts.lineage._utils as utils

        def _boom(*a, **k):
            raise FileNotFoundError("git")

        monkeypatch.setattr(utils.subprocess, "run", _boom)
        root = tmp_path / "plain"
        _cg_write(root, "scripts/keep.py", "ok")
        corpus = collect_framework_files(root, ["scripts/"])
        assert "scripts/keep.py" in corpus

    def test_git_path_and_fallback_yield_same_key_set(self, tmp_path):
        # Equivalent trees (no junk) produce identical KEY SETS via git-path vs fallback.
        # SCOPE: this equivalence is asserted only for a clean tree with no gitignored or
        # denylisted files. The two paths intentionally DIVERGE on a file that git ignores
        # but the fallback denylist does not (and vice versa) — git's ignore rules are the
        # source of truth on a repo, the denylist is best-effort framework-junk only. So
        # this is not a general "git path == fallback" contract; do not extend it to junk.
        files = {"scripts/a.py": "a", ".claude/agents/b.md": "b", "CLAUDE.md": "c"}
        git_root = tmp_path / "g"
        _cg_init_repo(git_root)
        for rel, content in files.items():
            _cg_write(git_root, rel, content)
        _cg_commit(git_root, "init")
        plain_root = tmp_path / "p"
        for rel, content in files.items():
            _cg_write(plain_root, rel, content)
        git_keys = set(collect_framework_files(git_root).keys())
        plain_keys = set(collect_framework_files(plain_root).keys())
        assert git_keys == plain_keys
        assert "scripts/a.py" in git_keys

    def test_untracked_framework_files_detected(self, tmp_path):
        # R3: untracked-but-not-ignored framework files are reported (they won't propagate).
        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, ".gitignore", ".claude/worktrees/\n")
        _cg_write(repo, "scripts/tracked.py", "committed")
        _cg_commit(repo, "init")
        _cg_write(repo, "scripts/new_skill.py", "uncommitted framework work")
        _cg_write(repo, ".claude/worktrees/ext/junk.py", "ignored")  # must NOT be reported

        untracked = list_untracked_framework_files(repo)
        assert untracked == ["scripts/new_skill.py"]

    def test_untracked_empty_when_all_committed(self, tmp_path):
        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, "scripts/a.py", "x")
        _cg_commit(repo, "init")
        assert list_untracked_framework_files(repo) == []

    def test_untracked_empty_for_non_git_root(self, tmp_path):
        root = tmp_path / "plain"
        _cg_write(root, "scripts/a.py", "x")
        assert list_untracked_framework_files(root, ["scripts/"]) == []

    def test_relative_root_is_resolved(self, tmp_path, monkeypatch):
        # The root is resolved internally; a relative path must work without error.
        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, "scripts/a.py", "x")
        _cg_commit(repo, "init")
        monkeypatch.chdir(repo)
        corpus = collect_framework_files(Path("."), ["scripts/"])
        assert "scripts/a.py" in corpus

    # ── Test-hardening (qa-specialist approve-with-changes, REV-20260614-030114) ──

    def test_ls_files_oserror_in_known_repo_raises(self, tmp_path, monkeypatch):
        # T1a: after a POSITIVE git-repo probe, an OS/timeout error from ls-files is a
        # real failure in a known repo — it must fail loud (RuntimeError), never silently
        # degrade to the denylist fallback (ADR-0025, _utils.py:81-84).
        import scripts.lineage._utils as utils

        probe = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"true\n")
        calls = {"n": 0}

        def _side_effect(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:  # _is_git_repo probe succeeds
                return probe
            raise subprocess.TimeoutExpired(cmd="git", timeout=15)

        monkeypatch.setattr(utils.subprocess, "run", _side_effect)
        repo = tmp_path / "hub"
        repo.mkdir()
        with pytest.raises(RuntimeError, match="known repo"):
            collect_framework_files(repo, ["scripts/"])

    def test_ls_files_nonzero_exit_in_known_repo_raises(self, tmp_path, monkeypatch):
        # T1b: after a positive probe, a non-zero ls-files exit is a real failure in a
        # known repo and must raise RuntimeError, not fall back silently (_utils.py:85-86).
        import scripts.lineage._utils as utils

        probe = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"true\n")
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"boom")
        calls = {"n": 0}

        def _side_effect(*a, **k):
            calls["n"] += 1
            return probe if calls["n"] == 1 else failed

        monkeypatch.setattr(utils.subprocess, "run", _side_effect)
        repo = tmp_path / "hub"
        repo.mkdir()
        with pytest.raises(RuntimeError, match="known repo"):
            collect_framework_files(repo, ["scripts/"])

    def test_resolve_root_rejects_flag_like_path(self, monkeypatch):
        # T2: the flag-injection guard rejects a root that resolves to a flag-like path.
        # NOTE (security F1): the guard is platform-VACUOUS on Windows — Path.resolve()
        # prepends a drive letter so startswith("-") is never True on win32. We therefore
        # mock resolve() to return a flag-like path so the guard is exercised cross-platform.
        import scripts.lineage._utils as utils

        monkeypatch.setattr(utils.Path, "resolve", lambda self, strict=False: Path("-malicious"))
        with pytest.raises(ValueError, match="flag-like"):
            utils._resolve_root(Path("repo"))

    def test_ls_files_nul_split_preserves_newline_path(self, tmp_path, monkeypatch):
        # T3: ls-files uses -z (NUL-delimited). A path containing a literal newline must
        # stay a SINGLE entry — locks the -z contract against a future splitlines() regress
        # that would smuggle a spurious corpus entry (_utils.py:87-89).
        import scripts.lineage._utils as utils

        out = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"scripts/a\nb.py\x00scripts/c.py\x00"
        )
        monkeypatch.setattr(utils.subprocess, "run", lambda *a, **k: out)
        result = utils._git_ls_files(tmp_path, "scripts/")
        assert result == ["scripts/a\nb.py", "scripts/c.py"]

    @pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics")
    def test_symlink_to_dir_silently_dropped_on_git_path(self, tmp_path):
        # T4: git tracks a symlink-to-directory as a file entry; the is_file() follow at
        # _utils.py:166 drops it (a dir, not a file) without raising. Locks that silent,
        # exception-free drop on the git path.
        repo = tmp_path / "hub"
        _cg_init_repo(repo)
        _cg_write(repo, "scripts/real.py", "ok")
        (repo / "scripts" / "link").symlink_to(repo / "scripts", target_is_directory=True)
        _cg_commit(repo, "init")
        corpus = collect_framework_files(repo, ["scripts/"])
        assert "scripts/real.py" in corpus
        assert "scripts/link" not in corpus
