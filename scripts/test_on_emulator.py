"""Run integration tests on an Android emulator.

Boots an emulator (or reuses a running one), deploys the app in debug mode,
runs integration tests, and reports results.

Usage:
    python scripts/test_on_emulator.py                     # auto-select AVD, run all tests
    python scripts/test_on_emulator.py --avd Pixel_7_API_36  # specific AVD
    python scripts/test_on_emulator.py --shutdown            # shut down emulator after tests
    python scripts/test_on_emulator.py --test-file smoke_test.dart  # specific test file

Exit codes:
    0 = all tests passed
    1 = tests failed
    2 = infrastructure error (emulator boot, deploy, etc.)
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Re-use deploy.py helpers
sys.path.insert(0, str(Path(__file__).parent))
from deploy import (
    _boot_emulator,
    _find_adb_exe,
    _find_flutter,
    _is_emulator,
    _list_available_emulators,
    _parse_build_status,
)

PROJECT_ROOT = Path(__file__).parent.parent
TEST_LOG = PROJECT_ROOT / "metrics" / "emulator_test_log.jsonl"

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _log_test_result(
    outcome: str,
    duration_seconds: float,
    device_id: str,
    avd_name: str | None,
    test_file: str,
    exit_code: int,
) -> None:
    """Append a JSONL record of the test run."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "outcome": outcome,
        "duration_seconds": round(duration_seconds, 1),
        "device": device_id,
        "device_type": "emulator" if _is_emulator(device_id) else "physical",
        "avd_name": avd_name,
        "test_file": test_file,
        "exit_code": exit_code,
    }
    TEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TEST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _clear_app_data(device_id: str) -> None:
    """Clear app data on the device for a clean test state."""
    adb = _find_adb_exe()
    pkg = "com.divinerdojo.agentic_journal"
    print(f"  Clearing app data for {pkg}...")
    try:
        subprocess.run(
            [adb, "-s", device_id, "shell", "pm", "clear", pkg],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(
            f"  {YELLOW}Warning{RESET}: Could not clear app data (app may not be installed yet)."
        )


def _run_integration_tests(
    flutter_cmd: str,
    device_id: str,
    test_file: str,
) -> int:
    """Run integration tests against a device and stream output live."""
    test_path = PROJECT_ROOT / "integration_test" / test_file
    if not test_path.exists():
        print(f"  {RED}ERROR{RESET}  Test file not found: {test_path}")
        return 2

    # Pass dart-defines from BUILD_STATUS.md for proper app configuration
    defaults = _parse_build_status()
    cmd = [
        flutter_cmd,
        "test",
        str(test_path),
        "-d",
        device_id,
    ]
    for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY"):
        if key in defaults:
            cmd.append(f"--dart-define={key}={defaults[key]}")

    print(f"\n{BOLD}Running integration tests{RESET}")
    print(f"  Device: {device_id}")
    print(f"  Test:   {test_file}")
    print(f"  {YELLOW}${RESET} {' '.join(cmd)}\n")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )
        for line in process.stdout:
            # Windows cp1252 stdout can't handle all UTF-8 chars (e.g. √)
            try:
                sys.stdout.write(line)
            except UnicodeEncodeError:
                sys.stdout.write(line.encode("ascii", errors="replace").decode("ascii"))
            sys.stdout.flush()
        return process.wait()
    except FileNotFoundError:
        print(f"  {RED}ERROR{RESET}  Failed to execute: {flutter_cmd}")
        return 2
    except KeyboardInterrupt:
        print(f"\n  {YELLOW}INTERRUPTED{RESET}  Tests cancelled by user.")
        process.terminate()
        return 130


def _shutdown_emulator(device_id: str) -> None:
    """Shut down an emulator via adb."""
    adb = _find_adb_exe()
    print(f"  Shutting down emulator {device_id}...")
    try:
        subprocess.run(
            [adb, "-s", device_id, "emu", "kill"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        print(f"  {GREEN}Emulator shut down.{RESET}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"  {YELLOW}Warning{RESET}: Could not shut down emulator cleanly.")


def main() -> int:
    """Boot emulator, run integration tests, report results."""
    parser = argparse.ArgumentParser(
        description="Run integration tests on Android emulator",
    )
    parser.add_argument(
        "--avd",
        help="AVD name to boot (default: first available)",
    )
    parser.add_argument(
        "--shutdown",
        action="store_true",
        help="Shut down emulator after tests complete",
    )
    parser.add_argument(
        "--test-file",
        default="smoke_test.dart",
        help="Integration test file to run (default: smoke_test.dart)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear app data before running tests (fresh install state)",
    )
    args = parser.parse_args()

    # Step 1: Resolve AVD
    avd_name = args.avd
    if not avd_name:
        avds = _list_available_emulators()
        if not avds:
            print(f"  {RED}ERROR{RESET}  No AVDs found. Create one in Android Studio.")
            return 2
        avd_name = avds[0]
        print(f"  Auto-selected AVD: {avd_name}")

    # Step 2: Boot emulator (or reuse running)
    print(f"\n{BOLD}Step 1: Boot emulator{RESET}")
    device_id = _boot_emulator(avd_name)

    # Step 3: Clean app data if requested
    if args.clean:
        print(f"\n{BOLD}Step 1b: Clear app data{RESET}")
        _clear_app_data(device_id)

    # Step 4: Find flutter
    flutter_cmd = _find_flutter()

    # Step 5: Run integration tests
    print(f"\n{BOLD}Step 2: Run integration tests{RESET}")
    start_time = time.monotonic()
    exit_code = _run_integration_tests(flutter_cmd, device_id, args.test_file)
    duration = time.monotonic() - start_time

    # Step 5: Report results
    outcome = "pass" if exit_code == 0 else "fail"
    minutes = int(duration // 60)
    seconds = duration % 60
    color = GREEN if outcome == "pass" else RED

    print(
        f"\n{BOLD}Test result: {color}{outcome}{RESET}{BOLD}  ({minutes}m {seconds:.1f}s){RESET}"
    )

    _log_test_result(
        outcome=outcome,
        duration_seconds=duration,
        device_id=device_id,
        avd_name=avd_name,
        test_file=args.test_file,
        exit_code=exit_code,
    )
    print(f"  Logged to {TEST_LOG.relative_to(PROJECT_ROOT)}")

    # Step 6: Optionally shut down
    if args.shutdown:
        _shutdown_emulator(device_id)

    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
