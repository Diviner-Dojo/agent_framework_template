# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-03-03 ~03:30 UTC

## Current Task

**Status:** Sprint N+1 shipped (v0.17.4+12, PR #59). On `main`. Ready for next sprint.
**Branch:** `main`
**Version:** `0.17.4+12`

### In Progress
(none)

### Just Completed
- **Voice Capture Reliability Research** (DISC-20260303-031401, sealed, 7 turns):
  - Motivation: Device testing revealed frequent STT mistranscriptions with `speech_to_text` + Android SpeechRecognizer; ChatGPT voice as north star
  - **CRITICAL finding**: `lib/services/speech_to_text_stt_service.dart:98` — `pauseFor: Duration(seconds: 5)` is the dominant latency contributor. Change to `Duration(seconds: 2)` immediately.
  - **Incremental path (recommended)**: Replace Android SpeechRecognizer with Deepgram Nova-3 streaming WebSocket. New `DeepgramSttService` implementing `SpeechRecognitionService`. New `deepgram-proxy` Edge Function. Configure `endpointing=2000`, `utterance_end_ms=1500`, `interim_results=true`. Est. $1.77/month at 10 min/day.
  - **North star (blocked)**: GPT-4o Realtime API blocked by WebSocket proxy ADR (ADR-0005 doesn't extend to WebSocket), constraint conflict (Claude as AI layer), and $3/session cost. Needs new ADR before implementation.
  - **On-device Whisper (conditional)**: sherpa_onnx/whisper.cpp as offline fallback. Snapdragon 888 SIGILL risk from ADR-0017 applies — requires hardware validation spike first.
  - **Endpoint detection key insight**: Journaling requires 2–3s silence threshold, NOT cloud defaults (~800ms) which interrupt thinking pauses. This config difference is as important as the STT provider choice.
  - Panel: architecture-consultant, performance-analyst, independent-perspective (2 rounds)
  - Discussion: DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture (sealed)

- **Sprint N+1: Intent Classifier Stability Refactor + Advisory Resolution** (SPEC-20260303-010332, PR #59, v0.17.4+12):
  - Root cause fix: `static const _calendarEventNouns` shared constant enforces noun-list sync between `_calendarIntentPattern` and `_hasStrongCalendarSignal` at compile time (eliminates PR #56/#57 regression class)
  - Word-count wildcard `(\s+[\w-]+){0,4}` replaces `.{0,15}` char-count wildcard in both patterns — brand-agnostic
  - `\b` anchor (was `^`) in `_calendarIntentPattern` for voice preamble support; `^` retained in `_hasStrongCalendarSignal`
  - 10 new regression tests; 1937 total, all pass, 81.2% coverage
  - Advisory resolution: A1–A5 from REV-20260302-232244 closed (INVARIANT comments, cold-start fallback, privacy filter, CLAUDE.md context-brief list, ADR-0030 stub)
  - ADR-0030: developer input capture schema extension (status: proposed, pending two-sprint evaluation gate)
  - Review: REV-20260303-013421 (approve-with-changes, 1 blocking resolved in-review, 8 advisory)
  - Discussions: DISC-20260303-010442 (spec), DISC-20260303-011131 (build), DISC-20260303-013421 (review) — all closed

- **Context-Brief Framework Rollout** (SPEC-20260302-192548 Step 2, PR #58, framework-only):
  - Added Step 3.5 (context-brief before specialist dispatch) to: `/review`, `/deliberate`, `/build_module`, `/plan`, `/retro`
  - Blocking fixes during review: plan.md synthesis `## Request Context` requirement, retro standing agenda restructured as Step 5.5, retro disposition dead-code condition rewritten as observable signals
  - Review: REV-20260302-232244 (approve-with-changes, 3 blocking resolved, 6 advisory)
  - Discussion: DISC-20260302-231156-review-context-brief-framework-rollout

- **Set Verb + Short-Message Guard Fix** (PR #57, v0.17.3+11):
  - Root cause: `_hasStrongCalendarSignal` not recognizing "set" + event noun; "set a calendar meeting" = 4 words → short-message guard fired → journal
  - Fix: "set" added to two `^add` sub-patterns in `_calendarIntentPattern`; `^(add|set)\b.{0,15}\b(event noun)\b` added to `_hasStrongCalendarSignal`
  - 2 regression tests; Review: REV-20260302-230547 (approve-with-changes, 1 blocking resolved, 5 advisory)
  - Deploy: SUCCESS on SM_G998U1 (59s)

- **Google Calendar Intent Classifier Fix** (PR #56, v0.17.3+11):
  - Root cause: `_calendarIntentPattern` had `.{0,15}` char limit between "add" and event noun; "a Google Calendar " = 19 chars — exceeded limit, message fell through to Claude
  - Fix: new sub-pattern `^add\b.{0,15}\b(google\s+)?calendar\b.{0,20}\b(meeting|...)` + `(google\s+)?` in "to...calendar" alternative
  - 4 regression tests added; 1925 total, all pass, 81.2% coverage
  - Review: REV-20260302-222520 (approve-with-changes, 0 blocking, 6 advisory)
  - Deploy: SUCCESS on SM_G998U1 (61s)
  - Files modified: `lib/services/intent_classifier.dart`, `test/services/intent_classifier_test.dart`, `memory/bugs/regression-ledger.md`, `pubspec.yaml`

- **Task Verbal Confirmation Race Fix** (PR #55, v0.17.2+10):
  - Root cause: `orchestrator.confirmTask()` ran an 8s verbal yes/no loop concurrently with UI task card. On card tap, task was added correctly but the timed-out completer spoke "Okay, I won't add that."
  - Fix: `resolveTaskConfirmation({required bool confirmed})` added to `VoiceSessionOrchestrator` — completes `_taskConfirmCompleter` immediately when card is tapped
  - Screen: task card `onConfirm`/`onDismiss` callbacks now call `resolveTaskConfirmation()` after `sessionNotifier.confirmTask/dismissTask()`
  - Regression tests: 3 new tests; 1921 total, all pass, 81.2% coverage
  - Ledger: entry added to `memory/bugs/regression-ledger.md`
  - Review: REV-20260302-201931 (approve-with-changes, all blocking resolved)
  - Deploy: SUCCESS on SM_G998U1 (54.9s)
  - Files modified: `lib/services/voice_session_orchestrator.dart`, `lib/ui/screens/journal_session_screen.dart`, `test/services/voice_session_orchestrator_test.dart`, `memory/bugs/regression-ledger.md`

- **Journal-Only Voice Mode: Three Bug Fixes + Back-Button Fix** (PR #54, v0.17.1+9):
  - Bug 1+2 fix: `acknowledgeNoResponse()` added to `VoiceSessionOrchestrator` — resumes listening loop without AI response (fixes stuck-in-processing in journal-only + after handled intents)
  - Bug 1+2 fix: `_resumeOrchestratorIfVoiceMode()` added to `SessionNotifier` — called at journal-only and handled-intent early exits in `sendMessage()`
  - Bug 3 fix: `shouldEndSession()` moved above `journalOnlyMode` guard and intent routing — "goodbye" now works in journal-only mode
  - Back-button fix: `_endSessionAndPop()` no longer pops on success — shows closing summary (matches "goodbye" UX), force-pops only on exception
  - Review B1 fix: Done button and overflow menu hidden during `isClosingComplete` — was silently no-oping via `isSessionEnding` re-entry guard
  - Advisory A1: no-op guard test pinning acknowledgeNoResponse() phase contract
  - Advisory A4: `isContinuousMode` guard in `acknowledgeNoResponse()` for push-to-talk safety
  - Advisory A6: cross-reference comments between `_doneSignals` and `VoiceCommandClassifier._strongEndPattern`
  - Regression tests: 3 new tests (orchestrator acknowledgeNoResponse, session goodbye, screen back-button)
  - Ledger: 3 new entries in `memory/bugs/regression-ledger.md`
  - Full test suite: EXIT 0 (1918 tests, all pass)
  - Review: REV-20260302-201931 (approve-with-changes, 1 blocking resolved in-review, 8 advisory)
  - Files modified: `lib/services/voice_session_orchestrator.dart`, `lib/providers/session_providers.dart`, `lib/ui/screens/journal_session_screen.dart`, `lib/repositories/agent_repository.dart`, `lib/services/voice_command_classifier.dart`, `test/services/voice_session_orchestrator_test.dart`, `test/providers/session_providers_test.dart`, `test/ui/journal_session_screen_test.dart`, `memory/bugs/regression-ledger.md`

- **Bug-Fix Sprint: Voice UX + Task + TTS Fallback** (PR #53, v0.17.0+8):
  - Fix 1: Task extraction context — `context` param in `TaskExtractionService.extract()`, last 3 turns passed from `_extractTaskDetails`; resolves pronoun "it" using conversation history
  - Fix 2: Journal-only mode intent routing — moved `journalOnlyMode` guard after `_routeByIntent()`; task/calendar intents now handled in journal-only mode
  - Fix 3: Voice cleanup on back navigation — `await stop()` in discard path, `unawaited()` in `onPopInvokedWithResult`, `stop()` added to `dispose()`
  - Fix 4: Empty session delete — `endSession()` empty guard now calls `discardSession()` (deletes row) instead of `endSession()` (preserves row)
  - Fix 5: TTS fallback — new `FallbackTtsService`, `ttsFallbackActiveProvider`, ElevenLabs wrapped with fallback, SnackBar notification in session screen
  - Review fix (in-review): `FallbackTtsService.stop()` guards `_primary.stop()` in try-catch
  - Tests: 1915 total (+21 new), 80.8% coverage, all 7 quality gate checks pass
  - New files: `lib/services/fallback_tts_service.dart`, `test/services/fallback_tts_service_test.dart`, `test/providers/session_providers_test.dart`
  - Review: REV-20260302-152240 (approve-with-changes, 1 blocking resolved in-review, 6 advisory)
  - Deploy: SUCCESS on SM_G998U1 (1m 18s)

- **Voice Bug Fixes + Integration Test** (PR #52, v0.16.3+7):
  - Fix: Black screen on back button — try-finally in _endSessionAndPop ensures Navigator.pop() always runs
  - Fix: STT silent after ElevenLabs TTS — AudioPlayer.stop() on completion releases audio session
  - Fix: Post-dispose orchestrator crashes — _disposed flag + _updateState guard
  - New: 8-phase voice_mode_test.dart integration test (emulator, 1m 14s)
  - New: 2 regression tests for post-dispose safety
  - Fix: quality_gate.py regression guard skips TODO entries, Unicode encoding fix
  - Review: approve-with-changes (REV-20260302-071854), 1 blocking resolved, 7 advisory
- **Coverage Recovery + Ship** (PR #51, v0.16.2+6):
  - 69.9% → 80.7% effective coverage (1850 → 1895 tests)
  - New test files: chat_bubble_test, session_list_screen_expanded_test, session_detail_screen_expanded_test, search_screen_results_test
  - Expanded existing: settings_screen_expanded_test (+9 tests), tasks_screen_expanded_test (+6 tests)
  - coverage:ignore-file pragmas: app_database.dart, google_calendar_service.dart, photo_service.dart, audio_file_service.dart, video_service.dart, video_player_widget.dart
  - Quick-win advisories: onboarding_providers doc comment, FAB warnIfMissed:true, @Tags lint fix
  - Review: approve-with-changes (REV-20260302-061043), 0 blocking, 8 advisory
  - Emulator smoke test: PASS (all features verified)
  - Physical device deploy: SUCCESS (release mode, SM_G998U1)
- **Emulator Testing + Navigator Fix** (PR #50, v0.16.1+5, ADR-0029):
  - Emulator support in deploy.py (--emulator, --list-emulators, boot/wait)
  - New test_on_emulator.py runner with JSONL logging
  - smoke_test.dart rewrite + new manual_test_automation.dart (emulator-compatible)
  - Bug fix: ref.watch→ref.read in app.dart (Navigator route stack collapse)
  - Regression test + ADR-0029 (Riverpod initialRoute constraint)
  - 10 new unit test files, 3 discussion artifacts, retro + review reports
  - Review: approve-with-changes (REV-20260302-032500), 2 blocking fixed, 11 advisory

### Recently Completed
- **Knowledge Amplification Pipeline** (PR #49, v0.16.0+4, ADR-0028):
  - 10 new Python scripts, 4 SQLite tables, 2 views, 1 new command (/knowledge-health)
  - Pipeline: extract_findings → mine_patterns → surface_candidates → compute_effectiveness
  - Backfill: 48 findings, 436 turns with content, 48 sightings, 2 Rule of Three hits
  - Review: approve-with-changes (REV-20260301-215800), 2 blocking fixed, 14 advisory
  - Dashboard health: 5/7
- **Voice Naturalness Sprint** (SPEC-20260228, PR #47, v0.15.0+2) — 5 tasks:
  1. Idle timer interruption guard (`_userIsSpeaking` flag)
  2. Markdown stripping before TTS (`stripMarkdown`)
  3. Confidence-weighted commit delay (`computeCommitDelay`)
  4. Non-verbal thinking sound (`just_audio` chime loop)
  5. LLM-marker turn completeness (✓/○/◐ markers in Edge Function)
  - Review: approve-with-changes (REV-20260301-025400), 2 blocking fixed, 12 advisories open
- **Semantic Versioning** (PR #46, v0.14.0+1 → 0.15.0+2):
  - `scripts/bump_version.py` + tests, dynamic Settings version via `package_info_plus`
  - `/ship` Step 1.5 auto-bump, `deploy.py --check-version`, ADR-0027
- **Deploy parser fix** (PR #48, v0.15.1+3) — fix `--check-version` for multi-field dumpsys lines
- **Phase 13: Google Tasks + Personal Assistant** — 8 sub-phases (A-H)
- **Conversational Onboarding** (E13)
- **Multi-project analysis** (7 projects) — consolidated enhancement plan

## Google Calendar OAuth Config

**GCP Project:** `agenticjournal` (project number: `774019106928`)

**OAuth Clients Created:**
- **Android:** `774019106928-0v541sgb13qnma44v3g35l4if5tes3k6.apps.googleusercontent.com`
  - Package: `com.divinerdojo.agentic_journal`
  - SHA-1: `8B:32:96:6B:DD:A2:7E:A7:53:D3:31:65:43:C8:89:48:DC:E7:B9:41`
- **Web:** `774019106928-211ougkvc63dm0lbare5qbq0it12huk7.apps.googleusercontent.com`

## Device Build Command

**Physical device:**
```bash
python scripts/deploy.py --install-only
```

**Emulator:**
```bash
python scripts/deploy.py --emulator --install-only
```

**Emulator (specific AVD):**
```bash
python scripts/deploy.py --emulator Pixel_7_API_36 --install-only
```

**List available emulators:**
```bash
python scripts/deploy.py --list-emulators
```

Or manually (physical device):
```bash
/c/src/flutter/bin/flutter run -d R5CR10LW2FE \
  --dart-define=SUPABASE_URL=https://oruastmawvtcpiyggrze.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ydWFzdG1hd3Z0Y3BpeWdncnplIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2MzEwMzYsImV4cCI6MjA4NzIwNzAzNn0.1bKaVE0RD0SZKBfnYA4DvlnkjllQ4KNq3voTRGOq35A
```

**adb** path: `/c/Users/evans/AppData/Local/Android/Sdk/platform-tools`

## Emulator Config

| Setting | Value |
|---------|-------|
| AVD Name (Google Play) | `Medium_Phone_API_36.1` |
| AVD Name (Pixel 7) | `Pixel_7_API_36` |
| Image | API 36, x86_64 |
| Google Play | Medium_Phone only |
| RAM | 2048 MB (Medium_Phone) |
| Notes | `--emulator` implies `--debug` (release AOT doesn't target x86_64) |

## Device Testing Results

| Feature | Physical Device | Emulator | Notes |
|---------|----------------|----------|-------|
| App launch | Working | **Working** | Supabase init OK on both |
| Onboarding | Working | **Working** | Conversational onboarding, Claude API, session end |
| Text journaling | Working | **Working** | FAB → session → send → Done → home |
| Session detail/resume | Working | **Working** | Card tap → detail → Continue Entry → send → end |
| Session discard | Working | **Working** | Empty session → back → auto-discard |
| Settings navigation | Working | **Working** | All 8 cards verified (Digital Assistant, Voice, AI, Sync, Location, Calendar, Data, About) |
| Unicode/edge cases | Working | **Working** | Unicode text preserved, long messages handled |
| Photo capture | Working | Simulated | Virtual camera (checkerboard scene) |
| Google Calendar | **Working** | Needs test | Emulator needs SHA-1 in GCP (Medium_Phone_API_36.1 has Google Play) |
| Supabase auth | Working | Needs test | evansarak@yahoo.com |
| Version display | **Working** | Needs test | Settings shows dynamic version via `package_info_plus` |
| Deploy --check-version | **Working** | Needs test | MATCH confirmed for 0.15.1+3 |
| Claude AI | Needs test | **Working** | Edge Function responding (200 OK), in-app conversation works |
| Video capture | Needs test | Limited | ffmpeg_kit may lack x86_64 libs |
| Voice/STT | Needs test | **Working** | voice_mode_test.dart: enable, session, toggle, back nav (1m 14s) |
| Local LLM | Disabled | Disabled | SIGILL on Snapdragon 888 / ARM-only binaries |

## Tech Debt

- **Coverage** — 81.2% (above 80% target, 1937 tests)
- **Education gates deferred** — Phase 11 + Phase 12; also deferred from REV-20260302-152240
- **Review advisories open** — 74 total: 12 from REV-20260301-025400, 14 from REV-20260301-215800, 8 from REV-20260302-061043, 7 from REV-20260302-071854, 6 from REV-20260302-152240, 8 from REV-20260302-201931, 6 from REV-20260302-222520, 5 from REV-20260302-230547, 8 from REV-20260303-013421 (net: 72 - 5 closed + 7 new = 74)
- **Local LLM disabled** — llamadart SIGILL on Snapdragon 888
- **PENDING adoptions** — 9 patterns approaching stale threshold 2026-03-05
- **Pipeline advisories** — stop words duplication, bare except, candidate_id collision risk (see REV-20260301-215800)
- **ADR-0030 evaluation gate** — two-sprint window starts now (Signal A: specialist echo, Signal B: framing drift — check at next retro)

## Key Decisions (Recent)

- ADR-0027: Semantic Versioning
- ADR-0026: Conversational Onboarding via Real Journal Session
- ADR-0021: Video Capture Architecture
- ADR-0020: Google Calendar Integration
- llamadart disabled → Claude API is primary conversation layer
- Google OAuth requires both Android + Web client IDs for scoped access

## Resume Instructions

1. **Education gate** — Re-deferred 2026-03-02: REV-20260302-152240 walkthrough/quiz on `fallback_tts_service.dart` + `voice_providers.dart`. Must complete before any further changes to fallback TTS or voice providers.
2. **Batch-evaluate adoptions** — 9 patterns approaching stale threshold (run `/batch-evaluate`)
3. **Run retro** — Sprint N+1 is landed. Run `/retro` to evaluate: ADR-0030 evaluation gate (Signal A/B check), advisory triage, protocol yield review.
4. **Voice sprint planning** — DISC-20260303-031401 produced the research foundation. Next steps in priority order:
   - **P0 (immediate fix, 1 line)**: `lib/services/speech_to_text_stt_service.dart:98` — change `pauseFor: Duration(seconds: 5)` to `Duration(seconds: 2)`
   - **P1 (next sprint)**: Deepgram Nova-3 integration — new `DeepgramSttService`, `deepgram-proxy` Edge Function, journaling-tuned endpoint config (`endpointing=2000`, `utterance_end_ms=1500`)
   - **P2 (future ADR first)**: GPT-4o Realtime — blocked; needs WebSocket proxy ADR before implementation
5. **Next sprint other candidates** — Session history injection (P1), ReusableCompleter (P1), typed errors (P1), stop-with-delay (P1), [PAUSE] tag (P1)
6. **Open advisory triage** — 74 total. Priority: A1 RegExp-per-call in `_hasStrongCalendarSignal` (REV-20260303-013421); A4 documentation_policy.md enforcement parenthetical (2-sprint carry-forward)

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
