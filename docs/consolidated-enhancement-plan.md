# Consolidated Enhancement Plan: Voice-First AI Journal Uplift

> Generated: 2026-02-26
> Sources: 7 project analyses + 8 research synthesis patterns + 5 prior project analyses

## Sources

### New Analyses (2026-02-26)
| # | Project | Repo | License | Patterns Found | Key Specialist Finding |
|---|---------|------|---------|---------------|----------------------|
| 1 | FlutterVoiceFriend | `jbpassot/flutter_voice_friend` | CC BY-NC-SA 4.0 | 6 | Activity-scoped templates + session history injection |
| 2 | LiveKit Flutter | `livekit/components-flutter` + `client-sdk-flutter` | Apache 2.0 | 6 | ReusableCompleter + AudioTrackState machine |
| 3 | Sherpa ONNX | `k2-fsa/sherpa-onnx` | Apache 2.0 | 6 | Silence padding + endpoint tuning for our STT |
| 4 | Cactus | `cactus-compute/cactus` | Custom (source-available) | 4 | ARM flag fix for SIGILL; avoid full adoption |
| 5 | PowerSync | `powersync-ja/powersync.dart` | Apache 2.0 | 7 | Drift bridge via SqliteAsyncDriftConnection |
| 6 | Dicio Android | `Stypox/dicio-android` | GPLv3 | 9 | WakeService not VoiceInteractionService; manifest bug |
| 7 | Porcupine | `Picovoice/porcupine` | Apache 2.0 | 6 | Two-tier API; custom keyword licensing constraints |

### Research Synthesis (2026-02-26)
8 patterns from cross-project analysis of 23+ GitHub projects and 9 shipped voice apps.

### Prior Analyses (2026-02-18, in `docs/unified-project-analysis.md`)
omi, lumma, kelivo, moodiary, syncable — 5 projects, patterns already in adoption log.

---

## Enhancement Priority Matrix

| # | Enhancement | Domain | Source(s) | Score | Priority | Effort | ADR? |
|---|-------------|--------|-----------|-------|----------|--------|------|
| 1 | Silence padding in stopListening() | STT | Sherpa ONNX | 24/25 | P0 | S | No |
| 2 | Endpoint rule tuning (rule1/rule2) | STT | Sherpa ONNX | 22/25 | P0 | S | No |
| 3 | ARM build flag fix (armv8.2-a) | LLM | Cactus | 22/25 | P0 | S | No |
| 4 | Manifest fix (foregroundServiceType) | Android | Dicio | N/A | P0 | S | No |
| 5 | Intent deduplication backoff (100ms) | Android | Dicio | N/A | P0 | S | No |
| 6 | Session history injection | Voice Loop | FlutterVoiceFriend | 22/25 | P1 | M | Yes |
| 7 | Raw audio preservation | Voice Loop | Research | 24/25 | P1 | M | Yes |
| 8 | ReusableCompleter for async safety | Architecture | LiveKit | 21/25 | P1 | S | No |
| 9 | Typed VoiceSessionError taxonomy | Architecture | LiveKit | 20/25 | P1 | S | No |
| 10 | Stop-with-delay (800ms) on PTT | Voice UX | FlutterVoiceFriend | 20/25 | P1 | S | No |
| 11 | [PAUSE] tag for conversational pacing | Voice UX | FlutterVoiceFriend | 20/25 | P1 | S | No |
| 12 | Unified voice-plus-text UI | UX | Research | 22/25 | P2 | L | Yes |
| 13 | Conversational onboarding | UX | Research | 22/25 | P2 | M | Yes |
| 14 | Journaling mode templates | Voice Loop | FlutterVoiceFriend | 22/25 | P2 | M | Yes |
| 15 | PowerSync + Drift bridge | Sync | PowerSync | 21/25 | P2 | XL | Yes |
| 16 | SupabaseConnector fatalResponseCodes | Sync | PowerSync | 22/25 | P2 | S | No |
| 17 | Lock screen management | Android | Dicio | 20/25 | P2 | S | No |
| 18 | Porcupine wake word ("Hey Journal") | Android | Porcupine | 20/25 | P2 | L | Yes |
| 19 | Three-tier STT architecture | STT | Research | 20/25 | P2 | L | Yes |
| 20 | DisposableChangeNotifier pattern | Architecture | LiveKit | 19/25 | P3 | M | No |
| 21 | AudioTrackState machine | Architecture | LiveKit | 19/25 | P3 | M | No |
| 22 | Dual notification channels | Android | Dicio | 18/25 | P3 | S | No |
| 23 | VAD + offline recognizer | STT | Sherpa ONNX | 18/25 | P3 | L | Yes |
| 24 | Soft gradient voice visualization | UX | Research | 18/25 | P3 | L | No |
| 25 | VoiceInteractionService Phase 2-3 | Android | Research | 18/25 | P4 | XL | Yes |
| 26 | Lock screen + background recording | Android | Research | 18/25 | P4 | XL | Yes |
| 27 | Concurrent local+cloud handoff | LLM | Cactus | 18/25 | P4 | L | Yes |
| 28 | CompletionResult telemetry fields | LLM | Cactus | 20/25 | P3 | S | No |

