---
discussion_id: DISC-20260224-183917-phase10-location-awareness-spec-review
started: 2026-02-24T18:42:44.383760+00:00
ended: 2026-02-24T18:44:12.006645+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 4
---

# Discussion: DISC-20260224-183917-phase10-location-awareness-spec-review

## Turn 1 — architecture-consultant (critique)
*2026-02-24T18:42:44.383760+00:00 | confidence: 0.87*
*tags: spec-review, architecture, phase-10*

APPROVE WITH CHANGES. Confidence: 0.87. 9 findings (2 blocking, 4 advisory, 3 low).

BLOCKING:
B1 (High): Sync payload leakage — uploadSession() explicitly lists fields in upsert map. No structural enforcement prevents coordinates from being added later. Need test asserting latitude/longitude/locationAccuracy absent from upsert payload + doc comment with ADR reference.
B2 (High): Fire-and-forget timing — location capture must occur AFTER createSession() commits, not concurrent with it. updateSessionLocation needs the session row to exist. Pattern: await createSession() then _captureLocationAsync(sessionId) (void, unawaited).

ADVISORY:
A1 (Medium): ADR-0019 content — must explicitly document 2-decimal-place truncation as deliberate privacy tradeoff, not display formatting. Also record raw-local/name-only-cloud sync boundary.
A2 (Medium): Settings persistence — location toggle must use SharedPreferences-backed Notifier (per PreferClaudeNotifier pattern), not ephemeral StateProvider. clearAllLocationData should also set toggle to false.
A3 (Medium): SessionNotifier coupling — read locationEnabledProvider imperatively via _ref.read() inside startSession(), don't watch reactively. Add LocationService via constructor injection per ADR-0007.
A4 (Medium): clearAllLocationData cloud divergence — clearing locally while cloud records persist. Should set syncStatus=PENDING on affected sessions so next sync uploads null locationName.

LOW:
L1: updateSessionLocation should include syncStatus='PENDING' in write companion (mirrors resumeSession pattern).
L2: Geocoding offline — simplify from 'retry later' to 'null permanently for this session' unless retry mechanism designed.
L3: Coarse permission only — ACCESS_COARSE_LOCATION sufficient for 2-decimal precision.

---

## Turn 2 — security-specialist (critique)
*2026-02-24T18:42:51.576066+00:00 | confidence: 0.88*
*tags: spec-review, security, phase-10, privacy*

APPROVE WITH CHANGES. Confidence: 0.88. 6 findings (1 blocking, 2 advisory, 3 low).

BLOCKING:
B1 (High): Sync payload leakage — uploadSession() has no structural enforcement preventing coordinate sync. Need toCloudMap() or equivalent + unit test asserting latitude/longitude/locationAccuracy absent from Supabase upsert payload. This is the same finding as architecture-consultant B1.

ADVISORY:
A1 (Medium): Geocoding sends coords to Google — Android Geocoder routes through Google servers. The privacy statement 'coordinates never leave the device' is technically incomplete. Need user-facing disclosure: 'Location names are looked up using your device location service, which may contact Google. Raw coordinates are not stored in your journal or synced to our servers.'
A2 (Medium): Clear Location Data scope — clearing locally leaves locationName in Supabase for already-synced sessions. Should set syncStatus=PENDING on affected sessions after local nullification so next sync uploads null locationName. Same finding as architecture-consultant A4.

LOW:
L1: Precision reduction (2 decimal places, ~1.1km) is sufficient for this threat model. No change needed.
L2: Permission declaration — both ACCESS_COARSE and ACCESS_FINE will appear in Play Store. Document the conditional nature.
L3: Fire-and-forget exception handling — wrap outermost level in try/catch for PermissionDeniedException and LocationServiceDisabledException. Only log in kDebugMode.

---

## Turn 3 — qa-specialist (critique)
*2026-02-24T18:43:02.959233+00:00 | confidence: 0.88*
*tags: spec-review, qa, testing, phase-10*

APPROVE WITH CHANGES. Confidence: 0.88. 12 findings (4 blocking, 5 advisory, 3 low).

BLOCKING:
B1 (High): LocationService needs injectable seam — geolocator has no public injection API (unlike ImagePicker which can be subclassed). Must define abstract interface or @visibleForTesting constructor with callable overrides for getLastKnownPosition/getCurrentPosition. Without this, AC2 (never throws) is untestable.
B2 (High): Missing fire-and-forget provider tests — AC4 (location doesn't delay greeting) needs Completer-based fake to verify startSession() resolves before location future completes. Also verify session row updated after fire-and-forget resolves, and location failure doesn't corrupt session.
B3 (High): Missing sync payload exclusion test — AC11 needs test capturing upsert map and asserting latitude/longitude/locationAccuracy keys absent. (Same finding as arch B1 and sec B1.)
B4 (High): Rounding edge case tests — AC3 needs parameterized tests: 51.507456->51.51, 0.004->0.0, -73.985->-73.99, 180.0->180.0, 0.005->0.01. Verify stored column value via DAO, not just service output.

ADVISORY:
A1 (Medium): Migration test should verify pre-migration session retains existing field values + null location columns after upgrade.
A2 (Medium): clearAllLocationData needs DAO-level tests: all sessions updated, non-location columns untouched, no-op on empty table, sessions with no location data handled.
A3 (Medium): getLastKnownPosition staleness policy undefined — what if cached position is 12 hours old? Define threshold or accept any cached position.
A4 (Medium): Settings screen widget tests needed — location toggle renders default off, toggle persists, clear button calls DAO, confirmation shown.
A5 (Medium): No-throw contract testing — use explicit returnsNormally assertions, not just null-check. Add geocoding exception test (NoResultFoundException).

LOW:
L1: geocoding static method injection — accept injectable geocoding function via @visibleForTesting parameter.
L2: Permission revocation mid-session — test getCurrentPosition() throwing PermissionDeniedException returns null.
L3: Widget tests for location pill (set/null) and card indicator (set/null) for AC7/AC8.

---

## Turn 4 — facilitator (synthesis)
*2026-02-24T18:44:12.006645+00:00 | confidence: 0.9*
*tags: synthesis, blocking:4, advisory:7*

Synthesis of Phase 10 spec review. All 3 specialists approved with changes. 4 blocking findings identified and addressed in spec revision:

1. Sync payload enforcement (all 3): Added unit test requirement for AC11 — test asserts latitude/longitude/locationAccuracy absent from upsert payload. Added PRIVACY-POLICY comment requirement. Added dedicated test file.
2. Fire-and-forget sequencing (arch): Clarified R3 and constraints — location capture must occur AFTER createSession() commits. Explicit pattern documented.
3. LocationService injectable seam (QA): Added constraint requiring injectable abstraction for geolocator/geocoding, following PhotoService(picker:) pattern.
4. Rounding edge cases (QA): Added parameterized test values to AC3.

7 advisory findings incorporated: SharedPreferences-backed location toggle, imperative preference reads, syncStatus=PENDING on location updates and clear, geocoding disclosure in opt-in text, no retry for failed geocoding, pre-migration row verification in migration test, clearAllLocationData DAO test coverage.

Spec status updated to 'reviewed'. All blocking findings resolved in the revised spec.

---
