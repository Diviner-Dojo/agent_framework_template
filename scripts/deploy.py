"""Deploy the Flutter app to a connected device or emulator and log timing metrics.

Wraps `flutter run -d <device> --release --dart-define=...` with:
- Full build+deploy timing
- JSONL outcome logging to metrics/deploy_log.jsonl
- Live output streaming (not captured silently)
- BUILD_STATUS.md default extraction for device ID and dart-define values
- Android emulator discovery, boot, and targeting

Usage:
    python scripts/deploy.py                          # defaults from BUILD_STATUS.md
    python scripts/deploy.py -d R5CR10LW2FE           # explicit device
    python scripts/deploy.py --debug                   # debug mode
    python scripts/deploy.py --install-only            # exit after install (don't stay attached)
    python scripts/deploy.py --dart-define KEY=VALUE   # explicit dart-define
    python scripts/deploy.py --emulator                # boot first available AVD, deploy in debug
    python scripts/deploy.py --emulator Pixel_7_API_36 # boot specific AVD

Exit code mirrors the flutter process exit code.

Note: NEVER uses `flutter install` — always `flutter run` per deploy safety rules.
See memory/lessons/deploy-safety.md.
"""

import argparse
import json
import os
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


def _find_android_sdk() -> Path | None:
    """Find the Android SDK path from local.properties, env var, or default location."""
    # Try android/local.properties
    local_props = PROJECT_ROOT / "android" / "local.properties"
    if local_props.exists():
        for line in local_props.read_text(encoding="utf-8").splitlines():
            if line.startswith("sdk.dir="):
                sdk_dir = line.split("=", 1)[1].replace("\\\\", "/").replace("\\", "/")
                p = Path(sdk_dir)
                if p.exists():
                    return p

    # Try ANDROID_HOME / ANDROID_SDK_ROOT env vars

    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(var)
        if val:
            p = Path(val)
            if p.exists():
                return p

    # Try common Windows default
    default = Path.home() / "AppData" / "Local" / "Android" / "Sdk"
    if default.exists():
        return default

    return None


