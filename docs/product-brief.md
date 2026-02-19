---
document_type: product-brief
title: "Agentic Journal — Cross-Platform AI Journaling App"
version: "1.0"
status: draft
created: 2026-02-18
tech_stack: [Flutter, Dart, Riverpod, drift, Supabase, Claude API]
phases: 6
target_mvp: "Phase 5 (Search + Memory Recall)"
---

## Related ADRs

- [ADR-0002: Flutter/Dart Cross-Platform Tech Stack](adr/ADR-0002-flutter-dart-tech-stack.md)
- [ADR-0003: Supabase as Cloud Backend](adr/ADR-0003-supabase-cloud-backend.md)
- [ADR-0004: Offline-First with Local SQLite Source of Truth](adr/ADR-0004-offline-first-architecture.md)
- [ADR-0005: Claude API via Supabase Edge Function Proxy](adr/ADR-0005-claude-api-proxy.md)
- [ADR-0006: Three-Layer Agent Design](adr/ADR-0006-layered-agent-design.md)

## Sprint Decomposition

Each phase in this brief will become a `SPEC-*` file in `docs/sprints/` when ready for implementation. Use `/plan` to generate a spec from a phase — this transforms the high-level phase description into an implementable sprint plan with task breakdown, acceptance criteria, and test strategy.

---

# Agentic Journal — Unified Build Plan (Agent-Ready)

## Project Summary

Build a **cross-platform AI journaling app** using **Flutter/Dart** that:

1. Registers as Android's **default digital assistant** (launchable via long-press Home/Power gesture)
2. Runs an **agentic journaling conversation** with context-aware follow-ups
3. Stores entries **offline-first** in local SQLite via `drift`
4. **Syncs to Supabase** (PostgreSQL) when connectivity is available
5. Supports **querying past entries** as an "external memory" via keyword search and future RAG
6. Is **cross-platform from day one** (Android primary, iOS secondary)

The developer is a **Python/SQL Server specialist** learning Flutter. Provide thorough inline comments, explain architectural decisions, and prefer patterns familiar to Python developers (explicit > implicit, SQL-native where possible).

---

## Tech Stack (Locked Decisions)

| Layer | Technology | Why |
|---|---|---|
| **Framework** | Flutter 3.x + Dart | Cross-platform, AI-tooling-friendly, Dart ≈ Python in approachability |
| **State Management** | Riverpod | Modern, testable, less boilerplate than Bloc |
| **Local Database** | drift (SQLite) | Type-safe SQL — leverages existing SQL expertise |
| **Cloud Backend** | Supabase (PostgreSQL + Auth + pgvector) | SQL-native, RAG-ready, Row Level Security, generous free tier |
| **HTTP Client** | dio | Interceptors for auth, retry logic, logging |
| **AI Conversation** | Claude API (via dio REST calls through a backend proxy) | Best conversation quality; proxy avoids exposing API key in app |
| **Background Sync** | workmanager | Android/iOS background task scheduling |
| **Voice Input** | speech_to_text (Phase 2+) | Cross-platform STT, optional in MVP |
| **Secure Storage** | flutter_secure_storage | API keys, auth tokens, encryption keys |
| **Connectivity** | connectivity_plus | Online/offline state detection |
| **Notifications** | flutter_local_notifications | Journaling reminders (Phase 6) |
| **Assistant Registration** | Native Kotlin via Platform Channel | Required for Android assistant gesture — small native bridge |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        FLUTTER APP                           │
│                                                              │
│  ┌────────────┐  ┌────────────────┐  ┌────────────────────┐ │
│  │  Chat UI   │  │  Session List  │  │  Search / Query UI │ │
│  │  (Journal) │  │  (Browse)      │  │  (Memory Recall)   │ │
│  └─────┬──────┘  └───────┬────────┘  └─────────┬──────────┘ │
│        │                 │                      │            │
│  ┌─────▼─────────────────▼──────────────────────▼──────────┐ │
│  │              Riverpod State Layer                        │ │
│  │  - SessionNotifier (active conversation state)          │ │
│  │  - SessionListNotifier (browsing / search results)      │ │
│  │  - SyncStatusNotifier (connectivity + sync state)       │ │
│  │  - SettingsNotifier (preferences, auth state)           │ │
│  └──────────────────────┬──────────────────────────────────┘ │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────────┐ │
│  │              Repository Layer                            │ │
│  │  - JournalRepository (CRUD for sessions + messages)     │ │
│  │  - SyncRepository (queue management, upload, download)  │ │
│  │  - AgentRepository (conversation logic, LLM calls)      │ │
│  │  - SearchRepository (FTS queries, future RAG)           │ │
│  └────────┬──────────────────┬─────────────────────────────┘ │
│           │                  │                               │
│  ┌────────▼────────┐  ┌─────▼──────────────┐               │
│  │  drift Database │  │  Remote Services   │               │
│  │  (SQLite)       │  │  - Supabase Client │               │
│  │  - Sessions     │  │  - Claude API Proxy│               │
│  │  - Messages     │  │  - Auth            │               │
│  │  - Sync Queue   │  └────────────────────┘               │
│  └─────────────────┘                                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  Platform Channels (Kotlin bridge)                       ││
│  │  - Assistant gesture registration                        ││
│  │  - VoiceInteractionService (Android-only)                ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
                          │
                 ┌────────▼─────────┐
                 │   CLOUD LAYER    │
                 │                  │
                 │  ┌────────────┐  │
                 │  │ Supabase   │  │  ← PostgreSQL + Auth +
                 │  │ (Postgres) │  │    RLS + pgvector
                 │  └────────────┘  │
                 │                  │
                 │  ┌────────────┐  │
                 │  │ API Proxy  │  │  ← FastAPI or Supabase
                 │  │ (Claude)   │  │    Edge Function
                 │  └────────────┘  │
                 └──────────────────┘
