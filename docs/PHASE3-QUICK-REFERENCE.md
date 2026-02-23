---
title: "Phase 3 Quick Reference"
description: "One-page summary of Claude API Integration architecture"
last_updated: "2026-02-22"
---

# Phase 3: Claude API Integration — Quick Reference

**Print this. Pin it to your desk. Reference while reading code.**

---

## The Three-Layer System (in 30 seconds)

```
Layer B (Claude, Online)
  ├─ Natural language
  ├─ Context-aware
  ├─ Requires: network + config
  └─ On failure → Layer A

Layer A (Rule-Based, Offline)
  ├─ Keywords → follow-ups
  ├─ Time-of-day greetings
  ├─ Hardcoded question pools
  └─ Always works (fallback)

User never sees an error. Always gets a response.
```

---

## Data Flow: One Message (in 60 seconds)

```
User: "I'm stressed"
  │
  ├─ UI: _sendMessage(text)
  │
  ├─ SessionNotifier.sendMessage()
  │  ├─ Save to DB (USER message)
  │  ├─ Check intent (Phase 5)
  │  ├─ Check end signals ("done", "nope", etc.)
  │  ├─ Set loading state (spinner shows)
  │  ├─ Call agent.getFollowUp()
  │  │
  │  ├─ AgentRepository.getFollowUp()
  │  │  ├─ Is LLM available (config + online)?
  │  │  │ ├─ YES → try Claude API
  │  │  │ └─ NO → skip to Layer A
  │  │  │
  │  │  ├─ ClaudeApiService.chat()
  │  │  │  ├─ POST /functions/v1/claude-proxy
  │  │  │  ├─ Edge Function validates + calls Claude
  │  │  │  └─ Returns response
  │  │  │
  │  │  ├─ On timeout/error → fall through to Layer A
  │  │  ├─ Layer A: keywords → "work" → work pool → unique question
  │  │  └─ Return AgentResponse(content, layer, metadata?)
  │  │
  │  ├─ Stale check: is session still active? YES
  │  ├─ Clear loading state (spinner hides)
  │  ├─ Save to DB (ASSISTANT message)
  │  ├─ Update state (increment followUpCount)
  │  └─ Return
  │
  └─ UI rebuilds
     └─ User sees follow-up: "That sounds stressful. Tell me more..."
```

---

## Module Map

| Module | File | Responsibility |
|--------|------|-----------------|
| **Environment** | `/lib/config/environment.dart` | Compile-time config (URL, key) |
| **Response Type** | `/lib/models/agent_response.dart` | Unified response (content + layer + metadata) |
| **HTTP Client** | `/lib/services/claude_api_service.dart` | POST to Edge Function, parse, typed exceptions |
| **Connectivity** | `/lib/services/connectivity_service.dart` | Check: are we online right now? |
| **Repository** | `/lib/repositories/agent_repository.dart` | Brain: Layer A/B switching, fallback chain |
| **State** | `/lib/providers/session_providers.dart` | SessionNotifier: orchestrates flow |
| **UI** | `/lib/ui/screens/journal_session_screen.dart` | Displays messages, sends text, shows spinner |
| **Edge Fn** | `/supabase/functions/claude-proxy/index.ts` | Server-side: auth, validation, Claude call |

---

## Key Patterns

### Pattern: Proxy
```
Client (has anon key)
  ├─ POST /functions/v1/claude-proxy
  │  Authorization: Bearer {anon-key}
  │
Edge Function
  ├─ Validate auth (JWT or proxy key)
  ├─ Load ANTHROPIC_API_KEY from secrets
  ├─ Call Claude API
  └─ Return safe response (never API key)
```

**Why**: API key never at risk on client.

### Pattern: Graceful Degradation
```dart
if (_isLlmAvailable) {
  try {
    return await claudeService.chat(...);  // Layer B
  } on ClaudeApiException {
    // Fall through to Layer A
  }
}
return _getLocalFollowUp(...);  // Layer A (always safe)
```

**Why**: Works offline, works on timeouts, works with misconfiguration.

### Pattern: Stale Response Guard
```dart
final response = await _agent.getFollowUp(...);  // Async, could take time
if (state.activeSessionId == null) return;  // Session may have ended
// Safe to save response
```

**Why**: Handles race condition where session ends mid-API-call.

