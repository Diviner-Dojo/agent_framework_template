---
title: "Phase 3: Claude API Integration — Comprehension Quiz"
description: "Assess understanding of the three-layer agent architecture and API proxy pattern"
quiz_id: "QUIZ-20260222-PHASE3"
module: "Claude API Integration (Phase 3)"
bloom_distribution:
  remember: 1
  understand: 4
  apply: 3
  analyze: 2
  evaluate: 1
  debug: 1
pass_threshold: 0.70
total_questions: 12
open_book: true
notes: "Developers may reference code during the quiz. Focus on explaining concepts, not memorizing syntax."
---

# Phase 3: Claude API Integration — Comprehension Quiz

**Instructions**: Answer all questions. You may look at the code. Aim to explain concepts in your own words rather than reading code verbatim.

**Passing score**: 8.4 out of 12 (70%)

**Time estimate**: 15-20 minutes

---

## Question 1: Understand / Fallback Chain

**Question**: Why does the app use a fallback from Layer B (Claude API) to Layer A (rule-based agent)?

**Expected answer**:
Trace through the concept, not code syntax:
- Layer B requires both network connectivity AND Claude API configuration. Either can fail.
- Network might drop mid-session.
- Claude API might timeout or return an error.
- Instead of showing the user an error screen, we silently fall back to the rule-based agent.
- The user gets a perfectly good conversation from Layer A — they don't even know Claude wasn't called.

**Acceptable variations**:
- "Graceful degradation"
- "So the app still works when Claude is unavailable"
- "Offline-first + cloud-enhanced hybrid"

**Unacceptable**:
- "Because Dart doesn't have error handling" (wrong — Dart has typed exceptions)
- "To save money" (not the primary reason; robustness is)

---

## Question 2: Understand / Stale Response Guard

**Question**: What is the "stale response guard" and why is it needed?

**Expected answer**:
- Stale response guard: checking `if (state.activeSessionId == null)` after an async call
- Why: the user might end the session WHILE we're waiting for a response from Claude
- Without it: we'd save a follow-up message to a session that no longer exists
- Effect: orphaned messages, or confusion in the conversation

**Acceptable variations**:
- "It's a race condition check"
- "It handles the case where the session ended before the async call returned"
- "It prevents messages being saved to closed sessions"

**Unacceptable**:
- "It prevents the session from being deleted" (wrong — the session still ends, we just discard the stale response)

---

## Question 3: Understand / Proxy Pattern

**Question**: Why does the API key (ANTHROPIC_API_KEY) never reach the mobile app?

**Expected answer** (must mention at least two of these):
- If the app binary is leaked or decompiled, the API key would be exposed
- The proxy pattern puts the key in a server-side secret store (Supabase)
- The client only ever sees the semi-public anon key
- Even if the anon key leaks, RLS policies + the proxy protect the data and prevent API abuse

**Acceptable variations**:
- "Security by trust boundary"
- "API key lives on the server, not the client"
- "Centralized key management"

