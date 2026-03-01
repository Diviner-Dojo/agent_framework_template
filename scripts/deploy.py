"""Deploy the Flutter app to a connected device and log timing metrics.

Wraps `flutter run -d <device> --release --dart-define=...` with:
- Full build+deploy timing
- JSONL outcome logging to metrics/deploy_log.jsonl
- Live output streaming (not captured silently)
- BUILD_STATUS.md default extraction for device ID and dart-define values

Usage:
    python scripts/deploy.py                          # defaults from BUILD_STATUS.md
    python scripts/deploy.py -d R5CR10LW2FE           # explicit device
    python scripts/deploy.py --debug                   # debug mode
    python scripts/deploy.py --install-only            # exit after install (don't stay attached)
    python scripts/deploy.py --dart-define KEY=VALUE   # explicit dart-define

Exit code mirrors the flutter process exit code.

Note: NEVER uses `flutter install` — always `flutter run` per deploy safety rules.
See memory/lessons/deploy-safety.md.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BUILD_STATUS = PROJECT_ROOT / "BUILD_STATUS.md"
PUBSPEC = PROJECT_ROOT / "pubspec.yaml"
DEPLOY_LOG = PROJECT_ROOT / "metrics" / "deploy_log.jsonl"

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _find_flutter() -> str:
    """Find the flutter executable, checking PATH and common install locations."""
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

    common_path = Path("C:/src/flutter/bin")
    if common_path.exists():
        flutter_bat = common_path / "flutter.bat"
        if flutter_bat.exists():
            return str(flutter_bat)

    print(f"  {RED}ERROR{RESET}  Flutter SDK not found on PATH.")
    print('         Add Flutter to PATH: export PATH="$PATH:/c/src/flutter/bin"')
    sys.exit(1)


def _parse_build_status() -> dict[str, str]:
    """Extract device ID and dart-define values from BUILD_STATUS.md.

    Looks for the 'Device Build Command' section and parses the flutter run
    command within it. Returns a dict with keys: device, SUPABASE_URL,
    SUPABASE_ANON_KEY (any or all may be absent).
    """
    if not BUILD_STATUS.exists():
        return {}

    content = BUILD_STATUS.read_text(encoding="utf-8")
    result: dict[str, str] = {}

    # Extract device ID: `-d <DEVICE_ID>`
    device_match = re.search(r"flutter\s+run\s+-d\s+(\S+)", content)
    if device_match:
        result["device"] = device_match.group(1)

    # Extract dart-define values
    for define_match in re.finditer(r"--dart-define=(\w+)=(\S+)", content):
        key, value = define_match.group(1), define_match.group(2)
        result[key] = value

    return result


def _read_pubspec_version() -> str:
    """Read the version string from pubspec.yaml (e.g. '0.14.0+1')."""
    content = PUBSPEC.read_text(encoding="utf-8")
    match = re.search(r"^version:\s*(\S+)", content, re.MULTILINE)
    return match.group(1) if match else "unknown"


def _check_version(device_arg: str | None) -> int:
    """Compare the installed app version on device to the pubspec version."""
    defaults = _parse_build_status()
    device = device_arg or defaults.get("device", "")
    if not device:
        print(f"  {RED}ERROR{RESET}  No device ID specified.")
        print("         Use -d DEVICE_ID or add a Device Build Command to BUILD_STATUS.md")
        return 1

    pubspec_version = _read_pubspec_version()
    # Split semver from build number: "0.14.0+1" → ("0.14.0", "1")
    if "+" in pubspec_version:
        sem_ver, build_num = pubspec_version.split("+", 1)
    else:
        sem_ver, build_num = pubspec_version, "?"

    print(f"{BOLD}Version check{RESET}")
    print(f"  Pubspec:  {pubspec_version}  (version={sem_ver}, build={build_num})")

    # Query the device via adb
    try:
        result = subprocess.run(
            [
                "adb",
                "-s",
                device,
                "shell",
                "dumpsys",
                "package",
                "com.divinerdojo.agentic_journal",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        print(f"  {RED}ERROR{RESET}  adb not found on PATH.")
        return 1
    except subprocess.TimeoutExpired:
        print(f"  {RED}ERROR{RESET}  adb timed out querying device {device}.")
        return 1

    if result.returncode != 0:
        print(f"  {RED}ERROR{RESET}  adb query failed (exit {result.returncode}).")
        return 1

    # Parse versionName and versionCode from dumpsys output
    version_name = None
    version_code = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("versionName="):
            version_name = stripped.split("=", 1)[1].split()[0]
        elif stripped.startswith("versionCode="):
            version_code = stripped.split("=", 1)[1].split()[0]

    if version_name is None:
        print(f"  {YELLOW}NOT INSTALLED{RESET}  App not found on device {device}.")
        return 0

    print(
        f"  Device:   {version_name}+{version_code or '?'}  "
        f"(versionName={version_name}, versionCode={version_code or '?'})"
    )

    # Compare
    if version_name == sem_ver and str(version_code) == str(build_num):
        print(f"\n  {GREEN}MATCH{RESET}  Device is running the pubspec version.")
    else:
        print(f"\n  {YELLOW}MISMATCH{RESET}  Device version differs from pubspec.")

    return 0


def _log_outcome(
    outcome: str,
    duration_seconds: float,
    mode: str,
    device: str,
    exit_code: int,
) -> None:
    """Append a JSONL record of the deploy outcome."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "outcome": outcome,
        "duration_seconds": round(duration_seconds, 1),
        "mode": mode,
        "device": device,
        "exit_code": exit_code,
        "version": _read_pubspec_version(),
    }

    DEPLOY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(DEPLOY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main() -> int:
    """Build and deploy the app, timing the full cycle."""
    parser = argparse.ArgumentParser(
        description="Deploy Flutter app to device with timing metrics",
    )
    parser.add_argument(
        "-d",
        "--device",
        help="Target device ID (default: read from BUILD_STATUS.md)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--release",
        action="store_true",
        default=True,
        help="Release mode (default)",
    )
    mode_group.add_argument(
        "--debug",
        action="store_true",
        help="Debug mode override",
    )
    parser.add_argument(
        "--install-only",
        action="store_true",
        help="Exit after install completes (don't stay attached for logs)",
    )
    parser.add_argument(
        "--dart-define",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Pass-through dart-define flags (repeatable)",
    )
    parser.add_argument(
        "--check-version",
        action="store_true",
        help="Compare installed app version on device to pubspec version, then exit",
    )
    args = parser.parse_args()

    # --check-version: compare device vs pubspec and exit
    if args.check_version:
        return _check_version(args.device)

    # Resolve mode
    mode = "debug" if args.debug else "release"

    # Read defaults from BUILD_STATUS.md
    defaults = _parse_build_status()

    # Resolve device ID
    device = args.device or defaults.get("device", "")
    if not device:
        print(f"  {RED}ERROR{RESET}  No device ID specified.")
        print("         Use -d DEVICE_ID or add a Device Build Command to BUILD_STATUS.md")
        return 1

    # Resolve dart-define values
    dart_defines = list(args.dart_define)
    if not dart_defines:
        # Pull from BUILD_STATUS.md defaults
        for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY"):
            if key in defaults:
                dart_defines.append(f"{key}={defaults[key]}")

    # Find flutter
    flutter_cmd = _find_flutter()

    # Build the command — NEVER `flutter install`, always `flutter run`
    cmd = [flutter_cmd, "run", "-d", device]
    if mode == "release":
        cmd.append("--release")
    for define in dart_defines:
        cmd.append(f"--dart-define={define}")

    # Print the command (mask dart-define values for safety)
    display_cmd = [flutter_cmd, "run", "-d", device]
    if mode == "release":
        display_cmd.append("--release")
    for define in dart_defines:
        key = define.split("=", 1)[0]
        display_cmd.append(f"--dart-define={key}=<redacted>")

    print(f"\n{BOLD}Deploying ({mode} mode) to {device}{RESET}")
    print(f"  {YELLOW}${RESET} {' '.join(display_cmd)}\n")

    # Marker that flutter prints once the app is installed and running
    _INSTALL_DONE_MARKER = "Flutter run key commands"

    # Run with live output streaming
    start_time = time.monotonic()

    if args.install_only:
        # Pipe stdout so we can watch for the install-complete marker,
        # forwarding each line live to the terminal.
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT),
                text=True,
                bufsize=1,
            )
            exit_code = None
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                if _INSTALL_DONE_MARKER in line:
                    print(f"\n  {GREEN}Install complete.{RESET} Detaching from device.")
                    process.terminate()
                    process.wait(timeout=10)
                    exit_code = 0
                    break
            if exit_code is None:
                # Process ended before we saw the marker — treat as failure
                exit_code = process.wait()
        except FileNotFoundError:
            print(f"\n  {RED}ERROR{RESET}  Failed to execute: {flutter_cmd}")
            exit_code = 127
        except KeyboardInterrupt:
            print(f"\n  {YELLOW}INTERRUPTED{RESET}  Deploy cancelled by user.")
            process.terminate()
            exit_code = 130
    else:
        # Normal mode: direct passthrough, stays attached until user quits
        try:
            process = subprocess.Popen(
                cmd,
                stdout=sys.stdout,
                stderr=sys.stderr,
                cwd=str(PROJECT_ROOT),
            )
            exit_code = process.wait()
        except FileNotFoundError:
            print(f"\n  {RED}ERROR{RESET}  Failed to execute: {flutter_cmd}")
            exit_code = 127
        except KeyboardInterrupt:
            print(f"\n  {YELLOW}INTERRUPTED{RESET}  Deploy cancelled by user.")
            process.terminate()
            exit_code = 130

    duration = time.monotonic() - start_time
    outcome = "success" if exit_code == 0 else "failure"

    # Summary
    minutes = int(duration // 60)
    seconds = duration % 60
    color = GREEN if outcome == "success" else RED
    print(
        f"\n{BOLD}Deploy {color}{outcome}{RESET}{BOLD}  "
        f"({minutes}m {seconds:.1f}s, exit code {exit_code}){RESET}"
    )

    # Log to JSONL
    _log_outcome(outcome, duration, mode, device, exit_code)
    print(f"  Logged to {DEPLOY_LOG.relative_to(PROJECT_ROOT)}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
