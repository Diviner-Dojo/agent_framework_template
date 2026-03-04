---
adr_id: ADR-0034
title: "Quick Capture Home Screen Widget + Passive Weather Metadata"
status: accepted
date: 2026-03-04
decision_makers: [architecture-consultant, security-specialist, independent-perspective, facilitator]
discussion_id: DISC-20260304-183306-review-phase-4bc-weather-widget
supersedes: null
risk_level: medium
confidence: 0.87
tags: [android, widget, weather, sync, security]
---

## Context

Phase 4B adds an Android home screen widget that opens the app directly in the user's last-used capture mode (ADHD effortless capture — one tap, no mode picker). Phase 4C adds passive weather metadata capture at session start (fire-and-forget, never blocks the session).

Two architectural decisions required explicit documentation:

1. The widget reads Flutter's `SharedPreferences` file directly from Kotlin, coupling Kotlin code to Flutter plugin internals.
2. Weather columns are captured locally but excluded from Supabase cloud sync — this needed to be an explicit decision, not an accidental omission.

A third concern arose from the security review: the mode string from the Android Intent extra must be validated before dispatch.

---

## Decision 1: Open-Meteo as the Weather Provider

**Choice**: Open-Meteo (`https://api.open-meteo.com/v1/forecast`)

**Rationale**:
- Free tier; no API key required; no per-call cost
- GDPR-compliant; no user account or session identifier sent
- WMO 306 standard weather codes — well-defined, stable
- Only the already-rounded 2 d.p. coordinates (per ADR-0019) are sent — no additional privacy surface

**Fire-and-forget contract**: `WeatherService.getWeather()` never throws. All failures (network error, API down, unexpected response shape) return `null`. Session start is never blocked. The fire-and-forget wrapper (`Future<void>(() async { ... })`) in `_captureWeatherAsync` ensures the HTTP call is entirely decoupled from the session creation path.

**Timeout**: Both `connectTimeout` and `receiveTimeout` are set to 5 seconds. Setting only `receiveTimeout` (as initially implemented) would allow TCP connection to hang for the platform default (~75 seconds) under captive portals or hostile networks.

---

## Decision 2: Weather Columns are Local-Only (Not Synced to Supabase)

**Choice**: `weatherTempC`, `weatherCode`, `weatherDescription` are excluded from `buildSessionUpsertMap` and will not be synced to Supabase.

**Rationale**:
- Weather is ambient journaling context — useful locally but not essential for cloud backup or multi-device restore
- The coordinates sent to Open-Meteo are already reduced-precision (ADR-0019); the weather result derived from them carries no additional identifying information
- Adding weather to the Supabase schema would require a PostgreSQL migration, RLS policy update, and schema sync — overhead disproportionate to the value for this phase

**Precedent**: This follows the same local-only decision made for raw GPS coordinates (ADR-0019 §3). The difference is that `locationName` is synced (it is the user-visible label), while weather is purely internal enrichment.

**Explicit assertion**: `test/repositories/sync_repository_location_test.dart` contains a load-bearing test (`'weather columns are excluded from buildSessionUpsertMap (stay local)'`) that fails if any of the three weather keys appear in the upsert map. This is the enforcement mechanism, following the ADR-0019 precedent.

**Future**: If weather sync is added in a future phase, `buildSessionUpsertMap`, the Supabase migration, and this ADR must be updated together.

---

## Decision 3: SharedPreferences Cross-Layer Coupling (Kotlin Reads Flutter's Prefs File)

**Choice**: The `QuickCaptureWidget` Kotlin class reads the `last_capture_mode` value directly from Flutter's `SharedPreferences` storage (`FlutterSharedPreferences` file, `flutter.` key prefix) rather than querying Flutter via a MethodChannel round-trip at widget render time.

**Rationale**:
- Android widget `onUpdate()` fires on the launcher's process — a MethodChannel call to Flutter is not possible at widget render time (Flutter may not be running)
- Reading `SharedPreferences` directly at render time means the PendingIntent always carries the mode value with zero additional latency
- The `flutter.` prefix convention is stable and widely depended upon by the Flutter ecosystem; it is documented in the `shared_preferences_android` plugin source and has not changed across major Flutter versions

