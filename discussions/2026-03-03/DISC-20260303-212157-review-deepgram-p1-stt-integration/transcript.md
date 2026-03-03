---
discussion_id: DISC-20260303-212157-review-deepgram-p1-stt-integration
started: 2026-03-03T21:22:22.593622+00:00
ended: 2026-03-03T21:39:14.371051+00:00
agents: [architecture-consultant, facilitator, performance-analyst, qa-specialist, security-specialist]
total_turns: 6
---

# Discussion: DISC-20260303-212157-review-deepgram-p1-stt-integration

## Turn 1 — facilitator (evidence)
*2026-03-03T21:22:22.593622+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Implement Deepgram P1 — Deepgram Nova-3 streaming STT integration per ADR-0031: new DeepgramSttService implementing SpeechRecognitionService, new deepgram-proxy Supabase Edge Function (WebSocket bidirectional relay), SttEngine.deepgram added as primary engine in voice_providers.dart, deepgramProxyWsUrl added to environment.dart, deepgram item added to settings STT dropdown, and 14 unit tests for event parsing logic
- **Files/scope**: supabase/functions/deepgram-proxy/index.ts (new), lib/services/deepgram_stt_service.dart (new), lib/providers/voice_providers.dart (SttEngine enum + provider update), lib/config/environment.dart (deepgramProxyWsUrl), test/services/deepgram_stt_service_test.dart (new, 14 tests), lib/ui/screens/settings_screen.dart (dropdown item)
- **Developer-stated motivation**: Replace Android SpeechRecognizer (15-20% WER, 800ms endpoint detection) with Deepgram Nova-3 (6-9% WER, 2000ms journaling-tuned endpoint) per SPEC-20260302-adhd-informed-feature-roadmap Voice Capture Prerequisites and ADR-0031
- **Explicit constraints**: Deepgram API key must never appear in client code (ADR-0005 proxy pattern); SpeechRecognitionService interface must be preserved (ADR-0022 swap boundary); SpeechToTextSttService retained as fallback A; sherpa_onnx retained as fallback B; journaling endpoint detection 2000ms (ADR-0031)

---

## Turn 2 — security-specialist (proposal)
*2026-03-03T21:38:13.014751+00:00 | confidence: 0.85*
*tags: security, blocking:2, advisory:2*

## Security Review — Deepgram P1 STT Integration

**Risk: Medium-High**

### Blocking Findings

**B-1: Deepgram API key in WebSocket URL query param may appear in server-side logs**
The Edge Function constructs `wss://api.deepgram.com/v1/listen?access_token=${deepgramApiKey}&...`. If Deno or any middleware logs the outgoing WebSocket URL, the key is exposed in logs. Standard WebSocket API does not support custom headers, but server-side Deno may have alternatives. Recommendation: if Deno stable WebSocket header support exists, migrate to `Authorization: Token ${key}` header; otherwise explicitly ensure the deepgramUrl variable is never passed to any log statement.

**B-2: coverage:ignore-start wraps entire class including auth header construction**
`_connectAndCapture()` builds the `Authorization: Bearer $_authToken` header — this auth logic has zero test coverage. The class-level ignore is broader than necessary. The parsing methods (`_onSocketMessage`, `_handleResultsEvent`, `_handleUtteranceEndEvent`) are pure logic that can and should be covered by tests.

### Advisory Findings

**A-1: Supabase anon key embedded in APK as Dart-define**
The anon key is transmitted to Deepgram proxy as Authorization header. Per ADR-0005, this is accepted design (anon key is public by design in Supabase). Low risk but worth noting.

**A-2: No auto-fallback on DeepgramSttService network failure**
If `_connectAndCapture()` throws, the error is added to the stream but no automatic fallback to `SpeechToTextSttService` occurs. This is deferred to provider-level orchestration.

**Confidence: 0.85**

---

## Turn 3 — architecture-consultant (proposal)
*2026-03-03T21:38:25.193889+00:00 | confidence: 0.87*
*tags: architecture, blocking:1, advisory:3*

## Architecture Review — Deepgram P1 STT Integration

**Risk: Medium**

### Blocking Findings

