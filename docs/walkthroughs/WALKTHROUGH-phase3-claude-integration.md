---
title: "Phase 3: Claude API Integration — Guided Walkthrough"
description: "Learn how the agentic journal integrates Claude API for enhanced conversations"
last_updated: "2026-02-22"
target_audience: "Developers new to Android/Flutter or the codebase"
estimated_duration: "10-15 minutes"
---

# Phase 3: Claude API Integration — Guided Walkthrough

## Welcome

You're about to understand how we layer a cloud-powered AI agent (Claude) on top of a rule-based local agent, so that journal conversations adapt based on network availability. By the end, you'll see how a user message flows from the UI all the way through the Claude API and back.

The key insight: **Your app never touches the API key.** It lives on the server. The app is a client that calls a proxy function, which is the gatekeeper between the mobile app and Claude.

---

## Part 1: The Big Picture (2 min)

### Three-Layer Agent System (ADR-0006)

The conversation engine has three layers:

- **Layer A (Rule-Based, Offline)**: Keyword detection, hardcoded follow-up pools, time-of-day greetings. Always works. Simple, predictable.
- **Layer B (Claude API, Online)**: Calls Claude for natural, context-aware responses. Richer, personalized. Only when network + config available.
- **Layer C (Intent Classification, Future)**: Phase 5 will add smart routing — "is the user asking a question or journaling?"

### Graceful Degradation

If Claude is unavailable (offline, not configured, timeout, error), **the app automatically falls back to Layer A**. The user never sees an error screen. They get a perfectly good conversation, just from a simpler agent.

Here's the fallback chain:
```
1. Check: is Claude API configured AND online?
   ├─ YES → Try Claude API call
   │  ├─ Success → Return Layer B response
   │  └─ Failure (timeout/network/parse) → Fall through to step 2
   └─ NO → Skip to step 2
2. Use Layer A (rule-based) → Always returns something
```

---

## Part 2: Architecture Overview (3 min)

Five key modules work together. They're arranged in a strict flow: **data travels down, never up**. This keeps the dependency graph clean.

```
┌─────────────────────────────────────────────────────────────┐
│  UI Layer (journal_session_screen.dart)                     │
│  Displays messages, sends text, shows loading indicator     │
└──────────────────────┬──────────────────────────────────────┘
                       │ calls
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  State Management (session_providers.dart)                  │
│  SessionNotifier: orchestrates greeting → message → summary │
│  Owns: activeSessionId, followUpCount, conversationHistory  │
└──────────────────────┬──────────────────────────────────────┘
                       │ calls
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent Repository (agent_repository.dart)                   │
│  The "brain": switches between Layer A and Layer B          │
│  Receives: latest message, conversation history, context    │
│  Returns: AgentResponse (content + layer tag + metadata)    │
└──────────────────────┬──────────────────────────────────────┘
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
    ┌────────────┐          ┌──────────────────┐
    │  Layer A   │          │  Layer B: Service │
    │ (Stateless)│          │ (claude_api_....)│
    │ Keywords   │          │ HTTP Client      │
    └────────────┘          └──────────────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ Supabase Edge Fn │
                            │ (claude-proxy)   │
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │  Claude API      │
                            │  (anthropic.com) │
                            └──────────────────┘
```

**Golden rule**: AgentRepository is stateless. All conversation state (followUpCount, used questions, message history) lives in SessionNotifier. The repository receives these as parameters.

---

## Part 3: Module-by-Module Walk (5 min)

### 1. Environment Configuration (`lib/config/environment.dart`)

**Purpose**: Externalize the Supabase URL and API key. They're baked into the binary at compile time via `--dart-define` flags.

**Key code pattern**:
```dart
// Developers build the app like this:
//   flutter run \
//     --dart-define=SUPABASE_URL=https://abc.supabase.co \
//     --dart-define=SUPABASE_ANON_KEY=eyJ...

// Inside environment.dart:
const Environment({
  this.supabaseUrl = const String.fromEnvironment('SUPABASE_URL'),
  this.supabaseAnonKey = const String.fromEnvironment('SUPABASE_ANON_KEY'),
  ...
});
```

**Why no secrets here?** The anon key is semi-public by design — Supabase uses Row-Level Security to enforce access control, not the key itself. The real secret (ANTHROPIC_API_KEY) never leaves the server. It lives in Supabase as an environment variable and is only used server-side in the Edge Function.

