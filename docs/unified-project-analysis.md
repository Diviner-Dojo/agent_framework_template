---
id: ANALYSIS-20260218-unified-flutter-journal
type: cross-project-analysis
date: 2026-02-18
status: complete
projects_analyzed:
  - BasedHardware/omi
  - geosmart/lumma
  - Chevey339/kelivo
  - ZhuJHua/moodiary
  - Mr-Pepe/syncable
scoring_rubric: prevalence/elegance/evidence/fit/maintenance (5 each, max 25)
recommendation_threshold: ">=20/25"
---

# Unified Cross-Project Analysis: Flutter Agentic Journal Patterns

## Executive Summary

Five open-source projects were analyzed to extract adoptable architectural patterns for the Agentic Journal — a Flutter/Dart mobile app combining offline-first sync (Drift + Supabase), agentic AI conversations (Claude API), RAG over personal journal data, and Riverpod state management.

**No single repository covers all requirements**, but studied together these five projects provide complete coverage across the 10 architectural dimensions. This document synthesizes findings into prioritized, actionable recommendations.

### Key Findings

| Priority | Pattern | Source Repo(s) | Score | Impact |
|----------|---------|---------------|-------|--------|
| P0 | Bidirectional Drift↔Supabase sync | syncable | 23/25 | Foundation for offline-first |
| P0 | `data:`/`think:` SSE streaming protocol | omi, kelivo | 23/25 | Streaming chat architecture |
| P0 | Dual-namespace vector separation (entries vs facts) | omi | 23/25 | RAG schema design |
| P0 | Multi-provider LLM abstraction with Claude | kelivo | 22/25 | Core AI integration |
| P0 | Streaming chat with tool calling | kelivo, omi | 22/25 | Agentic conversations |
| P0 | Conflict resolution via PostgreSQL triggers | syncable | 22/25 | Data integrity |
| P0 | LLM-adjudicated memory deduplication | omi | 22/25 | Memory quality |
| P0 | PageContext — current-screen awareness injection | omi | 22/25 | Contextual AI |
| P0 | UUID v7 as offline-first business key | moodiary | High | Identity for sync |
| P1 | Persistent memory extraction from conversations | omi | 21/25 | Context-aware journaling |
| P1 | MCP integration for agentic tools | kelivo, lumma | 21/25 | Extensible AI capabilities |
| P1 | Agent safety guard (loop/budget detection) | omi | 21/25 | Agentic reliability |
| P1 | Dual-mode journal UX (Q&A + Chat) | lumma | 20/25 | Core journal experience |
| P1 | Custom AI assistant personas | kelivo | 20/25 | Journal-specific AI personality |
| P1 | Material You dynamic color with fallback | moodiary | High | Android-native theming |
| P2 | Rich diary data model with mood/media | moodiary | 20/25 | Feature-complete diary |
| P2 | Privacy-first AI (local + cloud tiers) | moodiary | 20/25 | User trust and offline AI |
| P2 | SharedPreferencesWithCache with allowList | moodiary | High | Settings performance |
| P2 | KeyboardObserver state machine | moodiary | High | Chat/editor UX |
| P2 | Pre-tokenize search at write time (FTS5) | moodiary | Med | Search performance |
| P2 | Batched migration chunking (50 rows) | moodiary | High | Schema evolution |

---

## 1. BasedHardware/omi — RAG + Agentic AI Over Personal Data

### Project Profile

| Attribute | Value |
|-----------|-------|
| Stars | 7,687 |
| Language | Dart (Flutter app) + Python (backend) |
| License | MIT |
| Commits | ~11,000 |
| Architecture | Monorepo: `app/`, `backend/`, `plugins/`, `mcp/` |
| Maturity | Production (shipped wearable product) |

### Architecture Overview

Omi is an AI wearable companion that transcribes conversations and builds a persistent memory system. The Flutter app communicates with a Python/FastAPI backend that handles RAG, memory extraction, and multi-provider LLM integration.

**Monorepo structure:**
- `app/lib/backend/http/api/` — REST API clients (conversations, messages, memories)
- `app/lib/backend/schema/` — Data models (Memory, Conversation, Message)
- `backend/routers/` — FastAPI endpoints
- `backend/scripts/rag/` — Vector embedding and retrieval
- `mcp/` — Model Context Protocol server

### Scored Patterns

#### Pattern 1.1: Persistent Memory Extraction System
**Score: 21/25** (Prevalence: 3, Elegance: 5, Evidence: 5, Fit: 4, Maintenance: 4)

The `Memory` model automatically distills structured facts from unstructured conversations:

```dart
// Memory categorization: system | interesting | manual
class Memory {
  String id, uid, content;
  MemoryCategory category;    // auto-classified
  MemoryVisibility visibility; // private | public
  bool reviewed, manuallyAdded, edited, deleted, isLocked;
  DateTime createdAt, updatedAt;
}
```

**Key insight:** Memories are extracted *from* conversations but stored as independent first-class entities. The `conversationId` field links back to the source, creating a knowledge graph over time. Categories migrate from legacy granular types (hobbies, work, skills) to a simpler three-tier system.

**Adaptation for Agentic Journal:**
- Store extracted insights as `JournalInsight` entities in Drift, linked to source entries
- Use Claude's tool-calling to extract structured data (mood patterns, recurring themes, goals)
- The review/approval pattern (`reviewed`, `userReview` fields) is directly applicable — let users approve AI-extracted insights before they influence future conversations

#### Pattern 1.2: Streaming Chat with Typed Chunk Protocol
**Score: 22/25** (Prevalence: 4, Elegance: 5, Evidence: 5, Fit: 4, Maintenance: 4)

Messages stream via a line-delimited protocol with typed prefixes:

```
think: <reasoning content>
data: <incremental text>
done: <base64-encoded completion JSON>
message: <base64-encoded full message>
```

The `ServerMessageChunk` model handles this:
```dart
enum MessageChunkType { think, data, done, error, message }

class ServerMessageChunk {
  String messageId;
  MessageChunkType type;
  String text;
  ServerMessage? message; // populated on 'done' chunks
}
```

**Key insight:** Separating "thinking" content from "data" content allows UI to show reasoning (extended thinking) separately from the response. The `done` chunk carries the complete message object for persistence.

**Adaptation for Agentic Journal:**
- Implement the same typed-prefix streaming protocol between Flutter and your backend proxy
- Map Claude's extended thinking output to `think:` chunks
- Use `done:` chunks to trigger Drift persistence of the complete message
- Support `__CRLF__` placeholder substitution for multiline streaming

