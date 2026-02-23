---
title: "Phase 3: Education Gate Complete Package"
description: "Walkthrough + Quiz + Explain-Back — everything needed to master Phase 3"
gate_id: "GATE-PHASE3-20260222"
phase: "Phase 3: Claude API Integration"
target_audience: "Developers new to Android/Flutter or the codebase"
prerequisite: "Completed Phase 1-2 (basic journaling engine)"
expected_time: "45-60 minutes total"
---

# Phase 3: Education Gate — Complete Package

This document ties together three assessment artifacts designed to build your understanding of Phase 3: Claude API Integration. You'll progress through walkthrough → quiz → explain-back, with each step building on the previous.

---

## The Three-Gate Approach

### Gate 1: Guided Walkthrough (10-15 min)
**File**: `/docs/walkthroughs/WALKTHROUGH-phase3-claude-integration.md`

**What you'll learn**:
- High-level architecture (three layers, fallback chain)
- Module-by-module overview (Environment, Service, Repository, Notifier, UI)
- Complete user message flow from UI to Claude and back
- Key architectural patterns (proxy, graceful degradation, stale response guard)
- Android-specific context

**How to use it**:
1. Read Part 1-2 to understand the three-layer system
2. Read Part 3 module-by-module, opening the actual code files
3. Read Part 4 as a complete flow trace
4. Reference Part 5 (patterns) while reading actual code

**Outcome**: You'll understand the "why" behind each component.

---

### Gate 2: Comprehension Quiz (15-20 min)
**File**: `/docs/quizzes/QUIZ-phase3-claude-integration.md`

**What it tests**:
- 1 Remember-level fact check
- 4 Understand-level conceptual questions (fallback, stale responses, proxy, configuration)
- 3 Apply-level scenarios (trace a flow, store metadata, fallback decision)
- 2 Analyze-level design questions (stateless repo, defensive parsing)
- 1 Evaluate-level trade-off (sentinel pattern)
- 1 Debug scenario (wrong types in JSON)

**How to use it**:
1. Take the quiz open-book (you can refer to code/walkthrough)
2. Explain answers in your own words, don't just read code
3. Aim for 70% pass rate (8.4 out of 12)

**Outcome**: You can explain concepts and trace failure paths.

**If you struggle**:
- Understand questions: re-read fallback chain, trace one flow step-by-step
- Apply questions: code along in IDE with breakpoints
- Analyze questions: read ADR-0005 and ADR-0006
- Debug question: reason about types and defensive parsing

---

### Gate 3: Explain-Back Assessment (10-15 min)
**File**: `/docs/assessments/EXPLAIN-BACK-phase3-claude-integration.md`

**What it tests**:
- Can you articulate design rationale without looking at code?
- Do you understand failure modes and recovery?
- Can you think about extending the system responsibly?
- Are you ready to own this code?

**How to use it**:
1. Read the 8 prompts
2. Write 2-4 paragraphs for each, naturally and conversationally
3. Aim for 69% pass rate (22 out of 32 points)
4. Strong answers show nuanced thinking, not perfect recall

**Outcome**: You're ready to maintain, extend, and defend this architecture.

**What "strong" looks like**:
- You mention trade-offs, not just facts
- You can trace an exception through multiple layers
- You propose sensible tests and extensions
- You recognize architectural risks and mitigations

---

## The Complete Flow (How It All Works)

### Architecture Layers

```
Layer B (Claude, Online)
├─ Requires: network + config
├─ Quality: natural, context-aware
└─ Failure → fallback to Layer A

Layer A (Rule-Based, Offline)
├─ Always available
├─ Quality: predictable, keyword-based
└─ Fallback target
```

### Data Flow (One Message)

```
User types "I'm stressed" → UI → SessionNotifier.sendMessage()
  ↓
Save to DB + track in conversation history
  ↓
Classify intent (Phase 5: is this a query?)
  ↓
Check end signals (did user say "done"?)
  ↓
Set loading state (UI shows spinner)
  ↓
Call AgentRepository.getFollowUp(latestMessage, history, count, allMessages)
  ├─ Is LLM available (config + online)?
  │ ├─ YES → call ClaudeApiService.chat(allMessages)
  │ │ ├─ POST to Edge Function
  │ │ │ ├─ Edge Function validates auth + payload
  │ │ │ ├─ Calls Claude API
  │ │ │ └─ Returns response
  │ │ ├─ Parse response → AgentResponse(content, layer=llmRemote, metadata=null)
  │ │ └─ Return ✓
  │ │
  │ └─ Exception? → fall through
  │
  └─ Layer A: extract keywords → select pool → dedup → return AgentResponse(content, layer=ruleBasedLocal)

Back to SessionNotifier:
  ↓
Stale response guard: is session still active? YES
  ↓
Clear loading state (UI hides spinner)
  ↓
Save follow-up to DB
  ↓
Update state (increment followUpCount, add to usedQuestions, track in conversation)
  ↓
UI rebuilds, shows new message, auto-scrolls

User sees: follow-up question (from Claude or rule-based, doesn't matter)
```

