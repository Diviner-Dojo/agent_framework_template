---
spec_id: SPEC-20260225-120000
title: "Phase 11: Google Calendar + Reminders"
status: reviewed
risk_level: high
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260224-205141-phase11-calendar-spec-review
---

## Goal

Add Google Calendar integration to the journal companion so the AI can detect calendar-related intents during conversation, extract event details, and create events with user confirmation. This transforms the app from a passive journal into an active personal assistant.

## Context

Phases 6-10 delivered session management, continuous voice mode, local LLM, photos, and location awareness. The app now has a mature conversation pipeline with intent classification (journal vs query/recall), multi-layer LLM architecture (rule-based / local / Claude), and voice mode with verbal confirmations.

Phase 11 is the final planned phase. It is marked XL complexity because it combines OAuth2 (routinely a full sprint), temporal expression parsing, and an intent taxonomy redesign that must not regress existing recall classification.

**Current state:** Schema v4, 1021+ tests, 80.4% coverage, 2 intent types (`journal`, `query`).

### Key Constraint

The existing `IntentClassifier` scores temporal references (e.g., "tomorrow", "next week") as recall signals (+0.3). Calendar/reminder intents inherently contain temporal expressions. The classifier must be redesigned to return ranked multi-intent results before any routing logic is added.

## Requirements

### Functional

1. **Google OAuth2 sign-in** with minimal scopes (`calendar.events` for create/edit)
2. **Intent classification** expanded to 4 types: `journal`, `query`, `calendarEvent`, `reminder`
3. **AI-assisted event extraction**: detect calendar intent in conversation, extract title/date/time, present for confirmation
4. **Inline confirmation flow** in both text and voice modes before creating any event
5. **Google Calendar event creation** via the Google Calendar API
6. **Reminder creation** as all-day events or events with default reminder notifications
7. **Voice mode integration**: verbal confirmation of extracted details, verbal "edit that" corrections
8. **OAuth deferral in voice mode**: if not connected when calendar intent fires, queue for post-session
9. **Calendar settings**: connect/disconnect, auto-suggest toggle, confirmation toggle
10. **Local events table** (schema v5) tracking pending/confirmed/dismissed event suggestions

### Non-Functional

- OAuth token storage in `flutter_secure_storage` (never SharedPreferences or SQLite)
- Existing recall classification must not regress (test coverage on current `query` intent patterns)
- Event creation is always user-confirmed, never automatic
- Calendar API calls proxied through Supabase Edge Function (consistent with ADR-0005 pattern) OR direct from device with user's own OAuth token (personal use app — no server-side secret needed)

## Constraints

- **Unverified OAuth app**: For personal use, the 100-test-user limit is sufficient. Document the path to Google verification separately if the app is ever distributed.
- **No background sync**: Events are created on-demand during conversation, not synced in batch.
- **No read-back**: Phase 11 scope is create-only. Reading/listing upcoming events from Google Calendar is deferred (would require additional `calendar.events.readonly` scope).
- **Single calendar**: Events go to the user's primary Google Calendar. Multi-calendar selection is deferred.

## Tasks

### Task 1: ADR-0020 (Google Calendar Integration)

Document architectural decisions:
- **ADR-0005 deviation rationale** (blocking review finding): Explain why Google Calendar API calls go direct from device with user's OAuth token rather than through Supabase Edge Function proxy. Key distinction: ADR-0005 protects a fixed API key (Claude) that is a shared secret; Google OAuth tokens are per-user credentials that the user authenticates directly with Google to obtain — no server secret is involved. Token storage in `flutter_secure_storage` is the mitigating control. Document refresh-token lifecycle and revocation handling.
- OAuth scope selection and rationale. Investigate `calendar.events.owned` (limits access to app-created events only) vs full `calendar.events` scope. If narrower scope is unavailable, document as a scope minimization constraint.
- Intent taxonomy redesign: multi-intent ranked classification
- Token storage in `flutter_secure_storage`
- **Event lifecycle state vs sync state**: Separate `status` (pending_create/confirmed/failed/cancelled) from `syncStatus` (PENDING/SYNCED/FAILED) — do not conflate in a single column.
- **Event extraction routing**: Use direct `ClaudeApiService` call (or local LLM equivalent) bypassing ConversationLayer strategy interface, matching the existing recall pattern in `_handleRecallQuery()`.
- OAuth-during-voice-mode deferral pattern (state ownership: `pendingCalendarEvent` in `SessionState`)
- Event confirmation policy (never auto-create)
- Verbal edit flow for voice mode corrections
- PENDING event queue cap (max 5) with per-item confirmation before submission

