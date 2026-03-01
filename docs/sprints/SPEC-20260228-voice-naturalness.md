---
spec_id: SPEC-20260228-voice-naturalness
title: "Voice Naturalness Improvements — Research-Driven Sprint"
status: draft
risk_level: low
research_sources:
  - pipecat-ai/pipecat (10.5k stars, BSD-2)
  - livekit/agents (9.5k stars, Apache-2.0)
adoption_patterns:
  - Idle Timer Interruption Guard (pipecat, 22/25)
  - LLM-Marker Turn Completeness (pipecat, 20/25)
  - Confidence-Weighted Commit Delay (livekit, 20/25)
  - Thinking Sound Mixer (livekit, 18/25)
---

## Goal

Make voice interactions feel as natural as ChatGPT's Advanced Voice Mode by addressing four specific gaps identified through analysis of `pipecat-ai/pipecat` and `livekit/agents` — the two industry-leading real-time voice AI pipeline frameworks.

## Context

The app already has a sophisticated voice pipeline: ElevenLabs "Sarah" TTS, Google on-device STT, sentence-splitting for reduced perceived latency, [PAUSE] marker support, 15s silence timeout, and manual interrupt. The analysis of pipecat and livekit identified four gaps that account for most of the remaining "robotic feel":

1. **Silence timer race condition**: The 15s silence timer starts when TTS ends, but if the user immediately starts speaking after an interrupt, the timer runs concurrently with their speech. It's only cancelled on `isFinal` — a window exists where it could fire mid-utterance.
2. **AI jumps in at conversational pauses**: When the user says "So I was thinking, um—" and hits a natural pause, Google STT fires `isFinal`. The Claude request fires immediately. This is the biggest source of feeling interrupted.
3. **Verbal "Still thinking..." is intrusive**: It costs an ElevenLabs API call, fills the user's cognitive space with words while they're formulating their next thought, and blocks STT restart during playback.
4. **Low-confidence transcripts commit too fast**: If Google STT is uncertain, we still fire the Claude request immediately. A short delay on low-confidence results gives the user time to correct or continue.

## Why ChatGPT Sounds More Natural

ChatGPT Advanced Voice Mode uses GPT-4o's native audio tokens (end-to-end, no STT/TTS pipeline). We cannot replicate that architecture. But pipecat and livekit show that **the LLM itself can participate in turn management** — not just generate responses. That single design insight closes most of the gap.

## Requirements

### Task 1: Idle Timer Interruption Guard (XS — bug fix)
**Pattern source**: pipecat `user_idle_controller.py` lines 107-135

- R1: Cancel `_silenceTimer` on the first interim STT result (`recognizedWords.isNotEmpty`), not just on `isFinal`
- R2: Add `_userIsSpeaking` boolean flag to `VoiceSessionOrchestrator` that gates silence timer start
- R3: Set `_userIsSpeaking = true` on first interim result, `false` on `isFinal` or STT stop
- No new dependencies. One-line change with a guard boolean.

**Files**: `lib/services/voice_session_orchestrator.dart`

---

### Task 2: Markdown Stripping Before TTS (XS — quality fix)
**Pattern source**: livekit `filter_markdown` transform

- R4: Before passing LLM response text to `_speak()`, strip markdown formatting characters: `**bold**` → `bold`, `*italic*` → `italic`, `# Header` → `Header`, bullet `- item` → `item`
- R5: Use a simple Dart `String.replaceAll()` chain or `RegExp` — no new package needed
- R6: Verify by testing a Claude response that includes a bulleted list or bold text

**Files**: `lib/services/voice_session_orchestrator.dart` (where `_speak()` is called with the LLM response)

---

### Task 3: Confidence-Weighted Commit Delay (S)
**Pattern source**: livekit `audio_recognition.py` lines 109-120, 543-600

- R7: Add `_computeCommitDelay(double confidence) → Duration` to `VoiceSessionOrchestrator`:
  - `confidence >= 0.85` → `Duration.zero` (fire immediately)
  - `confidence >= 0.65` → `Duration(milliseconds: 400)`
  - `confidence < 0.65` → `Duration(milliseconds: 1200)`
- R8: On `isFinal`, start a `Timer(_computeCommitDelay(confidence), () => _commitUserTurn(text))` instead of committing immediately
- R9: Cancel the pending commit timer if a new interim or final result arrives
- R10: If `confidence == 0.0` (Google STT sometimes returns 0.0 for system TTS or noise), treat as `< 0.65`
- R11: Add a unit test: `commitDelay(0.9) == Duration.zero`, `commitDelay(0.7) == 400ms`, `commitDelay(0.5) == 1200ms`

**Files**: `lib/services/voice_session_orchestrator.dart`, `test/services/voice_session_orchestrator_test.dart`

---

### Task 4: Non-Verbal Thinking Sound (S)
**Pattern source**: livekit `background_audio.py` lines 29-41, 68-103, 316-329

- R12: Source or create a subtle thinking audio asset (soft keyboard tapping, gentle chime, or soft background hum). Must be: royalty-free, under 3 seconds, loopable. Suggested search: freesound.org CC0 license. Save to `assets/audio/thinking_chime.mp3`.
- R13: Register asset in `pubspec.yaml` under `flutter.assets`
- R14: Add `_thinkingPlayer` (`AudioPlayer?`) field to `VoiceSessionOrchestrator`
- R15: Add `_startThinkingSound()`: creates `AudioPlayer`, sets asset, sets `LoopMode.one`, sets volume to 0.4, starts playing
- R16: Add `_stopThinkingSound()`: stops + disposes `_thinkingPlayer`, sets to null
- R17: Call `_startThinkingSound()` when entering `VoiceLoopPhase.processing`
- R18: Call `_stopThinkingSound()` when entering `VoiceLoopPhase.speaking` or `VoiceLoopPhase.error`
- R19: **Remove** the `_llmThinking` timer that speaks `VoiceRecoveryMessages.llmThinking` via ElevenLabs. Replace with the audio cue.
- R20: `just_audio` is already a dependency — no new package needed

