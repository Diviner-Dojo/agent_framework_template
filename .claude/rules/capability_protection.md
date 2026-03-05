# Capability Protection Protocol (CPP)

> Enforces the Capability Protection Protocol defined in ADR-0035 and SPEC-20260305-080259.
> Root cause: Deepgram integration changed the production STT default in the same PR that
> introduced the unproven implementation, breaking all three STT engines via a microphone
> resource leak triggered by WebSocket 401 failures.

## The Core Rule

**You cannot change a provider default in the same PR that introduces the new implementation.**

This is the Two-PR Pattern. It is not negotiable.

### Two-PR Pattern

- **PR N**: Add the new implementation (service class, tests, provider case). The existing proven default MUST remain unchanged. Add the capability to `CAPABILITY_STATUS.md` as `EXPERIMENTAL`.
- **PR N+1**: After confirmed device testing, change the default. Update `CAPABILITY_STATUS.md` to `PROVEN`. Reference the device test (device model, OS version, date).

### Why This Rule Exists

In PR #72 (commit 328ec44), `DeepgramSttService` was introduced AND set as the production default in the same commit. Deepgram was never device-tested before becoming the default. Its WebSocket 401 failures triggered a latent microphone resource leak that blocked ALL three STT engines from acquiring the OS microphone. The result: voice mode completely broken for multiple sessions, visible only during physical device testing.

The Two-PR Pattern creates a mandatory pause between "I built this" and "this is now the default." That pause is where device testing, review, and CAPABILITY_STATUS.md update happen.

## What Counts as a "Default Change"

A default change is ANY change that promotes a capability to the primary user experience path:

1. **Provider default value**: Changing the return value of a `Notifier.build()` method when no stored preference exists (the zero-preference path)
2. **Settings UI label**: Changing a dropdown item from `(Experimental)` or `(Fallback)` to `(Default)` or `(Recommended)`
3. **Settings UI ordering**: Moving an EXPERIMENTAL capability to the first position in a list
4. **Feature flag default**: Enabling a feature flag by default for all users

## What the Quality Gate Checks (C2)

The quality gate detects when a Riverpod provider default changes via git diff. Specifically, it checks for changes to lines matching:
- `return SttEngine.*` (in files matching `*_providers.dart`)
- `return TtsEngine.*` (in files matching `*_providers.dart`)

If the new default is listed as `EXPERIMENTAL` or `BROKEN` in `CAPABILITY_STATUS.md`, the quality gate emits a **warning** requiring:

```
# CAPABILITY-GATE: approved by <name>
# Reason: <why this EXPERIMENTAL capability is becoming the default>
# Device test: <date, device, result>
```

Note: The quality gate check is a WARNING (not a hard BLOCK) because the Two-PR convention is the primary enforcement mechanism. C2 is a safety net.

## What the Review Gate Checks (C3)

Any PR that changes a default value in a Riverpod provider (detected via regex in the diff) automatically adds `independent-perspective` to the specialist panel. The independent-perspective agent is specifically asked:

> "Does this change replace a proven capability with an unproven one? What is the rollback plan if the new default fails on physical device?"

## CAPABILITY_STATUS.md — The Registry

`CAPABILITY_STATUS.md` at the project root is the authoritative capability registry.

- `PROVEN`: Device-verified, working end-to-end on physical hardware
- `EXPERIMENTAL`: Implemented but not device-tested, or device-tested with known failures
- `BROKEN`: Known non-functional; awaiting fix

**Staleness**: If a PROVEN capability's `Last verified` date is older than 30 days, treat it as UNCONFIRMED until re-tested. The quality gate emits a warning when this threshold is crossed.

**Update protocol**: When you device-test a capability, immediately update `CAPABILITY_STATUS.md` with the result, device, and date. Do not rely on memory across sessions — the regression ledger shows how quickly the verified state can be assumed without confirmation.

## The OS Resource Lifecycle Invariant

Any service implementing `SpeechRecognitionService` (or any future OS-hardware interface) MUST:

1. **Release hardware unconditionally in `dispose()`**: Do not gate cleanup on `isListening` or any internal state flag. `dispose()` must be safe to call in any state.

2. **Release hardware in `onDone`/`onError` callbacks**: Any callback that fires when an underlying stream (audio stream, WebSocket stream) closes must release the OS resource unconditionally — before modifying any state flags. The state flag (`_isListening`) may already be false when the callback fires, and subsequent cleanup guards on that flag will be skipped.

   Pattern:
   ```dart
   onDone: () {
     _audioSubscription?.cancel();
     _audioSubscription = null;
     _recorder?.stop().then((_) => _recorder?.dispose()).catchError((_) {});
     _recorder = null;
     // Now safe to modify flags:
     _isListening = false;
   },
   ```

3. **Do not start OS resources before establishing the connection they depend on**: If an audio recorder feeds a network connection, the recorder should not be started until the connection is confirmed open. Failure here means the recorder can run indefinitely if the connection fails to open.

## Known Enforcement Gap

The Two-PR convention is enforced by review and quality gate, not by a compile-time mechanism. A single PR could theoretically add an implementation, update `CAPABILITY_STATUS.md` to `PROVEN`, and change the default simultaneously — defeating C2. The mitigation is:

1. The `independent-perspective` agent in the review panel asks specifically about this scenario
2. The quality gate check makes the change visible in CI output
3. The test asserting `sttEngineProvider` default (see `test/providers/voice_providers_test.dart`) would fail if the default changes without a test update

This gap is documented and accepted per SPEC-20260305-080259 Risk Assessment and Principle #8 (least-complex intervention).

## References

- ADR-0035: Capability Protection Protocol
- SPEC-20260305-080259: Voice Stack Stabilization + CPP
- `CAPABILITY_STATUS.md`: Live capability registry
- `memory/bugs/regression-ledger.md`: Microphone leak post-mortem entry (2026-03-05)
- `scripts/quality_gate.py`: C2 implementation
- `.claude/commands/review.md`: C3 implementation (default-change trigger)
