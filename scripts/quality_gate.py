"""Run all quality checks for the Flutter/Dart project.

Validates formatting (dart format), linting (dart analyze), tests (flutter test),
coverage (>= 80%), ADR completeness, review existence for code changes, and
regression guard (verifying regression test files exist for known-bug files).

Usage:
    python scripts/quality_gate.py            # run all checks
    python scripts/quality_gate.py --fix      # auto-fix then check
    python scripts/quality_gate.py --skip-tests --skip-coverage
    python scripts/quality_gate.py --skip-reviews     # bypass review check
    python scripts/quality_gate.py --skip-regression  # bypass regression guard

Exit code 0 if all checks pass, 1 if any fail.

Note: Requires Flutter SDK on PATH. If running from Git Bash on Windows,
ensure 'flutter' and 'dart' are accessible (e.g., C:\\src\\flutter\\bin on PATH).
"""

import argparse
import os
import subprocess
import sys
from datetime import UTC
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "lib"
TESTS_DIR = PROJECT_ROOT / "test"
ADR_DIR = PROJECT_ROOT / "docs" / "adr"
REVIEWS_DIR = PROJECT_ROOT / "docs" / "reviews"
REGRESSION_LEDGER = PROJECT_ROOT / "memory" / "bugs" / "regression-ledger.md"

# ANSI color codes (no-op on terminals that don't support them)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _find_flutter() -> str:
    """Find the flutter executable, checking PATH and common install locations."""
    # Check if flutter is already on PATH
    for cmd in ["flutter", "flutter.bat"]:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Check common install location on Windows
    common_path = Path("C:/src/flutter/bin")
    if common_path.exists():
        flutter_bat = common_path / "flutter.bat"
        if flutter_bat.exists():
            return str(flutter_bat)

    print(f"  {RED}ERROR{RESET}  Flutter SDK not found on PATH.")
    print('         Add Flutter to PATH: export PATH="$PATH:/c/src/flutter/bin"')
    sys.exit(1)


