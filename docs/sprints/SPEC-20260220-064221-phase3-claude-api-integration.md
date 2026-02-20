---
spec_id: SPEC-20260220-064221
title: "Phase 3: Claude API Integration — LLM-Enhanced Conversations"
status: reviewed
risk_level: high
phase: 3
source: docs/product-brief.md
estimated_tasks: 11
autonomous_execution: true
depends_on: SPEC-20260220-000100
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260220-064342-phase3-spec-review
---

## Goal

Replace the local rule-based agent with real Claude API calls via a Supabase Edge Function proxy, while keeping the rule-based agent as an always-available offline fallback. After Phase 3, conversations are natural and AI-driven when online, with AI-generated summaries, mood tags, people extraction, and topic tags.

## Context

- Phase 1 delivered a working offline journaling app with a rule-based agent (Layer A per ADR-0006)
- Phase 2 added assistant registration, settings, and onboarding (133 tests, 86.6% coverage)
- `AgentRepository` is currently synchronous and stateless — all methods return `String` or `String?` synchronously
- `SessionNotifier` calls agent methods synchronously in `startSession()`, `sendMessage()`, `endSession()`
- The codebase has no network dependencies yet — `dio`, `connectivity_plus`, and Supabase are not in `pubspec.yaml`
- The `supabase/` directory does not exist — the Edge Function must be scaffolded from scratch
- ADR-0005 mandates the Claude API key never reaches the client; all LLM calls route through the Edge Function
- ADR-0006 mandates Layer A (rule-based) is never removed — it is the permanent offline fallback
- The developer is a Python/SQL specialist learning Flutter — TypeScript/Deno for the Edge Function is new territory
- Supabase Auth is not implemented until Phase 4 — the Edge Function runs with anon key access for now

### Design Decision: No ConversationAgent Interface

