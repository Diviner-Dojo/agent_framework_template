# Project Plan: Phases 6-11 — Voice-First AI Journal Companion

> **Revision 2** — incorporates findings from DISC-20260222-233425-phases-6-11-plan-review (5 specialists, 50 findings). Original plan preserved in git history.

## Context

The Agentic Journal app completed Phase 5 (search + memory recall) with 435 tests and 81.6% coverage. It's currently a **text-only** offline-first journaling app with Claude API integration, Supabase cloud sync, and Android assistant gesture support.

The developer's vision is to transform this into a **voice-first AI-powered personal companion**. Voice mode is the primary interaction mode — used while walking, commuting, driving, or any hands-free context. The next phases add: session management UX fixes, continuous voice mode, on-device LLM with a therapy-informed personality, photo capture, location awareness, and Google Calendar integration.

### Key Decisions Made
- **Target device**: Developer's own flagship phone (6GB+ RAM) — no need to support budget devices initially
- **Local LLM**: Qwen 2.5 3B (Q4_K_M, ~2GB) via `llamadart` — explicit Qwen support, Vulkan GPU, perfect pub.dev score, updated Feb 22 2026. **Also evaluate Qwen 2.5 1.5B** during spike for lower-latency alternative.
- **STT**: `sherpa_onnx` (Whisper-based) — the **only** Flutter STT package supporting continuous recognition without time limits. `speech_to_text` has a 60s iOS limit and 5s Android pause timeout. **Constrain to Whisper base.en or small.en** (~150-500MB) to coexist with LLM in RAM.
- **TTS**: `flutter_tts` — industry standard (1,560 likes, 147k downloads/week)
- **Assistant scope**: Google Calendar + reminders only (defer email, tasks to future)
- **Personality**: Research spike on therapeutic conversation techniques to inform "Guy" personality
- **Sentence boundary detection**: Use sherpa_onnx's native VAD (Voice Activity Detection) rather than a fixed silence timer — more accurate for variable speech patterns and noisy environments

### Package Research Summary

| Need | Package | Why This One |
|------|---------|-------------|
| LLM inference | `llamadart` ^0.6.2 | Perfect pub.dev score (160/130), explicit Qwen 2.5 doc, Vulkan GPU, verified publisher, updated Feb 22 2026. **Note**: pre-1.0 — pin exact version, expect API churn. |
| Speech-to-text | `sherpa_onnx` ^1.12.25 | Only Flutter STT with continuous recognition (no time limits), Whisper support, built-in VAD, fully offline, perfect pub.dev score |
| Text-to-speech | `flutter_tts` ^4.2.5 | Industry standard (1,560 likes, 147k/week downloads), verified publisher, battle-tested |
| Camera | `image_picker` ^1.1.2 | Standard Flutter camera/gallery package |
| Location | `geolocator` ^13.0.2 | Standard Flutter GPS package |
| Geocoding | `geocoding` ^3.0.0 | Reverse geocode lat/lng to human-readable names |
| Google Auth | `google_sign_in` ^6.2.2 | Standard Google OAuth2 for Flutter |
| Google APIs | `googleapis` ^13.2.0 | Official Google Calendar API client |

**Rejected alternative**: Cactus (all-in-one LLM+STT SDK) — lacks TTS (still needs flutter_tts), continuous STT undocumented, Qwen 2.5 3B unverified, lower adoption (23 likes), vendor lock-in risk.

---

## Prerequisites

Before starting Phase 6:

### P1. Fix Phase 5 blocking issues
From REV-20260220-234604:
1. Navigation route bug in `search_screen.dart`
2. Raw error exposure in `search_screen.dart`
3. Redundant `searchEntries()` in `session_providers.dart`

### P2. Complete deferred education gates
Phases 3, 4, and 5 each have deferred education gates. These must be completed before Phase 7 to close knowledge debt — Phase 7's voice architecture builds on Phase 5's memory recall code, and compounding knowledge gaps create integration risk.

### P3. Native library validation spike (1 session)
Before committing to Phases 7-8, validate on the target device:
1. **sherpa_onnx**: Confirm compilation, produce transcription output, measure RAM footprint
2. **llamadart**: Confirm compilation with Qwen 2.5 3B Q4_K_M, measure tokens/second (GPU and CPU), measure time-to-first-token, measure RSS memory during inference
3. **Also test Qwen 2.5 1.5B** — if 3B latency exceeds 8s per 150-token response, the 1.5B variant (2-4s) may be the better trade-off for voice mode
4. **Coexistence test**: Load both Whisper (base.en) and Qwen simultaneously, confirm no OOM on 6GB device

**If sherpa_onnx fails to build**: There is no alternative Flutter STT package with continuous recognition. The voice vision must be re-evaluated. This spike de-risks the entire plan.

---

## Phase 6: Session Management & UX Fixes
**Complexity**: S-M | **Schema version**: 2 (add resume columns)

### Tasks

#### 6.1 Discard/abort session capability
- Move "End Session" and "Discard" into a single overflow menu (three-dot icon) in `JournalSessionScreen` app bar — prevents mis-tap between two adjacent destructive actions
- Confirmation dialog: "Discard this entry? This cannot be undone."
- New `SessionNotifier.discardSession()`: delete session + messages from DB, clear state, pop navigation
- New DAO methods: `SessionDao.deleteSession(sessionId)`, `MessageDao.deleteMessagesBySession(sessionId)`

