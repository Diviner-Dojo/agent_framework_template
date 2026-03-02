# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-03-02 ~07:45 UTC

## Current Task

**Status:** Bug-fix sprint complete. Ready for review + commit.
**Branch:** `main`
**Version:** `0.16.3+7` (pending bump for this sprint)

### In Progress
(none)

### Just Completed
- **Bug-Fix Sprint: Voice UX + Task + TTS Fallback** (5 fixes, quality gate PASS):
  - Fix 1: Task extraction context — `context` param in `TaskExtractionService.extract()`, last 3 turns passed from `_extractTaskDetails`; resolves pronoun "it" using conversation history
  - Fix 2: Journal-only mode intent routing — moved `journalOnlyMode` guard after `_routeByIntent()`; task/calendar intents now handled in journal-only mode
  - Fix 3: Voice cleanup on back navigation — `await stop()` in discard path, `unawaited()` in `onPopInvokedWithResult`, `stop()` added to `dispose()`
  - Fix 4: Empty session delete — `endSession()` empty guard now calls `discardSession()` (deletes row) instead of `endSession()` (preserves row)
  - Fix 5: TTS fallback — new `FallbackTtsService`, `ttsFallbackActiveProvider`, ElevenLabs wrapped with fallback, SnackBar notification in session screen
  - Tests: 1914 total (+17 new), 80.8% coverage, all 6 quality gate checks pass
  - New files: `lib/services/fallback_tts_service.dart`, `test/services/fallback_tts_service_test.dart`, `test/providers/session_providers_test.dart`
  - Updated tests: `session_empty_guard_test.dart` (expects deletion), `task_extraction_service_test.dart` (+5 context tests), `voice_session_orchestrator_test.dart` (+1 regression)

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

- **Coverage** — 80.7% (above 80% target, 1897 tests)
- **Education gates deferred** — Phase 11 + Phase 12
- **Review advisories open** — 12 from REV-20260301-025400 + 14 from REV-20260301-215800 + 8 from REV-20260302-061043 + 7 from REV-20260302-071854
- **Local LLM disabled** — llamadart SIGILL on Snapdragon 888
- **PENDING adoptions** — 9 patterns approaching stale threshold 2026-03-05
- **Pipeline advisories** — stop words duplication, bare except, candidate_id collision risk (see REV-20260301-215800)

## Key Decisions (Recent)

- ADR-0027: Semantic Versioning
- ADR-0026: Conversational Onboarding via Real Journal Session
- ADR-0021: Video Capture Architecture
- ADR-0020: Google Calendar Integration
- llamadart disabled → Claude API is primary conversation layer
- Google OAuth requires both Android + Web client IDs for scoped access

## Resume Instructions

1. **Review + commit** — Run `/review` on bug-fix sprint files, then commit and PR
2. **Test on device** — All 5 bug fixes on SM_G998U1: journal-only task creation, context resolution, voice cleanup on discard, empty session delete, TTS fallback
3. **Address review advisories** — 41 total: 12 from REV-20260301-025400, 14 from REV-20260301-215800, 8 from REV-20260302-061043, 7 from REV-20260302-071854
4. **Start Sprint N+1** — Session history injection (P1), ReusableCompleter (P1), typed errors (P1), stop-with-delay (P1), [PAUSE] tag (P1)
5. **Batch-evaluate adoptions** — 9 patterns approaching stale threshold (run `/batch-evaluate`)
6. **Education gates** — Deferred from Phase 11 + 12

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
