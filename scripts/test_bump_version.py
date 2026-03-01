"""Unit tests for bump_version.py."""

import tempfile
import unittest
from pathlib import Path

from bump_version import bump_version, read_version

SAMPLE_PUBSPEC = """\
name: agentic_journal
description: "AI-powered journaling app with offline-first architecture"
publish_to: 'none'
version: 0.14.0+1

environment:
  sdk: ^3.11.0

dependencies:
  flutter:
    sdk: flutter
"""

PUBSPEC_WITH_COMMENT = """\
name: agentic_journal
version: 0.14.0+1  # current release
environment:
  sdk: ^3.11.0
"""


class TestReadVersion(unittest.TestCase):
    """Tests for read_version()."""

    def test_read_returns_current_version(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_PUBSPEC)
            path = Path(f.name)
        try:
            self.assertEqual(read_version(path), "0.14.0+1")
        finally:
            path.unlink()


class TestBumpVersion(unittest.TestCase):
    """Tests for bump_version()."""

    def _write_temp(self, content: str) -> Path:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return Path(f.name)

    def test_patch_bump(self) -> None:
        path = self._write_temp(SAMPLE_PUBSPEC)
        try:
            result = bump_version("patch", path)
            self.assertEqual(result, "0.14.1+2")
            # Verify file was written
            self.assertEqual(read_version(path), "0.14.1+2")
        finally:
            path.unlink()

    def test_minor_bump(self) -> None:
        path = self._write_temp(SAMPLE_PUBSPEC)
        try:
            result = bump_version("minor", path)
            self.assertEqual(result, "0.15.0+2")
        finally:
            path.unlink()

    def test_major_bump(self) -> None:
        path = self._write_temp(SAMPLE_PUBSPEC)
        try:
            result = bump_version("major", path)
            self.assertEqual(result, "1.0.0+2")
        finally:
            path.unlink()

    def test_build_only_bump(self) -> None:
        path = self._write_temp(SAMPLE_PUBSPEC)
        try:
            result = bump_version("build", path)
            self.assertEqual(result, "0.14.0+2")
        finally:
            path.unlink()

    def test_comments_preserved(self) -> None:
        path = self._write_temp(PUBSPEC_WITH_COMMENT)
        try:
            bump_version("patch", path)
            content = path.read_text(encoding="utf-8")
            self.assertIn("# current release", content)
            self.assertIn("version: 0.14.1+2", content)
        finally:
            path.unlink()

    def test_only_version_line_changed(self) -> None:
        path = self._write_temp(SAMPLE_PUBSPEC)
        try:
            original = path.read_text(encoding="utf-8")
            bump_version("patch", path)
            updated = path.read_text(encoding="utf-8")

            # Split into lines and compare — only the version line should differ
            orig_lines = original.splitlines()
            new_lines = updated.splitlines()
            self.assertEqual(len(orig_lines), len(new_lines))

            diff_count = 0
            for orig, new in zip(orig_lines, new_lines):
                if orig != new:
                    diff_count += 1
                    self.assertTrue(orig.startswith("version:"))
                    self.assertTrue(new.startswith("version:"))
            self.assertEqual(diff_count, 1)
        finally:
            path.unlink()

    def test_sequential_bumps_increment_build(self) -> None:
        path = self._write_temp(SAMPLE_PUBSPEC)
        try:
            bump_version("patch", path)  # 0.14.1+2
            result = bump_version("patch", path)  # 0.14.2+3
            self.assertEqual(result, "0.14.2+3")
        finally:
            path.unlink()

    def test_minor_resets_patch(self) -> None:
        """Minor bump should reset patch to 0."""
        content = SAMPLE_PUBSPEC.replace("0.14.0+1", "0.14.3+5")
        path = self._write_temp(content)
        try:
            result = bump_version("minor", path)
            self.assertEqual(result, "0.15.0+6")
        finally:
            path.unlink()

    def test_major_resets_minor_and_patch(self) -> None:
        """Major bump should reset minor and patch to 0."""
        content = SAMPLE_PUBSPEC.replace("0.14.0+1", "0.14.3+5")
        path = self._write_temp(content)
        try:
            result = bump_version("major", path)
            self.assertEqual(result, "1.0.0+6")
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
