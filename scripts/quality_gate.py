"""Run all quality checks defined in the framework's rules files.

Converts the documented standards from .claude/rules/ (coding_standards.md,
testing_requirements.md) and the selecting-review-gates skill into executable validation.

Usage:
    python scripts/quality_gate.py            # run all checks
    python scripts/quality_gate.py --fix      # auto-fix then check
    python scripts/quality_gate.py --skip-tests --skip-coverage
    python scripts/quality_gate.py --skip-reviews  # bypass review check

Exit code 0 if all checks pass, 1 if any fail. Skipped checks (``--skip-*``) are
recorded honestly in the JSONL log as ``overall: "pass_with_skips"`` — never as a
clean ``"pass"`` — so a skipped or vacuous run cannot be read as a complete pass
(Principle #2). See ``_build_outcome_record`` for the record schema.
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
REVIEWS_DIR = PROJECT_ROOT / "docs" / "reviews"
QUALITY_GATE_LOG = PROJECT_ROOT / "metrics" / "quality_gate_log.jsonl"
REGRESSION_LEDGER = PROJECT_ROOT / "memory" / "bugs" / "regression-ledger.md"

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


def _warn(name: str) -> None:
    print(f"  {YELLOW}WARN{RESET}  {name}")


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


# --- Regression ledger helpers ---


def _parse_regression_ledger() -> list[dict[str, str]]:
    """Parse the regression ledger for file-to-test mappings.

    Returns a list of dicts with 'file', 'test_file', and 'test_function' keys.
    """
    if not REGRESSION_LEDGER.exists():
        return []

    entries: list[dict[str, str]] = []
    text = REGRESSION_LEDGER.read_text(encoding="utf-8")
    for line in text.split("\n"):
        line = line.strip()
        if (
            not line.startswith("|")
            or line.startswith("| File")
            or line.startswith("| Approach")
            or line.startswith("| Class")
            or line.startswith("| **")
            or line.startswith("|--")
        ):
            continue
        if "<!--" in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        # Ledger format (6 cols): File | Bug Description | Root Cause Class | Fix Date | Test File | Test Function
        if len(cells) >= 6 and cells[0] and not cells[0].startswith("-"):
            entries.append(
                {
                    "file": cells[0],
                    "test_file": cells[4],
                    "test_function": cells[5],
                }
            )
    return entries


def check_regression_ledger() -> bool:
    """Check 7: verify regression test files exist for ledger entries.

    For each entry in the regression ledger, verifies:
    - The test file exists
    - Modified source files listed in the ledger have corresponding tests
    """
    entries = _parse_regression_ledger()
    if not entries:
        _pass("Regression ledger (no entries)")
        return True

    errors: list[str] = []
    for entry in entries:
        test_file = PROJECT_ROOT / entry["test_file"]
        if not test_file.exists():
            errors.append(f"Missing test file: {entry['test_file']} (guards {entry['file']})")

    if errors:
        _fail(f"Regression ledger ({len(errors)} missing test(s))")
        for err in errors[:5]:
            print(f"         {err}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
        return False

    _pass(f"Regression ledger ({len(entries)} guard(s))")
    return True


# --- Review existence helpers ---

# Directories whose files count as "code changes" requiring review
_CODE_PREFIXES = ("src/", "tests/", "scripts/")
_CODE_EXTENSIONS = (".py",)

# Framework infrastructure directories — .md files here are reviewable
_FRAMEWORK_PREFIXES = (".claude/agents/", ".claude/commands/", ".claude/rules/")
_FRAMEWORK_EXTENSIONS = (".md", ".py")


def _get_staged_code_files() -> list[str]:
    """Return staged files that count as reviewable code changes.

    Runs ``git diff --cached --name-only`` and filters for code files
    under known source directories.
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
        # Check code directories (src/, tests/, scripts/)
        is_code = any(f.startswith(p) for p in _CODE_PREFIXES) and any(
            f.endswith(ext) for ext in _CODE_EXTENSIONS
        )
        # Check framework directories (.claude/agents/, commands/, rules/)
        is_framework = any(f.startswith(p) for p in _FRAMEWORK_PREFIXES) and any(
            f.endswith(ext) for ext in _FRAMEWORK_EXTENSIONS
        )
        if is_code or is_framework:
            files.append(f)
    return files


def _find_todays_reviews() -> list[Path]:
    """Find review reports created today (matching REV-YYYYMMDD pattern).

    Checks both local-today and UTC-today since framework IDs are minted in
    UTC (see DISC-, REV- conventions) while ``date.today()`` returns local.
    Without this, commits in the local-evening / UTC-next-day window would
    falsely report 'no review today' even when a review file exists.
    """
    import datetime

    if not REVIEWS_DIR.is_dir():
        return []
    candidates: set[Path] = set()
    for date_str in {
        datetime.date.today().strftime("%Y%m%d"),
        datetime.datetime.now(datetime.UTC).strftime("%Y%m%d"),
    }:
        candidates.update(REVIEWS_DIR.glob(f"REV-{date_str}*.md"))
    return sorted(candidates)


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