**Safety check**: `isConfigured` getter returns false if either value is empty. When false, the app disables Layer B and uses Layer A only.

---

### 2. Response Types (`lib/models/agent_response.dart`)

**Purpose**: Unified type for both Layer A and Layer B responses.

**Key insight**: The caller (SessionNotifier) doesn't care which layer served the response. It's all `AgentResponse`:

```dart
class AgentResponse {
  final String content;              // The actual message
  final AgentLayer layer;            // Which layer produced this
  final AgentMetadata? metadata;     // Only populated by Layer B
}
```

**AgentMetadata** is only populated when Claude successfully extracts structure at session end:
- `summary`: Claude-generated summary
- `moodTags`, `people`, `topicTags`: extracted entities

All fields are nullable because Layer A doesn't produce this. If Claude fails to parse, all fields are null — the app still completes the session normally.

**Defensive parsing**: `AgentMetadata.fromJson()` uses safe type checks. If a field has the wrong type (e.g., mood_tags is a string instead of list), that field silently becomes null instead of throwing.

---

### 3. HTTP Client (`lib/services/claude_api_service.dart`)

**Purpose**: Transport layer. Makes POST requests to the Supabase Edge Function.

**Typed exceptions** — catch specific types:
- `ClaudeApiNotConfiguredException`: config missing
- `ClaudeApiTimeoutException`: request took too long
- `ClaudeApiNetworkException`: connection failed
- `ClaudeApiServerException`: Edge Function returned an error
- `ClaudeApiParseException`: response missing required fields

**Three modes** match the Edge Function:

1. **`chat()`**: Send a message, get a follow-up response
2. **`extractMetadata()`**: Send full conversation, get summary + tags
3. **`recall()`**: Phase 5 memory query with journal context

**Key security features**:
- TLS enforcement (no SSL bypass)
- Header logging disabled in release builds (never log journal content)
- JWT injection when user is authenticated (Phase 4)

Example:
```dart
// Layer B: try Claude
final response = await _claudeService.chat(
  messages: [{'role': 'user', 'content': 'Tell me more about that.'}],
);
```

---

### 4. Connectivity Service (`lib/services/connectivity_service.dart`)

**Purpose**: Point-in-time check: "Is the device online right now?"

**Stream-based monitoring**: Subscribes to platform connectivity changes.

**Key method**:
```dart
bool get isOnline {
  if (_currentStatus.isEmpty) return false;
  return !_currentStatus.every((result) => result == ConnectivityResult.none);
}
```

**Important caveat (TOCTOU)**: Between checking `isOnline` and dispatching the HTTP request, the network could drop. This is handled by the timeout + catch in AgentRepository, not by the connectivity check. The check is an optimization to skip unnecessary calls when we **know** we're offline.

---

### 5. Agent Repository (`lib/repositories/agent_repository.dart`)

**Purpose**: The "brain" — orchestrates Layer A and Layer B, with automatic fallback.

**Stateless design**: All mutable state is owned by SessionNotifier. The repository receives everything as parameters:

```dart
Future<AgentResponse?> getFollowUp({
  required String latestUserMessage,
  required List<String> conversationHistory,  // Used questions (Layer A dedup)
  required int followUpCount,
  List<Map<String, String>>? allMessages,    // Full history (Layer B context)
}) async {
  // Check if session should end (same logic for both layers)
  if (shouldEndSession(followUpCount: followUpCount, ...)) {
    return null;  // Signals: conversation is done
  }

  // Try Layer B first
  if (_isLlmAvailable && allMessages != null && allMessages.isNotEmpty) {
    try {
      final response = await _claudeService!.chat(messages: allMessages);
      return AgentResponse(content: response, layer: AgentLayer.llmRemote);
    } on ClaudeApiException {
      // Fall through to Layer A — network/config/timeout, doesn't matter
    }
  }

  // Layer A fallback
  final localFollowUp = _getLocalFollowUp(...);
  if (localFollowUp == null) return null;
  return AgentResponse(
    content: localFollowUp,
    layer: AgentLayer.ruleBasedLocal,
  );
}
```

**Three public methods**:
1. `getGreeting()`: Context-aware opening (time of day, days since last)
2. `getFollowUp()`: Conversational follow-up, nullable when session ends
3. `generateSummary()`: Summary + metadata extraction at session close

