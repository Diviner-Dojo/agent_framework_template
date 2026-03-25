"""Tests for the BUILD_STATUS.md freshness check in quality_gate.py."""

# We need to import after setting up sys.path
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from quality_gate import check_build_status_freshness


class TestBuildStatusFreshness:
    """Tests for the check_build_status_freshness function."""

    def test_missing_file_warns_but_passes(self, tmp_path, capsys):
        """Missing BUILD_STATUS.md warns but returns True."""
        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            result = check_build_status_freshness()
        assert result is True
        output = capsys.readouterr().out
        assert "WARN" in output

    def test_fresh_file_passes(self, tmp_path, capsys):
        """BUILD_STATUS.md modified recently passes."""
        bs = tmp_path / "BUILD_STATUS.md"
        bs.write_text("# Build Status\nLast updated: now\n")
        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            result = check_build_status_freshness()
        assert result is True
        output = capsys.readouterr().out
        assert "PASS" in output

    def test_stale_file_warns_but_passes(self, tmp_path, capsys):
        """BUILD_STATUS.md older than 60 minutes warns but returns True."""
        bs = tmp_path / "BUILD_STATUS.md"
        bs.write_text("# Build Status\nStale\n")
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        import os

        os.utime(bs, (old_time, old_time))
        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            result = check_build_status_freshness()
        assert result is True  # Advisory only
        output = capsys.readouterr().out
        assert "WARN" in output
