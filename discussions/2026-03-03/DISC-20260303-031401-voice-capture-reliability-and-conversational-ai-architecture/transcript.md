---
discussion_id: DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture
started: 2026-03-03T03:14:15.987412+00:00
ended: 2026-03-03T03:23:46.990123+00:00
agents: [architecture-consultant, facilitator, independent-perspective, performance-analyst]
total_turns: 7
---

# Discussion: DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture

## Turn 1 — facilitator (evidence)
*2026-03-03T03:14:15.987412+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Deep dive research on voice capture reliability and conversational AI interaction architecture — understand the landscape of STT alternatives and architectural approaches with ChatGPT voice mode as the north star
- **Files/scope**: No files — research deliberation covering STT options, end-to-end audio AI, turn-taking models, streaming architecture, and journal-specific considerations
- **Developer-stated motivation**: On-device STT (Flutter speech_to_text / Android SpeechRecognizer) produces frequent mistranscriptions in real-world use; ElevenLabs TTS is working well; want to understand incremental and architectural paths to significantly better voice capture and more natural conversational engagement
- **Explicit constraints**: ElevenLabs TTS is not the problem and should be retained; Claude remains the AI backbone for non-voice features; research should produce a recommendation matrix with incremental path, architectural upgrade path, turn-taking model, and north star delta

---

## Turn 2 — performance-analyst (proposal)
*2026-03-03T03:17:51.657842+00:00 | confidence: 0.82*
*tags: stt-comparison, latency-analysis, cost-analysis*

## Performance Analysis: Voice Capture Pipeline

**Confidence: 0.82**

### Critical Finding: pauseFor: Duration(seconds: 5) is the dominant latency contributor

The single largest blocker to conversational feel is in speech_to_text_stt_service.dart line 98: pauseFor: Duration(seconds: 5). This means Android waits up to 5 seconds of silence before committing a final result. Even if all downstream latency were zero, the user waits up to 5 seconds after speaking before the pipeline starts. Reduce to Duration(seconds: 2) immediately — highest-ROI change available, zero architecture change required.

### Current Pipeline Latency Stack (p50, 4G mobile)

Total: 1,600–4,480ms (realistic: 2.5–3.5s before audio plays)

- Android STT (5s pause window): 200–800ms
- Network to Supabase EF: 80–200ms  
- EF auth (getUser() inner call): 30–80ms per request
- Network EF → Anthropic: 80–150ms
- Claude generation (full, no stream): 600–1,500ms
- Anthropic → EF → app: 80–200ms
- App → ElevenLabs EF: 80–200ms
- ElevenLabs eleven_turbo_v2_5 (full buffer): 300–800ms
- EF → app transfer: 100–400ms
- just_audio decode + play start: 50–150ms

### Additional Structural Issues Found

1. Both Edge Functions call supabase.auth.getUser() on every request — 30–80ms of auth overhead per turn. Should use local JWT verification instead (jose in Deno) to eliminate the inner network call while preserving security.

2. Claude proxy does not use streaming (stream: false default). ElevenLabs proxy calls ttsResponse.arrayBuffer() — holds full MP3 before responding. Both force 100% response wait before playback.

3. ElevenLabs client uses responseType: ResponseType.bytes with 30s timeout — blocks until all audio bytes received.

4. max_tokens: 1024 for voice mode responses constrained to 15 words by system prompt — should be 50–80 for voice mode as a safety ceiling.

### STT Provider Comparison (conversational speech WER, 2025-2026)