**Avoided (with rationale):**
- Cactus full library adoption — SSL-off, unconsented telemetry, proprietary .cact format, custom license
- LiveKit CachingTokenSource — Supabase SDK handles token refresh; duplication creates stale-token risk
- LiveKit RoomContext/Provider widgets — conflicts with our Riverpod architecture
- FlutterVoiceFriend boolean-flag state machine — our VoiceLoopPhase enum is strictly superior
- FlutterVoiceFriend API keys in .env asset — violates ADR-0005
- Dicio RecognitionService — wrong problem for journaling app
- Dicio VoiceInteractionService — dicio doesn't even use it; not viable for third-party apps

---

## Domain 1: Voice Conversation Loop

### E1. Session History Injection (ADOPT — P1)
**Source**: FlutterVoiceFriend analysis
**What**: Query last 3-5 session summaries from drift, inject into Claude system prompt.
**Why**: Claude gains awareness of prior sessions, enabling continuity ("Last time you mentioned feeling stuck at work...").
**Evidence**: FlutterVoiceFriend's multi-chain summarization validates the pattern. Our `JournalSessions.summary` column already exists for this purpose.
**Implementation**: `SessionDao.getRecentSummaries(limit: 5)` -> format as text -> inject into `AgentRepository.buildSystemPrompt()`.
**Affected files**: `lib/database/daos/session_dao.dart`, `lib/repositories/agent_repository.dart`
**Effort**: M | **ADR**: Yes (touches prompt construction)

### E7. Raw Audio Preservation (ADOPT — P1)
**Source**: Research synthesis (Rosebud failure analysis)
**What**: Save raw audio file BEFORE attempting transcription. Pipeline: capture -> save to storage -> transcribe -> analyze.
**Why**: If transcription fails, the audio is the last line of defense. Rosebud users report voice entries not saving.
**Evidence**: Universal data preservation principle; every production audio app follows this.
**Implementation**: Ensure VoiceRecordingService writes audio file to local storage BEFORE passing to STT. Add `audio_file_path` column to sessions table.
**Affected files**: `lib/services/voice_recording_service.dart`, `lib/database/tables.dart`
**Effort**: M | **ADR**: Yes

### E14. Journaling Mode Templates (ADAPT — P2)
**Source**: FlutterVoiceFriend analysis
**What**: Activity-scoped LLM templates with numbered conversation steps per journaling mode (gratitude, dream analysis, mood check-in, free).
**Why**: Structured prompts with numbered steps guide better journaling outcomes than open-ended "you are a journaling assistant."
**Evidence**: FlutterVoiceFriend's deployed "The Friend in Me" app validates this approach for emotional wellness conversations.
**Implementation**: `JournalingMode` enum + `JournalingModeConfig` class, compose with `PersonalityConfig`, store mode on session record.
**Affected files**: `lib/models/journaling_mode.dart` (new), `lib/repositories/agent_repository.dart`, `lib/database/tables.dart`
**Effort**: M | **ADR**: Yes

