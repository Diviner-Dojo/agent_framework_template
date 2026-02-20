---
id: SPEC-20260220-phase4-cloud-sync
title: "Phase 4: Cloud Sync & Optional Auth"
status: approved
created: 2026-02-20
phase: 4
estimated_tasks: 15
adr_refs: [ADR-0012]
---

# Phase 4: Cloud Sync & Optional Auth

## Goal

Enable uploading journal sessions from the phone to Supabase PostgreSQL so the data is accessible in the cloud for data work (querying, analysis, Jupyter, etc.). Auth is optional — the app works fully offline without login. When the user signs in, sync activates.

## Sync Scope

- **Upload only**: phone → Supabase PostgreSQL
- Once in Supabase, data is queryable via: Dashboard SQL editor, REST API, direct PostgreSQL connection, Python/pandas/Jupyter, JS/Python client libraries
- Upload-only does NOT download cloud data to a second device (multi-device is future Phase 4b)

## Auth Model

- Optional. The app works fully offline without login.
- When the user signs in (Supabase Auth, email+password), sync activates.
- This preserves the instant-on journaling experience.

## Pre-Implementation: Manual Supabase Setup

Before running the app with sync enabled, the developer must:
1. Run the migration SQL in the Supabase Dashboard SQL editor
2. Enable Email Auth in Supabase Dashboard → Authentication → Providers
3. Add `SUPABASE_JWT_SECRET` to Edge Function secrets
4. Update `--dart-define` flags with Supabase URL and anon key (already done for Phase 3)

---

## Tasks

### Task 1: ADR-0012 + Dependencies
**Files**: `docs/adr/ADR-0012-optional-auth-upload-sync.md`, `pubspec.yaml`
- Write ADR documenting: optional auth, upload-only sync, JWT upgrade, Supabase Auth choice
- Add dependencies: `supabase_flutter: ^2.8.0`, `flutter_secure_storage: ^9.2.0`
- Note: WorkManager deferred to Phase 4b (periodic background sync) — Phase 4a uses on-demand sync only (on session end + manual "Sync Now") to reduce scope
- **Checkpoint**: exempt (ADR + dependency config)

### Task 2: Supabase Migration SQL
**File**: `supabase/migrations/001_initial_schema.sql`
- Tables: `journal_sessions`, `journal_messages`, `entry_embeddings`
- RLS policies: users can only CRUD their own data (`auth.uid() = user_id`)
- Indexes: user+date, session messages, sync status, full-text trigram
- Extensions: `vector` (pgvector for future RAG), `pg_trgm` (full-text search)
- **Checkpoint**: trigger → Database schema (performance-analyst, security-specialist)

### Task 3: SupabaseService
**File**: `lib/services/supabase_service.dart`
- Wraps `supabase_flutter` client initialization
- Auth methods: `signUp(email, password)`, `signIn(email, password)`, `signOut()`, `currentUser`, `onAuthStateChange` stream
- `accessToken` getter — returns current JWT or null
- Guarded: all methods return null/no-op when not configured (optional auth)
- Token persistence handled by supabase_flutter internally (uses flutter_secure_storage under the hood)
- Reuse: `Environment.isConfigured` check pattern from `ClaudeApiService`
- **Checkpoint**: trigger → Security-relevant (security-specialist, architecture-consultant)

### Task 4: Auth Providers
**File**: `lib/providers/auth_providers.dart`
- `supabaseServiceProvider` — singleton SupabaseService
- `authStateProvider` — StreamProvider wrapping `onAuthStateChange`
- `isAuthenticatedProvider` — derived bool from authStateProvider
- `currentUserProvider` — derived user info
- **Checkpoint**: trigger → State management (architecture-consultant, qa-specialist)

### Task 5: Auth UI Screen
**File**: `lib/ui/screens/auth_screen.dart`
- Email + password form with sign in / sign up toggle
- Error display (invalid credentials, network error, etc.)
- "Skip" button — optional auth means user can dismiss
- Loading state during auth call
- On success: pop back to settings or previous screen
- **Checkpoint**: trigger → UI flow / navigation (ux-evaluator, qa-specialist)

### Task 6: Routing + Settings Integration
**Files**: `lib/app.dart`, `lib/ui/screens/settings_screen.dart`
- Add `/auth` route to app.dart
- Settings screen: add "Cloud Sync" card above "About" card
  - If not authenticated: "Sign in to sync your journal to the cloud" + Sign In button → `/auth`
  - If authenticated: show email, sign out button, sync status, "Sync Now" button
- **Checkpoint**: trigger → UI flow / navigation (ux-evaluator, qa-specialist)

