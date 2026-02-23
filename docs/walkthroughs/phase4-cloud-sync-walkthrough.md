---
walkthrough_id: WALK-20260222-phase4
title: "Phase 4: Cloud Sync with Supabase — Guided Walkthrough"
target_audience: "Developers new to cloud sync architecture"
estimated_time: "20-30 minutes"
modules:
  - supabase_service.dart
  - sync_repository.dart
  - auth_providers.dart
  - sync_providers.dart
  - auth_screen.dart
  - settings_screen.dart
  - sync_status.dart
  - sync_status_indicator.dart
  - "001_initial_schema.sql"
related_adrs:
  - ADR-0012
  - ADR-0004
  - ADR-0005
---

# Phase 4: Cloud Sync with Supabase — Guided Walkthrough

## The Big Picture (2 min) — Optional Auth + Upload-Only Philosophy

Before diving into code, understand the core design decision that shapes everything in Phase 4.

**The Problem**: The app works beautifully offline with SQLite, but journal data lives trapped on the phone. The developer wants to query and analyze entries using Python/pandas, Jupyter notebooks, and direct SQL queries — this requires the data in a real cloud database (Supabase PostgreSQL).

**The Constraint**: The app's core value is *instant journaling* — no login barrier. Requiring sign-in before first use kills the user experience (see ADR-0012 for the full trade-off analysis).

**The Solution**: Make auth *optional*. The app works identically with or without a Supabase account. When signed in, journal data automatically syncs to the cloud. When offline or unsigned, everything still works locally.

**Upload-Only Logic**: Sync is one-way: phone → cloud. The phone is the source of truth. Data flows outward to Supabase, but doesn't flow back down (multi-device download is deferred to Phase 4b). This keeps the sync logic simple and makes retries safe via UPSERT.

**When Sync Happens**: Two triggers:
1. **Automatic on session end**: When the user ends a journaling session, `endSession()` triggers `syncSession()` immediately (fire-and-forget).
2. **Manual "Sync Now" button**: In Settings, the user can tap "Sync Now" to upload any pending sessions.

**Key ADR References**:
- **ADR-0012**: The overarching decision to make auth optional with upload-only sync
- **ADR-0004**: Offline-first architecture — UPSERT ensures retries are safe and idempotent
- **ADR-0005**: Supabase Edge Functions for Claude API proxying (the existing JWT auth path)

---

## Section 1: Auth Layer — From Device to JWT

### 1.1 SupabaseService: The Auth Wrapper

**File**: `/lib/services/supabase_service.dart` (165 lines)

**Purpose**: Wrap Supabase's auth methods in a thin service layer. Guard everything with `isConfigured` so the app works when Supabase is not configured (development without Supabase credentials, or end users with an older build).

**Key Design Decisions**:

1. **Configuration Guard** (lines 61–62)
   ```dart
   bool get isConfigured => _environment.isConfigured;
   ```
   All public methods check `isConfigured` before calling Supabase. If not configured, they return `null` or no-op. This is not error handling — it's *graceful degradation*. The app doesn't crash or throw; it simply behaves as if the user has not signed in.

2. **Auth State Stream** (lines 139–141)
   ```dart
   Stream<AuthState> get onAuthStateChange {
     if (!isConfigured) return const Stream.empty();
     return _client.auth.onAuthStateChange;
   }
   ```
   Supabase emits `AuthState` events whenever the user signs in, signs out, or the token is refreshed. This stream powers the reactive UI — listen to it, and your UI updates automatically without polling.

3. **JWT Access Token** (lines 144–151)
   ```dart
   String? get accessToken {
     if (!isConfigured) return null;
     return _client.auth.currentSession?.accessToken;
   }
   ```
   The Supabase JWT is the key to authenticated requests. Two consumers use it:
   - **ClaudeApiService** (Phase 3): Sends the JWT when calling `claude-proxy` Edge Function
   - **SyncRepository** (Phase 4): Not shown in this code, but the JWT is available for future Edge Function integrations

4. **Typed Exceptions** (lines 31–43)
   ```dart
   class SupabaseAuthException extends SupabaseServiceException {
     const SupabaseAuthException(super.message);
   }
   ```
   Wrap Supabase's generic `AuthException` in a typed exception. The UI can catch `SupabaseAuthException` and display it safely (not showing raw HTTP errors to the user).

**Three Auth Methods** (lines 71–124):
- `signUp(email, password)` → creates a new account (Phase 4 allows email+password signup)
- `signIn(email, password)` → signs in an existing account
- `signOut()` → clears the session (no-op if not configured)

