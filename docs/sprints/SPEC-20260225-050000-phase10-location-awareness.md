---
spec_id: SPEC-20260225-050000
title: "Phase 10: Location Awareness"
status: reviewed
risk_level: medium
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260224-183917-phase10-location-awareness-spec-review
---

## Goal

Add opt-in location awareness to journal sessions so users can see where they were when they journaled. Capture GPS coordinates at session start, reverse-geocode to a human-readable place name, display location in the UI, and provide privacy controls including a cloud sync policy that only syncs the place name (not raw coordinates).

## Context

Phase 9 (Photo Integration) is complete and merged. The app is at schema v3, 955 tests, 80.4% coverage. Phase 10 is the next phase per `docs/phases-6-11-project-plan.md` — a small-complexity phase (S) that adds location columns to the existing `JournalSessions` table (schema v4).

Location is privacy-sensitive. The design prioritizes user control: opt-in by default (off), precision reduction at capture time (2 decimal places, ~1.1km), and a cloud sync policy that only transmits the human-readable place name — raw coordinates remain local-only. Note: The Android platform geocoder routes reverse-geocode requests through Google's servers, so reduced-precision coordinates are sent to Google during geocoding. This is disclosed in the opt-in flow.

## Requirements

### Functional
- R1: Add location columns to `JournalSessions`: `latitude` (real, nullable), `longitude` (real, nullable), `locationAccuracy` (real, nullable), `locationName` (text, nullable)
- R2: Create a `LocationService` with an **injectable abstraction** over `geolocator` and `geocoding` (for testability). Provides `getLocation()` — tries `getLastKnownPosition()` first, falls back to `getCurrentPosition()` with 2-second timeout. Accept any cached position regardless of staleness (simplifies implementation; the fire-and-forget pattern means even a stale position is better than no position).
- R3: Capture location automatically at session start as fire-and-forget — **must occur after `createSession()` commits** (session row must exist before `updateSessionLocation()` can write to it). Pattern: `await createSession(...)` then `_captureLocationAsync(sessionId)` (void, unawaited). Must not delay session creation or greeting.
- R4: Reduce GPS precision to 2 decimal places (~1.1km) before storing. This is a **deliberate privacy tradeoff**, not a display formatting choice.
- R5: Reverse geocode lat/lng to "City, State" or "City, Country" using `geocoding` package. If geocoding fails (offline, no result, exception), leave `locationName` as null permanently for that session (no retry mechanism).
- R6: Handle offline gracefully — leave `locationName` null. No retry — null is a valid final state.
- R7: Display location as a pill/chip on session detail screen
- R8: Display small location indicator on session cards in the list
- R9: Provide a "Location" toggle in settings (default: off). Persist via **SharedPreferences-backed Notifier** (per `PreferClaudeNotifier` pattern). Opt-in disclosure text: "Location names are looked up using your device's location service, which may contact Google. Raw coordinates are not stored in your journal's cloud backup."
- R10: Provide "Clear Location Data" button in settings with confirmation dialog. Clears local location columns AND sets `syncStatus = 'PENDING'` on affected sessions so next sync uploads null `locationName` to Supabase. Also sets the location toggle to off.
- R11: Cloud sync policy: only sync `locationName` to Supabase, never sync raw coordinates. **Enforced by a unit test** that asserts `latitude`, `longitude`, `locationAccuracy` keys are absent from the upsert payload.

### Non-Functional
- NF1: Location capture must not add perceptible latency to session start
- NF2: Permission denial must be handled gracefully — session continues normally without location. Wrap fire-and-forget in try/catch at outermost level; catch `PermissionDeniedException` and `LocationServiceDisabledException` silently; only log unexpected exceptions in `kDebugMode`.
- NF3: Android permissions: `ACCESS_COARSE_LOCATION` by default; `ACCESS_FINE_LOCATION` only if user opts into higher precision in settings

## Constraints