### E11. [PAUSE] Tag for Conversational Pacing (ADAPT — P1)
**Source**: FlutterVoiceFriend analysis + research synthesis
**What**: Instruct Claude to use `[PAUSE]` after reflective questions. TTS pipeline inserts 2s silence per marker.
**Why**: "What did you feel in that moment?" benefits from silence — time for the user to reflect.
**Implementation**: In `_speakInSentences()`, add branch: if segment is `[PAUSE]`, insert `Future.delayed(Duration(seconds: 2))`.
**Affected files**: `lib/services/voice_session_orchestrator.dart`
**Effort**: S | **ADR**: No

---

## Domain 2: On-Device LLM

### E3. ARM Build Flag Fix — SIGILL Resolution (ADOPT — P0)
**Source**: Cactus analysis (android/CMakeLists.txt line 186)
**What**: Change llamadart's ARM build flag from `-march=armv8.7-a` to `-march=armv8.2-a+dotprod+fp16`.
**Why**: Snapdragon 888 (SM8350) implements ARMv8.2-A with dotprod but NOT ARMv8.7-A. The armv8.7-a flag emits instructions the Cortex-A78 cannot execute.
**Evidence**: Cactus ships on armv8.2-a baseline. llama.cpp GitHub issue #12393 confirms root cause.
**Implementation**: Fork llamadart, modify CMakeLists.txt, rebuild. Or file upstream issue with cactus as evidence.
**Affected files**: llamadart package build config (external)
**Effort**: S | **ADR**: No (build fix, not architecture change)

### E27. Concurrent Local+Cloud Handoff (DEFER — P4)
**Source**: Cactus analysis (concept only, not the implementation)
**What**: When local LLM confidence drops, fire cloud request concurrently. If cloud responds first, use cloud result.
**Why**: Free latency optimization — local generation time gives a window to start cloud request.
**Implementation**: Implement in Dart/Riverpod layer using llamadart's sampling data, not via cactus library.
**Effort**: L | **ADR**: Yes

### E28. CompletionResult Telemetry Fields (ADOPT — P3)
**Source**: Cactus analysis
**What**: Add `prefillTps`, `decodeTps`, `timeToFirstToken`, `confidence` to on-device LLM response type.
**Why**: Makes inference quality observable without separate instrumentation layer.
**Implementation**: Add fields to `AgentResponse` or create `OnDeviceCompletionResult`.
**Affected files**: `lib/models/agent_response.dart`
**Effort**: S | **ADR**: No

---

## Domain 3: STT Engine Upgrades

### E1. Silence Padding in stopListening() (ADOPT — P0)
**Source**: Sherpa ONNX analysis (dart-api-examples/streaming-asr)
**What**: Append `Float32List(8000)` (0.5s silence) before stopping recognizer to flush trailing audio.
**Why**: Without this, the last 32-64ms of audio is dropped when user stops speaking mid-word.
**Evidence**: Dart CLI examples use this pattern; Flutter examples share the gap with our code.
**Implementation**:
```dart
if (_stream != null && _recognizer != null) {
  final tailPadding = Float32List(8000);
  _stream!.acceptWaveform(samples: tailPadding, sampleRate: 16000);
  while (_recognizer!.isReady(_stream!)) { _recognizer!.decode(_stream!); }
}
```
**Affected files**: `lib/services/speech_recognition_service.dart` (stopListening method)
**Effort**: S | **ADR**: No

### E2. Endpoint Rule Tuning (ADOPT — P0)
**Source**: Sherpa ONNX analysis
**What**: Set explicit endpoint rules: `rule1MinTrailingSilence: 2.4`, `rule2MinTrailingSilence: 1.2`.
**Why**: Current code uses library defaults, which may not match natural journaling speech cadence.
**Implementation**: Add 2 named parameters to existing `OnlineRecognizerConfig`.
**Affected files**: `lib/services/speech_recognition_service.dart`
**Effort**: S | **ADR**: No

