# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-02-26 ~17:30 UTC

## Current Task

**Status:** Multi-project analysis complete. 7 external projects analyzed, consolidated enhancement plan produced.
**Branch:** `main`

### In Progress
- **STT reliability** — Fixed `error_speech_timeout` auto-restart + audio focus fight between just_audio and speech_to_text. Rebuilt and deployed.
- **Model switching** — User reports rule-based fallback triggers too often. Need to prevent silent fallback to Layer A.
- **Assistant gesture** — Long-press home not opening new chat. User needs to set app as default assistant in Android Settings.

### Recently Completed
- **Multi-project analysis (7 projects)** — FlutterVoiceFriend, LiveKit, Sherpa ONNX, Cactus, PowerSync, Dicio, Porcupine. All discussions sealed, analysis reports written, adoption log updated.
- **Consolidated enhancement plan** — `docs/consolidated-enhancement-plan.md` with 28 enhancements across 7 domains, prioritized P0-P4.
- **Research synthesis** — 8 cross-project patterns scored and captured in discussion DISC-20260226-162806-research-synthesis-voice-journal-uplift.
- **Adoption log update** — ~30 new pattern entries in `memory/lessons/adoption-log.md`. Total analyses: 15, patterns evaluated: 103.
- **ADR-0022: Voice Engine Swap** — ElevenLabs TTS (via Supabase proxy) + speech_to_text STT.

## Multi-Project Analysis Summary (2026-02-26)

### Deliverables
| Artifact | Path |
|----------|------|
| Consolidated enhancement plan | `docs/consolidated-enhancement-plan.md` |
| Adoption log (updated) | `memory/lessons/adoption-log.md` |
| Analysis reports (7) | `docs/reviews/ANALYSIS-20260226-*` |
| Discussions (8, all sealed) | `discussions/2026-02-26/DISC-*` |

### P0 Quick Wins (Zero-Risk Fixes)
1. **Silence padding** in stopListening() — 4-line fix, prevents dropped trailing audio
2. **Endpoint rule tuning** — rule1: 2.4s, rule2: 1.2s for journaling cadence
3. **ARM build flag fix** — `-march=armv8.2-a+dotprod+fp16` resolves SIGILL on Snapdragon 888
4. **Manifest fix** — remove `foregroundServiceType` from `<activity>` element
5. **Intent deduplication** — 100ms backoff for duplicate ACTION_ASSIST

### Key Findings
- **SIGILL root cause confirmed**: llamadart uses armv8.7-a, Snapdragon 888 only supports armv8.2-a
- **VoiceInteractionService not viable** for third-party apps (Dicio proves foreground service + AudioRecord is correct)
- **Rule of Three triggered**: Session history injection (3 sightings: FlutterVoiceFriend + kelivo + moodiary)
- **PowerSync + Drift bridge** viable but has 2 blocking conditions (background sync, forTesting redesign)

## Google Calendar OAuth Config (In Progress)

**GCP Project:** `agenticjournal` (project number: `774019106928`)

**OAuth Clients Created:**
- **Android:** `774019106928-0v541sgb13qnma44v3g35l4if5tes3k6.apps.googleusercontent.com`
  - Package: `com.divinerdojo.agentic_journal`
  - SHA-1: `8B:32:96:6B:DD:A2:7E:A7:53:D3:31:65:43:C8:89:48:DC:E7:B9:41`
- **Web:** `774019106928-211ougkvc63dm0lbare5qbq0it12huk7.apps.googleusercontent.com`

**Status:** `google-services.json` updated with both client IDs (client_type 1 = Web, client_type 3 = Android). NOT YET REBUILT — needs `flutter run` to deploy the updated config to device.

## Uncommitted Changes

- `android/app/google-services.json` — updated with real GCP OAuth client IDs
- `docs/consolidated-enhancement-plan.md` — NEW: 28-enhancement consolidated plan
- `docs/reviews/ANALYSIS-20260226-*` — NEW: 7 individual analysis reports
- `memory/lessons/adoption-log.md` — UPDATED: ~30 new pattern entries
- Various discussion files under `discussions/2026-02-26/`

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
| Local LLM | Disabled | SIGILL on Snapdragon 888 (fix path identified: ARM build flag) |

## Tech Debt

- **Coverage** — 77.2% (below 80% target)
- **Education gates deferred** — Phase 11 + Phase 12
- **Local LLM disabled** — llamadart SIGILL on Snapdragon 888 (fix: `-march=armv8.2-a+dotprod+fp16`)
- **Supabase credentials** — user reported invalid, may need fresh key from Dashboard
- **Path documentation mismatch** — ADR-0018/0021 say relative, actual values are absolute
- **PENDING adoptions** — 9 patterns approaching stale threshold 2026-03-05 + ~30 new patterns added

## Key Decisions (Recent)

- ADR-0021: Video Capture Architecture
- ADR-0020: Google Calendar Integration
- FFmpegKit retired → `ffmpeg_kit_min_gpl` fork (drop-in)
- llamadart disabled → Claude API is primary conversation layer
- Google OAuth requires both Android + Web client IDs for scoped access
- VoiceInteractionService NOT viable → foreground service + AudioRecord is correct path

## Resume Instructions

1. **Implement P0 quick wins** — 5 zero-risk fixes from consolidated enhancement plan (silence padding, endpoint tuning, ARM flag, manifest fix, intent dedup)
2. **Rebuild and deploy** — `google-services.json` is updated but not yet deployed to device
3. **Test remaining features** — Claude AI, video, voice (see testing table above)
4. **Commit google-services.json update** — After confirming Google Sign-In works
5. **Start Sprint N+1** — Session history injection (P1), ReusableCompleter (P1), typed errors (P1)
6. **Education gates + coverage recovery** — After device features verified

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
