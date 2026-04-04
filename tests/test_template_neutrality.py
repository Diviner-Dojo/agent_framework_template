"""Tests that the template remains tech-stack-neutral.

Greps agent definitions, rules, and commands for forbidden terms
that would indicate project-specific content leaked into the template.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent

FORBIDDEN_TERMS = ["Flutter", "Dart", "ADHD", "agentic_journal", "Riverpod", "pubspec"]

SCAN_DIRS = [
    PROJECT_ROOT / ".claude" / "agents",
    PROJECT_ROOT / ".claude" / "rules",
    PROJECT_ROOT / ".claude" / "commands",
]


def _collect_md_files():
    """Collect all .md files from scan directories."""
    files = []
    for d in SCAN_DIRS:
        if d.is_dir():
            files.extend(d.glob("*.md"))
    return files


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_no_forbidden_terms_in_framework_files(term):
    """Verify no project-specific terms appear in framework .md files."""
    violations = []
    for filepath in _collect_md_files():
        text = filepath.read_text(encoding="utf-8")
        # Case-insensitive search
        if term.lower() in text.lower():
            # Find the line number for the report
            for i, line in enumerate(text.split("\n"), 1):
                if term.lower() in line.lower():
                    violations.append(f"{filepath.name}:{i}: {line.strip()[:80]}")
    assert not violations, f"Forbidden term '{term}' found in template files:\n" + "\n".join(
        violations
    )
