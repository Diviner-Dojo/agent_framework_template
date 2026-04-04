"""Tests for scripts/spawn_project.py."""

import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.spawn_project import (  # noqa: E402
    BASE_ADRS,
    EMPTY_DIRS,
    FRAMEWORK_DIRS,
    FRAMEWORK_FILES,
    spawn_project,
)


@pytest.fixture()
def target_dir(tmp_path: Path) -> Path:
    """Return a non-existent target directory inside tmp_path."""
    return tmp_path / "new-project"


def test_spawn_creates_target_directory(target_dir: Path) -> None:
    """Target directory is created by spawn_project."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    assert target_dir.is_dir()


def test_spawn_copies_framework_dirs(target_dir: Path) -> None:
    """All framework directories are copied."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    for dir_name in FRAMEWORK_DIRS:
        assert (target_dir / dir_name).is_dir(), f"Missing directory: {dir_name}"


def test_spawn_copies_framework_files(target_dir: Path) -> None:
    """All individual framework files are copied."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    for file_name in FRAMEWORK_FILES:
        src = PROJECT_ROOT / file_name
        if src.exists():
            assert (target_dir / file_name).is_file(), f"Missing file: {file_name}"


def test_spawn_copies_base_adrs_only(target_dir: Path) -> None:
    """Only foundational ADRs are copied, not project-specific ones."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)

    adr_dir = target_dir / "docs" / "adr"
    for adr_path in BASE_ADRS:
        src = PROJECT_ROOT / adr_path
        if src.exists():
            assert (target_dir / adr_path).is_file(), f"Missing base ADR: {adr_path}"

    # Project-specific ADRs should NOT be present
    if (PROJECT_ROOT / "docs" / "adr" / "ADR-0003-private-fork-branching-strategy.md").exists():
        assert not (adr_dir / "ADR-0003-private-fork-branching-strategy.md").exists()


def test_spawn_creates_empty_dirs(target_dir: Path) -> None:
    """All required empty directories are created."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    for dir_name in EMPTY_DIRS:
        dir_path = target_dir / dir_name
        assert dir_path.is_dir(), f"Missing empty directory: {dir_name}"


def test_spawn_creates_gitkeep_files(target_dir: Path) -> None:
    """Empty directories contain .gitkeep files."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    # Check a few representative dirs that should be empty
    assert (target_dir / "discussions" / ".gitkeep").is_file()
    assert (target_dir / "memory" / "bugs" / ".gitkeep").is_file()


def test_spawn_creates_starter_files(target_dir: Path) -> None:
    """Starter files are created in src/ and tests/."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    assert (target_dir / "src" / "__init__.py").is_file()
    assert (target_dir / "tests" / "__init__.py").is_file()
    assert (target_dir / "tests" / "conftest.py").is_file()


def test_spawn_initializes_db(target_dir: Path) -> None:
    """Metrics database is created with expected tables."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    db_path = target_dir / "metrics" / "evaluation.db"
    assert db_path.is_file()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "discussions" in tables
    assert "turns" in tables
    assert "lineage_nodes" in tables


def test_spawn_initializes_lineage(target_dir: Path) -> None:
    """Lineage manifest is created with correct project name and type."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    manifest_path = target_dir / "framework-lineage.yaml"
    assert manifest_path.is_file()

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    assert manifest["instance"]["name"] == "Test Project"
    assert manifest["instance"]["type"] == "derived"
    assert manifest["lineage_id"]


def test_spawn_customizes_pyproject(target_dir: Path) -> None:
    """pyproject.toml is customized with the new project name."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    pyproject_path = target_dir / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")

    assert "test-project" in text
    assert "agentic-framework-template" not in text
    assert 'version = "0.1.0"' in text


def test_spawn_refuses_existing_target(target_dir: Path) -> None:
    """Error when target directory already exists."""
    target_dir.mkdir(parents=True)
    with pytest.raises(FileExistsError, match="already exists"):
        spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)


def test_spawn_refuses_empty_name(target_dir: Path) -> None:
    """Error when project name is empty."""
    with pytest.raises(ValueError, match="must not be empty"):
        spawn_project(target_dir, "", template_root=PROJECT_ROOT, init_git=False)

    with pytest.raises(ValueError, match="must not be empty"):
        spawn_project(target_dir, "   ", template_root=PROJECT_ROOT, init_git=False)


def test_spawn_excludes_pycache(target_dir: Path) -> None:
    """__pycache__ directories are not copied."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    pycache_dirs = list(target_dir.rglob("__pycache__"))
    assert len(pycache_dirs) == 0, f"Found __pycache__ dirs: {pycache_dirs}"


def test_spawn_no_instance_specific_files(target_dir: Path) -> None:
    """Instance-specific files from the template are not present."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)

    # discussions/ should be empty (only .gitkeep)
    discussions = target_dir / "discussions"
    contents = [f for f in discussions.iterdir() if f.name != ".gitkeep"]
    assert len(contents) == 0

    # No BUILD_STATUS.md
    assert not (target_dir / "BUILD_STATUS.md").exists()


def test_spawn_returns_result_dict(target_dir: Path) -> None:
    """spawn_project returns a dict with expected keys."""
    result = spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    assert result["project_name"] == "Test Project"
    assert result["template_version"]
    assert result["lineage_id"]
    assert result["files_copied"] > 0
    assert result["git_initialized"] is False


def test_spawn_no_git_flag(target_dir: Path) -> None:
    """No .git/ directory when init_git=False."""
    spawn_project(target_dir, "Test Project", template_root=PROJECT_ROOT, init_git=False)
    assert not (target_dir / ".git").exists()
