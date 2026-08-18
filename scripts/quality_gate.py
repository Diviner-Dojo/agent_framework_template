"""Run all quality checks defined in the framework's rules files.

Converts the documented standards from .claude/rules/ (coding_standards.md,
testing_requirements.md) and the selecting-review-gates skill into executable validation.

Usage:
    python scripts/quality_gate.py            # run all checks
    python scripts/quality_gate.py --fix      # auto-fix then check
    python scripts/quality_gate.py --skip-tests --skip-coverage
    python scripts/quality_gate.py --skip-reviews  # bypass review check
    python scripts/quality_gate.py --profile flutter-dart  # force a gate profile
    python scripts/quality_gate.py --fast     # deterministic test sample (NOT a commit gate)
    python scripts/quality_gate.py --rebaseline  # PRINT a proposed debt baseline (writes nothing)

Exit code 0 if all checks pass, 1 if any fail. Skipped checks (``--skip-*``) are
recorded honestly in the JSONL log as ``overall: "pass_with_skips"`` — never as a
clean ``"pass"`` — so a skipped or vacuous run cannot be read as a complete pass
(Principle #2 - capture is automatic, so the record must be honest). See
``_build_outcome_record`` for the record schema.

Stack-aware profiles (SPEC-20260716-233400): ``config/gate_profiles.yaml`` selects
which stack checks (format/lint/tests/coverage) run and with which commands.
Framework-integrity checks (ADRs, review existence, regression ledger, Layer 1
sealed-record integrity, advisories) cannot be configured by a profile — the
profile schema cannot name them. "Cannot be configured by a profile" is not the
same as "always run": each still has an explicit ``--skip-*`` flag, and the
three advisories only ever WARN. There is NO education-gate check here; see
``config/gate_profiles.yaml`` for why that claim was removed.

Layer 1 integrity (``check_layer1_integrity``): recomputes sha256 digests of every
``discussions/**`` record named in the append-only manifest at
``metrics/layer1_manifest.jsonl`` and compares them. A record whose BYTES changed
since sealing fails the gate; a sealed record that was never baselined only WARNs,
so a repo that has not yet run ``verify_layer1_integrity.py --baseline`` is not red
on day one; and a record that merely stopped being *classified* as sealed (the DB
is gitignored and git does not carry the read-only bit) WARNs at most — that
distinction is the fix for a measured 236-of-278 false red on any checkout without
``metrics/evaluation.db``. This is a detective control and does not depend on any
PreToolUse hook being wired.

Debt baseline (green-able gate): ``config/gate_baseline.json`` records known
pre-existing lint/format debt as stable fingerprints. Baselined findings WARN;
any NEW fingerprint still fails RED.

**Read this before relying on the paragraph above: the file has never existed.**
Measured 2026-08-07, re-measured 2026-08-08 — ``config/gate_baseline.json`` is
absent from this template and from all four derived projects (agentic_journal,
VerificationPortal, howie_family_wiki, dan_research_karpathy_wiki). So no
*recorded debt* has ever been compared against; treat the paragraph above as a
spec for an available mechanism, not a description of work happening in your
build.

**But "no baseline file" does not mean "the comparison never runs" — that is
what this docstring said until 2026-08-08 and it was false.** ``current_fps`` is
collected whenever ``baseline or args.rebaseline``, and a non-``None``
``current_fps`` routes format *and* lint through ``_check_against_baseline``
rather than ``check_formatting`` / ``check_linting``. So:

- an ordinary run with no baseline file → the ordinary path, comparison unused;
- ``--rebaseline`` with no baseline file → **the comparison runs**, against an
  empty baseline, and every finding is reported as "N NEW finding(s) not in
  baseline" when there is no baseline at all. The verdict is the same RED an
  ordinary lint failure would give, but the wording is a known wart; it is
  recorded here rather than described as unreachable.

That is the one invocation the paragraphs around it are about, and the
correction was forced by this module's own test suite:
``test_rebaseline_through_main_creates_no_baseline_file`` asserts ``exit 1``
("still RED"), an outcome only reachable through the comparison the prose said
had never run. Both halves are now pinned at the CLI by
``tests/test_quality_gate.py::TestWhichPathRunsWhenNoBaselineFileExists``.

The gate can only ever SHRINK the baseline (``--fix`` / ``--shrink-baseline``),
never grow it — see ``_baseline_write_plan``, which is the single decision point
and returns only subsets of the baseline that already exists. ``--rebaseline``
PROPOSES: it prints the file a developer would have to commit and writes nothing.
Growing the baseline therefore means a human committing that file, which
``check_review_existence`` treats as a change requiring a ``/review``. Until
2026-08-07 ``--rebaseline`` overwrote the file directly and the only thing
guarding the reward function was a sentence in an argparse help string asking the
agent not to run it. Growing the baseline is a reward-function surface and so
needs human approval (Principle #6); a request addressed to the actor it binds
is not a control.

**What makes the paragraph above checkable rather than merely asserted.** It is a
claim about ``main()``, so it is pinned by a test of ``main()``:
``tests/test_quality_gate.py::TestRebaselineWritesNothingThroughMain`` drives
real ``argv`` through this module's ``main()`` and fails if any write to the
baseline is reintroduced. That class exists because for one day (2026-08-07 →
2026-08-08) this guarantee was covered only by unit tests on the pure helper,
and restoring ``_write_baseline(current_fps)`` inside ``main()`` — the literal
pre-fix defect — left the entire suite green. If you touch the baseline write
path, that class is what has to keep passing; this docstring is not the control.
"""

import argparse
import re
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
GATE_PROFILES_FILE = PROJECT_ROOT / "config" / "gate_profiles.yaml"
GATE_BASELINE_FILE = PROJECT_ROOT / "config" / "gate_baseline.json"

# Stack checks a profile may vary. Integrity checks (ADRs, reviews, regression
# ledger, advisories) are NOT in this tuple and run unconditionally in every
# profile — the profile schema has no key that can name or disable them (R2.4).
_STACK_CHECKS = ("format", "lint", "tests", "coverage")

# argv[0] allow-list for profile-declared commands (security F3). The profile
# file declares arguments, not arbitrary programs: a command whose executable
# basename is not in this set fails closed.
_ALLOWED_EXECUTABLES = frozenset({"ruff", "pytest", "coverage", "python", "dart", "flutter"})

# The only profile whose ruff-based checks support debt baselining this build
# (arch A1). Other profiles no-op with one WARN line — never a crash, never a
# silent no-op (R1.0).
_BASELINE_PROFILE = "python-fastapi"

_BASELINE_SCHEMA_VERSION = 1
_PROFILES_SCHEMA_VERSION = 1

# Built-in profile definitions. The committed config/gate_profiles.yaml mirrors
# these (a sync test pins the equivalence); when the file is absent the gate
# falls back to these, so a repo with no config keeps today's behavior (R2.5).
# A check entry without "command" uses the built-in Python implementation
# (meaningful only for python-fastapi). A stack check a profile does not list
# is disabled — explicit over implicit.
_BUILTIN_PROFILES: dict[str, dict] = {
    "python-fastapi": {
        "checks": {
            "format": {"enabled": True},
            "lint": {"enabled": True},
            "tests": {"enabled": True},
            "coverage": {"enabled": True, "fail_under": 80},
        },
    },
    "flutter-dart": {
        "checks": {
            "format": {
                "enabled": True,
                "command": ["dart", "format", "--output=none", "--set-exit-if-changed", "."],
            },
            "lint": {"enabled": True, "command": ["dart", "analyze"]},
            "tests": {"enabled": True, "command": ["flutter", "test"]},
            "coverage": {"enabled": False},
        },
    },
    "markdown-corpus": {
        "checks": {
            "format": {"enabled": False},
            "lint": {"enabled": False},
            "tests": {"enabled": False},
            "coverage": {"enabled": False},
        },
    },
}

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


def _fail(name: str, hint: str = "", *, error_key: str = "", error_reason: str = "") -> None:
    """Print the human FAIL line; optionally emit the one-line machine ERROR (R3.1).

    When ``error_key`` is given, exactly one ``ERROR <check>: <reason>`` line is
    written to stderr (greppable as ``^ERROR \\w+: ``). Each failing check calls
    ``_fail`` exactly once per run, which is what makes the line exactly-once.
    """
    msg = f"  {RED}FAIL{RESET}  {name}"
    if hint:
        msg += f"  ({hint})"
    print(msg)
    if error_key:
        _emit_error_line(error_key, error_reason or hint or name)


