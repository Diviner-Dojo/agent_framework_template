---
adr_id: ADR-0020
title: Google Calendar Integration
status: accepted
date: 2026-02-25
supersedes: null
decision_makers: [developer, facilitator, architecture-consultant, security-specialist]
discussion_id: DISC-20260224-205141-phase11-calendar-spec-review
---

## Context

Phase 11 adds Google Calendar integration so the AI journal companion can detect calendar-related intents during conversation, extract event details, and create events with user confirmation (SPEC-20260225-120000).

This requires decisions on: OAuth architecture, intent classification redesign, event extraction validation, token management, and voice mode interaction patterns.

## Decision

### 1. Calendar API Access: Direct from Device (ADR-0005 Deviation)

Google Calendar API calls go **direct from the device** using the user's own OAuth token, rather than through the Supabase Edge Function proxy used for Claude API calls (ADR-0005).

**Rationale for deviation**: ADR-0005 protects a **fixed API key** (Claude) that is a shared secret — if embedded in the app, any user could extract it and make API calls billed to the developer. Google OAuth tokens are fundamentally different: they are **per-user credentials** that the user authenticates directly with Google to obtain. No server secret is involved. The user is both the principal and the resource owner.

**Mitigating controls**:
- OAuth tokens stored in `flutter_secure_storage` (Android Keystore-backed on non-rooted devices)
- `google_sign_in` SDK manages token refresh lifecycle automatically
- Token revocation on sign-out clears both local and server-side tokens
- Scope is minimized (see below)

### 2. OAuth Scope Minimization

Request `https://www.googleapis.com/auth/calendar.events` scope (create/edit events). Google does not offer a narrower `calendar.events.owned` scope that limits mutation to app-created events. The full `calendar.events` scope grants create, edit, and delete access to all events on the user's calendar.

**Mitigating control**: The app only calls `events.insert()` — never `events.update()`, `events.delete()`, or `events.list()`. The confirmation gate (always-on in v1) prevents unintended event creation.

**Scope minimization constraint**: Documented here because a narrower scope is not available from Google. If Google introduces `calendar.events.create` in the future, migrate to it.

### 3. Intent Taxonomy Redesign

Expand `IntentClassifier` from 2 types to 4:
- `journal` — normal journaling (existing)
- `query` — recall about past entries (existing)
- `calendarEvent` — create/schedule an event
- `reminder` — set a reminder

**Multi-intent ranking**: The classifier returns a ranked list of `IntentResult` objects rather than a single result. The top-ranked intent drives routing. This allows overlapping signals (e.g., temporal references scoring for both recall and calendar) to be resolved by comparing confidence scores rather than exclusive if/else branching.

**Temporal disambiguation**: Temporal references score for recall ONLY with past-tense question structure. Calendar/reminder score when temporal references combine with future-tense imperative/action verbs.

### 4. Event Extraction Routing

Event extraction uses **direct LLM calls** (ClaudeApiService or local LLM), bypassing the ConversationLayer strategy interface. This matches the existing pattern for recall queries (`_handleRecallQuery()` calls `_claudeApiService.recall()` directly at session_providers.dart line 886).

**Strict output validation**: LLM extraction output is validated against a strict schema before any Calendar API call:
- Title: non-empty, max 200 characters
- DateTime: valid ISO 8601, within range [today - 1 day, today + 2 years]
- No unexpected keys forwarded
- Malformed JSON returns typed `ExtractionError`, never thrown as exception

### 5. Event Lifecycle State vs Sync State

`CalendarEvents` table uses **two separate columns**:
- `status`: event lifecycle — `PENDING_CREATE | CONFIRMED | FAILED | CANCELLED`
- `syncStatus`: cloud sync — `PENDING | SYNCED | FAILED`

These are independent state machines. An event can be `CONFIRMED` (created in Google Calendar) but `PENDING` sync (not yet backed up to Supabase).

### 6. OAuth Token Storage

All Google OAuth tokens stored in `flutter_secure_storage`, consistent with the project security baseline. Never in SharedPreferences (plain XML) or SQLite.

### 7. OAuth-During-Voice-Mode Deferral

If a calendar intent fires during voice mode and Google is not connected:
- Event details are queued in `CalendarEvents` with status `PENDING_CREATE`
- TTS announces: "I'd need to connect to your Google Calendar first. I'll remind you when we're done."
- Conversation continues normally
- State ownership: `pendingCalendarEvent` field in `SessionState`
- Queue cap: max 5 pending events per session
- Post-session: pending events banner on session list screen

### 8. Event Confirmation Policy

Events are **never auto-created**. User must explicitly confirm via:
- Text mode: "Add to Calendar" button on inline confirmation card
- Voice mode: verbal "yes" after TTS reads extracted details
- "Require confirmation" toggle is always-on in v1 (cannot be disabled)

### 9. Verbal Edit Flow

In voice mode, after TTS reads extracted details:
- "yes" → create event
- "no" → dismiss
- "change the time to 4pm" / "wrong day" → re-extract with correction context, re-confirm
- Silence timeout → dismiss (do not auto-create)

## Alternatives Considered

- **Server-side proxy for Calendar API** (ADR-0005 pattern): Rejected because Google OAuth tokens are per-user credentials, not shared secrets. Proxying adds latency, server cost, and a point of failure without security benefit.
- **Apple EventKit / platform-native calendar**: Rejected because it locks to a single platform. Google Calendar is cross-platform and explicitly requested.
- **Single intent type with sub-routing**: Rejected in favor of 4-type taxonomy. A single "action" intent would need a secondary classifier, adding complexity without improving accuracy.
- **Auto-create events without confirmation**: Rejected for safety — misclassified intents or extraction errors could create unwanted events on the user's real calendar.

## Consequences

- Google OAuth adds a third authentication provider (Supabase Auth, Google Sign-In, plus unauthenticated local-only mode). Settings screen must clearly distinguish between Supabase cloud sync auth and Google Calendar auth.
- Intent classifier redesign requires comprehensive regression testing to avoid breaking existing recall classification.
- The ADR-0005 deviation is specific to user-owned OAuth tokens. Any future integration requiring a developer-owned API key must still use the Edge Function proxy pattern.

## References

- ADR-0005: Claude API via Supabase Edge Function Proxy
- ADR-0013: Search + Memory Recall Architecture
- ADR-0017: Local LLM Layer Architecture
- SPEC-20260225-120000: Phase 11 spec
- DISC-20260224-205141-phase11-calendar-spec-review: Spec review discussion