**Risk and mitigation**:
- If the `shared_preferences_android` plugin changes its storage format, the widget will read `null` instead of the stored mode string and fall back to opening the quick capture palette normally — one extra tap, not a crash
- The `PREF_LAST_CAPTURE_MODE = "flutter.last_capture_mode"` constant is co-located with a comment in `QuickCaptureWidget.kt` explaining the convention, making any future breakage immediately visible
- The graceful degradation (null → palette) means users on an affected Flutter version lose the shortcut but not functionality

**PendingIntent staleness**: The mode baked into the PendingIntent is captured at widget-draw time (`onUpdate`), not at tap time. Android controls widget refresh intervals (typically 30+ minutes). If the user changes their preferred mode inside the app between widget refreshes, the widget may launch with a stale mode until the next Android-triggered `onUpdate`. A future improvement is to call `AppWidgetManager.updateAppWidget()` from Flutter via MethodChannel after `lastCaptureModeProvider.setMode()` completes.

---

## Decision 4: Intent Extra Mode String Validation (Security)

**Choice**: The mode string received from `EXTRA_WIDGET_LAUNCH_MODE` is validated against a strict allowlist before being dispatched to `_dispatchCaptureMode()`.

**Rationale**:
- `MainActivity` is `exported="true"` (required for launcher and assistant intents)
- Any on-device app can send a crafted Intent to `MainActivity` with an arbitrary mode string
- Without validation, the mode flows directly into application routing logic
- The allowlist (`{'text', 'voice', '__quick_mood_tap__', 'pulse_check_in'}`) is defined as a constant in `session_list_screen.dart` alongside the `ref.listen` handler; unknown values are discarded silently

---

## Alternatives Considered

### Weather provider: OpenWeatherMap or WeatherAPI
- **Pros**: More detailed forecasts, more WMO code coverage, richer metadata
- **Cons**: Require API keys (secrets management complexity), per-call costs, user data potentially stored on provider servers
- **Reason rejected**: Open-Meteo covers all common WMO codes, is free and keyless, and is GDPR-compliant. The journaling use case needs only temperature + general condition, not forecast detail.

### Weather sync to Supabase
- **Pros**: Cloud backup of weather context, available in multi-device restore
- **Cons**: Requires PostgreSQL migration, RLS policy update, schema sync — disproportionate to the journaling value in Phase 4C scope
- **Reason rejected**: Weather is ambient enrichment, not core journaling content. Deferred to a future phase if demand arises. The coordinate-exclusion precedent (ADR-0019) establishes that passive environmental data stays local.

### Platform channel call from widget at render time
- **Pros**: Avoids the SharedPreferences internal-format coupling
- **Cons**: The widget's `onUpdate()` fires in the launcher process — Flutter may not be running, so a MethodChannel call is not possible
- **Reason rejected**: Technically infeasible at widget render time; SharedPreferences read is the only viable option.

### Intent extra validation via server-side list
- **Pros**: Allows mode strings to be updated without an app release
- **Cons**: Requires a network round-trip, adds latency to widget launch, introduces a dependency on connectivity
- **Reason rejected**: The set of valid modes is compile-time known and changes only with app releases. A hardcoded allowlist is simpler and faster.

## Consequences

- **Positive**: Weather context enriches session metadata at no cost to the user and zero session-blocking risk.
- **Positive**: One-tap widget reduces ADHD capture friction to its minimum.
- **Positive**: Security posture is sound: allowlist guard prevents Intent injection; SharedPreferences is `MODE_PRIVATE`; no new permissions required.
- **Negative**: Widget mode can be stale for up to 30+ minutes between Android-triggered refreshes (mitigated by graceful fallback and planned MethodChannel refresh).
- **Negative**: SharedPreferences coupling is an internal Flutter convention dependency (mitigated by graceful null fallback and explicit code comments).
- **Negative**: Weather data is local-only and not available in multi-device restore (accepted for Phase 4C scope).