**Design Principle**: The service *delegates*, it doesn't orchestrate. It's a thin wrapper — no retry logic, no caching, just pass-through to the Supabase client. Business logic lives in the repository and providers.

---

### 1.2 Auth Providers: Riverpod-Powered Reactivity

**File**: `/lib/providers/auth_providers.dart` (58 lines)

**Purpose**: Expose Supabase's auth state as Riverpod providers so the UI can react to auth changes without polling or manual callbacks.

**Three-Layer Provider Hierarchy**:

1. **supabaseServiceProvider** (lines 22–25)
   ```dart
   final supabaseServiceProvider = Provider<SupabaseService>((ref) {
     final environment = ref.watch(environmentProvider);
     return SupabaseService(environment: environment);
   });
   ```
   The base — depends on `environmentProvider` (loaded from `--dart-define` flags). Creates a singleton SupabaseService.

2. **authStateProvider** (lines 31–34)
   ```dart
   final authStateProvider = StreamProvider<AuthState>((ref) {
     final service = ref.watch(supabaseServiceProvider);
     return service.onAuthStateChange;
   });
   ```
   Wraps the auth state stream. When a user signs in/out, Supabase emits an `AuthState` event, and this provider re-evaluates all dependents. Use `StreamProvider` because auth changes are *events*, not a stable value.

3. **Derived Providers** (lines 42–57)
   ```dart
   final isAuthenticatedProvider = Provider<bool>((ref) {
     final service = ref.watch(supabaseServiceProvider);
     ref.watch(authStateProvider);  // Invalidate on auth change
     return service.isAuthenticated;
   });
   ```
   `isAuthenticatedProvider` is a plain `Provider` (returns a value, not a stream) but *depends* on `authStateProvider`. When auth state changes, Riverpod invalidates this provider, and the UI re-builds with the new `isAuthenticated` value.

   Similar for `currentUserProvider` — returns the signed-in `User` object or `null`.

**Why This Pattern?**: Riverpod providers decouple the UI from the service. The UI doesn't import `SupabaseService` directly — it watches providers. If you swap the auth implementation (Firebase → Supabase), the UI sees no change.

---

### 1.3 AuthScreen: The Sign In / Sign Up UI

**File**: `/lib/ui/screens/auth_screen.dart` (220 lines)

**Purpose**: Simple email+password form with a critical affordance: a "Skip" button. Auth is optional, so users can always dismiss this screen and continue journaling offline.

**Key Features**:

1. **Toggle Sign In ↔ Sign Up** (lines 35, 198–211)
   ```dart
   bool _isSignUp = false;
   ```
   Single form that switches modes. Create account? Toggle `_isSignUp`, reuse the same email/password fields, change the button label and heading.

2. **Form Validation** (lines 147–177)
   - Email: Required, must contain `@` and `.`
   - Password: Required, minimum 6 characters for sign-up

   Validation is client-side only. Server-side validation (duplicate email, weak password) happens in `signUp()` and throws `SupabaseAuthException`, caught and displayed (lines 70–73).

3. **Error Display** (lines 122–135)
   ```dart
   if (_errorMessage != null) ...[
     Container(
       padding: const EdgeInsets.all(12),
       decoration: BoxDecoration(
         color: theme.colorScheme.errorContainer,
         borderRadius: BorderRadius.circular(8),
       ),
       child: Text(_errorMessage!, ...),
     ),
   ]
   ```
   Catches `SupabaseAuthException` and displays the message in a styled error box. Examples: "User already registered", "Invalid login credentials".

4. **Loading State** (lines 49–51, 183–193)
   ```dart
   setState(() {
     _isLoading = true;
     _errorMessage = null;
   });
   ```
   During `signUp()` or `signIn()`, the submit button shows a spinner and is disabled. Prevents double-taps.

5. **Skip Button** (lines 94–99)
   ```dart
   TextButton(
     onPressed: () => Navigator.of(context).pop(),
     child: const Text('Skip'),
   ),
   ```
   **Critical for optional auth**: User can dismiss the auth screen at any time and return to journaling offline. This is the core principle of ADR-0012.

6. **On Success** (lines 67–69)
   ```dart
   if (mounted) {
     Navigator.of(context).pop();
   }
   ```
   After successful sign in/up, pop back to Settings. The auth state change is picked up by `authStateProvider`, which cascades through `isAuthenticatedProvider` → UI re-builds.

