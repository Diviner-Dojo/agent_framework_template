# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-03-02 ~01:35 UTC

## Current Task

**Status:** Emulator integration tests PASSING.
**Branch:** `main`
**Version:** `0.16.0+4`

### In Progress
- None

### Just Completed
- **Emulator integration tests** — Both `smoke_test.dart` and `manual_test_automation.dart` passing on `Medium_Phone_API_36.1` (emulator-5554)
  - smoke_test: ~1m 16s, manual_test: ~1m 25s
  - Key fix: navigate to settings immediately after onboarding (don't pump on home while Claude API closing summary is in flight)
  - `goHome()` helper updated to check FAB + title (not just title through stacked routes)

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
| Voice/STT | Needs test | Needs test | Voice naturalness shipped, needs on-device verify |
| Local LLM | Disabled | Disabled | SIGILL on Snapdragon 888 / ARM-only binaries |

## Tech Debt

- **Coverage** — 69.9% (below 80% target)
- **Education gates deferred** — Phase 11 + Phase 12
- **Review advisories open** — 12 from REV-20260301-025400 + 14 from REV-20260301-215800
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

1. **Test on device** — Voice naturalness (markdown stripping, turn-taking), Claude AI, video
2. **Coverage recovery** — Write tests for Phase 13 code (task_dao, task_extraction_service, tasks_screen, etc.)
3. **Address review advisories** — 12 non-blocking from voice naturalness review (REV-20260301-025400)
4. **Start Sprint N+1** — Session history injection (P1), ReusableCompleter (P1), typed errors (P1), stop-with-delay (P1), [PAUSE] tag (P1)
5. **Batch-evaluate adoptions** — 9 patterns approaching stale threshold (run `/batch-evaluate`)
6. **Education gates** — Deferred from Phase 11 + 12

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