#### Pattern 1.3: Conversation-Memory Architecture (1:Many Sessions)
**Score: 20/25** (Prevalence: 4, Elegance: 4, Evidence: 5, Fit: 4, Maintenance: 3)

```dart
class ServerConversation {
  String id;
  ConversationStatus status; // in_progress | processing | completed | failed
  Structured structured;     // categorized metadata
  List<TranscriptSegment> transcriptSegments;
  List<ConversationPhoto> photos;
  List<AudioFile> audioFiles;
  Geolocation? geolocation;
  // ...
}
```

Conversations carry rich metadata: geolocation, audio files with chunk timestamps, photos, and app integration results. The `status` enum manages lifecycle (in_progress → processing → completed).

**Adaptation for Agentic Journal:**
- Model journal sessions with similar lifecycle states
- Attach geolocation and weather data at session creation time
- The `Structured` sub-object pattern (categorized metadata within a conversation) maps to journal entry metadata (mood, tags, themes)

### Gaps & Risks
- Uses Firebase + Pinecone, not Supabase + pgvector — backend patterns need significant adaptation
- No Riverpod — uses custom state management
- Massive codebase (11k commits) — pattern extraction requires selective focus
- Commercial product — patterns may be over-engineered for an early-stage journal

---

## 2. geosmart/lumma — AI-Native Journal UX

### Project Profile

| Attribute | Value |
|-----------|-------|
| Stars | 159 |
| Language | Dart (Flutter) |
| License | Not specified |
| Default Branch | master |
| Architecture | MVC-like: `lib/dao/`, `lib/service/`, `lib/view/` |
| Maturity | Early (113 commits, small community) |

### Architecture Overview

Lumma is the closest conceptual match — it IS a Flutter AI journal. It uses local Markdown files for storage, WebDAV for sync, and supports multiple LLM providers for AI-assisted journaling.

**Key directories:**
- `lib/dao/diary_dao.dart` — File-based diary persistence (Markdown files)
- `lib/service/` — API provider, diary content, MCP, config services
- `lib/view/pages/` — Journal UI pages (edit, detail, calendar, timeline)
- `lib/model/` — App config, MCP config, sync config

### Scored Patterns

#### Pattern 2.1: Dual-Mode Journal UX (Q&A + Chat)
**Score: 20/25** (Prevalence: 3, Elegance: 4, Evidence: 3, Fit: 5, Maintenance: 5)

Lumma implements two distinct journaling modes:

- **Q&A Mode**: Structured prompts guide reflection. The AI asks questions, the user answers, and entries build as a timeline narrative. Works even without AI connectivity.
- **Chat Mode**: Freeform conversational journaling where the AI acts as a reflective partner.

The diary DAO structures entries with `DiaryEntry(title, time, category, q, a)` — each entry is a question-answer pair that can be rendered as structured content or conversation.

**Key insight:** The Q&A format produces better journal entries for users who struggle with blank-page anxiety. The `q`/`a` structure means entries are inherently structured for later AI analysis.

**Adaptation for Agentic Journal:**
- Implement a `JournalMode` enum: `freeform`, `guided`, `chat`
- In guided mode, Claude generates reflection prompts based on user history
- Store both the prompt and response, enabling later RAG over structured Q&A pairs
- The timeline narrative view works offline (no AI needed) — critical for offline-first

#### Pattern 2.2: Frontmatter-Based Entry Metadata
**Score: 20/25** (Prevalence: 4, Elegance: 4, Evidence: 3, Fit: 4, Maintenance: 5)

```dart
// Entries stored as YYYY-MM-DD.md with YAML frontmatter
// ---
// created: 2026-02-18 10:30:00
// updated: 2026-02-18 11:45:00
// tags: [reflection, goals]
// mood: positive
// ---
// ## Journal Content
```

The `DiaryContentService` parses YAML frontmatter between `---` delimiters, separating metadata from content. `DiaryDao` sorts files by date extracted from filenames.

**Adaptation for Agentic Journal:**
- While you'll use Drift instead of Markdown files, the frontmatter concept maps to structured columns in your journal entry table
- The metadata extraction pattern (AI generates tags/titles from content) is directly adoptable
- Consider exporting entries as Markdown with frontmatter for interoperability (Obsidian, etc.)

#### Pattern 2.3: MCP Integration for Journal Persistence
**Score: 20/25** (Prevalence: 3, Elegance: 4, Evidence: 3, Fit: 5, Maintenance: 5)

```dart
// JSON-RPC 2.0 protocol for MCP communication
{
  'method': 'tools/call',
  'params': { 'name': 'persist_diary', 'arguments': {
    'entityName': entryId,
    'content': diaryText,
    'createTime': timestamp
  }},
  'jsonrpc': '2.0'
}
```

The `McpService` uses a single `persist_diary` tool with Bearer token auth. Includes `testConnection()` for setup validation.

**Adaptation for Agentic Journal:**
- Extend MCP tools beyond persistence: `search_entries`, `get_mood_trends`, `find_related_entries`
- Use MCP as the bridge between Claude's tool-calling and your Drift database
- The JSON-RPC 2.0 pattern is standard and reusable

### Gaps & Risks
- No Drift, no Supabase, no Riverpod — entirely different data layer
- Small project (159 stars, 2 contributors) — limited battle-testing
- No RAG — AI features are prompt-based only
- GetX for state management (not Riverpod)
- The actual Q&A/Chat mode switching logic is in widgets not fully exposed — architectural patterns are more conceptual than concrete

---

## 3. Chevey339/kelivo — Claude API + MCP in Flutter

### Project Profile

| Attribute | Value |
|-----------|-------|
| Stars | 1,599 |
| Language | Dart (Flutter) |
| License | AGPL-3.0 |
| Default Branch | master |
| Architecture | Feature-layered: `lib/core/{models,providers,services}/` |
| Maturity | Production (App Store, 1000 commits) |

### Architecture Overview

Kelivo is the strongest reference for Claude API integration in Flutter. It supports Claude, OpenAI, Gemini, and DeepSeek with streaming, tool calling, and MCP. The architecture separates models, providers (state), and services (business logic).

**Key directories:**
- `lib/core/services/api/chat_api_service.dart` — Multi-provider LLM abstraction
- `lib/core/services/chat/` — Chat service, prompt transformer, document extraction
- `lib/core/services/mcp/` — MCP tool service + built-in fetch tool
- `lib/core/models/` — Assistant, Conversation, ChatMessage, ChatItem
- `lib/core/providers/` — Chat, MCP, Model, Assistant providers
- `dependencies/mcp_client/` — Full MCP client library (in-repo)