```

---

## Data Model

### Design Principles

- **Normalize conversations**: Session → Messages (1:many). Never store flat text blobs.
- **Track sync state per-session**: each session knows whether it's PENDING, SYNCED, or FAILED.
- **Use UUIDs**: generated client-side so offline creation doesn't conflict.
- **Timestamps as ISO 8601 UTC**: convert to local time only in the UI layer.
- **Design for future RAG**: include fields for embeddings, entities, and sentiment even if nullable in MVP.

### drift Schema (Local SQLite)

```dart
// ===========================================================================
// file: lib/database/tables.dart
// purpose: drift table definitions for the local SQLite database.
//          These mirror the Supabase PostgreSQL schema for sync compatibility.
// ===========================================================================

import 'package:drift/drift.dart';

/// Represents a single journaling session (one conversation).
/// A user triggers the assistant → conversation happens → session closes.
class JournalSessions extends Table {
  // Client-generated UUID — no server round-trip needed for creation
  TextColumn get sessionId => text()();

  // When the session started and ended (UTC ISO 8601)
  DateTimeColumn get startTime => dateTime()();
  DateTimeColumn get endTime => dateTime().nullable()();

  // IANA timezone string (e.g., "America/Denver") for display purposes
  TextColumn get timezone => text().withDefault(const Constant('UTC'))();

  // AI-generated summary of the session (created on session end)
  TextColumn get summary => text().nullable()();

  // AI-inferred mood tag(s), stored as JSON array string: '["happy","tired"]'
  TextColumn get moodTags => text().nullable()();

  // AI-extracted people mentioned, stored as JSON array string: '["Mike","Sarah"]'
  TextColumn get people => text().nullable()();

  // AI-extracted topic/theme tags, stored as JSON array string
  TextColumn get topicTags => text().nullable()();

  // Sync tracking
  // Values: 'PENDING' | 'SYNCED' | 'FAILED'
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();
  DateTimeColumn get lastSyncAttempt => dateTime().nullable()();

  // Standard timestamps
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {sessionId};
}

/// Individual messages within a session (the conversation transcript).
class JournalMessages extends Table {
  // Client-generated UUID
  TextColumn get messageId => text()();

