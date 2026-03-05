# Experimental-First Convention

> Part of the Capability Protection Protocol (CPP) — ADR-0035, SPEC-20260305-080259.

## The Rule

**New capabilities MUST NOT change a provider default in the same PR that introduces the implementation.**

This is the Two-PR Pattern. It exists because the alternative — introducing an unproven
capability and immediately making it the production default — is how all three STT engines
were broken simultaneously in 2026-03 (see `memory/bugs/regression-ledger.md`).

## The Two-PR Pattern

### PR N: Implementation (Default Unchanged)

In this PR you may:
- Add the new service class (e.g., `DeepgramSttService`)
- Add the new enum value (e.g., `SttEngine.deepgram`)
- Add the provider case that returns the new service for the new enum value
- Add tests for the new service
- Add the capability to `CAPABILITY_STATUS.md` as `EXPERIMENTAL`
- Wire the new option into the settings UI as an opt-in choice

You MUST NOT:
- Change the default return value of the notifier's `build()` method
- Mark the capability as `PROVEN` in `CAPABILITY_STATUS.md` before device testing
- Label the new option as "Recommended" or "Default" in the settings UI

### PR N+1: Default Promotion (After Device Testing)

Before opening this PR:
1. Run a voice session using the new capability on a physical device
2. Confirm the capability works end-to-end (transcription produces text, resources are released)
3. Update `CAPABILITY_STATUS.md`: change `EXPERIMENTAL` → `PROVEN`, fill in `Last verified`, `Verified on`

In this PR:
- Change the default return value in the notifier's `build()` method
- Update the settings UI label (remove `(Experimental)`, add `(Default)` or nothing)
- Add `# CAPABILITY-GATE: approved` comment if the quality gate warns
- Reference the device test in the PR description

## What Counts as "Changing the Default"

Any of these actions promote a capability to the primary user experience path and
require the two-PR pattern:

1. **Provider default**: Changing the fallthrough `return` in a Riverpod `Notifier.build()`
2. **Settings label**: Changing from `(Experimental)` to `(Default)` or `(Recommended)`
3. **UI ordering**: Moving the new capability to the first position in a selection list
4. **Feature flag**: Enabling a flag by default for all users

## Why Not Environment Separation?

The alternative — maintaining DEV and UAT environments where experimental features are
tested before promotion — has been explicitly rejected for this project. The agentic
development framework must be self-contained. Environment separation is legitimate
engineering, but it pushes complexity into deployment infrastructure outside the
framework's control. The Two-PR Pattern achieves the same isolation within a single
environment through process gates rather than infrastructure gates.

## Compliance Check

The quality gate (`scripts/quality_gate.py`) detects when a Riverpod provider default
changes and warns if the new default is EXPERIMENTAL in `CAPABILITY_STATUS.md`. The
review workflow (`.claude/commands/review.md`) automatically adds `independent-perspective`
to the specialist panel for any PR that changes a provider default.

These checks are warnings, not hard blocks. The Two-PR pattern is the primary control.
The checks make violations visible; the code review process enforces the response.

## Example: The Wrong Way (PR #72, 2026-03-03)

```dart
// ❌ Added DeepgramSttService AND changed the default in the same commit:
return SttEngine.deepgram; // Default changed from speechToText to deepgram
```

Deepgram was never device-tested. Its WebSocket 401 failures triggered a microphone
resource leak that blocked all three STT engines. Voice mode broke for multiple sessions.

## Example: The Right Way

**PR N** (implementation only):
```dart
// SttEngine.deepgram added as a new case — default unchanged
return SttEngine.speechToText; // Proven baseline unchanged
```

**After device testing:**
Update `CAPABILITY_STATUS.md`:
```
| STT: deepgram | PROVEN | Yes | 2026-03-10 | SM_G998U1 (Android 14) | WebSocket auth resolved |
```

**PR N+1** (default change only):
```dart
// CPP-GATE: approved — deepgram PROVEN per CAPABILITY_STATUS.md 2026-03-10
return SttEngine.deepgram;
```

## References

- ADR-0035: Capability Protection Protocol
- `CAPABILITY_STATUS.md`: Capability registry (project root)
- `.claude/rules/capability_protection.md`: Protocol enforcement rules
- `memory/bugs/regression-ledger.md`: Microphone leak root cause analysis
