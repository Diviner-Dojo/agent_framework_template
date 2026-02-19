---
spec_id: SPEC-20260219-174121
title: "Phase 1: Walking Skeleton — Zero to Working Journaling App"
status: approved
risk_level: medium
phase: 1
source: docs/product-brief.md
estimated_tasks: 13
autonomous_execution: true
reviewed_by: [architecture-consultant, qa-specialist, security-specialist]
discussion_id: DISC-20260219-175738-phase1-spec-review
---

## Goal

Starting from an empty Flutter project, deliver a fully working offline journaling app that:
- Launches and greets the user based on time of day
- Runs a rule-based conversational journaling session (Layer A agent)
- Persists all sessions and messages to local SQLite via drift
- Lets the user browse past sessions and view full transcripts
- Works 100% offline with zero network calls

This spec is designed for **autonomous agent execution** — every task includes exact commands, file paths, file contents, and verification steps. An agent should be able to execute this start-to-finish without human intervention.

## Context

- Flutter SDK is installed at `C:\src\flutter` (add `C:\src\flutter\bin` to PATH)
- Android SDK 36.1.0 is installed with all licenses accepted
- The project directory (`C:\Work\AI\agentic_journal`) contains framework infrastructure but no Flutter code yet
- Legacy Python app code exists in `src/` and `tests/` — these must be removed
- The quality gate script (`scripts/quality_gate.py`) is Python/ruff-based and must be updated for Dart
- The developer is new to Flutter — all code must have thorough inline comments
- ADRs 0002 (Flutter/Dart), 0004 (Offline-First), 0006 (Layered Agent) are accepted and locked

## Constraints

- **Offline-only**: Phase 1 makes zero network calls. No Supabase, no Claude API.
- **No over-engineering**: Only build what Phase 1 requires. No sync, no auth, no cloud.
- **drift code generation**: After writing table definitions, `dart run build_runner build` must run before any code that imports generated files.
- **PATH requirement**: Every shell command that uses `flutter` or `dart` must include: `export PATH="$PATH:/c/src/flutter/bin"`
- **Windows/Git Bash**: Shell environment is Git Bash on Windows 11. Use Unix syntax.
- **Comment thoroughly**: The developer is learning Flutter. Inline comments explaining "why" are required.

## Requirements

### Functional
- R1: App launches and displays a time-of-day greeting
- R2: User can type messages and receive rule-based follow-up questions
- R3: Follow-ups use keyword detection (emotional, social, work-related)
- R4: After 2-4 follow-ups, agent offers a summary and ends the session
- R5: All messages persist in local SQLite (survive app restart)
- R6: User can browse past sessions sorted by date (newest first)
- R7: User can tap a session to view the full transcript
- R8: User can start a new session from the session list
- R9: Session summary is generated locally (first-sentence extraction)

### Non-Functional
- NF1: App starts in under 3 seconds on a mid-range Android device
- NF2: All database operations are asynchronous (no UI blocking)
- NF3: Test coverage >= 80% for new code
- NF4: All code passes `dart format` and `dart analyze` with zero issues

---

## Task Breakdown

### Task 1: Flutter Project Scaffolding

**What**: Create the Flutter project in the existing directory, clean up legacy files, update gitignore.

**Commands**:
```bash
export PATH="$PATH:/c/src/flutter/bin"

# Create Flutter project in existing directory
flutter create --org com.divinerdojo --project-name agentic_journal .

# Remove legacy Python app code (NOT scripts/ — those are framework tools)
rm -rf src/ tests/

# Remove Python test/coverage artifacts that are no longer relevant
rm -f .coverage
```

**File: `.gitignore`** — Replace contents with Flutter-appropriate ignores:
```gitignore
# Flutter/Dart
.dart_tool/
.packages
build/
*.dart.js
*.dart.js.map
*.js.deps
*.js.map
.flutter-plugins
.flutter-plugins-dependencies

# Generated files
*.g.dart
*.freezed.dart
*.mocks.dart

# IDE
.idea/
.vscode/
*.iml
*.swp

# Platform builds
/android/app/debug/
/android/app/profile/
/android/app/release/

# OS
.DS_Store
Thumbs.db

# Project-specific
.claude/settings.local.json
*.db
*.sqlite
*.sqlite3
nul

# Python (framework scripts)
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/
dist/
.ruff_cache/
.pytest_cache/
.mypy_cache/
.coverage
```

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter doctor  # Should show [√] Flutter
ls lib/main.dart  # Should exist
ls pubspec.yaml  # Should exist
ls android/  # Should exist
ls src/ 2>/dev/null && echo "FAIL: src/ still exists" || echo "PASS: src/ removed"
ls tests/ 2>/dev/null && echo "FAIL: tests/ still exists" || echo "PASS: tests/ removed"
```

**Post-scaffold security hardening**:
After `flutter create` completes, edit `android/app/src/main/AndroidManifest.xml`:
- Set `android:allowBackup="false"` on the `<application>` tag
- This prevents unencrypted SQLite database extraction via Android backup (`adb backup`, Google Cloud Backup)
- Journal entries are deeply personal — this is a mandatory security baseline even in Phase 1

**Done when**: `flutter run --dry-run` or `flutter build apk --debug` starts without errors (may fail at code level later — that's expected). AndroidManifest.xml has `allowBackup="false"`.

---

### Task 2: Configure Dependencies

**What**: Add all Phase 1 dependencies to `pubspec.yaml` and configure drift code generation.

**File: `pubspec.yaml`** — Update the dependencies and dev_dependencies sections (keep the flutter-generated boilerplate for name, description, version, environment):
```yaml
name: agentic_journal
description: "AI-powered journaling app with offline-first architecture"
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: ^3.8.0

