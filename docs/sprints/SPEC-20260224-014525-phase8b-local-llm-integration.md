---
spec_id: SPEC-20260224-014525
title: "Phase 8B: Local LLM Integration — LocalLlmLayer + Personality"
status: reviewed
risk_level: high
phase: "8B"
depends_on: ["Phase 8A (merged)", "ADR-0017"]
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260224-014632-phase8b-local-llm-spec-review
---

## Goal

Implement on-device LLM inference via llamadart so the journal app can generate contextual greetings, empathetic follow-ups, and AI-powered summaries without requiring network access or Claude API credits. Add a configurable personality system (default: "Guy") with therapeutic conversation techniques.

## Context

Phase 8A extracted the ConversationLayer strategy pattern (ADR-0017), created the `RuleBasedLayer` and `ClaudeApiLayer` implementations, added the `AgentLayer.llmLocal` enum value, and wired session-locked layer lifecycle into the providers. The `localLlmLayer` slot on `AgentRepository` is ready but null.

The developer has spike-tested llamadart with Qwen 2.5 1.5B and 3B GGUF models in `spike-models/llm/`. The model research report (`docs/available_model_research_report.md`) recommends Qwen 2.5 0.5B (Q4_K_M, ~380MB) as the best quality-to-size ratio for mobile. ADR-0017 specifies Qwen 2.5 0.5B.

llamadart v0.6.2 provides:
- `LlamaEngine` + `LlamaBackend` for model loading
- `ChatSession` with `systemPrompt` for conversational inference
- Streaming via `await for (chunk in session.create(messages))`
- Automatic Vulkan GPU acceleration on Android
- Background isolate inference (no UI thread blocking)
- `dispose()` for resource cleanup

The existing STT model download service (`ModelDownloadService`) and dialog (`ModelDownloadDialog`) provide a proven pattern for WiFi-gated, resumable, checksum-verified model downloads.

## Requirements

### R1: LocalLlmService — llamadart wrapper
- Abstract class `LocalLlmService` for testability (same pattern as `SpeechRecognitionService`)
- `LlamadartLlmService` implementation wrapping `LlamaEngine` + `ChatSession`
- `loadModel(String modelPath)` — loads GGUF model, wraps all native exceptions into `LocalLlmException`, returns when ready
- `unloadModel()` — disposes engine, frees RAM
- `isModelLoaded` — synchronous getter for current state
- `generate({required List<Map<String, String>> messages, String? systemPrompt})` → `Future<String>` — collects streaming output internally
- Streaming is an internal implementation detail of `LlamadartLlmService` (not on the abstract interface). Promote to abstract only when a streaming UI consumer exists (e.g., voice mode streaming TTS).
- Parameters: temperature=0.7, top_p=0.9, max_tokens=150 (configurable via constructor)
- Suppress llamadart native logging in release builds
- `LocalLlmException` and subtypes (`ModelNotLoadedException`, `InferenceException`) defined in `lib/services/local_llm_service.dart`, following `ClaudeApiException` pattern
- `loadModel()` wraps all native/FFI exceptions into `LocalLlmException` — ensures the fallback chain in AgentRepository always catches cleanly