### Key Design Decisions

| Decision | Why | Trade-off |
|----------|-----|-----------|
| **Proxy Pattern** | API key on server, not client | One more network hop |
| **Graceful Degradation** | Always work, even offline | Complexity of two layers |
| **Stateless Repository** | Testable, decoupled | More parameters to pass |
| **Defensive Parsing** | Partial data > no data | Metadata might be incomplete |
| **Stale Response Guard** | Prevent race condition bugs | Need to check after every await |

---

## Knowledge Dependency Graph

```
Phase 1-2: Basic Journaling Engine
│
├─ Phase 3: Claude API Integration (YOU ARE HERE)
│  ├─ Requires: Understanding of Riverpod, drift DAOs, async/await
│  ├─ ADR-0005: Claude API via Supabase Edge Function Proxy
│  └─ ADR-0006: Three-Layer Agent Design
│
└─ Phase 4: Authentication & Sync
   ├─ Requires: Phase 3 + JWT understanding
   └─ Extends: Edge Function auth (JWT vs. anon key)
```

---

## Practical Next Steps (After Passing All Gates)

### Safe First Changes
1. **Modify Layer A**: Add a new follow-up question to a pool
2. **Test Layer A**: Write a unit test for keyword extraction
3. **Review code**: Read and understand a PR that touches `agent_repository.dart`

### Moderate Changes
1. **Extend metadata**: Add a new tag type (time_of_day_tags, locations)
2. **Modify greeting**: Change time-of-day logic or context
3. **Add instrumentation**: Log layer selection for analytics

### Advanced Changes
1. **Phase 5 preparation**: Understand intent classification (read `/lib/services/intent_classifier.dart`)
2. **Edge Function**: Propose security improvements (validation, rate limiting)
3. **Add new mode**: New end-of-session extraction logic

---

## FAQ: Common Questions While Learning Phase 3

**Q: Why doesn't the app just always use Layer A? It's simpler.**
A: UX. Claude provides richer, more natural conversations. Users prefer it when available. Layer A is the fallback.

**Q: What if Claude's response is really bad?**
A: That's an LLM quality issue, not an architecture issue. The system still works. The prompt engineering (system prompts in the Edge Function) determines quality.

**Q: Can we cache Claude responses?**
A: Not yet. Phase 5+ might add caching. Currently, every message hits Claude when online.

**Q: What if the Edge Function is down?**
A: Users get Layer A (rule-based). Eventually, someone notices the Edge Function is down and fixes it. Meanwhile, the app still works.

**Q: Why no error screen when things fail?**
A: By design. Graceful degradation means users should never see errors. If they do, it's a bug in our fallback logic.

**Q: What's the difference between `ClaudeApiTimeoutException` and `ClaudeApiNetworkException`?**
A: Timeout: server too slow. Network: connection failed. Both trigger Layer A fallback. The distinction is mainly for debugging/metrics.

**Q: Why does metadata have nullable fields?**
A: Layer A doesn't extract metadata, so it's always null. Claude might fail to parse, so it could be null. Safe default: assume metadata is optional.

**Q: Can users see which layer served their response?**
A: Not in the UI (by design — we want transparent fallback). But the `AgentLayer` enum is logged for analytics. Developers can see which layer was used.

---

## Testing Strategy for Phase 3

### Unit Tests
- **Agent Repository**: Mock ClaudeApiService, test fallback chain
- **ClaudeApiService**: Mock dio, test error translation and parsing
- **AgentMetadata**: Test defensive parsing with wrong types
- **Environment**: Test isConfigured logic

### Integration Tests
- **Full flow**: User message → Layer B → save response → UI shows message
- **Fallback**: User message → Layer B timeout → Layer A → save response
- **Session end**: Multiple messages → summary → metadata storage

### Edge Function Tests
- **Input validation**: Test 50KB limit, invalid JSON, missing fields
- **Auth**: Test JWT validation, anon key fallback
- **Claude API errors**: Test 429, 401, 503 → client-safe errors

### Manual Testing
- **Offline mode**: Disable network, send messages, see Layer A responses
- **Timeout scenario**: Slow Edge Function, slow Claude, wait for timeout
- **Stale response**: Send message, quickly press back, verify no orphaned messages

---

## Reading Order (If You Want Deep Dives)