#### 6.2 Delete individual journal entries
- Add delete action to `SessionCard` (swipe-to-delete or overflow menu)
- Confirmation dialog showing session date + summary preview
- Cascade delete: session + all messages
- `allSessionsProvider` stream updates UI automatically

#### 6.3 Clear all entries + storage summary
- Add "Data Management" section to settings screen
- Storage summary: "Journal entries: X sessions, Y messages" (extend later with photo storage in Phase 9)
- "Clear All Entries" with two-step confirmation: dialog → type "DELETE" to confirm
- New DAO methods: `SessionDao.deleteAllSessions()`, `MessageDao.deleteAllMessages()`

#### 6.4 Don't save empty/illegible sessions
- In `endSession()`: check if session has any USER messages
- If no user messages (only AI greeting), call `discardSession()` instead of generating summary
- Show brief SnackBar: "Session discarded — nothing was recorded." Auto-dismiss after 3 seconds, no action required. (Not silent — gives the user confirmation the outcome was intentional, especially on accidental launches.)

#### 6.5 Redesign landing page with chronological grouping
- Keep the existing flat list (newest first) but add **sticky month-year section headers** as non-interactive visual dividers
- Within each month: sessions sorted by date, descending
- No drill-down navigation — sessions remain one tap from home screen
- New DAO method: `watchSessionsPaginated(limit: 50)` with "Load more" at bottom for older entries
- Add index on `startTime DESC` to `JournalSessions` for query performance at scale
- Use `SliverList` + `SliverPersistentHeader` for sticky headers

#### 6.6 Verify UTC storage + local timezone display
- Audit: all DB inserts use `DateTime.now().toUtc()` (likely already correct — `timezone` column stores IANA string)
- Audit: all display renders use `.toLocal()` in `SessionCard`, `ChatBubble`, detail screens
- Add test: round-trip UTC → DB → local display preserves correctness

#### 6.7 Resume/add to past journal entry
- "Continue Entry" button on `SessionDetailScreen`
- Loads existing session, appends new messages (original `startTime` preserved)
- Schema: add `isResumed: BoolColumn` and `resumeCount: IntColumn` to `JournalSessions` (migration v2)
- Works in both text mode and voice mode

> **Moved from Phase 7**: Session resume is functionally independent of voice mode. Building it in Phase 6 validates the schema migration path and reduces Phase 7's scope to pure voice concerns.

### Key files
- `lib/providers/session_providers.dart` — discard logic, empty session check, resume
- `lib/database/daos/session_dao.dart` — delete methods, paginated queries, resume columns
- `lib/database/daos/message_dao.dart` — cascade delete methods
- `lib/ui/screens/session_list_screen.dart` — grouped landing page
- `lib/ui/screens/journal_session_screen.dart` — overflow menu (discard + end)
- `lib/ui/screens/settings_screen.dart` — data management section
- `lib/ui/widgets/session_card.dart` — delete action

### ADR needed
- **ADR-0014**: Session Lifecycle — discard vs delete semantics, empty session policy, resume semantics (original date preservation, multi-resume)

---

## Phase 7A: Voice Foundation
**Complexity**: M | **Schema version**: 2 (no new migration)

> **Split from original Phase 7**: Native library integration (STT + TTS) is validated separately from the continuous conversation loop. This derisks the native C++/JNI integration before building complex orchestration on top.

### Tasks

#### 7A.1 Integrate `sherpa_onnx` for continuous STT
- New `lib/services/speech_recognition_service.dart` as **abstract class** with mock implementation for testing
- Whisper model via sherpa_onnx — constrain to **base.en** (~150MB) or **small.en** (~500MB), document ceiling in ADR-0015
- Download Whisper model on first use, store in app-private internal storage (`getApplicationDocumentsDirectory()`)
- Verify sherpa_onnx processes audio in-memory only (no temp files to disk) — document in ADR-0015
- Continuous streaming recognition — no time limits, no pause timeouts
- Use **sherpa_onnx native VAD** (Voice Activity Detection) for utterance boundary detection instead of a fixed silence timer
- Expose `Stream<String>` of recognized text chunks
- Android permissions: `RECORD_AUDIO` in manifest + runtime permission request with rationale dialog
- Android manifest: declare `android:foregroundServiceType="microphone"` for background STT on Android 10+
- Handle permission denial gracefully: degrade to text-only mode, show explanation with Settings deep link

#### 7A.2 Integrate `flutter_tts`
- New `lib/services/text_to_speech_service.dart` as **abstract class** with mock implementation
- `speak(text)`, `stop()`, `speakSentence(text)` (for streaming from LLM), completion callbacks
- Configurable voice params (rate, pitch, volume) with sensible defaults

#### 7A.3 Push-to-talk mode
- Mic button in `JournalSessionScreen` input area — hold/tap to record, release to send
- Transcribed text appears in the message input field for review before sending
- TTS speaks the AI response
- This validates the full STT → message → response → TTS pipeline without continuous mode complexity
- Voice mode toggle in settings: "Start in voice mode" (default: false until continuous mode ships in 7B)

#### 7A.4 Audio focus management
- Register `AudioManager.OnAudioFocusChangeListener` via platform channel
- On `AUDIOFOCUS_LOSS` (phone call, navigation turn-by-turn): pause STT, save state
- On `AUDIOFOCUS_GAIN`: resume STT automatically
- On `AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK`: reduce TTS volume, continue STT
- Handle Bluetooth audio device connect/disconnect