### E19. Three-Tier STT Architecture (ADAPT — P2)
**Source**: Research synthesis
**What**: Tier 1 (online, quick): speech_to_text. Tier 2 (offline, continuous): Sherpa ONNX with Silero VAD. Tier 3 (optional): Whisper re-transcription in background.
**Why**: Each tier optimized for its scenario — quick notes vs. long sessions vs. accuracy improvement.
**Implementation**: Promote Sherpa ONNX to Tier 2 primary for sessions. Add STT tier selector in VoiceOrchestrator.
**Affected files**: `lib/services/voice_orchestrator.dart`, `lib/services/stt_engine_selector.dart` (new)
**Effort**: L | **ADR**: Yes

### E23. VAD + Offline Recognizer (DEFER — P3)
**Source**: Sherpa ONNX analysis
**What**: Silero VAD segments audio into speech chunks, passes to OfflineRecognizer (SenseVoice int8 ~25MB) for higher accuracy.
**Why**: Saves 40-60% ASR compute during pauses; better accuracy than streaming Zipformer.
**Pending decision**: Do users need partial results during speech, or is post-utterance final text acceptable?
**Effort**: L | **ADR**: Yes

---

## Domain 4: UX Patterns

### E12. Unified Voice-Plus-Text UI (ADAPT — P2)
**Source**: Research synthesis (ChatGPT Nov 2025, Gemini Live, Pi)
**What**: Voice and text in a single scrollable view. Real-time transcription appears as growing text block. AI responses as chat bubbles.
**Why**: Industry convergence — every major voice AI app has adopted this pattern.
**Implementation**: Replace separate recording overlay with inline voice capture in JournalSessionScreen.
**Affected files**: `lib/ui/journal_session_screen.dart`, new `voice_text_unified_widget.dart`
**Effort**: L | **ADR**: Yes

### E13. Conversational Onboarding (ADAPT — P2)
**Source**: Research synthesis (Pi, Rosebud)
**What**: First-run experience is conversational, not a settings wizard. AI greets by voice, asks an easy opener.
**Why**: Radically simple; removes entire onboarding screen stack. Pi proves it works.
**Implementation**: Replace current onboarding with single `ConversationalOnboardingScreen`.
**Affected files**: `lib/ui/onboarding/conversational_onboarding_screen.dart` (new), `lib/main.dart`
**Effort**: M | **ADR**: Yes

### E10. Stop-With-Delay (800ms) on Push-to-Talk (ADOPT — P1)
**Source**: FlutterVoiceFriend analysis
**What**: 800ms delay between user releasing mic button and STT stop call.
**Why**: Users trail off at end of sentences; immediate stop discards last words.
**Implementation**: `Future.delayed` in UI handler before calling `stopPushToTalk()`. Cancel on double-tap.
**Affected files**: `lib/ui/journal_session_screen.dart`
**Effort**: S | **ADR**: No

---

## Domain 5: Android Assistant Integration

### E4. Manifest Fix (ADOPT — P0)
**Source**: Dicio analysis
**What**: Remove `android:foregroundServiceType="microphone"` from `<activity>` element. It belongs on `<service>` only.
**Why**: Configuration error that will cause issues when WakeService is added.
**Affected files**: `android/app/src/main/AndroidManifest.xml`
**Effort**: S

### E5. Intent Deduplication Backoff (ADOPT — P0)
**Source**: Dicio analysis (documents an undocumented Android bug)
**What**: Track `nextAssistAllowed = Instant.now().plusMillis(100)`. Skip duplicate ACTION_ASSIST intents.
**Why**: "During testing Android would send the assist intent twice in a row."
**Affected files**: `android/app/src/main/kotlin/.../MainActivity.kt`
**Effort**: S

### E17. Lock Screen Management (ADOPT — P2)
**Source**: Dicio analysis
**What**: `setShowWhenLocked(true)` + `setTurnScreenOn(true)` on wake-triggered launches. Revert in `onStop()`.
**Constraint**: Audio-only mode on lock screen (no text rendering of journal entries) per security review.
**Affected files**: `android/app/src/main/AndroidManifest.xml`, `MainActivity.kt`
**Effort**: S