1. **This file** (you're here)
2. **Walkthrough** (`/docs/walkthroughs/WALKTHROUGH-phase3-claude-integration.md`)
3. **Code**: Start with `/lib/models/agent_response.dart` (simplest)
4. **Code**: Move to `/lib/repositories/agent_repository.dart` (core logic)
5. **Code**: Then `/lib/providers/session_providers.dart` (orchestration)
6. **Code**: Finally `/supabase/functions/claude-proxy/index.ts` (security)
7. **Quiz** (`/docs/quizzes/QUIZ-phase3-claude-integration.md`)
8. **ADRs**: `/docs/adr/ADR-0005-claude-api-proxy.md` and `ADR-0006-layered-agent-design.md`
9. **Explain-Back** (`/docs/assessments/EXPLAIN-BACK-phase3-claude-integration.md`)

---

## Mastery Checkpoints

**Checkpoint 1: Can You Trace a Flow?**
- [ ] Explain what happens when network drops mid-follow-up
- [ ] Draw the data flow from UI to Claude and back
- [ ] Identify where stale response guard kicks in

**Checkpoint 2: Can You Spot Bugs?**
- [ ] Why is `AgentMetadata._parseStringList()` needed?
- [ ] What breaks if we remove the sentinel pattern?
- [ ] What happens if we skip the stale response check?

**Checkpoint 3: Can You Extend It?**
- [ ] How would you add a new follow-up question pool?
- [ ] Where would you add a new metadata type?
- [ ] How would you debug if Layer A is being called instead of Layer B?

**Checkpoint 4: Are You Ready?**
- [ ] Pass Quiz (70%+)
- [ ] Pass Explain-Back (69%+)
- [ ] Can you defend design decisions to a skeptical colleague?
- [ ] Can you propose safe modifications?

---

## Resources at a Glance

| Resource | File | Purpose |
|----------|------|---------|
| Walkthrough | `/docs/walkthroughs/WALKTHROUGH-phase3-claude-integration.md` | Learn the architecture |
| Quiz | `/docs/quizzes/QUIZ-phase3-claude-integration.md` | Test comprehension (70% to pass) |
| Explain-Back | `/docs/assessments/EXPLAIN-BACK-phase3-claude-integration.md` | Demonstrate mastery (69% to pass) |
| ADR-0005 | `/docs/adr/ADR-0005-claude-api-proxy.md` | Deep dive on proxy pattern |
| ADR-0006 | `/docs/adr/ADR-0006-layered-agent-design.md` | Deep dive on three-layer design |
| Code: Environment | `/lib/config/environment.dart` | Config + compile-time setup |
| Code: Response Types | `/lib/models/agent_response.dart` | Unified response type |
| Code: HTTP Client | `/lib/services/claude_api_service.dart` | Transport layer |
| Code: Connectivity | `/lib/services/connectivity_service.dart` | Online/offline check |
| Code: Repository | `/lib/repositories/agent_repository.dart` | Business logic + fallback |
| Code: Notifier | `/lib/providers/session_providers.dart` | State orchestration |
| Code: UI | `/lib/ui/screens/journal_session_screen.dart` | Presentation layer |
| Code: Edge Function | `/supabase/functions/claude-proxy/index.ts` | Server-side proxy |

---

## Success Criteria

**You're ready to own Phase 3 code when**:

- [ ] You can trace a user message from UI to Claude API to response display
- [ ] You understand why graceful degradation matters
- [ ] You can explain the proxy pattern to someone unfamiliar with it
- [ ] You know what happens when Claude times out (and why it's not an error)
- [ ] You recognize the stale response guard and can explain why it's needed
- [ ] You can read the Edge Function and spot the security controls
- [ ] You pass the quiz (70%+)
- [ ] You pass the explain-back (69%+)
- [ ] You can propose a modification without breaking the system

---

## Facilitator Checklist

If you're guiding a developer through this gate:

- [ ] Developer has completed Phase 1-2 (basic journaling engine)
- [ ] Developer has time for 45-60 minutes of focused learning
- [ ] Developer has access to the code repository
- [ ] You've answered their Android/Flutter context questions
- [ ] Developer completes walkthrough and can trace one flow
- [ ] Developer completes quiz and scores ≥70%
- [ ] Developer completes explain-back and scores ≥69%
- [ ] You've discussed their answers and addressed misconceptions
- [ ] Developer can propose a safe first modification
- [ ] Developer is cleared to review PRs and make changes

---

## Where to Ask Questions

- **Architecture questions**: Refer to `/docs/adr/ADR-0005` and `ADR-0006`
- **Code questions**: Pair program through the actual flow with breakpoints
- **Security questions**: Review the Edge Function audit comments
- **Testing questions**: Look at test suite: `/test/services/claude_api_service_test.dart`
- **Design questions**: Discuss trade-offs with the team or raise in `/discussions/`