#### 7A.5 STT model download UX
- Check for Whisper model at first voice activation (not cold start)
- Show download dialog with size + progress bar
- **WiFi-only gate**: If on cellular, show "Download on Wi-Fi (recommended) / Download Now on cellular (X MB)" choice
- Verify available storage before starting download
- Resume capability via `dio` Range headers with persisted byte offset
- SHA-256 checksum hardcoded in app — verify after download, reject + delete on mismatch
- "Cancel" = text-only mode until downloaded

### Key files
- `lib/services/speech_recognition_service.dart` (new) — abstract class + sherpa_onnx implementation
- `lib/services/text_to_speech_service.dart` (new) — abstract class + flutter_tts implementation
- `lib/ui/screens/journal_session_screen.dart` — mic button, push-to-talk UI
- `android/app/src/main/AndroidManifest.xml` — RECORD_AUDIO permission, foreground service type

### New dependencies
```yaml
sherpa_onnx: ^1.12.25
flutter_tts: ^4.2.5
```

### ADR needed
- **ADR-0015**: Voice Mode Architecture — STT/TTS boundaries, VAD configuration, audio focus strategy, foreground service, Whisper model size ceiling, audio buffer lifecycle, error recovery contract, battery considerations

### Risks
- **High**: sherpa_onnx native build complexity — first JNI/C++ integration
- **Medium**: VAD tuning across different environments (quiet room vs street vs car)
- **Medium**: Battery drain from microphone + ONNX inference during extended sessions

---

## Phase 7B: Continuous Voice Mode
**Complexity**: L | **Schema version**: 2 (no new migration)

> **Depends on**: Phase 7A validated and working on target device.

### Tasks

#### 7B.1 Voice session orchestrator
- New `lib/services/voice_session_orchestrator.dart` — dedicated state machine for voice loop
- Receives `SpeechRecognitionService`, `TextToSpeechService`, reference to `SessionNotifier`
- Manages the listen → speak → listen state machine with explicit states: `idle`, `listening`, `processing`, `speaking`, `error`, `paused`
- Calls `SessionNotifier.sendMessage()` for actual message processing
- New Riverpod provider: `voiceOrchestratorProvider`
- **Keeps SessionNotifier focused on message pipeline** — voice orchestration does not bloat it

#### 7B.2 Continuous voice conversation loop
Core flow after session starts in voice mode:
1. Get greeting → TTS speaks it
2. After TTS completes → STT starts listening
3. Accumulate recognized text → VAD detects utterance end
4. Send accumulated text as USER message
5. Get agent follow-up → **stream TTS from first completed sentence** while LLM generates the rest (reduces perceived latency from 7-11s to 3-5s)
6. After TTS completes → resume STT
7. Repeat until verbal close or manual end

Handle interruption: if user speaks while AI is speaking, stop TTS immediately and process input.

**Transcription preview**: Display accumulated STT text on screen in real-time. Serves as visual feedback (user can glance to confirm what was heard) and accessibility for silent/noisy environments.

#### 7B.3 Voice mode error recovery contract
Define and implement verbal recovery for every error state:
- **STT failure** (model not loaded, permission revoked): TTS speaks "I can't hear you right now. Try switching to text mode." Transition to text mode automatically.
- **STT returns empty** after extended listening: TTS speaks "I didn't catch that. Try again?" Resume listening.
- **LLM timeout** (>5s with no tokens): TTS speaks "Still thinking..." at 5s. If >10s, fall back to Layer A response and announce: "Let me give you a simpler response."
- **TTS audio focus loss** (phone call): Pause session, save state. On focus regain: TTS speaks "Welcome back. Where were we?" and resumes listening.
- **Network loss mid-Claude call**: Silent fallback to Layer A, no announcement needed (response just comes from a different layer).
- All recovery utterances defined in a constants file: `lib/constants/voice_recovery_messages.dart`

#### 7B.4 Verbal close commands
- Use the **LLM (Layer B or C) for intent detection** instead of fuzzy string matching — the LLM has sentence-level understanding and correctly distinguishes "I'm done with the dishes" from "I'm done journaling"
- For Layer A fallback: use the existing `_doneSignals` list but require **verbal confirmation**: AI responds "Got it, shall I save and close?" — user says "yes" to confirm
- Add **verbal discard**: "delete this entry", "discard this", "never mind, throw it away" → verbal confirmation: "Delete this entry? Say yes to confirm."
- On confirmed close: trigger `endSession()`, speak closing summary via TTS, auto-save
- Add verbal "undo" for 30s after unintended close: "wait, no" or "I didn't mean that" reopens the session

#### 7B.5 Auto-save on disconnect/backgrounding
- `WidgetsBindingObserver` in `JournalSessionScreen`: on `paused`/`detached` → auto-end session
- Ensure session saved even if app killed mid-conversation (messages already saved per-message)
- Handle audio focus loss events from Phase 7A.4
- Setting: "Auto-save on exit" (on by default)

#### 7B.6 Hands-free operation validation
- After assistant gesture launch: greeting plays → listening starts → zero touch required for the conversation loop
- All confirmations handleable verbally ("yes"/"no" via STT)
- Error states recover verbally (per 7B.3)
- Manual UI actions (photo capture, text editing) remain available via touch — voice mode does not disable any touch features

