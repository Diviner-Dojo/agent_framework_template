"""Tests for scripts/bump_version.py.

Covers all 4 CLI modes (--read, --patch, --minor, --major),
missing version line, missing file, TOML formatting preservation,
and [project] section scoping.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))

from scripts.bump_version import (  # noqa: E402
    VersionNotFoundError,
    bump_version,
    read_version,
)


@pytest.fixture()
def pyproject_file(tmp_path: Path) -> Path:
    """Create a minimal pyproject.toml with a known version."""
    content = (
        '[project]\nname = "test-project"\nversion = "1.2.3"\n'
        'requires-python = ">=3.11"\n\n'
        "[tool.ruff]\n"
        'target-version = "py311"\n'
    )
    path = tmp_path / "pyproject.toml"
    path.write_text(content, encoding="utf-8")
    return path


class TestReadVersion:
    """Tests for reading the current version."""

    def test_read_existing_version(self, pyproject_file: Path) -> None:
        assert read_version(pyproject_file) == "1.2.3"

    def test_read_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_version(tmp_path / "nonexistent.toml")

    def test_read_no_version_under_project(self, tmp_path: Path) -> None:
        path = tmp_path / "pyproject.toml"
        path.write_text('[project]\nname = "test"\n', encoding="utf-8")
        with pytest.raises(VersionNotFoundError):
            read_version(path)


class TestBumpVersion:
    """Tests for version bumping."""

    def test_bump_patch(self, pyproject_file: Path) -> None:
        old, new = bump_version("patch", pyproject_file)
        assert old == "1.2.3"
        assert new == "1.2.4"
        assert read_version(pyproject_file) == "1.2.4"

    def test_bump_minor(self, pyproject_file: Path) -> None:
        old, new = bump_version("minor", pyproject_file)
        assert old == "1.2.3"
        assert new == "1.3.0"
        assert read_version(pyproject_file) == "1.3.0"

    def test_bump_major(self, pyproject_file: Path) -> None:
        old, new = bump_version("major", pyproject_file)
        assert old == "1.2.3"
        assert new == "2.0.0"
        assert read_version(pyproject_file) == "2.0.0"

    def test_bump_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            bump_version("patch", tmp_path / "nonexistent.toml")

    def test_formatting_preserved(self, pyproject_file: Path) -> None:
        """Verify that bumping only changes the version line."""
        original = pyproject_file.read_text(encoding="utf-8")
        bump_version("patch", pyproject_file)
        updated = pyproject_file.read_text(encoding="utf-8")

        # All lines should be identical except the version line
        orig_lines = original.splitlines()
        upd_lines = updated.splitlines()
        assert len(orig_lines) == len(upd_lines)

        for orig, upd in zip(orig_lines, upd_lines):
            if "version" in orig and "1.2.3" in orig:
                assert "1.2.4" in upd
            else:
                assert orig == upd

    def test_bump_invalid_type_raises(self, pyproject_file: Path) -> None:
        with pytest.raises(ValueError, match="Invalid bump_type"):
            bump_version("invalid", pyproject_file)


class TestProjectSectionScoping:
    """Tests that only [project] version is modified."""

    def test_ignores_version_in_other_sections(self, tmp_path: Path) -> None:
        """Version keys in non-[project] sections must not be modified."""
        content = (
            '[project]\nname = "test"\nversion = "1.0.0"\n\n[tool.some-tool]\nversion = "9.9.9"\n'
        )
        path = tmp_path / "pyproject.toml"
        path.write_text(content, encoding="utf-8")

        bump_version("patch", path)
        text = path.read_text(encoding="utf-8")

        # [project] version should be bumped
        assert 'version = "1.0.1"' in text
        # [tool.some-tool] version should be unchanged
        assert 'version = "9.9.9"' in text

    def test_no_version_under_project_raises(self, tmp_path: Path) -> None:
        """If [project] has no version but another section does, raise error."""
        content = '[project]\nname = "test"\n\n[tool.other]\nversion = "2.0.0"\n'
        path = tmp_path / "pyproject.toml"
        path.write_text(content, encoding="utf-8")

        with pytest.raises(VersionNotFoundError):
            read_version(path)