def _skip(name: str) -> None:
    print(f"  {YELLOW}SKIP{RESET}  {name}")


def _warn(name: str) -> None:
    print(f"  {YELLOW}WARN{RESET}  {name}")


def _one_line(text: str) -> str:
    """Collapse a reason to a single ASCII-safe line for the machine convention.

    Display strings must be ASCII-only (see _format_summary and the regression
    ledger's cp1252 entries) and the greppable convention is one line per event.
    """
    collapsed = " ".join(text.split())
    return collapsed.encode("ascii", "replace").decode("ascii")


def _emit_error_line(check: str, reason: str) -> None:
    """Emit the machine-greppable failure line: ``ERROR <check>: <reason>`` (R3.1)."""
    print(f"ERROR {check}: {_one_line(reason)}", file=sys.stderr)


def _emit_warn_line(check: str, reason: str) -> None:
    """Emit the machine-greppable warning line: ``WARN <check>: <reason>`` (R3.1)."""
    print(f"WARN {check}: {_one_line(reason)}", file=sys.stderr)


class GateConfigError(Exception):
    """A gate config file (profiles or baseline) is invalid — the gate fails closed."""


# --- Profile helpers (R2) ---


def _load_profiles_config(path: Path | None = None) -> dict:
    """Load and validate config/gate_profiles.yaml.

    Absent file → ``{}`` (built-in profiles only; current behavior unchanged).
    Present but malformed → GateConfigError (fail closed, never a silent
    fallback to python — R2.3).
    """
    profiles_path = path or GATE_PROFILES_FILE
    if not profiles_path.exists():
        return {}
    try:
        data = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise GateConfigError(f"cannot parse {profiles_path.name}: {e}") from e
    if data is None:
        raise GateConfigError(f"{profiles_path.name} is empty")
    if not isinstance(data, dict):
        raise GateConfigError(f"{profiles_path.name} top level must be a mapping")
    if data.get("schema_version") != _PROFILES_SCHEMA_VERSION:
        raise GateConfigError(
            f"{profiles_path.name} schema_version must be {_PROFILES_SCHEMA_VERSION}"
        )
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        raise GateConfigError(f"{profiles_path.name} 'profiles' must be a mapping")
    for name, profile in profiles.items():
        _validate_profile_entry(profiles_path.name, name, profile)
    pin = data.get("profile")
    if pin is not None and not isinstance(pin, str):
        raise GateConfigError(f"{profiles_path.name} 'profile' pin must be a string")
    return data


def _validate_profile_entry(source: str, name: str, profile: object) -> None:
    """Validate one profile entry; ignore (with a WARN line) non-stack check keys.

    Integrity checks are enforced in code and cannot be named here (R2.4 /
    security F4): a checks key outside _STACK_CHECKS has no effect — it is
    warned about and ignored, never honored.
    """
    if not isinstance(profile, dict):
        raise GateConfigError(f"{source} profile '{name}' must be a mapping")
    checks = profile.get("checks", {})
    if not isinstance(checks, dict):
        raise GateConfigError(f"{source} profile '{name}' 'checks' must be a mapping")
    for check_name, entry in checks.items():
        if check_name not in _STACK_CHECKS:
            _emit_warn_line(
                "profile",
                f"ignoring unknown check key '{check_name}' in profile '{name}' "
                "(integrity checks cannot be configured)",
            )
            continue
        if not isinstance(entry, dict):
            raise GateConfigError(
                f"{source} profile '{name}' check '{check_name}' must be a mapping"
            )
        command = entry.get("command")
        if command is not None and (
            not isinstance(command, list)
            or not command
            or not all(isinstance(c, str) for c in command)
        ):
            # An EMPTY list must be rejected here: it is falsy at the dispatch
            # site and would silently fall through to the built-in Python check
            # instead of failing closed (qa checkpoint, 2026-07-17).
            raise GateConfigError(
                f"{source} profile '{name}' check '{check_name}' command must be a "
                "non-empty list of strings"
            )
        fail_under = entry.get("fail_under")
        if fail_under is not None and (
            isinstance(fail_under, bool) or not isinstance(fail_under, int) or fail_under < 0
        ):
            # An unvalidated value would reach int() at dispatch and raise an
            # uncaught ValueError traceback instead of the clean one-line
            # ERROR contract (security review, 2026-07-17).
            raise GateConfigError(
                f"{source} profile '{name}' check '{check_name}' fail_under must be a "
                "non-negative integer"
            )


def _merged_profiles(config: dict) -> dict[str, dict]:
    """Built-in profiles overlaid by any file-declared profiles (by name)."""
    profiles = dict(_BUILTIN_PROFILES)
    profiles.update(config.get("profiles", {}))
    return profiles


def _autodetect_profile(root: Path | None = None) -> tuple[str, str]:
    """Detect the stack from marker files. Returns (profile_name, marker)."""
    root = root or PROJECT_ROOT
    if (root / "pubspec.yaml").exists():
        return "flutter-dart", "pubspec.yaml"
    if (root / "pyproject.toml").exists():
        return "python-fastapi", "pyproject.toml"
    return "markdown-corpus", "no stack marker found"


def _resolve_profile(
    cli_profile: str | None, config: dict, root: Path | None = None
) -> tuple[str, dict]:
    """Resolve the active profile: flag > config ``profile:`` pin > auto-detect.

    The resolution notice goes to stderr so the stdout summary stays
    byte-identical to the pre-profile gate on this repo (R2.5 / AC6).
    Unknown names fail closed (R2.3).
    """
    root = root or PROJECT_ROOT
    profiles = _merged_profiles(config)
    if cli_profile is not None:
        name, source = cli_profile, "--profile flag"
    elif config.get("profile") is not None:
        name, source = config["profile"], "config pin"
    else:
        name, marker = _autodetect_profile(root)
        source = f"auto-detected: {marker}"
        if name == "flutter-dart" and (root / "pyproject.toml").exists():
            # Monorepo guard (independent-perspective review, 2026-07-17): the
            # F6 warning below covers the markdown-corpus branch; this covers
            # the sibling silent-loss route — both stack markers present.
            warning = (
                "both pubspec.yaml and pyproject.toml present - auto-detected "
                "flutter-dart, so python code checks are disabled; pin a "
                "profile explicitly if this is wrong"
            )
            _warn(f"Profile: {warning}")
            _emit_warn_line("profile", warning)
        if name == "markdown-corpus":
            py_files = list((root / "src").glob("**/*.py")) + list(
                (root / "scripts").glob("**/*.py")
            )
            if py_files:
                # Deleting pyproject.toml must not silently disable code checks
                # (security F6) — loud, but never blocks a legitimate corpus.
                warning = (
                    "auto-detected markdown-corpus but .py files exist under "
                    "src/ or scripts/ - code checks are disabled; pin a profile "
                    "explicitly if this is wrong"
                )
                _warn(f"Profile: {warning}")
                _emit_warn_line("profile", warning)
    if name not in profiles:
        raise GateConfigError(
            f"unknown profile '{name}' (available: {', '.join(sorted(profiles))})"
        )
    print(f"profile: {name} ({source})", file=sys.stderr)
    return name, profiles[name]


def _command_allowed(command: list[str]) -> bool:
    """True if the command's argv[0] is a bare, allow-listed executable name (F3).

    Bare PATH-resolved names only: an argv[0] containing a path separator or a
    drive-letter colon is rejected outright — ``subprocess.run`` would execute
    such a string verbatim, so ``C:/attacker/python.exe`` must not pass as
    ``python`` (checkpoint security finding, 2026-07-17). The config declares
    arguments, not arbitrary programs.
    """
    if not command:
        return False
    argv0 = command[0]
    if any(sep in argv0 for sep in ("/", "\\", ":")):
        return False
    exe = argv0.lower()
    exe = exe.removesuffix(".exe").removesuffix(".bat").removesuffix(".cmd")
    return exe in _ALLOWED_EXECUTABLES


_CHECK_LABELS = {
    "format": "Formatting",
    "lint": "Linting",
    "tests": "Tests",
    "coverage": "Coverage",
}