---

## Section 2: Sync Layer — From Local Database to Cloud

### 2.1 SyncRepository: The Upload Engine

**File**: `/lib/repositories/sync_repository.dart` (186 lines)

**Purpose**: Implement the core sync logic — fetch pending/failed sessions from SQLite, UPSERT them to Supabase PostgreSQL, and update local sync status.

**Three Public Methods**:

1. **syncPendingSessions()** (lines 60–96)
   ```dart
   Future<SyncResult> syncPendingSessions() async {
     if (!_supabaseService.isAuthenticated) {
       return const SyncResult();
     }

     final sessionsToSync = await _sessionDao.getSessionsToSync();
     // Loop through and uploadSession each one
   }
   ```
   Called from the "Sync Now" button or manually from integration tests. Syncs *all* pending and failed sessions. Returns a `SyncResult` with counts and errors.

   **Guard**: If not authenticated, return early with empty result (no-op). No error, no log entry — auth is optional.

2. **syncSession()** (lines 102–125)
   ```dart
   Future<void> syncSession(String sessionId) async {
     if (!_supabaseService.isAuthenticated) return;

     final session = await _sessionDao.getSessionById(sessionId);
     // uploadSession + update sync status
   }
   ```
   Called automatically after `endSession()` completes. Syncs a *single* session. Fire-and-forget — doesn't wait for the result or report errors to the UI (that's for Phase 4b background sync with user notifications).

3. **uploadSession()** (lines 138–184, marked `@visibleForTesting`)
   ```dart
   Future<void> uploadSession(JournalSession session) async {
     final client = _supabaseService.client;
     if (client == null) return;

     // UPSERT session
     await client.from('journal_sessions').upsert({...});

     // UPSERT messages
     await client.from('journal_messages').upsert(messageRows);
   }
   ```
   The heart of sync. Two separate calls (not atomic):
   - First: UPSERT the session row to `journal_sessions`
   - Second: UPSERT all messages for that session to `journal_messages`

**Why Two Calls (Not One Transaction)?**
- If the session UPSERT succeeds but messages fail, the session row is already in Supabase.
- If sync is retried, the UPSERT is idempotent (per ADR-0004) — the session is updated, messages are re-uploaded.
- One atomic transaction would be "cleaner" but adds complexity. The idempotent design makes retries safe without nested transactions.

**UPSERT for Idempotency** (lines 146–159)
```dart
await client.from('journal_sessions').upsert({
  'session_id': session.sessionId,
  'user_id': userId,
  'start_time': session.startTime.toUtc().toIso8601String(),
  // ... other fields
  'sync_status': 'SYNCED',
  'updated_at': DateTime.now().toUtc().toIso8601String(),
});
```
The UPSERT is keyed on `session_id` (the primary key). If the session already exists in Supabase (from a previous sync attempt), the row is updated with the latest values, not duplicated. This is why retries are safe — idempotency is enforced at the database layer, not the application layer.

**Error Handling** (lines 73–92)
```dart
try {
  await uploadSession(session);
  await _sessionDao.updateSyncStatus(sessionId, 'SYNCED', ...);
  synced++;
} on Exception catch (e) {
  await _sessionDao.updateSyncStatus(sessionId, 'FAILED', ...);
  failed++;
  errors.add('Session $sessionId: $e');
}
```
If any exception occurs during upload, catch it, mark the session as FAILED locally, and continue looping. This ensures one failed session doesn't block others.

**SyncResult Model** (lines 24–36)
```dart
class SyncResult {
  final int syncedCount;
  final int failedCount;
  final List<String> errors;
}
```
Tracks the outcome. Used by tests and future analytics.

---

### 2.2 Sync Providers: Wiring the Repository

**File**: `/lib/providers/sync_providers.dart` (42 lines)

**Purpose**: Expose SyncRepository and pending sync count as Riverpod providers.

**Two Providers**:

1. **syncRepositoryProvider** (lines 20–29)
   ```dart
   final syncRepositoryProvider = Provider<SyncRepository>((ref) {
     final supabaseService = ref.watch(supabaseServiceProvider);
     final sessionDao = ref.watch(sessionDaoProvider);
     final messageDao = ref.watch(messageDaoProvider);
     return SyncRepository(
       supabaseService: supabaseService,
       sessionDao: sessionDao,
       messageDao: messageDao,
     );
   });
   ```
   Dependency injection. Wires up the repository with its three dependencies. The UI uses `ref.read(syncRepositoryProvider)` to get the repository and call `syncPendingSessions()`.