**B-1: Test subclass `_TestableDeepgramSttService._parseAndCollect()` duplicates production parsing logic**
The test file contains a full reimplementation of the Deepgram event parsing state machine. Tests verify the test-double code, not production code — the actual `_onSocketMessage`, `_handleResultsEvent`, and `_handleUtteranceEndEvent` methods are untested. Fix: expose `@visibleForTesting` hooks on the production class so tests drive real code paths.

### Advisory Findings

**A-1: 500ms hardcoded flush delay in `stopListening()`**
`await Future<void>.delayed(const Duration(milliseconds: 500))` is a timing-based heuristic. If Deepgram processes quickly, this wastes 500ms on every session end. Consider making this configurable or using a CloseStream acknowledgement event from Deepgram if available.

**A-2: Unbounded `pendingAudio` queue in Edge Function**
Before Deepgram WebSocket opens, audio chunks are buffered in `pendingAudio: (string | ArrayBuffer)[]` with no size cap. Under slow connections or Deepgram API cold starts, this could grow without bound. Add a cap (e.g., 100 chunks ≈ 2s of audio at 20ms/chunk).

**A-3: No auto-fallback on network failure at provider level**
ADR-0031 defines a fallback chain (Deepgram → SpeechToText → sherpaOnnx) but `sttServiceProvider` does not dynamically switch on error — it only reads the stored engine preference. The fallback requires manual user action in settings.

**Confidence: 0.87**

---

## Turn 4 — qa-specialist (proposal)
*2026-03-03T21:38:36.442942+00:00 | confidence: 0.88*
*tags: qa, blocking:2, advisory:3*

## QA Review — Deepgram P1 STT Integration

**Risk: Medium**

### Blocking Findings

**B-1: Test double duplicates production parsing logic (same as arch-consultant B-1)**
`_TestableDeepgramSttService._parseAndCollect()` reimplements the ADR-0031 mapping table in the test file. A bug in production `_handleResultsEvent()` would not be caught by these tests since they never call it. Fix required before merge.

**B-2: Double `startListening()` guard is untested**
`startListening()` has `if (_isListening) throw StateError('Already listening...')`. This guard is not covered by any test. A regression here would cause silent hangs rather than a clear error. Add a test for this guard in the lifecycle group.

### Advisory Findings

**A-1: No test for `_onSocketMessage` with a non-String rawMessage**
The `if (rawMessage is! String) return;` guard handles binary frames from the socket. No test verifies this path.

**A-2: No test for `stopListening()` when already stopped**
The `if (!_isListening) return;` early exit in `stopListening()` is logic that could regress without a test.

**A-3: Coverage gap on `startListening()` stream setup code**
The `_connectAndCapture().catchError()` lambda is infrastructure but coverage:ignore at class level means the rest of `startListening()` (stream controller setup, `_isListening = true`) is also ignored.

**Confidence: 0.88**

---

## Turn 5 — performance-analyst (proposal)
*2026-03-03T21:38:47.850154+00:00 | confidence: 0.82*
*tags: performance, blocking:0, advisory:4*

## Performance Review — Deepgram P1 STT Integration

**Risk: Medium**

### Advisory Findings

**A-1: Unbounded `pendingAudio` queue in Edge Function (same as arch-consultant A-2)**
At 16kHz PCM16 mono with 20ms chunks (~640 bytes each), a 5-second Deepgram cold start could buffer 250+ chunks (~160KB). Not critical for a personal app but wrong to leave unbounded. Cap at ~100 chunks (2s of audio) with oldest-first eviction — this prioritizes the most recent speech for transcription accuracy.

**A-2: 500ms hardcoded flush delay in `stopListening()`**
Every session end pays a 500ms unconditional delay. For voice journaling sessions averaging 5-10 minutes, this is acceptable but could be improved. Deepgram does not send a CloseStream acknowledgement event, so the delay is necessary for flush correctness. Document this constraint explicitly.

**A-3: No audio chunk batching before WebSocket send**
The client sends each ~640-byte PCM16 chunk as a separate WebSocket frame. Batching 4-8 chunks (~20-50ms of audio) per frame would reduce WebSocket overhead by 4-8x. Low priority for a personal app but worth noting.

