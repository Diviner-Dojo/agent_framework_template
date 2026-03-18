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
        """Agent count must match CLAUDE.md documented count (14)."""
        assert len(agent_files) == 14, (
            f"Expected 14 agent files, found {len(agent_files)}: {[f.stem for f in agent_files]}"
        )


class TestNewAgentDefinitions:
    """Specific tests for the three new agents added in Sprint 2."""

    @pytest.fixture(scope="class")
    def new_agents(self) -> dict[str, dict]:
        """Parse frontmatter for the three new agents."""
        new_agent_names = ["finding-validator", "compliance-auditor", "history-analyst"]
        result = {}
        for name in new_agent_names:
            path = AGENTS_DIR / f"{name}.md"
            assert path.exists(), f"New agent file missing: {name}.md"
            result[name] = _parse_agent_frontmatter(path)
        return result

    def test_new_agents_are_sonnet_tier(self, new_agents: dict[str, dict]) -> None:
        """All three new agents should be Sonnet tier per spec."""
        for name, fm in new_agents.items():
            assert fm["model"] == "sonnet", f"{name}: expected sonnet tier, got {fm['model']}"

    def test_finding_validator_has_read_tool(self, new_agents: dict[str, dict]) -> None:
        """Finding-validator must have Read tool to verify findings against code."""
        tools = new_agents["finding-validator"]["tools"]
        assert "Read" in tools, "finding-validator needs Read tool for code verification"

    def test_compliance_auditor_has_no_write(self, new_agents: dict[str, dict]) -> None:
        """Compliance-auditor should not have Write/Edit — it audits, not modifies."""
        tools = new_agents["compliance-auditor"]["tools"]
        assert "Write" not in tools, "compliance-auditor should not have Write tool"
        assert "Edit" not in tools, "compliance-auditor should not have Edit tool"

    def test_history_analyst_has_bash(self, new_agents: dict[str, dict]) -> None:
        """History-analyst needs Bash for git commands."""
        tools = new_agents["history-analyst"]["tools"]
        assert "Bash" in tools, "history-analyst needs Bash tool for git log/blame"


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