def check_build_status_freshness() -> bool:
    """Check 8 (advisory): warn if BUILD_STATUS.md is older than 60 minutes.

    This is an advisory check — it warns but does not fail the gate.
    Always returns True (never blocks).
    """
    build_status = PROJECT_ROOT / "BUILD_STATUS.md"
    if not build_status.exists():
        _warn("BUILD_STATUS.md freshness (file not found — consider creating it)")
        return True

    import time

    mtime = build_status.stat().st_mtime
    age_minutes = (time.time() - mtime) / 60
    if age_minutes > 60:
        _warn(
            f"BUILD_STATUS.md freshness (last updated {age_minutes:.0f} minutes ago — consider updating)"
        )
        return True

    _pass(f"BUILD_STATUS.md freshness ({age_minutes:.0f} min ago)")
    return True


def check_subscription_fee_not_staged() -> bool:
    """Advisory: warn if config/subscription.yaml is staged with a real fee.

    The subscription fee (telemetry A3) is personal financial metadata and the
    real file is gitignored — only ``config/subscription.yaml.example`` (a
    ``0.00`` placeholder) is committed. The PreToolUse secret scanner does not
    recognise a numeric YAML field, so this advisory backstop warns if the real
    file is ever force-staged with a positive fee. Warns only; never blocks.
    Always returns True.
    """
    target = "config/subscription.yaml"
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )
        if result.returncode != 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True
    if target not in {line.strip() for line in result.stdout.splitlines()}:
        return True

    fee_path = PROJECT_ROOT / target
    try:
        import yaml

        data = yaml.safe_load(fee_path.read_text(encoding="utf-8")) or {}
        fee = float(data.get("monthly_fee_usd", 0) or 0) if isinstance(data, dict) else 0.0
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        fee = 0.0
    if fee > 0.0:
        _warn(
            f"{target} is staged with a real fee (monthly_fee_usd={fee}) — this is "
            "personal financial metadata; the file should stay gitignored "
            "(commit only subscription.yaml.example)"
        )
    return True


_CHECK_NAMES = ["format", "lint", "tests", "coverage", "adrs", "reviews", "regression"]
# The argparse ``--skip-*`` flag attribute for each check, in _CHECK_NAMES order.
# Derived from _CHECK_NAMES so a new check is added in exactly one place.
_SKIP_ATTRS = [f"skip_{name}" for name in _CHECK_NAMES]


def _build_outcome_record(
    args: argparse.Namespace, results: list[bool], passed: int, total: int
) -> dict:
    """Build the JSONL outcome record, recording skipped checks honestly.

    ``overall`` distinguishes three states so a run that skipped checks can
    never be read as a clean, complete pass (Principle #2 — capture must be
    honest):

    - ``"fail"`` — at least one check that ran failed (``passed != total``).
    - ``"pass_with_skips"`` — every check that ran passed, but one or more were
      skipped (via ``--skip-*``). This also covers the vacuous case where every
      check is skipped (``total == 0``): ``passed == total`` holds, but the run
      verified nothing, so it is not a plain ``"pass"``.
    - ``"pass"`` — every check ran and passed.

    The per-check ``checks`` map records ``"skipped"`` / ``"pass"`` / ``"fail"``
    individually, and ``skipped_count`` exposes the skip total for trend queries
    without having to walk the nested map.

    ``passed`` and ``total`` are computed by the caller (``main``) and must be
    consistent with ``results`` — ``total`` counts only the checks that ran (one
    per ``True``/``False`` entry in ``results``), and ``passed`` is the number of
    ``True`` entries. This function does not re-derive them from ``results``.
    """
    from datetime import UTC, datetime

    check_results: dict[str, str] = {}
    idx = 0
    for name, skip_attr in zip(_CHECK_NAMES, _SKIP_ATTRS):
        if getattr(args, skip_attr, False):
            check_results[name] = "skipped"
        else:
            check_results[name] = "pass" if idx < len(results) and results[idx] else "fail"
            idx += 1

    skipped_count = sum(1 for status in check_results.values() if status == "skipped")
    if passed != total:
        overall = "fail"
    elif skipped_count:
        overall = "pass_with_skips"
    else:
        overall = "pass"

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "overall": overall,
        "passed_count": passed,
        "total": total,
        "skipped_count": skipped_count,
        "checks": check_results,
    }