**A-4: dart:io WebSocket may block the UI thread if audio chunks are large**
`_socket!.add(chunk)` is called synchronously from the audio stream listener. For normal 640-byte chunks this is fine, but large chunks could cause brief UI jank. Not an issue at current config.

**Confidence: 0.82**

---

## Turn 6 — facilitator (synthesis)
*2026-03-03T21:39:14.371051+00:00 | confidence: 0.9*
*tags: synthesis, blocking:4, advisory:7*

## Request Context
- **What was requested**: Implement Deepgram Nova-3 as primary STT engine per ADR-0031: new `DeepgramSttService implements SpeechRecognitionService`, new `deepgram-proxy` Supabase Edge Function WebSocket relay, provider wiring, settings UI.
- **Files/scope**: `supabase/functions/deepgram-proxy/index.ts`, `lib/services/deepgram_stt_service.dart`, `lib/providers/voice_providers.dart`, `lib/config/environment.dart`, `test/services/deepgram_stt_service_test.dart`, `lib/ui/screens/settings_screen.dart`
- **Developer-stated motivation**: Replace Android SpeechRecognizer (15-20% WER, 800ms endpoint detection) with Deepgram Nova-3 (6-9% WER, journaling-tuned 2000ms endpoint), per ADR-0031 ADHD voice capture reliability requirements.
- **Explicit constraints**: CLAUDE.md ADR-0005 proxy pattern — no Deepgram API key in client code.

## Review Verdict: APPROVE-WITH-CHANGES

### Blocking Findings — All Resolved In-Review

**B-1 (arch + qa): Test duplication** — RESOLVED
`_TestableDeepgramSttService._parseAndCollect()` duplicated production parsing logic. Fixed: class-level `coverage:ignore-start/end` removed; parsing methods (`_onSocketMessage`, `_handleResultsEvent`, `_handleUtteranceEndEvent`) now outside coverage:ignore. Added `@visibleForTesting initStreamForTesting()` (sync:true StreamController) and `injectMessageForTesting()` hooks. Test subclass now drives production code paths via these hooks.

**B-2 (qa): Double-startListening guard untested** — RESOLVED
Added lifecycle test: `'startListening throws StateError if already listening'` confirms `_isListening` guard fires before `_connectAndCapture()`.

**B-3 (security): API key in Edge Function URL / coverage scope** — RESOLVED
Updated comment with 3-point explanation of why `access_token` query param is safe server-side (key never transmitted to client, URL never logged, logs only accessible to project admin). Added note to migrate to Authorization header if Deno adds stable support. Narrow `coverage:ignore` blocks replace class-level ignore — `startListening()` guard logic and parsing methods are now tested.

**A-2 (arch + perf): Unbounded pendingAudio queue** — RESOLVED
Added `MAX_PENDING_AUDIO = 100` constant (≈2s at 20ms/chunk). Oldest-first eviction in `clientSocket.onmessage`.

### Open Advisories

**A-1 (security/arch)**: No auto-fallback on DeepgramSttService network failure — deferred, requires provider-level orchestration design.
**A-2 (arch/perf)**: 500ms hardcoded flush delay in stopListening — document constraint, defer optimization.
**A-3 (arch)**: ADR-0031 fallback chain not dynamically triggered — deferred to Phase 3A provider orchestration.
**A-4 (perf)**: No audio chunk batching — low priority for personal app, defer.
**A-5 (perf)**: dart:io WebSocket synchronous add — not an issue at 640-byte chunks.
**A-6 (qa)**: non-String rawMessage not tested — minor, add opportunistically.
**A-7 (qa)**: stopListening idempotency not tested — minor.

### Strengths
- Clean ADR-0031 SpeechResult mapping table implementation — all 4 scenarios covered with dedicated tests.
- UtteranceEnd fallback pattern (safety net for dropped speech_final) correctly implemented with state clear.
- Edge Function WebSocket bidirectional relay is concise and follows ADR-0005 proxy pattern.
- deepgramProxyWsUrl derived from supabaseUrl (no additional config surface).
- SttEngine enum addition follows existing provider pattern; settings UI updated correctly.
- 15 passing tests, 80.6% coverage.

**Confidence: 0.90**

---