### Task 2: Intent Classifier Redesign

**This is the highest-risk task — it touches the core message routing pipeline.**

**Step 2a: Regression harness FIRST** (blocking review finding):
- Before any classifier code changes, extract all existing test cases from `intent_classifier_test.dart` into a named regression fixture group: `group('recall regression suite — must not change', ...)`.
- Pin expected intent types AND minimum confidence values, not just the type enum.
- Run this group as the first step of the new `intent_classifier_calendar_test.dart`.

**Step 2b: Classifier redesign:**
- Add `IntentType.calendarEvent` and `IntentType.reminder` to the enum
- Change `classify()` return type from `IntentClassification` (single result) to `List<IntentClassification>` ranked by confidence (or add a `classifyMulti()` method to avoid breaking the existing API)
- Add calendar/reminder signal patterns:
  - Calendar signals: "add to calendar", "schedule", "book", "set up a meeting", "put X on my calendar"
  - Reminder signals: "remind me", "don't let me forget", "remember to", "make sure I"
  - Temporal + action: "meeting tomorrow at 3pm", "dinner on Friday"
- Disambiguate temporal overlap: temporal references score for recall ONLY when combined with past-tense question structure (existing behavior). Calendar/reminder score when temporal references combine with future-tense imperative/action verbs.
- **Temporal collision tests** (blocking review finding): Add parameterized tests covering the collision space:
  - `'What did I schedule for last Monday?'` → recall (past-tense question)
  - `'Add a meeting for next Monday'` → calendarEvent (future-tense imperative)
  - `'Remind me about what I wrote last week'` → multi-intent collision (recall + reminder)
  - `'What meetings did I add last Tuesday?'` → recall (past-tense query)

**Step 2c: Routing update:**
- Modify `lib/providers/session_providers.dart`:
  - Refactor `sendMessage()` intent routing to use a handler map (`IntentType → handler function`) rather than extending the if/else chain (architecture-consultant advisory — this is the right inflection point)
  - Add `_handleCalendarIntent()` parallel to existing `_handleRecallQuery()`
  - Add `pendingCalendarEvent` state field (following `pendingRecallQuery` pattern)

### Task 3: Google Auth Service

Create `lib/services/google_auth_service.dart`:
- `signIn()` → Google OAuth2 consent flow via `google_sign_in`
- `signOut()` → revoke + clear tokens
- `isSignedIn` getter
- `getAuthClient()` → authenticated HTTP client for Google APIs
- Token persistence in `flutter_secure_storage`
- Token refresh handling (via `google_sign_in` SDK — handles refresh automatically when using `authenticatedClient()`)

Create `lib/providers/calendar_providers.dart`:
- `googleAuthServiceProvider` (Provider)
- `isGoogleConnectedProvider` (StateProvider or FutureProvider)
- `calendarAutoSuggestProvider` (SharedPreferences-backed NotifierProvider)
- `calendarConfirmationProvider` (SharedPreferences-backed NotifierProvider)

### Task 4: Google Calendar Service

Create `lib/services/google_calendar_service.dart`:
- `createEvent(title, startTime, endTime, {description})` → Google Calendar API insert
- `createReminder(title, dateTime, {description})` → all-day event or timed event with notification
- Uses `googleapis` CalendarApi with the authenticated client from Task 3
- Events go to the user's primary calendar (`"primary"`)
- Returns the created event ID for local tracking

### Task 5: Event Extraction Service

