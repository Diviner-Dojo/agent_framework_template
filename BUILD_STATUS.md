# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-02-26 ~23:10 UTC

## Current Task

**Status:** E13 Conversational Onboarding built and reviewed. Ready to commit.
**Branch:** `main`

### In Progress
- **Device testing** — P0 STT changes (silence padding, endpoint tuning) need on-device verification
- **Model switching** — User reports rule-based fallback triggers too often. Need to prevent silent fallback to Layer A.
- **Assistant gesture** — Long-press home not opening new chat. User needs to set app as default assistant in Android Settings.

### Recently Completed
- **E13 Conversational Onboarding** — Replaces static wizard with conversational first session. Build: DISC-20260226-224410. Review: REV-20260226-230621 (approve-with-changes, 0 blocking, 13 advisory). ADR-0026.
- **Sprint N+2 (E7, E14, E16, E17, E28)** — Merged via PR #39.
- **Sprint N+1 (E6, E8, E9, E10, E11)** — Merged via PR #38.
- **P0 Quick Wins (E1-E5)** — Merged via PR #37. Silence padding, endpoint tuning, manifest fix, intent dedup, test fixes. Build: DISC-20260226-185523. Review: REV-20260226-191743 (approve-with-changes, 0 blocking, 8 advisory).
- **Multi-project analysis (7 projects)** — FlutterVoiceFriend, LiveKit, Sherpa ONNX, Cactus, PowerSync, Dicio, Porcupine.
- **Consolidated enhancement plan** — `docs/consolidated-enhancement-plan.md` with 28 enhancements across 7 domains, prioritized P0-P4.
- **ADR-0022: Voice Engine Swap** — ElevenLabs TTS (via Supabase proxy) + speech_to_text STT.

## Multi-Project Analysis Summary (2026-02-26)

### Deliverables
| Artifact | Path |
|----------|------|
| Consolidated enhancement plan | `docs/consolidated-enhancement-plan.md` |
| Adoption log (updated) | `memory/lessons/adoption-log.md` |
| Analysis reports (7) | `docs/reviews/ANALYSIS-20260226-*` |
| Discussions (8, all sealed) | `discussions/2026-02-26/DISC-*` |

### P0 Quick Wins — SHIPPED (PR #37, commit 85735d8)
1. ~~**Silence padding** in stopListening()~~ — DONE
2. ~~**Endpoint rule tuning** — rule1: 2.4s, rule2: 1.2s~~ — DONE
3. **ARM build flag fix** — `-march=armv8.2-a+dotprod+fp16` resolves SIGILL on Snapdragon 888 — DEFERRED (requires llamadart fork)
4. ~~**Manifest fix** — remove `foregroundServiceType` from `<activity>`~~ — DONE
5. ~~**Intent deduplication** — 100ms backoff for duplicate ACTION_ASSIST~~ — DONE

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
| Voice/STT | Needs test | Silence padding + endpoint tuning shipped, needs on-device verify |
| Local LLM | Disabled | SIGILL on Snapdragon 888 (fix path identified: ARM build flag) |

## Tech Debt

- **Coverage** — 77.2% (below 80% target)
- **Education gates deferred** — Phase 11 + Phase 12
- **Local LLM disabled** — llamadart SIGILL on Snapdragon 888 (fix: `-march=armv8.2-a+dotprod+fp16`)
- **Supabase credentials** — user reported invalid, may need fresh key from Dashboard
- **Path documentation mismatch** — ADR-0018/0021 say relative, actual values are absolute
- **PENDING adoptions** — 9 patterns approaching stale threshold 2026-03-05 + ~30 new patterns added

## Key Decisions (Recent)

- ADR-0026: Conversational Onboarding via Real Journal Session
- ADR-0021: Video Capture Architecture
- ADR-0020: Google Calendar Integration
- FFmpegKit retired → `ffmpeg_kit_min_gpl` fork (drop-in)
- llamadart disabled → Claude API is primary conversation layer
- Google OAuth requires both Android + Web client IDs for scoped access
- VoiceInteractionService NOT viable → foreground service + AudioRecord is correct path

## Resume Instructions

1. **Rebuild and deploy** — P0 changes + `google-services.json` update need deployment to device
2. **Verify P0 on device** — Test STT silence padding (say a word and stop immediately — should capture it)
3. **Test remaining features** — Claude AI, video, voice (see testing table above)
4. **Start Sprint N+1** — Session history injection (P1), ReusableCompleter (P1), typed errors (P1), stop-with-delay (P1), [PAUSE] tag (P1)
5. **Address review advisories** — JWT test assertions, Kotlin test coverage, bounded flush loop (REV-20260226-191743)
6. **Education gates + coverage recovery** — After device features verified

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
