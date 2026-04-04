"""Tests for agent definition frontmatter schema validation.

Validates that all agent definitions in .claude/agents/ have required
frontmatter fields and follow established conventions. Part of the
review blueprint adoption (SPEC-20260313-201024).
"""

import re
from pathlib import Path

import pytest
import yaml

AGENTS_DIR = Path(__file__).parent.parent / ".claude" / "agents"

REQUIRED_FIELDS = {"name", "model", "description", "tools"}
VALID_MODELS = {"sonnet", "opus", "haiku"}
VALID_TOOL_NAMES = {
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "Task",
    "WebSearch",
    "WebFetch",
}


def _parse_agent_frontmatter(filepath: Path) -> dict:
    """Parse YAML frontmatter from an agent definition file.

    Args:
        filepath: Path to the agent .md file.

    Returns:
        Parsed frontmatter as a dictionary.

    Raises:
        ValueError: If frontmatter delimiters are missing or malformed.
    """
    content = filepath.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"{filepath.name}: missing opening frontmatter delimiter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{filepath.name}: missing closing frontmatter delimiter")
    return yaml.safe_load(parts[1])


def _get_agent_files() -> list[Path]:
    """Get all agent definition files."""
    return sorted(AGENTS_DIR.glob("*.md"))


class TestAgentFrontmatterSchema:
    """Validate agent definition frontmatter across all agents."""

    @pytest.fixture(scope="class")
    def agent_files(self) -> list[Path]:
        """Fixture providing all agent definition files."""
        files = _get_agent_files()
        assert len(files) > 0, "No agent definition files found"
        return files

    @pytest.fixture(scope="class")
    def parsed_agents(self, agent_files: list[Path]) -> list[tuple[Path, dict]]:
        """Fixture providing parsed frontmatter for all agents."""
        results = []
        for f in agent_files:
            fm = _parse_agent_frontmatter(f)
            results.append((f, fm))
        return results

    def test_all_agents_have_valid_frontmatter(
        self, parsed_agents: list[tuple[Path, dict]]
    ) -> None:
        """Every agent file must have parseable YAML frontmatter."""
        for filepath, fm in parsed_agents:
            assert fm is not None, f"{filepath.name}: frontmatter parsed as None"
            assert isinstance(fm, dict), f"{filepath.name}: frontmatter is not a dict"

    def test_required_fields_present(self, parsed_agents: list[tuple[Path, dict]]) -> None:
        """Every agent must have name, model, description, and tools."""
        for filepath, fm in parsed_agents:
            missing = REQUIRED_FIELDS - set(fm.keys())
            assert not missing, f"{filepath.name}: missing required fields: {missing}"

    def test_model_tier_valid(self, parsed_agents: list[tuple[Path, dict]]) -> None:
        """Model tier must be one of the valid values."""
        for filepath, fm in parsed_agents:
            model = fm.get("model")
            assert model in VALID_MODELS, (
                f"{filepath.name}: invalid model '{model}', expected one of {VALID_MODELS}"
            )

    def test_tools_are_valid(self, parsed_agents: list[tuple[Path, dict]]) -> None:
        """All listed tools must be from the known tool set."""
        for filepath, fm in parsed_agents:
            tools = fm.get("tools", [])
            assert isinstance(tools, list), f"{filepath.name}: tools must be a list"
            invalid = set(tools) - VALID_TOOL_NAMES
            assert not invalid, f"{filepath.name}: invalid tools: {invalid}"

    def test_name_matches_filename(self, parsed_agents: list[tuple[Path, dict]]) -> None:
        """Agent name in frontmatter must match the filename (without .md)."""
        for filepath, fm in parsed_agents:
            expected_name = filepath.stem
            actual_name = fm.get("name", "")
            assert actual_name == expected_name, (
                f"{filepath.name}: name '{actual_name}' doesn't match filename '{expected_name}'"
            )

    def test_description_is_nonempty_string(self, parsed_agents: list[tuple[Path, dict]]) -> None:
        """Description must be a non-empty string."""
        for filepath, fm in parsed_agents:
            desc = fm.get("description", "")
            assert isinstance(desc, str) and len(desc) > 10, (
                f"{filepath.name}: description must be a meaningful string"
            )

    def test_agent_count_matches_expected(self, agent_files: list[Path]) -> None:
        """Agent count must match CLAUDE.md documented count (12)."""
        assert len(agent_files) == 12, (
            f"Expected 12 agent files, found {len(agent_files)}: {[f.stem for f in agent_files]}"
        )