### R2: LocalLlmLayer — ConversationLayer implementation
- Implements `ConversationLayer` interface (getGreeting, getFollowUp, generateSummary, getResumeGreeting)
- Constructor takes `LocalLlmService` and personality system prompt (captured at construction time — immutable for the layer instance's lifetime, ensuring mid-session personality changes don't affect the active session)
- `getGreeting()`: uses system prompt + time-of-day context + days-since-last
- `getFollowUp()`: passes full conversation history to LLM via `generate()` (non-streaming) with system prompt
- `generateSummary()`: prompts LLM for structured summary from conversation
- `getResumeGreeting()`: contextual resume greeting
- All methods return `AgentResponse` with `layer: AgentLayer.llmLocal`
- Throws `LocalLlmException` on failure — caught by existing `on Exception` handler in AgentRepository, falls back to RuleBasedLayer. No special cleanup needed beyond the standard fallback (model state recovery is LocalLlmService's responsibility internally).

### R3: LLM model download
- New `LlmModelDownloadService` extending the `ModelDownloadService` pattern
- Reuse existing `ModelFileInfo`, `ModelDownloadStatus`, and `ModelDownloadProgress` types (avoid duplicating these classes)
- Single GGUF file: Qwen 2.5 0.5B Instruct Q4_K_M (~380MB)
- Download from HuggingFace CDN (the one accepted direct external dependency per ADR-0017)
- WiFi-only gate when on cellular (same UX as STT model download)
- Resume capability via HTTP Range headers
- **SHA-256 checksum must be non-empty and pre-verified before shipping.** Compute by downloading the GGUF from HuggingFace directly and running `sha256sum`. Do NOT copy the empty-placeholder pattern from `ModelDownloadService` (existing STT gap tracked as separate remediation).
- **Chunked SHA-256 verification**: use `file.openRead()` with incremental `sha256` digest — NOT `readAsBytes()` which would allocate ~380MB on Dart heap and risk OOM. This is a deliberate deviation from the STT download service's pattern, justified by the 5.5x larger file size.
- Storage space check before download
- Store in `getApplicationSupportDirectory()/llm/` (app-private, not backed up)
- Model version pinning: exact URL, expected file size, and SHA-256 hardcoded

### R4: LLM model download UX
- Reuse `ModelDownloadDialog` pattern for the LLM download dialog
- Trigger from settings screen "Download" button (not automatic at first session)
- Show file size (~380MB), progress, WiFi warning on cellular
- Cancel support
- Settings screen shows model status: "Not downloaded" / "Downloading..." / "Ready" / "Error"

### R5: Personality system
- `PersonalityConfig` data class: `name` (String), `systemPrompt` (String), `conversationStyle` (enum: warm/professional/curious), `customPrompt` (String?, nullable)
- Implements `==`, `hashCode`, `toJson()`, `factory fromJson()` for provider rebuild correctness and SharedPreferences serialization
- Serialized as JSON in a single SharedPreferences key (`personality_config`). Corrupted JSON on read falls back to `PersonalityConfig.defaults()` — never throws.
- Default personality "Guy": warm companion tone, motivational interviewing principles, active listening, non-judgmental, reflective questions
- `PersonalityNotifier` Riverpod notifier with persistence
- Custom prompt sanitization rules: trim whitespace, strip control characters (U+0000-U+001F except newlines U+000A), normalize ChatML role markers (strip `<|im_start|>`, `<|im_end|>`, `Human:`, `Assistant:`, `### System` patterns that could confuse the chat template), enforce 500 UTF-16 code unit limit
- **Prompt isolation boundary**: custom prompt injected into LocalLlmLayer constructor only. ClaudeApiLayer structurally prohibits a `systemPrompt` parameter — add a class-level doc comment asserting this boundary (ADR-0005). Add a test verifying that `allMessages` passed to ClaudeApiLayer after a LocalLlmLayer→fallback transition contains no custom prompt text.
- Note: SharedPreferences stores personality in cleartext. Acceptable for single-user app with device encryption. If custom prompt is classified as health data in future, migrate to `flutter_secure_storage`.

### R6: Settings UI updates
- Replace placeholder "Local AI: Not downloaded" with live model status from provider
- Add "Download Local AI" button (shows download dialog)
- Add personality section: name field, conversation style dropdown, custom prompt text area
- Personality changes take effect on next session start (not mid-session, per session-locked layer)
- Disable personality section when journal-only mode is active

### R7: Provider wiring
- `localLlmServiceProvider` — singleton, disposed on container dispose
- `localLlmLayerProvider` — depends on service + personality; returns `LocalLlmLayer?` (null when model not loaded)
- `llmModelReadyProvider` — `FutureProvider<bool>` checking model file existence (same pattern as `sttModelReadyProvider`)
- `llmModelPathProvider` — `FutureProvider<String>` for model directory
- `personalityConfigProvider` — `NotifierProvider` with SharedPreferences persistence
- **AgentRepository wiring fix**: inject `localLlmLayer` via AgentRepository constructor (not mutable field assignment). Add `LocalLlmLayer? localLlmLayer` as a constructor parameter, matching the existing `claudeService`/`connectivityService` injection pattern. The `agentRepositoryProvider` watches `localLlmLayerProvider` so the repo rebuilds when the local LLM becomes available. This solves the provider-rebuild problem where the mutable field was lost on rebuild.

### R8: Tests
- `MockLocalLlmService` — mock implementation of abstract class. `generate()` returns configurable responses. No `generateStream()` on mock (streaming is private to real implementation).
- `LocalLlmLayer` unit tests:
  - All four methods (greeting, follow-up, summary, resume) assert both `response.content` and `response.layer == AgentLayer.llmLocal`
  - With personality prompt: verify mock was called with custom prompt included
  - Without personality prompt (null customPrompt): verify mock called with default system prompt only
  - Error: each method throws `LocalLlmException` → verify it propagates correctly
  - getFollowUp with empty allMessages: returns null or safe fallback
- `PersonalityConfig` tests:
  - `toJson()` / `fromJson()` round-trip
  - `fromJson()` with unknown keys → ignored
  - `fromJson()` with missing required fields → defaults
  - Corrupted JSON string → falls back to `PersonalityConfig.defaults()`
  - Sanitization boundary: exactly 500 chars (accept), 501 chars (truncate), only control chars (empty string), only whitespace (empty string), ChatML markers stripped
  - `==` and `hashCode` correctness
- Provider tests:
  - `PersonalityNotifier` persistence round-trip (save non-default, re-create container, assert restored)
  - Each test calls `SharedPreferences.setMockInitialValues(...)` before constructing container
  - `llmModelReadyProvider` state: false when model absent, true when present
- AgentRepository layer selection tests:
  - llmLocal selected when model loaded + "Prefer Claude" off
  - ClaudeApiLayer selected when "Prefer Claude" on + online (even if local model loaded)
  - **Fallback tested for all 4 methods**: getGreeting, getFollowUp, generateSummary, getResumeGreeting — each with a `ThrowingLocalLlmLayer` mock that throws `LocalLlmException`, verifying `AgentLayer.ruleBasedLocal` in response
- Prompt isolation test: after LocalLlmLayer→RuleBasedLayer fallback, verify `allMessages` contains no custom prompt text
- Download dialog: use `tester.pump()` not `pumpAndSettle` after initiating download (avoids `LinearProgressIndicator` animation deadlock — same pattern as `model_download_dialog_test.dart`)
- `isOnWifi` tests: WiFi (true), mobile only (false), empty result list (false)
- Target: maintain >= 80% coverage

## Constraints

- **No new database migration**: personality config uses SharedPreferences (ADR-0017)
- **llamadart is pre-1.0**: pin exact version `0.6.2`, expect API churn
- **Model download is user-initiated**: triggered from settings, not automatic (avoid surprising 380MB download)
- **Custom prompts are LocalLlmLayer-only**: never leak into ClaudeApiLayer (ADR-0005 / ADR-0017 §7)
- **Session-locked layer**: once a session starts on LocalLlmLayer, it stays there even if model is unloaded mid-session (falls back to RuleBasedLayer on error)
- **RAM budget**: Qwen 0.5B Q4_K_M needs ~600MB RAM. On 6GB device with Zipformer STT (~50MB), Flutter (~200MB), OS (~2GB): ~3.1GB headroom. Comfortable, but still implement lazy load and dispose.
- **No `onTrimMemory` in this phase**: defer Android memory pressure callbacks to a future phase. For now, model stays loaded until app is killed or explicitly unloaded.

## Acceptance Criteria

- [ ] `flutter test` passes with >= 80% coverage
- [ ] `dart analyze` reports zero errors
- [ ] LocalLlmLayer produces greetings, follow-ups, and summaries when model is loaded (verified by unit tests with mock service)
- [ ] All LocalLlmLayer tests assert `response.layer == AgentLayer.llmLocal`
- [ ] Model download dialog shows progress, handles WiFi gate, supports cancel
- [ ] SHA-256 constant for the GGUF is non-empty and matches the value computed from the canonical HuggingFace release
- [ ] SHA-256 verification uses chunked hashing (not readAsBytes) for the 380MB file
- [ ] Settings screen shows live model status (not downloaded / ready)
- [ ] Settings screen personality section allows name, style, and custom prompt changes
- [ ] AgentRepository injects LocalLlmLayer via constructor (not mutable field)
- [ ] AgentRepository selects LocalLlmLayer when model is loaded and "Prefer Claude" is off
- [ ] AgentRepository falls back to RuleBasedLayer when LocalLlmLayer throws — tested for all 4 methods
- [ ] Custom prompt is injected into LocalLlmLayer only, never into ClaudeApiLayer (structural prohibition + test)
- [ ] Personality changes take effect on next session start, not mid-session
- [ ] PersonalityConfig corrupted JSON falls back to defaults (never throws)
- [ ] PersonalityConfig sanitization handles boundary cases (500/501 chars, control-only, ChatML markers)
- [ ] Quality gate passes (6/6): format, lint, test, coverage, ADR, review

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| llamadart pre-1.0 API instability | Medium | Pin exact version 0.6.2, wrap in abstract service |
| 380MB model download UX | Medium | WiFi gate, resume, storage check, user-initiated only |
| Inference latency (0.5B may feel slow on budget cores) | Medium | Streaming response display, max_tokens=150, fallback to rule-based |
| RAM pressure with STT + LLM coexisting | Low | 0.5B model needs ~600MB; 6GB device has ~3GB headroom |
| Personality prompt injection via custom override | Low | Sanitize input, length limit 500 chars, strip control chars |

## Affected Components

### New files
| File | Purpose |
|------|---------|
| `lib/services/local_llm_service.dart` | Abstract + llamadart wrapper |
| `lib/layers/local_llm_layer.dart` | ConversationLayer implementation |
| `lib/models/personality_config.dart` | Personality data model + defaults |
| `lib/services/llm_model_download_service.dart` | LLM-specific model download service |
| `lib/ui/widgets/llm_model_download_dialog.dart` | Download dialog for LLM model |
| `lib/providers/personality_providers.dart` | Personality config provider + notifier |
| `test/services/local_llm_service_test.dart` | Service unit tests |
| `test/layers/local_llm_layer_test.dart` | Layer unit tests |
| `test/models/personality_config_test.dart` | Config tests |
| `test/providers/personality_providers_test.dart` | Provider tests |

### Modified files
| File | Changes |
|------|---------|
| `pubspec.yaml` | Add `llamadart: 0.6.2` (exact pin, no caret — pre-1.0 package) |
| `lib/providers/llm_providers.dart` | Add localLlmService, localLlmLayer, llmModelReady providers |
| `lib/providers/session_providers.dart` | Wire localLlmLayer into AgentRepository at session start |
| `lib/ui/screens/settings_screen.dart` | Live model status, download button, personality settings |
| `lib/repositories/agent_repository.dart` | Change `localLlmLayer` from mutable field to constructor parameter; import LocalLlmException |

## Dependencies

### Depends on
- Phase 8A (merged) — ConversationLayer, AgentLayer.llmLocal, session-locked layer
- ADR-0017 — architecture decisions for local LLM integration
- llamadart 0.6.2 (exact pin) — llama.cpp Flutter bindings

### Depended on by
- Phase 8B+ personality refinements (therapeutic research spike can enhance default prompts later)
- Voice mode LLM integration (voice loop streaming TTS from LocalLlmLayer tokens)
