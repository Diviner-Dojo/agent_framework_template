---
plan_id: PLAN-20260301-emulator-integration
date: 2026-03-01
status: draft
priority: high
estimated_effort: 3-5 days
basis: framework-effectiveness-review-20260301, device-testing-pain-point
---

# Project Plan: Android Emulator Integration

## Problem

All testing currently requires a USB-connected physical device (Samsung Galaxy S21, device ID `R5CR10LW2FE`). This creates friction: the phone must be nearby, unlocked, connected, and developer-options-enabled for every iteration. ~90% of app features can run on an emulator, which would allow faster feedback loops and testing from any workstation.

## Goals

1. Create a ready-to-use Android emulator (AVD) configured for this project
2. Extend `deploy.py` to discover, boot, and target emulators automatically
3. Update the integration test workflow to run on emulator
4. Document which features require physical device vs emulator
5. Keep physical-device workflow unchanged (no regressions)

## Non-Goals

- CI/CD pipeline setup (deferred to framework improvement Phase 3)
- ARM emulator images (x86_64 is faster and sufficient for debug builds)
- Re-enabling llamadart on emulator (already disabled project-wide)

---

## Phase 1: AVD Creation and Manual Verification (Day 1)

### Task 1.1: Create the Project AVD

**Prerequisites:**
- Android Studio installed
- SDK location: `C:\Users\evans\AppData\Local\Android\Sdk` (already in `android/local.properties`)

**Steps:**