dependencies:
  flutter:
    sdk: flutter
  # State management — modern, testable, explicit dependency injection
  flutter_riverpod: ^2.6.1
  riverpod_annotation: ^2.6.1

  # Local database — type-safe SQL, leverages developer's SQL expertise
  drift: ^2.25.0
  sqlite3_flutter_libs: ^0.5.28

  # UUID generation — client-side IDs for offline-first
  uuid: ^4.5.1

  # Timezone detection
  flutter_timezone: ^3.0.1

  # Core Flutter
  cupertino_icons: ^1.0.8
  path_provider: ^2.1.5
  path: ^1.9.1

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0

  # drift code generation
  drift_dev: ^2.25.0
  build_runner: ^2.4.14

  # Riverpod code generation
  riverpod_generator: ^2.6.4
  custom_lint: ^0.7.5
  riverpod_lint: ^2.6.4

  # Testing utilities
  mockito: ^5.4.5
```

**File: `build.yaml`** — Create in project root:
```yaml
targets:
  $default:
    builders:
      drift_dev:
        options:
          # Generate companion classes for type-safe queries
          generate_connect_constructor: false
          # Use named parameters for generated data classes
          named_parameters: true
          # Store drift-specific helper columns
          store_date_time_values_as_text: true
```

**Commands**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter pub get
```

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter pub deps | head -20  # Should show drift, flutter_riverpod, etc.
```

**Done when**: `flutter pub get` completes without errors.

---

### Task 3: Create Project Directory Structure

**What**: Create all directories defined in the product brief's project structure.

**Commands**:
```bash
# Create all lib/ subdirectories
mkdir -p lib/database/daos
mkdir -p lib/models
mkdir -p lib/repositories
mkdir -p lib/providers
mkdir -p lib/services
mkdir -p lib/ui/screens
mkdir -p lib/ui/widgets
mkdir -p lib/ui/theme
mkdir -p lib/utils

# Create all test/ subdirectories
mkdir -p test/database
mkdir -p test/models
mkdir -p test/repositories
mkdir -p test/providers
mkdir -p test/utils
mkdir -p test/ui

# Create integration test directory
mkdir -p integration_test
```

**Verification**:
```bash
find lib/ -type d | sort
find test/ -type d | sort
```

**Done when**: All directories exist matching the product brief's project structure.

---

### Task 4: Database Layer — Tables and Database Class

**What**: Define drift tables and the AppDatabase class. This is the foundation — everything else depends on it.

**File: `lib/database/tables.dart`** — Copy exactly from the product brief's drift schema (Data Model section). Include all columns for JournalSessions and JournalMessages.

**File: `lib/database/app_database.dart`**:
```dart
// ===========================================================================
// file: lib/database/app_database.dart
// purpose: drift database class — single entry point for all local DB access.
//          Uses lazy initialization and includes migration strategy.
//
// Why drift? It provides type-safe SQL that feels familiar to SQL developers.
// Generated code (*.g.dart) is created by build_runner — run:
//   dart run build_runner build
// ===========================================================================

import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

import 'tables.dart';

// Include this annotation so build_runner generates the database code.
// The generated file will be app_database.g.dart.
part 'app_database.g.dart';

// schemaVersion: increment this whenever you change table definitions,
// then add migration logic in the MigrationStrategy below.
@DriftDatabase(tables: [JournalSessions, JournalMessages])
class AppDatabase extends _$AppDatabase {
  // Default constructor — uses a file-based SQLite database.
  // For testing, pass a different QueryExecutor (e.g., NativeDatabase.memory()).
  AppDatabase() : super(_openConnection());