### Scored Patterns

#### Pattern 3.1: Multi-Provider LLM Abstraction with Claude
**Score: 22/25** (Prevalence: 4, Elegance: 5, Evidence: 5, Fit: 4, Maintenance: 4)

The `ChatApiService` classifies providers and routes to specialized stream handlers:

```dart
final kind = ProviderConfig.classify(config.id, explicitType: config.providerType);
if (kind == ProviderKind.openai) {
  yield* _sendOpenAIStream(...);
} else if (kind == ProviderKind.claude) {
  yield* _sendClaudeStream(...);
} else if (kind == ProviderKind.google) {
  yield* _sendGoogleStream(...);
}
```

All providers share a unified interface:
```dart
static Stream<ChatStreamChunk> sendMessageStream({
  required ProviderConfig config,
  required String modelId,
  required List<Map<String, dynamic>> messages,
  List<Map<String, dynamic>>? tools,
  Function(String name, Map args)? onToolCall,
  // ...
})
```

**Key insights:**
- Provider-specific logic is isolated in private methods (`_sendClaudeStream`, `_sendOpenAIStream`)
- Tool calling follows a loop pattern: stream → accumulate tool calls → execute → append results → re-stream
- Vendor-specific knobs (reasoning effort, thinking budget) are normalized through a unified parameter
- `ModelInfo` with per-instance overrides allows treating the same model differently across deployments

**Adaptation for Agentic Journal:**
- Start with Claude-only, but use this abstraction pattern for future provider flexibility
- The tool-calling loop is directly adoptable for agentic journal features (search entries, mood analysis, goal tracking)
- The `ProviderConfig` + `ModelInfo` pattern maps to your app settings for model selection

#### Pattern 3.2: MCP Tool Service Architecture
**Score: 21/25** (Prevalence: 3, Elegance: 5, Evidence: 4, Fit: 5, Maintenance: 4)

```dart
// Tools bound per-conversation via MCP server IDs
class McpToolService {
  listAvailableToolsForConversation(conversationId) → tools
  listAvailableToolsForAssistant(assistantId) → tools
  callToolForConversation(conversationId, toolName, args) → result
}
```

Features:
- Per-conversation MCP server selection (different tools for different contexts)
- Multi-content-type result handling (text, images saved as `[image:path]`, resource URIs)
- Structured error feedback enabling model self-correction
- Built-in `kelivo_fetch` tool as reference implementation

**Adaptation for Agentic Journal:**
- Create journal-specific MCP tools: `search_entries(query, date_range)`, `get_mood_trend(period)`, `find_similar_entries(entry_id)`, `extract_action_items(entry_id)`
- Bind different tool sets to different conversation modes (reflective journaling gets mood tools, goal-setting gets action-item tools)
- The error feedback pattern (structured JSON with tool name, args, schema) helps Claude retry intelligently

#### Pattern 3.3: Custom AI Assistant Personas
**Score: 20/25** (Prevalence: 4, Elegance: 4, Evidence: 4, Fit: 4, Maintenance: 4)

```dart
class Assistant {
  String id, name, systemPrompt;
  String? messageTemplate;      // "{{ message }}" for input formatting
  double temperature;            // 0.0-2.0
  int contextMessageSize;        // default 64
  int? thinkingBudget, maxTokens;
  bool enableMemory;
  bool enableRecentChatsReference;
  List<String> mcpServerIds;     // per-persona tool sets
  List<PresetMessage> presetMessages; // conversation starters
  // ...
}
```

**Key insight:** Each persona is a complete behavioral configuration — not just a system prompt, but temperature, context window, tools, and memory settings. The `presetMessages` field provides conversation starters that guide the interaction.

**Adaptation for Agentic Journal:**
- Create personas: "Reflective Journal Coach" (empathetic, guided prompts), "Goal Tracker" (action-oriented), "Gratitude Guide" (positive focus)
- Use `presetMessages` as guided journaling prompts that change with persona
- The `enableRecentChatsReference` flag maps to your RAG toggle — should the AI reference past entries?
- `contextMessageSize: 64` as default is a good starting point for journal conversations

#### Pattern 3.4: Prompt Transformation Pipeline
**Score: 20/25** (Prevalence: 4, Elegance: 4, Evidence: 4, Fit: 4, Maintenance: 4)

Two-tier placeholder system:
1. **System-level placeholders**: `{cur_date}`, `{cur_time}`, `{timezone}`, `{os_type}`, `{nickname}`, `{assistant_name}`, `{model_id}`
2. **Message-level templates**: `{{ role }}`, `{{ message }}`, `{{ time }}`, `{{ date }}`

**Adaptation for Agentic Journal:**
- Add journal-specific placeholders: `{mood_trend}`, `{streak_count}`, `{last_entry_date}`, `{recurring_themes}`
- The two-tier approach (system context vs per-message formatting) keeps prompts maintainable

### Gaps & Risks
- No offline-first architecture — online-only chat client
- No local database (no Drift/SQLite)
- No journaling features, mood tracking, or entry management
- Uses Hive for storage, not Drift
- AGPL-3.0 license — code cannot be directly copied, only patterns adopted

---

## 4. ZhuJHua/moodiary — Production Diary UX

### Project Profile

| Attribute | Value |
|-----------|-------|
| Stars | 1,736 |
| Language | Dart (Flutter) + Rust (via flutter_rust_bridge) |
| License | AGPL-3.0 |
| Default Branch | develop |
| Architecture | GetX pattern: `lib/common/`, `lib/components/`, `lib/pages/` |
| Maturity | Production (17 releases, 613 commits, docs site) |

### Architecture Overview

Moodiary is the most polished open-source Flutter diary. It uses Isar for local storage, GetX for state management, and TFLite for on-device sentiment analysis. The Rust bridge handles performance-critical NLP tasks.

**Key directories:**
- `lib/common/models/isar/` — Diary, Category, Font, SyncRecord models
- `lib/common/models/tflite.dart` — NLP data structures for on-device AI
- `lib/components/` — Reusable UI (audio player, ask_question, bubble, category_add)
- `lib/pages/` — Diary details, diary settings, edit, home, etc.
- `lib/common/values/` — Constants (diary_type, media_type, mood, colors, sync_status)

### Scored Patterns