### E18. Porcupine Wake Word — "Hey Journal" (ADAPT — P2)
**Source**: Porcupine analysis
**What**: `WakeWordService` wraps `PorcupineManager`, arms after session ends, disarms on trigger.
**Constraints**:
- Custom "Hey Journal" keyword requires training at console.picovoice.ai
- Free tier: 90-day validity, 3-device limit
- AccessKey must NOT enter source control
- 100-150ms microphone release delay between Porcupine stop and STT start
- Foreground-only detection for MVP (background requires native Foreground Service)
**Affected files**: `lib/services/wake_word_service.dart` (new), `pubspec.yaml`
**Effort**: L | **ADR**: Yes (new module + licensing decision)

### E22. Dual Notification Channels (DEFER — P3)
**Source**: Dicio analysis
**What**: `IMPORTANCE_LOW` for persistent wake indicator, `IMPORTANCE_HIGH` for triggered wake.
**Why**: Single HIGH channel for persistent indicator spams the user.
**Implementation**: One-time WakeService setup.
**Effort**: S (bundled with WakeService implementation)

---

## Domain 6: Sync Architecture

### E15. PowerSync + Drift Bridge (ADOPT — P2)
**Source**: PowerSync analysis
**What**: `SqliteAsyncDriftConnection` wraps PowerSync's SQLite database as Drift's backing connection. Drift remains the query layer; PowerSync becomes the transport layer.
**Conditions before adoption**:
1. **Background sync strategy** (blocking): PowerSync's sync isolate dies when app backgrounds. Need `flutter_workmanager` or accept foreground-only sync.
2. **`forTesting()` redesign** (blocking): `AppDatabase.forTesting(NativeDatabase.memory())` won't work for synced tables. Need PowerSync test mode.
3. **`CalendarEvents` as `Table.localOnly()`**: Device-sourced data should NOT sync to Supabase.
**Affected files**: `pubspec.yaml`, `lib/database/app_database.dart`, new `lib/services/powersync_connector.dart`
**Effort**: XL | **ADR**: Yes

### E16. SupabaseConnector with fatalResponseCodes (ADOPT — P2)
**Source**: PowerSync analysis (all 3 specialists converged)
**What**: Classify Postgres error codes (class 22, 23, 42501) as fatal — discard rather than retry.
**Why**: Without this, RLS violations cause infinite retry loops.
**Implementation**: ~100 lines, copy and adapt from PowerSync demo.
**Affected files**: `lib/services/powersync_connector.dart` (new)
**Effort**: S

---

## Domain 7: Architecture Improvements

### E8. ReusableCompleter for Async Safety (ADOPT — P1)
**Source**: LiveKit analysis (all 3 specialists converged)
**What**: Drop-in replacement for raw `Completer<T>` with double-completion guard, reset semantics, and timeout.
**Why**: Our `capturePhotoDescription()` and `confirmCalendarEvent()` have a subscription-replacement race and no double-completion protection.
**Implementation**: Copy `ReusableCompleter` class to `lib/utils/reusable_completer.dart`, refactor 2-3 usages.
**Affected files**: `lib/utils/reusable_completer.dart` (new), `lib/services/voice_session_orchestrator.dart`
**Effort**: S | **ADR**: No

### E9. Typed VoiceSessionError Taxonomy (ADAPT — P1)
**Source**: LiveKit analysis
**What**: Replace `errorMessage: String?` in `VoiceOrchestratorState` with `VoiceSessionError?` carrying `VoiceSessionErrorKind` enum.
**Why**: Makes error handling testable without string matching; enables type-specific recovery affordances.
**Implementation**: `enum VoiceSessionErrorKind { sttFailure, ttsFailure, processingFailure, audioFocusLoss }`
**Affected files**: `lib/services/voice_session_orchestrator.dart`
**Effort**: S | **ADR**: No

---

## Implementation Roadmap