Create `lib/services/event_extraction_service.dart`:
- Given a user message classified as `calendarEvent` or `reminder`, extract structured event details: title, date, time, duration (optional)
- **Strategy**: Use the LLM directly (ClaudeApiService or local LLM, matching recall pattern) to extract structured data from the natural language input. The LLM prompt requests JSON output: `{"title": "...", "date": "...", "time": "...", "duration_minutes": ...}`
- **Strict output validation** (blocking review finding): After LLM extraction, validate the JSON against a strict schema before use. Validation rules: title is non-empty string under 200 characters, startTime/endTime parse as valid ISO 8601 datetimes within a sane range (not before today minus 1 day, not after today plus 2 years), no unexpected keys present. Reject and surface an error to the user if validation fails. Extract fields explicitly from the parsed Map — never forward the raw LLM JSON directly to the Calendar API.
- **Failure contract**: malformed JSON → return typed `ExtractionError`, not an exception. Missing fields (title but no time) → return partial extraction with nulls. Past datetime → flag to user for confirmation ("This time is in the past — did you mean...?").
- Fallback for Layer A (rule-based): basic regex extraction of dates and quoted titles — limited but functional
- Parse extracted date/time strings into `DateTime` objects with timezone awareness

### Task 6: Schema v5 — Events Table

Modify `lib/database/tables.dart`:
- Add `CalendarEvents` table: `eventId` (PK), `sessionId` (FK), `userId`, `title`, `startTime`, `endTime` (nullable), `googleEventId` (nullable), `status` (PENDING_CREATE/CONFIRMED/FAILED/CANCELLED — event lifecycle), `syncStatus` (PENDING/SYNCED/FAILED — cloud sync, reuses existing pattern), `rawUserMessage`, `createdAt`, `updatedAt`

Modify `lib/database/app_database.dart`:
- `schemaVersion` 4 → 5
- Migration: `m.createTable(calendarEvents)` + index on `session_id`

Create `lib/database/daos/calendar_event_dao.dart`:
- `insertEvent()`, `getEventById()`, `getEventsForSession()`, `updateStatus()`, `updateGoogleEventId()`, `getPendingEvents()`, `deleteEvent()`

### Task 7: Confirmation Flow UI

Modify `lib/ui/screens/journal_session_screen.dart`:
- When `pendingCalendarEvent` is set, show an inline confirmation card below the message:
  - Event title, date/time preview
  - "Add to Calendar" / "Edit" / "Dismiss" buttons
  - If not Google-connected: "Connect Google Calendar" button instead of "Add"

Create `lib/ui/widgets/calendar_event_card.dart`:
- Material 3 card showing extracted event details
- Editable fields: title, date, time
- Action buttons

Voice mode integration in `lib/services/voice_session_orchestrator.dart`:
- When calendar intent detected in voice mode: TTS reads extracted details aloud
- "Add 'Team Meeting' on Tuesday at 3pm to your calendar?"
- Verbal "yes" → create, "no" → dismiss, "change the time to 4pm" → re-extract and re-confirm

### Task 8: OAuth-During-Voice-Mode Deferral

Modify `lib/providers/session_providers.dart`:
- If calendar intent fires but Google is not connected AND voice mode is active:
  - Queue event details in `CalendarEvents` table with status `PENDING`
  - TTS: "I'd need to connect to your Google Calendar first. I'll remind you when we're done."
  - Continue conversation normally
- After session ends: if pending events exist, show a card on the session list screen

Modify `lib/ui/screens/session_list_screen.dart`:
- Optional banner at top when pending (unconnected) calendar events exist
- Tapping banner → Google sign-in flow → review pending events

### Task 9: Calendar Settings Card

Modify `lib/ui/screens/settings_screen.dart`:
- New `_buildCalendarCard()` between Location and Data Management cards
- Google account connection status + Connect/Disconnect button
- "Auto-suggest calendar events" toggle (default: on)
- "Require confirmation before creating" toggle (default: on, non-disableable in v1 — always confirm)

### Task 10: Supabase Migration (Optional Cloud Sync)

Create `supabase/migrations/003_events_schema.sql`:
- `calendar_events` table mirroring local schema
- RLS: `auth.uid() = user_id`
- Note: Cloud sync for events is lower priority than sessions/photos. The local table is the source of truth; cloud backup follows the existing UPSERT pattern from `SyncRepository`.

Extend `lib/repositories/sync_repository.dart`:
- `buildEventUpsertMap()` for calendar events
- Sync events as part of `syncPendingSessions()` or as a separate `syncPendingEvents()`

## Acceptance Criteria