- Schema migration v3 → v4 (add columns to existing `JournalSessions` table)
- Must use `geolocator` ^13.0.2 and `geocoding` ^3.0.0 per project plan
- Must follow constructor-injection pattern for service dependencies (ADR-0007)
- Must follow existing Riverpod provider patterns
- Fire-and-forget pattern: location capture runs **after** session record is created, updates session asynchronously
- No `ACCESS_BACKGROUND_LOCATION` — location is foreground-only at session start
- `LocationService` must have an injectable seam for `geolocator` and `geocoding` — either an abstract interface or `@visibleForTesting` constructor accepting callable overrides (same pattern as `PhotoService(picker:)`)
- `updateSessionLocation()` must set `syncStatus = 'PENDING'` to ensure location data enters the sync queue
- Read location preference imperatively via `_ref.read()` inside `startSession()`, not as a reactive watch on `SessionNotifier`

## Acceptance Criteria

- [ ] AC1: Schema v4 migration adds 4 nullable columns to JournalSessions; existing data unaffected (verified by migration test with pre-migration row)
- [ ] AC2: `LocationService.getLocation()` returns position or null (never throws); handles permission denial, timeout, service disabled, mid-session permission revocation
- [ ] AC3: Coordinates are rounded to 2 decimal places before storage (parameterized tests: 51.507456→51.51, 0.004→0.0, -73.985→-73.99, 180.0→180.0, 0.005→0.01)
- [ ] AC4: Session start with location enabled: `startSession()` resolves before location future completes; session row updated with location asynchronously after fire-and-forget resolves; location failure does not corrupt session
- [ ] AC5: Session start with location disabled skips location capture entirely
- [ ] AC6: Reverse geocoding populates `locationName` when online; null when offline or geocoding exception
- [ ] AC7: Session detail screen shows location pill when `locationName` is set; no pill when null
- [ ] AC8: Session card shows location indicator icon when location data exists; no icon when null
- [ ] AC9: Settings screen has location toggle (default off, persisted via SharedPreferences) and "Clear Location Data" button
- [ ] AC10: "Clear Location Data" nullifies all location columns across all sessions, sets syncStatus to PENDING on affected rows, and sets location toggle to off
- [ ] AC11: `uploadSession()` includes `locationName` but omits `latitude`/`longitude`/`locationAccuracy` — **verified by unit test asserting absence of coordinate keys in upsert payload**
- [ ] AC12: All tests pass, coverage >= 80%
- [ ] AC13: `dart analyze` zero errors, `dart format` clean

## Risk Assessment

- **Low: GPS cold start latency** — Mitigated by `getLastKnownPosition()` first, 2-second timeout on `getCurrentPosition()`, and fire-and-forget pattern so session is never blocked.
- **Low: Geocoding offline** — Acceptable degradation: `locationName` stays null permanently for that session. No retry mechanism.
- **Medium: Privacy** — Mitigated by opt-in default (off), precision reduction (deliberate privacy tradeoff per ADR-0019), local-only coordinates, cloud-only place name, sync payload exclusion test. Geocoding disclosure included in opt-in flow.
- **Low: Permission model complexity** — Only coarse location by default; fine location is a settings opt-in. Single permission request with rationale.

## Affected Components

### New Files
- `lib/services/location_service.dart` — GPS + geocoding wrapper with injectable seam
- `lib/providers/location_providers.dart` — Riverpod providers for location service and location-enabled setting (SharedPreferences-backed)
- `test/services/location_service_test.dart` — Unit tests with injectable fakes (permission scenarios, timeout, rounding, geocoding failures)
- `test/database/migration_v4_test.dart` — Migration test (pre-migration row survives, null location columns)
- `test/database/session_dao_location_test.dart` — DAO tests for `updateSessionLocation` and `clearAllLocationData`
- `test/repositories/sync_repository_location_test.dart` — Sync payload exclusion test (AC11)
- `docs/adr/ADR-0019-location-tracking.md` — Architecture Decision Record

