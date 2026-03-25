"""Spawn a new project from the framework template.

Copies framework-essential files to a target directory, initializes lineage
tracking and the metrics database, and optionally sets up a git repository.

Usage:
    python scripts/spawn_project.py TARGET_DIR --name "My Project" [--no-git]
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.bump_version import read_version  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from scripts.lineage.init_lineage import lineage_init  # noqa: E402

# Framework directories to copy recursively
FRAMEWORK_DIRS: list[str] = [
    ".claude",
    "scripts",
    "docs/templates",
]

# Individual framework files to copy
FRAMEWORK_FILES: list[str] = [
    "CLAUDE.md",
    "PHILOSOPHY.md",
    "REVIEW.md",
    "pyproject.toml",
    "requirements.txt",
    ".gitignore",
]

# Foundational ADRs that apply to all derived projects
BASE_ADRS: list[str] = [
    "docs/adr/ADR-0001-adopt-agentic-framework.md",
    "docs/adr/ADR-0002-adopt-steward-agent.md",
]

# Patterns to exclude when copying directories
EXCLUDE_PATTERNS: set[str] = {
    "__pycache__",
    ".pyc",
    ".ruff_cache",
    ".pytest_cache",
    "lineage-events.jsonl",
    "settings.local.json",
}

# Empty directories to create in the new project (with .gitkeep)
EMPTY_DIRS: list[str] = [
    "discussions",
    "memory",
    "memory/archive",
    "memory/bugs",
    "memory/decisions",
    "memory/lessons",
    "memory/patterns",
    "memory/reflections",
    "memory/rules",
    "metrics",
    "src",
    "tests",
    "docs/reviews",
    "docs/sprints",
]


def _should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from copying.

    Args:
        path: The path to check.

    Returns:
        True if the path matches any exclusion pattern.
    """
    for part in path.parts:
        for pattern in EXCLUDE_PATTERNS:
            if part == pattern or part.endswith(pattern):
                return True
    return False


def _copy_ignore(directory: str, contents: list[str]) -> set[str]:
    """Ignore function for shutil.copytree.

    Args:
        directory: The directory being copied.
        contents: List of items in the directory.

    Returns:
        Set of items to ignore.
    """
    ignored = set()
    dir_path = Path(directory)
    for item in contents:
        item_path = dir_path / item
        if _should_exclude(item_path):
            ignored.add(item)
    return ignored