def _find_emulator_exe() -> str | None:
    """Find the Android emulator executable."""
    sdk = _find_android_sdk()
    if sdk:
        for name in ("emulator.exe", "emulator"):
            exe = sdk / "emulator" / name
            if exe.exists():
                return str(exe)
    # Fallback: check PATH
    try:
        result = subprocess.run(
            ["emulator", "-list-avds"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return "emulator"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _find_adb_exe() -> str:
    """Find the adb executable."""
    sdk = _find_android_sdk()
    if sdk:
        for name in ("adb.exe", "adb"):
            exe = sdk / "platform-tools" / name
            if exe.exists():
                return str(exe)
    # Fallback: check PATH
    try:
        result = subprocess.run(
            ["adb", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return "adb"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print(f"  {RED}ERROR{RESET}  adb not found. Check Android SDK installation.")
    sys.exit(1)


def _list_available_emulators() -> list[str]:
    """List installed AVD names using `emulator -list-avds`."""
    emu = _find_emulator_exe()
    if not emu:
        return []
    try:
        result = subprocess.run(
            [emu, "-list-avds"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


def _get_running_emulators(adb: str) -> list[str]:
    """Return device IDs of currently running emulators (e.g. ['emulator-5554'])."""
    try:
        result = subprocess.run(
            [adb, "devices"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            devices = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
                    devices.append(parts[0])
            return devices
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


def _is_emulator(device_id: str) -> bool:
    """Check if a device ID refers to an emulator."""
    return device_id.startswith("emulator-")


def _boot_emulator(avd_name: str, timeout_seconds: int = 120) -> str:
    """Boot an Android emulator and wait for it to be ready.

    Args:
        avd_name: The AVD name to boot.
        timeout_seconds: Max seconds to wait for boot completion.

    Returns:
        The device ID (e.g. 'emulator-5554').

    Raises:
        SystemExit: If emulator cannot be found, booted, or times out.
    """
    emu = _find_emulator_exe()
    if not emu:
        print(f"  {RED}ERROR{RESET}  Android emulator executable not found.")
        print("         Check Android SDK installation and ensure emulator package is installed.")
        sys.exit(1)

    adb = _find_adb_exe()

    # Check if an emulator is already running
    running = _get_running_emulators(adb)
    if running:
        device_id = running[0]
        print(f"  {GREEN}Reusing{RESET} already-running emulator: {device_id}")
        return device_id

    # Launch emulator as background process
    print(f"  Booting emulator: {avd_name}...")
    try:
        process = subprocess.Popen(
            [emu, "-avd", avd_name, "-no-snapshot-load"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print(f"  {RED}ERROR{RESET}  Failed to launch emulator at: {emu}")
        sys.exit(1)

    # Wait for the emulator to appear in adb devices
    start = time.monotonic()
    device_id = None
    while time.monotonic() - start < timeout_seconds:
        time.sleep(3)
        running = _get_running_emulators(adb)
        if running:
            device_id = running[0]
            break

    if not device_id:
        elapsed = int(time.monotonic() - start)
        print(f"  {RED}ERROR{RESET}  Emulator did not appear in adb devices after {elapsed}s.")
        process.terminate()
        sys.exit(1)

    # Wait for sys.boot_completed
    print(f"  Emulator appeared as {device_id}. Waiting for boot to complete...")
    while time.monotonic() - start < timeout_seconds:
        try:
            result = subprocess.run(
                [adb, "-s", device_id, "shell", "getprop", "sys.boot_completed"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip() == "1":
                elapsed = int(time.monotonic() - start)
                print(f"  {GREEN}Emulator ready{RESET} ({elapsed}s)")
                return device_id
        except subprocess.TimeoutExpired:
            pass
        time.sleep(2)

    elapsed = int(time.monotonic() - start)
    print(f"  {RED}ERROR{RESET}  Emulator boot did not complete after {elapsed}s.")
    print("         The emulator process is still running — you may need to close it manually.")
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
    device_type: str = "physical",
    avd_name: str | None = None,
) -> None:
    """Append a JSONL record of the deploy outcome."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "outcome": outcome,
        "duration_seconds": round(duration_seconds, 1),
        "mode": mode,
        "device": device,
        "device_type": device_type,
        "exit_code": exit_code,
        "version": _read_pubspec_version(),
    }
    if avd_name:
        record["avd_name"] = avd_name

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
    parser.add_argument(
        "--emulator",
        nargs="?",
        const="",
        default=None,
        metavar="AVD_NAME",
        help="Boot and target an emulator. If AVD_NAME omitted, use first available AVD. "
        "Implies --debug unless --release is explicitly set.",
    )
    parser.add_argument(
        "--list-emulators",
        action="store_true",
        help="List available AVDs and running emulators, then exit.",
    )
    args = parser.parse_args()

    # --check-version: compare device vs pubspec and exit
    if args.check_version:
        return _check_version(args.device)

    # --list-emulators: show available AVDs and exit
    if args.list_emulators:
        avds = _list_available_emulators()
        adb = _find_adb_exe()
        running = _get_running_emulators(adb)
        print(f"{BOLD}Available AVDs:{RESET}")
        if avds:
            for avd in avds:
                print(f"  - {avd}")
        else:
            print("  (none found)")
        print(f"\n{BOLD}Running emulators:{RESET}")
        if running:
            for dev in running:
                print(f"  - {dev}")
        else:
            print("  (none running)")
        return 0

    # Track emulator state for logging
    emulator_avd_name: str | None = None

    # --emulator: discover/boot emulator and use it as target device
    if args.emulator is not None:
        avd_name = args.emulator  # empty string if no name given
        if not avd_name:
            # Pick first available AVD
            avds = _list_available_emulators()
            if not avds:
                print(f"  {RED}ERROR{RESET}  No AVDs found. Create one in Android Studio.")
                print("         Tools → Device Manager → Create Virtual Device")
                return 1
            avd_name = avds[0]
            print(f"  Auto-selected AVD: {avd_name}")

        emulator_avd_name = avd_name
        device_id = _boot_emulator(avd_name)
        args.device = device_id

        # --emulator implies --debug unless --release was explicitly passed
        if not any(a in sys.argv for a in ("--release",)):
            args.debug = True

    # Resolve mode
    mode = "debug" if args.debug else "release"

    # Read defaults from BUILD_STATUS.md
    defaults = _parse_build_status()

    # Resolve device ID
    device = args.device or defaults.get("device", "")
    if not device:
        print(f"  {RED}ERROR{RESET}  No device ID specified.")
        print(
            "         Use -d DEVICE_ID, --emulator, or add a Device Build Command to BUILD_STATUS.md"
        )
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

    device_type = "emulator" if _is_emulator(device) else "physical"
    device_label = f"{device} ({device_type})"
    if emulator_avd_name:
        device_label = f"{device} (emulator: {emulator_avd_name})"
    print(f"\n{BOLD}Deploying ({mode} mode) to {device_label}{RESET}")
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
    _log_outcome(
        outcome,
        duration,
        mode,
        device,
        exit_code,
        device_type="emulator" if _is_emulator(device) else "physical",
        avd_name=emulator_avd_name,
    )
    print(f"  Logged to {DEPLOY_LOG.relative_to(PROJECT_ROOT)}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
