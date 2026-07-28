"""Tests for the deterministic risk scoring behind the education gate."""

import pytest

from scripts.assess_risk import (
    LIGHT_MAX,
    STANDARD_MAX,
    assess,
    depth_for_score,
    render,
)


def numstat(added: int, removed: int, path: str = "src/thing.py") -> list[str]:
    """Build a git numstat line."""
    return [f"{added}\t{removed}\t{path}"]


class TestDepthForScore:
    def test_zero_is_light(self):
        assert depth_for_score(0) == "light"

    def test_light_boundary(self):
        assert depth_for_score(LIGHT_MAX) == "light"
        assert depth_for_score(LIGHT_MAX + 1) == "standard"

    def test_standard_boundary(self):
        assert depth_for_score(STANDARD_MAX) == "standard"
        assert depth_for_score(STANDARD_MAX + 1) == "deep"

    def test_large_scores_stay_deep(self):
        assert depth_for_score(99) == "deep"


class TestSignals:
    def test_trivial_change_is_light(self):
        result = assess(["README.md"], numstat(3, 1, "README.md"))
        assert result.depth == "light"
        assert result.score == 0
        assert result.signals == []

    def test_new_source_file_scores(self):
        result = assess(["src/new.py"], numstat(40, 0, "src/new.py"), new_files=["src/new.py"])
        assert result.score == 2
        assert result.depth == "standard"
        assert "new source file" in result.signals[0].reason

    def test_new_test_file_does_not_score(self):
        result = assess(
            ["tests/test_new.py"],
            numstat(40, 0, "tests/test_new.py"),
            new_files=["tests/test_new.py"],
        )
        assert result.score == 0

    def test_security_path_pushes_to_deep_alone_with_new_file(self):
        result = assess(
            ["src/auth.py"],
            numstat(60, 10, "src/auth.py"),
            new_files=["src/auth.py"],
        )
        assert result.score == 5
        assert result.depth == "deep"

    @pytest.mark.parametrize(
        "path",
        ["src/login.py", "src/session_store.py", "lib/crypto_utils.py", "src/sanitize.py"],
    )
    def test_security_keywords_detected(self, path):
        result = assess([path], numstat(10, 0, path))
        assert result.score >= 3

    def test_schema_change_scores(self):
        result = assess(["migrations/001_add.py"], numstat(20, 0, "migrations/001_add.py"))
        assert any("schema" in s.reason for s in result.signals)

    def test_dependency_change_scores(self):
        result = assess(["pyproject.toml"], numstat(2, 1, "pyproject.toml"))
        assert any("dependencies" in s.reason for s in result.signals)

    def test_large_deletion_scores(self):
        result = assess(["src/old.py"], numstat(0, 120, "src/old.py"))
        assert any("removes 120 lines" in s.reason for s in result.signals)

    def test_wide_change_scores_on_non_test_files(self):
        files = [f"src/mod_{i}.py" for i in range(7)]
        result = assess(files, [f"5\t0\tsrc/mod_{i}.py" for i in range(7)])
        assert any("spans 7 non-test files" in s.reason for s in result.signals)

    def test_test_files_excluded_from_reach_signal(self):
        files = [f"tests/test_{i}.py" for i in range(9)]
        result = assess(files, [f"5\t0\ttests/test_{i}.py" for i in range(9)])
        assert not any("spans" in s.reason for s in result.signals)

    def test_large_change_scores(self):
        result = assess(["src/big.py"], numstat(300, 50, "src/big.py"))
        assert any("350 lines changed" in s.reason for s in result.signals)

    def test_signals_accumulate_to_deep(self):
        result = assess(
            ["src/auth.py", "pyproject.toml"],
            ["200\t200\tsrc/auth.py", "3\t1\tpyproject.toml"],
            new_files=["src/auth.py"],
        )
        assert result.depth == "deep"
        assert result.score >= 5


class TestNumstatParsing:
    def test_counts_added_and_removed(self):
        result = assess(["a.py", "b.py"], ["10\t2\ta.py", "5\t3\tb.py"])
        assert result.lines_added == 15
        assert result.lines_removed == 5

    def test_binary_files_ignored(self):
        result = assess(["img.png"], ["-\t-\timg.png"])
        assert result.lines_added == 0
        assert result.lines_removed == 0

    def test_malformed_lines_ignored(self):
        result = assess(["a.py"], ["garbage", "10\t2\ta.py"])
        assert result.lines_added == 10

    def test_empty_diff(self):
        result = assess([], [])
        assert result.score == 0
        assert result.files_changed == 0
        assert result.depth == "light"


class TestRender:
    def test_render_includes_depth_and_reasons(self):
        result = assess(["src/auth.py"], numstat(10, 0, "src/auth.py"))
        output = render(result)
        assert "DEEP" in output or "STANDARD" in output
        assert "Why:" in output

    def test_render_handles_no_signals(self):
        output = render(assess(["README.md"], numstat(1, 0, "README.md")))
        assert "no elevated signals" in output

    def test_to_dict_roundtrips(self):
        result = assess(["src/auth.py"], numstat(10, 0, "src/auth.py"))
        payload = result.to_dict()
        assert payload["depth"] == result.depth
        assert len(payload["signals"]) == len(result.signals)
        assert all({"weight", "reason"} == set(s) for s in payload["signals"])


class TestDocumentationIsNotCode:
    """Prose that discusses auth is not auth (false positive found dogfooding)."""

    def test_markdown_mentioning_session_does_not_score_security(self):
        result = assess(
            [".claude/skills/wrapping-up-sessions/SKILL.md"],
            numstat(10, 0, ".claude/skills/wrapping-up-sessions/SKILL.md"),
        )
        assert not any("security-relevant" in s.reason for s in result.signals)

    def test_source_file_with_same_keyword_still_scores(self):
        result = assess(["src/session_store.py"], numstat(10, 0, "src/session_store.py"))
        assert any("security-relevant" in s.reason for s in result.signals)

    def test_docs_still_count_toward_size_and_reach(self):
        files = [f"docs/note_{i}.md" for i in range(8)]
        result = assess(files, [f"5\t0\tdocs/note_{i}.md" for i in range(8)])
        assert any("spans 8 non-test files" in s.reason for s in result.signals)