#### Pattern 4.1: Rich Diary Data Model
**Score: 20/25** (Prevalence: 4, Elegance: 4, Evidence: 5, Fit: 4, Maintenance: 3)

```dart
@collection
class Diary {
  // Identity
  String id;          // UUID v7
  @Id() int isarId;   // hash-based DB key

  // Content
  String title;
  String content;      // Delta format (rich text)
  String contentText;  // Plain text for search

  // Metadata
  DateTime time;       // with computed indices: yM, yMd
  DateTime lastModified;
  bool show;           // soft-delete/trash
  String? categoryId;

  // Mood & Context
  double mood;         // 0.0-1.0 scale (default 0.5)
  List<String> weather;
  List<String> position; // location data

  // Media Attachments
  List<String> imageName, audioName, videoName;
  int? imageColor;     // cover color
  double? aspect;      // image aspect ratio

  // Semantic Data
  List<String> tags, keywords, tokenizer;
}
```

**Key insights:**
- Mood as a `double` (0.0-1.0) enables granular tracking and visualization, not just emoji categories
- Separate `content` (rich Delta) and `contentText` (plain) fields enable both rich editing and fast full-text search
- UUID v7 for business IDs, hash-based IDs for Isar — separates identity from storage
- Computed date indices (`yM`, `yMd`) optimize calendar view queries
- Media stored as filename lists, not embedded — keeps the diary table lightweight

**Adaptation for Agentic Journal:**
- Map this model to Drift tables, replacing Isar decorators with Drift column definitions
- Keep the dual content fields (rich + plain text) — essential for search performance
- Use mood as `REAL` column (0.0-1.0) in Drift, with Supabase `numeric` for sync
- Add `syncable` columns: `userId`, `createdAt`, `updatedAt`, `deletedAt` (from syncable pattern)
- Consider UUID v7 (time-ordered) for natural chronological sorting

#### Pattern 4.2: Privacy-First AI Architecture (Local + Cloud)
**Score: 20/25** (Prevalence: 3, Elegance: 5, Evidence: 4, Fit: 4, Maintenance: 4)

Moodiary implements a two-tier AI architecture:

**Tier 1 — On-Device (TFLite):**
- MobileBERT for sentiment analysis and reading comprehension
- SQuAD-format data pipeline: `SquadExample` → `InputFeatures` → `RawResult`
- Jieba keyword extraction via Rust bridge
- No network required — works fully offline

**Tier 2 — Cloud LLM (Optional):**
- Tencent Hunyuan for more powerful analysis
- Only activated with user consent
- Graceful degradation when unavailable

**Key insight:** On-device AI handles the privacy-sensitive operations (sentiment, keywords) that run on every entry, while cloud AI is reserved for optional, user-initiated features (deeper analysis, conversation). This respects user trust.

**Adaptation for Agentic Journal:**
- Phase 1: Cloud-only (Claude API) — simpler to implement
- Phase 2: Add on-device sentiment via `tflite_flutter` for offline mood analysis
- The graceful degradation pattern is critical — journal entries should always work, AI features enhance but don't gate
- Use on-device inference for: auto-mood detection, keyword extraction, basic categorization
- Reserve Claude for: reflective conversations, RAG-powered context, complex analysis

#### Pattern 4.3: Flutter + Native Code Bridge
**Score: 20/25** (Prevalence: 4, Elegance: 4, Evidence: 4, Fit: 4, Maintenance: 4)

Moodiary uses `flutter_rust_bridge` for performance-critical NLP:
- Jieba word segmentation (Chinese text tokenization)
- Image processing operations
- Computationally intensive tasks that would lag in Dart

**Adaptation for Agentic Journal:**
- Use Platform Channels to Kotlin (your stated stack) for similar needs
- Good candidates for native code: audio recording/processing, background sync scheduling, biometric auth
- The pattern of keeping UI in Flutter and computation in native code is well-established

### Gaps & Risks
- Uses Isar (not Drift) and GetX (not Riverpod) — different ORM and state management
- No Supabase — sync via LAN/WebDAV
- No RAG or agentic AI conversations
- AGPL-3.0 — patterns only, no code copying
- Chinese-first documentation and UI strings

---

## 5. Mr-Pepe/syncable — Drift + Supabase Offline-First Sync

### Project Profile

| Attribute | Value |
|-----------|-------|
| Stars | 38 |
| Language | Dart |
| License | MIT |
| Default Branch | main |
| Architecture | Library: `lib/src/` (6 files) |
| Maturity | Published on pub.dev, production use in Chill Chinese app |
| Dependencies | drift ^2.26.0, supabase ^2.6.3, Dart ^3.8.0 |

### Architecture Overview

Syncable is a focused library providing the exact Drift + Supabase bidirectional sync plumbing. It's the **highest tech-stack overlap** of any analyzed project. Every source file is relevant.

**Source files:**
- `lib/src/sync_manager.dart` — Core sync orchestration
- `lib/src/syncable_table.dart` — Table interface for sync-ready Drift tables
- `lib/src/syncable_database.dart` — Database mixin for sync capabilities
- `lib/src/syncable.dart` — Base data object contract
- `lib/src/sync_timestamp_storage.dart` — Incremental sync state
- `lib/src/supabase_names.dart` — Supabase column naming conventions

**Supabase migrations:**
- `010_enable_realtime.sql` — Real-time publication setup
- `020_create_trigger_to_reject_old_modifications.sql` — Conflict resolution
- `030_create_items_table.sql` — Reference table implementation

### Scored Patterns

#### Pattern 5.1: Bidirectional Drift↔Supabase Sync Manager
**Score: 23/25** (Prevalence: 3, Elegance: 5, Evidence: 4, Fit: 5, Maintenance: 5) — **HIGHEST SCORING PATTERN**

The `SyncManager<T extends SyncableDatabase>` implements a complete bidirectional sync:

**Outgoing (Local → Supabase):**
1. Local Drift DB changes detected via `subscribe()` streams
2. Changes queued in `_outQueues` (keyed by item ID)
3. Background loop processes queue via batch upserts
4. Conflict handled by composite key: `'$idKey,$userIdKey'`

**Incoming (Supabase → Local):**
1. Supabase real-time subscriptions push changes
2. Changes buffered in `_inQueues`
3. Deduplicated against `_sentItems`/`_receivedItems` sets
4. Batch-written to Drift with `updatedAt` comparison

**Sync loop:** `Process outgoing → Process incoming → Delay → Repeat` (configurable interval, default 1s)