def _customize_pyproject(target_dir: Path, project_name: str) -> None:
    """Update pyproject.toml with the new project's name and reset version.

    Args:
        target_dir: Root of the new project.
        project_name: Human-readable project name.
    """
    pyproject_path = target_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return

    text = pyproject_path.read_text(encoding="utf-8")

    # Replace project name (convert to kebab-case for pyproject)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", project_name).strip("-").lower()
    text = text.replace("agentic-framework-template", slug)

    # Replace description
    text = text.replace(
        "AI-Native Agentic Development Framework template for Claude Code",
        f"{project_name} — built on the AI-Native Agentic Development Framework",
    )

    # Reset version to 0.1.0 (it should already be, but be explicit)
    text = re.sub(
        r'^(version\s*=\s*["\'])\d+\.\d+\.\d+(["\'])',
        r"\g<1>0.1.0\2",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    pyproject_path.write_text(text, encoding="utf-8")


def _create_starter_files(target_dir: Path) -> None:
    """Create minimal starter files for the new project.

    Args:
        target_dir: Root of the new project.
    """
    # src/__init__.py
    src_init = target_dir / "src" / "__init__.py"
    src_init.write_text('"""Application source code."""\n', encoding="utf-8")

    # tests/__init__.py
    tests_init = target_dir / "tests" / "__init__.py"
    tests_init.write_text("", encoding="utf-8")

    # tests/conftest.py
    conftest = target_dir / "tests" / "conftest.py"
    conftest.write_text(
        '"""Shared test fixtures and configuration."""\n\nimport pytest\n\n\n'
        "def pytest_addoption(parser: pytest.Parser) -> None:\n"
        '    """Register custom command-line options for pytest."""\n'
        "    parser.addoption(\n"
        '        "--run-llm",\n'
        '        action="store_true",\n'
        "        default=False,\n"
        '        help="Run tests that call real LLM APIs",\n'
        "    )\n"
        "    parser.addoption(\n"
        '        "--run-slow",\n'
        '        action="store_true",\n'
        "        default=False,\n"
        '        help="Run slow tests",\n'
        "    )\n\n\n"
        "def pytest_collection_modifyitems(\n"
        "    config: pytest.Config, items: list[pytest.Item]\n"
        ") -> None:\n"
        '    """Skip marked tests unless their flag is passed."""\n'
        '    if not config.getoption("--run-llm"):\n'
        '        skip_llm = pytest.mark.skip(reason="needs --run-llm option to run")\n'
        "        for item in items:\n"
        '            if "uses_llm" in item.keywords:\n'
        "                item.add_marker(skip_llm)\n"
        '    if not config.getoption("--run-slow"):\n'
        '        skip_slow = pytest.mark.skip(reason="needs --run-slow option to run")\n'
        "        for item in items:\n"
        '            if "slow" in item.keywords:\n'
        "                item.add_marker(skip_slow)\n",
        encoding="utf-8",
    )


def spawn_project(
    target_dir: Path,
    project_name: str,
    template_root: Path | None = None,
    init_git: bool = True,
) -> dict:
    """Create a new project from the framework template.

    Args:
        target_dir: Directory to create the new project in. Must not exist.
        project_name: Human-readable name for the new project.
        template_root: Root of the template repo. Defaults to this repo's root.
        init_git: Whether to initialize a git repository.

    Returns:
        Dict with spawn results (lineage_id, files_copied, etc.).

    Raises:
        FileExistsError: If target_dir already exists.
        ValueError: If project_name is empty.
    """
    root = template_root or _PROJECT_ROOT

    # Validate inputs
    if not project_name or not project_name.strip():
        raise ValueError("Project name must not be empty")

    if target_dir.exists():
        raise FileExistsError(f"Target directory already exists: {target_dir}")

    # Read template version
    template_version = read_version(root / "pyproject.toml")

    # Create target directory
    target_dir.mkdir(parents=True)

    files_copied = 0

    # Copy framework directories
    for dir_name in FRAMEWORK_DIRS:
        src = root / dir_name
        dst = target_dir / dir_name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=_copy_ignore)
            files_copied += sum(1 for _ in dst.rglob("*") if _.is_file())

    # Copy individual framework files
    for file_name in FRAMEWORK_FILES:
        src = root / file_name
        if src.is_file():
            dst = target_dir / file_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            files_copied += 1

    # Copy base ADRs
    for adr_path in BASE_ADRS:
        src = root / adr_path
        if src.is_file():
            dst = target_dir / adr_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            files_copied += 1

    # Create empty directories with .gitkeep
    for dir_name in EMPTY_DIRS:
        dir_path = target_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        gitkeep = dir_path / ".gitkeep"
        if not any(dir_path.iterdir()) or not gitkeep.exists():
            gitkeep.touch()

    # Create starter files
    _create_starter_files(target_dir)

    # Customize pyproject.toml
    _customize_pyproject(target_dir, project_name)

    # Initialize metrics database
    db_path = target_dir / "metrics" / "evaluation.db"
    init_db(db_path=db_path)

    # Initialize lineage tracking
    manifest = lineage_init(
        project_root=target_dir,
        template_version=template_version,
        project_name=project_name,
        project_type="derived",
        db_path=db_path,
        manifest_path=target_dir / "framework-lineage.yaml",
        custodian_dir=target_dir / ".claude" / "custodian",
    )

    lineage_id = manifest.get("lineage_id", "unknown")

    # Initialize git repo
    git_initialized = False
    if init_git and shutil.which("git"):
        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(target_dir),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=str(target_dir),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Initialize from AI-Native Agentic Framework template v{template_version}",
                ],
                cwd=str(target_dir),
                check=True,
                capture_output=True,
            )
            git_initialized = True
        except subprocess.CalledProcessError as e:
            print(f"Warning: git initialization failed: {e}", file=sys.stderr)

    result = {
        "target_dir": str(target_dir),
        "project_name": project_name,
        "template_version": template_version,
        "lineage_id": lineage_id,
        "files_copied": files_copied,
        "git_initialized": git_initialized,
    }

    # Print summary
    print(f"\nProject '{project_name}' created at {target_dir}")
    print(f"  Template version: {template_version}")
    print(f"  Lineage ID: {lineage_id}")
    print(f"  Files copied: {files_copied}")
    print(f"  Git initialized: {git_initialized}")
    print("\nNext steps:")
    print(f"  1. cd {target_dir}")
    print("  2. Review and customize CLAUDE.md for your project")
    print("  3. Review and customize PHILOSOPHY.md for your project")
    print("  4. pip install -r requirements.txt")
    print("  5. python scripts/quality_gate.py  (verify everything works)")
    print("  6. Start building with /plan")

    return result


def main() -> None:
    """CLI entry point for spawn_project."""
    parser = argparse.ArgumentParser(
        description="Create a new project from the framework template"
    )
    parser.add_argument(
        "target_dir",
        type=Path,
        help="Directory to create the new project in (must not exist)",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Human-readable project name",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Skip git repository initialization",
    )

    args = parser.parse_args()

    try:
        spawn_project(
            target_dir=args.target_dir.resolve(),
            project_name=args.name,
            init_git=not args.no_git,
        )
    except (FileExistsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