Phase 2's spec included a stretch goal (Stretch B) to extract a `ConversationAgent` abstract interface to prepare the Layer A/B boundary for Phase 3. This was not implemented. **Decision: We are NOT extracting `ConversationAgent` for Phase 3.** Instead, switching logic lives directly inside `AgentRepository`, consistent with ADR-0006's Consequences section ("Layer switching logic adds some complexity to `agent_repository.dart`"). This avoids premature abstraction (Principle #8) and is the minimum-complexity intervention.

**Phase 5 re-evaluation**: When Layer C (intent classification: journaling vs. querying) is added, `AgentRepository` will dispatch among three layers. At that point, evaluate whether layer dispatch should be extracted into a separate strategy class. The single-class approach works for two layers but may overload with three.

## Constraints

- **No API keys in client code**: Claude API key is a Supabase Edge Function secret, never in Dart (ADR-0005)
- **Layer A must always work**: If the Claude API is unreachable, the app falls back to rule-based conversation seamlessly (ADR-0006)
- **No Supabase Auth yet**: Phase 4 adds authentication. Phase 3 calls the Edge Function using Supabase's project URL + anon key. The Edge Function checks for an `Authorization: Bearer <jwt>` header — if present, validates it; if absent, proceeds without auth (open access for Phase 3). Phase 4 changes this to reject unauthenticated requests (one-line change).
- **Offline-first remains the default**: The app must never block on a network call. All LLM calls have timeouts with graceful fallback.
- **TLS enforcement**: The `dio` client must not disable SSL certificate verification. No `BadCertificateCallback` overrides that return `true`. The Edge Function URL must be validated as `https://` scheme at startup.
- **No logging of journal content in release**: dio's `LogInterceptor` (if used) must be conditional on `kDebugMode`. Never log request/response bodies containing journal content in release builds.
- **PATH requirement**: Every shell command using `flutter` or `dart` must include: `export PATH="$PATH:/c/src/flutter/bin"`
- **Windows/Git Bash**: Shell environment is Git Bash on Windows 11. Use Unix syntax.
- **Comment thoroughly**: Inline explanations for new patterns (dio, connectivity, Edge Function concepts)
- **No breaking changes to existing tests**: Phase 1 and 2 tests must continue to pass

## Requirements

### Functional

- R1: Supabase Edge Function `claude-proxy` accepts conversation messages and returns Claude API responses
- R2: Edge Function injects the journaling system prompt server-side (not sent from client)
- R3: Edge Function stores Claude API key as a Supabase secret — never in source code
- R4: `ClaudeApiService` in Flutter makes HTTP calls to the Edge Function via `dio`
- R5: `AgentRepository` methods become async; use Claude when online, rule-based when offline
- R6: Greeting generation uses Claude when online (context-aware: time-of-day, days since last session, session count)
- R7: Follow-up questions come from Claude's conversational response when online
- R8: Session end triggers Claude to produce structured metadata: summary, mood_tags, people, topic_tags
- R9: Structured metadata is parsed and stored in the JournalSession record (fields already exist in drift schema)
- R10: Connectivity detection determines online/offline status before each LLM call
- R11: All LLM calls have a configurable timeout (default: 30 seconds) with fallback to Layer A
- R12: Environment configuration (Edge Function URL, anon key) is externalized — not hardcoded

### Non-Functional

- NF1: Claude API latency is masked with a loading indicator in the chat UI
- NF2: Fallback from LLM to rule-based is invisible to the user (no error dialogs for network failures)
- NF3: No regression in existing test suite (Phase 1 + Phase 2 tests pass)
- NF4: New code has >= 80% test coverage

## Acceptance Criteria

- [ ] AC1: Edge Function deployed and callable — `curl` to the function URL with a messages array returns a Claude response
- [ ] AC2: When online, user messages get natural Claude-generated follow-ups (not keyword-based)
- [ ] AC3: When offline (airplane mode), user messages get rule-based follow-ups identically to Phase 1
- [ ] AC4: When online and session ends, the session record has AI-generated summary, mood_tags, people, and topic_tags
- [ ] AC5: When offline and session ends, the session record has the local summary (Phase 1 behavior)
- [ ] AC6: A network timeout during a Claude call falls back to rule-based within 30 seconds (no hang)
- [ ] AC7: Claude API key is NOT present in any Dart file, pubspec.yaml, or committed config file
- [ ] AC8: Chat UI shows a typing/loading indicator while waiting for Claude's response
- [ ] AC9: All Phase 1 and Phase 2 tests still pass
- [ ] AC10: New tests cover: ClaudeApiService (mocked), connectivity detection, AgentRepository online/offline branching, SessionNotifier async flow, structured metadata parsing

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Edge Function deployment issues (Supabase CLI, Deno unfamiliarity) | Medium | High | Provide step-by-step deployment guide; test locally with `supabase functions serve` |
| Claude API rate limiting | Medium | Low | Edge Function returns graceful error; client falls back to Layer A |
| Response parsing failures (Claude returns unexpected format) | Medium | Medium | Defensive parsing: strip code fences, try/catch jsonDecode, null metadata on failure, session end completes normally |
| Breaking existing tests when making AgentRepository async | High | High | **Mandatory**: update all existing test assertions to `await` async methods. Override agentRepositoryProvider with mocks in session_notifier tests. |
| Network latency degrading UX | Medium | High | Loading indicators, 30s timeout, immediate fallback |
| Unauthenticated Edge Function abuse (cost amplification) | Medium | Medium | **Accepted risk** for Phase 3: 50KB payload cap + Supabase project rate limits. Phase 4 JWT auth is the real gate. |
| Prompt injection from journal entries | Low (Phase 3) | Medium | Single-user self-attack in Phase 3. Use Anthropic API `system` parameter (not concatenated). Phase 5 RAG must sanitize retrieved content. |
| Journal content exposure in transit | Medium | Low | TLS enforced (Supabase + dio). No SSL bypass. No release-mode logging of request/response bodies. |

## Affected Components

### New Files
- `supabase/functions/claude-proxy/index.ts` — Deno Edge Function
- `supabase/functions/claude-proxy/index_test.ts` — Deno unit tests for Edge Function
- `lib/services/claude_api_service.dart` — dio HTTP client to Edge Function
- `lib/services/connectivity_service.dart` — Online/offline detection
- `lib/config/environment.dart` — Edge Function URL, anon key, timeout config (via `--dart-define`)
- `lib/models/agent_response.dart` — AgentResponse, AgentLayer, AgentMetadata types
- `.env.example` — Documents required `--dart-define` flags
- `test/services/claude_api_service_test.dart` — ClaudeApiService unit tests (9 cases)
- `test/services/connectivity_service_test.dart` — ConnectivityService tests
- `test/config/environment_test.dart` — Environment config tests
- `test/repositories/agent_repository_test.dart` — Updated agent tests for async + online/offline branching

### Modified Files
- `pubspec.yaml` — add dio, connectivity_plus
- `lib/repositories/agent_repository.dart` — async methods, ClaudeApiService integration, connectivity check
- `lib/providers/session_providers.dart` — SessionNotifier async agent calls, structured metadata handling
- `lib/providers/database_provider.dart` — add new service providers
- `lib/ui/screens/journal_session_screen.dart` — loading indicator while awaiting Claude response
- `lib/main.dart` — initialize connectivity monitoring

### Unchanged (verify no regression)
- `lib/database/` — tables, DAOs, app_database (schema already has summary/mood/people/topic fields)
- `lib/utils/keyword_extractor.dart` — still used by Layer A fallback
- Phase 2 files — assistant_registration_service, onboarding, settings

## Dependencies

- **Supabase project**: Must have a Supabase project created with Edge Functions enabled
- **Claude API key**: Must be stored as a Supabase secret (`ANTHROPIC_API_KEY`)
- **Supabase CLI**: Needed to deploy the Edge Function (`supabase functions deploy`)
- **Internet access**: Required for testing LLM mode (offline mode can be tested without)

## Task Breakdown

### Task 1: Add Dependencies
Add `dio` and `connectivity_plus` to `pubspec.yaml`. Run `flutter pub get`.

### Task 2: Create Environment Configuration
Create `lib/config/environment.dart` with externalized configuration for the Edge Function URL, anon key, and timeouts. Use `String.fromEnvironment` with `--dart-define` for compile-time injection.

**Important**: `String.fromEnvironment` bakes values into the compiled binary — they are extractable from the APK via `strings` or apktool. This is acceptable because:
- The Supabase anon key is semi-public by design (RLS enforces access control, not the key)
- The genuine secret is the `ANTHROPIC_API_KEY` inside the Edge Function, which never reaches the client
- Phase 4 adds JWT-based auth for the real access control layer

The `environment.dart` class must: (a) validate that the Edge Function URL scheme is `https://` (assert in debug, fail-safe to disabled in release), (b) provide `isConfigured` getter (false when URL is empty/missing), (c) be overridable in tests. If `ClaudeApiService` detects `!environment.isConfigured`, it disables itself and the app uses Layer A exclusively.

Document the required `--dart-define` flags in a `.env.example` file.

### Task 3: Create Supabase Edge Function
Create `supabase/functions/claude-proxy/index.ts`:
- Accept POST with `{ messages: [{role, content}...], context?: {time_of_day, days_since_last, session_count}, mode: "chat" | "metadata" }`
- The `mode` field distinguishes conversational follow-ups (`chat`) from end-of-session metadata extraction (`metadata`). Single endpoint, discriminated by mode.
- Inject the journaling system prompt (defined in the function, not sent from client). Use the Anthropic API's `system` parameter for the system prompt — never concatenate it into user messages.
- Call Claude API using `ANTHROPIC_API_KEY` secret
- Return `{ response: string, metadata?: { summary, mood_tags, people, topic_tags } }`
- **Input validation** (security-specialist requirement):
  - Validate `messages` array is non-empty and total content length is under 50KB
  - Validate `mode` is one of the expected values
  - Return 400 with structured error JSON for invalid input
- **Auth header future-proofing**: Check for `Authorization: Bearer <jwt>` header. If present, validate using Supabase JWT verification. If absent, proceed without auth (Phase 3 behavior). Phase 4 changes this to reject unauthenticated requests.
- **Rate limiting**: Acknowledge that without auth, the Edge Function is callable by anyone with the anon key. Mitigation for Phase 3: Supabase project-level rate limiting + the 50KB payload cap. This is an **accepted risk** for the development/personal-use phase. Phase 4 JWT auth is the real gate.
- Handle errors gracefully (return structured error JSON, never expose API key or internal errors)
- **Prompt injection awareness**: For Phase 3 (single-user), prompt injection from journal entries is a self-attack. Note for Phase 5: when RAG retrieves past journal content as Claude context, that content must be sanitized before injection (stored prompt injection vector).

Also create basic Deno unit tests in `supabase/functions/claude-proxy/index_test.ts`:
- Happy path: valid messages → response with metadata
- Missing/invalid messages body → structured 400 error
- Claude API error (mocked fetch) → structured error, no key leakage
- Error response does not contain `ANTHROPIC_API_KEY`, `sk-`, or env var names

### Task 4: Create ConnectivityService
Create `lib/services/connectivity_service.dart`:
- Wrap `connectivity_plus` to expose `isOnline` property
- Stream-based connectivity monitoring
- Riverpod provider for access throughout the app

### Task 5: Create ClaudeApiService
Create `lib/services/claude_api_service.dart`:
- Use `dio` to POST conversation messages to the Edge Function
- **TLS enforcement**: Configure `BaseOptions` without disabling SSL verification. No `BadCertificateCallback` overrides. Validate URL is HTTPS at construction time.
- **Logging**: Only add `LogInterceptor` when `kDebugMode` is true. Never log request/response bodies in release builds.
- Parse response: extract chat message + optional structured metadata
- **Defensive metadata parsing**: Strip markdown code fences before JSON parse. Use `try/catch` around `jsonDecode`. Validate expected top-level keys exist. On any parse failure: log raw response (debug only), return null metadata, do not throw. The session end flow must complete normally even with failed metadata extraction.
- Configurable timeout (default 30s)
- Return typed `AgentResponse` objects: `AgentResponse({required String content, required AgentLayer layer, AgentMetadata? metadata})`
  - `AgentLayer` enum: `ruleBasedLocal`, `llmRemote`
  - `AgentMetadata`: `{String? summary, List<String>? moodTags, List<String>? people, List<String>? topicTags}`
- Throw typed exceptions on failure (network error, timeout, parse error for the response itself — not metadata)
- Expose `isConfigured` getter that checks environment config

### Task 6: Make AgentRepository Async with LLM Integration
Update `lib/repositories/agent_repository.dart`:
- Add optional `ClaudeApiService` and `ConnectivityService` constructor parameters
- Make `getGreeting()`, `getFollowUp()`, `generateSummary()` return `Future<AgentResponse>`
- Decision logic: if Claude service available AND online → use LLM; if LLM call throws (timeout, network error, parse error) → fall back to rule-based. This means connectivity flapping mid-request is handled by the catch path, not just the pre-check.
- Return `AgentResponse` (defined in Task 5) that indicates which layer served the request
- Keep all existing rule-based logic as private methods (Layer A fallback)
- **Phase 5 note** (architecture-consultant advisory): When Layer C is added, evaluate whether layer dispatch should be extracted into a separate strategy class. For Phase 3's two layers, the single-class approach is correct per Principle #8.

**CRITICAL — Test migration** (qa-specialist blocking finding): Making methods async changes return types from `String` to `Future<String>`. In Dart, un-awaited `Future` objects satisfy assertions like `expect(future, isNotEmpty)` without error, creating silent false-passing tests. **All existing tests in `agent_repository_test.dart` must be updated to `await` the new async methods.** This is a mandatory part of Task 6, not deferred to Task 10.

### Task 7: Update SessionNotifier for Async Agent
Update `lib/providers/session_providers.dart`:
- `startSession()` — set `isWaitingForAgent = true` **immediately** (before the greeting fetch, not after), await async greeting from agent, then clear the flag. This ensures the UI shows a loading indicator during the greeting fetch, not just follow-ups.
- `sendMessage()` — set `isWaitingForAgent = true`, await async follow-up from agent, clear flag. Handle stale responses: if `activeSessionId` is null when the response arrives (user ended session during wait), discard the response.
- `endSession()` — async summary + metadata from agent, store metadata in session record. On metadata parse failure, null all metadata fields and complete normally.
- Parse structured metadata (mood_tags, people, topic_tags) from `AgentResponse.metadata` and store in the session record via `SessionDao.endSession()`
- Update `SessionState` with an `isWaitingForAgent` flag for UI loading indicator

**Test migration**: Existing `session_notifier_test.dart` must override `agentRepositoryProvider` with a mock after Phase 3 modifies the real `AgentRepository`. Without this, tests become environment-dependent (pass online, fail offline).

### Task 8: Update Providers
Update `lib/providers/database_provider.dart` or create new provider file:
- `connectivityServiceProvider` — singleton ConnectivityService
- `claudeApiServiceProvider` — singleton ClaudeApiService (depends on environment config)
- Update `agentRepositoryProvider` — inject ClaudeApiService and ConnectivityService

### Task 9: Update Chat UI
Update `lib/ui/screens/journal_session_screen.dart`:
- Show a typing/loading indicator when `isWaitingForAgent` is true
- Disable send button while waiting for response
- No error dialogs on network failure — the fallback is transparent

### Task 10: Tests
Write comprehensive tests:
- `ClaudeApiService` with mocked dio:
  - Success (chat mode + metadata mode)
  - Timeout → typed exception
  - Network error → typed exception
  - HTTP 200 but `response` field is null → fallback trigger
  - HTTP 200 but `response` field is empty string → fallback trigger
  - HTTP 200 but `metadata.mood_tags` is wrong type (string not array) → graceful handling
  - HTTP 200 but `metadata` key missing entirely → response with null metadata
  - HTTP 200 but body has no `response` key → typed exception
  - HTTP 429 (rate limit) → typed exception, triggers fallback
- `ConnectivityService` with mocked connectivity_plus: online, offline, transition
- `AgentRepository` async:
  - Online path (mock Claude success) → returns AgentResponse with layer=llmRemote
  - Offline path (connectivity false) → returns AgentResponse with layer=ruleBasedLocal
  - Online but dio throws connectionError mid-request → falls back to rule-based (the connectivity flapping case)
  - Environment not configured (isConfigured=false) → rule-based only
- `SessionNotifier` with mocked async agent:
  - Full conversation flow (start → messages → end) with mocked Claude responses
  - Metadata storage: assert specific parsed values for mood_tags, people, topic_tags (not just null checks)
  - Offline path: assert metadata fields are null when Layer A serves
  - Loading state: assert `isWaitingForAgent=true` immediately after sendMessage, false after completion
  - Stale response: endSession called while sendMessage awaiting → response discarded
- Widget: Chat loading indicator visible when `isWaitingForAgent`, send button disabled
- `Environment` config: assert behavior when `--dart-define` values are absent (isConfigured=false)
- Regression: verify all Phase 1 + Phase 2 tests still pass

### Task 11: Edge Function Deno Tests
Write Deno unit tests in `supabase/functions/claude-proxy/index_test.ts` (created alongside Task 3 but run separately):
- Happy path: valid messages → response with metadata
- Missing/invalid messages body → 400 structured error
- Claude API error (mocked) → structured error, no key leakage
- Error response body does not contain API key string or env var names
- Input validation: oversized payload (>50KB) → 400
- Input validation: invalid mode value → 400

These run with `deno test`, not `flutter test`.

## System Prompt (for Edge Function)

```
You are a personal journal assistant. Your role is to help the user capture
their day through natural, warm conversation.

Rules:
- Ask 2-3 focused follow-up questions to draw out details
- Focus on: what happened, how they felt, who they were with, what they learned
- Be warm but concise — keep questions focused, one at a time
- When the user seems done, provide a brief summary of what was captured
- Do NOT invent or assume details the user didn't mention
- Keep each response under 100 words

Context:
- Time of day: {time_of_day}
- Days since last journal session: {days_since_last}
- Total session count: {session_count}
```

## Structured Metadata Extraction

After the conversation ends, send a separate Claude call (or parse from the final message) with:

```
Based on this journal conversation, extract the following as JSON:
{
  "summary": "2-3 sentence summary of what was discussed",
  "mood_tags": ["list", "of", "moods"],
  "people": ["names", "mentioned"],
  "topic_tags": ["themes", "discussed"]
}

Only include items that were explicitly mentioned. Do not invent or infer.
```

## Test Strategy

| Test Type | What | Tool |
|-----------|------|------|
| Unit | ClaudeApiService: success, timeout, error, malformed responses (9 cases) | mockito + dio mock |
| Unit | ConnectivityService: online, offline, transition | mockito |
| Unit | AgentRepository: online/LLM, offline/rule-based, mid-request fallback, unconfigured | mockito |
| Unit | SessionNotifier: async flow, metadata storage, loading state, stale response handling | mockito + in-memory drift |
| Unit | Structured metadata parsing: valid JSON, missing fields, wrong types, code fences | direct |
| Unit | Environment config: configured, missing dart-define, invalid URL scheme | direct |
| Unit (Deno) | Edge Function: happy path, validation, error handling, key non-leakage | deno test |
| Widget | Chat loading indicator, disabled send button | flutter_test |
| Integration | Full conversation flow (mocked Claude) | flutter_test |
| Regression | All Phase 1 + Phase 2 tests (with provider overrides for determinism) | flutter test |
| Manual | Edge Function deployment + real Claude call | curl / app on device |

## New Files Summary

- `supabase/functions/claude-proxy/index.ts` — Edge Function
- `supabase/functions/claude-proxy/index_test.ts` — Deno unit tests
- `lib/config/environment.dart` — Compile-time config via `--dart-define`
- `lib/services/claude_api_service.dart` — dio HTTP client
- `lib/services/connectivity_service.dart` — Online/offline detection
- `lib/models/agent_response.dart` — `AgentResponse`, `AgentLayer`, `AgentMetadata` types
- `.env.example` — Documents required `--dart-define` flags
- `test/services/claude_api_service_test.dart`
- `test/services/connectivity_service_test.dart`
- `test/repositories/agent_repository_test.dart` (updated)
- `test/config/environment_test.dart`

## Specialist Review Notes

Three specialists reviewed this spec at risk level HIGH:

**architecture-consultant** (confidence 0.87, REVISE → resolved):
- BLOCKING: Missing decision record for ConversationAgent interface deferral → **Added** "Design Decision" section to Context
- Advisory: AgentRepository taking on connectivity dispatch is a boundary tension with established service/repository split, but ADR-0006 endorses it → **Added** Phase 5 re-evaluation note
- Advisory: Define AgentResponse return type → **Added** to Task 5
- Advisory: Commit to `--dart-define` → **Added** to Task 2 with rationale
- Advisory: Single endpoint with mode discriminant → **Added** to Task 3

**security-specialist** (confidence 0.87, REVISE → resolved):
- BLOCKING: Edge Function input validation → **Added** payload size cap, input validation requirements to Task 3
- BLOCKING: TLS enforcement → **Added** to Constraints + Task 5
- BLOCKING: Auth header format → **Added** to Task 3 + Constraints
- Advisory: Prompt injection documented → **Added** to Task 3 + Risk Assessment
- Advisory: `String.fromEnvironment` secrecy clarification → **Added** to Task 2
- Advisory: dio logging restriction → **Added** to Constraints + Task 5
- Advisory: Metadata parse failure handling → **Added** to Task 5 + Task 7

**qa-specialist** (confidence 0.88, REVISE → resolved):
- BLOCKING: Async test migration will silently break existing tests → **Added** mandatory migration note to Task 6
- BLOCKING: Edge Function needs automated tests → **Added** Task 11 (Deno tests) + test requirements to Task 3
- BLOCKING: session_notifier_test must mock agent provider → **Added** to Task 7 + Task 10
- Advisory: Malformed response tests → **Added** to Task 10 (9 ClaudeApiService test cases)
- Advisory: Connectivity flapping test → **Added** to Task 10 (mid-request fallback case)
- Advisory: Widget test specification → **Added** to Task 10
- Advisory: Metadata assertion specificity → **Added** to Task 10
