# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-02-25 ~23:00 UTC

## Current Task

**Status:** Device activation — app running on Galaxy S21 Ultra. Build fixes need commit.
**Branch:** `main`

### In Progress
- **Commit build fixes** — ffmpeg package swap, google-services.json placeholder, LLM disable (3 code + 3 auto-gen files)

### Recently Completed
- **Device deployment** — App successfully built and running on Galaxy S21 Ultra (Android 15, Snapdragon 888). Supabase + Claude API working end-to-end.
- **Supabase backend setup** — Edge Function deployed, secrets configured (ANTHROPIC_API_KEY, PROXY_ACCESS_KEY). Claude proxy verified working.
- **Device-testing fixes** — PR #33, merged. REV-20260225-210000.md (0 blocking, 17 advisory).
- **Phase 12: Video Capture** — PR #29, merged (ADR-0021)
- **Phase 11: Google Calendar + Reminders** — PR #28, merged (ADR-0020)

## Uncommitted Build Fixes

These files were modified to get the app building and running on device:
- `pubspec.yaml` — `ffmpeg_kit_flutter_min_gpl` → `ffmpeg_kit_min_gpl` (original package retired, Maven artifacts removed)
- `lib/services/video_service.dart` — updated imports for ffmpeg fork
- `android/app/google-services.json` — NEW placeholder file (Google Services Gradle plugin requires it)
- `lib/providers/llm_providers.dart` — disabled LLM auto-load (SIGILL crash on Snapdragon 888)
- `lib/ui/screens/settings_screen.dart` — disabled manual LLM load
- `pubspec.lock`, `macos/Flutter/GeneratedPluginRegistrant.swift` — auto-generated

## Supabase Credentials (for device builds)

```bash
/c/src/flutter/bin/flutter run -d R5CR10LW2FE \
  --dart-define=SUPABASE_URL=https://oruastmawvtcpiyggrze.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ydWFzdG1hd3Z0Y3BpeWdncnplIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2MzEwMzYsImV4cCI6MjA4NzIwNzAzNn0.1bKaVE0RD0SZKBfnYA4DvlnkjllQ4KNq3voTRGOq35A
```

## Tech Debt

- **Coverage** — 77.2% (below 80% target). Phases 11+12 add platform-dependent code that requires device mocks.
- **Education gates deferred** — Phase 11 + Phase 12. Two consecutive deferrals = Principle 6 violation.
- **Local LLM disabled** — llamadart's libllama.so uses i8mm/SVE instructions unsupported on Snapdragon 888. TODO(local-llm): Re-enable when baseline arm64-v8a build ships.
- **Google Calendar not configured** — Placeholder google-services.json. Needs GCP OAuth setup + real credentials.
- **Path documentation mismatch** — ADR-0018 and ADR-0021 document localPath as relative, but stored values are absolute.
- **PENDING adoptions** — 9 patterns from 2026-02-19, approaching 14-day stale threshold on 2026-03-05.

## Open Discussions

- None

## Key Decisions (Recent)

- ADR-0021: Video Capture Architecture
- ADR-0020: Google Calendar Integration
- FFmpegKit retired → switched to `ffmpeg_kit_min_gpl` fork (drop-in replacement)
- llamadart disabled on device due to SIGILL — Claude API is primary conversation layer

## Blockers

- None

## Resume Instructions

App is running on Galaxy S21 Ultra. Next actions:
1. Commit build fixes (this session)
2. Test features on device (Claude AI, auth, sync, photos)
3. Google Calendar setup (GCP Console OAuth + real google-services.json)
4. Education gates + coverage recovery

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