1. Open Android Studio → Tools → Device Manager → Create Virtual Device
2. Select hardware profile: **Pixel 7** (1080x2400, 6.3")
3. Download system image: **API 34 (Android 14) — Google Play Intel x86_64**
   - Google Play image required for Google Calendar OAuth testing
   - ~1.5 GB download
4. Configure AVD settings:

   | Setting | Value | Rationale |
   |---------|-------|-----------|
   | AVD Name | `AgenticJournal_Pixel7_API34` | Project-specific, descriptive |
   | RAM | 4096 MB | SQLite + audio + image processing headroom |
   | VM Heap | 512 MB | Video thumbnail and image handling |
   | Internal Storage | 4096 MB | STT model files (~50 MB) + app data |
   | SD Card | 512 MB | Optional, for large file testing |
   | Multi-Core CPU | 4 | FFI workloads, sherpa_onnx inference |
   | Graphics | Automatic (host GPU) | Smooth UI rendering |
   | Camera (front + back) | Emulated | Virtual camera for photo/video capture flow |

5. Launch and verify boot completes

### Task 1.2: Manual App Deploy and Smoke Test

```bash
# Verify emulator is visible
adb devices
# Expected: emulator-5554   device

# Deploy in debug mode
flutter run -d emulator-5554 --debug \
  --dart-define=SUPABASE_URL=https://oruastmawvtcpiyggrze.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ydWFzdG1hd3Z0Y3BpeWdncnplIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2MzEwMzYsImV4cCI6MjA4NzIwNzAzNn0.1bKaVE0RD0SZKBfnYA4DvlnkjllQ4KNq3voTRGOq35A
```

**Manual smoke test checklist:**

| Feature | Test Action | Expected |
|---------|------------|----------|
| App launch | Open app | No crash, onboarding or home screen |
| Journal CRUD | Create session, type entry, end | Session saved, appears in list |
| Claude AI | Send message in session | AI response received |
| TTS | Receive AI response with voice on | Audio plays through emulator speaker |
| Photo (gallery) | Attach photo from gallery | Sample image attaches |
| Photo (camera) | Capture photo via camera | Virtual camera image captured |
| Google Calendar | Settings → connect calendar | OAuth flow completes (see Task 1.3) |
| STT (Google) | Tap mic, speak into host mic | Transcription appears |
| STT (sherpa_onnx) | Switch to offline STT, speak | Transcription appears |
| Location | Start session, check metadata | Simulated GPS coordinates captured |
| Video capture | Record video | Virtual camera records (may crash — see Known Limitations) |
| Settings | Open settings screen | All cards render, version displays |

### Task 1.3: Google OAuth Setup for Emulator

The emulator uses a different debug keystore than the physical device. Google Calendar OAuth requires the emulator's SHA-1 registered in GCP.

```bash
# Get emulator debug keystore SHA-1
keytool -list -v ^
  -keystore "%USERPROFILE%\.android\debug.keystore" ^
  -alias androiddebugkey ^
  -storepass android -keypass android
```

If the SHA-1 differs from the one registered in GCP (`8B:32:96:6B:DD:A2:7E:A7:53:D3:31:65:43:C8:89:48:DC:E7:B9:41`):

1. Go to [GCP Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials?project=agenticjournal)
2. Create a new **Android OAuth client ID**
3. Package name: `com.divinerdojo.agentic_journal`
4. SHA-1: paste the emulator's SHA-1
5. Save — OAuth should work on emulator within a few minutes

**Note:** The same Web client ID (`774019106928-211ougkvc63dm0lbare5qbq0it12huk7`) is shared and does not need duplication.

### Task 1.4: Document Feature Compatibility Matrix

Update `BUILD_STATUS.md` Device Testing Results table to include emulator column:

| Feature | Physical Device | Emulator | Notes |
|---------|----------------|----------|-------|
| App launch | Working | Expected | — |
| Journal CRUD | Working | Expected | — |
| Claude AI | Needs test | Expected | Network only |
| TTS | Needs test | Expected | Built-in TTS engine |
| Photo capture | Working | Simulated | Virtual camera (checkerboard scene) |
| Video capture | Needs test | Limited | ffmpeg_kit may lack x86_64 libs |
| Google Calendar | Working | Expected | Needs emulator SHA-1 in GCP |
| STT (Google) | Needs test | Expected | Uses host microphone |
| STT (sherpa_onnx) | Needs test | Expected | x86_64 libs included |
| Location | Needs test | Simulated | Extended Controls → set coordinates |
| Local LLM | Disabled | Disabled | ARM-only binaries |
| Voice naturalness | Needs test | Expected | Timer/chime logic is platform-independent |

---

## Phase 2: deploy.py Emulator Support (Day 2–3)

### Task 2.1: Add Emulator Discovery

Add `_list_available_emulators()` function to `scripts/deploy.py`:

- Run `emulator -list-avds` to enumerate installed AVDs
- Run `adb devices` to find already-running emulators (prefix `emulator-`)
- Return list of `(avd_name, device_id_if_running)` tuples

### Task 2.2: Add Emulator Boot and Wait

Add `_boot_emulator(avd_name)` function:

- Launch `emulator -avd <name> -no-snapshot-load` as a background process
- Poll `adb -s emulator-5554 shell getprop sys.boot_completed` until it returns `1`
- Timeout after 120 seconds with clear error message
- Return the device ID (`emulator-5554`)

### Task 2.3: Add --emulator Flag

Extend `main()` argument parsing:

```
--emulator [AVD_NAME]    Boot and target an emulator.
                         If AVD_NAME omitted, use first available AVD.
                         Implies --debug unless --release explicitly set.
```

Behavior:
1. If `--emulator` given with a name → boot that specific AVD
2. If `--emulator` given without a name → list AVDs, pick first, boot it
3. If emulator is already running → reuse it (skip boot)
4. Default to `--debug` mode (release AOT doesn't target x86_64 by default)
5. All other flags (`--install-only`, `--dart-define`, `--check-version`) work identically

### Task 2.4: Add Device Type Detection

Add `_is_emulator(device_id)` helper:

- Check `device_id.startswith("emulator-")` (fast path)
- Or query `adb -s <id> shell getprop ro.build.characteristics` for `emulator`
- Used to auto-select `--debug` and log device type in `metrics/deploy_log.jsonl`

### Task 2.5: Update Deploy Log Schema

Add `device_type` field to JSONL records in `metrics/deploy_log.jsonl`:

```json
{
  "timestamp": "...",
  "device": "emulator-5554",
  "device_type": "emulator",
  "avd_name": "AgenticJournal_Pixel7_API34",
  "mode": "debug",
  "version": "0.15.1+3",
  "outcome": "success"
}
```

This enables future analysis of emulator vs physical device test frequency and outcomes.

---

## Phase 3: Integration Test on Emulator (Day 3–4)

### Task 3.1: Verify Existing Smoke Test on Emulator

Run the existing integration test against the emulator:

```bash
flutter test integration_test/smoke_test.dart -d emulator-5554
```

Document any failures specific to emulator environment (virtual camera, mic, GPS).

### Task 3.2: Add Emulator-Safe Guards to Integration Tests

For tests that touch hardware-dependent features, add platform/emulator detection:

```dart
bool get isEmulator => Platform.environment.containsKey('ANDROID_EMULATOR')
    || (Platform.isAndroid && /* check ro.build.characteristics */);
```

Skip or adapt tests that require:
- Real camera output (accept virtual camera as passing)
- Real microphone audio (accept silence/noise as non-crash)
- Real GPS (use simulated coordinates)

### Task 3.3: Create Emulator Test Runner Script

Add `scripts/test_on_emulator.py` (or extend deploy.py):

```bash
python scripts/test_on_emulator.py [--avd AgenticJournal_Pixel7_API34]
```

Behavior:
1. Boot emulator (or reuse running)
2. Run `flutter test integration_test/ -d emulator-5554`
3. Capture results
4. Optionally shut down emulator when done (`--shutdown`)

### Task 3.4: Add deploy.py --test Flag

Extend deploy.py to support running integration tests after deployment:

```bash
python scripts/deploy.py --emulator --test
```

After install completes, automatically runs `flutter test integration_test/ -d <device>`.

---

## Phase 4: Workflow Documentation and BUILD_STATUS Updates (Day 4–5)

### Task 4.1: Update BUILD_STATUS.md

Add emulator build command alongside physical device command:

```markdown
## Device Build Command

**Physical device:**
python scripts/deploy.py --install-only

**Emulator:**
python scripts/deploy.py --emulator --install-only

**Emulator + integration tests:**
python scripts/deploy.py --emulator --test
```

### Task 4.2: Add Emulator Section to BUILD_STATUS.md

New section tracking emulator state:

```markdown
## Emulator Config

| Setting | Value |
|---------|-------|
| AVD Name | AgenticJournal_Pixel7_API34 |
| Image | API 34, Google Play, x86_64 |
| RAM | 4096 MB |
| Emulator OAuth SHA-1 | (fill after Task 1.3) |
```

### Task 4.3: Update CLAUDE.md Developer Workflow

Add emulator as a first-class testing target in the Directory Layout or Quality Gate sections, noting that `deploy.py --emulator` is the standard command for iterative testing.

### Task 4.4: Update Ship Workflow Guidance

In `.claude/commands/ship.md`, add a pre-ship step recommending emulator smoke test:

> Before Step 1 (Analyze Changes): If the change affects UI or device features, run `python scripts/deploy.py --emulator --test` to verify on emulator. Physical device testing is required only for video capture, audio quality, and performance profiling.

---

## Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| **ffmpeg_kit x86_64 support** | Video metadata stripping may crash on emulator | Test video on physical device; guard with try/catch in app |
| **llamadart x86_64 binaries** | Local LLM inference won't work | Already disabled project-wide; non-issue |
| **Release mode on x86_64** | Flutter AOT only targets arm64 by default | Use `--debug` on emulator (deploy.py defaults to this) |
| **Virtual camera** | Checkerboard scene, not realistic images | Sufficient for capture flow testing, not photo quality |
| **Host microphone latency** | STT may have higher latency than on-device | Acceptable for functional testing |
| **Emulator startup time** | Cold boot ~30-60s | Use snapshot save/restore; `--no-snapshot-load` for clean state |
| **Disk space** | ~6-10 GB for emulator image + system | Verify C: drive has space before setup |
| **Hyper-V / Docker conflict** | HAXM may conflict with Hyper-V/WSL2 | Use WHPX backend (recent emulators handle automatically) |

---

## Verification Criteria

- [ ] AVD created and boots successfully
- [ ] App deploys to emulator with `deploy.py --emulator`
- [ ] Manual smoke test passes for all non-video features
- [ ] Google Calendar OAuth works after emulator SHA-1 registration
- [ ] `deploy.py --emulator` auto-boots, auto-selects, defaults to debug
- [ ] `deploy.py --emulator --test` runs integration tests end-to-end
- [ ] Integration test passes on emulator (with emulator-safe guards)
- [ ] BUILD_STATUS.md updated with emulator config and dual-target commands
- [ ] Deploy log captures device_type field for emulator runs
- [ ] Video capture failure on emulator is gracefully handled (no crash)

---

## Files Modified

| File | Change |
|------|--------|
| `scripts/deploy.py` | Add `--emulator`, `--test` flags, emulator discovery/boot/wait functions, device type detection |
| `BUILD_STATUS.md` | Add emulator config section, dual build commands, extended device testing table |
| `CLAUDE.md` | Add emulator as testing target in developer workflow |
| `integration_test/smoke_test.dart` | Add emulator-safe guards for hardware-dependent tests |
| `.claude/commands/ship.md` | Add emulator smoke test as pre-ship recommendation |
| `metrics/deploy_log.jsonl` | Extended schema with `device_type` and `avd_name` fields |
| `android/app/build.gradle.kts` | No changes needed (debug mode handles x86_64 automatically) |

## Files Created

| File | Purpose |
|------|---------|
| `scripts/test_on_emulator.py` | Standalone emulator test runner (optional — may fold into deploy.py) |