#### 7B.7 Android assistant direct voice launch
- Modify `MainActivity.kt`: detect `ACTION_ASSIST`/`ACTION_VOICE_ASSIST` → start session in voice mode
- Route: `/session?voice=true`
- Voice mode: detect "add to today's entry" or "continue my journal" to resume most recent session (uses Phase 6.7's resume capability)

### Key files
- `lib/services/voice_session_orchestrator.dart` (new) — voice loop state machine
- `lib/constants/voice_recovery_messages.dart` (new) — all verbal recovery utterances
- `lib/providers/voice_mode_providers.dart` (new) — voice state, orchestrator provider
- `lib/ui/screens/journal_session_screen.dart` — continuous voice UI (waveform, transcription preview)
- `lib/repositories/agent_repository.dart` — verbal close detection
- `android/app/src/main/kotlin/.../MainActivity.kt` — assistant intent handling

### ADR needed
- (Covered by ADR-0015 from Phase 7A)

### Risks
- **High**: Voice loop latency — total STT→LLM→TTS chain must be under 5s perceived (streaming TTS is critical)
- **Medium**: VAD sensitivity tuning — too sensitive = fragmented input, too lenient = long waits
- **Medium**: False positive/negative verbal close detection — mitigated by verbal confirmation
- **Medium**: Battery drain from continuous STT — mitigated by pausing during TTS and inference

---

## Phase 8: Local LLM + Personality
**Complexity**: L | **Schema version**: 2 (no new migration)

### Tasks

#### 8.0 Extract ConversationLayer strategy
- The existing `AgentRepository` was designed as a two-way switch (Layer A/B). Adding Layer C transforms it into a multi-concern orchestrator. The codebase itself anticipated this at `agent_repository.dart:18-19`.
- Extract a `ConversationLayer` abstract class: `getGreeting(...)`, `getFollowUp(...)`, `generateSummary(...)`
- Implement `RuleBasedLayer` (existing Layer A code), `ClaudeApiLayer` (existing Layer B code)
- `AgentRepository` becomes a thin dispatcher selecting which `ConversationLayer` to use
- Each layer receives dependencies via constructor injection (ADR-0007)
- Add `AgentLayer.llmLocal` to the `AgentLayer` enum (currently only has `ruleBasedLocal` and `llmRemote`)
- Update all exhaustive `switch` statements on `AgentLayer`

#### 8.1 Research spike: therapeutic conversation techniques
- Research motivational interviewing (MI), active listening, CBT-informed prompts, non-directive counseling
- Document in `docs/research/therapeutic-conversation-techniques.md`
- Extract prompt engineering patterns for empathetic, non-judgmental responses

#### 8.2 Integrate `llamadart` with Qwen 2.5 3B (or 1.5B)
- New `LocalLlmLayer` implementing `ConversationLayer`
- New `lib/services/local_llm_service.dart`: llamadart wrapper
- Model: Qwen 2.5 3B Instruct GGUF (Q4_K_M, ~2GB) — or 1.5B if spike shows 3B latency is unacceptable for voice mode
- Configure: temperature=0.7, top_p=0.9, **max_tokens=150** (reduced from 200 — at 10 tok/s, 150 tokens = 15s vs 20s generation time; voice responses should be concise)
- Vulkan GPU acceleration with CPU fallback
- Streaming token response via `Stream<String>`
- **Verify FFI binding type**: If `llamadart` uses blocking FFI, wrap inference in `Isolate.run()` in `local_llm_service.dart` to avoid freezing the Dart UI isolate
- **Model lifecycle management**: Lazy-load Qwen only when first inference is needed. Unload on `onTrimMemory` callback from Android. If RAM is critically low, degrade to Layer A rather than OOM crash.
- Pause sherpa_onnx STT recognizer during LLM inference (the voice loop already stops STT while TTS speaks — extend this window to cover inference). This eliminates the need for both models to hold full resident memory simultaneously.

#### 8.3 Model download on first use
- New `lib/services/model_download_service.dart`
- **Defer download prompt to after first completed session** — user should experience the app working (via Layer A or B) before committing 2GB of storage
- Download from Hugging Face over HTTPS
- **SHA-256 checksum hardcoded in app binary** — compute after download, reject + delete on mismatch. Do not leave partial or corrupt files on disk. Document specific checksum in ADR-0017.
- **WiFi-only gate**: If on cellular, show "This download is ~2GB. Download on Wi-Fi (recommended) / Download Now" choice
- **Storage check**: Verify available storage before starting. Show: "This requires X GB. You have Y GB available."
- Resume capability via `dio` Range headers with persisted byte offset in SharedPreferences. On app restart: file exists at expected size = complete; partial = resume; absent = fresh start.
- "Cancel" = use Layer A/B until downloaded
- **Model version pinning**: Hardcode the exact HuggingFace model URL and file size in the app. Document in ADR-0017 that the Hugging Face CDN is the one accepted direct external dependency (model files are too large for Edge Function proxy).
- **Background download announcement**: When Layer A is active because the model is still downloading, verbally announce at session start in voice mode: "I'm running in basic mode while my full personality downloads."

#### 8.4 Resolve layer architecture (supersede ADR-0006)
- ADR-0006 defined three layers: A (rule-based), B (Claude API), C (memory recall/RAG). **The plan's "Layer C" for local LLM collides with the existing Layer C (memory recall), which is already implemented in `session_providers.dart`.**
- New layer architecture:
  - **Layer A**: Rule-based (offline, always available) — unchanged
  - **Layer B**: LLM-enhanced, with two sub-strategies:
    - **B.remote**: Claude API via Supabase Edge Function — unchanged
    - **B.local**: Local LLM via llamadart — new
  - **Layer C**: Memory Recall (intent classification + search + LLM synthesis) — unchanged, can use B.remote or B.local for synthesis
- Fallback chain:
  1. If "prefer Claude" setting on + online → B.remote
  2. If local model downloaded → B.local
  3. Else → Layer A
- Default: B.local to avoid API costs. Setting: "Prefer Claude when online" (default: off)
- **Lock layer per session**: Once a session starts on a given layer, it stays there for the session duration. No mid-session personality switching — brief wait + fallback announcement is less disorienting than a sudden quality change.
- **Custom prompt isolation**: The `customPromptOverride` from personality settings is injected only into B.local context. For B.remote, the system prompt remains server-side per ADR-0005. These must never cross.

#### 8.5 Default personality "Guy"
- New `lib/models/personality_config.dart`: name, systemPrompt, conversationStyle, techniques
- Default system prompt informed by research (MI + active listening + warm companion tone)
- Personality config stored in **drift/SQLite** (not SharedPreferences) — it is structured data with multiple fields, consistent with ADR-0004's "local drift/SQLite is the authoritative source of truth" pattern. Simple boolean settings remain in SharedPreferences; structured configs go in drift.
- Sanitize and length-limit `customPromptOverride` before injection into LLM system prompt

#### 8.6 Personality settings panel
- Settings section: assistant name, conversation style dropdown (Warm/Professional/Curious), technique toggles, custom prompt override
- Rebuild agent personality on next session start (not mid-session)

#### 8.7 "Journal only" mode
- Toggle in settings (off by default, remembered across sessions)
- When on: skip greeting, skip follow-ups, skip AI summary — just capture user input silently
- Use Layer A first-sentence summary only

#### 8.8 Layer fallback integration tests
- Test all fallback paths: B.local→B.remote→A, B.remote→B.local→A, offline+no-model→A
- Test session-locked layer: simulate mid-session model crash, verify layer stays locked with fallback announcement
- Mock network + model availability for deterministic tests
- Design service interfaces (`SpeechRecognitionService`, `TextToSpeechService`, `LocalLlmService`) as abstract classes with mock implementations from day one to maintain 80% coverage target

### Key files
- `lib/services/local_llm_service.dart` (new) — llamadart wrapper
- `lib/services/model_download_service.dart` (new) — download orchestration
- `lib/models/personality_config.dart` (new) — personality data model
- `lib/models/conversation_layer.dart` (new) — abstract ConversationLayer + RuleBasedLayer, ClaudeApiLayer, LocalLlmLayer
- `lib/repositories/agent_repository.dart` — thin dispatcher over ConversationLayer strategy
- `lib/providers/session_providers.dart` — journal-only mode, session-locked layer
- `lib/ui/screens/settings_screen.dart` — personality + journal-only settings

### New dependencies
```yaml
llamadart: ^0.6.2
```

### ADR needed
- **ADR-0017**: Local LLM Integration — supersedes ADR-0006 with sub-strategy architecture, model selection (3B vs 1.5B rationale from spike), fallback chain, model lifecycle/RAM management, checksum verification, download source pinning, session-locked layer policy, custom prompt isolation. **Must be written before Phase 8 implementation.**
- **ADR-0018**: Personality System — prompt engineering, therapy technique mapping, drift storage rationale

### Risks
- **High**: llamadart FFI binding may block Dart isolate — must verify and wrap in `Isolate.run()` if needed
- **High**: 2GB model download UX — mitigated by WiFi gate, storage check, resume, deferred prompt
- **High**: RAM pressure — Whisper + Qwen + Flutter on 6GB device — mitigated by STT pause during inference, lazy loading, `onTrimMemory` lifecycle
- **Medium**: Inference latency — 3B model may take 5-10s per response — mitigated by streaming TTS, reduced max_tokens, 1.5B fallback option

---

## Phase 9: Photo Integration
**Complexity**: M | **Schema version**: 3 (single migration — Photos table + JournalMessages column)

### Tasks

#### 9.1 Photo database schema
- **Single migration v3** (not split across v3+v4): new `Photos` table (photoId, sessionId, messageId nullable, localPath, cloudUrl, description, timestamp, syncStatus, width, height, fileSizeBytes) AND add `photoId: TextColumn` nullable to `JournalMessages`
- New `PhotoDao` with CRUD + query methods

#### 9.2 Camera + gallery integration
- New `lib/services/photo_service.dart` using `image_picker`
- `takePhoto()` / `pickFromGallery()` → **strip EXIF metadata** → compress (max 2048px, 85% JPEG) → save to `photos/[sessionId]/[photoId].jpg`
- **EXIF stripping is mandatory** — `image_picker` preserves EXIF including GPS coordinates, device model, timestamps. Strip before local storage and before cloud upload. Use the `image` package to re-encode without EXIF, or `native_exif` to remove metadata.
- Run compression in `Isolate.run()` — CPU-bound resize + JPEG encode must not block the UI isolate
- Validate photo file paths: always construct from `sessionId` + `photoId` using a canonical function. Never use stored `localPath` directly from database for file access (path traversal protection).
- Android permission: `CAMERA` in manifest + runtime request with rationale

#### 9.3 Photo capture UI in journal session
- Camera button in input area (beside text field) — available in **both text mode and voice mode**
- Bottom sheet: "Take Photo" / "Choose from Gallery"
- Preview with "Add" / "Cancel"
- In voice mode: the camera button is a manual touch interaction (not hands-free). After capture, the voice loop resumes automatically.

#### 9.4 Voice mode photo flow
- After photo added in voice mode: AI speaks "Tell me about this photo"
- STT captures description → saved to `Photos.description`
- If VAD detects no speech after prompt → skip description, continue conversation
- Voice loop resumes seamlessly after photo flow completes

#### 9.5 Photo messages in conversation
- Photo messages render as thumbnails in `ChatBubble`
- Tap thumbnail → full-screen viewer
- Caption below thumbnail

#### 9.6 Photo gallery screen
- New `lib/ui/screens/photo_gallery_screen.dart`: grid view (3 columns), newest first
- Tap → full-screen with swipe, caption overlay, "Jump to entry" button
- Gallery icon in session list app bar — **hidden until at least one photo exists** (progressive disclosure, matching the search icon pattern)

#### 9.7 Photos in session detail view
- Inline thumbnails in message list (chronological)
- Tap → full-screen viewer

#### 9.8 Cloud sync for photos
- Extend `SyncRepository`: upload photos to Supabase Storage after session messages
- **Supabase Storage bucket must be private** with RLS: `auth.uid() = user_id`. Document as required migration step.
- Path: `journals/[userId]/photos/[photoId].jpg`
- **Parallelize uploads within a session** using `Future.wait()` (max 3-5 concurrent) — photos within a session have no ordering dependency
- Per-photo sync status tracking — a failed photo upload does not mark the entire session as FAILED
- Queue for offline → online transition

#### 9.9 Photo deletion
- Delete from full-screen viewer with confirmation
- Cascade: session delete → delete all associated photos (files + DB records)

#### 9.10 Storage management
- Extend "Data Management" section (from Phase 6.3): "Photos: X photos, Y MB" storage summary
- Future consideration (not Phase 9 scope): "cloud-only after sync" mode to reclaim local storage

### Key files
- `lib/database/tables.dart` — Photos table + JournalMessages photoId column
- `lib/database/daos/photo_dao.dart` (new) — photo CRUD
- `lib/services/photo_service.dart` (new) — camera/gallery/EXIF strip/compression
- `lib/ui/screens/photo_gallery_screen.dart` (new)
- `lib/ui/widgets/photo_message_bubble.dart` (new)
- `lib/repositories/sync_repository.dart` — photo upload with parallel uploads
- `lib/ui/screens/journal_session_screen.dart` — camera button

### New dependencies
```yaml
image_picker: ^1.1.2
```

### ADR needed
- **ADR-0019**: Photo Storage — local path structure, EXIF stripping policy, compression policy, Supabase bucket ACL, canonical path construction (path traversal prevention), cloud sync strategy

### Risks
- **Medium**: EXIF stripping adds a processing step — verify `image_picker` output format to choose the most efficient stripping method
- **Medium**: Photo sync volume — parallelize within sessions but rate-limit to avoid overwhelming mobile radio
- **Low**: Storage growth — ~875MB/year for a daily user with 3 photos/session. Acceptable for flagship device, documented in ADR-0019

---

## Phase 10: Location Awareness
**Complexity**: S | **Schema version**: 4 (add columns to sessions)

### Tasks

#### 10.1 Location schema
- Add to `JournalSessions`: `latitude`, `longitude`, `locationAccuracy` (all REAL nullable), `locationName` (TEXT nullable)
- **Precision reduction at capture time**: Round coordinates to 2 decimal places (~1.1km precision) before storing in database. Full GPS precision is unnecessary for "I journaled in San Francisco" and creates a movement diary if the Supabase instance is compromised.

#### 10.2 Location service + permissions
- New `lib/services/location_service.dart` using `geolocator`
- Use `getLastKnownPosition()` first (returns immediately if a recent fix exists). Only fall back to `getCurrentPosition()` with a **2-second timeout** if last-known is null or stale (>1 hour).
- Android permissions: `ACCESS_COARSE_LOCATION` as default. Only request `ACCESS_FINE_LOCATION` if user explicitly opts into higher precision in settings. Do NOT declare `ACCESS_BACKGROUND_LOCATION` — location is captured at session start only (foreground operation).
- Runtime permission request with rationale dialog. Handle denial gracefully: skip location capture, continue session normally.

#### 10.3 Capture location on session start
- In `startSession()`: **fire-and-forget** location capture in `Future.microtask()` after session record is created and greeting has started — must not delay session creation
- Update session record with location data asynchronously
- Respect "Location enabled" setting (default: **off** — opt-in, not opt-out, given sensitivity)

#### 10.4 Reverse geocoding
- `geocoding` package: lat/lng → "City, State" or "City, Country"
- Handle offline: leave `locationName` null, populate on next sync or next app start when online

#### 10.5 Display location in UI
- Session detail: location pill at top ("San Francisco, CA")
- Session card: small location icon indicator

#### 10.6 Location privacy settings
- Toggle in settings (default: off), "Clear Location Data" button with confirmation
- **Cloud sync policy**: Sync only `locationName` (human-readable string) to Supabase. Raw coordinates remain local-only. This prevents a cloud compromise from yielding precise location history. Document in ADR-0020.

### Key files
- `lib/services/location_service.dart` (new)
- `lib/database/tables.dart` — location columns
- `lib/providers/session_providers.dart` — capture on start (fire-and-forget)
- `lib/ui/screens/session_detail_screen.dart` — display

### New dependencies
```yaml
geolocator: ^13.0.2
geocoding: ^3.0.0
```

### ADR needed
- **ADR-0020**: Location Tracking — opt-in default, precision reduction rationale, cloud-only-locationName policy, data clearing, permission strategy (coarse default, fine opt-in)

### Risks
- **Low**: GPS cold start latency — mitigated by `getLastKnownPosition()` first, fire-and-forget pattern
- **Low**: Geocoding offline — acceptable, populate later

---

## Phase 11: Google Calendar + Reminders
**Complexity**: XL | **Schema version**: 5 (optional events table)

> **Upgraded from L to XL**: OAuth2 alone routinely consumes a full sprint. Combined with temporal expression parsing and intent taxonomy redesign, this phase has substantial novel complexity.

### Tasks

#### 11.1 Research: personal assistant capabilities
- Survey common patterns, narrow to calendar + reminders for v1
- Document in `docs/research/personal-assistant-capabilities.md`

#### 11.2 Google OAuth2 integration
- `google_sign_in` + `googleapis` packages
- **Minimal OAuth scopes** — request `https://www.googleapis.com/auth/calendar.events` (create/edit events) only. If `listUpcomingEvents()` is needed, add `https://www.googleapis.com/auth/calendar.events.readonly` as a separate justified scope. Never request the full `calendar` scope.
- Token storage in `flutter_secure_storage`
- Token refresh handling
- **Note**: For personal use, unverified OAuth app status is sufficient (100 test users). Document the path to full Google verification separately if the app is ever shared. The verification process requires domain ownership, privacy policy URL, and potentially a security assessment.

#### 11.3 Google Calendar service
- New `lib/services/google_calendar_service.dart`
- `createEvent()`, `createReminder()`, `listUpcomingEvents()` (if readonly scope approved)

#### 11.4 Unified intent taxonomy redesign
- **The current `IntentClassifier` returns `IntentType.journal` or `IntentType.query`**. Adding `calendarEvent` and `reminder` creates a multi-way classification that interacts with existing confidence thresholds. Temporal expressions overlap (e.g., "Remind me about tomorrow's meeting" contains temporal references the current classifier scores as a recall signal).
- Redesign the classifier to return a **ranked list of intents** with confidence scores, rather than a single type. Top intent drives routing.
- New intent types: `calendarEvent`, `reminder` alongside existing `journal`, `query`
- Handle overlapping signals: "Did I have a meeting tomorrow?" is both recall and temporal

#### 11.5 AI-assisted event suggestion
- After user message with calendar intent: AI suggests "Add to calendar?" with extracted details (title, date, time)
- Inline confirmation widget in conversation
- In voice mode: TTS reads the extracted details aloud ("Add 'Team Meeting' on Tuesday at 3pm to your calendar?") before asking for confirmation

#### 11.6 User confirmation + creation
- "Add to Calendar" → OAuth if needed → create event → success toast
- "No thanks" → dismiss, continue conversation
- Never auto-create without confirmation
- In voice mode: verbal "yes"/"no" confirmation
- Verbal "edit that" path: "change it to 4pm" or "wrong day" → AI re-extracts, reads corrected details back for re-confirmation

#### 11.7 OAuth-during-voice-mode handling
- If Google is not yet connected when a calendar intent fires in voice mode: **do not interrupt with OAuth screen**. AI verbally says "I'd need to connect to your Google Calendar first. I'll remind you when we're done."
- Queue the event details for post-session confirmation
- After session ends: show a notification or card on home screen: "You mentioned a calendar event. Connect Google Calendar to add it."

#### 11.8 Calendar settings
- Settings section: connect/disconnect Google, auto-suggest toggle, confirmation toggle

### Key files
- `lib/services/google_auth_service.dart` (new)
- `lib/services/google_calendar_service.dart` (new)
- `lib/services/intent_classifier.dart` — unified intent taxonomy
- `lib/providers/session_providers.dart` — suggestion flow, queued events
- `lib/ui/screens/journal_session_screen.dart` — confirmation widget

### New dependencies
```yaml
google_sign_in: ^6.2.2
googleapis: ^13.2.0
extension_google_sign_in_as_googleapis_auth: ^2.0.13
```

### ADR needed
- **ADR-0021**: Google Calendar Integration — minimal OAuth scopes with rationale, unified intent taxonomy design, confirmation policy, OAuth-during-voice-mode deferral pattern, verbal edit flow, token management, unverified app limitations

### Risks
- **High**: OAuth2 complexity — consent flow, token refresh, Google verification process
- **High**: Temporal expression parsing accuracy (consider `chrono` or similar NLP library)
- **High**: Intent taxonomy redesign ripples through existing recall classification (must not regress Phase 5)
- **Medium**: False positive intent detection could annoy users — mitigated by confirmation requirement

---

## Cross-Phase Notes

### Database Migration Path
Phase 6: v2 (resume columns) → Phase 7A: v2 → Phase 7B: v2 → Phase 8: v2 → Phase 9: v3 (Photos + photoId) → Phase 10: v4 (location) → Phase 11: v5 (events)

### Supabase Schema Sync Strategy
Each schema change needs a matching Supabase migration in `supabase/migrations/`. Strategy:
- **Column additions**: `ALTER TABLE ... ADD COLUMN ... DEFAULT NULL` on Supabase (backward-compatible)
- **New tables** (Photos, Events): Require new RLS policies restricting access to `auth.uid() = user_id`
- **New storage** (Photos): Requires private Supabase Storage bucket with RLS
- **SyncRepository UPSERT maps**: Must be updated for each new column. Consider centralizing column maps to prevent drift from schema.
- **Location sync exception**: Only `locationName` syncs to cloud; raw coordinates remain local-only (ADR-0020)

### Concurrency Policy
Phases 7-9 introduce CPU-bound native operations that must not block the Dart UI isolate:
- **LLM inference** (llamadart): Verify FFI binding; if blocking, wrap in `Isolate.run()`
- **Image compression** (Phase 9): Run in `Isolate.run()`
- **STT/TTS** (sherpa_onnx, flutter_tts): Managed by platform channels (async by default, verify)
- **Network I/O** (sync, geocoding): Async I/O, safe on main isolate
- **SQLite** (drift): Already runs on background isolate by default
- Document in ADR-0015 or ADR-0017: "CPU-bound operations must run in background isolates"

### Permission Management
Phases 7, 9, and 10 introduce Android runtime permissions. Unified strategy:
- Request permissions **at first use of the feature**, not upfront at app start
- Provide rationale dialogs explaining why the permission is needed
- Handle "Don't ask again" with a Settings deep-link explanation
- Graceful degradation on denial: voice → text-only, camera → hidden, location → skipped
- `RECORD_AUDIO` denial is the most impactful (blocks core voice experience) — provide prominent in-app guidance

### ADR Summary

| ADR | Phase | Topic | Supersedes |
|-----|-------|-------|------------|
| ADR-0014 | 6 | Session Lifecycle — discard, delete, empty policy, resume semantics | — |
| ADR-0015 | 7A | Voice Mode Architecture — STT/TTS, VAD, audio focus, foreground service, error recovery, battery | — |
| ADR-0017 | 8 | Local LLM Integration — sub-strategy architecture, model lifecycle, RAM, checksum, download, session-locked layer | ADR-0006 |
| ADR-0018 | 8 | Personality System — prompt engineering, therapy techniques, drift storage | — |
| ADR-0019 | 9 | Photo Storage — EXIF stripping, path security, bucket ACL, compression, sync | — |
| ADR-0020 | 10 | Location Tracking — opt-in, precision reduction, cloud-only-locationName | — |
| ADR-0021 | 11 | Google Calendar — OAuth scopes, intent taxonomy, voice-mode deferral | — |

### Verification Approach
Each phase: run `python scripts/quality_gate.py` (format, lint, test, coverage >=80%, ADR check). Run `/review` for code changes. Test on physical device for voice/camera/location features. Design service interfaces as abstract classes with mock implementations to maintain coverage target through native-dependent phases.

### New Dependency Summary
```yaml
# Phase 7A
sherpa_onnx: ^1.12.25
flutter_tts: ^4.2.5

# Phase 8
llamadart: ^0.6.2

# Phase 9
image_picker: ^1.1.2

# Phase 10
geolocator: ^13.0.2
geocoding: ^3.0.0

# Phase 11
google_sign_in: ^6.2.2
googleapis: ^13.2.0
extension_google_sign_in_as_googleapis_auth: ^2.0.13
```

### Risk Register Summary

| Risk | Severity | Phase | Mitigation |
|------|----------|-------|------------|
| sherpa_onnx native build failure | Critical | 7A | Pre-integration spike (P3) — validate before committing |
| RAM coexistence (Whisper + Qwen + Flutter) | High | 7A+8 | Constrain Whisper to base.en, pause STT during inference, lazy load, onTrimMemory |
| Voice loop latency (7-11s per turn) | High | 7B+8 | Streaming TTS, VAD, max_tokens=150, benchmark 1.5B vs 3B |
| llamadart FFI blocks Dart isolate | High | 8 | Verify binding type, wrap in Isolate.run() if blocking |
| 2GB model download failure/cellular cost | High | 8 | WiFi gate, resume, storage check, deferred prompt, hardcoded checksum |
| Model integrity (MITM on HuggingFace) | High | 8 | SHA-256 hardcoded in binary, reject + delete on mismatch |
| Location data privacy (cloud movement diary) | High | 10 | Precision reduction, opt-in, cloud-only locationName |
| Photo EXIF metadata leaks GPS | High | 9 | Strip EXIF before storage and upload |
| Google OAuth complexity + verification | High | 11 | Unverified app for personal use, document verification path |
| Intent taxonomy redesign regression | High | 11 | Comprehensive test coverage on existing recall classification |
| Audio focus conflicts (calls, nav) | Medium | 7A | AudioFocusChangeListener, pause/resume STT |
| Pre-1.0 llamadart API churn | Medium | 8 | Pin exact version, expect breaking changes |
| Test coverage erosion (native deps) | Medium | 7A+ | Abstract service interfaces with mock implementations |
| Education gate debt (Phases 3-5) | Medium | Pre | Schedule before Phase 7 (P2) |
