---
adr_id: ADR-0031
title: "Deepgram Nova-3 as Primary STT Engine"
status: accepted
date: 2026-03-03
risk_level: medium
confidence: 0.85
tags: [voice, stt, deepgram, adhd-roadmap]
discussion_id: DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture
supersedes: null
superseded_by: null
decision_makers: [Developer]
required_before: SPEC-20260302-adhd-informed-feature-roadmap Phase 3A (Pulse Check-In voice flow)
---

## Context

On-device testing revealed that the current `speech_to_text` package (wrapping Android's
Google SpeechRecognizer) produces frequent mistranscriptions under real-world journaling
conditions. Key failure modes identified in DISC-20260303-031401:

1. **Latency**: Android's cloud pipeline introduces 2–4s round-trip latency per utterance.
   The P0 fix (`pauseFor: Duration(seconds: 2)`, PR #61) reduces dead silence but does not
   address transcription quality.
2. **Accuracy**: WER 15–20% in noisy environments vs. Deepgram Nova-3's reported 6–9%.
   Mistranscriptions degrade the journal corpus and undermine AI correlation outputs.
3. **Endpoint detection**: Android SpeechRecognizer uses ~800ms silence default — designed
   for search commands, not journaling. Thinking pauses in ADHD journaling routinely exceed
   2–3 seconds (see SPEC-20260302-adhd-informed-feature-roadmap `## Design Principles`).
   The result: Android cuts off mid-thought.
4. **ADR-0022 boundary**: The `SpeechRecognitionService` abstract interface was designed
   explicitly as the STT provider swap boundary. This is the planned use of that interface.

The ChatGPT voice mode experience was identified as the north-star reference for what
responsive, accurate voice capture feels like.

## Decision

**Replace Android SpeechRecognizer with Deepgram Nova-3 streaming WebSocket as the primary
STT engine, implemented as `DeepgramSttService implements SpeechRecognitionService`.**

The existing `speech_to_text` implementation (`SpeechToTextSttService`) is retained as a
fallback, and the sherpa_onnx offline path (ADR-0022) remains available. Provider selection
is controlled by a Riverpod provider that reads a feature flag / user setting.

This decision is conditional on the `deepgram-proxy` Edge Function being implemented per
ADR-0005 (all external API calls proxied through Supabase Edge Functions — never direct from
client to third-party API). No Deepgram API key is ever embedded in the Flutter app.

## Implementation Scope

### New Files
- `lib/services/deepgram_stt_service.dart` — `DeepgramSttService implements SpeechRecognitionService`
- `supabase/functions/deepgram-proxy/index.ts` — WebSocket proxy Edge Function
- `test/services/deepgram_stt_service_test.dart` — unit + mock tests

### Modified Files
- `lib/providers/voice_providers.dart` — add `deepgramSttServiceProvider`, update
  `sttServiceProvider` to select between `DeepgramSttService` and `SpeechToTextSttService`
  based on feature flag

### `SpeechResult` Mapping (Deepgram WebSocket → SpeechRecognitionService contract)

Deepgram's streaming WebSocket emits two event types that map to `SpeechResult.isFinal`:

| Deepgram event | `SpeechResult.isFinal` | Notes |
|---|---|---|
| `is_final: false` (interim) | `false` | Display only; not committed to journal |
| `is_final: true` + `speech_final: false` | `false` | Deepgram internal segment boundary |
| `is_final: true` + `speech_final: true` | **`true`** | Primary commit trigger |
| `utterance_end` event | **`true`** (synthetic) | Fallback if `speech_final` not received |

`SpeechResult.isFinal = true` signals the orchestrator to commit the turn. Both
`speech_final: true` and `utterance_end` map to this; the latter is a safety net for
network conditions where the `speech_final` message is dropped.

### Endpoint Detection Configuration (Journaling-Tuned)

```
endpointing=2000        # 2000ms silence before speech_final fires
utterance_end_ms=1500   # emit utterance_end after 1500ms silence (fallback)
interim_results=true    # stream partials for responsive UI
vad_events=true         # voice activity detection events
model=nova-3
language=en-US
```

**Rationale for 2000ms**: Standard cloud STT defaults (~800ms) interrupt ADHD thinking
pauses. The 2s threshold matches the `pauseFor` value in `SpeechToTextSttService` after
the P0 fix, providing a consistent endpoint detection experience regardless of STT backend.
This is the same tuning insight documented in DISC-20260303-031401.

### Edge Function Architecture

The `deepgram-proxy` Edge Function follows the ADR-0005 proxy pattern:
- Client opens WebSocket to `wss://<project>.supabase.co/functions/v1/deepgram-proxy`
- Edge Function authenticates (Supabase JWT validation), then opens a WebSocket to
  `wss://api.deepgram.com/v1/listen?...` with the Deepgram API key from Supabase secrets
- Audio bytes from client are forwarded verbatim to Deepgram
- Deepgram transcription events are forwarded back to client
- No audio is stored server-side

**ADR-0005 extension**: ADR-0005 governs HTTP proxy via Edge Functions. WebSocket proxying
requires a new constraint: the Edge Function must maintain two concurrent WebSocket
connections (client ↔ proxy ↔ Deepgram). Supabase Edge Functions support Deno WebSocket;
this pattern is documented but requires validation in a spike before Phase 3A begins.

## Cost Model

| Usage | Deepgram Nova-3 rate | Monthly cost |
|---|---|---|
| 10 min/day × 30 days | $0.0059/min | ~$1.77/month |
| 20 min/day × 30 days | $0.0059/min | ~$3.54/month |
| Edge Function invocations | ~$0.002/invocation | ~$0.06/month |

Well within acceptable operating cost for a personal journaling application.

## Fallback Chain

1. **Primary**: `DeepgramSttService` (Deepgram Nova-3, cloud, ~$1.77/month)
2. **Fallback A**: `SpeechToTextSttService` (Android SpeechRecognizer, free, ~15–20% WER)
   — triggered when: network unavailable, Deepgram API error, Edge Function failure
3. **Fallback B**: sherpa_onnx (offline, on-device) — retained from ADR-0022; blocked by
   Snapdragon 888 SIGILL risk (ADR-0017); requires hardware validation spike before enabling

The `sttServiceProvider` selects Primary when network is available and the feature flag
is enabled; otherwise Fallback A. Fallback B remains disabled until ADR-0017 risk is resolved.

## Alternatives Considered

### A. Keep Android SpeechRecognizer (status quo)
Rejected. WER 15–20%, 2–4s latency, ~800ms endpoint detection that interrupts thinking
pauses. Directly undermines the "effortless capture" clinical UX contract and EMA
<2-minute compliance threshold.

### B. OpenAI Whisper via HTTP batch (not streaming)
Rejected. Batch transcription requires buffering the full utterance before sending — adds
2–5s latency after speech ends. No interim results for responsive UI. Streaming is required
for the Pulse Check-In voice flow (Phase 3A of SPEC-20260302-adhd-informed-feature-roadmap).

### C. GPT-4o Realtime API (north star, deferred)
GPT-4o Realtime provides turn-taking, interruption, and real-time conversation — the true
ChatGPT voice north star. **Blocked:**
- ADR-0005 governs HTTP proxy only; WebSocket proxying to OpenAI Realtime requires a new
  ADR to define the constraint boundary.
- Claude as the conversational AI layer is a foundational constraint (ADR-0004); GPT-4o
  Realtime conflates STT + LLM into one API, creating a constraint conflict.
- Cost: ~$0.06/min input + $0.12/min output = ~$3.00+ per 10-minute session.
- Initiation requires a new ADR resolving the above conflicts before any implementation.
  This ADR explicitly defers that decision.

### D. On-device Whisper via sherpa_onnx / whisper.cpp
Available as Fallback B above. Cannot be primary until Snapdragon 888 SIGILL risk from
ADR-0017 is resolved via hardware validation spike.

## Consequences

**If implemented:**
- Voice capture WER improves from ~15–20% to ~6–9%.
- Endpoint detection tuned to journaling cadence (2s pause), eliminating mid-thought cutoffs.
- Journal corpus quality improves, strengthening AI correlation outputs (Phase 2).
- New operational dependency: Deepgram API + `deepgram-proxy` Edge Function.
- Network required for primary STT path; offline mode degrades to Fallback A accuracy.
- `SpeechToTextSttService` is retained (not deleted) to serve as fallback.

**If deferred:**
- `SpeechToTextSttService` with `pauseFor: Duration(seconds: 2)` (P0 fix) remains in use.
- Phase 3A (Pulse Check-In voice flow) proceeds with lower transcription quality.
- The Pulse Check-In numeric parser must be more robust to handle mistranscriptions of
  digit words ("too" → 2, "for" → 4, "ate" → 8, "won" → 1).

## Linked Discussion

- DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture
- SPEC-20260302-adhd-informed-feature-roadmap — `## Voice Capture Prerequisites`
- ADR-0022 — Voice Engine Swap (defines `SpeechRecognitionService` swap boundary)
- ADR-0005 — Supabase Edge Function proxy pattern
- ADR-0017 — On-device model execution (sherpa_onnx SIGILL risk)
