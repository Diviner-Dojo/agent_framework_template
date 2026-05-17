"""Tests for assertion_store.substrate — the per-project memory substrate.

Covers the resolve_project_id error paths flagged in REV-20260512-132622
(qa-specialist Finding 2). The schema-init path (substrate.init) is exercised
transitively by the end-to-end roundtrip test in test_mcp_server.py.
"""

from __future__ import annotations

import pytest

from assertion_store.substrate import resolve_project_id


class TestResolveProjectId:
    """resolve_project_id reads [project].name from pyproject.toml at a given root."""

    def test_returns_name_from_valid_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-cool-project"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        assert resolve_project_id(tmp_path) == "my-cool-project"

    def test_missing_pyproject_raises_file_not_found(self, tmp_path):
        # tmp_path is fresh — no pyproject.toml exists
        with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
            resolve_project_id(tmp_path)

    def test_pyproject_without_project_name_raises_key_error(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 99\n",
            encoding="utf-8",
        )
        with pytest.raises(KeyError, match=r"no \[project\].name"):
            resolve_project_id(tmp_path)

    def test_pyproject_with_project_section_no_name_raises_key_error(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        with pytest.raises(KeyError):
            resolve_project_id(tmp_path)