2. **pendingSyncCountProvider** (lines 35–41)
   ```dart
   final pendingSyncCountProvider = StreamProvider<int>((ref) {
     final isAuthenticated = ref.watch(isAuthenticatedProvider);
     if (!isAuthenticated) return Stream.value(0);

     final sessionDao = ref.watch(sessionDaoProvider);
     return sessionDao.watchPendingSyncCount();
   });
   ```
   A stream of pending sync counts. When not authenticated, immediately returns 0 (no sessions to sync). When authenticated, watches the database for changes — the UI updates in real-time as sync status changes.

---

### 2.3 Settings Screen: Cloud Sync Card Integration

**File**: `/lib/ui/screens/settings_screen.dart` (290 lines, focusing on `_buildCloudSyncCard`)

**Purpose**: The main UI for sync controls. Show auth state, pending count, and action buttons.

**Unauthenticated State** (lines 167–179)
```dart
if (!isAuthenticated) ...[
  Text('Sign in to sync your journal to the cloud', ...),
  FilledButton.icon(
    onPressed: () => Navigator.of(context).pushNamed('/auth'),
    icon: const Icon(Icons.cloud_upload_outlined),
    label: const Text('Sign In'),
  ),
]
```
If `isAuthenticatedProvider` returns `false`, show a brief explanation and a "Sign In" button that navigates to AuthScreen.

**Authenticated State** (lines 180–250)
```dart
else ...[
  // Show signed-in email
  Row(
    children: [
      const Icon(Icons.check_circle, color: Colors.green, size: 20),
      Expanded(
        child: Text(currentUser?.email ?? 'Signed in', ...),
      ),
    ],
  ),

  // Show pending count
  pendingSyncAsync.when(
    data: (count) => count > 0
        ? Text('$count session${count == 1 ? '' : 's'} pending sync', ...)
        : Text('All sessions synced', ...),
    loading: () => Text('Checking sync status...'),
    error: (_, _) => const SizedBox.shrink(),
  ),

  // Sync Now and Sign Out buttons
  Row(
    children: [
      FilledButton.icon(
        onPressed: () async {
          final syncRepo = ref.read(syncRepositoryProvider);
          await syncRepo.syncPendingSessions();
          ref.invalidate(pendingSyncCountProvider);
        },
        icon: const Icon(Icons.sync),
        label: const Text('Sync Now'),
      ),
      OutlinedButton(
        onPressed: () async {
          final service = ref.read(supabaseServiceProvider);
          await service.signOut();
        },
        child: const Text('Sign Out'),
      ),
    ],
  ),
]
```

**Key Interactions**:
1. Watch `isAuthenticatedProvider` to conditionally render
2. Watch `currentUserProvider` to show the email
3. Watch `pendingSyncCountProvider` to show pending count (reactive)
4. On "Sync Now", call `syncPendingSessions()`, then invalidate the pending count provider to refresh the UI
5. On "Sign Out", call `signOut()` (which triggers `authStateProvider` to emit a change, cascading to all dependent providers)

---

## Section 3: Cloud Schema — PostgreSQL Design

### 3.1 Database Tables

**File**: `/supabase/migrations/001_initial_schema.sql` (110 lines)

**Purpose**: Cloud-side tables that mirror the local drift schema. Designed for multi-user access with Row Level Security (RLS) so each user sees only their data.