### Modified Files
- `lib/database/tables.dart` — Add location columns to JournalSessions
- `lib/database/app_database.dart` — Schema v4 migration
- `lib/database/daos/session_dao.dart` — `updateSessionLocation()` (with syncStatus reset), `clearAllLocationData()` (with syncStatus reset)
- `lib/providers/session_providers.dart` — Fire-and-forget location capture in `startSession()` (after createSession, read location pref imperatively)
- `lib/repositories/sync_repository.dart` — Include `locationName` in upload, exclude coordinates (with PRIVACY-POLICY comment + ADR reference)
- `lib/ui/screens/session_detail_screen.dart` — Location pill display
- `lib/ui/widgets/session_card.dart` — Location indicator icon
- `lib/ui/screens/settings_screen.dart` — Location toggle + clear data button
- `android/app/src/main/AndroidManifest.xml` — `ACCESS_COARSE_LOCATION` and `ACCESS_FINE_LOCATION` permissions
- `pubspec.yaml` — Add `geolocator` and `geocoding` dependencies

## Dependencies

- **Depends on**: Phase 9 (schema v3) — complete and merged
- **Depended on by**: No direct downstream dependencies; Phase 11 (Calendar) is independent

## Tasks (Implementation Order)

1. **ADR-0019**: Document decisions — opt-in default, 2-decimal-place precision reduction as deliberate privacy tradeoff, raw-local/name-only-cloud sync boundary, permission strategy (coarse default/fine opt-in), geocoding disclosure, no retry for failed geocoding
2. **Task 1**: Schema v4 — Add location columns to `JournalSessions`, migration, `updateSessionLocation()` (with syncStatus=PENDING), `clearAllLocationData()` (with syncStatus=PENDING). Tests: `migration_v4_test.dart`, `session_dao_location_test.dart`.
3. **Task 2**: LocationService — Injectable seam for geolocator/geocoding, `getLocation()` (getLastKnownPosition → getCurrentPosition fallback), precision rounding, reverse geocoding with exception handling. Tests: `location_service_test.dart` with parameterized rounding tests and all error scenarios.
4. **Task 3**: Location providers + settings — SharedPreferences-backed location toggle, location service provider, fire-and-forget capture in `startSession()` (after createSession, imperative read of setting, outermost try/catch).
5. **Task 4**: UI — Session detail pill, session card indicator, settings toggle + clear button + disclosure text. Widget tests for conditional display.
6. **Task 5**: Cloud sync — Include `locationName` only in `uploadSession()`, with PRIVACY-POLICY comment. Sync payload exclusion test asserting coordinate keys absent.

## Specialist Review Summary

**Discussion**: DISC-20260224-183917-phase10-location-awareness-spec-review

### Blocking Findings (addressed in this revision)
- **B1 (all 3 specialists)**: Sync payload leakage — Added AC11 enforcement via unit test, PRIVACY-POLICY comment requirement, dedicated test file.
- **B2 (architecture)**: Fire-and-forget sequencing — Clarified R3 and constraints: must occur after `createSession()` commits.
- **B3 (QA)**: LocationService injectable seam — Added constraint requiring injectable abstraction for geolocator/geocoding.
- **B4 (QA)**: Rounding edge cases — Added parameterized test cases to AC3.

### Advisory Findings (noted for implementation)
- ADR-0019 must document precision reduction as deliberate privacy tradeoff (not display formatting)
- Settings persistence via SharedPreferences-backed Notifier (per PreferClaudeNotifier pattern)
- SessionNotifier reads location pref imperatively, not reactively
- clearAllLocationData sets syncStatus=PENDING to propagate nullification to cloud
- updateSessionLocation sets syncStatus=PENDING to enter sync queue
- Geocoding sends coords to Google — disclosed in opt-in flow text
- Geocoding failure = null permanently (no retry mechanism)
- Migration test should verify pre-migration row retains values + null location columns
- clearAllLocationData DAO tests: all sessions updated, non-location columns untouched, empty table no-op