  // Named constructor for testing — accepts any executor (e.g., in-memory DB).
  AppDatabase.forTesting(super.executor);

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
        // onCreate runs when the database file is first created.
        onCreate: (Migrator m) async {
          await m.createAll();
        },
        // onUpgrade handles schema changes in future versions.
        // For now, Phase 1 only has version 1 — no migrations needed yet.
        onUpgrade: (Migrator m, int from, int to) async {
          // Future migrations will go here as we increment schemaVersion.
          // Example:
          // if (from < 2) {
          //   await m.addColumn(journalSessions, journalSessions.newColumn);
          // }
        },
      );
}

// _openConnection creates the SQLite database file in the app's documents directory.
// This is a standard drift pattern — the LazyDatabase delays opening until first use.
LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    // getApplicationDocumentsDirectory() returns a platform-appropriate location:
    // - Android: /data/data/com.divinerdojo.agentic_journal/files
    // - iOS: NSDocumentDirectory
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'agentic_journal.sqlite'));
    return NativeDatabase.createInBackground(file);
  });
}
```

**Commands** (run AFTER writing both files):
```bash
export PATH="$PATH:/c/src/flutter/bin"
dart run build_runner build --delete-conflicting-outputs
```

**Verification**:
```bash
ls lib/database/app_database.g.dart  # Generated file must exist
```

**Done when**: `build_runner` completes and `app_database.g.dart` is generated without errors.

**IMPORTANT**: If build_runner fails, read the error carefully. Common issues:
- Missing `part 'app_database.g.dart';` directive
- Import path mismatches
- Missing `@DriftDatabase` annotation
Fix the source files and re-run build_runner.

---

### Task 5: Database Layer — DAOs

**What**: Create Data Access Objects for sessions and messages. These provide the CRUD API that repositories will call.

**File: `lib/database/daos/session_dao.dart`**:
Implement a DAO class with these methods:
- `createSession(String sessionId, DateTime startTime, String timezone)` → inserts a new session
- `endSession(String sessionId, DateTime endTime, String? summary, String? moodTags, String? people, String? topicTags)` → updates end time and metadata
- `getSessionById(String sessionId)` → returns single session or null
- `getAllSessionsByDate()` → returns all sessions ordered by startTime DESC
- `getSessionsByDateRange(DateTime start, DateTime end)` → filtered query
- `watchAllSessions()` → returns a `Stream` of sessions (for reactive UI updates via Riverpod)

**File: `lib/database/daos/message_dao.dart`**:
Implement a DAO class with these methods:
- `insertMessage(String messageId, String sessionId, String role, String content, DateTime timestamp, {String inputMethod = 'TEXT'})` → inserts a message
- `getMessagesForSession(String sessionId)` → returns messages ordered by timestamp ASC
- `watchMessagesForSession(String sessionId)` → returns a `Stream` for reactive UI
- `getMessageCount(String sessionId)` → returns count of messages in a session

Use drift's generated query API. Do NOT use raw SQL strings — use drift's type-safe Dart query builders.

**DAO Pattern Decision**: DAOs should be standalone classes that accept the `AppDatabase` instance in their constructor (dependency injection, not inheritance). This intentionally diverges from drift's standard `@DriftAccessor` mixin pattern. Rationale: constructor injection enables direct testing with `AppDatabase.forTesting(NativeDatabase.memory())` without mocking. Document this choice with a comment in each DAO file header so future phases don't accidentally revert to the mixin pattern.

**Commands** (if any new generated code is needed):
```bash
export PATH="$PATH:/c/src/flutter/bin"
dart run build_runner build --delete-conflicting-outputs
```

**Verification** (run after writing both DAOs — do not defer to Task 11):
```bash
export PATH="$PATH:/c/src/flutter/bin"
dart analyze lib/database/
```
This catches compilation errors immediately rather than six tasks later.

---

### Task 6: Domain Models and Utilities

**What**: Create the sync status enum and utility functions.

**Domain Model Decision**: In Phase 1, use drift's generated data classes (`JournalSession`, `JournalMessage` from `app_database.g.dart`) directly throughout the app. Separate domain model classes (`lib/models/journal_session.dart`, `lib/models/journal_message.dart`) are deferred to Phase 3 when the distinction between local DB records and API DTOs becomes relevant. The `lib/models/` directory exists for `sync_status.dart` and as a placeholder for Phase 3+.

**File: `lib/models/sync_status.dart`**:
```dart
/// Tracks whether a journal session has been synced to the cloud.
/// Phase 1 only uses PENDING (no sync implemented yet).
enum SyncStatus {
  pending,
  synced,
  failed;

  /// Convert from the string stored in SQLite (e.g., 'PENDING')
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

