# Five GitHub repos an Agentic Journal project-analyst should study

**No single open-source repository combines Flutter + offline-first sync + agentic AI + RAG over personal journal data — but five repos together cover every hard pattern.** The most valuable reference is BasedHardware/omi, a production Flutter app with RAG, vector search, and agentic AI over personal conversations. The others fill critical gaps: lumma demonstrates the AI-native journal UX, kelivo shows Claude API integration with MCP, moodiary proves a polished Flutter diary can ship at scale, and syncable provides the exact Drift-to-Supabase sync plumbing. Studied together, these repos give a project-analyst agent scoreable patterns across all 10 architectural dimensions of the Agentic Journal project.

---

## 1. BasedHardware/omi — Flutter + RAG + agentic AI over personal data

**Repository:** [BasedHardware/omi](https://github.com/BasedHardware/omi)
**Stars:** ~7,700 | **Last updated:** December 13, 2025 | **Commits:** 11,099 | **License:** MIT

**Tech stack overlap with Agentic Journal:**
Flutter/Dart (mobile app), speech-to-text (Deepgram/Speechmatic), vector embeddings for RAG (Pinecone), LLM API integration (OpenAI-compatible), background processing, connectivity management. Uses Firebase rather than Supabase, and Pinecone rather than pgvector — but the patterns transfer directly.

**Key architectural patterns demonstrated:**
- **RAG over personal data** — the backend indexes all user conversations and transcriptions into vector embeddings, with dedicated `backend/scripts/rag/` modules for retrieval. This is the closest open-source reference to "RAG over journal entries" in a Flutter app.
- **Agentic AI conversations** — the AI agent performs multi-step task execution with no turn limit, maintaining context across sessions through a persistent memory system that creates structured memories from unstructured conversations.
- **Chat-based UI with session management** — the Flutter app manages conversation sessions with a 1:many session-to-messages architecture, plus automatic summarization.
- **Speech-to-text pipeline** — production-quality voice input with multiple STT provider options (Deepgram, Speechmatic, Soniox), directly relevant to Phase 2+ voice journaling.
- **MCP server support** — includes Model Context Protocol integration for agentic tool use.

**What the project-analyst agent could learn:**
Omi is the **best single reference for the hardest patterns** — RAG retrieval over personal data, agentic multi-step AI conversations, and Flutter-to-backend vector search integration. The monorepo structure (`app/`, `backend/`, `plugins/`, `mcp/`) demonstrates clean separation between the Flutter client and Python/FastAPI backend, which maps to the Agentic Journal's Flutter-frontend + backend-proxy-to-Claude architecture. The memory extraction system (automatically distilling facts and preferences from conversations) is directly applicable to building "context-aware follow-ups" in a journal.

**Notable gaps:** Uses Firebase + Pinecone instead of **Supabase + pgvector**. No Riverpod or drift — the Flutter app uses its own state management. Not a journaling app per se (it's a wearable companion), so the UX patterns around daily journal entries, mood tracking, and reflective writing don't apply. The codebase is large (11k commits) and commercial, which may make pattern extraction more complex.

---

## 2. geosmart/lumma — the closest conceptual match to an AI journal

**Repository:** [geosmart/lumma](https://github.com/geosmart/lumma)
**Stars:** 159 | **Last updated:** December 14, 2025 (v1.0.5) | **Commits:** 113 | **License:** Not specified

**Tech stack overlap with Agentic Journal:**
Flutter 3.32+/Dart (cross-platform including Android, iOS, desktop, web), multi-LLM provider support (configurable — analogous to Claude API integration), local Markdown storage (offline-first local data), WebDAV cloud sync, voice input support.

**Key architectural patterns demonstrated:**
- **AI-native journaling with two interaction modes** — Q&A Mode uses guided prompts for structured reflection (timeline narrative that works even without AI), while Chat Mode enables freeform conversational AI journaling. This dual-mode pattern maps perfectly to the Agentic Journal's "agentic AI conversations" requirement.
- **Context-aware AI features** — auto-generates journal titles, extracts tags, and produces summaries from entries, demonstrating LLM integration that goes beyond one-shot prompts.
- **Multi-LLM provider abstraction** — configurable LLM backends with custom prompt support, showing how to build a provider-agnostic AI layer that could wrap Claude, GPT, or Gemini.
- **Obsidian sync integration** — uses Advanced URI plugin for bidirectional sync with Obsidian, demonstrating interoperability patterns for personal knowledge management.

**What the project-analyst agent could learn:**
Lumma is the **most directly analogous app** — it is literally a Flutter AI journal. The Q&A/Chat dual-mode UX design is the strongest reference for how agentic journaling conversations should flow. The auto-summarization and tag extraction patterns show how to integrate LLMs into the journaling workflow without disrupting the writing experience. The CLAUDE.md file in the repo suggests the developer used AI-assisted development practices, which may yield insights into prompt engineering for journal-context AI.

**Notable gaps:** No Riverpod, drift, or Supabase — uses local Markdown files and WebDAV for sync rather than SQLite + PostgreSQL. **No RAG implementation** — AI features are prompt-based rather than retrieval-augmented. No offline-first database sync (Markdown files sync via WebDAV, not a conflict-resolving database sync). Small project with only 2 contributors, so architectural sophistication may be limited compared to larger codebases. No pgvector or vector embeddings.

---

## 3. Chevey339/kelivo — Flutter's best Claude API and agentic LLM reference

**Repository:** [Chevey339/kelivo](https://github.com/Chevey339/kelivo)
**Stars:** 969 | **Last updated:** December 13, 2025 (v1.1.5) | **Commits:** 1,000 | **License:** AGPL-3.0

**Tech stack overlap with Agentic Journal:**
Flutter 3.x/Dart (cross-platform including Android, iOS, Windows, macOS, Linux), **Anthropic Claude API** (direct integration), multi-LLM support (OpenAI, Gemini, DeepSeek), Material You design system, chat session management.

**Key architectural patterns demonstrated:**
- **Multi-provider LLM abstraction with Claude support** — kelivo directly integrates Anthropic's Claude alongside OpenAI, Gemini, and DeepSeek. The v1.1.5 release specifically added tool calls for Claude reasoning models, making this the **best Flutter reference for Claude API patterns**.
- **MCP (Model Context Protocol) integration** — supports Anthropic's MCP standard for agentic tool use, including a built-in MCP Fetch tool and web search across **12+ search engines** (Exa, Tavily, Brave, Bing, SearXNG, and more). This is the strongest reference for agentic capabilities in a Flutter chat app.
- **Chat UI with session management** — manages multiple conversation sessions with backup/restore, custom AI assistant personas, streaming responses with Markdown rendering (code highlighting, LaTeX, tables), and multimodal input (images, PDFs, Word docs).
- **Production deployment patterns** — published on the iOS App Store, with automated builds, TestFlight beta, and HarmonyOS adaptation in a separate repo.

**What the project-analyst agent could learn:**
Kelivo demonstrates how to **wire Claude API into a Flutter app** with streaming responses, tool calling, and multi-turn context. The MCP integration is particularly valuable — it shows how a Flutter client can enable agentic AI behaviors (web search, tool use, function calling) through a standardized protocol, which directly maps to the Agentic Journal's "agentic AI conversations" requirement. The custom assistant feature (creating personalized AI personas with specific system prompts) provides patterns for building a journal-specific AI personality. The web search integration patterns could inform how the Agentic Journal retrieves external context alongside personal journal data.

**Notable gaps:** **No offline-first architecture** — kelivo is an online-first chat client. No local database (drift/SQLite) or cloud sync (Supabase). No journaling features, mood tracking, or personal data RAG. No Riverpod — uses its own state management. The codebase is chat-focused rather than journal-focused, so entry creation/editing patterns aren't present.

---

## 4. ZhuJHua/moodiary — a mature Flutter diary app that ships

**Repository:** [ZhuJHua/moodiary](https://github.com/ZhuJHua/moodiary)
**Stars:** ~1,700 | **Last updated:** Active on develop branch (release v2.7.3, ~March 2025) | **Commits:** 613 | **License:** AGPL-3.0

**Tech stack overlap with Agentic Journal:**
Flutter 3.29+/Dart (cross-platform: Android, iOS, Windows, macOS, Linux), local AI via TensorFlow Lite, third-party LLM integration (Tencent Hunyuan), rich text editing, multimedia attachments (photos, audio, video, drawing), biometric security, LAN sync + WebDAV backup. Uses Rust (via flutter_rust_bridge) for performance-critical tasks.

**Key architectural patterns demonstrated:**
- **Privacy-first AI architecture** — on-device NLP via MobileBERT/TFLite for sentiment analysis and reading comprehension, avoiding cloud transmission of sensitive diary data. Optional cloud LLM integration for more powerful features. This dual-layer AI approach (local for privacy, cloud for capability) is an elegant pattern for a journal app.
- **Production Flutter diary UX** — **100+ GitHub issues resolved**, multiple editor modes (Markdown, rich text, plain text), mood/weather/location tracking, full-text search, categorization, custom themes and fonts, dark/light modes. This is the most polished open-source Flutter diary UI available.
- **Flutter + Rust bridge** — uses flutter_rust_bridge for computationally intensive tasks like Jieba keyword extraction and image processing, demonstrating how to extend Flutter with native code (analogous to the Agentic Journal's Platform Channels to Kotlin).
- **Cross-platform parity** — ships on Android, iOS, Windows, and macOS with platform-specific adaptations and build configurations.

**What the project-analyst agent could learn:**
Moodiary is the **best reference for how a polished diary app should work in Flutter** — the editor experience, entry management, search, multimedia handling, and privacy features are all production-grade. The local AI + optional cloud AI pattern directly informs how the Agentic Journal might handle the spectrum from offline TFLite sentiment analysis to online Claude conversations. The Rust bridge pattern shows an alternative to Platform Channels for native code integration. The project's maturity (17 releases, dedicated docs site, active community) provides patterns for long-term app maintenance.

**Notable gaps:** Uses **Isar** (not drift) for local storage and **GetX** (not Riverpod) for state management — different ORM and state management choices from the Agentic Journal's stack. No Supabase integration — sync is via LAN or WebDAV rather than PostgreSQL cloud sync. **No RAG or agentic AI conversations** — the LLM integration is relatively simple (assistant-style, not context-aware multi-turn with retrieval). No pgvector or embeddings.

---

## 5. Mr-Pepe/syncable — the exact Drift + Supabase offline-first sync pattern

**Repository:** [Mr-Pepe/syncable](https://github.com/Mr-Pepe/syncable)
**Stars:** 34 | **Last updated:** July 27, 2025 (v1.0.3) | **Commits:** 25 | **License:** MIT | **Published on:** pub.dev

**Tech stack overlap with Agentic Journal:**
**Drift** (SQLite ORM — exact match), **Supabase** (PostgreSQL backend + real-time subscriptions — exact match), Supabase RLS (Row Level Security), Dart/Flutter, SharedPreferences for sync state persistence. This is the **highest tech-stack overlap** of any repo found, hitting the two hardest infrastructure choices (Drift + Supabase) simultaneously.

**Key architectural patterns demonstrated:**
- **Bidirectional offline-first sync** — the `SyncManager` class listens to local Drift DB changes and queues writes to Supabase, while simultaneously listening to Supabase real-time subscriptions and queuing writes to the local DB. A background loop processes both queues at configurable intervals. This is the **exact pattern** the Agentic Journal needs for offline-first journal sync.
- **Conflict resolution** — implements last-write-wins based on `updatedAt` timestamps, with a PostgreSQL trigger function (`discard_older_updates()`) that rejects stale writes at the database level. Soft-deletion propagates deletes across devices.
- **Incremental sync with persistent timestamps** — stores the last sync timestamp in SharedPreferences so reconnection after offline periods only fetches changes, not full table scans.
- **Anonymous-to-authenticated user migration** — `fillMissingUserIdForLocalTables` handles the case where a user starts journaling anonymously and later signs up, a pattern directly relevant to journal app onboarding.
- **Device presence optimization** — tracks which devices are connected to minimize unnecessary Supabase real-time connections, reducing costs.

**What the project-analyst agent could learn:**
Syncable provides the **most directly adoptable code** of any repo in this list. The `SyncableTable` and `SyncableDatabase` interfaces define exactly what a Drift table needs to be syncable (userId, createdAt, updatedAt, deletedAt columns). The PostgreSQL trigger for conflict rejection, the RLS policy templates, and the real-time publication setup provide the complete Supabase backend configuration. The library is battle-tested in the production Chill Chinese app (iOS/Android/web). For the Agentic Journal, the project-analyst agent could study this repo's sync architecture and adapt it for journal entries, message sessions, and user preferences — likely the **single highest-ROI pattern extraction** across all five repos.

**Notable gaps:** **No AI, no journaling, no RAG** — this is purely a sync library. No UI components. No Riverpod (state management is left to the consuming app). Only 25 commits and 34 stars, reflecting its focused scope as a library rather than a full application. Does not demonstrate how to handle large binary attachments (images, audio) in sync, which journal apps need.

---

## How these five repos cover the Agentic Journal's pattern needs

The table below maps each of the 10 architectural patterns to which repos demonstrate them. Studying all five gives **complete coverage** of the hardest patterns.

| Architectural pattern | omi | lumma | kelivo | moodiary | syncable |
|---|---|---|---|---|---|
| 1. Offline-first sync to cloud | — | — | — | — | **✅✅** |
| 2. Agentic AI conversations | **✅✅** | ✅ | **✅✅** | — | — |
| 3. Local SQLite + cloud PostgreSQL sync | — | — | — | — | **✅✅** |
| 4. RAG over personal data | **✅✅** | — | — | — | — |
| 5. Flutter + LLM API integration | ✅ | ✅ | **✅✅** | ✅ | — |
| 6. Chat UI with session management | **✅✅** | ✅ | **✅✅** | — | — |
| 7. Riverpod state management | — | — | — | — | — |
| 8. drift ORM usage | — | — | — | — | **✅✅** |
| 9. Supabase integration (auth, RLS, real-time) | — | — | — | — | **✅✅** |
| 10. Android Platform Channels (native) | — | — | — | ✅* | — |

*Moodiary uses flutter_rust_bridge (analogous native code integration pattern)

**The one gap no repo fills is Riverpod state management combined with the other patterns.** The closest reference is the PowerSync demo (`powersync-ja/powersync.dart/demos/supabase-todolist-drift`), which combines Riverpod + Drift + Supabase in a small todo app — worth examining as a supplementary reference but too simple to rank in the top 5. For production Riverpod patterns, `rodydavis/clean_architecture_todo_app` (163★) demonstrates Riverpod + Drift with clean architecture but no cloud sync.

## Honorable mentions worth a secondary pass

Three repos fell just outside the top 5 but offer valuable supplementary patterns. **khoj-ai/khoj** (~30,700★) is the most sophisticated open-source personal AI with RAG, agentic agents, and even a WhatsApp journal feature — but it's Python/Django, not Flutter. **supabase-community/chatgpt-your-files** is the official Supabase reference for pgvector RAG with RLS, providing the exact SQL schemas and Edge Functions needed for the Agentic Journal's future RAG pipeline. And **mylxsw/aidea** (~6,500★) is the highest-starred Flutter AI app, demonstrating session management with SQLite and multi-LLM support at production scale, though it uses BLoC rather than Riverpod.

The open-source landscape reveals a clear market gap: **no existing Flutter app combines offline-first database sync, agentic AI, and RAG over personal journal data**. The Agentic Journal project would be the first to do so, which makes pattern extraction from these five complementary repos — rather than forking any single one — the right strategy.