Provider | WER (conv.) | Streaming | Latency (first token) | Cost/min | Monthly@10min/day
---------|-------------|-----------|----------------------|----------|-------------------
Deepgram Nova-3 | 6-9% | YES | 200-400ms | /usr/bin/bash.0059 | ~.77
OpenAI Whisper | 8-13% | NO (batch) | 800-2000ms | /usr/bin/bash.006 | ~.80
AssemblyAI Universal-2 | 8-11% | YES | 300-600ms | /usr/bin/bash.0065 | ~.95
Google Cloud STT v2 | 9-14% | YES | 200-500ms | /usr/bin/bash.016-0.02 | ~.80-6.00
ElevenLabs Scribe | 8-12% | NO (batch) | n/a | /usr/bin/bash.0067 | ~.00
Azure Speech | 8-13% | YES | 200-450ms | /usr/bin/bash.0167 | ~.00

**Winner: Deepgram Nova-3** — best WER on conversational/noisy audio, streaming, lowest cost. ElevenLabs Scribe and Whisper are batch-only, disqualifying them for low-latency architecture.

### GPT-4o Realtime API

- End-to-end latency (audio in → audio out first chunk): 250-400ms favorable, 400-700ms mobile
- Cost: ~.08/month at 10 min/day (audio input + output tokens)
- Cheaper than Deepgram + Claude + ElevenLabs combined (~-7/month)
- BUT: replaces Claude as voice AI backbone — conflicts with stated constraint

### Latency Stack: Optimized (Deepgram streaming + Claude streaming + EL streaming)

Total first-audio-out p50: 530–1,050ms (vs. current 1,600–4,480ms)

Deepgram final transcript arrives ~200ms after speaker stops (no silence window wait). First Claude token: 200-400ms. First ElevenLabs audio chunk: 150-300ms. These overlap in streaming mode.

### Theoretical Minimum Per Architecture

Architecture | Theoretical Min | Notes
-------------|-----------------|-------
Current (batch) | 1,400ms | Best case, perfect network
Deepgram+Claude+EL streaming | 400-500ms | Network physics bound
GPT-4o Realtime | 250-350ms | Single WebSocket, unified model
On-device (sherpa+local LLM) | 80-200ms | No network but quality trade

### Cost Summary (10 min/day)

Stack | Monthly
------|--------
Current (free STT + Claude + EL) | ~.50-5.00
Deepgram + Claude + EL | ~.50-7.50
GPT-4o Realtime (voice) + Claude (text) | ~.00-3.00
On-device everything | ~/usr/bin/bash

### Key Structural Advantage

The existing SpeechRecognitionService abstract interface means swapping STT providers requires no changes to the orchestrator — only a new implementation. The existing dual-proxy pattern (claude-proxy, elevenlabs-proxy) means a deepgram-proxy follows the same established pattern. The turn-completeness marker system (checkmark/circle/half-circle) is architecturally sound and worth preserving.

---

## Turn 3 — independent-perspective (proposal)
*2026-03-03T03:18:40.075675+00:00 | confidence: 0.82*
*tags: hidden-assumptions, pre-mortem, alternative-perspectives*

## Independent Perspective: Voice Capture Research

**Confidence: 0.82**

### Hidden Assumptions Being Made

1. 'Mistranscription is the primary problem.' Two prior STT swaps (sherpa_onnx → speech_to_text) already occurred without user-reported accuracy measurements. A third swap is being considered based on assumed improvement direction, not measured data.

2. 'ChatGPT voice feels natural because of a superior STT provider.' False. GPT-4o Realtime processes audio end-to-end — no STT→LLM→TTS serial chain. No cloud STT provider inserted into the current architecture will reproduce that experience because the pipeline shape is fundamentally different.

3. 'The user wants the AI to be more present/responsive.' Never stated. 'Better voice capture' and 'more natural conversational engagement' are different problems. Better capture is an STT accuracy problem. More natural engagement is an AI response quality and latency problem. The framing conflates them.

4. 'Cloud STT works reliably on a walk.' The use case is explicitly walking. ADR-0004 (offline-first) chose on-device STT for exactly this scenario. This decision is being reconsidered without evaluating how often the use case involves poor connectivity.

5. 'Journal speech resembles command speech.' Journaling is stream-of-consciousness, frequent self-corrections, incomplete sentences, trailing thoughts, long inhalations before emotional content. No STT provider has published accuracy benchmarks for this specific modality.