  /// Convert to the string format stored in SQLite
  String toDbString() => name.toUpperCase();
}
```

**File: `lib/utils/uuid_generator.dart`**:
```dart
// Thin wrapper around the uuid package.
// Client-generated UUIDs are essential for offline-first — we can create
// records without a server round-trip, and they won't collide on sync.
import 'package:uuid/uuid.dart';

const _uuid = Uuid();

/// Generate a new v4 UUID string.
String generateUuid() => _uuid.v4();
```

**File: `lib/utils/timestamp_utils.dart`**:
```dart
/// Utility functions for timestamp handling.
/// All timestamps are stored as UTC in the database.
/// Convert to local time only in the UI layer.

/// Get the current time in UTC.
DateTime nowUtc() => DateTime.now().toUtc();

/// Format a DateTime for display (local time).
/// Example: "Feb 19, 2026 at 10:41 AM"
String formatForDisplay(DateTime utcTime) {
  final local = utcTime.toLocal();
  final months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  final month = months[local.month - 1];
  final day = local.day;
  final year = local.year;
  final hour = local.hour > 12 ? local.hour - 12 : (local.hour == 0 ? 12 : local.hour);
  final minute = local.minute.toString().padLeft(2, '0');
  final period = local.hour >= 12 ? 'PM' : 'AM';
  return '$month $day, $year at $hour:$minute $period';
}

/// Format a DateTime as a short date string for session cards.
/// Example: "Feb 19" or "Feb 19, 2025" if not current year.
String formatShortDate(DateTime utcTime) {
  final local = utcTime.toLocal();
  final now = DateTime.now();
  final months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  final month = months[local.month - 1];
  if (local.year == now.year) {
    return '$month ${local.day}';
  }
  return '$month ${local.day}, ${local.year}';
}