**Adaptation for Agentic Journal:**
- **Directly adopt as a dependency** (MIT license, published on pub.dev)
- Or fork and extend for journal-specific needs (binary attachment handling, RAG vector sync)
- The 1-second sync interval is aggressive — consider 5-10s for battery efficiency on mobile
- Add error handling for Supabase rate limits and network failures

#### Pattern 5.2: SyncableTable + Syncable Interface Contract
**Score: 23/25** (Prevalence: 3, Elegance: 5, Evidence: 4, Fit: 5, Maintenance: 5)

**Table interface (4 required columns):**
```dart
abstract class SyncableTable {
  TextColumn get id;        // business key
  TextColumn get userId;    // ownership
  DateTimeColumn get updatedAt; // conflict resolution
  BoolColumn get deleted;   // soft-delete
}
```

**Data object interface:**
```dart
abstract class Syncable {
  String get id;
  String? get userId;
  DateTime get updatedAt;
  bool get deleted;

  Map<String, dynamic> toJson();        // → Supabase
  UpdateCompanion<Syncable> toCompanion(); // → Drift
}
```

**Key insight:** The dual serialization (`toJson()` for network, `toCompanion()` for Drift) is the essential bridge pattern. Every syncable entity knows how to express itself for both persistence layers.

**Adaptation for Agentic Journal:**
- Every Drift table must implement `SyncableTable`: journal_entries, chat_sessions, chat_messages, user_preferences, mood_records
- Every data class must implement `Syncable` with both serialization methods
- Add a `createdAt` column (syncable only requires `updatedAt`, but you want both)
- Consider adding `deviceId` for multi-device conflict debugging

#### Pattern 5.3: Last-Write-Wins via PostgreSQL Trigger
**Score: 22/25** (Prevalence: 4, Elegance: 5, Evidence: 4, Fit: 5, Maintenance: 4)

```sql
CREATE OR REPLACE FUNCTION discard_older_updates()
RETURNS trigger AS $$
BEGIN
    IF NEW.updated_at <= OLD.updated_at THEN
        RETURN NULL; -- Discard the stale write
    END IF;
    RETURN NEW; -- Allow the newer write
END;
$$ LANGUAGE plpgsql;
```

Applied as a `BEFORE UPDATE` trigger on every syncable table. Combined with Supabase RLS policies for user isolation.

**Adaptation for Agentic Journal:**
- Apply this trigger to all syncable tables in your Supabase schema
- For journal entries, last-write-wins is appropriate (single user, multiple devices)
- For collaborative features (future), consider CRDT or operational transform instead
- The trigger + RLS combination provides both conflict safety and access control

#### Pattern 5.4: Incremental Sync with Persistent Timestamps
**Score: 22/25** (Prevalence: 4, Elegance: 5, Evidence: 4, Fit: 5, Maintenance: 4)

```dart
abstract class SyncTimestampStorage {
  Future<void> setSyncTimestamp(String key, DateTime timestamp);
  DateTime? getSyncTimestamp(String key);
}
```

Per-table timestamps mean reconnection after offline periods only fetches changes since last sync, not full table scans. Recommended implementation: SharedPreferences.

**Adaptation for Agentic Journal:**
- Use SharedPreferences or Drift itself to store sync timestamps
- Consider per-table + per-direction timestamps (last pushed, last pulled)
- Critical for battery/bandwidth efficiency on mobile

#### Pattern 5.5: Anonymous-to-Authenticated User Migration
**Score: 21/25** (Prevalence: 3, Elegance: 5, Evidence: 4, Fit: 5, Maintenance: 4)

`fillMissingUserIdForLocalTables()` handles the case where a user starts journaling anonymously and later signs up. All local records with null `userId` get backfilled with the authenticated user's ID.

**Adaptation for Agentic Journal:**
- Essential for onboarding — let users journal immediately, sign up later
- Supabase anonymous auth → authenticated auth upgrade
- All Drift records created pre-auth get userId backfilled on first sign-in

#### Pattern 5.6: Conditional Real-Time Subscriptions
**Score: 20/25** (Prevalence: 3, Elegance: 4, Evidence: 4, Fit: 5, Maintenance: 4)

Real-time subscriptions activate only when:
- Syncing is enabled
- User is authenticated
- Other devices are considered active (within configurable timeout)

When no other devices are active, subscriptions are unsubscribed to reduce Supabase costs and battery drain.

**Adaptation for Agentic Journal:**
- Device presence tracking reduces Supabase real-time connection costs
- Consider disabling real-time during active journaling (batch sync on save instead)
- Re-enable when app is backgrounded or another device comes online

### Gaps & Risks
- No AI, no journaling, no UI — purely sync infrastructure
- Only 25 commits, 38 stars — limited community validation
- No large binary attachment handling (images, audio) — will need extension
- No vector/embedding sync (need to handle pgvector columns separately)
- Supabase real-time has connection limits — plan for scaling

---

## Cross-Project Synthesis

### Patterns Seen Across Multiple Projects (Rule of Three)

| Pattern | omi | lumma | kelivo | moodiary | syncable | Count |
|---------|-----|-------|--------|----------|----------|-------|
| Streaming LLM responses | ✅ | - | ✅ | - | - | 2 |
| Chat session management | ✅ | ✅ | ✅ | - | - | 3 ✅ |
| MCP integration | ✅ | ✅ | ✅ | - | - | 3 ✅ |
| Soft-delete pattern | ✅ | - | - | ✅ | ✅ | 3 ✅ |
| Rich metadata on entries | ✅ | ✅ | ✅ | ✅ | - | 4 ✅ |
| Tool calling loop | ✅ | - | ✅ | - | - | 2 |
| Multi-LLM provider support | - | ✅ | ✅ | ✅ | - | 3 ✅ |
| Timestamp-based sync | - | - | - | ✅ | ✅ | 2 |
| AI memory/context system | ✅ | ✅ | ✅ | - | - | 3 ✅ |

**Patterns meeting the Rule of Three** (seen in 3+ projects → priority consideration):
1. Chat session management
2. MCP integration
3. Soft-delete pattern
4. Rich entry metadata
5. Multi-LLM provider support
6. AI memory/context persistence

### Architecture Stack Recommendations

Based on cross-project analysis, here is the recommended architecture for each layer:

#### Data Layer (Drift + Supabase)
**Primary source: syncable**

