---
spec_id: SPEC-20260305-080259
title: "Voice Stack Stabilization + Agentic Capability Protection Protocol"
status: draft
risk_level: high
discussion_id: DISC-20260305-080259-voice-regression-postmortem-and-capability-protection
---

## Goal

Two goals with the same root cause:

1. **Immediate stabilization**: Restore the voice stack to the last known-working
   baseline (speech_to_text + sherpa_onnx) on physical device and emulator, after
   the Deepgram integration broke all three STT engines through a microphone resource
   leak triggered by Deepgram's persistent WebSocket 401 failures.

2. **Framework enhancement**: Introduce a Capability Protection Protocol (CPP) into
   the agentic development framework — a set of conventions, checks, and workflow
   gates that prevent experimental capabilities from silently breaking proven ones,
   without requiring separate environments.

---

## Post-Mortem: How Deepgram Broke the Working Voice Stack

### Timeline of the Regression

| Commit | What changed | Impact |
|--------|-------------|--------|
| `52828fa` (PR #52, 2026-03-01) | 8-phase voice integration test added; voice confirmed working on emulator with `speechToText` default | **Last known-working baseline** |
| `87429d2` (PR #61) | STT pauseFor 5s→2s (ADHD P0) | Voice still working |
| `328ec44` (PR #72, 2026-03-03) | DeepgramSttService added; **default changed from `speechToText` to `deepgram`** | **Regression introduced** |
| All subsequent PRs | Features built on top of broken voice stack | Problem masked |
| `9a19f69` (2026-03-04) | voiceRecognition audio source + 500ms ttsReleaseDelay | Debugging deepgram, still broken |
| `e1ad873` (2026-03-05) | Microphone leak fixed in onDone + dispose() | All-STT-blocked symptom fixed |

### The Two Compounding Failures

**Failure 1: Deepgram WebSocket 401 (unreported until device testing)**

Commit `328ec44` introduced `DeepgramSttService` and immediately set it as the
production default. The Deepgram proxy had never been tested end-to-end on a
physical device before becoming the default. The WebSocket 401 (auth failure)
meant every voice session immediately closed the Deepgram connection.

This was not caught because:
- The integration test (`voice_mode_test.dart`) does NOT test real STT transcription
  (by design — emulators have no mic). It tests the UI/state machine only.
- The review (REV-20260303-220000) approved the code without device STT verification.
- No definition existed in the framework of "capability must be device-tested before
  becoming default."

**Failure 2: Microphone leak in onDone (latent bug exposed by Failure 1)**

`DeepgramSttService._connectAndCapture()` starts the `AudioRecorder` BEFORE the
Deepgram WebSocket connection is established. When the WebSocket closes with 401:
- `onDone` fires, sets `_isListening = false`
- `AudioRecorder` is NOT stopped (no cleanup in `onDone`)
- `stopListening()` guards on `if (!_isListening) return` → returns early, recorder
  stays running, holding the OS microphone
- All subsequent STT engines (speech_to_text, sherpa_onnx) fail to acquire the mic

This latent bug existed in both `DeepgramSttService` and `SherpaOnnxSpeechRecognitionService`.
It was harmless in normal operation (where the socket closes cleanly after stopListening()
is called first). It became catastrophic when combined with Failure 1.

The fix (commit `e1ad873`) added unconditional recorder cleanup in `onDone` and
`dispose()` for both services. But the root question is: why did the framework allow
this bug to exist undetected?

### The Architectural Flaw: Resource Lifecycle Not Enforced by the Interface

`SpeechRecognitionService` defines a `stopListening()` / `dispose()` lifecycle
contract, but the contract does NOT guarantee OS resource release under abnormal
termination. Implementations could (and did) leak the microphone if the internal
`_isListening` flag was set false by an out-of-band event before `stopListening()`
was called.

The interface makes correct teardown the programmer's responsibility but provides
no guard against incorrect teardown under error conditions.

### The Methodological Flaw: No "Default Gate" for Capabilities

The framework has gates for many things (reviews, quality gate, education gate) but
had NO gate specifically for: **"this new capability is about to become the default
for something that was previously working."**

When `SttEngineNotifier.build()` changed from returning `SttEngine.speechToText` to
returning `SttEngine.deepgram`, it crossed from "adding an option" to "replacing the
working default." The framework treated these identically. They are not the same risk.

---

## Requirements

### Part A: Immediate Stabilization (implement this plan)

- **A1**: Change the default STT engine back to `speechToText` in `voice_providers.dart`.
  Deepgram remains available as an opt-in setting for future testing.
- **A2**: Verify the voice stack (speech_to_text engine) works end-to-end on the emulator
  using `voice_mode_test.dart`.
- **A3**: Update `SttEngineNotifier` doc comment to clarify Deepgram is EXPERIMENTAL,
  not the production default.
- **A4**: Suppress the Deepgram STT option in settings until the proxy 401 is resolved,
  OR clearly label it as "Experimental (may not work)".

### Part B: Architectural Fix — Resource Lifecycle Invariant

- **B1**: Both services now have the fix (commit `e1ad873`). This requirement is
  documenting the pattern as a rule.
- **B2**: Add a `CAPABILITY_STATUS.md` file at project root tracking capability
  verification status (PROVEN / EXPERIMENTAL / BROKEN).
- **B3**: Add a regression test that specifically verifies the microphone is NOT held
  after a simulated connection failure in `DeepgramSttService`. Use `@visibleForTesting`
  hooks to inject a socket close event.

### Part C: Framework Capability Protection Protocol (CPP)

The protocol that must be enforced by the framework itself — not by environment
separation, not by individual programmer discipline.

- **C1 — Capability Registry** (`CAPABILITY_STATUS.md`):
  A structured markdown table that the framework reads. Format:
  ```
  | Capability | Status | Device-tested? | Verified on | Notes |
  |------------|--------|----------------|-------------|-------|
  | STT: speech_to_text | PROVEN | Yes | SM_G998U1, 2026-03-01 | via PR #52 |
  | STT: deepgram | EXPERIMENTAL | No | — | WebSocket 401 unresolved |
  | STT: sherpa_onnx | EXPERIMENTAL | No | — | Model download required |
  ```

- **C2 — Quality Gate: Default-Change Warning**:
  Add a check to `scripts/quality_gate.py` that detects when a provider's
  default value changes (via git diff). If the new default is listed as
  EXPERIMENTAL in `CAPABILITY_STATUS.md`, emit a **blocking warning** requiring
  a `# CAPABILITY-GATE: approved by <name> <reason>` comment in the commit
  message or an explicit `--approve-capability-change` flag.

- **C3 — Review Gate: Default-Change Trigger**:
  Any PR that changes a default value in a Riverpod provider (detected via
  regex in the diff) automatically adds `independent-perspective` to the
  specialist panel. The independent perspective agent is specifically asked
  to evaluate: "Does this change replace a proven capability with an unproven
  one? What is the rollback plan?"

- **C4 — BUILD_STATUS.md: Proven Baseline Section**:
  Add a `## Proven Baseline` section to BUILD_STATUS.md listing the last
  device-verified state of each critical capability (STT, TTS, camera, calendar).
  The `/ship` command reads this section and warns if the current code would
  change a PROVEN capability to an EXPERIMENTAL one.

- **C5 — The "Experimental-First" Convention (codified as a rule)**:
  New capabilities MUST be added as alternatives with the existing proven
  capability remaining default. The rule: "You cannot change a provider default
  in the same PR that introduces the new implementation." Two-PR pattern:
  - PR N: Add implementation (tests, service, provider case). Default unchanged.
  - PR N+1: After explicit device verification note in BUILD_STATUS.md: change default.

---

## Acceptance Criteria

### Part A (Stabilization)
- [ ] A1: `voice_providers.dart` default STT engine is `speechToText`
- [ ] A2: `voice_mode_test.dart` passes on emulator
- [ ] A3: Doc comment updated, Deepgram clearly labeled EXPERIMENTAL in settings UI
- [ ] A4: `CAPABILITY_STATUS.md` exists with current verified state

### Part B (Architectural Fix)
- [ ] B1: Both STT services have the recorder cleanup fix (done in e1ad873)
- [ ] B2: `CAPABILITY_STATUS.md` created and populated
- [ ] B3: Regression test for mic release after connection failure

### Part C (Framework CPP)
- [ ] C1: `CAPABILITY_STATUS.md` format defined and populated
- [ ] C2: quality_gate.py default-change check implemented
- [ ] C3: Review workflow (`.claude/commands/review.md`) updated with default-change trigger
- [ ] C4: BUILD_STATUS.md `## Proven Baseline` section added
- [ ] C5: `docs/conventions/experimental-first.md` codifying the two-PR pattern
- [ ] C5: `.claude/rules/capability_protection.md` enforcing the convention

---

## Risk Assessment

- **Regression risk from A1**: Very low. Reverting to the previously proven default.
  SharedPreferences persists the user's current setting, so the device that currently
  has `deepgram` stored will keep using deepgram until the user changes it — which is
  acceptable since the microphone leak is now fixed.
- **Risk of C2 implementation**: Medium. `quality_gate.py` is a shared script;
  changes to it affect all commits. Must be implemented carefully to avoid false
  positives.
- **Framework complexity risk**: The CPP adds overhead. The design should be
  lightweight — a markdown file and a git-diff grep, not a database.

---

## Affected Components

- `lib/providers/voice_providers.dart` — A1 (default change), A3 (doc comment)
- `lib/ui/screens/settings_screen.dart` — A4 (experimental label)
- `CAPABILITY_STATUS.md` — C1, B2 (new file)
- `scripts/quality_gate.py` — C2 (new check)
- `.claude/commands/review.md` — C3 (default-change trigger)
- `BUILD_STATUS.md` — C4 (new section)
- `.claude/rules/capability_protection.md` — C5 (new rule)

---

## Dependencies

- Microphone leak fix (e1ad873) — already merged. Required before A1.
- `integration_test/voice_mode_test.dart` — must pass after A1 to confirm stabilization.
