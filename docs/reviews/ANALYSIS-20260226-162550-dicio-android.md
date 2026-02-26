---
analysis_id: "ANALYSIS-20260226-162550-dicio-android"
discussion_id: "DISC-20260226-162550-analyze-dicio-android"
target_project: "https://github.com/Stypox/dicio-android"
target_language: "Kotlin (Android)"
target_stars: ~1500
agents_consulted: [project-analyst, architecture-consultant, security-specialist, ux-evaluator]
patterns_evaluated: 9
patterns_recommended: 3
patterns_deferred: 2
patterns_avoided: 2
analysis_date: "2026-02-26"
license: "GPLv3"
license_constraint: "Ideas only — no code adaptation"
---

## Project Profile

- **Name**: Dicio Android
- **Source**: https://github.com/Stypox/dicio-android
- **Tech Stack**: Kotlin, Android, Vosk STT, native Android assistant APIs
- **Domain**: Open-source voice assistant for Android
- **Maturity**: Active, 1500+ stars, community-maintained

## Synthesis

9 patterns identified. Critical reframe: Dicio does NOT use VoiceInteractionService — uses WakeService (foreground service + AudioRecord loop). ADOPT: manifest fix (`foregroundServiceType` on activity is wrong), intent deduplication, lock screen management. DEFER: dual notification channels, WakeService patterns (for when wake word is implemented).

Found manifest bug in OUR project.

## Pattern Recommendations

### ADOPT

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Manifest fix (foregroundServiceType) | N/A | E4 | P0 |
| Intent deduplication backoff | N/A | E5 | P0 |
| Lock screen management | 20/25 | E17 | P2 |

**Manifest Fix**: Remove `android:foregroundServiceType="microphone"` from `<activity>` element in our AndroidManifest.xml. It belongs on `<service>` only. This is a configuration error that will cause issues when WakeService is added. Discovered by analyzing Dicio's manifest structure.

**Intent Deduplication**: Track `nextAssistAllowed = Instant.now().plusMillis(100)`. Skip duplicate ACTION_ASSIST intents. Documents an undocumented Android bug: "During testing Android would send the assist intent twice in a row."

**Lock Screen Management**: `setShowWhenLocked(true)` + `setTurnScreenOn(true)` on wake-triggered launches. Revert in `onStop()`. Security constraint: audio-only mode on lock screen (no text rendering of journal entries).

### DEFER

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Dual notification channels | 18/25 | E22 | P3 |
| WakeService foreground pattern | 18/25 | — | — |

**Dual Notification Channels**: `IMPORTANCE_LOW` for persistent wake indicator, `IMPORTANCE_HIGH` for triggered wake. Single HIGH channel for persistent indicator spams the user. Bundled with future WakeService implementation.

### AVOID

- **RecognitionService**: Wrong problem for journaling app (command/response, not continuous transcription)
- **VoiceInteractionService**: Dicio doesn't even use it — proves it's not viable for third-party apps

### Critical Reframe

The analysis revealed that **VoiceInteractionService is not viable for third-party assistant apps**. Dicio, the most mature open-source Android voice assistant, deliberately chose a foreground service with AudioRecord loop instead. This validates the WakeService approach for wake word detection (Porcupine) over VoiceInteractionService for our project.

## License Impact

GPLv3 — Ideas and patterns only. No code can be copied or adapted. All implementations must be written from scratch. The manifest bug fix and intent deduplication pattern are generic Android knowledge, not derived code.

## Adoption Log Entries

All entries logged to `memory/lessons/adoption-log.md` with `Source: dicio`.

---

*See also: `docs/consolidated-enhancement-plan.md` for full implementation details and roadmap.*