### Pattern: Defensive Parsing
```dart
static List<String>? _parseStringList(dynamic value) {
  if (value is! List) return null;  // Wrong type? Return null
  try {
    return value.whereType<String>().toList();
  } catch (_) {
    return null;  // Any error? Return null
  }
}
```

**Why**: Never crash on bad JSON. Fail gracefully.

### Pattern: Stateless Repository
```dart
Future<AgentResponse?> getFollowUp({
  required String latestUserMessage,  // Parameter
  required List<String> conversationHistory,  // Parameter
  required int followUpCount,  // Parameter
  ...
})
// Use parameters, don't store state. Easy to test.
```

**Why**: Testable, decoupled, data flow obvious.

---

## Exception Hierarchy (How Failures Map to Layer A)

```
Any ClaudeApiException
  ├─ NotConfigured
  │  └─ Cause: No --dart-define or empty values
  │  └─ Result: Layer A only
  │
  ├─ Network
  │  └─ Cause: No internet, connection refused, DNS failed
  │  └─ Result: Layer A fallback
  │
  ├─ Timeout
  │  └─ Cause: Claude API too slow
  │  └─ Result: Layer A fallback
  │
  ├─ Server
  │  └─ Cause: Edge Function error (500), Claude error (rate limit)
  │  └─ Result: Layer A fallback
  │
  └─ Parse
     └─ Cause: Response missing required fields
     └─ Result: Layer A fallback
```

**Key**: All exceptions trigger the same behavior: fall back to Layer A.

---

## Configuration & Deployment

### Build-Time Config

```bash
flutter run \
  --dart-define=SUPABASE_URL=https://abc.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=eyJ... \
  --dart-define=CLAUDE_PROXY_TIMEOUT=30
```

- Values baked into binary at compile time
- Missing values? Layer A only (no error)
- Release builds must include all three

### Runtime Environment (Edge Function)

```
Supabase Secrets:
  ANTHROPIC_API_KEY=sk-ant-...
  SUPABASE_URL=https://abc.supabase.co
  SUPABASE_ANON_KEY=eyJ...
  PROXY_ACCESS_KEY=min-32-chars (entropy check)
```

- NEVER expose in responses
- PROXY_ACCESS_KEY is fallback for unauthenticated mode
- Phase 4: JWT auth becomes primary

---

## Database Schema (Relevant Fields)

```sql
-- journal_sessions table (end-of-session metadata)
summary TEXT                    -- Claude-generated summary or Layer A
mood_tags TEXT                  -- JSON: ["happy", "tired"]
people TEXT                     -- JSON: ["Alice", "Bob"]
topic_tags TEXT                 -- JSON: ["work", "family"]

-- journal_messages table
id TEXT PRIMARY KEY
session_id TEXT FOREIGN KEY
role TEXT                       -- "USER" or "ASSISTANT"
content TEXT                    -- The message text
timestamp DATETIME
entities_json TEXT              -- Phase 5: recall metadata
```

---

## State Machine: Session Lifecycle

```
┌─────────────┐
│   START     │ flutter navigate to journal screen
└──────┬──────┘
       │ startSession()
       ▼
┌──────────────────┐
│  GREETING WAIT   │ isWaitingForAgent = true (spinner shows)
└──────┬───────────┘
       │ response arrives
       ▼
┌──────────────────┐
│  READY TO CHAT   │ user can type, send button enabled
└──────┬───────────┘
       │ user sends message → saveMessage() → getFollowUp()
       ├─→ (repeats)
       │ user sends "done" OR followUpCount > 3 → endSession()
       ▼
┌──────────────────┐
│  SESSION ENDING  │ isSessionEnding = true, generateSummary()
└──────┬───────────┘
       │ response arrives
       ▼
┌──────────────────┐
│  CLOSING READY   │ isClosingComplete = true, show "Done" button
└──────┬───────────┘
       │ user taps "Done" → dismissSession()
       ▼
┌──────────────────┐
│  END            │ navigate back to session list
└──────────────────┘
```

---

## Failure Recovery Flowchart

```
Claude API call made
  │
  ├─ Success? → Return response ✓
  │
  └─ Failure?
     │
     ├─ Type: Timeout, Network, Server, Parse, NotConfigured
     │  │
     │  └─ All types → Caught as ClaudeApiException
     │
     └─ Fall through to Layer A
        │
        ├─ Extract keywords from user message
        ├─ Select question pool (emotional, social, work, generic)
        ├─ Pick unused question
        │
        └─ Return Layer A response ✓

User sees: response from one layer or the other. No error screen.
```

