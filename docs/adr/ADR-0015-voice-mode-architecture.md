---
adr_id: ADR-0015
title: "Voice Mode Architecture — Push-to-Talk Foundation"
status: accepted
date: 2026-02-23
decision_makers: [facilitator, architecture-consultant]
discussion_id: null
supersedes: null
risk_level: medium
confidence: 0.85
tags: [voice, stt, tts, sherpa-onnx, audio, phase-7a]
---

## Context

The developer's vision is a voice-first journaling companion used while walking, commuting, or driving. Phase 7A lays the native library foundation and delivers a usable push-to-talk experience. Phase 7B will add continuous voice mode.

A P3 native library validation spike on the target device (Galaxy S21 Ultra, 6GB RAM) confirmed all critical libraries work:

| Library | Result | Key Metrics |
|---------|--------|-------------|
| sherpa_onnx (Zipformer STT) | PASS | 5-8s load, ~215MB RSS, real-time streaming |
| record (PCM microphone) | PASS | 16kHz mono PCM16 feeds sherpa_onnx correctly |
| flutter_tts | PASS | Speaks clearly, completion callback in ~4s |
| Coexistence (STT + LLM) | PASS | 1.95GB combined RSS, no OOM |

## Decision

### 1. STT Engine: Zipformer-transducer via sherpa_onnx OnlineRecognizer

Use `sherpa_onnx` with the streaming Zipformer-transducer model, NOT Whisper. Whisper is batch-only (requires complete audio before transcription), making it unsuitable for real-time streaming where users need to see words appear as they speak. The Zipformer-transducer supports true streaming: audio chunks are fed incrementally and partial results are available immediately.

**Critical**: `sherpa_onnx.initBindings()` must be called before any recognizer creation. Without this call, all recognition silently returns empty strings. This was discovered during spike validation.

### 2. Audio Capture: `record` package (separate from sherpa_onnx)

sherpa_onnx does not handle microphone input — it only processes audio samples. The `record` package captures PCM16 audio from the microphone and streams it as byte chunks. We convert these to Float32 samples (`int16 / 32768.0`) before feeding to sherpa_onnx.

Using `record` ^6.2.0 (spike-validated), not ^5.1.3 from the original spec. The 6.x API is confirmed working.

### 3. Polling Wrapper: StreamController<SpeechResult>

sherpa_onnx is pull-based — callers must check `isReady()` and call `decode()` explicitly. We wrap this in a `StreamController<SpeechResult>` that polls the recognizer after each audio chunk arrives, emitting partial and final results as a Dart stream. This hides the pull-based API behind a reactive interface that integrates naturally with Flutter's widget system.

### 4. Endpoint Detection: Built-in isEndpoint()

`OnlineRecognizer.isEndpoint()` detects when the speaker has finished an utterance (pause detection). This is sufficient for push-to-talk — no separate VAD (Voice Activity Detection) is needed. When an endpoint is detected, we emit a `SpeechResult(isFinal: true)` and reset the recognizer stream for the next utterance.

### 5. TTS: flutter_tts with System Engine

Use `flutter_tts` which delegates to the Android system TTS engine (fully offline, no model download needed). The assistant's response is spoken aloud after it arrives, with a completion callback to track speaking state.

### 6. Push-to-Talk First (Phase 7A)

Phase 7A uses tap-to-toggle push-to-talk (not hold-to-talk, for accessibility). The user taps the mic button to start recording, sees real-time transcription in the text field, and taps stop (or endpoint detection fires) to finish. The transcribed text stays in the text field for review before sending.

Phase 7B will add continuous voice mode with always-on listening.

### 7. Audio Focus: Platform Channel to Android AudioManager

Audio focus management via a `MethodChannel` to Android's `AudioManager`:
- `requestAudioFocus()` before starting STT
- `abandonAudioFocus()` when stopping
- Handle `AUDIOFOCUS_LOSS` (pause STT), `AUDIOFOCUS_GAIN` (resume), `AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK` (reduce TTS volume)

This follows the existing platform channel pattern established by `AssistantRegistrationService`.

### 8. Model Storage: getApplicationSupportDirectory()

Zipformer model files (~71MB total) are stored in `getApplicationSupportDirectory()/zipformer/`, which is app-private storage confirmed by the spike. This directory is not backed up, not visible to file managers, and is cleaned up on app uninstall.

### 9. Model Download: Lazy with WiFi Gate

Model download is lazy — triggered on first voice activation, not at app install. For downloads >20MB (the encoder is ~68MB), a WiFi-only gate warns users on cellular connections. Downloads include:
- SHA-256 checksum verification after download
- Progress reporting via StreamController<double>
- Resume capability via HTTP Range headers
- Four files: encoder (~68MB), decoder (~2MB), joiner (~254KB), tokens (~5KB)

### 10. Error Recovery: Graceful Degradation

On microphone permission denial or model unavailability, the app degrades gracefully to text-only mode. The voice toggle in settings shows model download status, and the mic button only appears when the model is ready and permission is granted.

### 11. Service Abstraction

Both STT and TTS use abstract class + concrete implementation pattern:
- `SpeechRecognitionService` (abstract) → `SherpaOnnxSpeechRecognitionService`
- `TextToSpeechService` (abstract) → `FlutterTextToSpeechService`

This enables mock implementations for testing (sherpa_onnx and flutter_tts cannot run in CI).

## Alternatives Considered

### Alternative 1: Whisper for STT
- **Pros**: Higher accuracy for long-form transcription, widely known
- **Cons**: Batch-only — requires complete audio before transcription, no real-time partial results
- **Reason rejected**: Confirmed batch-only in P3 spike. Push-to-talk requires streaming for responsive UX.

### Alternative 2: Google Speech-to-Text (cloud)
- **Pros**: High accuracy, no model download
- **Cons**: Requires internet, violates offline-first principle (ADR-0004), ongoing API cost
- **Reason rejected**: Core value proposition is offline-first journaling.

### Alternative 3: Hold-to-talk instead of tap-to-toggle
- **Pros**: Familiar pattern from messaging apps
- **Cons**: Requires sustained finger pressure, not accessible for extended speech
- **Reason rejected**: Tap-to-toggle is more accessible for the journaling use case where utterances can be long.

### Alternative 4: Bundled model in APK
- **Pros**: Immediate availability, no download step
- **Cons**: 71MB increases APK by 5x, penalizes users who never use voice
- **Reason rejected**: Lazy download keeps APK small and only downloads for users who opt in.

## Consequences

### Positive
- Fully offline voice input — works without internet connection
- Real-time streaming transcription provides immediate feedback
- Existing text pipeline reused — voice is just another input method
- Abstract services enable comprehensive testing without device
- Lazy model download keeps initial APK small

### Negative
- 71MB model download required on first voice use
- 5-8 second model load time on first activation per session
- ~215MB additional RSS when STT is active
- Push-to-talk requires manual start/stop (mitigated by endpoint detection)

### Neutral
- Battery consumption limited by push-to-talk (not always-on) in 7A
- Audio focus handling adds complexity but is required for correct Android behavior
- Model download UX (progress dialog) is a one-time cost per install