6. 'More responsive AI is what makes journaling feel better.' ChatGPT voice mode is optimized for Q&A. Journaling is primarily monologue with occasional prompting. An AI that jumps in on a 200ms thinking pause may be actively harmful to the journaling experience — silence was not an invitation to speak.

### Pre-Mortem Scenarios

**Scenario 1 (Privacy Breach — HIGH RISK)**: Private journal entries streamed to Deepgram/AssemblyAI/Google servers. Journaling apps live or die on trust. The raw audio preservation feature (ADR-0024) saves WAV files locally — if that same audio is also being streamed to a cloud vendor, the disclosure must be unambiguous. This is the highest-risk item in the upgrade path.

**Scenario 2 (Wrong Root Cause)**: Deepgram is integrated, WER drops from ~15% to ~7%. User satisfaction does not improve because the problem was not transcription — it was that AI follow-up questions feel canned and tone-deaf to emotional content. The presenting complaint (garbled words) was a proxy complaint for 'not feeling heard.' The minimum test: manually correct current transcriptions and replay through Claude to isolate the STT contribution.

**Scenario 3 (GPT-4o Context Split)**: GPT-4o Realtime for voice + Claude for text. Personality, tone, and memory diverge across providers over time. The journaling companion starts to feel like two different entities depending on whether the user is speaking or typing. Erodes the continuity that makes a companion feel like a relationship. Recommendation: Do not adopt GPT-4o Realtime.

**Scenario 4 (Latency Improvement Becomes Interruption — HIGH RISK)**: Streaming cloud STT with aggressive endpoint detection fires during a 2-second thinking pause — normal journaling behavior. The AI begins responding mid-thought. The current settings (rule1MinTrailingSilence: 2.4s, rule2MinTrailingSilence: 1.2s) are deliberately generous for journaling cadence. Cloud STT defaults (0.8–1.0s) are tuned for commands. This could make the experience actively worse. Any cloud STT integration MUST explicitly configure endpoint detection to match or exceed current silence thresholds.

**Scenario 5 (Compounded Outage)**: ElevenLabs outage + cloud STT outage = total voice mode unavailability. The current architecture has offline fallbacks (sherpa_onnx, flutter_tts). These must remain maintained and tested as first-class options, not legacy paths.

### Unconsidered Alternatives

**Alternative 1 — On-Device Whisper (whisper.cpp)**: The ADRs rejected on-device Whisper in 2024 as batch-only. This is less clearly true now. whisper.cpp with streaming VAD produces first transcription within 1–2 seconds of utterance completion on modern phones. Whisper was trained on 680,000 hours including spontaneous speech and noisy environments — closer to journaling's distribution than command speech benchmarks. ~150MB model (Small). For journaling where LLM+TTS takes 2–4s anyway, a 1.5s Whisper transcription is absorbed into the latency budget with no perceptible difference. Privacy guarantee preserved. RECOMMEND: Validation spike before committing to cloud STT.

**Alternative 2 — Fix the Prompt Before Fixing the Pipe**: The conversation_layer.dart isVoiceMode flag threads into Claude. If the voice prompt is not specifically tuned for: shorter responses, acknowledging emotional content before asking follow-ups, not interrupting long monologue entries — then improving STT may expose a different problem. Audit what Claude's voice prompt actually does differently before assuming STT is the bottleneck. Lowest-cost intervention per CLAUDE.md Principle #8.

**Alternative 3 — Push-to-Talk with Streaming Feedback**: PTT as primary voice UX with live streaming partial transcription displayed. User sees their words appearing live. On button release, transcript is committed. Eliminates endpoint-detection-as-interruption risk entirely. Simpler than continuous mode. Preserves offline operation. May be the right UX for journaling where monologue is the primary activity and AI response is periodic, not continuous.

### Consensus Caution