---

## Security Checklist

- [ ] API key in Edge Function secrets, never in app code
- [ ] Anon key in app is semi-public (RLS + proxy protect it)
- [ ] All network calls use HTTPS (no SSL bypass)
- [ ] Edge Function validates: auth, payload size, field types, input format
- [ ] Edge Function strips structural delimiters from user content
- [ ] No journal content logged in release builds
- [ ] Typed exceptions prevent vague error handling
- [ ] Phase 4: JWT auth for real access control via RLS

---

## Testing Checklist

- [ ] Unit: AgentRepository fallback chain
- [ ] Unit: ClaudeApiService error translation
- [ ] Unit: AgentMetadata defensive parsing
- [ ] Integration: Full message → response flow
- [ ] Integration: Layer B timeout → Layer A fallback
- [ ] Integration: Session end → metadata storage
- [ ] Manual: Offline mode (disable network)
- [ ] Manual: Slow API (wait for timeout)
- [ ] Manual: Stale response (back button during agent wait)
- [ ] Edge Function: Input validation, auth, error mapping

---

## Debugging Tips

**"Which layer was used?"**
→ Check `agentResponse.layer` → `AgentLayer.llmRemote` or `AgentLayer.ruleBasedLocal`

**"Why did Claude not get called?"**
→ Check: `Environment.isConfigured` (config missing?) AND `ConnectivityService.isOnline` (offline?)

**"What's the follow-up coming from?"**
→ Look at `AgentResponse.layer`. If `ruleBasedLocal`: keywords matched, pool selected.

**"Why did the session not save metadata?"**
→ If `AgentMetadata` is all null: Layer A, OR Claude failed to parse, OR network error. All are safe (metadata is optional).

**"Stale response happened — what do I see?"**
→ Conversation continues normally, response is discarded silently. Look at logs to confirm `activeSessionId == null` check fired.

---

## ADRs for Deep Dives

| ADR | Topic | Link |
|-----|-------|------|
| ADR-0005 | Claude API via Supabase Edge Function Proxy | `/docs/adr/ADR-0005-claude-api-proxy.md` |
| ADR-0006 | Three-Layer Agent Design | `/docs/adr/ADR-0006-layered-agent-design.md` |
| ADR-0007 | Constructor Injection + DAOs | `/docs/adr/ADR-0007-constructor-injection-daos.md` |
| ADR-0012 | Optional Auth — JWT injection | `/docs/adr/ADR-0012-optional-auth-jwt.md` |

---

## Common Gotchas

| Gotcha | Reality |
|--------|---------|
| "The app crashed because Claude failed" | No — caught exception, Layer A fallback |
| "The API key is in the app" | No — it's on the server |
| "Users see empty responses sometimes" | No — Layer A always returns something |
| "Stale response overwrites end-of-session" | No — stale check prevents it |
| "Metadata is required" | No — all fields nullable, Layer A has none |
| "Layer A is a fallback for bugs" | No — it's a full, parallel implementation |

---

## File Locations (Cheat Sheet)

```
Configuration:
  lib/config/environment.dart

Types:
  lib/models/agent_response.dart

Services:
  lib/services/claude_api_service.dart
  lib/services/connectivity_service.dart

Business Logic:
  lib/repositories/agent_repository.dart

State:
  lib/providers/session_providers.dart

UI:
  lib/ui/screens/journal_session_screen.dart

Server:
  supabase/functions/claude-proxy/index.ts

Tests:
  test/services/claude_api_service_test.dart
  test/repositories/agent_repository_test.dart

Docs:
  docs/adr/ADR-0005-claude-api-proxy.md
  docs/adr/ADR-0006-layered-agent-design.md
  docs/walkthroughs/WALKTHROUGH-phase3-claude-integration.md
  docs/quizzes/QUIZ-phase3-claude-integration.md
  docs/assessments/EXPLAIN-BACK-phase3-claude-integration.md
```

---

## Print & Post

Save this page. Print it. Post it near your desk. Reference it while:
- Reading code for the first time
- Debugging a flow
- Explaining to a colleague
- Designing an extension

---

**Last updated**: 2026-02-22
**Phase**: 3 (Claude API Integration)
**Audience**: Developers new to this codebase
