"""Run all quality checks defined in the framework's rules files.

Converts the documented standards from .claude/rules/ (coding_standards.md,
testing_requirements.md, review_gates.md) into executable validation.

Usage:
    python scripts/quality_gate.py            # run all checks
    python scripts/quality_gate.py --fix      # auto-fix then check
    python scripts/quality_gate.py --skip-tests --skip-coverage

Exit code 0 if all checks pass, 1 if any fail.
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"
ADR_DIR = PROJECT_ROOT / "docs" / "adr"

# ANSI color codes (no-op on terminals that don't support them)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def validate_directories() -> list[str]:
    """Validate that SRC_DIR and TESTS_DIR exist and contain Python files.

    Returns a list of error messages (empty if all valid).
    """
    errors: list[str] = []
    for label, directory in [("Source", SRC_DIR), ("Tests", TESTS_DIR)]:
        if not directory.is_dir():
            errors.append(f"{label} directory does not exist: {directory}")
        elif not list(directory.glob("*.py")):
            errors.append(f"{label} directory contains no .py files: {directory}")
    return errors


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command and return the result without raising on failure."""
    return subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def _pass(name: str) -> None:
    print(f"  {GREEN}PASS{RESET}  {name}")


def _fail(name: str, hint: str = "") -> None:
    msg = f"  {RED}FAIL{RESET}  {name}"
    if hint:
        msg += f"  ({hint})"
    print(msg)


def _skip(name: str) -> None:
    print(f"  {YELLOW}SKIP{RESET}  {name}")


def check_formatting(fix: bool = False) -> bool:
    """Check 1: ruff format compliance."""
    if fix:
        _run(["python", "-m", "ruff", "format", str(SRC_DIR), str(TESTS_DIR)])
    result = _run(["python", "-m", "ruff", "format", "--check", str(SRC_DIR), str(TESTS_DIR)])
    if result.returncode == 0:
        _pass("Formatting (ruff format)")
        return True
    _fail("Formatting (ruff format)", "run: python -m ruff format src/ tests/")
    return False


def check_linting(fix: bool = False) -> bool:
    """Check 2: ruff lint compliance."""
    if fix:
        _run(["python", "-m", "ruff", "check", "--fix", str(SRC_DIR), str(TESTS_DIR)])
    result = _run(["python", "-m", "ruff", "check", str(SRC_DIR), str(TESTS_DIR)])
    if result.returncode == 0:
        _pass("Linting (ruff check)")
        return True
    _fail("Linting (ruff check)", "run: python -m ruff check src/ tests/")
    if result.stdout:
        # Show first few lines of lint output for context
        lines = result.stdout.strip().split("\n")
        for line in lines[:5]:
            print(f"         {line}")
        if len(lines) > 5:
            print(f"         ... and {len(lines) - 5} more")
    return False


def check_tests() -> bool:
    """Check 3: pytest passes."""
    result = _run(["python", "-m", "pytest", str(TESTS_DIR), "-x", "-q"])
    if result.returncode == 0:
        _pass("Tests (pytest)")
        return True
    _fail("Tests (pytest)")
    if result.stdout:
        lines = result.stdout.strip().split("\n")
        for line in lines[-10:]:
            print(f"         {line}")
    return False