def check_profile_command(check_key: str, command: list[str]) -> bool:
    """Run a profile-declared stack check command via the ``_run()`` seam (R2.6).

    The command is data from gate_profiles.yaml — a list argv executed without
    a shell, argv[0] restricted to the allow-list; on failure the tool output is
    truncated to the last 20 lines (R3.4).
    """
    label = f"{_CHECK_LABELS.get(check_key, check_key)} ({' '.join(command[:2])})"
    if not _command_allowed(command):
        argv0 = command[0] if command else "(empty)"
        _fail(
            label if command else f"{_CHECK_LABELS.get(check_key, check_key)} (profile command)",
            error_key=check_key,
            error_reason=f"profile command argv[0] '{argv0}' is not on the executable "
            f"allow-list ({', '.join(sorted(_ALLOWED_EXECUTABLES))})",
        )
        return False
    result = _run(command)
    if result.returncode == 0:
        _pass(label)
        return True
    _fail(label, error_key=check_key, error_reason=f"command failed: {' '.join(command)}")
    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        lines = output.strip().split("\n")
        if len(lines) > 20:
            print(f"         ... ({len(lines) - 20} earlier line(s) truncated)")
        for line in lines[-20:]:
            print(f"         {line}")
        print(f"         (rerun for full output: {' '.join(command)})")
    return False


# --- Debt baseline helpers (R1) ---
#
# A fingerprint is (check, posix_relative_path, code) — never a line number,
# which drifts on every edit (accepted trade-off: identical violations in one
# file collapse to one fingerprint). Fingerprints come from structured tool
# output only (ruff check --output-format=json / ruff format --check's
# "Would reformat:" lines), never scraped from human-format text (qa 3).

Fingerprint = tuple[str, str, str]


def _load_baseline(path: Path | None = None) -> set[Fingerprint]:
    """Load config/gate_baseline.json as a fingerprint set.

    Absent file → empty set (current behavior unchanged). Present but invalid
    (malformed JSON, wrong shape, unknown schema version) → GateConfigError:
    a corrupt baseline fails closed, NEVER silently treated as empty — that
    would mask real debt as new-free (qa 1 / R1.1a).
    """
    import json

    baseline_path = path or GATE_BASELINE_FILE
    if not baseline_path.exists():
        return set()
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GateConfigError(f"cannot parse {baseline_path.name}: {e}") from e
    if not isinstance(data, dict):
        raise GateConfigError(f"{baseline_path.name} top level must be a mapping")
    if data.get("schema_version") != _BASELINE_SCHEMA_VERSION:
        raise GateConfigError(
            f"{baseline_path.name} schema_version must be {_BASELINE_SCHEMA_VERSION}"
        )
    raw = data.get("fingerprints")
    if not isinstance(raw, list):
        raise GateConfigError(f"{baseline_path.name} 'fingerprints' must be a list")
    fingerprints: set[Fingerprint] = set()
    for i, entry in enumerate(raw):
        if (
            not isinstance(entry, dict)
            or not all(isinstance(entry.get(k), str) for k in ("check", "file", "code"))
            or entry.get("check") not in ("format", "lint")
        ):
            raise GateConfigError(f"{baseline_path.name} fingerprint #{i} is malformed")
        fingerprints.add((entry["check"], entry["file"], entry["code"]))
    return fingerprints


def _baseline_payload(fingerprints: set[Fingerprint]) -> dict:
    """Build the baseline file's JSON payload (sorted for stable, reviewable diffs)."""
    return {
        "schema_version": _BASELINE_SCHEMA_VERSION,
        "_comment": (
            "Known pre-existing gate debt (SPEC-20260716-233400). Baselined "
            "findings WARN instead of failing; NEW findings still fail RED. "
            "The gate can only SHRINK this file, never grow it: growing it means "
            "editing this file by hand and committing it, which check_review_existence "
            "treats as a code change requiring a /review."
        ),
        "fingerprints": [
            {"check": c, "file": f, "code": code} for c, f, code in sorted(fingerprints)
        ],
    }


def _write_baseline(fingerprints: set[Fingerprint], path: Path | None = None) -> None:
    """Write the baseline file.

    Callers must route through :func:`_baseline_write_plan`, which is the single
    place that decides what may be written. That function never returns a set
    containing a fingerprint the existing baseline did not already hold, so this
    writer cannot grow the baseline no matter which flags were passed.
    """
    import json

    baseline_path = path or GATE_BASELINE_FILE
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(_baseline_payload(fingerprints), indent=2) + "\n", encoding="utf-8"
    )


def _resolved_debt(baseline: set[Fingerprint], current: set[Fingerprint]) -> set[Fingerprint]:
    """Baselined findings that are now fixed — empty while NEW findings exist (R1.3).

    The ratchet only runs from a clean state (``current`` a subset of
    ``baseline``): with new findings present the gate is RED anyway, and the
    right move is to fix the new debt, not to re-cut the baseline around it.
    """
    if current - baseline:
        return set()
    return baseline - current


def _baseline_write_plan(
    *,
    rebaseline: bool,
    fix: bool,
    shrink: bool,
    baseline: set[Fingerprint],
    current: set[Fingerprint],
) -> set[Fingerprint] | None:
    """Decide what the gate may persist to the baseline. ``None`` = write nothing.

    **This function is the consent mechanism**, and it is deliberately shaped so
    the consent can be checked rather than merely asserted:

        every set it returns is a SUBSET of the baseline that already exists.

    So no invocation of this script — no flag, no combination of flags — can add
    a fingerprint to ``config/gate_baseline.json``. Growing the baseline means
    editing that file by hand and committing it, and ``_GATE_CONFIG_FILES``
    makes that a change ``check_review_existence`` demands a ``/review`` for.

    **What this replaced, and why.** ``--rebaseline`` used to call
    ``_write_baseline(current_fps)`` — an unconditional overwrite with whatever
    the tree currently produces, which grows the baseline by construction. The
    only thing standing between an autonomous agent and re-cutting its own
    reward function was a sentence in an argparse help string asking it not to.
    A rule that exists only as prose addressed to the actor it is meant to bind
    is not a control. ``--rebaseline`` now PROPOSES: it prints the exact file a
    developer would have to commit, and writes nothing.

    **Where this leaks** — say it whenever you say the rest: the agent can still
    author ``config/gate_baseline.json`` with an ordinary file write. What stops
    that is the review gate on the path plus the fact that the diff is a sorted,
    human-readable fingerprint list. This function removes the *sanctioned
    one-flag* route and makes the gate itself incapable of growing its own
    baseline; it is not a filesystem permission.

    **And this docstring is not the guard either.** The property above is proved
    at two levels, deliberately: ``TestBaselineCannotGrow`` exercises this
    function across all 8 flag combinations, and
    ``TestRebaselineWritesNothingThroughMain`` drives ``main()`` itself. The
    second exists because the first, alone, stayed green when the pre-fix write
    was restored in ``main()`` — a guarantee about the CLI needs a test of the
    CLI.
    """
    if rebaseline:
        return None
    if not (fix or shrink):
        return None
    if not _resolved_debt(baseline, current):
        return None
    return baseline & current


def _print_baseline_proposal(fingerprints: set[Fingerprint]) -> None:
    """Print the baseline a developer would have to commit. Writes nothing."""
    import json

    _warn(
        f"Baseline: --rebaseline PROPOSES ONLY - nothing was written. "
        f"{len(fingerprints)} fingerprint(s) below; growing the baseline is a "
        f"developer action (commit config/gate_baseline.json, which requires a /review)."
    )
    _emit_warn_line(
        "baseline",
        f"--rebaseline proposed {len(fingerprints)} fingerprint(s) - nothing written",
    )
    print(json.dumps(_baseline_payload(fingerprints), indent=2))


def _relative_posix(file_path: str) -> str:
    """Normalize a tool-reported path to a project-relative POSIX string (qa 4)."""
    p = Path(file_path)
    try:
        p = p.relative_to(PROJECT_ROOT)
    except ValueError:
        pass
    return p.as_posix()


def _collect_format_fingerprints() -> set[Fingerprint]:
    """Fingerprints from ``ruff format --check`` ("Would reformat: <path>" lines)."""
    result = _run(["python", "-m", "ruff", "format", "--check", str(SRC_DIR), str(TESTS_DIR)])
    fingerprints: set[Fingerprint] = set()
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("Would reformat:"):
            file_part = line.split(":", 1)[1].strip()
            fingerprints.add(("format", _relative_posix(file_part), "reformat"))
    return fingerprints