**Table 1: journal_sessions** (lines 21–34)
```sql
CREATE TABLE journal_sessions (
    session_id     UUID PRIMARY KEY,
    user_id        UUID NOT NULL REFERENCES auth.users(id),
    start_time     TIMESTAMPTZ NOT NULL,
    end_time       TIMESTAMPTZ,
    timezone       TEXT NOT NULL DEFAULT 'UTC',
    summary        TEXT,
    mood_tags      JSONB DEFAULT '[]'::jsonb,
    people         JSONB DEFAULT '[]'::jsonb,
    topic_tags     JSONB DEFAULT '[]'::jsonb,
    sync_status    TEXT NOT NULL DEFAULT 'SYNCED',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Key design decisions:
- **UUID Primary Key**: Sessions are created on the phone with `uuid.v4()`, synced up as-is. No sequence-based ID.
- **Foreign Key on user_id**: Integrates with Supabase Auth. When a user is deleted, their sessions cascade-delete.
- **TIMESTAMPTZ**: All timestamps in UTC with timezone awareness (PostgreSQL best practice).
- **JSONB for Tags**: Mood, people, and topics are arrays of strings. JSONB allows full-text indexing later (not in Phase 4, but prepared).
- **sync_status**: Always 'SYNCED' on the cloud copy. The local SQLite version has PENDING/FAILED. This field is a placeholder for future sync-from-cloud logic (Phase 4b).

**Table 2: journal_messages** (lines 36–48)
```sql
CREATE TABLE journal_messages (
    message_id     UUID PRIMARY KEY,
    session_id     UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES auth.users(id),
    role           TEXT NOT NULL CHECK (role IN ('USER', 'ASSISTANT', 'SYSTEM')),
    content        TEXT NOT NULL,
    timestamp      TIMESTAMPTZ NOT NULL,
    input_method   TEXT NOT NULL DEFAULT 'TEXT',
    entities_json  JSONB,
    sentiment      DOUBLE PRECISION,
    embedding_id   UUID,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Key design decisions:
- **Double Foreign Key**: References both `session_id` (the parent session) and `user_id` (for fast RLS policy evaluation — see below).
- **ON DELETE CASCADE**: When a session is deleted, all messages go too. Maintains referential integrity.
- **role CHECK Constraint**: Ensures only valid roles (USER, ASSISTANT, SYSTEM) are stored. Database enforces data quality.
- **sentiment DOUBLE PRECISION**: Optional float. `NULL` if no sentiment analysis yet. Ready for Phase 5.
- **embedding_id UUID**: Pointers to embeddings in the `entry_embeddings` table (deferred to Phase 4b or 5).

**Table 3: entry_embeddings** (lines 51–58)
```sql
CREATE TABLE entry_embeddings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES auth.users(id),
    chunk_text     TEXT NOT NULL,
    embedding      vector(1536),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

A table for storing vector embeddings of journal chunks. Used for semantic search and RAG (deferred to Phase 5). The `pgvector` extension (line 12) enables this.

---

### 3.2 Indexes for Query Performance

**Lines 65–80** create indexes for common query patterns:

1. **idx_sessions_user_date** (line 65)
   ```sql
   CREATE INDEX idx_sessions_user_date ON journal_sessions(user_id, start_time DESC);
   ```
   Primary access pattern: "Get all sessions for a user, ordered by date (most recent first)". Multi-column index (user_id, start_time) avoids a second sort.

2. **idx_messages_session** (line 68)
   ```sql
   CREATE INDEX idx_messages_session ON journal_messages(session_id, timestamp ASC);
   ```
   Access pattern: "Get all messages in a session, ordered chronologically". Used when viewing a session's conversation.

3. **idx_messages_user** (line 71)
   ```sql
   CREATE INDEX idx_messages_user ON journal_messages(user_id);
   ```
   RLS policy evaluation. The policy checks `auth.uid() = user_id` — an index on `user_id` ensures this is O(1) lookup, not a table scan.

4. **idx_sessions_sync** (line 77)
   ```sql
   CREATE INDEX idx_sessions_sync ON journal_sessions(sync_status) WHERE sync_status != 'SYNCED';
   ```
   Partial index. "Get all sessions that are not synced" — used by Phase 4b background sync logic. The `WHERE` clause means the index only stores rows with `sync_status != 'SYNCED'`, saving space.

5. **idx_messages_content_trgm** (line 80)
   ```sql
   CREATE INDEX idx_messages_content_trgm ON journal_messages USING gin(content gin_trgm_ops);
   ```
   Trigram (trigram = 3-character substring) index on message content. Enables fast full-text search. Example: searching for "happy" matches "happiness", "unhappy", etc.

---

### 3.3 Row Level Security (RLS)

**Lines 86–109** define RLS policies. This is the security boundary.

```sql
ALTER TABLE journal_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE entry_embeddings ENABLE ROW LEVEL SECURITY;
```

Enable RLS on all three tables. When RLS is ON and no policy exists, the default is DENY (users see nothing). Policies explicitly allow access.

**Policy 1: journal_sessions** (lines 92–95)
```sql
CREATE POLICY "Users can CRUD their own sessions"
    ON journal_sessions FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
```

- **USING**: Filters rows on SELECT (and DELETE). Users see only rows where `auth.uid() = user_id`.
- **WITH CHECK**: Filters rows on INSERT/UPDATE. Users can only insert/update rows for themselves.
- **FOR ALL**: Applies to all operations (SELECT, INSERT, UPDATE, DELETE). If you want different policies per operation, use `FOR SELECT`, `FOR INSERT`, etc.

**Example**: User `abc-123` signs in. Supabase sets `auth.uid()` in the request context. When they query `journal_sessions`, PostgreSQL automatically filters to rows where `user_id = 'abc-123'`. If they try to INSERT a row with `user_id = 'xyz-789'` (someone else's ID), the WITH CHECK clause rejects it.

**Policy 2: journal_messages** (lines 99–102)
```sql
CREATE POLICY "Users can CRUD messages in their own sessions"
    ON journal_messages FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
```

Same as sessions — users can only access their own messages. The comment says "Direct user_id check (O(1)) instead of correlated subquery" — we *could* check `session_id IN (SELECT session_id FROM journal_sessions WHERE user_id = auth.uid())`, but that's slower. Instead, every message row stores `user_id` redundantly, so the check is a simple column comparison.

**Policy 3: entry_embeddings** (lines 106–109)
```sql
CREATE POLICY "Users can CRUD embeddings for their own sessions"
    ON entry_embeddings FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
```

Same pattern — all embedding access is gated on `user_id`.

**How RLS Integrates with SyncRepository**: When `uploadSession()` calls `client.from('journal_sessions').upsert({...})`, the Supabase client automatically attaches the JWT to the request. Supabase validates the JWT, sets `auth.uid()` in the PostgreSQL session context, and then executes the UPSERT. The RLS policy `USING (auth.uid() = user_id)` checks if the JWT's user ID matches the row's user_id. If not, the UPSERT is silently rejected (no error, but the row is not modified).

---

## Section 4: UI Integration — Status Display and Sync Feedback

### 4.1 SyncStatus Enum: Type-Safe Sync States

**File**: `/lib/models/sync_status.dart` (39 lines)

**Purpose**: Enum for the three sync states with safe string conversion.

```dart
enum SyncStatus {
  pending,
  synced,
  failed;

  static SyncStatus fromString(String value) {
    switch (value.toUpperCase()) {
      case 'SYNCED':
        return SyncStatus.synced;
      case 'FAILED':
        return SyncStatus.failed;
      case 'PENDING':
      default:
        return SyncStatus.pending;
    }
  }

  String toDbString() => name.toUpperCase();
}
```

**Why Enum Over Strings?**: Type safety. When you use `SyncStatus.synced`, the compiler knows it's valid. If you use a string `'sync3d'`, the compiler doesn't catch the typo.

**fromString() Safe Default**: If the database returns an unknown value, default to `pending`. Why? A pending session will be retried on the next sync attempt. This is safer than defaulting to `synced` (which would hide the problem).

**toDbString() Uppercase**: SQLite and PostgreSQL store 'PENDING', 'SYNCED', 'FAILED' as uppercase. When updating the local database, convert `SyncStatus.pending` → `'PENDING'`.

---

### 4.2 SyncStatusIndicator: Visual Feedback

**File**: `/lib/ui/widgets/sync_status_indicator.dart` (45 lines)

**Purpose**: A small icon showing the sync status of a session. Used in SessionCard and other places where you display session metadata.

```dart
class SyncStatusIndicator extends StatelessWidget {
  final SyncStatus status;
  final double size;

  const SyncStatusIndicator({super.key, required this.status, this.size = 16});

  @override
  Widget build(BuildContext context) {
    final (icon, color, tooltip) = switch (status) {
      SyncStatus.synced => (Icons.cloud_done, Colors.green, 'Synced'),
      SyncStatus.pending => (
        Icons.cloud_upload_outlined,
        Colors.grey,
        'Pending sync',
      ),
      SyncStatus.failed => (Icons.cloud_off, Colors.red, 'Sync failed'),
    };

    return Tooltip(
      message: tooltip,
      child: Icon(icon, size: size, color: color),
    );
  }
}
```

**Dart 3 Pattern Matching** (line 29)
```dart
final (icon, color, tooltip) = switch (status) { ... };
```

This is Dart 3 switch *expression* with destructuring. It's cleaner than a series of if-else statements. The switch returns a tuple `(IconData, Color, String)`, which is destructured into three variables.

**Visual Meanings**:
- **Green cloud-done**: Synced to Supabase. User knows this session is backed up.
- **Gray cloud-upload**: Pending. Waiting to be synced (e.g., user is offline, or hasn't tapped "Sync Now" yet).
- **Red cloud-off**: Sync failed. Previous attempt had an error. User should tap "Sync Now" to retry, or check their internet connection.

**Tooltip**: Hover over the icon, and a tooltip explains the state. Accessible.

---

## Section 5: Data Flow Trace — End-to-End Sync

Let's trace what happens when a user ends a journaling session.

### 5.1 Scenario: User Taps "End Session" (Authenticated)

**Step 1: End Session Locally** (drift/SQLite)
```
User taps "End Session" in the UI.
→ SessionNotifier.endSession(sessionId) is called
→ SessionDao.updateSessionEndTime(sessionId, now) completes
→ JournalSession.endTime is now set
→ drift emits a changed event
```

**Step 2: Trigger Sync** (SyncRepository)
```
After endSession() completes, a call to syncSession(sessionId) is made (fire-and-forget).
→ SyncRepository.syncSession(sessionId) runs
→ Fetches the session and its messages from SQLite
→ Calls uploadSession(session)
```

**Step 3: Upload to Supabase** (PostgreSQL)
```
uploadSession() extracts the data:
  - session_id (UUID, already generated on phone)
  - user_id (from currentUser, authenticated via JWT)
  - start_time, end_time (converted to UTC ISO8601 strings)
  - summary, mood_tags, people, topic_tags (extracted from the local session)
  - sync_status='SYNCED' (hardcoded — cloud copy is always synced)
  - created_at, updated_at (timestamps)

→ client.from('journal_sessions').upsert({...}) is called
→ Supabase JWT is attached to the HTTP request by supabase_flutter
→ Supabase validates the JWT and extracts auth.uid()
→ PostgreSQL RLS policy checks: auth.uid() = user_id ?
→ If yes: Row is inserted (or updated if session_id already exists)
→ If no: Row is silently rejected (no error)
```

**Step 4: Upload Messages** (PostgreSQL)
```
uploadSession() then uploads all messages for the session:
  - Queries SQLite for all messages in that session
  - For each message, extracts: message_id, session_id, user_id, role, content, etc.
  - client.from('journal_messages').upsert(messageRows) is called
  - Same JWT validation, RLS check, and insertion as above
```

**Step 5: Update Local Sync Status** (SQLite)
```
If upload succeeds:
  → SessionDao.updateSyncStatus(sessionId, 'SYNCED', now) is called
  → Local session.syncStatus is updated to 'SYNCED'
  → drift emits a changed event
  → pendingSyncCountProvider is triggered → re-evaluates
  → Settings screen re-builds, pending count decreases

If upload fails (exception caught):
  → SessionDao.updateSyncStatus(sessionId, 'FAILED', now) is called
  → Local session.syncStatus is 'FAILED'
  → Settings screen shows red sync icon
  → User can tap "Sync Now" later to retry
```

---

### 5.2 Security Boundaries

At each step, the system enforces constraints:

1. **Local SQLite**: No restrictions. Phone data is owned by the user. The app trusts local data.

2. **Authentication Boundary**: SupabaseService enforces `isConfigured` and `isAuthenticated` checks. If the user is not signed in, `syncSession()` returns early (no-op). No attempt to upload.

3. **JWT Validation**: Supabase validates the JWT signature and expiration. If the token is forged or expired, Supabase rejects it. (Token refresh is handled transparently by supabase_flutter.)

4. **RLS Policies**: PostgreSQL checks `auth.uid() = user_id` for every row. Even if a user's JWT is valid, they can only access their own data. If they forge a different user_id in the UPSERT payload, PostgreSQL's WITH CHECK clause rejects it.

5. **Optional Auth**: If `isAuthenticated` is false, sync is a no-op. The app doesn't throw an error or annoy the user. Journaling continues offline.

---

## Section 6: Edge Function Auth Upgrade (Phase 4 Integration)

**File**: `supabase/functions/claude-proxy/index.ts` (Phase 4 changes)

**Context**: Phase 3 had the `claude-proxy` Edge Function for LLM calls. It used a proxy access key (`PROXY_ACCESS_KEY`) for authentication, which was less secure (API keys are "something you know", not "something that proves you are"). Phase 4 upgrades this to JWT auth.

**Before Phase 4** (Phase 3 style):
```typescript
const accessKey = req.headers.get('authorization');
if (accessKey !== `Bearer ${PROXY_ACCESS_KEY}`) {
  return new Response('Unauthorized', { status: 401 });
}
```

**After Phase 4**:
```typescript
// JWT validation first (authenticated path)
const jwt = req.headers.get('authorization')?.replace('Bearer ', '');
if (jwt) {
  const { data: { user }, error } = await supabase.auth.getUser(jwt);
  if (error || !user) {
    return new Response('Invalid JWT', { status: 401 });
  }
  // User is authenticated. Proceed with the user's context.
  userId = user.id;
} else {
  // Fallback: unauthenticated path (proxy access key)
  const accessKey = req.headers.get('authorization');
  if (accessKey !== `Bearer ${PROXY_ACCESS_KEY}`) {
    return new Response('Unauthorized', { status: 401 });
  }
  // Proceed with anonymous context (no user ID)
}
```

**Why Two Auth Paths?**
1. **Authenticated (JWT)**: When the user signs in, the Flutter app sends the JWT. The Edge Function validates it, learns the user ID, and can optionally store the LLM response in the database with the user's ID.
2. **Unauthenticated (Proxy Key)**: When the user hasn't signed in, the app uses the anon key + proxy key fallback. LLM calls still work, but the response is not stored in the cloud database (no user_id context).

This dual-path design keeps the experience seamless — LLM features work with or without auth.

---

## Section 7: Key Design Principles Recap

Before moving to the quiz, review these three principles that shape all Phase 4 code:

### Principle 1: Optional Auth Preserves Instant-On Journaling
Every method guarded by `isAuthenticated` or `isConfigured` checks. No error thrown, no retry loop, no friction. If not authenticated, sync is a no-op. Journaling continues. This is the core of ADR-0012.

### Principle 2: Idempotency Enables Safe Retries
UPSERT on the cloud side, per ADR-0004. If sync fails and retries, the second upload doesn't duplicate or corrupt data. The `session_id` is the conflict key. Clients can retry indefinitely without coordinating with the server.

### Principle 3: RLS Enforces Data Isolation
Every row in PostgreSQL carries `user_id`. Every policy checks `auth.uid() = user_id`. No cross-user data leaks, even if a user obtains another user's JWT (which is prevented by TLS in production). This is a security boundary, not a UI convenience.

---

## Next Steps: Taking This Further

Phase 4 is upload-only. To deepen your understanding, consider these Phase 4b/5 extensions (not implemented yet):

1. **Background Sync**: WorkManager (Android) or background_fetch (iOS) every 15 minutes.
2. **Download Sync**: Periodic pull from Supabase to the phone (multi-device support).
3. **Conflict Resolution**: Last-write-wins or user-chosen merge strategy for conflicting edits.
4. **Semantic Search**: Embeddings + pgvector for "find all sessions about X" queries.
5. **Analytics**: Database views and materialized views in Supabase for insights (mood trends, topic frequency, etc.).

Each extension builds on the foundations in Phase 4 — JWT auth, RLS, UPSERT idempotency.

---

## Summary

You've now traced Phase 4 from three angles:

1. **Auth Layer**: SupabaseService → auth providers → AuthScreen. Optional sign-in with graceful no-ops when not authenticated.
2. **Sync Layer**: SyncRepository uploads UPSERT payloads to PostgreSQL. UPSERT idempotency makes retries safe. RLS policies gate access by user_id.
3. **Cloud Layer**: PostgreSQL schema with tables, indexes, and RLS policies. Two auth paths (JWT + proxy key) for backward compatibility.

The design is simple, intentional, and composable. Each layer (service, repository, providers, UI) has a single responsibility, and Riverpod wires them together reactively.

---

## References

- **ADR-0012**: Optional Auth with Upload-Only Cloud Sync
- **ADR-0004**: Offline-First Architecture (UPSERT idempotency)
- **ADR-0005**: Supabase Edge Functions for Claude API (JWT context)
- **SupabaseService**: `/lib/services/supabase_service.dart`
- **SyncRepository**: `/lib/repositories/sync_repository.dart`
- **Auth Providers**: `/lib/providers/auth_providers.dart`
- **Sync Providers**: `/lib/providers/sync_providers.dart`
- **Auth Screen**: `/lib/ui/screens/auth_screen.dart`
- **Settings Screen**: `/lib/ui/screens/settings_screen.dart` (Cloud Sync card)
- **SyncStatus Enum**: `/lib/models/sync_status.dart`
- **SyncStatusIndicator**: `/lib/ui/widgets/sync_status_indicator.dart`
- **Cloud Schema**: `/supabase/migrations/001_initial_schema.sql`