def check_adrs() -> bool:
    """Check 5: ADR completeness — required frontmatter fields and markdown sections."""
    required_fields = {"adr_id", "title", "status", "date", "decision_makers", "discussion_id"}
    required_sections = {
        "## Context",
        "## Decision",
        "## Alternatives Considered",
        "## Consequences",
    }

    adr_files = sorted(ADR_DIR.glob("ADR-*.md"))
    if not adr_files:
        _pass("ADR completeness (no ADRs to check)")
        return True

    errors: list[str] = []
    for adr_path in adr_files:
        text = adr_path.read_text(encoding="utf-8")

        # Parse YAML frontmatter (between --- delimiters)
        if not text.startswith("---"):
            errors.append(f"{adr_path.name}: missing YAML frontmatter")
            continue

        parts = text.split("---", 2)
        if len(parts) < 3:
            errors.append(f"{adr_path.name}: malformed YAML frontmatter")
            continue

        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            errors.append(f"{adr_path.name}: invalid YAML — {e}")
            continue

        if not isinstance(frontmatter, dict):
            errors.append(f"{adr_path.name}: frontmatter is not a mapping")
            continue

        missing_fields = required_fields - set(frontmatter.keys())
        if missing_fields:
            errors.append(f"{adr_path.name}: missing fields: {', '.join(sorted(missing_fields))}")

        body = parts[2]
        missing_sections = {s for s in required_sections if s not in body}
        if missing_sections:
            errors.append(
                f"{adr_path.name}: missing sections: {', '.join(sorted(missing_sections))}"
            )

    if errors:
        _fail(f"ADR completeness ({len(errors)} issue(s) in {len(adr_files)} ADR(s))")
        for err in errors[:5]:
            print(f"         {err}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
        return False

    _pass(f"ADR completeness ({len(adr_files)} ADR(s))")
    return True


def check_coverage() -> bool:
    """Check 4: coverage meets threshold (configured in pyproject.toml)."""
    result = _run(
        [
            "python",
            "-m",
            "pytest",
            str(TESTS_DIR),
            f"--cov={SRC_DIR}",
            "--cov-report=term-missing:skip-covered",
            "--cov-fail-under=80",
            "-q",
        ]
    )
    if result.returncode == 0:
        _pass("Coverage (>= 80%)")
        return True
    _fail("Coverage (>= 80%)", "run: pytest --cov=src --cov-fail-under=80")
    if result.stdout:
        lines = result.stdout.strip().split("\n")
        # Show coverage summary lines
        for line in lines:
            if "TOTAL" in line or "FAIL" in line or "%" in line:
                print(f"         {line}")
    return False


def main() -> int:
    """Run all quality checks and return exit code."""
    parser = argparse.ArgumentParser(description="Quality gate — validate all framework standards")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix formatting and lint issues before checking",
    )
    parser.add_argument("--skip-format", action="store_true")
    parser.add_argument("--skip-lint", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-coverage", action="store_true")
    parser.add_argument("--skip-adrs", action="store_true")
    args = parser.parse_args()

    print(f"\n{BOLD}Quality Gate{RESET}")
    print("=" * 40)

    # Validate directories before running any checks
    dir_errors = validate_directories()
    if dir_errors:
        for err in dir_errors:
            _fail(f"Directory validation ({err})")
        print("=" * 40)
        print(
            f"{RED}{BOLD}Quality Gate: FAILED — source or test directories missing or empty{RESET}\n"
        )
        return 1

    results: list[bool] = []
    total = 0

    # Check 1: Formatting
    if args.skip_format:
        _skip("Formatting (ruff format)")
    else:
        total += 1
        results.append(check_formatting(fix=args.fix))

    # Check 2: Linting
    if args.skip_lint:
        _skip("Linting (ruff check)")
    else:
        total += 1
        results.append(check_linting(fix=args.fix))

    # Check 3: Tests
    if args.skip_tests:
        _skip("Tests (pytest)")
    else:
        total += 1
        results.append(check_tests())

    # Check 4: Coverage
    if args.skip_coverage:
        _skip("Coverage (>= 80%)")
    else:
        total += 1
        results.append(check_coverage())

    # Check 5: ADR completeness
    if args.skip_adrs:
        _skip("ADR completeness")
    else:
        total += 1
        results.append(check_adrs())

    # Summary
    passed = sum(results)
    print("=" * 40)
    if passed == total:
        print(f"{GREEN}{BOLD}Quality Gate: {passed}/{total} passed{RESET}\n")
        return 0
    else:
        print(f"{RED}{BOLD}Quality Gate: FAILED ({passed}/{total} passed){RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