def _collect_lint_fingerprints() -> set[Fingerprint]:
    """Fingerprints from ``ruff check --output-format=json`` (structured, qa 3)."""
    import json

    result = _run(
        [
            "python",
            "-m",
            "ruff",
            "check",
            "--output-format=json",
            str(SRC_DIR),
            str(TESTS_DIR),
        ]
    )
    fingerprints: set[Fingerprint] = set()
    try:
        findings = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        # Unparseable ruff output: return a sentinel no baseline can contain,
        # so the check fails RED (fail closed) rather than passing on garbage.
        return {("lint", "(ruff-json-unparseable)", "internal")}
    for finding in findings if isinstance(findings, list) else []:
        if not isinstance(finding, dict):
            continue
        filename = str(finding.get("filename", ""))
        code = finding.get("code")
        fingerprints.add(("lint", _relative_posix(filename), str(code or "syntax-error")))
    return fingerprints


def _check_against_baseline(
    check_key: str,
    label: str,
    current: set[Fingerprint],
    baseline: set[Fingerprint],
    hint: str,
) -> bool:
    """Compare current findings to the baseline by set membership (security F2).

    Membership, never count: a 1-for-1 swap of an old finding for a new one
    fails even though the total is unchanged. Baselined findings WARN and pass;
    new findings fail RED naming the new fingerprint(s).
    """
    new = current - baseline
    baselined = current & baseline
    if new:
        sample = ", ".join("/".join(fp) for fp in sorted(new)[:3])
        more = f" (+{len(new) - 3} more)" if len(new) > 3 else ""
        _fail(
            f"{label}: {len(new)} NEW finding(s) not in baseline",
            hint,
            error_key=check_key,
            error_reason=f"{len(new)} new finding(s) not in baseline: {sample}{more}",
        )
        for fp in sorted(new)[:5]:
            print(f"         new: {'/'.join(fp)}")
        return False
    if baselined:
        _warn(f"{label}: {len(baselined)} baselined debt item(s) (tracked, not new)")
        _emit_warn_line(check_key, f"{len(baselined)} baselined debt item(s)")
        return True
    _pass(label)
    return True


def check_formatting(fix: bool = False) -> bool:
    """Check 1: ruff format compliance."""
    if fix:
        _run(["python", "-m", "ruff", "format", str(SRC_DIR), str(TESTS_DIR)])
    result = _run(["python", "-m", "ruff", "format", "--check", str(SRC_DIR), str(TESTS_DIR)])
    if result.returncode == 0:
        _pass("Formatting (ruff format)")
        return True
    _fail(
        "Formatting (ruff format)",
        "run: python -m ruff format src/ tests/",
        error_key="format",
        error_reason="ruff format --check reported unformatted files",
    )
    return False


def check_linting(fix: bool = False) -> bool:
    """Check 2: ruff lint compliance."""
    if fix:
        _run(["python", "-m", "ruff", "check", "--fix", str(SRC_DIR), str(TESTS_DIR)])
    result = _run(["python", "-m", "ruff", "check", str(SRC_DIR), str(TESTS_DIR)])
    if result.returncode == 0:
        _pass("Linting (ruff check)")
        return True
    _fail(
        "Linting (ruff check)",
        "run: python -m ruff check src/ tests/",
        error_key="lint",
        error_reason="ruff check reported violations",
    )
    if result.stdout:
        # Show first few lines of lint output for context
        lines = result.stdout.strip().split("\n")
        for line in lines[:5]:
            print(f"         {line}")
        if len(lines) > 5:
            print(f"         ... and {len(lines) - 5} more")
    return False


def _select_fast_tests() -> list[str]:
    """Deterministic ``--fast`` sample: every 4th test file by sorted path (R3.3).

    Content-independent ordering: the same file list yields the same subset on
    every run; the subset changes only when the test-file list changes.
    """
    files = sorted(p.as_posix() for p in TESTS_DIR.glob("test_*.py"))
    return files[::4] if files else []