**Layer A fallback logic** for follow-ups:
1. Extract keywords from user message (emotional, social, work, generic)
2. Select the appropriate question pool
3. Pick a question that hasn't been asked yet (dedup against conversationHistory)
4. If the pool is exhausted, fall back to generic questions

---

### 6. Session Providers (`lib/providers/session_providers.dart`)

**Purpose**: State management orchestrator. The UI never talks directly to repositories — it talks to this notifier.

**Key responsibilities**:

**`startSession()`**: Create DB record, get greeting, save as first message.
```dart
// 1. Create session in DB
await _sessionDao.createSession(sessionId, now, 'UTC');

// 2. Set loading state IMMEDIATELY (UI shows spinner)
state = SessionState(activeSessionId: sessionId, isWaitingForAgent: true);

// 3. Call agent (async, may hit Claude)
final greetingResponse = await _agent.getGreeting(...);

// 4. Save greeting to DB
await _messageDao.insertMessage(sessionId, 'ASSISTANT', greetingResponse.content, now);

// 5. Clear loading state, track in conversation history
state = state.copyWith(
  isWaitingForAgent: false,
  conversationMessages: [{'role': 'assistant', 'content': greetingResponse.content}],
);
```

**`sendMessage(text)`**: User sends a message.
```dart
// 1. Save user message to DB
await _messageDao.insertMessage(sessionId, 'USER', text, now);

// 2. Phase 5: Intent classification (is this a query?)
final intent = _intentClassifier.classify(text);
if (intent.type == IntentType.query && intent.confidence >= 0.8) {
  // High confidence: route to recall (memory search)
  await _handleRecallQuery(text, intent.searchTerms);
  return;
}

// 3. Check end-session signals ("done", "nope", "goodbye")
if (_agent.shouldEndSession(followUpCount: state.followUpCount, ...)) {
  await endSession();
  return;
}

// 4. Get follow-up (async, may hit Claude)
state = state.copyWith(isWaitingForAgent: true);
final followUpResponse = await _agent.getFollowUp(...);

// 5. STALE RESPONSE GUARD: Check if session is still active
if (state.activeSessionId == null) return;

// 6. Save follow-up to DB
await _messageDao.insertMessage(sessionId, 'ASSISTANT', followUpResponse.content, now);

// 7. Update state
state = state.copyWith(
  followUpCount: state.followUpCount + 1,
  usedQuestions: [...state.usedQuestions, followUpResponse.content],
  conversationMessages: [...state.conversationMessages, {'role': 'assistant', ...}],
);
```

**Stale response handling**: After every `await`, check `if (state.activeSessionId == null)`. This handles the race condition where the user ends the session while a follow-up is being fetched. If the session ended, discard the response.

**`endSession()`**: Wrap up the session.
```dart
// 1. Get all user messages
final userMessages = messages.where((m) => m.role == 'USER').toList();

// 2. Generate summary (async, Claude extracts metadata when online)
final summaryResponse = await _agent.generateSummary(
  userMessages: userMessages,
  allMessages: state.conversationMessages,
);

// 3. Save summary message to DB
await _messageDao.insertMessage(
  sessionId, 'ASSISTANT', closingMessage, now
);

// 4. Extract metadata and store as JSON strings
final metadata = summaryResponse.metadata;
final moodTagsJson = metadata?.moodTags != null ? jsonEncode(metadata!.moodTags) : null;
// ... same for people, topicTags

// 5. Update session record with end time, summary, metadata
await _sessionDao.endSession(
  sessionId, now,
  summary: summaryResponse.metadata?.summary ?? summaryResponse.content,
  moodTags: moodTagsJson,
  people: peopleJson,
  topicTags: topicTagsJson,
);

// 6. Signal that closing is complete, don't clear activeSessionId yet
state = state.copyWith(isWaitingForAgent: false, isClosingComplete: true);

// 7. Trigger non-blocking sync (Phase 4 — runs in background)
_triggerSyncAfterEnd(sessionId);
```

**Sentinel pattern for copyWith**: The state class uses a sentinel object (`_sentinel`) to distinguish "caller didn't pass a value" from "caller passed null". This allows `copyWith(activeSessionId: null)` to work correctly:
```dart
SessionState copyWith({
  Object? activeSessionId = _sentinel,  // Default is sentinel
  ...
}) {
  return SessionState(
    activeSessionId: identical(activeSessionId, _sentinel)
        ? this.activeSessionId  // Preserve current value
        : activeSessionId as String?,  // Use new value (possibly null)
    ...
  );
}
```