/// Format a Duration as a human-readable string.
/// Example: "5 min" or "1 hr 23 min"
String formatDuration(Duration duration) {
  if (duration.inMinutes < 1) return '<1 min';
  if (duration.inHours < 1) return '${duration.inMinutes} min';
  final hours = duration.inHours;
  final minutes = duration.inMinutes % 60;
  if (minutes == 0) return '$hours hr';
  return '$hours hr $minutes min';
}
```

**File: `lib/utils/keyword_extractor.dart`**:
Implement the keyword detection logic from the product brief's Layer A agent spec:
- Emotional words: stressed, angry, happy, excited, sad, anxious, frustrated, worried, overwhelmed, grateful, proud, lonely, confused, hopeful, tired, exhausted, energetic, calm, nervous
- People references: he, she, they, we, proper nouns (capitalized words mid-sentence), mom, dad, brother, sister, friend, boss, coworker
- Work/project references: meeting, deadline, project, client, boss, presentation, email, office, work, job, interview, promotion
- Return an enum or string indicating the detected category (emotional, social, work, none)
- If multiple categories match, prioritize: emotional > social > work

**Done when**: All files compile without errors.

---

### Task 7: Rule-Based Agent (Layer A)

**What**: Implement the conversation engine from the product brief's Layer A spec. This is the core logic of Phase 1.

**File: `lib/repositories/agent_repository.dart`**:

**Design Decision**: `AgentRepository` is **intentionally stateless**. All conversation state (follow-up count, message history) is owned by `SessionNotifier` in the providers layer (Task 8). The repository receives everything it needs as method parameters. This keeps it pure and trivially testable.

**Phase 3 Extension Point**: The constructor should accept an optional future dependency injection point for `ClaudeApiService`. For now, the constructor is empty, but include this comment:
```dart
class AgentRepository {
  // Phase 3 will add: final ClaudeApiService? _claudeService;
  // Phase 3 constructor: AgentRepository({ClaudeApiService? claudeService})
  //   : _claudeService = claudeService;
  AgentRepository();
```

Implement these methods:

```dart
/// Get the opening greeting based on current time of day.
/// Accepts an optional [now] parameter for deterministic testing.
/// Rules from product brief:
///   5 AM – 11:59 AM  → "Good morning! Any plans or thoughts for today?"
///   12 PM – 4:59 PM  → "How's your afternoon going?"
///   5 PM – 9:59 PM   → "How was your day?"
///   10 PM – 4:59 AM  → "Still up? What's on your mind?"
///   After 2+ day gap  → "It's been a few days — want to catch up?"
String getGreeting({DateTime? lastSessionDate, DateTime? now})

/// Get a follow-up question based on the user's message and conversation history.
/// Uses keyword extraction to select contextually relevant follow-ups.
/// Returns null when the conversation should end (after 2-4 follow-ups).
String? getFollowUp({
  required String latestUserMessage,
  required List<String> conversationHistory,
  required int followUpCount,
})

/// Generate a local summary from the user's messages.
/// Phase 1 approach: extract first sentence of each user message as bullet points.
String generateLocalSummary(List<String> userMessages)

/// Determine if the session should end.
/// Returns true after 2-4 follow-ups OR if user indicates they're done.
bool shouldEndSession({
  required int followUpCount,
  required String latestUserMessage,
})
```

The follow-up logic should:
1. Run keyword extraction on the latest user message
2. Select from a pool of follow-up questions based on the detected category
3. Avoid repeating the same question twice in a session
4. After 2-4 follow-ups, transition to closing: "Got it. Here's what I captured: [summary]. Anything to add?"
5. Detect "done" signals: "no", "nope", "that's it", "nothing", "I'm done", "that's all", "goodbye", "bye"

Include at least 3-4 follow-up questions per category so the agent doesn't repeat itself.

**Done when**: Agent can drive a multi-turn conversation from greeting → follow-ups → summary → close.

---

### Task 8: Riverpod Providers

**What**: Wire up the state management layer that connects the UI to the database and agent.

**File: `lib/providers/database_provider.dart`**:
- Provide a singleton `AppDatabase` instance via Riverpod
- The database should be created once and reused across the app

**File: `lib/providers/session_providers.dart`**:
Implement these providers:

```dart
/// Holds the active session ID (null when no session is in progress).
/// When set, the UI shows the journal conversation screen.

/// Streams all sessions from the database (for the session list screen).
/// Uses watchAllSessions() from SessionDao for reactive updates.

/// Streams messages for the active session.
/// Uses watchMessagesForSession() from MessageDao.

/// Manages the active conversation state:
/// - Start a new session (create in DB, get greeting, add as assistant message)
/// - Send a user message (save to DB, get follow-up, save follow-up)
/// - End session (generate summary, update session record)
/// - Track follow-up count
```

The session notifier should be an `AsyncNotifier` (or `Notifier`) that encapsulates all the business logic for a journaling session. The UI simply calls `startSession()`, `sendMessage(text)`, and `endSession()`.

**State Ownership**: `SessionNotifier` owns all mutable conversation state: `followUpCount`, `activeSessionId`, and the list of used follow-up questions (to prevent repeats). The `AgentRepository` is stateless — the notifier passes `followUpCount` and `conversationHistory` as parameters on each call.

**lastSessionDate Flow**: When `SessionNotifier.startSession()` is called, it should:
1. Query the most recent session's start time from `SessionDao` (or via `lastSessionDateProvider`)
2. Pass that date as the `lastSessionDate` parameter to `AgentRepository.getGreeting()`
3. The repository never imports or depends on any provider — data flows DOWN (provider → repository), not UP

**File: `lib/providers/settings_providers.dart`**:
- For Phase 1, this is minimal — just a placeholder provider for future settings
- Include a `lastSessionDateProvider` that queries the most recent session's start time via `SessionDao`

**Done when**: Providers compile and the session notifier correctly orchestrates the create → message → follow-up → end flow.

---

### Task 9: UI — Theme, App Shell, and Navigation

**What**: Set up the app's visual foundation and screen routing.

**File: `lib/ui/theme/app_theme.dart`**:
- Define a Material 3 theme with a calming color scheme (think journaling — soft blues, warm neutrals)
- Include both light and dark theme definitions
- Use `TextTheme` with readable sizes for chat messages

**File: `lib/app.dart`**:
- `MaterialApp` with the theme applied
- Simple navigator with named routes:
  - `/` → Session list screen (home)
  - `/session` → Active journal session screen
  - `/session/detail` → Past session detail (read-only transcript)
- **Navigation Strategy Note**: String-based named routes are intentionally used for Phase 1 simplicity (3 screens). Before Phase 5 adds search and onboarding screens, migrate to `go_router` for type-safe, declarative routing. This is a known upgrade path, not technical debt.

**File: `lib/main.dart`**:
```dart
// Entry point — wraps the app in ProviderScope for Riverpod.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    // ProviderScope is Riverpod's equivalent of a dependency injection container.
    // It must wrap the entire app so all providers are accessible.
    const ProviderScope(child: AgenticJournalApp()),
  );
}
```

**Done when**: App launches to an empty session list screen with proper theming.

---

### Task 10: UI — Screens and Widgets

**What**: Build the three screens and supporting widgets.

**File: `lib/ui/widgets/chat_bubble.dart`**:
- Visually distinct bubbles for USER (right-aligned, colored) vs ASSISTANT (left-aligned, neutral)
- Show the message content and timestamp
- Rounded corners, appropriate padding

**File: `lib/ui/widgets/session_card.dart`**:
- Card showing: date, summary (or "No summary" placeholder), duration, message count
- Tappable — navigates to session detail

**File: `lib/ui/widgets/end_session_button.dart`**:
- Button in app bar or bottom of chat that triggers session end
- Shows confirmation dialog: "End this session?"

**File: `lib/ui/screens/journal_session_screen.dart`**:
- Scrollable list of chat bubbles (assistant + user messages)
- Text input field at the bottom with send button
- Auto-scrolls to latest message when new messages arrive
- App bar with session info and end session button
- On first load: creates a new session, displays greeting

**File: `lib/ui/screens/session_list_screen.dart`**:
- Lists all past sessions using `SessionCard` widgets
- Sorted by date, newest first
- Floating action button to start a new session
- Empty state: "No journal sessions yet. Tap + to start your first entry."
- Uses the stream provider from Task 8 for reactive updates

**File: `lib/ui/screens/session_detail_screen.dart`**:
- Read-only view of a past session's full transcript
- Shows all messages as chat bubbles
- App bar shows session date and summary
- No text input (this is view-only)

**Done when**: Full user flow works: session list → start new session → converse → end → see session in list → tap to view transcript.

---

### Task 11: Tests

**What**: Write tests achieving >= 80% coverage on new code.

**Test isolation note**: Every test group using `AppDatabase.forTesting(NativeDatabase.memory())` MUST call `await database.close()` in `tearDown` or `tearDownAll`. Drift's in-memory database does not auto-close, and leaking connections causes non-deterministic failures.

**Test files to create** (10 files):

1. **`test/database/session_dao_test.dart`**:
   - Use in-memory database: `AppDatabase.forTesting(NativeDatabase.memory())`
   - Test createSession + getSessionById round-trip
   - Test empty database returns empty list from getAllSessionsByDate
   - Test multiple sessions are ordered by date descending (requires 2+ sessions)
   - Test endSession writes all 5 fields: assert each of `endTime`, `summary`, `moodTags`, `people`, `topicTags` individually after calling getSessionById
   - Test endSession on non-existent session ID does not corrupt database
   - Test getSessionsByDateRange with valid range, empty range, and inverted range (start > end)
   - `tearDown`: `await database.close()`

2. **`test/database/message_dao_test.dart`**:
   - Use in-memory database
   - Test insertMessage + getMessagesForSession round-trip
   - Test messages are ordered by timestamp ascending
   - **Cross-session isolation**: Insert messages into two distinct sessions, verify `getMessagesForSession(sessionA)` returns only session A's messages
   - Test getMessageCount returns 0 for session with no messages
   - Test getMessageCount returns correct count after multiple inserts
   - `tearDown`: `await database.close()`

3. **`test/repositories/agent_repository_test.dart`**:
   - Test getGreeting for each time period: pass `now:` parameter set to 8 AM, 2 PM, 7 PM, 11 PM (deterministic, no clock dependency)
   - Test getGreeting gap detection boundaries: `lastSessionDate = null` (first use), `1 day ago` (no gap), `exactly 2 days ago` (gap triggers), `3 days ago` (gap triggers)
   - Test getFollowUp returns appropriate follow-ups for emotional/social/work keywords
   - Test getFollowUp returns null after max follow-ups (pass followUpCount = 4)
   - **Non-repetition**: Call getFollowUp 4+ times with same emotional keyword and verify returned questions are not all identical
   - Test shouldEndSession detects "done" signals: "no", "nope", "I'm done", "that's all"
   - Test shouldEndSession with false positives: "I'm done with the project" (contains "done" but is not a termination signal — verify expected behavior and document the design choice)
   - Test generateLocalSummary with: empty list (should not crash), single-word message, multi-sentence messages (extracts first sentence only)

4. **`test/utils/keyword_extractor_test.dart`**:
   - Test detection of emotional keywords (e.g., "stressed", "happy")
   - Test detection of social keywords (e.g., "mom", "friend")
   - Test detection of work keywords (e.g., "meeting", "deadline")
   - Test priority: emotional > social > work (e.g., "I'm stressed about the deadline" → emotional)
   - Test case insensitivity: "STRESSED" and "Stressed" match
   - Test empty string returns none category
   - Test no-match input returns none category

5. **`test/models/sync_status_test.dart`**:
   - Test `SyncStatus.fromString('PENDING')` → `SyncStatus.pending`
   - Test `SyncStatus.fromString('SYNCED')` → `SyncStatus.synced`
   - Test `SyncStatus.fromString('FAILED')` → `SyncStatus.failed`
   - Test `SyncStatus.fromString('UNKNOWN_VALUE')` → `SyncStatus.pending` (default fallback)
   - Test `toDbString()` round-trip for each value (e.g., `SyncStatus.pending.toDbString()` → `'PENDING'`)

6. **`test/utils/timestamp_utils_test.dart`**:
   - Test `formatForDisplay` at midnight (12:00 AM), noon (12:00 PM), 1 AM, 1 PM
   - Test `formatShortDate` for same-year (omits year) vs prior-year (includes year)
   - Test `formatDuration` with: 0 seconds → "<1 min", 59 seconds → "<1 min", 1 minute, 59 minutes, 1 hour exact → "1 hr", 1 hour 30 minutes → "1 hr 30 min"

7. **`test/providers/session_notifier_test.dart`**:
   - Use `ProviderContainer` with overridden database provider (in-memory AppDatabase)
   - Test startSession: creates a session in DB and adds a greeting message
   - Test sendMessage: adds user message AND a follow-up message to DB
   - Test endSession: sets endTime and summary on the session record
   - Test follow-up count reaches max → notifier transitions to closing
   - `tearDown`: dispose ProviderContainer, close database

8. **`test/ui/chat_bubble_test.dart`**:
   - Widget test: USER messages are right-aligned
   - Widget test: ASSISTANT messages are left-aligned
   - Widget test: message content text is displayed correctly

9. **`test/ui/session_list_screen_test.dart`**:
   - Widget test: empty state shows placeholder text "No journal sessions yet"
   - Widget test: FAB (floating action button) is present
   - Widget test: with populated data (override stream provider with fake emitting 2 sessions), verify two SessionCard widgets render

10. **`test/ui/end_session_button_test.dart`**:
    - Widget test: tap button → confirmation dialog appears
    - Widget test: tap "Cancel" in dialog → callback is NOT invoked
    - Widget test: tap "End" (or confirm) in dialog → callback IS invoked

**Commands**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter test
flutter test --coverage
```

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter test --coverage
# Check coverage report
cat coverage/lcov.info | grep -E "^(SF|LF|LH)" | head -30
```

**Done when**: All tests pass and coverage >= 80%.

---

### Task 12: Update Quality Gate for Flutter/Dart

**What**: Rewrite `scripts/quality_gate.py` to validate Flutter/Dart code instead of Python/ruff.

The updated quality gate should check:
1. **Formatting**: `dart format --set-exit-if-changed lib/ test/` (exit 0 = pass)
2. **Linting**: `dart analyze lib/ test/` (exit 0 = pass)
3. **Tests**: `flutter test` (exit 0 = pass)
4. **Coverage**: `flutter test --coverage` then parse `coverage/lcov.info` for >= 80%
5. **ADR completeness**: Keep the existing ADR check (it's already correct)

Preserve the existing CLI interface: `--fix`, `--skip-format`, `--skip-lint`, `--skip-tests`, `--skip-coverage`, `--skip-adrs`.

For `--fix`: run `dart format lib/ test/` (without `--set-exit-if-changed`) and `dart fix --apply`.

Update `SRC_DIR` to `lib/` and `TESTS_DIR` to `test/` (singular, Flutter convention).

The `validate_directories()` function should check for `.dart` files instead of `.py` files.

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
python scripts/quality_gate.py
```