class TestHistoryAnalystAgent:
    """Tests for the history-analyst agent (retained per ADR-0009)."""

    @pytest.fixture(scope="class")
    def history_analyst(self) -> dict:
        """Parse frontmatter for the history-analyst agent."""
        path = AGENTS_DIR / "history-analyst.md"
        assert path.exists(), "history-analyst.md missing"
        return _parse_agent_frontmatter(path)

    def test_history_analyst_is_sonnet_tier(self, history_analyst: dict) -> None:
        """History-analyst should be Sonnet tier per spec."""
        assert history_analyst["model"] == "sonnet", (
            f"history-analyst: expected sonnet tier, got {history_analyst['model']}"
        )

    def test_history_analyst_has_bash(self, history_analyst: dict) -> None:
        """History-analyst needs Bash for git commands."""
        tools = history_analyst["tools"]
        assert "Bash" in tools, "history-analyst needs Bash tool for git log/blame"

    def test_removed_agents_do_not_exist(self) -> None:
        """finding-validator and compliance-auditor were demoted per ADR-0009."""
        assert not (AGENTS_DIR / "finding-validator.md").exists(), (
            "finding-validator.md should not exist (demoted to facilitator step per ADR-0009)"
        )
        assert not (AGENTS_DIR / "compliance-auditor.md").exists(), (
            "compliance-auditor.md should not exist (demoted to rule injection per ADR-0009)"
        )


class TestReviewMd:
    """Tests for the REVIEW.md convention."""

    @pytest.fixture(scope="class")
    def review_md_path(self) -> Path:
        """Path to REVIEW.md."""
        return Path(__file__).parent.parent / "REVIEW.md"

    def test_review_md_exists(self, review_md_path: Path) -> None:
        """REVIEW.md must exist at project root."""
        assert review_md_path.exists(), "REVIEW.md not found at project root"

    def test_review_md_has_numbered_rules(self, review_md_path: Path) -> None:
        """REVIEW.md should contain numbered rules."""
        content = review_md_path.read_text(encoding="utf-8")
        numbered_rules = re.findall(r"^\d+\.", content, re.MULTILINE)
        assert len(numbered_rules) >= 10, (
            f"Expected at least 10 numbered rules, found {len(numbered_rules)}"
        )

    def test_review_md_has_section_headers(self, review_md_path: Path) -> None:
        """REVIEW.md should have organized section headers."""
        content = review_md_path.read_text(encoding="utf-8")
        headers = re.findall(r"^## .+", content, re.MULTILINE)
        assert len(headers) >= 4, f"Expected at least 4 section headers, found {len(headers)}"

    def test_review_md_references_adr(self, review_md_path: Path) -> None:
        """REVIEW.md should reference ADR-0006."""
        content = review_md_path.read_text(encoding="utf-8")
        assert "ADR-0006" in content, "REVIEW.md should reference ADR-0006"

    def test_review_md_has_subordination_clause(self, review_md_path: Path) -> None:
        """REVIEW.md must declare subordination to CLAUDE.md and PHILOSOPHY.md (ADR-0009)."""
        content = review_md_path.read_text(encoding="utf-8")
        assert "CLAUDE.md and PHILOSOPHY.md govern" in content, (
            "REVIEW.md must have subordination clause per ADR-0009"
        )


class TestAdr0006:
    """Tests for ADR-0006 existence and structure."""

    @pytest.fixture(scope="class")
    def adr_path(self) -> Path:
        """Path to ADR-0006."""
        return (
            Path(__file__).parent.parent
            / "docs"
            / "adr"
            / "ADR-0006-adopt-review-md-convention.md"
        )

    def test_adr_exists(self, adr_path: Path) -> None:
        """ADR-0006 must exist."""
        assert adr_path.exists(), "ADR-0006 not found"

    def test_adr_has_valid_frontmatter(self, adr_path: Path) -> None:
        """ADR-0006 must have valid YAML frontmatter with required fields."""
        content = adr_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        assert len(parts) >= 3, "ADR missing frontmatter delimiters"
        fm = yaml.safe_load(parts[1])
        assert fm["adr_id"] == "ADR-0006"
        assert fm["status"] == "accepted"
        assert "review" in fm.get("tags", [])

    def test_adr_documents_review_md_scope(self, adr_path: Path) -> None:
        """ADR-0006 must document that REVIEW.md is review-time only."""
        content = adr_path.read_text(encoding="utf-8")
        assert "review" in content.lower()
        assert "CLAUDE.md" in content