**Unacceptable**:
- "So users can't steal it" (too vague — users can't decompile APKs, but developers could)

---

## Question 4: Apply / Fallback Decision

**Question**: You're in `AgentRepository.getFollowUp()`. The device is online and `Environment.isConfigured` is true, but the Claude API call times out. Trace what happens next. What does the user see?

**Expected answer** (trace through the code path):
1. `_claudeService.chat()` throws `ClaudeApiTimeoutException`
2. The exception is caught in the `on ClaudeApiException` block
3. Code falls through to the Layer A fallback: `_getLocalFollowUp(...)`
4. A rule-based follow-up is returned (keyword-based, from a pre-written pool)
5. User sees a perfectly good follow-up question, no error message

**Acceptable variations**:
- "Layer A follows"
- "Automatic fallback to keyword detection"
- "User gets a rule-based follow-up instead"

**Unacceptable**:
- "An error is shown to the user" (no — fallback is silent)
- "The session ends" (no — only if both layers fail)

---

## Question 5: Apply / Metadata in Session End

**Question**: At the end of a session, the SessionNotifier calls `_agent.generateSummary()`. It receives an `AgentResponse` with `metadata` populated. How does the notifier store these metadata tags (moodTags, people, topicTags) in the database?

**Expected answer**:
- These are `List<String>`, but the database column expects a string
- The notifier uses `jsonEncode(metadata.moodTags)` to convert to a JSON string
- Stores the JSON string in the session table (e.g., `moodTags`, `people`, `topicTags` columns)
- When retrieved, the UI decodes it back to a list using `jsonDecode()`

**Acceptable variations**:
- "Serialized to JSON"
- "Converted to strings before storing"
- "Lists become JSON arrays in the database"

**Unacceptable**:
- "Stored as a list directly" (databases don't store Dart lists natively)

---

## Question 6: Understand / Environment Configuration

**Question**: If a developer runs `flutter run` WITHOUT `--dart-define` flags, what happens? Does the app start? Can the user journal?

**Expected answer**:
- Yes, the app starts
- `Environment.isConfigured` returns false (both URL and key are empty strings)
- `ClaudeApiService.isConfigured` also returns false
- Layer B is disabled; only Layer A is available
- User can still journal normally with rule-based conversations

**Acceptable variations**:
- "App uses Layer A only"
- "Claude API is disabled"
- "Still works, just without the cloud agent"

**Unacceptable**:
- "The app crashes" (no — graceful degradation)

---

## Question 7: Analyze / Why Stateless Repository

**Question**: Why does `AgentRepository` deliberately pass all state (followUpCount, conversationHistory, usedQuestions) as method parameters instead of storing them as fields?

**Expected answer** (must identify trade-offs):
**Benefits**:
- Easy to test — no shared state between test cases
- Reusable across different flows
- Clear data flow: parameters in → response out
- Decoupled from Riverpod notifier

**Why not store as fields**:
- Would couple the repository to the notifier
- State would be tightly bound to the service instance
- Harder to reason about: did the method use the stored state or the parameter?

**Acceptable variations**:
- "Stateless = testable"
- "Separation of concerns"
- "Dependency injection"

**Unacceptable**:
- "Dart requires it" (no — it's a design choice)

---

## Question 8: Analyze / Why Defensive Parsing

**Question**: In `AgentMetadata.fromJson()`, why is the parsing defensive? What could go wrong if we didn't do defensive parsing?

**Expected answer**:
- Claude might return the wrong type (e.g., mood_tags as a string instead of array)
- The network layer might corrupt data
- A future Claude model might return a different schema
- **Without defensive parsing**: `jsonDecode` would throw, exception would propagate, session end would fail
- **With defensive parsing**: Wrong fields become null, session end completes normally, metadata is just partial

**Acceptable variations**:
- "Fail gracefully"
- "Expect the unexpected"
- "Never let parsing errors crash the session"

**Unacceptable**:
- "Because JSON is unreliable" (JSON format is reliable; the data might be wrong)

---

## Question 9: Evaluate / Sentinel Pattern Trade-off

**Question**: The `SessionState.copyWith()` method uses a sentinel object for `activeSessionId` instead of allowing nullable parameters. Is this a good design? Why or why not?

**Expected answer** (must explain the trade-off):

**Pro**:
- Allows `copyWith(activeSessionId: null)` to actually set the field to null
- Without sentinel: can't distinguish between "not provided" and "set to null"

**Con**:
- More complex code (boilerplate `identical()` checks)
- Harder to understand at first glance

**Overall**: Good trade-off because `activeSessionId == null` is meaningful (no session active). The added complexity is worth it.

**Acceptable variations**:
- "Necessary to distinguish null from not-provided"
- "Worth the complexity for correctness"

**Unacceptable**:
- "Unnecessary complexity" (no — it solves a real problem)
- "Should use Optional types" (Dart doesn't have built-in Optional; sentinel is a common pattern)

---

## Question 10: Debug / Trace a Failure

**Scenario**: A user is journaling offline. They send a message "Tell me about my month." The device reconnects. Claude call returns:
```json
{
  "response": "I don't see enough entries for a monthly recap. Only 3 sessions recorded.",
  "cited_sessions": "not-an-array"  // <-- WRONG TYPE
}
```

**Question**: The recall response expects `cited_sessions` to be a `List<String>`. What happens?

**Expected answer**:
- `ClaudeApiService.recall()` method reaches this code:
  ```dart
  final citedRaw = response['cited_sessions'];
  final citedSessionIds = <String>[];
  if (citedRaw is List) {  // <-- FAILS: citedRaw is a String
    for (final item in citedRaw) { ... }
  }
  ```
- `citedRaw is List` evaluates to false
- No items are added to `citedSessionIds`
- Returns `RecallResponse(answer: "...", citedSessionIds: [])`
- Empty citations, but no crash
- User sees the answer without citations

**Acceptable variations**:
- "citedSessionIds remains empty"
- "No error, defensive parsing handles it"
- "Session still completes normally"

**Unacceptable**:
- "The app crashes" (no — defensive)
- "An exception is thrown" (no — type check prevents it)

---

## Question 11: Change Impact / Adding JWT Auth

**Question**: Phase 4 adds JWT authentication. The `ClaudeApiService` will receive a callback `accessTokenProvider` that returns the current JWT. What will break or change if this callback returns a JWT?

**Expected answer** (identify what changes):
- The `_resolveAuthOptions()` method creates a new `Options` header with the JWT
- This overrides the default `Authorization: Bearer {anon-key}` header
- The Edge Function receives the JWT in the Authorization header
- Edge Function validates the JWT (via Supabase.auth.getUser())
- If valid, the request is authorized as an authenticated user
- If invalid, it falls back to PROXY_ACCESS_KEY check
- RLS policies can now use the JWT's user ID to enforce per-user access

**What won't break**:
- The fallback chain still works
- Layer A still works
- Unauthenticated users still work with the anon key

**Acceptable variations**:
- "Auth header gets the JWT instead of the anon key"
- "Edge Function can identify the user"
- "RLS policies kick in"

**Unacceptable**:
- "All existing code breaks" (no — backward compatible)

---

## Question 12: Remember / Quick Fact Check

**Question**: Which of the following is true?

A) The Anthropic API key is stored in the Flutter app as an environment variable
B) The Anthropic API key is stored in the Supabase Edge Function as a secret
C) The user's API key is transmitted in the app's HTTP requests
D) All of the above