- [ ] AC1: Google OAuth sign-in/sign-out works with `calendar.events` scope
- [ ] AC2: OAuth tokens stored in `flutter_secure_storage`, not SharedPreferences
- [ ] AC3: Intent classifier returns ranked multi-intent results
- [ ] AC4: Existing recall classification does not regress (all current `query` test cases pass)
- [ ] AC5: Calendar intent detected for phrases like "add meeting tomorrow at 3pm"
- [ ] AC6: Reminder intent detected for phrases like "remind me to call Mom on Friday"
- [ ] AC7: Extracted event details shown to user for confirmation before creation
- [ ] AC8: "Add to Calendar" creates event in Google Calendar
- [ ] AC9: Voice mode reads extracted details aloud and accepts verbal yes/no/edit
- [ ] AC10: If Google not connected during voice mode, event queued for post-session
- [ ] AC11: Calendar settings card shows connection status and toggles
- [ ] AC12: Schema v5 migration adds CalendarEvents table
- [ ] AC13: Quality gate passes (>=80% coverage, 0 lint errors, all tests pass)

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| OAuth2 complexity (consent, token refresh, scopes) | High | Use `google_sign_in` SDK which handles most complexity; personal app avoids Google verification |
| Intent taxonomy redesign regresses recall | High | Comprehensive regression test suite on all existing classify() test cases; ship classifier redesign as a standalone PR before adding calendar routing |
| Temporal expression parsing accuracy | High | Use the LLM for extraction (not regex); Layer A fallback is explicitly limited |
| False positive calendar intent detection | Medium | Confirmation requirement prevents unwanted event creation |
| OAuth callback handling in voice mode | Medium | Deferral pattern queues events, avoids screen interruption |
| `google_sign_in` version compatibility | Low | Pin version; widely used, stable package |

## Affected Components

**New files (lib):**
- `lib/services/google_auth_service.dart`
- `lib/services/google_calendar_service.dart`
- `lib/services/event_extraction_service.dart`
- `lib/providers/calendar_providers.dart`
- `lib/database/daos/calendar_event_dao.dart`
- `lib/ui/widgets/calendar_event_card.dart`

**Modified files (lib):**
- `lib/database/tables.dart` (CalendarEvents table)
- `lib/database/app_database.dart` (schema v5, migration)
- `lib/database/daos/session_dao.dart` (cascade delete for events)
- `lib/services/intent_classifier.dart` (multi-intent redesign)
- `lib/providers/session_providers.dart` (calendar intent routing, pendingCalendarEvent)
- `lib/repositories/sync_repository.dart` (event sync)
- `lib/ui/screens/journal_session_screen.dart` (confirmation card)
- `lib/ui/screens/session_list_screen.dart` (pending events banner)
- `lib/ui/screens/settings_screen.dart` (calendar card)
- `lib/services/voice_session_orchestrator.dart` (verbal calendar confirmation)
- `pubspec.yaml` (3 new dependencies)

**New files (other):**
- `docs/adr/ADR-0020-google-calendar-integration.md`
- `supabase/migrations/003_events_schema.sql`

**New test files:**
- `test/services/intent_classifier_calendar_test.dart`
- `test/services/google_auth_service_test.dart`
- `test/services/google_calendar_service_test.dart`
- `test/services/event_extraction_service_test.dart`
- `test/database/calendar_event_dao_test.dart`
- `test/database/migration_v5_test.dart`
- `test/providers/calendar_providers_test.dart`
- `test/ui/widgets/calendar_event_card_test.dart`
- `test/ui/settings_screen_calendar_test.dart`

## Dependencies

**Depends on:**
- Phase 10 complete (schema v4 — merged)
- Phase 7B voice mode (for verbal confirmation flow)
- Phase 8 ConversationLayer (for LLM-based event extraction)

**New package dependencies:**
```yaml
google_sign_in: ^6.2.2
googleapis: ^13.2.0
extension_google_sign_in_as_googleapis_auth: ^2.0.13
```

## Execution Order

1. Task 1: ADR-0020 (decisions before code)
2. Task 2: Intent classifier redesign (highest risk, standalone testable)
3. Task 3: Google Auth Service (OAuth — standalone testable)
4. Task 6: Schema v5 + CalendarEventDao (foundation for storage)
5. Task 4 + 5: Calendar Service + Event Extraction (can parallelize after 3+6)
6. Task 7: Confirmation Flow UI (depends on 2+5+6)
7. Task 8: OAuth deferral in voice mode (depends on 7)
8. Task 9: Calendar Settings Card (depends on 3)
9. Task 10: Supabase migration + sync (depends on 4+6)