```
┌─────────────────────────────────────────────┐
│            Flutter App (Drift)               │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ JournalEntry │  │ ChatSession          │  │
│  │ + SyncableT  │  │ + SyncableTable      │  │
│  ├─────────────┤  ├──────────────────────┤  │
│  │ id (UUIDv7) │  │ id (UUIDv7)          │  │
│  │ userId      │  │ userId               │  │
│  │ title       │  │ title, mode          │  │
│  │ content     │  │ assistantId          │  │
│  │ contentText │  │ mcpServerIds         │  │
│  │ mood (0-1)  │  │ summary              │  │
│  │ tags[]      │  │ status               │  │
│  │ weather[]   │  │ updatedAt, deletedAt │  │
│  │ location[]  │  └──────────────────────┘  │
│  │ media[]     │                             │
│  │ updatedAt   │  ┌──────────────────────┐  │
│  │ deletedAt   │  │ ChatMessage          │  │
│  └─────────────┘  │ + SyncableTable      │  │
│                    ├──────────────────────┤  │
│  ┌─────────────┐  │ id, sessionId        │  │
│  │ JournalInsight│ │ role, content        │  │
│  │ + SyncableT  │ │ chunkType (think/    │  │
│  ├─────────────┤  │   data/done)         │  │
│  │ id          │  │ toolCalls[]          │  │
│  │ entryId     │  │ updatedAt, deletedAt │  │
│  │ content     │  └──────────────────────┘  │
│  │ category    │                             │
│  │ reviewed    │                             │
│  └─────────────┘                             │
│         ▼ SyncManager ▼                      │
├─────────────────────────────────────────────┤
│          Supabase (PostgreSQL)               │
│  + RLS policies per table                    │
│  + discard_older_updates() trigger           │
│  + Real-time publications                    │
│  + pgvector for RAG (future)                 │
└─────────────────────────────────────────────┘
```

#### AI Layer (Claude API + MCP)
**Primary sources: kelivo (abstraction), omi (memory), lumma (journal UX)**