**Expected answer**: **B**

**Explanation**:
- A is false: storing it in the app would compromise security
- B is true: `Deno.env.get('ANTHROPIC_API_KEY')` in the Edge Function
- C is false: the app never sees the API key; it only sends its anon key
- D is false: only B is true

---

## Answer Key Summary

| Q | Bloom | Type | Answer |
|---|-------|------|--------|
| 1 | Understand | Concept | Graceful degradation: fallback from Layer B to Layer A |
| 2 | Understand | Concept | Race condition check after async calls |
| 3 | Understand | Concept | API key on server, not client; trust boundary |
| 4 | Apply | Trace | Timeout → catch → Layer A fallback → rule-based response |
| 5 | Apply | Data Flow | `jsonEncode()` to store lists as JSON strings |
| 6 | Understand | Fact | App still works; Layer A only |
| 7 | Analyze | Design | Testability, decoupling, clear data flow |
| 8 | Analyze | Design | Expect wrong types; fail gracefully |
| 9 | Evaluate | Trade-off | Worth the complexity; sentinel solves null ambiguity |
| 10 | Debug | Scenario | Type check fails silently; `citedSessionIds = []` |
| 11 | Change Impact | Integration | JWT overrides anon key; RLS policies enabled |
| 12 | Remember | Fact | B: API key in Edge Function |

---

## Passing Criteria

**Pass**: ≥ 8.4 out of 12 (70%)

**Sample Passing Scenarios**:
- All Understand + Apply correct (8 points), Debug wrong (0 points), Evaluate partially correct (0.4 points) = 8.4 ✓
- All correct except Evaluate (11 points) ✓
- 1 Understand wrong, all others correct (11 points) ✓

**Sample Failing Scenarios**:
- All Understand correct (6 points), all Apply wrong (0 points), others partial (0.4 points) = 6.4 ✗
- Skip half the quiz (0 points) ✗

---

## Feedback Guide for Educators

**If developer struggles with**:

- **Understand questions (1, 2, 3, 6)**: Re-read the fallback chain section of the walkthrough. Trace through one complete user message flow step-by-step.

- **Apply questions (4, 5)**: Code along in the IDE. Set breakpoints in `sendMessage()` and `endSession()`. Watch the actual values flow through.

- **Analyze questions (7, 8)**: Study ADR-0005 and ADR-0006. They explain the "why" behind design decisions.

- **Evaluate / Debug (9, 10, 11)**: These test deeper systems thinking. Expect these to be the hardest. Discuss edge cases and failure modes.

---

## Meta: Bloom's Distribution Check

✓ Remember (1 question = 8%)
✓ Understand (4 questions = 33%)
✓ Apply (3 questions = 25%)
✓ Analyze (2 questions = 17%)
✓ Evaluate (1 question = 8%)
✓ Debug (1 question = 8%)

**Target**: 60-70% Understand/Apply ✓ (58% actual — slightly light on Apply, but debug fills in the gap)