---

### 7. UI Screen (`lib/ui/screens/journal_session_screen.dart`)

**Purpose**: Display the conversation. Simple, dumb — just renders what the notifier tells it.

**Key features**:

1. **Auto-scroll on new messages**: Only when message count changes, not on every stream emission. This avoids fighting the keyboard.
   ```dart
   if (messages.length != _lastMessageCount) {
     _lastMessageCount = messages.length;
     WidgetsBinding.instance.addPostFrameCallback((_) {
       _scrollToBottom();
     });
   }
   ```

2. **Loading indicator**: Escalates over time (0s → "Thinking...", 8s → "Still thinking...", 15s → "Taking a moment..."). Reassures the user during slow API calls.

3. **Input disabled while waiting**: `enabled: !isWaiting`

4. **Back navigation**: PopScope intercepts back button with a confirmation dialog.

5. **Session ending flow**: Hide input → show "Wrapping up..." → show "Done" button. User can read the summary at their own pace.

---

### 8. Edge Function (`supabase/functions/claude-proxy/index.ts`)

**Purpose**: The trust boundary. Never expose the API key to the client. System prompts are server-side only.

**Three modes**:

1. **Chat mode**: User sends a message, get a conversational response
2. **Metadata mode**: Full conversation, extract summary + tags
3. **Recall mode**: Memory query with journal context (Phase 5)

**System prompts** (all server-side, never sent from client):
- **Chat**: "You are a personal journal assistant. Ask 2-3 focused follow-ups..."
- **Metadata**: "Extract summary, mood_tags, people, topic_tags..."
- **Recall**: "Answer using only information from journal entries. Cite dates..."

**Security layers**:

1. **Auth**: Try JWT validation first (Phase 4). If no JWT, fall back to PROXY_ACCESS_KEY check.
2. **Payload size**: Max 50KB (protects against resource exhaustion)
3. **Input validation**: Every field checked, types enforced
4. **Prompt injection mitigation**: Delimiter stripping for recall mode (user-authored content wrapped in structural delimiters like `[JOURNAL ENTRY...]...[END ENTRY]` with delimiters stripped to prevent collision)
5. **Error mapping**: Never expose internal details. Claude API errors (429, 401, 503) mapped to safe client messages.

**Defensive parsing**: If Claude doesn't return valid JSON in metadata/recall modes, the function returns raw text instead of failing. The client has a fallback parser.

---

## Part 4: The Complete Flow (3 min)

Here's a user message flowing through the system:

```
1. USER TYPES: "I had a stressful day at work"
   └─ Text field → _sendMessage() method

2. SCREEN LAYER:
   └─ ref.read(sessionNotifierProvider.notifier).sendMessage(text)

3. SESSION NOTIFIER (sendMessage):
   a. Save user message to DB:
      INSERT INTO journal_messages (id, session_id, role, content, timestamp)
   b. Classify intent (Phase 5):
      intent = _intentClassifier.classify("I had a stressful day at work")
      → type: journalEntry (not a query)
   c. Check end signals (matches "done", "nope", etc.?):
      → No, continue
   d. Set loading state:
      state.isWaitingForAgent = true  ✓ UI shows spinner
   e. Call agent for follow-up:
      followUpResponse = await _agent.getFollowUp(
        latestUserMessage: "I had a stressful day at work",
        conversationHistory: [...used questions...],
        followUpCount: 0,
        allMessages: [
          {'role': 'assistant', 'content': 'Good morning! ...'},
          {'role': 'user', 'content': 'I had a stressful day...'}
        ]
      )

4. AGENT REPOSITORY (getFollowUp):
   a. Check if LLM is available:
      → Environment.isConfigured? YES
      → ConnectivityService.isOnline? YES
      → → → Proceed to Layer B
   b. Try Claude API:
      response = await _claudeService.chat(
        messages: [
          {'role': 'assistant', 'content': 'Good morning! ...'},
          {'role': 'user', 'content': 'I had a stressful day...'}
        ]
      )

5. HTTP CLIENT (chat method):
   a. Validate configuration:
      if (!isConfigured) throw ClaudeApiNotConfiguredException()
   b. Build request body:
      {
        "messages": [...],
        "mode": "chat"
      }
   c. POST to Claude proxy:
      dio.post(
        'https://abc.supabase.co/functions/v1/claude-proxy',
        data: body,
        options: Options(headers: {'Authorization': 'Bearer {anon-key}'})
      )
   d. Handle response/errors:
      if (DioException: timeout) → throw ClaudeApiTimeoutException()
      if (response.data['response']) → return text

6. NETWORK: POST to Supabase Edge Function

7. EDGE FUNCTION (index.ts):
   a. Extract JWT from Authorization header:
      token = "Bearer eyJ..."
   b. Validate auth:
      Try Supabase.auth.getUser(token)  ← JWT validation
      → Success: isAuthorized = true
   c. Validate request:
      messages array? ✓
      mode in ["chat", "metadata", "recall"]? ✓
      Payload < 50KB? ✓
   d. Build system prompt:
      systemPrompt = "You are a personal journal assistant..."
   e. Call Claude API:
      fetch('https://api.anthropic.com/v1/messages', {
        headers: {'x-api-key': Deno.env.get('ANTHROPIC_API_KEY')},
        body: {
          model: 'claude-sonnet-4-20250514',
          system: systemPrompt,
          messages: [...]
        }
      })
   f. Parse response:
      responseText = claudeResponse.content[0].text
   g. Return to client:
      { "response": responseText }

8. HTTP CLIENT (receives response):
   ✓ responseText = "That sounds stressful. What was the main..."
   ✓ Return as Future<String>

9. AGENT REPOSITORY (back in getFollowUp):
   ✓ response = "That sounds stressful..."
   ✓ return AgentResponse(
       content: response,
       layer: AgentLayer.llmRemote
     )

10. SESSION NOTIFIER (back in sendMessage):
    ✓ followUpResponse.content = "That sounds stressful..."
    ✓ Stale response check: activeSessionId still set? YES
    ✓ Save follow-up to DB:
       INSERT INTO journal_messages (id, session_id, role, content, timestamp)
       VALUES (..., 'ASSISTANT', 'That sounds stressful...', now)
    ✓ Update state:
       state.followUpCount = 1
       state.usedQuestions = ['That sounds stressful...']
       state.conversationMessages.add({'role': 'assistant', 'content': '...'})
    ✓ state.isWaitingForAgent = false

11. UI REBUILDS:
    ✓ activeSessionMessagesProvider emits new messages (via drift watch)
    ✓ ListView rebuilds with new assistant message
    ✓ Auto-scroll to bottom
    ✓ Text field re-enabled
    ✓ Spinner hidden
    ✓ User sees: "That sounds stressful. What was the main..."
```

**What happens if Claude fails?** At step 4b, if `_claudeService.chat()` throws `ClaudeApiTimeoutException`, it's caught. Fallback to Layer A:
```dart
on ClaudeApiException {
  // Fall through
}
// Layer A fallback
final localFollowUp = _getLocalFollowUp(
  latestUserMessage: "I had a stressful day at work",
  conversationHistory: [...],
  followUpCount: 0,
);
// → Extracts keyword "work", selects work follow-ups pool
// → Returns a pre-written question (never asked before)
// → e.g., "How do you feel about how that's going?"
return AgentResponse(
  content: localFollowUp,
  layer: AgentLayer.ruleBasedLocal,
);
```

User sees a perfectly good response — they don't know Claude wasn't called.

---

## Part 5: Key Architectural Patterns (2 min)

### Pattern 1: Proxy Pattern (ADR-0005)

**Problem**: The mobile app can't safely store API keys.

**Solution**: All API calls go through a Supabase Edge Function. The function stores the real secret (Anthropic API key) and returns safe responses.

```
Client (has: semi-public anon key)
  │
  ├─ POST /functions/v1/claude-proxy
  │ (Bearer: anon-key)
  │
Supabase Edge Function
  ├─ Validates JWT or anon-key
  ├─ Loads ANTHROPIC_API_KEY from secrets
  ├─ Calls Claude API
  │ (x-api-key: ANTHROPIC_API_KEY)
  │
  └─ Returns safe response (never API key)
```

**Benefit**: If the anon key leaks, it's not a disaster. RLS and the proxy protect the data. The real secret is never at risk.

### Pattern 2: Graceful Degradation (ADR-0006)

**Problem**: Network might be unavailable or Claude might be misconfigured.