  // Foreign key to JournalSessions
  TextColumn get sessionId => text().references(JournalSessions, #sessionId)();

  // Who sent this message
  // Values: 'USER' | 'ASSISTANT' | 'SYSTEM'
  TextColumn get role => text()();

  // The actual message content
  TextColumn get content => text()();

  // When this message was sent (UTC)
  DateTimeColumn get timestamp => dateTime()();

  // How the user entered this message (for analytics/UX decisions)
  // Values: 'TEXT' | 'VOICE'
  TextColumn get inputMethod => text().withDefault(const Constant('TEXT'))();

  // === Future fields (nullable, populated by AI processing later) ===

  // Named entities extracted from this message (JSON)
  TextColumn get entitiesJson => text().nullable()();

  // Sentiment score (-1.0 to 1.0, nullable)
  RealColumn get sentiment => real().nullable()();

  // Reference to an embedding vector (stored separately or in Supabase pgvector)
  TextColumn get embeddingId => text().nullable()();

  @override
  Set<Column> get primaryKey => {messageId};
}
```

### Supabase PostgreSQL Schema (Cloud — mirrors local)

```sql
-- ===========================================================================
-- file: supabase/migrations/001_initial_schema.sql
-- purpose: Cloud-side tables that mirror the local drift schema.
--          Includes RLS policies so each user can only access their own data.
-- ===========================================================================

-- Enable pgvector extension for future RAG / semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
    sync_status    TEXT NOT NULL DEFAULT 'SYNCED',  -- cloud copy is always "synced"
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE journal_messages (
    message_id     UUID PRIMARY KEY,
    session_id     UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    role           TEXT NOT NULL CHECK (role IN ('USER', 'ASSISTANT', 'SYSTEM')),
    content        TEXT NOT NULL,
    timestamp      TIMESTAMPTZ NOT NULL,
    input_method   TEXT NOT NULL DEFAULT 'TEXT' CHECK (input_method IN ('TEXT', 'VOICE')),
    entities_json  JSONB,
    sentiment      DOUBLE PRECISION,
    embedding_id   UUID,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Future: embeddings table for RAG
CREATE TABLE entry_embeddings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    chunk_text     TEXT NOT NULL,
    embedding      vector(1536),  -- dimensions match the embedding model used
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX idx_sessions_user_date ON journal_sessions(user_id, start_time DESC);
CREATE INDEX idx_messages_session ON journal_messages(session_id, timestamp ASC);
CREATE INDEX idx_sessions_sync ON journal_sessions(sync_status) WHERE sync_status != 'SYNCED';

-- Full-text search index on message content
CREATE INDEX idx_messages_content_trgm ON journal_messages USING gin(content gin_trgm_ops);

-- Row Level Security: users can only access their own sessions and messages
ALTER TABLE journal_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE entry_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can CRUD their own sessions"
    ON journal_sessions FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD messages in their own sessions"
    ON journal_messages FOR ALL
    USING (
        session_id IN (
            SELECT session_id FROM journal_sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can CRUD embeddings for their own sessions"
    ON entry_embeddings FOR ALL
    USING (
        session_id IN (
            SELECT session_id FROM journal_sessions WHERE user_id = auth.uid()
        )
    );
```

---

## Agent Design (Layered)

### Layer A — MVP Agent (Ships in Phase 1)

The MVP agent works **without any LLM call** so it functions fully offline. It uses rule-based follow-up logic.

```
BEHAVIOR:
1. Determine greeting based on time of day:
   - 5 AM – 11:59 AM  → "Good morning! Any plans or thoughts for today?"
   - 12 PM – 4:59 PM  → "How's your afternoon going?"
   - 5 PM – 9:59 PM   → "How was your day?"
   - 10 PM – 4:59 AM  → "Still up? What's on your mind?"
   - After 2+ day gap  → "It's been a few days — want to catch up?"

2. After user responds, ask 2-4 follow-ups based on keyword detection:
   - Emotional words (stressed, angry, happy, excited, sad, anxious, frustrated)
     → "What brought that on?" / "Tell me more about how that felt."
   - People names or references (he/she/they/we, proper nouns)
     → "Who were you with?" / "How did that go with them?"
   - Work/project references (meeting, deadline, project, client, boss)
     → "How did that turn out?" / "What's the next step?"
   - If no keywords detected:
     → "Anything else on your mind?" / "What was the highlight of your day?"

3. After 2-4 follow-ups OR user says they're done:
   → "Got it. Here's what I captured: [summary]. Anything to add?"
   → End session, generate summary locally.

4. Summary generation (offline):
   - Concatenate user messages
   - Extract first sentence of each as bullet points
   - This is a placeholder until LLM summarization is available
```

### Layer B — LLM-Enhanced Agent (Phase 3)

When connectivity exists, replace rule-based logic with Claude API calls via a backend proxy.

```
SYSTEM PROMPT (sent to Claude API):
---
You are a personal journal assistant. Your role is to help the user capture
their day through natural, warm conversation.

Rules:
- Start with the provided opening prompt (based on time of day)
- Ask 2-3 focused follow-up questions to draw out details
- Focus on: what happened, how they felt, who they were with, what they learned
- Be warm but concise — keep questions focused, one at a time
- When the user seems done, provide a brief summary of what was captured
- Do NOT invent or assume details the user didn't mention

After the conversation ends, return a structured JSON block:
{
  "summary": "2-3 sentence summary of the session",
  "mood_tags": ["happy", "tired"],
  "people": ["Mike", "Sarah"],
  "topic_tags": ["work", "exercise", "family"]
}
---

IMPLEMENTATION:
- Send conversation history as messages array to Claude API
- Parse the structured JSON from the final assistant response
- Store parsed tags in the JournalSession record
- If Claude API is unreachable, fall back to Layer A (rule-based)
```

### Layer C — Memory Recall / Query Mode (Phase 5)

The app must distinguish between **journaling** (capturing new entries) and **querying** (asking about past entries).

```
INTENT CLASSIFICATION (simple keyword/pattern matching):
- Query indicators: "what did I", "when did I", "last time", "do you remember",
  "what happened on", "who did I", "how many times", question marks about past events
- Journal indicators: everything else (statements, present tense, feelings, events)

QUERY PIPELINE:
1. Detect query intent
2. Extract date references (if any) and keywords
3. Search local SQLite:
   a. Date filter on journal_sessions.start_time
   b. FTS / LIKE search on journal_messages.content
   c. JSON search on people, mood_tags, topic_tags
4. If online and local results are insufficient:
   a. Hit Supabase pgvector for semantic search on entry_embeddings
5. Feed retrieved session summaries + relevant messages as context to Claude
6. Claude synthesizes an answer GROUNDED ONLY in the provided context
7. Display answer with source session references (tappable links to full transcripts)

ANTI-HALLUCINATION RULE:
- Claude's system prompt for query mode explicitly states:
  "Answer ONLY based on the journal entries provided below. If the information
   is not in the entries, say 'I don't have a journal entry about that.'
   Never invent or assume details."
```

---

## API Proxy Decision

**Do NOT call the Claude API directly from the phone.** Route through a backend proxy.

### Why

- **API key security**: Embedding an API key in a mobile app binary is extractable. A proxy keeps the key server-side.
- **Cost control**: The proxy can enforce rate limits, track token usage per user, and cap spending.
- **Prompt management**: System prompts live server-side, so you can update conversation behavior without shipping an app update.
- **Future flexibility**: Swap Claude for another model, add caching, or add preprocessing without touching the client.

### Implementation Options (Pick One)

**Option A: Supabase Edge Function (Recommended for MVP)**
- Write a Deno/TypeScript edge function hosted on Supabase
- Receives conversation messages from the app
- Calls Claude API with the system prompt + messages
- Returns the response
- Zero additional infrastructure to manage

**Option B: Dedicated FastAPI Backend**
- Deploy a small FastAPI service (familiar stack for the developer)
- More control over logging, caching, and prompt versioning
- More infrastructure to manage
- Better choice if you want to add complex server-side processing later

**For MVP, use Option A (Supabase Edge Function).** Migrate to Option B if/when you need more server-side logic.

---

## Security & Privacy

Journal entries are deeply personal. Security is not a "later" task.

### MVP Security (Implement in Phase 1)

1. **HTTPS everywhere** — Supabase enforces TLS. Dio client should reject non-TLS connections.
2. **Supabase Auth** — Email/password or magic link. Every API call is authenticated.
3. **Row Level Security** — Already defined in the schema above. Users can only read/write their own data.
4. **flutter_secure_storage** — Store auth tokens and any local encryption keys in the OS keychain (Android Keystore / iOS Keychain).
5. **No API keys in the app binary** — Claude API key lives in the Supabase Edge Function environment variables.

### Phase 2+ Security (Add When Implementing Sync)

6. **Optional biometric app lock** — Gate the journal screen behind fingerprint/face unlock using `local_auth` package.
7. **Optional local database encryption** — Use SQLCipher via drift's encryption support if the user enables it in settings.
8. **Data export** — JSON export of all sessions + messages.
9. **Data deletion** — "Delete all cloud data" button that cascades through Supabase.
10. **Delete cloud copy only** — Keep local, remove cloud. Useful for going offline-only.

---

## Offline-First Sync Engine

### Core Principle

The local SQLite database is the **source of truth**. The cloud is a backup and sync target. The app must function fully without any network connectivity.

### Sync Flow

```
┌─────────────────┐
│ User ends a      │
│ journal session   │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────┐
│ Session saved to drift  │
│ syncStatus = 'PENDING'  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ WorkManager enqueues sync task          │
│ Constraints: network available          │
│ Backoff: exponential (30s → 1m → 5m)   │
│ Policy: KEEP (don't replace pending)    │
└────────┬────────────────────────────────┘
         │
         ▼  (when network available)
┌─────────────────────────────────────────┐
│ SyncWorker executes:                    │
│ 1. Query all sessions WHERE             │
│    syncStatus = 'PENDING' or 'FAILED'   │
│ 2. For each session:                    │
│    a. Upsert session to Supabase        │
│    b. Upsert all messages for session   │
│    c. On success: set syncStatus =      │
│       'SYNCED', update lastSyncAttempt  │
│    d. On failure: set syncStatus =      │
│       'FAILED', update lastSyncAttempt  │
│ 3. Return Result.success() or retry()   │
└─────────────────────────────────────────┘
```

### Conflict Resolution (Simple — MVP)

- **Last-write-wins** based on `updated_at` timestamp.
- This is sufficient for a single-user journaling app.
- If multi-device support is added later, implement a merge strategy using per-field timestamps.

### Idempotent Uploads

- Use `UPSERT` (INSERT ... ON CONFLICT UPDATE) for all Supabase writes.
- UUIDs are generated client-side, so re-uploading the same session is safe.
- The sync worker can safely retry without creating duplicates.

---

## Default Assistant Registration (Android Platform Channel)

### Android-Side (Kotlin)

```kotlin
// ===========================================================================
// file: android/app/src/main/kotlin/.../AssistantActivity.kt
// purpose: Handles the ACTION_ASSIST intent so the OS can launch this app
//          when the user triggers the assistant gesture (long-press Home).
// ===========================================================================

// In AndroidManifest.xml, add this intent filter to your main activity:
// <intent-filter>
//     <action android:name="android.intent.action.ASSIST" />
//     <category android:name="android.intent.category.DEFAULT" />
// </intent-filter>

// Optionally, implement VoiceInteractionService for deeper integration:
// This allows the OS to treat the app as a full assistant replacement.
// See: https://developer.android.com/reference/android/service/voice/VoiceInteractionService
```

### Flutter-Side (Platform Channel)

```dart
// ===========================================================================
// file: lib/services/assistant_registration_service.dart
// purpose: Platform channel to check/request default assistant status.
//          Android-only — on iOS this is a no-op.
// ===========================================================================

import 'package:flutter/services.dart';

class AssistantRegistrationService {
  static const _channel = MethodChannel('com.divinerdojo.journal/assistant');

  /// Check if this app is currently set as the default assistant.
  Future<bool> isDefaultAssistant() async {
    try {
      return await _channel.invokeMethod<bool>('isDefaultAssistant') ?? false;
    } on PlatformException {
      return false;
    }
  }

  /// Open the system settings screen where the user can set the default assistant.
  Future<void> openAssistantSettings() async {
    try {
      await _channel.invokeMethod('openAssistantSettings');
    } on PlatformException {
      // Fallback: open general app settings
    }
  }
}
```

### User-Facing Setup

Include a Settings screen with:
- A card showing current default assistant status
- A "Set as Default Assistant" button that calls `openAssistantSettings()`
- Clear instructions: "Go to Settings → Apps → Default Apps → Digital Assistant → Select Agentic Journal"
- A note: "On some devices, this also maps to long-press Power button"

---

## Project Structure

```
agentic_journal/
├── android/
│   └── app/src/main/
│       ├── kotlin/com/divinerdojo/journal/
│       │   └── MainActivity.kt          # Platform channel + assistant intent
│       └── AndroidManifest.xml           # ACTION_ASSIST intent filter
├── ios/                                  # iOS-specific (minimal for MVP)
├── lib/
│   ├── main.dart                         # App entry point, Riverpod ProviderScope
│   ├── app.dart                          # MaterialApp, routing, theme
│   │
│   ├── database/
│   │   ├── app_database.dart             # drift database class, migration strategy
│   │   ├── tables.dart                   # Table definitions (JournalSessions, JournalMessages)
│   │   └── daos/
│   │       ├── session_dao.dart          # CRUD operations for sessions
│   │       └── message_dao.dart          # CRUD operations for messages
│   │
│   ├── models/
│   │   ├── journal_session.dart          # Domain model (separate from drift table)
│   │   ├── journal_message.dart          # Domain model
│   │   └── sync_status.dart              # Enum: PENDING, SYNCED, FAILED
│   │
│   ├── repositories/
│   │   ├── journal_repository.dart       # Orchestrates local DB + remote sync
│   │   ├── sync_repository.dart          # Manages sync queue and upload logic
│   │   ├── agent_repository.dart         # Conversation logic (rule-based + LLM)
│   │   └── search_repository.dart        # FTS search, date filtering, future RAG
│   │
│   ├── providers/
│   │   ├── database_provider.dart        # Riverpod provider for drift DB instance
│   │   ├── session_providers.dart        # Active session state, session list
│   │   ├── sync_providers.dart           # Sync status, connectivity state
│   │   └── settings_providers.dart       # User preferences, auth state
│   │
│   ├── services/
│   │   ├── claude_api_service.dart       # HTTP calls to Claude proxy (Supabase Edge Fn)
│   │   ├── supabase_service.dart         # Supabase client setup, auth, CRUD
│   │   ├── sync_worker.dart              # WorkManager background sync logic
│   │   ├── assistant_registration.dart   # Platform channel for assistant gesture
│   │   └── connectivity_service.dart     # Online/offline state monitoring
│   │
│   ├── ui/
│   │   ├── screens/
│   │   │   ├── journal_session_screen.dart   # Main chat UI (journaling conversation)
│   │   │   ├── session_list_screen.dart      # Browse sessions by date
│   │   │   ├── session_detail_screen.dart    # View full transcript of a past session
│   │   │   ├── search_screen.dart            # Keyword search across sessions
│   │   │   ├── settings_screen.dart          # Assistant setup, privacy, export/delete
│   │   │   └── onboarding_screen.dart        # First-launch setup (auth, assistant config)
│   │   │
│   │   ├── widgets/
│   │   │   ├── chat_bubble.dart              # Individual message bubble (user vs assistant)
│   │   │   ├── session_card.dart             # Session preview in list view
│   │   │   ├── mood_tag_chip.dart            # Colored chip for mood tags
│   │   │   ├── sync_status_indicator.dart    # Visual indicator of sync state
│   │   │   └── end_session_button.dart       # Button to close session + generate summary
│   │   │
│   │   └── theme/
│   │       └── app_theme.dart                # Color scheme, typography, dark mode
│   │
│   └── utils/
│       ├── uuid_generator.dart               # Client-side UUID generation
│       ├── timestamp_utils.dart              # UTC conversion, timezone handling
│       └── keyword_extractor.dart            # Rule-based keyword detection for Layer A agent
│
├── supabase/
│   ├── migrations/
│   │   └── 001_initial_schema.sql            # Tables, indexes, RLS (defined above)
│   └── functions/
│       └── claude-proxy/
│           └── index.ts                      # Edge Function: proxies Claude API calls
│
├── test/
│   ├── database/                             # drift DAO tests
│   ├── repositories/                         # Repository unit tests
│   └── ui/                                   # Widget tests
│
├── pubspec.yaml                              # Dependencies
└── README.md
```

---

## Phased Build Plan

### Phase 1: Walking Skeleton (Week 1-2)

**Goal:** Have a working journaling conversation that saves locally.

**Tasks:**

1. **Project setup**
   - Create Flutter project: `flutter create --org com.divinerdojo agentic_journal`
   - Add dependencies to `pubspec.yaml` (drift, riverpod, dio, uuid, flutter_secure_storage, connectivity_plus)
   - Configure drift code generation (`build.yaml`)
   - Set up project structure (directories as defined above)

2. **Database layer**
   - Define drift tables (`tables.dart`)
   - Create `AppDatabase` class with migration strategy
   - Implement `SessionDao` — createSession, endSession, getSessionsByDate, getSessionById
   - Implement `MessageDao` — insertMessage, getMessagesForSession
   - Write unit tests for DAOs

3. **Rule-based agent (Layer A)**
   - Implement `keyword_extractor.dart` — detect emotional, social, work-related keywords
   - Implement `agent_repository.dart`:
     - `getGreeting()` → time-of-day aware opening prompt
     - `getFollowUp(conversationHistory)` → rule-based follow-up question
     - `generateLocalSummary(messages)` → simple concatenation-based summary
   - Track follow-up count; stop after 2-4 follow-ups

4. **Chat UI**
   - Build `journal_session_screen.dart`:
     - Text input field at bottom
     - Scrollable message list (chat bubbles)
     - Auto-scroll to latest message
     - End session button in app bar
   - Build `chat_bubble.dart` — visually distinguish USER vs ASSISTANT messages
   - Wire up Riverpod providers:
     - `activeSessionProvider` — holds current session ID and message list
     - Messages persist to drift immediately on send

5. **Session lifecycle**
   - On app launch → create new JournalSession → display greeting
   - Each user message → save to drift → get agent follow-up → save follow-up → display
   - End session → generate local summary → update session record → navigate to session list

6. **Basic navigation**
   - Session list screen (shows past sessions sorted by date descending)
   - Tap session → session detail screen (full transcript)
   - Floating action button → start new session

**Definition of Done (Phase 1):**
- [ ] App launches and displays a greeting
- [ ] User can type messages and receive rule-based follow-ups
- [ ] All messages persist in local SQLite (survives app restart)
- [ ] User can end a session and see a summary
- [ ] User can browse past sessions by date
- [ ] User can view full transcript of any past session
- [ ] Works completely offline (no network calls needed)

---

### Phase 2: Assistant Registration + Voice (Week 3)

**Goal:** Launch from assistant gesture; optionally accept voice input.

**Tasks:**

1. **Android assistant integration**
   - Add `ACTION_ASSIST` intent filter to `AndroidManifest.xml`
   - Implement platform channel in `MainActivity.kt`
   - Implement `AssistantRegistrationService` (Flutter side)
   - Build settings card showing default assistant status with setup button

2. **Voice input (optional, stretch)**
   - Add `speech_to_text` dependency
   - Add microphone button to chat input bar
   - On tap: start listening → transcribe → insert as text message
   - Store `inputMethod = 'VOICE'` on the message record

3. **Onboarding flow**
   - First-launch screen explaining the app
   - Guide user to set as default assistant
   - Request microphone permission (if voice enabled)

**Definition of Done (Phase 2):**
- [ ] Long-press Home (or Power, on supported devices) opens the app
- [ ] Settings screen shows assistant status and setup instructions
- [ ] (Stretch) Voice input works and transcribes to text

---

### Phase 3: LLM-Enhanced Conversations (Week 4)

**Goal:** Claude API integration for smarter follow-ups, summaries, and tagging.

**Tasks:**

1. **Supabase Edge Function (Claude proxy)**
   - Create `supabase/functions/claude-proxy/index.ts`
   - Accepts: `{ messages: [...], system_prompt: "..." }`
   - Calls Claude API with the journaling system prompt
   - Returns assistant response + structured JSON (summary, mood, people, topics)
   - Store Claude API key as Supabase secret (not in client code)

2. **Claude API service (Flutter)**
   - Implement `claude_api_service.dart`
   - POST conversation history to Supabase Edge Function
   - Parse response: extract chat response + JSON metadata
   - Handle timeout/failure → fall back to Layer A rule-based agent

3. **Enhanced agent repository**
   - Update `agent_repository.dart`:
     - If online → call Claude API via proxy
     - If offline → fall back to Layer A (rule-based)
   - On session end: call Claude for final summary + tags
   - Parse and store: `summary`, `moodTags`, `people`, `topicTags`

4. **Context-aware prompts**
   - Morning vs. evening vs. returning-after-gap greetings
   - Include session count and days since last session in the system prompt context

**Definition of Done (Phase 3):**
- [ ] When online, Claude provides follow-up questions and summaries
- [ ] When offline, app falls back to rule-based follow-ups seamlessly
- [ ] Sessions have AI-generated summaries, mood tags, people, and topic tags
- [ ] API key is never present in the app binary

---

### Phase 4: Cloud Sync (Week 5)

**Goal:** Sessions sync to Supabase; app works fully offline and syncs when reconnected.

**Tasks:**

1. **Supabase setup**
   - Run migration `001_initial_schema.sql`
   - Configure Supabase Auth (email/password for MVP)
   - Test RLS policies

2. **Auth flow in app**
   - Sign up / sign in screen
   - Store auth token in `flutter_secure_storage`
   - Initialize Supabase client with auth on app start

3. **Sync engine**
   - Implement `sync_repository.dart`:
     - `syncPendingSessions()` — query drift for PENDING/FAILED, upsert to Supabase
     - `downloadRemoteSessions()` — pull sessions from Supabase not in local DB (for multi-device)
   - Implement `sync_worker.dart`:
     - WorkManager periodic task (every 15 minutes when online)
     - WorkManager one-shot task (triggered when session ends)
     - Exponential backoff on failure

4. **Connectivity handling**
   - `connectivity_service.dart` — monitor network state changes
   - When connectivity restored → trigger one-shot sync
   - UI indicator showing sync status (synced ✓, pending ↻, failed ✗)

5. **Sync status UI**
   - `sync_status_indicator.dart` — small icon on session cards
   - Settings screen shows: last sync time, pending count, "Sync Now" button

**Definition of Done (Phase 4):**
- [ ] User can sign up / sign in
- [ ] Sessions sync to Supabase when online
- [ ] Sync retries automatically on failure with backoff
- [ ] Sync happens in background via WorkManager
- [ ] UI shows sync status per session
- [ ] App works fully offline; syncs when reconnected

---

### Phase 5: Search + Memory Recall (Week 6)

**Goal:** User can search past entries and ask natural language questions about their history.

**Tasks:**

1. **Keyword search (local)**
   - Implement FTS (Full-Text Search) in drift using `fts5`
   - Search across `journal_messages.content`
   - Filter by date range, mood tags, people
   - Build search UI with filters

2. **Intent classification**
   - Implement simple pattern matching to distinguish journal mode vs. query mode
   - When query detected → switch to retrieval pipeline instead of journaling flow

3. **Memory recall pipeline**
   - Retrieve relevant sessions based on date + keyword filters
   - Format retrieved entries as context for Claude
   - Claude synthesizes answer grounded in the retrieved context
   - Display answer with links to source sessions

4. **(Stretch) Semantic search**
   - Generate embeddings for session summaries (via Claude or another embedding model)
   - Store in Supabase pgvector
   - Use cosine similarity search for semantic queries

**Definition of Done (Phase 5):**
- [ ] User can search by keyword across all sessions
- [ ] User can filter sessions by date range, mood, and people
- [ ] User can ask "What did I do last Thursday?" and get a grounded answer
- [ ] Answers cite source sessions (tappable to view transcript)
- [ ] No hallucinated memories — answers only reference stored data

---

### Phase 6: Polish + Extend (Week 7+)

**Goal:** Production readiness, quality of life, and expansion features.

**Tasks:**

1. **Data portability**
   - Export all data as JSON
   - Export as formatted Markdown (human-readable journal)
   - Delete all cloud data (keep local)
   - Delete all data (local + cloud)

2. **Biometric lock**
   - `local_auth` package for fingerprint/face unlock
   - Optional setting: require biometric to open the app

3. **Journaling reminders**
   - `flutter_local_notifications` — configurable daily reminder
   - "You haven't journaled in 2 days" nudge

4. **UI polish**
   - Dark mode support
   - Mood tag color coding
   - Session summary cards with tags and people chips
   - Smooth animations and transitions

5. **iOS build + testing**
   - Test on iOS simulator
   - Handle iOS-specific permissions (microphone, notifications)
   - Note: assistant gesture is Android-only; on iOS, the app is launched normally

---

## Phase 2+ Roadmap (Post-MVP Ideas)

These are future features to consider after the core app is stable:

- **Weekly / monthly reflection summaries** — AI-generated digest of patterns, moods, recurring themes
- **Mood tracking dashboard** — visualize mood over time (charts)
- **Photo attachment** — snap a photo during journaling, stored with the entry
- **Location tagging** — auto-tag entries with current location
- **Actionable intents** — "Remind me to call Mike" → create a local notification
- **Therapist export** — formatted PDF export for mental health professionals
- **Wearable integration** — pull heart rate / stress data for mood correlation
- **On-device model** — small local LLM for fully offline AI conversations (Gemma, Phi)
- **Multi-device sync** — proper conflict resolution for editing from phone + tablet

---

## Definition of Done (Overall MVP — End of Phase 5)

- [ ] Launchable from Android assistant gesture on supported devices
- [ ] Cross-platform: runs on Android and iOS from the same codebase
- [ ] Captures full journaling conversations with AI follow-ups (online) or rule-based follow-ups (offline)
- [ ] All data persists locally in SQLite (survives app restart, works offline)
- [ ] Syncs to Supabase when online, with automatic retry
- [ ] User can browse sessions by date
- [ ] User can search by keyword, date, mood, and people
- [ ] User can ask natural language questions about past entries (grounded in stored data)
- [ ] User can export all data as JSON
- [ ] User can delete cloud data
- [ ] API keys are never in the app binary
- [ ] Auth with Row Level Security ensures data isolation
- [ ] No hallucinated memories — all answers cite stored journal entries

---

## Agent Instructions

When implementing this project:

1. **Start with Phase 1.** Do not skip ahead. Each phase builds on the previous.
2. **Test each layer before moving on.** Write unit tests for DAOs and repositories.
3. **Commit after each completed task** within a phase.
4. **Use drift's code generation** — run `dart run build_runner build` after changing table definitions.
5. **Keep the rule-based agent working at all times** — it is the offline fallback and must never be removed.
6. **Never hardcode API keys in Dart code.** Use environment variables or Supabase secrets.
7. **Follow the project structure exactly** as defined above. Do not flatten or restructure.
8. **Comment thoroughly** — the developer is learning Flutter and benefits from inline explanations.
9. **Prefer explicit over implicit** — avoid Dart "magic" or overly terse patterns. Clarity > brevity.
10. **When in doubt, ask** — flag architectural decisions that aren't covered in this plan rather than guessing.