**Also**: Update the `CLAUDE.md` "Quality Gate" section to reflect the new Dart commands (`dart format`, `dart analyze`, `flutter test`) instead of the old Python/ruff references. The project constitution must stay current with implementation.

**Done when**: Quality gate passes with all checks green. CLAUDE.md Quality Gate section is updated.

---

### Task 13: Final Verification and Cleanup

**What**: End-to-end verification that everything works together.

**Checklist**:
```bash
export PATH="$PATH:/c/src/flutter/bin"

# 1. Clean build
flutter clean && flutter pub get
dart run build_runner build --delete-conflicting-outputs

# 2. Static analysis
dart format --set-exit-if-changed lib/ test/
dart analyze lib/ test/

# 3. Tests
flutter test --coverage

# 4. Quality gate
python scripts/quality_gate.py

# 5. Build APK (proves the full Android toolchain works)
flutter build apk --debug
```

**Acceptance Criteria**:
- [ ] `flutter pub get` — no errors
- [ ] `dart run build_runner build` — generates `*.g.dart` files without errors
- [ ] `dart format` — zero changes needed
- [ ] `dart analyze` — zero issues
- [ ] `flutter test` — all tests pass
- [ ] Coverage >= 80%
- [ ] `python scripts/quality_gate.py` — all checks pass
- [ ] `flutter build apk --debug` — produces a debug APK
- [ ] App launches on emulator/device (manual check if available)
- [ ] Full flow works: greeting → type messages → receive follow-ups → end session → view in list → tap to see transcript
- [ ] `CLAUDE.md` Quality Gate section reflects Dart commands (updated in Task 12)
- [ ] `android/app/src/main/AndroidManifest.xml` has `android:allowBackup="false"`