def check_tests(fast_files: list[str] | None = None) -> bool:
    """Check 3: pytest passes (optionally on the deterministic --fast sample)."""
    if fast_files is not None:
        if not fast_files:
            # Zero test files matched: passing no paths would silently fall
            # back to pytest's full-suite discovery, defeating the sample
            # contract (qa checkpoint, 2026-07-17). Nothing to sample = warn.
            _warn("Tests (pytest, fast sample) - no test files found to sample")
            _emit_warn_line("fast", "no test files found to sample")
            return True
        label = f"Tests (pytest, fast sample of {len(fast_files)} file(s))"
        cmd = ["python", "-m", "pytest", *fast_files, "-x", "-q"]
    else:
        label = "Tests (pytest)"
        cmd = ["python", "-m", "pytest", str(TESTS_DIR), "-x", "-q"]
    result = _run(cmd)
    if result.returncode == 0:
        _pass(label)
        return True
    _fail(label, error_key="tests", error_reason="pytest reported failures")
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
        _fail(
            f"ADR completeness ({len(errors)} issue(s) in {len(adr_files)} ADR(s))",
            error_key="adrs",
            error_reason=f"{len(errors)} ADR completeness issue(s), first: {errors[0]}",
        )
        for err in errors[:5]:
            print(f"         {err}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
        return False

    _pass(f"ADR completeness ({len(adr_files)} ADR(s))")
    return True


def check_coverage(fail_under: int = 80) -> bool:
    """Check 4: coverage meets the profile threshold (default 80)."""
    result = _run(
        [
            "python",
            "-m",
            "pytest",
            str(TESTS_DIR),
            f"--cov={SRC_DIR}",
            # scripts/education/ ships the education-gate registry + transcript
            # ingest chokepoint; it lives outside src/ so it needs an explicit
            # --cov target (path form is cross-platform). Keep in sync with the
            # pyproject [tool.coverage.run] source list.
            "--cov=scripts/education",
            "--cov-report=term-missing:skip-covered",
            f"--cov-fail-under={fail_under}",
            "-q",
        ]
    )
    if result.returncode != 0:
        _fail(
            f"Coverage (>= {fail_under}%)",
            f"run: pytest --cov=src --cov-fail-under={fail_under}",
            error_key="coverage",
            error_reason=f"coverage below {fail_under} percent or tests failed under coverage",
        )
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            # Show coverage summary lines
            for line in lines:
                if "TOTAL" in line or "FAIL" in line or "%" in line:
                    print(f"         {line}")
        return False

    # The aggregate threshold above is dominated by src/ statement count, so a
    # regression confined to scripts/education/ could hide inside a green TOTAL.
    # Enforce the 80% floor on that path in isolation from the same .coverage data.
    edu_result = _run(
        [
            "python",
            "-m",
            "coverage",
            "report",
            "--include=scripts/education/*",
            "--fail-under=80",
        ]
    )
    if edu_result.returncode != 0:
        _fail(
            f"Coverage (>= {fail_under}%)",
            "scripts/education/ below 80% in isolation: "
            "coverage report --include=scripts/education/* --fail-under=80",
            error_key="coverage",
            error_reason="scripts/education/ coverage below 80 percent in isolation",
        )
        if edu_result.stdout:
            for line in edu_result.stdout.strip().split("\n"):
                if "%" in line or "TOTAL" in line:
                    print(f"         {line}")
        return False

    _pass(f"Coverage (>= {fail_under}%, incl. scripts/education/ in isolation)")
    return True


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
        # Ledger format (6 cols):
        # File | Bug Description | Root Cause Class | Fix Date | Test File | Test Function
        if len(cells) >= 6 and cells[0] and not cells[0].startswith("-"):
            entries.append(
                {
                    "file": cells[0],
                    "test_file": cells[4],
                    "test_function": cells[5],
                }
            )
    return entries


# A ledger "Test Function" cell is prose as often as it is a list: it carries
# parentheticals ("(also test_x in tests/test_y.py)"), prose connectives, and
# pytest parametrisation suffixes. Only unambiguous pytest identifiers are
# extracted; everything else is deliberately ignored rather than guessed at.
# Measured on this repo's ledger (2026-08-07): 59 entries -> 298 identifiers.
# Re-measure with:
#   python -c "import sys;sys.path.insert(0,'scripts');import quality_gate as q;\
#   e=q._parse_regression_ledger();\
#   print(len(e),sum(len(q._parse_guard_names(x['test_function'])) for x in e))"
# A looser variant (keep parentheticals, drop the identifier filter) was measured
# on 2026-08-07 at 19 not-found hits, of which exactly 1 was a real pytest
# identifier; the other 18 were prose fragments — literally `also`, `in`, `and`,
# and bare paths like `tests/test_dashboard_server.py`. Re-measured 2026-08-08
# after the ledger's one real finding was repaired: 16 hits, 0 real identifiers,
# 16 prose fragments. BOTH figures are recorded because the ledger is edited
# constantly — the ratio is the durable result (prose dominates), the counts are
# not, so re-run before citing either. Prints "<not-found> <of-which-real>";
# note the dedupe, without which the same run reports 18 rather than 16:
#   python -c "import sys,re;sys.path.insert(0,'scripts');import quality_gate as q;\
#   loose=lambda c:list(dict.fromkeys(s for t in re.split(r'[;,\\s]+',c) \
#   for s in re.sub(r'\\[.*?\\]$','',t.strip()).split('::') if s));\
#   miss=[x for e in q._parse_regression_ledger() \
#   if (q.PROJECT_ROOT/e['test_file']).exists() for x in loose(e['test_function']) \
#   if not q._defines_guard((q.PROJECT_ROOT/e['test_file']).read_text('utf-8','replace'),x) \
#   and not q._find_guard_elsewhere(x,q.TESTS_DIR)];\
#   print(len(miss),len([x for x in miss if q._LEDGER_GUARD_IDENT.match(x)]))"
# Manufacturing red on prose is how a check gets switched off (the lesson Row 1
# of docs/education/governance-mechanisms.md keeps re-learning).
_LEDGER_GUARD_IDENT = re.compile(r"^(?:test_[A-Za-z0-9_]*|Test[A-Za-z0-9_]*)$")


def _parse_guard_names(cell: str) -> list[str]:
    """Extract pytest identifiers named as guards in a ledger 'Test Function' cell.

    Conservative by design: drops parenthetical asides, splits on separators and
    ``::``, strips ``[param]`` suffixes, and keeps only tokens shaped like a
    pytest test function (``test_*``) or test class (``Test*``).
    """
    names: list[str] = []
    for token in re.split(r"[;,\s]+", re.sub(r"\([^)]*\)", " ", cell)):
        token = re.sub(r"\[.*?\]$", "", token.strip())
        for segment in token.split("::"):
            segment = segment.strip()
            if segment and _LEDGER_GUARD_IDENT.match(segment) and segment not in names:
                names.append(segment)
    return names


def _defines_guard(source: str, name: str) -> bool:
    """True if ``source`` defines ``name`` as a function or a class.

    A substring search is not enough: the name this check was written to catch
    survives as a *docstring mention* after the function itself is renamed away
    (measured — see ``test_no_slug_or_env_leak_on_no_db_path``, which appears
    only inside a docstring in ``tests/test_dashboard_server.py``). Only a real
    ``def``/``class`` binding counts as a guard.

    The flip side, and it is load-bearing for how the result must be worded: a
    docstring mention is often *evidence of a rename*, so "no binding found"
    means the name is gone — not that the protection is. See
    :func:`check_regression_ledger` for why the failure text says only what this
    function can actually know.
    """
    escaped = re.escape(name)
    return bool(
        re.search(rf"^\s*(?:async\s+)?def\s+{escaped}\s*\(", source, re.MULTILINE)
        or re.search(rf"^\s*class\s+{escaped}\b", source, re.MULTILINE)
    )


def _find_guard_elsewhere(name: str, tests_dir: Path) -> str | None:
    """Return the test file that defines ``name``, searching ``tests/`` — or None.

    Only called for a name already missing from the file the ledger points at,
    so the whole test tree is read on the *exception* path, never on every run.
    """
    if not tests_dir.is_dir():
        return None
    for path in sorted(tests_dir.rglob("test_*.py")):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _defines_guard(source, name):
            return _relative_posix(str(path))
    return None


def check_regression_ledger() -> bool:
    """Check 7: verify each ledger entry's regression guard actually exists.

    For each entry in the regression ledger, verifies:

    - The named test FILE exists, and
    - every guard FUNCTION/CLASS named in the 'Test Function' column is really
      defined in it.

    **Why the second half exists.** Until 2026-08-07 this check parsed
    ``test_function`` into the entry dict and then never read it: only
    ``test_file.exists()`` was checked. So deleting the named guard function
    while leaving the file in place passed the gate silently — the ledger's
    whole promise ("this bug has a test that stops it coming back") rested on
    a filename.

    Severity is split on what this check can actually distinguish:

    - Named guard defined in a **different** test file than the ledger's Test
      File column -> **WARN**. The guard is found, so it demonstrably still
      runs; only the ledger's bookkeeping is stale. Turning stale bookkeeping
      red would block ordinary work for a defect that costs nothing at runtime.
    - **No function or class of that name defined anywhere under** ``tests/``
      -> **FAIL**. Say exactly that and no more. This fires on a guard that was
      *deleted* AND on a guard that was *renamed* (or renamed and migrated into
      another file under a new name), and **this check cannot tell the two
      apart** — a rename leaves no trace it can follow, which is precisely why
      :func:`_defines_guard` refuses to count docstring mentions. So a red here
      means "the ledger names something that no longer exists, go look", not
      "the protection is gone".

    The rename case is not hypothetical: it is the only instance this check has
    ever found in this repo (``test_no_slug_or_env_leak_on_no_db_path``, whose
    C2 no-slug assertions live on in
    ``tests/test_dashboard_server.py::test_main_render_static_missing_db_no_file_no_browser_no_slug``).
    Red is still the right verdict — a ledger row pointing at a name that is
    defined nowhere needs a human — but the *message* must not claim more than
    the code checked. See Row 4 of ``docs/education/governance-mechanisms.md``.

    Current state on this repo, measured 2026-08-08 after that row was repointed
    at the surviving name: **59 entries -> 298 guard identifiers, 0 errors, 10
    WARN (guard found in a different file than the ledger names)** — so the
    live signal today is stale bookkeeping, not missing guards. Re-measure with
    ``python -c "import sys;sys.path.insert(0,'scripts');import quality_gate as
    q;q.check_regression_ledger()"`` rather than trusting these numbers.
    """
    entries = _parse_regression_ledger()
    if not entries:
        _pass("Regression ledger (no entries)")
        return True

    errors: list[str] = []
    misfiled: list[str] = []
    guards_checked = 0

    for entry in entries:
        rel = entry["test_file"]
        test_file = PROJECT_ROOT / rel
        if not test_file.exists():
            errors.append(f"Missing test file: {rel} (guards {entry['file']})")
            continue
        try:
            source = test_file.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            errors.append(f"Unreadable test file: {rel} ({type(e).__name__})")
            continue

        for name in _parse_guard_names(entry["test_function"]):
            guards_checked += 1
            if _defines_guard(source, name):
                continue
            elsewhere = _find_guard_elsewhere(name, TESTS_DIR)
            if elsewhere:
                misfiled.append(f"{name}: ledger says {rel}, actually in {elsewhere}")
            else:
                # Say only what was checked. "Not defined anywhere" is a fact;
                # "the protection is absent" would be an inference this check
                # cannot make, because a rename looks exactly like a deletion
                # from here.
                errors.append(
                    f"Undefined guard: {name} - no def/class of that name anywhere "
                    f"under tests/ (ledger says {rel}). Deleted, or renamed and the "
                    f"ledger not updated - this check cannot tell which; go look."
                )

    for note in misfiled[:5]:
        _warn(f"Regression ledger: {note}")
    if misfiled:
        _emit_warn_line(
            "regression",
            f"{len(misfiled)} ledger guard(s) named in the wrong test file, first: {misfiled[0]}",
        )

    if errors:
        _fail(
            f"Regression ledger ({len(errors)} undefined guard name(s))",
            error_key="regression",
            error_reason=(
                f"{len(errors)} ledger guard name(s) not defined anywhere under tests/ "
                f"(deleted or renamed - indistinguishable here), first: {errors[0]}"
            ),
        )
        for err in errors[:5]:
            print(f"         {err}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
        return False

    # Wording is pinned by tests/fixtures/gate_summary_golden.txt. It is kept
    # verbatim, but the NUMBER changed meaning: it used to be len(entries) —
    # ledger rows, described as "guards" — and is now the count of guard
    # functions/classes actually found to be defined.
    _pass(f"Regression ledger ({guards_checked} guard(s))")
    return True


# --- Layer 1 integrity ---


def check_layer1_integrity() -> bool | None:
    """Check 9: verify no SEALED Layer 1 discussion record has changed since sealing.

    Layer 1 (``discussions/**``) is the canonical record the whole capture stack
    rests on. Until this check existed the gate never looked at it at all
    (``grep -n "events.jsonl" scripts/quality_gate.py`` exited 1), and on
    2026-08-07 a subagent truncated a sealed, read-only ``events.jsonl`` to
    0 bytes with nothing objecting.

    Delegates to ``scripts/verify_layer1_integrity.py``, which compares sha256
    digests against an append-only manifest. It detects a change regardless of
    HOW the change was made — no command-text prediction is involved.

    FAIL vs WARN, decided deliberately:

    - ``CHANGED`` -> **FAIL**. This is positive evidence about *bytes*: a watched
      record's digest no longer matches, or the file is gone from disk, or the
      manifest holds two conflicting digests for it, or git holds a committed
      blob the working copy is not. There is no benign reading of any of those,
      so it is the one condition that turns the gate red.

      That claim only became true in this round. The first version also folded
      **seal metadata** into CHANGED: any manifest path not currently classified
      as sealed was reported "no longer sealed" and failed the gate. Sealed-ness
      is derived from ``metrics/evaluation.db`` (gitignored, ``.gitignore:13``
      matches ``*.db``) and the read-only bit (git does not carry it), so on any
      clone, worktree, CI runner or derived project that is every record.
      Measured on this repo: 236 of 278 byte-identical sealed records reported
      CHANGED with the DB path redirected to a nonexistent file. A gate whose
      central verdict is false on every fresh checkout is a gate that gets
      switched off. Seal-metadata loss is now a separate, never-fatal signal
      (``report.unsealed``), warned about only when the seal source could be
      consulted at all.
    - ``UNKNOWN`` (sealed but never baselined) -> **WARN**. On a repo that has
      never run ``--baseline`` every sealed record is UNKNOWN, and failing there
      would make the gate red on day one for every derived project — the
      "blocks ordinary work, gets switched off, same as no guard" outcome. An
      absence of evidence is reported as an absence of evidence.
    - A manifest that exists but cannot be parsed -> **FAIL**. Failing closed
      matters here: if a corrupt manifest degraded to "no records", overwriting
      it with garbage would silently return every record to UNKNOWN.

    ``SUSPECT`` records (a seal-time anomaly, e.g. a closed discussion whose
    ``events.jsonl`` is 0 bytes) are surfaced as a warning and are never counted
    as intact, but they do not fail the gate on their own — the damage predates
    the baseline and failing forever on unfixable history helps nobody.

    A repo with NO sealed records at all (a fresh seed, or any project with no
    ``discussions/``) returns None: there is nothing to verify, so the check
    prints nothing and is NOT counted in passed/total. Counting it would add a
    vacuous "pass" to the gate's score — the same dishonesty ``_build_outcome_record``
    already refuses for ``--skip-*`` runs, where "every check passed" must never
    be reported for checks that verified nothing.

    Returns:
        False when a sealed record changed or the manifest is unreadable, True
        when the sealed records were inspected and none had changed, and None
        when there was nothing to inspect.
    """
    try:
        from verify_layer1_integrity import ManifestError, verify
    except ImportError as exc:
        _warn(f"Layer 1 integrity (checker unavailable: {exc})")
        _emit_warn_line("integrity", f"checker unavailable: {exc}")
        return True

    try:
        report = verify(root=PROJECT_ROOT)
    except ManifestError as exc:
        _fail(
            "Layer 1 integrity (manifest unreadable)",
            error_key="integrity",
            error_reason=f"layer1 manifest unreadable: {exc}",
        )
        return False
    except OSError as exc:
        _warn(f"Layer 1 integrity (could not read discussions: {exc})")
        _emit_warn_line("integrity", f"could not read discussions: {exc}")
        return True

    if not report.results:
        return None

    if report.suspect:
        _warn(
            f"Layer 1 integrity: {len(report.suspect)} sealed record(s) carry a seal-time "
            "anomaly - frozen, NOT certified intact"
        )
        _emit_warn_line(
            "integrity",
            f"{len(report.suspect)} sealed record(s) suspect at baseline - not certified intact",
        )

    if report.unsealed and report.seal_source_available:
        # Metadata, not content: the digests of these records were still
        # compared and still matched. Warn-only on purpose — see the FAIL vs
        # WARN note above for the 236/278 false-red this replaces. Suppressed
        # entirely when the seal source could not be consulted, because then the
        # signal is unmeasurable rather than negative.
        _warn(
            f"Layer 1 integrity: {len(report.unsealed)} record(s) no longer classified as sealed "
            "(read-only bit or DB row lost) - bytes still verified"
        )
        _emit_warn_line(
            "integrity",
            f"{len(report.unsealed)} record(s) no longer sealed (metadata only, bytes verified)",
        )

    if report.changed:
        _fail(
            f"Layer 1 integrity ({len(report.changed)} sealed record(s) CHANGED since sealing)",
            error_key="integrity",
            error_reason=(
                f"{len(report.changed)} sealed Layer 1 record(s) changed since sealing, "
                f"first: {report.changed[0].path}"
            ),
        )
        for result in report.changed[:5]:
            print(f"         {result.path}: {result.reason}")
        if len(report.changed) > 5:
            print(f"         ... and {len(report.changed) - 5} more")
        return False

    if report.unknown:
        _warn(
            f"Layer 1 integrity: {len(report.unknown)}/{len(report.results)} sealed record(s) "
            "never baselined - run: python scripts/verify_layer1_integrity.py --baseline"
        )
        _emit_warn_line(
            "integrity",
            f"{len(report.unknown)} sealed record(s) never baselined - run --baseline",
        )
        return True

    _pass(f"Layer 1 integrity ({len(report.verified)} sealed record(s) verified)")
    return True


# --- Review existence helpers ---

# Directories whose files count as "code changes" requiring review
_CODE_PREFIXES = ("src/", "tests/", "scripts/")
_CODE_EXTENSIONS = (".py",)

# Framework infrastructure directories — .md files here are reviewable
_FRAMEWORK_PREFIXES = (".claude/agents/", ".claude/commands/", ".claude/rules/")
_FRAMEWORK_EXTENSIONS = (".md", ".py")

# Gate config files are part of the reward function: an out-of-band edit to the
# debt baseline or the profile definitions must not commit without a /review
# (security F1 / R1.3a) — the human gate is enforced by the gate itself.
_GATE_CONFIG_FILES = ("config/gate_baseline.json", "config/gate_profiles.yaml")


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
        # Gate config files (baseline + profiles) are review-gated (F1/R1.3a)
        is_gate_config = f in _GATE_CONFIG_FILES
        if is_code or is_framework or is_gate_config:
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
        error_key="reviews",
        error_reason="code or gate-config changes staged but no review report found today",
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
        _emit_warn_line("build_status", "BUILD_STATUS.md not found - consider creating it")
        return True

    import time

    mtime = build_status.stat().st_mtime
    age_minutes = (time.time() - mtime) / 60
    if age_minutes > 60:
        _warn(
            f"BUILD_STATUS.md freshness (last updated {age_minutes:.0f} minutes ago"
            " — consider updating)"
        )
        _emit_warn_line(
            "build_status",
            f"BUILD_STATUS.md last updated {age_minutes:.0f} minutes ago - consider updating",
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
        _emit_warn_line(
            "subscription",
            f"{target} staged with a real fee - keep it gitignored",
        )
    return True


_PROMOTION_BACKLOG_THRESHOLD = 5  # Pending candidates that trigger a warning.
_PROMOTION_STALE_DAYS = 30  # Days without promotion/retro activity that triggers a warning.


def check_promotion_backlog() -> bool:
    """Advisory: warn when the /promote backlog is large or stale (ADR-0022, R3.2).

    Warns when pending promotion_candidates > _PROMOTION_BACKLOG_THRESHOLD OR the
    freshest promotion/retro signal is older than _PROMOTION_STALE_DAYS days.
    Degrades silently if the DB or tables are absent.
    Always returns True (advisory — never blocks the gate).
    """
    db_path = PROJECT_ROOT / "metrics" / "evaluation.db"
    if not db_path.exists():
        return True

    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM promotion_candidates WHERE promoted = 0"
            ).fetchone()[0]

            # Freshest signal: most recent promoted_at or reflection created_at.
            last_activity_row = conn.execute(
                """SELECT MAX(ts) FROM (
                       SELECT MAX(promoted_at) AS ts FROM promotion_candidates
                       UNION ALL
                       SELECT MAX(created_at) AS ts FROM reflections
                   )"""
            ).fetchone()
            last_activity = last_activity_row[0] if last_activity_row else None
        finally:
            conn.close()
    except Exception:
        return True

    # Count-trigger: backlog too large.
    if pending > _PROMOTION_BACKLOG_THRESHOLD:
        _warn(
            f"Promotion backlog: {pending} pending candidates (>{_PROMOTION_BACKLOG_THRESHOLD}) "
            "— consider running /promote to review pattern sightings"
        )
        _emit_warn_line(
            "promotion",
            f"{pending} pending promotion candidates - consider running /promote",
        )
        return True

    # Staleness-trigger: only warn when there is activity to go stale.
    if last_activity and pending > 0:
        from datetime import UTC, datetime

        try:
            last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            # Normalize naive datetimes (no TZ stored) to UTC to avoid TypeError.
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
        except (ValueError, AttributeError):
            return True
        age_days = (datetime.now(UTC) - last_dt).days
        if age_days > _PROMOTION_STALE_DAYS:
            _warn(
                f"Promotion backlog: {pending} pending candidate(s), "
                f"last activity {age_days} days ago (>{_PROMOTION_STALE_DAYS}) "
                "— consider running /promote"
            )
            _emit_warn_line(
                "promotion",
                f"{pending} pending candidate(s), last activity {age_days} days ago",
            )

    return True


_PROMOTION_BACKLOG_THRESHOLD = 5  # Pending candidates that trigger a warning.
_PROMOTION_STALE_DAYS = 30  # Days without promotion/retro activity that triggers a warning.


def check_promotion_backlog() -> bool:
    """Advisory: warn when the /promote backlog is large or stale (ADR-0022, R3.2).

    Warns when pending promotion_candidates > _PROMOTION_BACKLOG_THRESHOLD OR the
    freshest promotion/retro signal is older than _PROMOTION_STALE_DAYS days.
    Degrades silently if the DB or tables are absent.
    Always returns True (advisory — never blocks the gate).
    """
    db_path = PROJECT_ROOT / "metrics" / "evaluation.db"
    if not db_path.exists():
        return True

    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM promotion_candidates WHERE promoted = 0"
            ).fetchone()[0]

            # Freshest signal: most recent promoted_at or reflection created_at.
            last_activity_row = conn.execute(
                """SELECT MAX(ts) FROM (
                       SELECT MAX(promoted_at) AS ts FROM promotion_candidates
                       UNION ALL
                       SELECT MAX(created_at) AS ts FROM reflections
                   )"""
            ).fetchone()
            last_activity = last_activity_row[0] if last_activity_row else None
        finally:
            conn.close()
    except Exception:
        return True

    # Count-trigger: backlog too large.
    if pending > _PROMOTION_BACKLOG_THRESHOLD:
        _warn(
            f"Promotion backlog: {pending} pending candidates (>{_PROMOTION_BACKLOG_THRESHOLD}) "
            "— consider running /promote to review pattern sightings"
        )
        return True

    # Staleness-trigger: only warn when there is activity to go stale.
    if last_activity and pending > 0:
        from datetime import UTC, datetime

        try:
            last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            # Normalize naive datetimes (no TZ stored) to UTC to avoid TypeError.
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
        except (ValueError, AttributeError):
            return True
        age_days = (datetime.now(UTC) - last_dt).days
        if age_days > _PROMOTION_STALE_DAYS:
            _warn(
                f"Promotion backlog: {pending} pending candidate(s), "
                f"last activity {age_days} days ago (>{_PROMOTION_STALE_DAYS}) "
                "— consider running /promote"
            )

    return True


_CHECK_NAMES = ["format", "lint", "tests", "coverage", "adrs", "reviews", "regression"]
# The argparse ``--skip-*`` flag attribute for each check, in _CHECK_NAMES order.
# Derived from _CHECK_NAMES so a new check is added in exactly one place.
_SKIP_ATTRS = [f"skip_{name}" for name in _CHECK_NAMES]

# Checks recorded by NAME rather than by position. _CHECK_NAMES is walked
# positionally against the ``results`` list, so appending to it would silently
# re-map every existing check for any caller that passes a shorter list.
# Non-positional checks are counted in passed/total and logged inside
# ``checks``, but are passed to _build_outcome_record explicitly by status.
_NON_POSITIONAL_CHECKS = ["integrity"]


def _build_outcome_record(
    args: argparse.Namespace,
    results: list[bool],
    passed: int,
    total: int,
    *,
    profile: str = "python-fastapi",
    disabled: set[str] | None = None,
    baseline_debt_count: int = 0,
    integrity_status: str | None = None,
) -> dict:
    """Build the JSONL outcome record, recording skipped checks honestly.

    ``overall`` distinguishes three states so a run that skipped checks can
    never be read as a clean, complete pass (Principle #2 - capture is automatic,
    and an automatic record that overstates itself is worse than none):

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

    Profile-disabled stack checks are recorded as ``"disabled"`` — distinct from
    ``"skipped"`` (a ``--skip-*`` bypass): disabled-by-profile is by-design and
    does not demote ``overall`` to ``pass_with_skips``. The four
    SPEC-20260716-233400 fields (``profile``, ``baseline_debt_count``,
    ``rebaseline``, ``fast``) are additive only — telemetry consumers pin every
    pre-existing field (AC9).

    ``integrity_status`` (the Layer 1 integrity check) is passed by name instead
    of riding in ``results``. The walk above is positional, so adding an eighth
    entry to ``_CHECK_NAMES`` would re-map every check for callers passing a
    seven-element list. Defaulting to None means a legacy-shaped call produces
    a byte-identical record — the key is simply absent — which keeps the AC9
    top-level schema pin intact (the new key lives inside ``checks``, not at the
    top level).
    """
    from datetime import UTC, datetime

    disabled = disabled or set()
    check_results: dict[str, str] = {}
    idx = 0
    for name, skip_attr in zip(_CHECK_NAMES, _SKIP_ATTRS):
        if name in disabled:
            check_results[name] = "disabled"
        elif getattr(args, skip_attr, False):
            check_results[name] = "skipped"
        else:
            check_results[name] = "pass" if idx < len(results) and results[idx] else "fail"
            idx += 1

    if integrity_status is not None:
        check_results["integrity"] = integrity_status

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
        "profile": profile,
        "baseline_debt_count": baseline_debt_count,
        "rebaseline": bool(getattr(args, "rebaseline", False)),
        "fast": bool(getattr(args, "fast", False)),
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


def _log_outcome(
    args: argparse.Namespace,
    results: list[bool],
    passed: int,
    total: int,
    *,
    profile: str = "python-fastapi",
    disabled: set[str] | None = None,
    baseline_debt_count: int = 0,
    integrity_status: str | None = None,
) -> None:
    """Append a JSONL record of the quality gate outcome for trend analysis."""
    import json

    record = _build_outcome_record(
        args,
        results,
        passed,
        total,
        profile=profile,
        disabled=disabled,
        baseline_debt_count=baseline_debt_count,
        integrity_status=integrity_status,
    )

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
        "--skip-integrity",
        action="store_true",
        help="Skip the Layer 1 sealed-record integrity check",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help=(
            "Force a gate profile (python-fastapi / flutter-dart / markdown-corpus). "
            "Precedence: this flag > 'profile:' pin in config/gate_profiles.yaml > "
            "stack auto-detect. Unknown names fail closed."
        ),
    )
    parser.add_argument(
        "--rebaseline",
        action="store_true",
        help=(
            "PROPOSE a baseline: print the config/gate_baseline.json a developer would "
            "have to commit, and write nothing. Growing the baseline changes the gate's "
            "reward function, so it is a developer action - commit the file yourself; "
            "check_review_existence then requires a /review for it. This flag used to "
            "overwrite the file, guarded only by a sentence in this help text."
        ),
    )
    parser.add_argument(
        "--shrink-baseline",
        action="store_true",
        help="Ratchet the debt baseline down to the currently-remaining findings (never grows it)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help=(
            "Deterministic test sample for mid-build iteration. NOT a commit gate: "
            "coverage is skipped, the run is logged fast:true, and it never counts "
            "as commit-time verification."
        ),
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

    # --- Profile + baseline resolution (fail closed on config errors) ---
    try:
        profiles_config = _load_profiles_config()
        profile_name, profile = _resolve_profile(args.profile, profiles_config)
    except GateConfigError as e:
        _emit_error_line("profile", str(e))
        return 1

    baseline: set[Fingerprint] = set()
    baseline_supported = profile_name == _BASELINE_PROFILE
    if baseline_supported:
        try:
            baseline = _load_baseline()
        except GateConfigError as e:
            _emit_error_line("baseline", str(e))
            return 1
    elif GATE_BASELINE_FILE.exists() or args.rebaseline or args.shrink_baseline:
        # R1.0: never a crash, never a silent no-op — exactly one WARN line.
        reason = f"not supported for profile {profile_name} (python-fastapi only this build)"
        _warn(f"Baseline: {reason}")
        _emit_warn_line("baseline", reason)

    print(f"\n{BOLD}Quality Gate{RESET}")
    print("=" * 40)

    if args.fast:
        # F5 invariant: this script must NEVER write the pre-commit hook's
        # .claude/hooks/.state/commit-verified cache file (a --fast sampled run
        # must not stand in as commit-time verification). The gate satisfies
        # this by omission today — do not add an "auto-mark verified" feature
        # here without re-reading SPEC-20260716-233400 security F5.
        print(
            f"  {YELLOW}NOTICE{RESET}  --fast: deterministic test sample - NOT a commit "
            "gate; coverage is skipped; run the full gate before committing"
        )
        _emit_warn_line("fast", "sampled run - NOT a commit gate")
        args.skip_coverage = True

    checks_cfg = profile.get("checks") or {}

    def _check_cfg(key: str) -> dict:
        entry = checks_cfg.get(key)
        return entry if isinstance(entry, dict) else {}

    # Built-in (command-less) checks need src/ + tests/ with .py files; a profile
    # running only declared commands (flutter-dart) or no stack checks at all
    # (markdown-corpus) has no business failing on Python directory layout.
    needs_python_dirs = any(
        _check_cfg(k).get("enabled") and not _check_cfg(k).get("command") for k in _STACK_CHECKS
    )
    if needs_python_dirs:
        dir_errors = validate_directories()
        if dir_errors:
            for err in dir_errors:
                _fail(f"Directory validation ({err})")
            _emit_error_line("setup", "source or test directories missing or empty")
            print("=" * 40)
            print(
                f"{RED}{BOLD}Quality Gate: FAILED — "
                f"source or test directories missing or empty{RESET}\n"
            )
            _notify_outcome(0, 0, enabled=args.notify, setup_error=True)
            return 1

    # Baseline fingerprint collection: once, shared by the format/lint compare,
    # the burn-down ratchet, and --rebaseline (R1).
    current_fps: set[Fingerprint] | None = None
    if baseline_supported and (baseline or args.rebaseline):
        if args.fix:
            _run(["python", "-m", "ruff", "format", str(SRC_DIR), str(TESTS_DIR)])
            _run(["python", "-m", "ruff", "check", "--fix", str(SRC_DIR), str(TESTS_DIR)])
        current_fps = _collect_format_fingerprints() | _collect_lint_fingerprints()
        if args.rebaseline:
            _print_baseline_proposal(current_fps)

    results: list[bool] = []
    total = 0
    disabled: set[str] = set()

    # Check 1: Formatting
    fmt_cfg = _check_cfg("format")
    if not fmt_cfg.get("enabled"):
        disabled.add("format")
        _skip(f"Formatting (disabled by profile {profile_name})")
    elif args.skip_format:
        _skip("Formatting (ruff format)")
    else:
        total += 1
        if fmt_cfg.get("command"):
            results.append(check_profile_command("format", fmt_cfg["command"]))
        elif current_fps is not None:
            results.append(
                _check_against_baseline(
                    "format",
                    "Formatting (ruff format)",
                    {fp for fp in current_fps if fp[0] == "format"},
                    {fp for fp in baseline if fp[0] == "format"},
                    "run: python -m ruff format src/ tests/",
                )
            )
        else:
            results.append(check_formatting(fix=args.fix))

    # Check 2: Linting
    lint_cfg = _check_cfg("lint")
    if not lint_cfg.get("enabled"):
        disabled.add("lint")
        _skip(f"Linting (disabled by profile {profile_name})")
    elif args.skip_lint:
        _skip("Linting (ruff check)")
    else:
        total += 1
        if lint_cfg.get("command"):
            results.append(check_profile_command("lint", lint_cfg["command"]))
        elif current_fps is not None:
            results.append(
                _check_against_baseline(
                    "lint",
                    "Linting (ruff check)",
                    {fp for fp in current_fps if fp[0] == "lint"},
                    {fp for fp in baseline if fp[0] == "lint"},
                    "run: python -m ruff check src/ tests/",
                )
            )
        else:
            results.append(check_linting(fix=args.fix))

    # Baseline ratchet: shrink only, never grow (R1.3). Growing requires
    # --rebaseline (R1.4, developer-consent).
    baseline_debt_count = 0
    if current_fps is not None:
        baseline_debt_count = len(current_fps & baseline)
        resolved = _resolved_debt(baseline, current_fps)
        plan = _baseline_write_plan(
            rebaseline=args.rebaseline,
            fix=args.fix,
            shrink=args.shrink_baseline,
            baseline=baseline,
            current=current_fps,
        )
        if plan is not None:
            _write_baseline(plan)
            _warn(f"Baseline: shrunk by {len(resolved)} resolved item(s) (ratchet down)")
            _emit_warn_line("baseline", f"shrunk by {len(resolved)} resolved item(s)")
        elif resolved and not args.rebaseline:
            _warn(
                f"Baseline: {len(resolved)} item(s) resolved - run --shrink-baseline "
                "to ratchet the baseline down"
            )
            _emit_warn_line("baseline", f"{len(resolved)} item(s) resolved - shrink available")

    # Check 3: Tests
    tests_cfg = _check_cfg("tests")
    if not tests_cfg.get("enabled"):
        disabled.add("tests")
        _skip(f"Tests (disabled by profile {profile_name})")
    elif args.skip_tests:
        _skip("Tests (pytest)")
    else:
        total += 1
        if tests_cfg.get("command"):
            if args.fast:
                _emit_warn_line(
                    "fast", "not supported for profile-command tests; running full command"
                )
            results.append(check_profile_command("tests", tests_cfg["command"]))
        else:
            results.append(check_tests(fast_files=_select_fast_tests() if args.fast else None))

    # Check 4: Coverage
    cov_cfg = _check_cfg("coverage")
    if not cov_cfg.get("enabled"):
        disabled.add("coverage")
        _skip(f"Coverage (disabled by profile {profile_name})")
    elif args.skip_coverage:
        _skip("Coverage (>= 80%)")
    else:
        total += 1
        if cov_cfg.get("command"):
            results.append(check_profile_command("coverage", cov_cfg["command"]))
        else:
            results.append(check_coverage(fail_under=int(cov_cfg.get("fail_under", 80))))

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

    # Check 9: Layer 1 sealed-record integrity. Counted in passed/total like any
    # other blocking check, but tracked OUTSIDE ``results`` — that list is walked
    # positionally against _CHECK_NAMES (see _build_outcome_record).
    integrity_status: str | None
    integrity_passed = 0
    if args.skip_integrity:
        integrity_status = "skipped"
        _skip("Layer 1 integrity")
    else:
        integrity_ok = check_layer1_integrity()
        if integrity_ok is None:
            # No sealed records exist — nothing to verify. Not counted, so the
            # gate never scores a vacuous pass (see check_layer1_integrity).
            integrity_status = "not_applicable"
        else:
            total += 1
            integrity_status = "pass" if integrity_ok else "fail"
            integrity_passed = 1 if integrity_ok else 0

    # Check 8 (advisory): BUILD_STATUS.md freshness
    # This check always passes — it only warns. Not counted in pass/fail totals.
    check_build_status_freshness()

    # Advisory: warn if a real subscription fee (telemetry A3) is staged.
    # Always passes — only warns. Not counted in pass/fail totals.
    check_subscription_fee_not_staged()

    # Advisory: warn if the /promote backlog is large or stale (ADR-0022).
    # Always passes — only warns. Not counted in pass/fail totals.
    check_promotion_backlog()

    # Summary
    passed = sum(results) + integrity_passed
    print("=" * 40)

    # Log outcome to JSONL for trend analysis (additive fields — AC9)
    _log_outcome(
        args,
        results,
        passed,
        total,
        profile=profile_name,
        disabled=disabled,
        baseline_debt_count=baseline_debt_count,
        integrity_status=integrity_status,
    )

    # Best-effort push notification (opt-in via --notify; no-op otherwise)
    _notify_outcome(passed, total, enabled=args.notify)

    skipped = sum(1 for skip_attr in _SKIP_ATTRS if getattr(args, skip_attr, False)) + sum(
        1 for name in _NON_POSITIONAL_CHECKS if getattr(args, f"skip_{name}", False)
    )
    print(_format_summary(passed, total, skipped) + "\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
