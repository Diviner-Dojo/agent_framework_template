---
analysis_id: "ANALYSIS-20260226-162551-porcupine"
discussion_id: "DISC-20260226-162551-analyze-porcupine"
target_project: "https://github.com/Picovoice/porcupine"
target_language: "Dart (Flutter), Java, Swift, C"
target_stars: ~3500
agents_consulted: [project-analyst, architecture-consultant, performance-analyst, security-specialist]
patterns_evaluated: 6
patterns_recommended: 2
patterns_adapted: 2
patterns_deferred: 1
analysis_date: "2026-02-26"
license: "Apache 2.0 (SDK)"
license_constraint: "Custom keywords require paid license for distribution beyond free tier"
---

## Project Profile

- **Name**: Porcupine (Picovoice)
- **Source**: https://github.com/Picovoice/porcupine
- **Tech Stack**: C core engine, Flutter/Dart SDK (`porcupine_flutter`), `flutter_voice_processor`
- **Domain**: On-device wake word detection
- **Maturity**: Production SDK, 3500+ stars, actively maintained by Picovoice

## Synthesis

6 patterns identified. ADOPT: two-tier API (PorcupineManager inside WakeWordService), typed exception taxonomy, integration test pattern (WAV frame feeding). ADAPT: lifecycle cleanup (wire into existing orchestrator). DEFER: background detection (native Foreground Service, high cost).

Key constraints: custom "Hey Journal" keyword has 90-day trial limit and needs licensing decision.

## Pattern Recommendations

### ADOPT

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Two-tier API (PorcupineManager + Porcupine) | 20/25 | E18 | P2 |
| Typed exception hierarchy | 20/25 | — | — |

**Two-Tier API**: `PorcupineManager` wraps `Porcupine` (low-level) with audio pipeline management. Our `WakeWordService` should wrap `PorcupineManager`, not `Porcupine` directly. This provides:
- Automatic audio capture via `flutter_voice_processor`
- Frame buffering and sample rate conversion
- Clean start/stop lifecycle

Implementation: `WakeWordService` arms after session ends, disarms on trigger. 100-150ms microphone release delay between Porcupine stop and STT start.

**Typed Exception Hierarchy**: `PorcupineException` base with `PorcupineMemoryException`, `PorcupineIOException`, `PorcupineInvalidArgumentException`, etc. Maps well to our existing error handling patterns. Rule of Three triggered (also seen in LiveKit + our project).

### ADAPT

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Asset extraction pattern | 19/25 | — | — |
| Lifecycle management | 19/25 | — | — |

**Asset Extraction**: Extract `.ppn` keyword files from Flutter assets to temp directory for native engine. Standard pattern for bridging Flutter assets to native code.

**Lifecycle Management**: Wire Porcupine start/stop into existing VoiceOrchestrator lifecycle. Must coordinate with STT and TTS for microphone exclusivity.

### DEFER

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Background wake word detection | 16/25 | — | P4 |

**Background Detection**: Requires native Android Foreground Service running Porcupine engine continuously. High battery cost, complex lifecycle. Foreground-only detection for MVP.

## Licensing Constraints

Critical decisions needed before adoption:
- **Custom "Hey Journal" keyword**: Requires training at console.picovoice.ai
- **Free tier limits**: 90-day keyword validity, 3-device limit
- **AccessKey**: Must NOT enter source control (flutter_secure_storage)
- **Distribution**: Personal use OK on free tier; App Store distribution requires paid plan
- **Built-in keywords**: "Hey Google", "Alexa", etc. available without custom training

## License Impact

Apache 2.0 (SDK code) — Permissive for the SDK itself. Custom keyword files (`.ppn`) are tied to Picovoice licensing. The two-tier API pattern and exception hierarchy are generic architectural knowledge.

## Adoption Log Entries

All entries logged to `memory/lessons/adoption-log.md` with `Source: porcupine`.

---

*See also: `docs/consolidated-enhancement-plan.md` for full implementation details and roadmap.*