**Post-completion**: Update `BUILD_STATUS.md` with Phase 1 completion status.

---

## Specialist Review Summary

Three specialists reviewed this spec before finalization:

### Architecture Consultant (confidence: 0.91)
**Verdict**: Approved after changes. Blocking findings addressed:
1. AgentRepository statelessness and Phase 3 extension point — documented in Task 7
2. Domain model ambiguity — resolved: Phase 1 uses drift generated classes directly (Task 6)

Advisory items incorporated: DAO pattern rationale (Task 5), intermediate compile check (Task 5), lastSessionDate flow (Task 8), navigation strategy note (Task 9), CLAUDE.md update (Task 12/13).

Noted architectural debt: `JournalRepository` (CRUD orchestrator between providers and DAOs) is absent in Phase 1 — providers call DAOs directly. Phase 4 will need to introduce this layer for sync orchestration.

### QA Specialist (confidence: 0.87)
**Verdict**: Approved after changes. Test suite expanded from 6 to 10 files:
- Added: `session_notifier_test.dart`, `timestamp_utils_test.dart`, `sync_status_test.dart`, `end_session_button_test.dart`
- Expanded: boundary cases for getGreeting (1-day/2-day/null), per-field assertions for endSession, cross-session message isolation, non-repetition for getFollowUp, populated-state session list test
- Added `DateTime? now` parameter to getGreeting for deterministic testing
- Added database teardown requirement for all DAO tests