All agents will agree WER improvements are desirable. But for journaling specifically, slightly imperfect transcription of emotional speech may be less harmful than the user feeling their thinking was cut off. The relationship between transcription accuracy and journaling quality is not linear — after a 'good enough' threshold, other factors dominate. Do not over-index on WER metrics when the actual user need is qualitative (feeling supported, feeling heard).

### Strengths of Current Architecture

The existing architecture already embodies the right journaling instincts: generous endpoint silences (2.4s/1.2s), offline-first (ADR-0004), raw audio preservation fallback (ADR-0024), abstract service interfaces (SpeechRecognitionService, TextToSpeechService) for painless provider swaps, isVoiceMode threading through ConversationLayer. Any upgrade should preserve these properties, not replace them.

---

## Turn 4 — architecture-consultant (proposal)
*2026-03-03T03:20:07.345844+00:00 | confidence: 0.88*
*tags: architecture-options, deepgram, gpt4o-realtime, turn-taking*

Architecture analysis: Voice Capture Reliability (confidence: 0.88). See full analysis in discussion transcript. Key findings: (1) Android SpeechRecognizer fails for journaling due to 5 structural issues: internet dependency, session limits, noise model mismatch for command speech vs journaling speech, no acoustic adaptation, and audio focus contention with just_audio. (2) GPT-4o Realtime uses persistent WebSocket with server-side VAD, unified STT+LLM+TTS — produces 250-500ms end-to-end latency. Requires PCM16 24kHz. (3) Four architectural options: A=Deepgram drop-in (2-3 days, 3x STT speed, zero orchestrator change), B=Full streaming pipeline (1-2 weeks, sub-1.5s total latency), C=GPT-4o Realtime hybrid (1-2 weeks, 300-500ms feel, WebSocket proxy ADR needed), D=Future Anthropic audio (same as C). (4) Critical: pauseFor Duration(seconds:5) and audio focus contention disappear entirely with cloud STT — these are structural consequences of Android SpeechRecognizer, not tunable parameters. (5) The SpeechRecognitionService abstract interface makes Option A approximately one new class plus one Edge Function. (6) Option C blocker: ADR-0005 proxy pattern does not naturally extend to WebSocket — Supabase Edge Functions have limited WebSocket proxy support. Needs new ADR before implementation. (7) Recommend Option A now, Option C as Phase 8C/9 per CLAUDE.md Principle 8 (least-complex intervention first). The FallbackSttService wrapping Deepgram with sherpa_onnx fallback is directly analogous to the existing FallbackTtsService pattern — the groundwork for graceful STT degradation is already established.

---

## Turn 5 — architecture-consultant (critique)
*2026-03-03T03:22:14.475602+00:00 | confidence: 0.82*
*tags: round2, deepgram-config, whisper-risk*

Round 2 responses (confidence: 0.82). Challenge 1 (On-device Whisper): PARTIALLY AGREE. ADR-0022 rejection is thin, but ADR-0017 SIGILL on SM-G998U1 Snapdragon 888 is directly relevant — whisper.cpp via ONNX faces the same risk as llamadart. ONNX Runtime native libraries on Android ship architecture-specific builds; Snapdragon 888 has documented compatibility gaps with SVE/Helium-accelerated inference paths. SIGILL concern does not transfer automatically but is a strong caution flag requiring explicit hardware validation before any ADR update. Deepgram recommendation stands. Challenge 2 (Endpoint detection risk): AGREE. Risk is real. Deepgram parameters for journaling: endpointing=2000ms (2s post-speech silence), utterance_end_ms=1500, interim_results=true, vad_events=true. These approximate current rule1MinTrailingSilence: 2.4s. Must be documented in the Deepgram ADR as explicit required configuration, not magic numbers in implementation. Challenge 3 (Voice prompt audit first): DISAGREE. Prompt already well-constructed (15 words max, turn-completeness markers, no markdown). pauseFor: Duration(seconds: 5) is the latency source — STT holds the session open for 5 seconds of silence before finalizing regardless of response length. Prompt quality is not the constraint.