```
┌──────────────────────────────────────────────┐
│              AI Service Layer                 │
│  ┌──────────────────────────────────────┐    │
│  │ ChatApiService (from kelivo pattern)  │    │
│  │  - Provider routing (Claude primary)  │    │
│  │  - Streaming with typed chunks        │    │
│  │  - Tool calling loop                  │    │
│  └──────────────┬───────────────────────┘    │
│                 │                              │
│  ┌──────────────▼───────────────────────┐    │
│  │ PromptTransformer                     │    │
│  │  - System placeholders {date, mood}   │    │
│  │  - Message templates {{ message }}    │    │
│  │  - Journal-specific context injection │    │
│  └──────────────┬───────────────────────┘    │
│                 │                              │
│  ┌──────────────▼───────────────────────┐    │
│  │ McpToolService (from kelivo pattern)  │    │
│  │  - search_entries(query, date_range)  │    │
│  │  - get_mood_trend(period)             │    │
│  │  - find_similar_entries(entry_id)     │    │
│  │  - extract_action_items(entry_id)     │    │
│  └──────────────────────────────────────┘    │
│                                               │
│  ┌──────────────────────────────────────┐    │
│  │ MemoryService (from omi pattern)      │    │
│  │  - Extract insights from entries      │    │
│  │  - Build user knowledge graph         │    │
│  │  - Context for future conversations   │    │
│  └──────────────────────────────────────┘    │
│                                               │
│  ┌──────────────────────────────────────┐    │
│  │ AssistantService (from kelivo pattern)│    │
│  │  - Reflective Coach persona           │    │
│  │  - Goal Tracker persona               │    │
│  │  - Gratitude Guide persona            │    │
│  │  - Per-persona: prompt, temp, tools   │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

#### Journal UX Layer
**Primary sources: lumma (modes), moodiary (diary UX), kelivo (chat UI)**

```
┌──────────────────────────────────────────────┐
│           Journal Experience                  │
│                                               │
│  ┌─────────────────────────────────────┐     │
│  │ Journal Modes (from lumma)           │     │
│  │  - Freeform: blank page writing      │     │
│  │  - Guided: Q&A reflection prompts    │     │
│  │  - Chat: conversational journaling   │     │
│  └─────────────────────────────────────┘     │
│                                               │
│  ┌─────────────────────────────────────┐     │
│  │ Entry Management (from moodiary)     │     │
│  │  - Rich text + plain text dual store │     │
│  │  - Mood slider (0.0-1.0)            │     │
│  │  - Weather + location auto-capture   │     │
│  │  - Photo/audio/video attachments     │     │
│  │  - Tags + AI-extracted keywords      │     │
│  │  - Calendar view with date indices   │     │
│  │  - Full-text search                  │     │
│  └─────────────────────────────────────┘     │
│                                               │
│  ┌─────────────────────────────────────┐     │
│  │ Chat UI (from kelivo + omi)          │     │
│  │  - Streaming markdown rendering      │     │
│  │  - Think/data/done chunk display     │     │
│  │  - Tool call visualization           │     │
│  │  - Session list + management         │     │
│  │  - Message version selection         │     │
│  └─────────────────────────────────────┘     │
└──────────────────────────────────────────────┘
```

---

## Prioritized Implementation Roadmap

### Phase 1: Foundation (Offline-First Data + Basic AI)

| Step | Pattern | Source | Priority |
|------|---------|--------|----------|
| 1.1 | Set up Drift tables with SyncableTable interface | syncable | P0 |
| 1.2 | Implement SyncManager for Drift↔Supabase | syncable | P0 |
| 1.3 | Apply PostgreSQL triggers + RLS | syncable | P0 |
| 1.4 | Build JournalEntry model (mood, media, tags) | moodiary | P0 |
| 1.5 | Implement ChatApiService with Claude streaming | kelivo | P0 |
| 1.6 | Basic chat UI with streaming markdown | kelivo, omi | P0 |

### Phase 2: Journal Intelligence

| Step | Pattern | Source | Priority |
|------|---------|--------|----------|
| 2.1 | Dual-mode journal (Freeform + Guided + Chat) | lumma | P1 |
| 2.2 | Custom assistant personas for journal contexts | kelivo | P1 |
| 2.3 | Prompt transformer with journal placeholders | kelivo | P1 |
| 2.4 | Memory extraction from conversations | omi | P1 |
| 2.5 | MCP tools for journal search/analysis | kelivo, lumma | P1 |
| 2.6 | Anonymous-to-authenticated migration | syncable | P1 |

### Phase 3: Advanced Features

| Step | Pattern | Source | Priority |
|------|---------|--------|----------|
| 3.1 | On-device sentiment analysis (TFLite) | moodiary | P2 |
| 3.2 | RAG over journal entries (pgvector) | omi | P2 |
| 3.3 | Voice input/transcription | omi | P2 |
| 3.4 | Rich text editor with Delta format | moodiary | P2 |
| 3.5 | Multimedia attachment handling + sync | moodiary | P2 |
| 3.6 | Device presence optimization | syncable | P2 |

---

## Critical Gap: Riverpod State Management

**No analyzed project uses Riverpod with Drift + Supabase.** This is the one pattern gap that must be designed from scratch:

- **kelivo** uses custom providers (closest to Riverpod pattern but not Riverpod)
- **moodiary** uses GetX
- **lumma** uses GetX
- **omi** uses custom state management
- **syncable** is state-management agnostic

**Recommendation:** Study the following supplementary references (not in the top 5 but relevant):
- `powersync-ja/powersync.dart/demos/supabase-todolist-drift` — Riverpod + Drift + Supabase in a small app
- `rodydavis/clean_architecture_todo_app` — Riverpod + Drift with clean architecture

The Riverpod integration should wrap the SyncManager as a provider, expose table streams as `StreamProvider`s, and manage auth state via `StateNotifierProvider`.

---

## License Compatibility Summary

| Project | License | Can Copy Code? | Can Adopt Patterns? |
|---------|---------|---------------|-------------------|
| syncable | MIT | Yes | Yes |
| omi | MIT | Yes | Yes |
| lumma | Not specified | Caution — patterns only | Yes |
| kelivo | AGPL-3.0 | No (viral) | Yes (patterns only) |
| moodiary | AGPL-3.0 | No (viral) | Yes (patterns only) |

**Actionable:** Only syncable and omi code can be directly used. Kelivo and moodiary patterns must be reimplemented from scratch.

---

## Appendix: File Reference Index

### syncable (Highest Priority — Read All Files)
- `lib/src/sync_manager.dart` — Core bidirectional sync orchestration
- `lib/src/syncable_table.dart` — Required table columns interface
- `lib/src/syncable_database.dart` — Database mixin for sync
- `lib/src/syncable.dart` — Data object contract (toJson + toCompanion)
- `lib/src/sync_timestamp_storage.dart` — Incremental sync timestamps
- `supabase/migrations/020_create_trigger_to_reject_old_modifications.sql` — Conflict resolution trigger

### kelivo (AI Integration Reference)
- `lib/core/services/api/chat_api_service.dart` — Multi-provider LLM abstraction
- `lib/core/services/mcp/mcp_tool_service.dart` — MCP tool integration
- `lib/core/services/chat/chat_service.dart` — Chat service architecture
- `lib/core/services/chat/prompt_transformer.dart` — Prompt assembly pipeline
- `lib/core/models/assistant.dart` — Custom AI persona configuration
- `lib/core/models/conversation.dart` — Chat session model

### omi (Memory + Streaming Reference)
- `app/lib/backend/schema/memory.dart` — Persistent memory model
- `app/lib/backend/schema/conversation.dart` — Conversation with rich metadata
- `app/lib/backend/schema/message.dart` — Message schema with streaming chunks
- `app/lib/backend/http/api/messages.dart` — Streaming message API

### lumma (Journal UX Reference)
- `lib/dao/diary_dao.dart` — Diary entry CRUD + Q&A structure
- `lib/service/diary_content_service.dart` — Content parsing + frontmatter
- `lib/service/mcp_service.dart` — MCP journal persistence tool
- `lib/view/pages/diary_edit_page.dart` — Journal editing UX

### moodiary (Diary Model Reference)
- `lib/common/models/isar/diary.dart` — Rich diary model (mood, media, tags)
- `lib/common/models/tflite.dart` — On-device NLP data structures
- `lib/common/values/diary_type.dart` — Entry type constants
- `lib/utils/theme_util.dart` — Material You dynamic color with CorePalette → AccentColor fallback
- `lib/persistence/pref.dart` — SharedPreferencesWithCache with allowList pattern
- `lib/components/keyboard_listener/keyboard_listener.dart` — Keyboard state machine
- `lib/persistence/isar.dart` — Migration chunking, search, database access layer
- `lib/utils/lru.dart` — Thread-safe AsyncLRUCache with Lock mutex

---

## Appendix B: Agent-Sourced Deep Patterns

The following patterns were identified by specialist project-analyst agents performing deep code forensics. They supplement the patterns in the main sections above.

### From omi Agent: Backend AI Architecture Patterns

These patterns are from omi's Python/FastAPI backend. While our Agentic Journal doesn't have a Python backend, the architectural concepts translate to Dart/Supabase Edge Functions.

#### B.1: LLM-Adjudicated Memory Deduplication
**Score: 22/25** | **Source:** `backend/utils/llm/memories.py` `resolve_memory_conflict()`

When a new extracted memory has vector cosine similarity >= 0.85 to an existing memory, instead of silently discarding or overwriting, the system calls an LLM to adjudicate with four possible outcomes:

- **keep_new** — genuinely new information
- **keep_existing** — new is redundant
- **merge** — combine into better version (max 10 words)
- **keep_both** — distinct complementary facts

**Why this matters:** Pure vector similarity deduplication produces false positives ("Has a dog" vs "Has a dog named Max" score high but the second is strictly better). The four-action vocabulary handles the update case that binary keep/discard misses.

**Adoption path:** Use pgvector similarity search + Claude API adjudication. Query: `SELECT * FROM extracted_facts ORDER BY embedding <=> $1 LIMIT 5 WHERE similarity > 0.85`. If matches found, call Claude with both to adjudicate.

#### B.2: Dual-Namespace Vector Separation
**Score: 23/25** | **Source:** `backend/database/vector_db.py`

Conversations stored in namespace `ns1`, extracted facts/memories in namespace `ns2`. Each has separate upsert, search, and delete functions. Prevents retrieval pollution — searching "what's my favorite food?" hits the facts store, not full conversations.

**Adoption path:** Two separate pgvector tables in Supabase:
- `journal_entry_embeddings` — full entry text for RAG retrieval
- `extracted_fact_embeddings` — short authoritative facts for context injection

#### B.3: Agent Safety Guard (Tool Call Loop Detection)
**Score: 21/25** | **Source:** `backend/utils/retrieval/safety.py`

Stateful guard injected per-request into the agentic conversation:
1. **Absolute tool call limit** (default 25)
2. **Loop detection** — same tool+params in >= 2 of last 3 calls
3. **Context token budget** (500K ceiling)

At 80% of limits: user-visible warning. At 100%: graceful stop with user-friendly message ("I seem to be stuck... Could you rephrase?").

**Adoption path:** Implement Dart `AgentSafetyGuard` class wrapping Claude API tool-use calls. Instantiate per conversation turn. Critical for preventing runaway API costs.

#### B.4: PageContext — Current-Screen Awareness
**Score: 22/25** | **Source:** `backend/models/chat.py` `PageContext`

When the user views a specific journal entry and taps the chat input, the app sends context: `{type: "journal_entry", id: "...", title: "..."}`. The AI pre-loads the entry into the system prompt, making it contextually aware without the user needing to say "I'm looking at my entry from Tuesday."

**Adoption path:** Add `pageContext` field to chat message requests. When composing the Claude API system prompt, inject the relevant entry content. Simple to implement, high UX impact.

#### B.5: Conversation Post-Processing Pipeline
**Source:** `backend/utils/llm/conversation_processing.py`

After a conversation closes, a pipeline runs:
1. `should_discard_conversation()` — LLM decides if content is worth saving (100-word early exit optimization)
2. `extract_action_items()` — pull out TODOs
3. `assign_conversation_to_folder()` — auto-categorize

**Adoption path:** Run a similar pipeline after each journal chat session closes. Use Claude tool-calling to extract: mood assessment, key themes, action items, and memory-worthy facts.

#### B.6: Anti-Patterns Observed in omi
- Firebase/Firestore for relational data (joins done in Python, not DB) — validates our Drift+Supabase choice
- `print()` as logging (no structured observability) — use Dart `logging` package from day one
- Hardcoded `limit = 5000` when `offset == 0` — acknowledged tech debt
- No structured error hierarchy — validates our `AppError` hierarchy pattern

### From moodiary Agent: Flutter UX & Infrastructure Patterns

#### B.7: UUID v7 as Offline-First Business Key
**Applicability: High** | **Source:** `lib/common/models/isar/diary.dart` lines 8-13

```dart
String id = const Uuid().v7();
```

UUID v7 is time-sortable (chronological ordering by key), globally unique without a server (offline-safe), and maps to Supabase's `uuid` column type. The FNV hash derivative for Isar's int key is an anti-pattern to avoid — Drift's `TextColumn` can be the primary key directly.

**Adoption:** Add `uuid` package to `pubspec.yaml`. Use `Uuid().v7()` as the Drift `TextColumn` primary key for all entities.

#### B.8: Material You Dynamic Color with Two-Stage Fallback
**Applicability: High** | **Source:** `lib/utils/theme_util.dart`

```dart
// Stage 1: CorePalette (Android 12+)
final CorePalette? corePalette = await DynamicColorPlugin.getCorePalette();
// Stage 2: AccentColor (Android 8+)
final Color? accentColor = await DynamicColorPlugin.getAccentColor();
// Stage 3: Static seed color (all devices)
```

Combined with `ColorScheme.fromSeed()`, `DynamicSchemeVariant.tonalSpot`, and `.harmonized()` for accessible contrast. Variable font weight via `FontVariation('wght', weight)` per text style slot.

**Adoption:** Add `dynamic_color` and `material_color_utilities` to `pubspec.yaml`. Copy the two-stage fallback structure.

#### B.9: SharedPreferencesWithCache with allowList
**Applicability: High** | **Source:** `lib/persistence/pref.dart`

```dart
_prefs = await SharedPreferencesWithCache.create(
  cacheOptions: const SharedPreferencesWithCacheOptions(
    allowList: allowList,  // const Set<String> of all valid keys
  ),
);
```

Loads all listed keys into memory at startup (synchronous reads thereafter). The `allowList` prevents unbounded cache growth and serves as compile-time documentation of all preference keys.

**Adoption:** Use instead of plain `SharedPreferences`. Define `allowList` as a const set before writing any settings code.

#### B.10: KeyboardObserver State Machine
**Applicability: High** | **Source:** `lib/components/keyboard_listener/keyboard_listener.dart`

```dart
void didChangeMetrics() {
  WidgetsBinding.instance.addPostFrameCallback((_) {
    final height = PlatformDispatcher.instance.views.first.viewInsets.bottom;
    // State machine: opening → closing → closed
    // Transition guards prevent duplicate callbacks
  });
}
```

The `addPostFrameCallback` ensures measurement happens after layout (avoiding the classic timing issue). State machine with transition guards prevents duplicate callbacks during keyboard animation. Used across chat, search, and editor pages.

**Adoption:** Copy the class directly. Wire `onStateChanged` callback into Riverpod state notifiers. More reliable than `MediaQuery.viewInsets.bottom` polling inside `build()`.

#### B.11: Pre-Tokenize at Write Time for Search
**Applicability: Medium** | **Source:** `lib/persistence/isar.dart`, `lib/components/search_sheet/`

Architecture: tokenize content at save time → store tokens as indexed array → multi-token OR union search at query time. Moodiary uses Rust jieba for Chinese segmentation.

**Adoption path:** Use Drift's FTS5 virtual table support with `porter` or `unicode61` tokenizer (for English). The structural principle — write-time computation, index-backed search — is the adoptable pattern regardless of the specific tokenizer.

#### B.12: Batched Migration Chunking (50 Rows)
**Applicability: High** | **Source:** `lib/persistence/isar.dart` `mergeToV2_7_4`

```dart
for (var i = 0; i < countDiary; i += 50) {
  final diaries = await _isar.diarys.where().findAllAsync(offset: i, limit: 50);
  // Process batch, write back
}
```

Prevents OOM on large diary collections during schema migration. Named versioned static methods (`mergeToV2_6_0`, `mergeToV2_7_4`) provide clear migration lineage.

**Adoption:** Apply chunked batch processing in all Drift `onUpgrade` callbacks that transform existing row data. The version-named-method discipline transfers directly.

#### B.13: Anti-Patterns Observed in moodiary
- Supabase integration is a facade (empty URL/anonKey, unimplemented sync methods) — no sync reference value
- Zero test files — all patterns sourced here must be validated in our test suite
- GetX implicit coupling (`Bind.find<>()`) creates hidden dependencies — validates our Riverpod choice
- TFLite MobileBERT code is commented out — the on-device AI feature shipped incomplete
- FNV hash collision risk for DB primary keys — do not replicate; use Drift TextColumn directly