### Task 7: Edge Function JWT Upgrade
**File**: `supabase/functions/claude-proxy/index.ts`
- Replace PROXY_ACCESS_KEY check with JWT validation using Supabase client
- Keep PROXY_ACCESS_KEY as fallback for unauthenticated mode (when user hasn't signed in, Edge Function still works with the old key)
- **Checkpoint**: trigger → Security-relevant + External API (security-specialist, architecture-consultant)

### Task 8: ClaudeApiService JWT Injection
**File**: `lib/services/claude_api_service.dart`
- Add optional `accessToken` parameter to constructor or inject via a token provider
- When authenticated: send JWT as `Authorization: Bearer <jwt>`
- When not authenticated: keep existing behavior (anon key as Bearer)
- Reuse: existing `_createDefaultDio` pattern, extend headers
- **Checkpoint**: trigger → Security-relevant (security-specialist, architecture-consultant)

### Task 9: Sync DAO Methods
**Files**: `lib/database/daos/session_dao.dart`, `lib/database/daos/message_dao.dart`
- `SessionDao.getSessionsToSync()` — query where syncStatus is 'PENDING' or 'FAILED'
- `SessionDao.updateSyncStatus(sessionId, status, lastAttempt)` — update status + timestamp
- `MessageDao.getMessagesForSession(sessionId)` — already exists, confirm coverage
- **Checkpoint**: trigger → Database schema (performance-analyst, security-specialist)

### Task 10: SyncRepository
**File**: `lib/repositories/sync_repository.dart`
- `syncPendingSessions()` — main sync loop:
  1. Query drift for sessions where syncStatus != 'SYNCED'
  2. For each session: upload session row + all messages via Supabase client
  3. Use UPSERT (ON CONFLICT DO UPDATE) for idempotency (per ADR-0004)
  4. On success: update syncStatus to 'SYNCED'
  5. On failure: update syncStatus to 'FAILED', record lastSyncAttempt
  6. Return sync result summary (synced count, failed count)
- `syncSession(sessionId)` — sync a single session (used after endSession)
- Requires authenticated SupabaseService (no-op if not authenticated)
- **Checkpoint**: trigger → External API (security-specialist, performance-analyst)

### Task 11: Sync Providers
**File**: `lib/providers/sync_providers.dart`
- `syncRepositoryProvider` — depends on SupabaseService, SessionDao, MessageDao
- `pendingSyncCountProvider` — StreamProvider watching sessions where syncStatus != 'SYNCED'
- `syncNowProvider` — FutureProvider.family for manual sync trigger
- **Checkpoint**: trigger → State management (architecture-consultant, qa-specialist)

### Task 12: Session Lifecycle + Sync Trigger
**File**: `lib/providers/session_providers.dart`
- After `endSession()` completes: if authenticated, trigger `syncSession(sessionId)`
- Non-blocking: sync failure doesn't affect the session closing flow
- Use existing `ConnectivityService` to check online status before attempting
- **Checkpoint**: trigger → State management (architecture-consultant, qa-specialist)

### Task 13: Sync Status UI
**Files**: `lib/ui/widgets/sync_status_indicator.dart`, `lib/ui/widgets/session_card.dart`, `lib/ui/screens/settings_screen.dart`
- `SyncStatusIndicator` widget: small icon showing SYNCED/PENDING/FAILED
- Add to `SessionCard` — show sync indicator per session
- Settings "Cloud Sync" card: show pending count, last sync time, "Sync Now" button
- "Sync Now" button calls `syncPendingSessions()` with loading indicator
- **Checkpoint**: trigger → UI flow / navigation (ux-evaluator, qa-specialist)

### Task 14: Supabase Initialization
**File**: `lib/main.dart`
- Initialize Supabase client in main() (before runApp)
- Conditional: only if `Environment.isConfigured`
- `await Supabase.initialize(url: env.supabaseUrl, anonKey: env.supabaseAnonKey)`
- **Checkpoint**: exempt (app initialization config)

### Task 15: Tests
**Files**: multiple test files
- `test/services/supabase_service_test.dart` — auth methods, guard behavior
- `test/providers/auth_providers_test.dart` — provider wiring, auth state
- `test/repositories/sync_repository_test.dart` — sync logic, status updates, error handling
- `test/providers/sync_providers_test.dart` — provider wiring
- `test/providers/session_notifier_sync_test.dart` — sync trigger after endSession
- Widget tests for auth screen, sync status indicator
- **Checkpoint**: exempt (pure test writing)

---

## Key Reuse Points

| Existing Code | Reuse In |
|---|---|
| `Environment.isConfigured` (`lib/config/environment.dart:74`) | SupabaseService guard, main.dart init |
| `SyncStatus` enum (`lib/models/sync_status.dart`) | SyncRepository, sync DAO methods, UI |
| `ConnectivityService` (`lib/services/connectivity_service.dart`) | SyncRepository online check |
| `JournalSessions.syncStatus` column (`lib/database/tables.dart:59`) | Sync DAO queries |
| `ClaudeApiService._createDefaultDio` pattern (`lib/services/claude_api_service.dart:107-139`) | JWT header injection |
| `SettingsScreen._buildAssistantCard` pattern (`lib/ui/screens/settings_screen.dart:73-145`) | Cloud Sync card structure |

## Deferred to Phase 4b

- **WorkManager background sync**: Periodic 15-min background sync. Phase 4a uses on-demand sync only.
- **Multi-device download**: Downloading cloud data to a second phone.
- **Sync conflict resolution**: Last-write-wins is sufficient for single-user upload-only.

## Verification

1. `flutter test --reporter expanded` — all tests pass
2. `dart analyze lib/ test/` — no issues
3. `dart format --set-exit-if-changed lib/ test/` — formatted
4. `python scripts/quality_gate.py` — all checks pass, coverage >= 80%
5. Manual: sign in, create session, end session, verify data in Supabase Dashboard