---

## Turn 6 — independent-perspective (critique)
*2026-03-03T03:22:24.777573+00:00 | confidence: 0.82*
*tags: round2, pausefor-fix, endpoint-config, whisper-conditional*

Round 2 revised assessment (confidence: 0.82). On pauseFor finding: YES, changes sequencing. Minimum viable change is now: (1) reduce pauseFor from 5s to 2-3s immediately — single line, certain impact; (2) audit voice prompt in parallel, not sequentially. Caveat: 2s may cause premature cut-offs for journaling users who pause mid-thought. Value should be validated against journaling-pace speech, not just reactive commands. 2-3s range recommended, not 2s as a hard floor. On Scenario 4 (endpoint detection): Downgraded from HIGH to MEDIUM. Risk is bounded to the migration path — it manifests as a 'developers use defaults' problem, and the default is now known (5s). For any cloud STT migration, explicit endpointing configuration is a required migration task, not an optional tuning. On on-device Whisper: Downgraded from viable to conditional. SIGILL precedent on Snapdragon 888 from ADR-0017 is a real warning, not isolated. Whisper.cpp via ONNX faces the same vector. Requires chip-compatibility validation spike before committing. New finding: hidden assumption about hung recognizer state — if audio focus contention with just_audio causes Android recognizer to never reach notListening (instead hanging), the restart loop never fires. A hung state that never errors may bypass the 3-consecutive-failure escalation path. Verify during pauseFor fix testing.

---

## Turn 7 — facilitator (synthesis)
*2026-03-03T03:23:46.990123+00:00 | confidence: 0.88*

Synthesis of voice capture reliability and conversational AI architecture deliberation. CRITICAL FINDING (unanimous): pauseFor: Duration(seconds: 5) in speech_to_text_stt_service.dart:98 is the dominant latency contributor — forces 5-second silence wait before pipeline starts. Fix to Duration(seconds: 2-3) immediately. Single-line change, zero architecture change, highest ROI. Voice prompt already well-constructed (15 words max, turn markers) — audit in parallel, will confirm not discover. RECOMMENDATION MATRIX: Path 1 (Days 1-2): Fix pauseFor to 2.5s, monitor for hung recognizer states (audio focus contention may cause recognizer to never reach notListening). Path 2 (1-2 weeks): Deepgram Nova-3 streaming — best WER 6-9% on conversational speech, streaming first token 200-400ms, .77/month at 10 min/day. SpeechRecognitionService abstract interface makes this ~one new class + one Edge Function. CRITICAL: Configure endpointing=2000ms/utterance_end_ms=1500 for journaling — NOT cloud defaults (0.8s will interrupt thinking pauses). sherpa_onnx stays as offline fallback. On-device Whisper: CONDITIONAL — ADR-0017 SIGILL on Snapdragon 888 is direct warning for whisper.cpp/ONNX; requires chip validation spike first. Path 3 (1-2 months): GPT-4o Realtime for voice — 250-500ms end-to-end, server-side semantic VAD. Blockers: (1) ADR-0005 WebSocket proxy architecture unresolved, (2) constraint conflict with Claude-as-backbone, (3) .00/session cost vs. /usr/bin/bash.10/session current. NORTH STAR DELTA: Four properties of ChatGPT voice feel: server-side semantic VAD (only achievable via Path 3), pipelined audio delivery (achievable via Path 2 streaming), single round-trip (only Path 3), interruption handling (only Path 3). JOURNALING CAUTION: 300ms responsiveness may not be optimal for voice journaling — generous silence tolerance (2-3s) is a first-class design requirement for the reflective pause use case, not a legacy artifact. STT provider comparison winner: Deepgram Nova-3 (WER 6-9%, streaming, .77/month). Disqualified: Whisper API (batch-only), ElevenLabs Scribe (batch-only), Google Cloud (3x more expensive), Azure (5x more expensive).

---