def _format_summary(passed: int, total: int, skipped: int) -> str:
    """Build the colored one-line gate summary printed at the end of a run.

    The text is intentionally ASCII-only (apart from the ANSI color escapes,
    which are themselves ASCII): this line is printed to a raw terminal whose
    codec on Windows is cp1252, which cannot encode characters like the em-dash
    and raises UnicodeEncodeError mid-run (the same class as the context_sensor
    statusLine and notify-title crashes — see the regression ledger).
    """
    if passed != total:
        return f"{RED}{BOLD}Quality Gate: FAILED ({passed}/{total} passed){RESET}"
    if skipped:
        return (
            f"{YELLOW}{BOLD}Quality Gate: {passed}/{total} passed "
            f"({skipped} skipped - not a complete pass){RESET}"
        )
    return f"{GREEN}{BOLD}Quality Gate: {passed}/{total} passed{RESET}"


def _log_outcome(args: argparse.Namespace, results: list[bool], passed: int, total: int) -> None:
    """Append a JSONL record of the quality gate outcome for trend analysis."""
    import json

    record = _build_outcome_record(args, results, passed, total)

    QUALITY_GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(QUALITY_GATE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _notify_outcome(
    passed: int,
    total: int,
    *,
    enabled: bool,
    setup_error: bool = False,
) -> None:
    """Fire a best-effort ntfy push with the gate result, if --notify was passed.

    No-op unless ``enabled`` (the ``--notify`` flag), so the pre-commit hook —
    which runs the gate on every commit and never passes ``--notify`` — stays
    silent. Delivery is best-effort: ``notify.send_notification`` itself never
    raises and silently no-ops when ``NTFY_TOPIC`` is unset, and this helper
    swallows any remaining error so a notification problem can never change the
    gate's exit code (the "never crash the caller" rule).

    Message text is intentionally generic — counts only, no file paths, IDs, or
    secrets — because ntfy.sh is a public relay (see the notifying-the-developer
    skill).

    A ``total`` of 0 (every check skipped via ``--skip-*``) satisfies
    ``passed == total``, so a "passed" ping is sent — a vacuous pass is treated
    as a pass.

    Args:
        passed: Number of checks that passed.
        total: Total number of checks run.
        enabled: Whether --notify was requested.
        setup_error: True when the gate bailed before running checks (e.g.
            missing source/test directories); sends a distinct failure ping.
    """
    if not enabled:
        return
    try:
        from notify import send_notification

        if setup_error:
            send_notification(
                "Quality gate could not run — source or test directories missing.",
                title="Quality Gate: setup error",
                priority="high",
                tags="warning",
            )
        elif passed == total:
            send_notification(
                f"All {total} checks passed.",
                title="Quality Gate: passed",
                tags="white_check_mark",
            )
        else:
            send_notification(
                f"{passed}/{total} checks passed — gate FAILED.",
                title="Quality Gate: FAILED",
                priority="high",
                tags="warning",
            )
    except Exception as exc:
        # Best-effort only — a notification failure (including notify.py being
        # absent from the path) must never break the gate. Emit a one-line stderr
        # notice for debuggability; the exit code is unaffected.
        print(f"  [notify] gate-result notification skipped: {exc}", file=sys.stderr)


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
        help="Skip regression ledger check",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help=(
            "Send a push notification (ntfy) with the result when the gate "
            "finishes. Off by default so the pre-commit hook stays silent; add "
            "it for long manual runs when stepping away. No-op unless NTFY_TOPIC "
            "is set in .env."
        ),
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
        _notify_outcome(0, 0, enabled=args.notify, setup_error=True)
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

    # Check 6: Review existence
    if args.skip_reviews:
        _skip("Review existence")
    else:
        total += 1
        results.append(check_review_existence())

    # Check 7: Regression ledger
    if args.skip_regression:
        _skip("Regression ledger")
    else:
        total += 1
        results.append(check_regression_ledger())

    # Check 8 (advisory): BUILD_STATUS.md freshness
    # This check always passes — it only warns. Not counted in pass/fail totals.
    check_build_status_freshness()

    # Advisory: warn if a real subscription fee (telemetry A3) is staged.
    # Always passes — only warns. Not counted in pass/fail totals.
    check_subscription_fee_not_staged()

    # Summary
    passed = sum(results)
    print("=" * 40)

    # Log outcome to JSONL for trend analysis
    _log_outcome(args, results, passed, total)

    # Best-effort push notification (opt-in via --notify; no-op otherwise)
    _notify_outcome(passed, total, enabled=args.notify)

    skipped = sum(1 for skip_attr in _SKIP_ATTRS if getattr(args, skip_attr, False))
    print(_format_summary(passed, total, skipped) + "\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
