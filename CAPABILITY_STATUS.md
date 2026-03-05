# Capability Status Registry

> **CPP (Capability Protection Protocol)** — Part of the Agentic Development Framework.
> See: ADR-0035, SPEC-20260305-080259, `.claude/rules/capability_protection.md`
>
> This file is the authoritative source of truth for capability maturity status.
> The quality gate reads this file to block EXPERIMENTAL capabilities from becoming defaults.
> Update this file whenever a capability is device-tested or its status changes.

## Status Definitions

| Status | Meaning |
|--------|---------|
| **PROVEN** | Device-verified, working end-to-end on physical hardware |
| **EXPERIMENTAL** | Implemented but not device-tested, or device-tested with known failures |
| **BROKEN** | Known to be non-functional; awaiting fix |
| **DEPRECATED** | Superseded by another capability; retained for reference |

## Voice / Speech-to-Text (STT)

| Capability | Status | Device-tested? | Last verified | Verified on | Notes |
|------------|--------|----------------|---------------|-------------|-------|
| STT: speech_to_text | **PROVEN** | Yes | 2026-03-01 | SM_G998U1 (Android 14) | PR #52 voice integration test passing; confirmed working before Deepgram introduction. |
| STT: deepgram | **EXPERIMENTAL** | No | — | — | WebSocket 401 unresolved. Proxy mints temp token via /v1/auth/grant + ?access_token= param (PR e1ad873). Auth path fixed but not device-verified post-fix. NOT the default. |
| STT: sherpa_onnx | **EXPERIMENTAL** | No | — | — | Implementation complete. Requires 71MB model download. Not device-tested on SM_G998U1. Zipformer SIGILL risk on Snapdragon 888 unresolved (ADR-0017). |

## Voice / Text-to-Speech (TTS)

| Capability | Status | Device-tested? | Last verified | Verified on | Notes |
|------------|--------|----------------|---------------|-------------|-------|
| TTS: ElevenLabs | **PROVEN** | Yes | 2026-03-04 | SM_G998U1 (Android 14) | Primary TTS, device-verified across multiple sessions. |
| TTS: Flutter system TTS (fallback) | **PROVEN** | Yes | 2026-03-04 | SM_G998U1 (Android 14) | FallbackTtsService wraps system TTS; activated when ElevenLabs fails. |

## Camera / Photo

| Capability | Status | Device-tested? | Last verified | Verified on | Notes |
|------------|--------|----------------|---------------|-------------|-------|
| Photo capture | **PROVEN** | Yes | 2026-03-04 | SM_G998U1 (Android 14) | image_picker + photo description. Voice race condition fixed (PR #83). |

## Calendar

| Capability | Status | Device-tested? | Last verified | Verified on | Notes |
|------------|--------|----------------|---------------|-------------|-------|
| Google Calendar integration | **PROVEN** | Yes | 2026-03-04 | SM_G998U1 (Android 14) | OAuth + event creation working. |

## Notifications

| Capability | Status | Device-tested? | Last verified | Verified on | Notes |
|------------|--------|----------------|---------------|-------------|-------|
| Scheduled task reminders | **PROVEN** | Yes | 2026-03-04 | SM_G998U1 (Android 14) | flutter_local_notifications + zonedSchedule. PR #80. |

## Home Screen Widget

| Capability | Status | Device-tested? | Last verified | Verified on | Notes |
|------------|--------|----------------|---------------|-------------|-------|
| Android Quick Capture widget | **PROVEN** | Yes | 2026-03-04 | SM_G998U1 (Android 14) | AppWidgetProvider + MethodChannel bridge. PR #84. |

---

## Recording Protocol

When you device-test a capability:

```bash
# Update this file: change Status to PROVEN, set Device-tested to Yes,
# fill in Last verified (YYYY-MM-DD) and Verified on (device + OS version).
# Then commit with a message referencing the PR or commit that was tested.
```

**Staleness warning**: If a PROVEN capability's `Last verified` date is older than 30 days,
treat it as UNCONFIRMED until re-tested. The quality gate will warn when this threshold is crossed.

---

*Last updated: 2026-03-05 | SPEC-20260305-080259 | ADR-0035*