### Sprint N (Immediate — Zero-Risk Fixes)
- [ ] E1: Silence padding in stopListening() (S)
- [ ] E2: Endpoint rule tuning (S)
- [ ] E3: ARM build flag fix for SIGILL (S)
- [ ] E4: Manifest fix — foregroundServiceType (S)
- [ ] E5: Intent deduplication backoff (S)

### Sprint N+1 (Low-Cost, High-Value Patterns)
- [ ] E6: Session history injection (M, ADR)
- [ ] E8: ReusableCompleter (S)
- [ ] E9: Typed VoiceSessionError (S)
- [ ] E10: Stop-with-delay on PTT (S)
- [ ] E11: [PAUSE] tag for pacing (S)

### Sprint N+2 (Medium Architecture Work)
- [ ] E7: Raw audio preservation (M, ADR)
- [ ] E14: Journaling mode templates (M, ADR)
- [ ] E16: SupabaseConnector fatalResponseCodes (S)
- [ ] E17: Lock screen management (S)
- [ ] E28: CompletionResult telemetry fields (S)

### Sprint N+3+ (Large Features — ADR Required)
- [ ] E12: Unified voice-plus-text UI (L, ADR)
- [ ] E13: Conversational onboarding (M, ADR)
- [ ] E15: PowerSync + Drift bridge (XL, ADR)
- [ ] E18: Porcupine wake word (L, ADR)
- [ ] E19: Three-tier STT architecture (L, ADR)

### Deferred (P3-P4)
- E20: DisposableChangeNotifier pattern
- E21: AudioTrackState machine
- E22: Dual notification channels
- E23: VAD + offline recognizer
- E24: Soft gradient voice visualization
- E25: VoiceInteractionService Phase 2-3
- E26: Lock screen + background recording
- E27: Concurrent local+cloud handoff

---

## Legal Notes

| Project | License | Constraint |
|---------|---------|-----------|
| FlutterVoiceFriend | CC BY-NC-SA 4.0 | Ideas only — no code adaptation for commercial use |
| Dicio Android | GPLv3 | Ideas only — no code adaptation |
| Cactus | Custom source-available | AVOID full adoption — $2M ARR limit, auto-termination |
| Porcupine | Apache 2.0 (SDK) | Custom keywords need paid license for distribution |
| Sherpa ONNX | Apache 2.0 | Permissive — code adaptation allowed |
| PowerSync | Apache 2.0 | Permissive — code adaptation allowed |
| LiveKit | Apache 2.0 | Permissive — code adaptation allowed |

---

## Key Architectural Decisions Needed

1. **SIGILL fix path**: Fork llamadart vs. upstream issue vs. alternative runtime (ADR required if forking)
2. **Background sync strategy**: WorkManager vs. foreground-only (blocking for PowerSync adoption)
3. **Partial vs. final STT results**: Determines VAD+offline path (blocking for three-tier STT)
4. **Wake word licensing**: Personal use only vs. distribution (blocking for Porcupine custom keyword)
5. **Lock screen privacy**: Audio-only mode vs. full UI (blocking for lock screen feature)

---

## Cross-Reference: Adoption Log Entries

New entries to add to `memory/lessons/adoption-log.md`:

### Rule of Three Candidates (3+ sightings)
- **Session summarization / cross-session memory**: FlutterVoiceFriend + moodiary + kelivo = 3 sightings -> +2 bonus, fast-track
- **Typed exception hierarchy**: LiveKit + our project + Porcupine = 3 sightings -> already adopted
- **Dual-STT fallback**: FlutterVoiceFriend + research synthesis + our project = 3 sightings -> +2 bonus

### New Sightings for Existing Patterns
- `sync-queue-with-retry` -> +1 (PowerSync)
- `foreground-service-recording` -> +1 (Dicio)
- `platform-channel-bridge` -> +1 (Porcupine)

---

*This document consolidates findings from 7 new project analyses, 8 research synthesis patterns, and 5 prior project analyses (omi, lumma, kelivo, moodiary, syncable). All patterns scored on the standard 5-dimension rubric (prevalence, elegance, evidence, fit, maintenance) out of 25.*
