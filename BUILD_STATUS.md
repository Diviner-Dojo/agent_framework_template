# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-02-25 ~22:15 UTC

## Current Task

**Status:** Voice engine swap (ADR-0022) deployed and working. Fixing STT reliability + model switching.
**Branch:** `main`

### In Progress
- **STT reliability** — Fixed `error_speech_timeout` auto-restart + audio focus fight between just_audio and speech_to_text. Rebuilt and deployed.
- **Model switching** — User reports rule-based fallback triggers too often. Need to prevent silent fallback to Layer A.
- **Assistant gesture** — Long-press home not opening new chat. User needs to set app as default assistant in Android Settings.

### Recently Completed
- **ADR-0022: Voice Engine Swap** — ElevenLabs TTS (via Supabase proxy) + speech_to_text STT. Old engines kept as offline fallbacks.
- **Custom prompt bug fix** — `onFieldSubmitted` → `onChanged` in settings_screen.dart.
- **elevenlabs-proxy Edge Function** — Deployed to Supabase, ELEVENLABS_API_KEY set as secret.
- **Network security config** — Cleartext HTTP for localhost (just_audio internal server).
- **Build fixes committed** — PR #35, merged.
- **Device deployment** — App built and running on Galaxy S21 Ultra (Android 15, Snapdragon 888).

## Google Calendar OAuth Config (In Progress)

**GCP Project:** `agenticjournal` (project number: `774019106928`)

**OAuth Clients Created:**
- **Android:** `774019106928-0v541sgb13qnma44v3g35l4if5tes3k6.apps.googleusercontent.com`
  - Package: `com.divinerdojo.agentic_journal`
  - SHA-1: `8B:32:96:6B:DD:A2:7E:A7:53:D3:31:65:43:C8:89:48:DC:E7:B9:41`
- **Web:** `774019106928-211ougkvc63dm0lbare5qbq0it12huk7.apps.googleusercontent.com`

**Status:** `google-services.json` updated with both client IDs (client_type 1 = Web, client_type 3 = Android). NOT YET REBUILT — needs `flutter run` to deploy the updated config to device.

**Previous errors:**
- First attempt used a Desktop (`installed`) client type instead of Android — caused `ApiException: 10` (DEVELOPER_ERROR)
- Fixed by creating proper Android + Web Application client IDs

**Next step:** Rebuild and deploy, then test Settings > Calendar > Connect Google Calendar.

## Uncommitted Changes

- `android/app/google-services.json` — updated with real GCP OAuth client IDs (was placeholder, now has both Android + Web clients)

Other build fixes (ffmpeg swap, LLM disable) already committed in PR #35.

## Device Build Command

```bash
/c/src/flutter/bin/flutter run -d R5CR10LW2FE \
  --dart-define=SUPABASE_URL=https://oruastmawvtcpiyggrze.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ydWFzdG1hd3Z0Y3BpeWdncnplIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2MzEwMzYsImV4cCI6MjA4NzIwNzAzNn0.1bKaVE0RD0SZKBfnYA4DvlnkjllQ4KNq3voTRGOq35A
```

## Device Testing Results

| Feature | Status | Notes |
|---------|--------|-------|
| App launch | Working | No crash, Supabase init OK |
| Photo capture | Working | Camera + gallery confirmed |
| Google Calendar | **Working** | OAuth connected via Firebase + GCP test user |
| Supabase auth | Working | New account (evansarak@yahoo.com), new publishable key (sb_publishable_...) |
| Claude AI | Needs test | Edge Function deployed + verified via curl, untested in-app |
| Video capture | Needs test | ffmpeg fork compiles, untested on device |
| Voice/STT | Needs test | Model download on first use |
| Local LLM | Disabled | SIGILL on Snapdragon 888 |

## Tech Debt

- **Coverage** — 77.2% (below 80% target)
- **Education gates deferred** — Phase 11 + Phase 12
- **Local LLM disabled** — llamadart SIGILL on Snapdragon 888
- **Supabase credentials** — user reported invalid, may need fresh key from Dashboard
- **Path documentation mismatch** — ADR-0018/0021 say relative, actual values are absolute
- **PENDING adoptions** — 9 patterns approaching stale threshold 2026-03-05

## Key Decisions (Recent)

- ADR-0021: Video Capture Architecture
- ADR-0020: Google Calendar Integration
- FFmpegKit retired → `ffmpeg_kit_min_gpl` fork (drop-in)
- llamadart disabled → Claude API is primary conversation layer
- Google OAuth requires both Android + Web client IDs for scoped access

## Resume Instructions

1. **Rebuild and deploy** — `google-services.json` is updated but not yet deployed to device. Run the build command above.
2. **Test Google Calendar** — Settings > Calendar > Connect Google Calendar. Should show Google consent screen now.
3. **Test Supabase auth** — If still failing, check Dashboard for fresh anon key.
4. **Test remaining features** — Claude AI, video, voice (see testing table above).
5. **Commit google-services.json update** — After confirming Google Sign-In works.
6. **Education gates + coverage recovery** — After device features verified.

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
