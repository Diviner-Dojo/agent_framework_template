---
analysis_id: "ANALYSIS-20260226-162548-sherpa-onnx"
discussion_id: "DISC-20260226-162548-analyze-sherpa-onnx"
target_project: "https://github.com/k2-fsa/sherpa-onnx"
target_language: "Dart (Flutter), C++, Python"
target_stars: ~4000
agents_consulted: [project-analyst, architecture-consultant, performance-analyst, qa-specialist]
patterns_evaluated: 6
patterns_recommended: 2
patterns_deferred: 2
analysis_date: "2026-02-26"
license: "Apache 2.0"
license_constraint: "Permissive — code adaptation allowed"
scope: "flutter-examples/, dart-api-examples/, Flutter plugin code (not full C++ engine)"
---

## Project Profile

- **Name**: Sherpa ONNX
- **Source**: https://github.com/k2-fsa/sherpa-onnx
- **Tech Stack**: C++ core, Dart/Flutter bindings, ONNX Runtime, Silero VAD
- **Domain**: On-device speech recognition and voice activity detection
- **Maturity**: Production-grade, 4000+ stars, active development, comprehensive model zoo

## Synthesis

6 patterns identified. ADOPT: silence padding (`Float32List(8000)` before stop), endpoint rule tuning (rule1: 2.4s, rule2: 1.2s). DEFER: VAD+offline recognizer (pending product decision on partials UX), model factory pattern (for future model selection).

Key finding: our `stopListening()` drops trailing audio — silence padding is a 4-line fix with high impact.

## Pattern Recommendations

### ADOPT

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| Silence padding in stopListening() | 24/25 | E1 | P0 |
| Endpoint rule tuning | 22/25 | E2 | P0 |

**Silence Padding**: Append `Float32List(8000)` (0.5s silence at 16kHz) before stopping recognizer to flush trailing audio. Without this, the last 32-64ms of audio is dropped when user stops speaking mid-word. Found in dart-api-examples (streaming-asr); Flutter examples share the same gap as our code.

```dart
if (_stream != null && _recognizer != null) {
  final tailPadding = Float32List(8000);
  _stream!.acceptWaveform(samples: tailPadding, sampleRate: 16000);
  while (_recognizer!.isReady(_stream!)) { _recognizer!.decode(_stream!); }
}
```

**Endpoint Rule Tuning**: Set explicit endpoint rules: `rule1MinTrailingSilence: 2.4`, `rule2MinTrailingSilence: 1.2`. Current code uses library defaults, which may not match natural journaling speech cadence (longer pauses during reflection).

### DEFER

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| VAD + offline recognizer | 18/25 | E23 | P3 |
| Model factory pattern | 17/25 | — | — |

**VAD + Offline Recognizer**: Silero VAD segments audio into speech chunks, passes to OfflineRecognizer (SenseVoice int8 ~25MB) for higher accuracy. Saves 40-60% ASR compute during pauses. Pending decision: do users need partial results during speech, or is post-utterance final text acceptable?

**Model Factory Pattern**: Generic model loading with size/accuracy/speed selection. Deferred until multiple models are needed.

## License Impact

Apache 2.0 — Permissive. Code patterns and implementation approaches can be directly adapted.

## Adoption Log Entries

All entries logged to `memory/lessons/adoption-log.md` with `Source: sherpa-onnx`.

---

*See also: `docs/consolidated-enhancement-plan.md` for full implementation details and roadmap.*