### Security Specialist (confidence: 0.88)
**Verdict**: Approved after changes. Two items addressed:
1. `*.sqlite` added to `.gitignore` (prevents accidental DB commit)
2. `android:allowBackup="false"` added to Task 1 (prevents unencrypted backup extraction)

Advisory items noted for future phases: enum validation at DAO boundary (pre-Phase 3), manifest security check in quality gate (pre-Phase 4), SQLCipher encryption gate (pre-Phase 4).

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| drift code generation fails | Medium | High (blocks all DB code) | Task 4 has explicit error recovery instructions; re-run build_runner after fixes |
| Flutter version mismatch with dependencies | Low | Medium | pubspec.yaml pins SDK constraint; `flutter pub get` will fail fast if incompatible |
| Windows path issues in shell commands | Medium | Low | All commands use Unix syntax (Git Bash); PATH export included in every command block |
| Test coverage below 80% | Low | Medium | Task 11 specifically targets all business logic; coverage gaps are caught in Task 13 |
| Legacy Python files interfere with Flutter | Low | Medium | Task 1 explicitly removes `src/` and `tests/` |

## Affected Components

**New files** (approximately 25-30 Dart files):
- `lib/database/` — tables, database class, DAOs (5 files + generated)
- `lib/models/` — sync_status enum (1 file; domain models deferred to Phase 3)
- `lib/repositories/` — agent repository (1 file)
- `lib/providers/` — Riverpod providers (3 files)
- `lib/utils/` — utilities (3 files)
- `lib/ui/` — screens, widgets, theme (8 files)
- `lib/main.dart`, `lib/app.dart`
- `test/` — test files (10 files)

**Modified files**:
- `.gitignore` — Flutter entries
- `pubspec.yaml` — dependencies
- `scripts/quality_gate.py` — Flutter/Dart checks

**Removed files**:
- `src/` — legacy Python app code
- `tests/` — legacy Python tests
- `.coverage` — Python coverage artifact

## Dependencies

- **Depends on**: Flutter SDK installed (done), Android SDK configured (done)
- **Blocked by**: Nothing — this is the first implementation phase
- **Blocks**: Phase 2 (Assistant Registration), Phase 3 (LLM Integration), all subsequent phases

## Execution Notes for Agents

1. **Execute tasks in order** (1 through 13). Tasks have sequential dependencies.
2. **After Task 4**, always verify `*.g.dart` files were generated before proceeding.
3. **PATH**: Every `flutter` or `dart` command needs `export PATH="$PATH:/c/src/flutter/bin"` prepended.
4. **Comment everything**: The developer is learning Flutter. Every file should have a header comment explaining its purpose, and non-obvious logic should have inline comments.
5. **Prefer explicit code**: No Dart "magic". Named parameters, explicit types, clear variable names.
6. **When stuck**: If a command fails, read the error output carefully, fix the issue, and retry. Do not skip tasks.
7. **drift pattern**: Write table definitions → run build_runner → then write code that uses generated classes. Never import `*.g.dart` files before they exist.