**Files**: `lib/services/voice_session_orchestrator.dart`, `lib/constants/voice_recovery_messages.dart` (remove `llmThinking` constant if no longer used), `assets/audio/thinking_chime.mp3`, `pubspec.yaml`

---

### Task 5: LLM-Marker Turn Completeness ✓/○/◐ (M)
**Pattern source**: pipecat `user_turn_completion_mixin.py` lines 32-143, 343-428

This is the highest-impact pattern. Claude is instructed (via system prompt) to prefix every response with a turn-completeness marker:
- `✓` = user's turn was complete → respond normally
- `○` = user was cut off / incomplete (grammatically and conversationally) → suppress response, wait 5s, re-prompt gently ("Go ahead, I didn't want to interrupt you.")
- `◐` = user is deliberating (grammatically complete but conversationally open) → suppress response, wait 10s, check in ("Take your time — I'm here when you're ready.")

Critical distinction: *"That's a great question."* is grammatically complete but conversationally `◐` — the user hasn't answered or continued yet.

- R21: Add marker parsing to `VoiceSessionOrchestrator._onLlmResponse()`:
  ```dart
  const _complete = '✓';
  const _incompleteShort = '○';
  const _incompleteLong = '◐';
  ```
- R22: Strip the marker from the response string before any TTS call
- R23: On `○` (incomplete short): do NOT call TTS. Start a `Timer(Duration(seconds: 5), () => _promptUserToContinue(brief: true))`. Cancel on next STT interim result.
- R24: On `◐` (incomplete long): do NOT call TTS. Start a `Timer(Duration(seconds: 10), () => _promptUserToContinue(brief: false))`. Cancel on next STT interim result.
- R25: `_promptUserToContinue(brief)`:
  - `brief: true` → speak `"Go ahead, I didn't want to interrupt."` (brief, ElevenLabs)
  - `brief: false` → speak `"Take your time — I'm here when you're ready."` (patient, ElevenLabs)
- R26: If user speaks during the timer window, cancel the timer and resume normally
- R27: Add system prompt instructions to the Edge Function (`supabase/functions/claude-chat/index.ts`). Adapt the pipecat prompt verbatim — it distinguishes grammatical vs conversational completeness clearly.
- R28: Graceful fallback: if response starts with any character other than ✓/○/◐, treat as `✓` (respond normally). Claude may occasionally not follow the instruction.
- R29: Add unit tests for marker parsing and strip logic

**Files**:
- `lib/services/voice_session_orchestrator.dart`
- `supabase/functions/claude-chat/index.ts`
- `lib/constants/voice_recovery_messages.dart` (add new re-prompt messages)
- `test/services/voice_session_orchestrator_test.dart`

---

### Task 6: Update Adoption Log
- R30: Add all 4 new patterns to `memory/lessons/adoption-log.md` with source repos, scores, and implementation status

---

## Patterns Explicitly Deferred

| Pattern | Reason |
|---------|--------|
| False interruption detection + auto-resume | Only needed with VAD-based barge-in; our current tap model doesn't have false positives |
| ONNX turn-detection ML model | Server-side only; mobile impractical (20-60MB, NDK complexity, battery) |
| Preemptive speculative LLM generation | Requires streaming Claude API first |
| ElevenLabs WebSocket streaming TTS | Would help latency, but significant architectural change; sentence-splitting already covers most of the gap |

## Non-Functional Requirements

- No new packages (use `just_audio` already present)
- Must not change the visible state machine API (consumers of `VoiceOrchestratorState` must be unaffected)
- All changes covered by existing or new unit tests
- Quality gate must pass: `python scripts/quality_gate.py`

## Verification

After implementing each task:

1. **Task 1 (timer guard)**: Interrupt mid-TTS → speak immediately → verify 15s timer does NOT fire during speech (add temporary log)
2. **Task 2 (markdown)**: Ask Claude for a bulleted list → verify ElevenLabs speaks clean prose, not "asterisk" or "dash"
3. **Task 3 (confidence delay)**: Mumble quietly → verify there is a brief pause before Claude responds (vs. immediate)
4. **Task 4 (thinking sound)**: Ask a complex question → verify the subtle audio plays during processing, not "Still thinking..."
5. **Task 5 (LLM marker)**: Say "So I was thinking..." and stop mid-sentence → verify AI waits 5s and prompts gently rather than jumping in
6. **All**: `flutter test`, `python scripts/quality_gate.py`

## Estimated Effort Summary

| Task | Effort | Risk |
|------|--------|------|
| 1. Idle timer guard | XS (0.5d) | Very low |
| 2. Markdown stripping | XS (0.5d) | Very low |
| 3. Confidence-weighted delay | S (1d) | Low |
| 4. Thinking sound | S (1d + asset sourcing) | Low |
| 5. LLM-marker turn completeness | M (2-3d) | Low-Medium (depends on Claude following system prompt) |
| **Total** | **~5-6 days** | **Low** |