def _find_dart(flutter_cmd: str) -> str:
    """Derive the dart command from the flutter command location."""
    flutter_path = Path(flutter_cmd).resolve()
    # Check the same directory as flutter
    for candidate_dir in [flutter_path.parent, Path("C:/src/flutter/bin")]:
        for name in ["dart.bat", "dart", "dart.exe"]:
            dart_path = candidate_dir / name
            if dart_path.exists():
                return str(dart_path)
    # Fallback: try running dart directly (might be on PATH)
    try:
        result = subprocess.run(["dart", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return "dart"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print(f"  {RED}ERROR{RESET}  Dart SDK not found.")
    sys.exit(1)


# Resolve Flutter and Dart commands once at module level
FLUTTER_CMD = _find_flutter()
DART_CMD = _find_dart(FLUTTER_CMD)


def validate_directories() -> list[str]:
    """Validate that SRC_DIR and TESTS_DIR exist and contain Dart files.

    Returns a list of error messages (empty if all valid).
    """
    errors: list[str] = []
    for label, directory in [("Source (lib/)", SRC_DIR), ("Tests (test/)", TESTS_DIR)]:
        if not directory.is_dir():
            errors.append(f"{label} directory does not exist: {directory}")
        elif not list(directory.rglob("*.dart")):
            errors.append(f"{label} directory contains no .dart files: {directory}")
    return errors


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command and return the result without raising on failure."""
    # Ensure Flutter SDK is on PATH for subprocesses
    env = os.environ.copy()
    flutter_bin = str(Path(FLUTTER_CMD).parent)
    if flutter_bin not in env.get("PATH", ""):
        env["PATH"] = flutter_bin + os.pathsep + env.get("PATH", "")

    return subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
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
    """Check 1: dart format compliance."""
    if fix:
        _run([DART_CMD, "format", str(SRC_DIR), str(TESTS_DIR)])
        _run([DART_CMD, "fix", "--apply"])

    result = _run([DART_CMD, "format", "--set-exit-if-changed", str(SRC_DIR), str(TESTS_DIR)])
    if result.returncode == 0:
        _pass("Formatting (dart format)")
        return True
    _fail("Formatting (dart format)", "run: dart format lib/ test/")
    if result.stdout:
        lines = result.stdout.strip().split("\n")
        for line in lines[:5]:
            print(f"         {line}")
        if len(lines) > 5:
            print(f"         ... and {len(lines) - 5} more")
    return False


def check_linting(fix: bool = False) -> bool:
    """Check 2: dart analyze compliance."""
    if fix:
        _run([DART_CMD, "fix", "--apply"])

    result = _run([DART_CMD, "analyze", str(SRC_DIR), str(TESTS_DIR)])
    if result.returncode == 0:
        # dart analyze returns 0 even with infos — check output for errors
        output = result.stdout + result.stderr
        if "error" in output.lower() and "0 errors" not in output.lower():
            _fail("Linting (dart analyze)")
            return False
        _pass("Linting (dart analyze)")
        return True
    _fail("Linting (dart analyze)", "run: dart analyze lib/ test/")
    if result.stdout:
        lines = result.stdout.strip().split("\n")
        for line in lines[:5]:
            print(f"         {line}")
        if len(lines) > 5:
            print(f"         ... and {len(lines) - 5} more")
    return False


def check_tests() -> bool:
    """Check 3: flutter test passes."""
    result = _run([FLUTTER_CMD, "test"])
    if result.returncode == 0:
        _pass("Tests (flutter test)")
        return True
    _fail("Tests (flutter test)")
    output = result.stdout or result.stderr
    if output:
        lines = output.strip().split("\n")
        for line in lines[-10:]:
            print(f"         {line}")
    return False


def check_coverage() -> bool:
    """Check 4: coverage meets >= 80% threshold.

    Runs flutter test --coverage, then parses coverage/lcov.info
    to compute the overall line coverage percentage.
    """
    result = _run([FLUTTER_CMD, "test", "--coverage"])
    if result.returncode != 0:
        _fail("Coverage (tests failed — cannot compute coverage)")
        return False

    lcov_path = PROJECT_ROOT / "coverage" / "lcov.info"
    if not lcov_path.exists():
        _fail("Coverage (no lcov.info generated)")
        return False

    # Parse lcov.info to compute coverage.
    # Exclude generated files (*.g.dart, *.freezed.dart) and files with
    # '// coverage:ignore-file' which inflate the denominator without
    # reflecting hand-written code quality.
    total_lines = 0
    hit_lines = 0
    current_file = ""
    skip_file = False
    text = lcov_path.read_text(encoding="utf-8")
    for line in text.split("\n"):
        if line.startswith("SF:"):
            current_file = line[3:]
            skip_file = current_file.endswith(".g.dart") or current_file.endswith(".freezed.dart")
            # Also skip files with // coverage:ignore-file directive.
            if not skip_file:
                try:
                    source_path = Path(current_file)
                    if source_path.exists():
                        first_line = source_path.read_text(encoding="utf-8").split("\n", 1)[0]
                        if "coverage:ignore-file" in first_line:
                            skip_file = True
                except OSError:
                    pass
        elif skip_file:
            continue
        elif line.startswith("LF:"):
            total_lines += int(line[3:])
        elif line.startswith("LH:"):
            hit_lines += int(line[3:])

    if total_lines == 0:
        _fail("Coverage (no lines found in lcov.info)")
        return False

    percentage = (hit_lines / total_lines) * 100
    if percentage >= 80:
        _pass(f"Coverage ({percentage:.1f}% >= 80%)")
        return True
    _fail(f"Coverage ({percentage:.1f}% < 80%)", "target: >= 80%")
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


# --- Review existence helpers ---

# Directories whose files count as "code changes" requiring review
_CODE_PREFIXES = ("lib/", "test/", "scripts/")
_CODE_EXTENSIONS = (".dart", ".py")
_GENERATED_SUFFIXES = (".g.dart", ".freezed.dart")

# Framework infrastructure directories — .md files here are reviewable
_FRAMEWORK_PREFIXES = (".claude/agents/", ".claude/commands/", ".claude/rules/")
_FRAMEWORK_EXTENSIONS = (".md", ".py")


def _get_staged_code_files() -> list[str]:
    """Return staged files that count as reviewable code changes.

    Runs ``git diff --cached --name-only`` and filters for code files
    under known source directories, excluding generated files.
    Returns an empty list if git is unavailable (fails safe).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    files: list[str] = []
    for line in result.stdout.strip().split("\n"):
        f = line.strip()
        if not f:
            continue
        # Check code directories (lib/, test/, scripts/)
        is_code = (
            any(f.startswith(p) for p in _CODE_PREFIXES)
            and any(f.endswith(ext) for ext in _CODE_EXTENSIONS)
            and not any(f.endswith(s) for s in _GENERATED_SUFFIXES)
        )
        # Check framework directories (.claude/agents/, commands/, rules/)
        is_framework = any(f.startswith(p) for p in _FRAMEWORK_PREFIXES) and any(
            f.endswith(ext) for ext in _FRAMEWORK_EXTENSIONS
        )
        if is_code or is_framework:
            files.append(f)
    return files


def _find_todays_reviews() -> list[Path]:
    """Find review reports created today (matching REV-YYYYMMDD pattern)."""
    import datetime

    today = datetime.date.today().strftime("%Y%m%d")
    if not REVIEWS_DIR.is_dir():
        return []
    return sorted(REVIEWS_DIR.glob(f"REV-{today}*.md"))


def check_review_existence() -> bool:
    """Check 6: verify a review report exists when code changes are staged.

    Logic:
    - No staged code files → PASS (nothing to review)
    - Staged code files + review report from today → PASS
    - Staged code files + no review today → FAIL
    """
    staged = _get_staged_code_files()
    if not staged:
        _pass("Review existence (no code changes staged)")
        return True

    reviews = _find_todays_reviews()
    if reviews:
        names = ", ".join(r.stem for r in reviews)
        _pass(f"Review existence ({names})")
        return True

    _fail(
        "Review existence",
        "code changes staged but no review report found today. "
        "Run /review before committing, or use --skip-reviews to bypass.",
    )
    print(f"         Staged code files: {', '.join(staged[:5])}")
    if len(staged) > 5:
        print(f"         ... and {len(staged) - 5} more")
    return False


def _parse_regression_ledger() -> dict[str, str]:
    """Parse the regression ledger into a map of source basename → test path.

    Returns a dict where keys are source file basenames (e.g. 'elevenlabs_tts_service.dart')
    and values are the corresponding regression test paths. Entries with 'N/A' test paths
    are excluded.
    """
    if not REGRESSION_LEDGER.exists():
        return {}

    text = REGRESSION_LEDGER.read_text(encoding="utf-8")
    source_to_test: dict[str, str] = {}

    for line in text.split("\n"):
        line = line.strip()
        # Skip non-table rows (no pipes, header row, separator row)
        if not line.startswith("|") or line.startswith("| Bug") or line.startswith("|---"):
            continue

        cols = [c.strip() for c in line.split("|")]
        # Split produces empty strings at start/end from leading/trailing pipes
        # Expected columns: ['', Bug, File(s), Root Cause, Fix, Regression Test, Date, '']
        if len(cols) < 7:
            continue

        files_col = cols[2]  # File(s)
        test_col = cols[5]  # Regression Test

        # Skip process-only entries
        if "N/A" in test_col:
            continue

        # Extract just the file path (strip method/test name references like ':test name')
        test_path = test_col.split(":")[0].strip()

        # Map each source file basename to the test path
        for src_file in files_col.split(", "):
            src_file = src_file.strip()
            if src_file:
                source_to_test[src_file] = test_path

    return source_to_test


def check_regression_guard() -> bool:
    """Check 7: verify regression test files exist for staged files with known bugs.

    Parses the regression ledger and checks that for every staged file matching
    a ledger entry, the corresponding regression test file exists on disk.
    """
    source_to_test = _parse_regression_ledger()
    if not source_to_test:
        _pass("Regression guard (no ledger entries)")
        return True

    staged = _get_staged_code_files()
    if not staged:
        _pass("Regression guard (no files staged)")
        return True

    # Build set of staged basenames for matching
    staged_basenames = {Path(f).name for f in staged}

    missing: list[str] = []
    checked = 0
    for src_basename, test_path in source_to_test.items():
        if src_basename in staged_basenames:
            checked += 1
            full_test_path = PROJECT_ROOT / test_path
            if not full_test_path.exists():
                missing.append(f"{src_basename} → {test_path}")

    if not checked:
        _pass("Regression guard (no staged files match ledger)")
        return True

    if missing:
        _fail(f"Regression guard ({len(missing)} missing test file(s))")
        for entry in missing:
            print(f"         {entry}")
        return False

    _pass(f"Regression guard ({checked} file(s) verified)")
    return True


QUALITY_GATE_LOG = PROJECT_ROOT / "metrics" / "quality_gate_log.jsonl"

_CHECK_NAMES = ["format", "lint", "tests", "coverage", "adrs", "reviews", "regression"]


def _log_outcome(args: argparse.Namespace, results: list[bool], passed: int, total: int) -> None:
    """Append a JSONL record of the quality gate outcome for trend analysis."""
    import json
    from datetime import datetime

    check_results = {}
    idx = 0
    for name, skip_attr in zip(
        _CHECK_NAMES,
        [
            "skip_format",
            "skip_lint",
            "skip_tests",
            "skip_coverage",
            "skip_adrs",
            "skip_reviews",
            "skip_regression",
        ],
    ):
        if getattr(args, skip_attr, False):
            check_results[name] = "skipped"
        else:
            check_results[name] = "pass" if idx < len(results) and results[idx] else "fail"
            idx += 1

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "overall": "pass" if passed == total else "fail",
        "passed_count": passed,
        "total": total,
        "checks": check_results,
    }

    QUALITY_GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(QUALITY_GATE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


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
    parser.add_argument(
        "--skip-reviews",
        action="store_true",
        help="Skip review existence check",
    )
    parser.add_argument(
        "--skip-regression",
        action="store_true",
        help="Skip regression guard check",
    )
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
        _skip("Formatting (dart format)")
    else:
        total += 1
        results.append(check_formatting(fix=args.fix))

    # Check 2: Linting
    if args.skip_lint:
        _skip("Linting (dart analyze)")
    else:
        total += 1
        results.append(check_linting(fix=args.fix))

    # Check 3: Tests
    if args.skip_tests:
        _skip("Tests (flutter test)")
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

    # Check 6: Review existence
    if args.skip_reviews:
        _skip("Review existence")
    else:
        total += 1
        results.append(check_review_existence())

    # Check 7: Regression guard
    if args.skip_regression:
        _skip("Regression guard")
    else:
        total += 1
        results.append(check_regression_guard())

    # Summary
    passed = sum(results)
    print("=" * 40)

    # Log outcome to JSONL for trend analysis
    _log_outcome(args, results, passed, total)

    if passed == total:
        print(f"{GREEN}{BOLD}Quality Gate: {passed}/{total} passed{RESET}\n")
        return 0
    else:
        print(f"{RED}{BOLD}Quality Gate: FAILED ({passed}/{total} passed){RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