**Solution**: Try Layer B, fall back to Layer A. Always return something.

```dart
async getFollowUp() {
  if (isLlmAvailable) {
    try {
      return await claudeService.chat(...);
    } on ClaudeApiException {
      // Fall through
    }
  }
  return localAgent.getFollowUp(...);
}
```

**Benefit**: Users never see a blank screen. Conversations work offline. Network hiccups are invisible.

### Pattern 3: Stale Response Guard

**Problem**: User ends session while a follow-up is being fetched. We get a response for a session that no longer exists.

**Solution**: After every async call, check if the session is still active before processing the response.

```dart
final followUpResponse = await _agent.getFollowUp(...);
if (state.activeSessionId == null) return;  // Session ended, discard
// Safe to save the response
```

**Benefit**: No orphaned messages. No crashes.

### Pattern 4: Defensive Parsing

**Problem**: JSON responses might have wrong types or missing fields.

**Solution**: Check types, not just existence. Never throw on bad data.

```dart
static List<String>? _parseStringList(dynamic value) {
  if (value is! List) return null;  // Wrong type
  try {
    return value.whereType<String>().toList();  // Filter non-strings
  } catch (_) {
    return null;  // Any error: return null
  }
}
```

**Benefit**: Metadata extraction never throws. Session end flow always completes.

### Pattern 5: Stateless Repository

**Problem**: Coupling between repository and state management. Hard to test.

**Solution**: Repository receives all state as parameters. DAOs and services are injected.

```dart
Future<AgentResponse?> getFollowUp({
  required String latestUserMessage,
  required List<String> conversationHistory,  // Passed in
  required int followUpCount,                 // Passed in
  List<Map<String, String>>? allMessages,    // Passed in
}) async {
  // Use parameters, don't store state
}
```

**Benefit**: Easy to test. Decoupled from notifier. Reusable.

---

## Part 6: For Android Developers (1 min)

If you're new to Android, here's what's important for this integration:

1. **No native code needed for Phase 3.** Everything is Dart/Flutter.
2. **Secrets in `local.properties`?** No — use `--dart-define` at build time (handled by CI/CD).
3. **Permissions**: Network access is handled by the `dio` package (no extra AndroidManifest.xml changes needed for HTTP).
4. **TLS**: The `dio` client enforces HTTPS by default. No SSL bypass in our code.
5. **Background sync** (Phase 4+): Uses Dart background timers, not Android WorkManager. Different paradigm.

---

## Summary

You now understand:

- **Why**: Layered agents give us offline-first + cloud-enhanced conversations.
- **What**: Five modules (Environment, Service, Repository, Notifier, UI) in a clean dependency graph.
- **How**: A message flows UI → Notifier → Repository → Service → Edge Function → Claude → back.
- **When it fails**: Automatic fallback to rule-based agent. User never sees an error.
- **Security**: API key never touches the client. Proxy is the gatekeeper.

Next steps:
- Read the ADRs: **ADR-0005** (Proxy), **ADR-0006** (Layered Agent)
- Trace a real flow: Set a breakpoint in `sendMessage()`, send a message, step through
- Run the test suite: `flutter test --coverage` — see how each layer is tested

---

## File Locations (Quick Reference)

| Module | File |
|--------|------|
| Configuration | `/lib/config/environment.dart` |
| Response types | `/lib/models/agent_response.dart` |
| HTTP client | `/lib/services/claude_api_service.dart` |
| Connectivity | `/lib/services/connectivity_service.dart` |
| Agent logic | `/lib/repositories/agent_repository.dart` |
| State management | `/lib/providers/session_providers.dart` |
| UI screen | `/lib/ui/screens/journal_session_screen.dart` |
| Edge Function | `/supabase/functions/claude-proxy/index.ts` |

---

## Recommended Reading Order

1. This walkthrough (you're here)
2. `lib/models/agent_response.dart` — understand the unified response type
3. `lib/repositories/agent_repository.dart` — see the fallback chain
4. `lib/providers/session_providers.dart` — trace `sendMessage()`
5. `lib/services/claude_api_service.dart` — understand the HTTP layer
6. `/supabase/functions/claude-proxy/index.ts` — see the security gatekeeper
7. `/docs/adr/ADR-0005-claude-api-proxy.md` — deep dive on design choices
8. `/docs/adr/ADR-0006-layered-agent-design.md` — deep dive on layer architecture
