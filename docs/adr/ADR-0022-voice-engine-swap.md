---
adr_id: ADR-0022
title: "Voice Engine Swap — ElevenLabs TTS + speech_to_text STT"
status: accepted
date: 2026-02-25
decision_makers: [developer, facilitator]
supersedes: null
risk_level: medium
confidence: 0.85
tags: [voice, tts, stt, elevenlabs, speech-to-text, supabase, edge-function]
discussion_id: null
---

## Context

Phase 7A (ADR-0015) introduced voice mode using:
- **STT**: sherpa_onnx Zipformer (offline, requires 71MB model download)
- **TTS**: flutter_tts (Android system engine, robotic voice)

User feedback identified two issues:
1. **TTS quality**: flutter_tts produces robotic, unnatural-sounding speech that undermines the conversational journaling experience.
2. **STT accuracy**: sherpa_onnx misses words in continuous speech, particularly during natural conversational cadence. The model also outputs ALL CAPS which requires post-processing.

Additionally, the 71MB model download required for sherpa_onnx creates friction for first-time voice users.

## Decision

### 1. ElevenLabs TTS via Supabase Edge Function Proxy

Replace flutter_tts with ElevenLabs for natural-sounding TTS, proxied through a new Supabase Edge Function (`elevenlabs-proxy`). This follows the same security pattern as the Claude API proxy (ADR-0005):

- **API key**: Stored as Supabase secret `ELEVENLABS_API_KEY`, never in the app
- **Auth**: JWT validation + PROXY_ACCESS_KEY fallback (same as claude-proxy)
- **Flow**: App sends text → proxy calls ElevenLabs API → returns MP3 audio bytes
- **Playback**: `just_audio` package plays MP3 bytes from memory via `StreamAudioSource`
- **Default voice**: "Sarah" (EXAVITQu4vr4xnSDxMaL), eleven_turbo_v2_5 model

**Why not `elevenlabs_flutter` SDK**: The official SDK requires a client-side API key, which violates the security baseline (no secrets in the app).

### 2. speech_to_text STT (Google On-Device)

Replace sherpa_onnx with `speech_to_text` package, which wraps Android's built-in speech recognizer (Google):

- **No model download**: Uses the system recognizer, zero setup friction
- **Better accuracy**: Google's recognizer handles natural speech cadence well
- **Auto-restart**: The service transparently restarts when Android's silence timeout fires, maintaining continuous listening without orchestrator changes
- **Mixed case output**: Returns natural casing, unlike sherpa_onnx's ALL CAPS

### 3. Offline Fallback Preserved

Both old engines remain available as selectable options in Settings:
- **TTS**: "Natural (ElevenLabs)" (default) / "Basic (Offline)" (flutter_tts)
- **STT**: "Google (No download)" (default) / "Offline (71MB model)" (sherpa_onnx)

Engine preference is persisted in SharedPreferences. The provider layer creates the appropriate service implementation based on the selected engine.

### 4. VoiceSessionOrchestrator Unchanged

The orchestrator depends only on the abstract `SpeechRecognitionService` and `TextToSpeechService` interfaces. The engine swap is transparent to it — no changes needed.

## Consequences

### Positive
- Natural-sounding TTS significantly improves the journaling experience
- Zero-download STT removes a major friction point for first-time users
- Offline fallback preserves functionality without network
- Security model maintained (no API keys in app)

### Negative
- ElevenLabs TTS requires network connectivity (no offline natural voices)
- ElevenLabs has per-character pricing (cost scales with usage)
- Additional Supabase secret to manage (ELEVENLABS_API_KEY)
- `just_audio` adds a new native dependency

### Risks
- **ElevenLabs rate limits**: Could throttle heavy TTS usage. Mitigated by keeping flutter_tts as fallback.
- **speech_to_text Android compatibility**: Depends on Google's recognizer being installed. Standard on all Google-certified devices.
- **Latency**: ElevenLabs TTS adds network round-trip vs. local flutter_tts. eleven_turbo_v2_5 model is optimized for low latency.

## Alternatives Considered

1. **elevenlabs_flutter SDK**: Official ElevenLabs Flutter SDK. Rejected because it requires a client-side API key, violating the security baseline (no secrets in the app). The proxy pattern from ADR-0005 is preferred.
2. **Google Cloud TTS**: High-quality voices, but requires GCP billing setup and API key management. ElevenLabs offers simpler pricing and superior voice quality for conversational use.
3. **Whisper (on-device)**: OpenAI's Whisper model for STT. Would require model download (similar friction to sherpa_onnx) and native integration complexity. Google's built-in recognizer via speech_to_text is zero-setup.
4. **Keep sherpa_onnx as default STT**: The ALL CAPS output and word-skipping issues degraded the user experience enough to warrant replacing the default, while keeping it as an offline fallback.

## Files Changed

| File | Change |
|------|--------|
| `pubspec.yaml` | Added `speech_to_text`, `just_audio` |
| `supabase/functions/elevenlabs-proxy/index.ts` | New Edge Function |
| `lib/services/elevenlabs_tts_service.dart` | New TTS implementation |
| `lib/services/speech_to_text_stt_service.dart` | New STT implementation |
| `lib/config/environment.dart` | Added `elevenlabsProxyUrl` |
| `lib/providers/voice_providers.dart` | Engine enums, selection providers, service provider updates |
| `lib/ui/screens/settings_screen.dart` | Engine dropdowns, custom prompt bug fix |
| `lib/ui/screens/journal_session_screen.dart` | Skip model download for speech_to_text |
| `android/app/src/main/AndroidManifest.xml` | Added RecognitionService query |
