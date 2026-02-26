---
analysis_id: "ANALYSIS-20260226-162547-flutter-voice-friend"
discussion_id: "DISC-20260226-162547-analyze-flutter-voice-friend"
target_project: "https://github.com/jbpassot/flutter_voice_friend"
target_language: "Dart (Flutter)"
target_stars: ~50
agents_consulted: [project-analyst, architecture-consultant, qa-specialist, ux-evaluator]
patterns_evaluated: 6
patterns_recommended: 3
patterns_adapted: 3
patterns_avoided: 2
analysis_date: "2026-02-26"
license: "CC BY-NC-SA 4.0"
license_constraint: "Ideas only — no code adaptation for commercial use"
---

## Project Profile

- **Name**: FlutterVoiceFriend ("The Friend in Me")
- **Source**: https://github.com/jbpassot/flutter_voice_friend
- **Tech Stack**: Flutter/Dart, Langchain, speech_to_text, flutter_tts, Google/Anthropic LLMs
- **Domain**: Voice conversation loop for emotional wellness
- **Maturity**: Published app with activity-based conversation system

## Synthesis

6 patterns identified. ADOPT: session history injection, stop-with-delay, error cascade gate. ADAPT: journaling mode templates, multi-chain summarization, [PAUSE] tag. AVOID: boolean-flag state machine, API keys in .env.

Key finding: activity-scoped templates + session history injection for cross-session memory.

## Pattern Recommendations

### ADOPT

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Session history injection | 22/25 | E6 | P1 |
| Stop-with-delay (800ms) on PTT | 20/25 | E10 | P1 |
| Error cascade gate | 20/25 | — | — |

**Session History Injection**: Query last 3-5 session summaries from drift, inject into Claude system prompt. Enables continuity ("Last time you mentioned..."). Our `JournalSessions.summary` column already exists for this. **Rule of Three triggered** (also seen in kelivo + moodiary).

**Stop-with-Delay**: 800ms delay between user releasing mic button and STT stop call. Users trail off at end of sentences; immediate stop discards last words.

### ADAPT

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Journaling mode templates | 22/25 | E14 | P2 |
| [PAUSE] tag for pacing | 20/25 | E11 | P1 |
| Multi-chain summarization | 19/25 | — | P3 |

**Journaling Mode Templates**: Activity-scoped LLM templates with numbered conversation steps per mode (gratitude, dream analysis, mood check-in, free). Structured prompts guide better outcomes than open-ended instructions.

**[PAUSE] Tag**: Instruct Claude to use `[PAUSE]` after reflective questions. TTS pipeline inserts 2s silence per marker for user reflection time.

### AVOID

- **Boolean-flag state machine**: Our `VoiceLoopPhase` enum is strictly superior
- **API keys in .env asset**: Violates ADR-0005 (proxy through Supabase Edge Functions)

## License Impact

CC BY-NC-SA 4.0 — Ideas and patterns only. No code can be copied or adapted for commercial use. All implementations must be written from scratch using only the conceptual patterns documented here.

## Adoption Log Entries

All entries logged to `memory/lessons/adoption-log.md` with `Source: flutter_voice_friend`.

---

*See also: `docs/consolidated-enhancement-plan.md` for full implementation details and roadmap.*
