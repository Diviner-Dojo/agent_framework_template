---
title: "Phase 3: Claude API Integration — Explain-Back Assessment"
description: "Developer summarizes key design decisions and failure modes"
assessment_id: "EXPLAIN-BACK-20260222-PHASE3"
module: "Claude API Integration (Phase 3)"
depth_level: "moderate"
estimated_duration: "10-15 minutes"
target_outcome: "Developer can articulate design rationale and system resilience without referring to code"
---

# Phase 3: Claude API Integration — Explain-Back Assessment

**Purpose**: Before we consider you ready to maintain and extend this code, explain the design choices and failure modes in your own words. No code required — just your understanding.

**Format**: Answer the prompts below. Write naturally, as if explaining to a colleague. Aim for 2-4 paragraphs per question.

**Passing**: Clear articulation of design intent and ability to reason about failure modes.

---

## Prompt 1: The Three-Layer Design

**Explain**, in your own words:
- Why does the app have both a rule-based agent (Layer A) and a Claude agent (Layer B)?
- What happens when Claude becomes unavailable?
- How does this design help users?

**What we're listening for**:
- Recognition that Layer A is the foundation, Layer B is enhancement
- Awareness of the trade-off: complexity vs. resilience
- Understanding that graceful degradation is the goal, not "Claude always works"

**Strong answer includes**:
- "Offline-first" or "works without internet"
- "Fallback from Claude to rule-based"
- "User never sees a broken state"
- Ideally: mention "trust boundary" or "architectural risk mitigation"

---

## Prompt 2: The Proxy Pattern

**Explain**, in your own words:
- Why does the Anthropic API key live on the server (Edge Function) instead of in the app?
- What would go wrong if we embedded the key in the app binary?
- How does the proxy pattern make the app more secure?

**What we're listening for**:
- Recognition that app binaries can be decompiled or extracted
- Understanding that secrets need a trust boundary
- Awareness of the anon key vs. the API key distinction

**Strong answer includes**:
- "API key never leaves the server"
- "Anon key is semi-public, RLS enforces access control"
- "If the app is compromised, the API key isn't"
- Ideally: "Centralized key management means we can rotate keys without updating the app"

---

## Prompt 3: Stale Response Handling

**Explain**, in your own words:
- What is the "stale response guard" and what problem does it solve?
- What would happen if we didn't have it?
- Why is this a real concern (not just theoretical)?

**What we're listening for**:
- Awareness that async operations + concurrent user actions = race conditions
- Recognition that "session ended" doesn't instantly abort network calls
- Understanding that ignoring stale responses is safer than trying to be clever

**Strong answer includes**:
- "User presses back while we're waiting for a follow-up"
- "Response arrives for a session that no longer exists"
- "Without the guard: orphaned messages, incorrect state"
- Ideally: "This is a real bug if ignored; happens during slow networks or fast user gestures"

---

## Prompt 4: Defensive Parsing

**Explain**, in your own words:
- What does "defensive parsing" mean in this codebase?
- Why don't we just throw an exception if JSON has the wrong type?
- What's the worst-case scenario without defensive parsing?

**What we're listening for**:
- Recognition that external data is untrustworthy (Claude might change, network corruption, bugs)
- Understanding that crashing is worse than partial data
- Awareness that sessions must complete even if metadata extraction fails

**Strong answer includes**:
- "Claude returns wrong types or missing fields"
- "We check types instead of trusting the data"
- "Wrong fields become null; session still ends"
- Ideally: "Fail open (keep going) rather than fail closed (crash)"

---

## Prompt 5: Stateless Repository Design

**Explain**, in your own words:
- Why does `AgentRepository` receive conversation state as parameters instead of storing it?
- What's the downside of this approach?
- Why is it worth the downside?

**What we're listening for**:
- Recognition that testability and decoupling are goals
- Awareness that "stateless" is a design constraint, not a limitation
- Understanding that parameters make data flow explicit

**Strong answer includes**:
- "All state flows down from the notifier; nothing stored in the service"
- "Easy to test: no shared state between calls"
- "Trade-off: a bit more verbose (passing parameters)"
- Ideally: "Makes the data flow obvious and prevents bugs from hidden state"

---

## Prompt 6: Failure Modes and Recovery

**Scenario**: A user is journaling. The network drops mid-follow-up. The Claude call times out. What happens? Walk us through the recovery.

**Expected flow**:
1. `ClaudeApiService.chat()` throws `ClaudeApiTimeoutException`
2. Exception is caught in `AgentRepository.getFollowUp()`
3. Falls back to Layer A (rule-based)
4. Returns a keyword-based follow-up
5. User sees a follow-up, unaware that Claude failed
6. Session continues normally

**What we're listening for**:
- Ability to trace an exception through the call stack
- Understanding that fallback is transparent to the user
- Awareness that Layer A is always a valid fallback

**Strong answer includes**:
- Clear exception type (timeout, not generic)
- Explicit catch and fallback
- "User sees a rule-based follow-up"
- Ideally: "Session state remains consistent; no orphaned data"

---

## Prompt 7: Design Trade-Offs

**Reflect on the overall Phase 3 design**:
- What's the biggest architectural strength?
- What's the biggest architectural risk or limitation?
- How would you test this to gain confidence it works?

**What we're listening for**:
- Nuanced thinking about strengths and weaknesses
- Awareness that no design is perfect
- Practical ideas for validation

**Strong answer might include**:

**Strengths**:
- "Graceful degradation means the app is very resilient"
- "Clear separation of concerns makes it maintainable"
- "Proxy pattern is rock-solid security"

**Risks**:
- "If Claude becomes flaky, users might complain they get different quality responses"
- "Metadata extraction could fail silently; users might not notice missing tags"
- "If the Edge Function goes down, users are stuck with Layer A"

**Testing**:
- "Mock the Claude API to return timeouts and errors"
- "Test Layer A fallback explicitly"
- "Test stale response guard: end session while a follow-up is in flight"
- "Audit the Edge Function security (auth, input validation, secrets)"

---

## Prompt 8: Extending the System

**Imagine**: You need to add a new feature where users can ask "Tell me about my week" — Claude synthesizes from multiple sessions.

**Questions**:
- How would this fit into the existing architecture?
- Which layer (A or B) would this belong to?
- What new failure modes would you need to handle?
- Where would you want tests?

**What we're listening for**:
- Systems thinking: how does new code fit with existing?
- Recognition that feature scope affects architecture
- Awareness of new edge cases

**Strong answer includes**:
- "This is a memory query — similar to Phase 5 recall"
- "Layer B (Claude) for synthesis; Layer A (rule-based or just list results) for fallback"
- "Failure modes: no sessions found, Claude returns gibberish, user deletes sessions mid-query"
- "Need integration tests for the full flow, unit tests for Claude integration, fallback tests"
- Ideally: "This would probably trigger a new ADR because it's a significant feature"

---

## Scoring Rubric

### Prompt 1-5 (Conceptual Understanding)

**Strong (4/4 points)**: Clear, complete explanation. Shows deep understanding. Mentions trade-offs or implementation details.

**Good (3/4 points)**: Clear explanation. Correct understanding. May miss a nuance.

**Adequate (2/4 points)**: Generally correct but some gaps. Might confuse Layer A/B, or miss why design matters.

**Weak (1/4 points)**: Partially correct. Significant misunderstanding or confusion.

**Missing (0/4 points)**: Blank or fundamentally wrong.

### Prompt 6 (Failure Mode Tracing)

**Strong (5/5 points)**: Traces exception through all layers. Explains fallback. Describes user experience.

**Good (4/5 points)**: Traces most of the path. Gets the idea of fallback.

**Adequate (3/5 points)**: Understands fallback happens but misses details.

**Weak (1/5 points)**: Confused about what happens.

**Missing (0/5 points)**: Blank.

### Prompt 7 (Reflection)

**Strong (5/5 points)**: Identifies real strengths and risks. Proposes sensible tests. Shows nuanced thinking.

**Good (4/5 points)**: Identifies strengths and risks. Testing ideas are reasonable.

**Adequate (3/5 points)**: Identifies some trade-offs. Limited testing ideas.

**Weak (1/5 points)**: Superficial or incorrect analysis.

**Missing (0/5 points)**: Blank.

### Prompt 8 (Systems Thinking)

**Strong (5/5 points)**: Proposes sensible architecture. Identifies failure modes. Thinks about tests and process.

**Good (4/5 points)**: Architecture makes sense. Aware of some failure modes.

**Adequate (3/5 points)**: Reasonable architecture. Limited failure mode awareness.

**Weak (1/5 points)**: Confused architecture or vague proposals.

**Missing (0/5 points)**: Blank.

---

## Total: 32 Points

**Pass**: ≥ 22 points (69%)

**Interpretation**:
- **26-32 (Strong)**: You're ready to own and extend this code.
- **22-25 (Adequate)**: You understand the design. Ask questions before making major changes.
- **Below 22 (Needs Work)**: Do another walkthrough pass, then re-attempt.

---

## What's Next After Passing?

1. **Code review**: Ask to review the Claude API changes in Phase 3 pull requests (see `/docs/reviews/`)
2. **Pairing session**: Walk through an actual session flow in the debugger
3. **Safe change**: Modify a Layer A follow-up question or time-of-day greeting logic
4. **Audit task**: Review the Edge Function code and security controls (ADR-0005)
5. **Own a test**: Write a new test for fallback behavior or defensive parsing

---

## Facilitator Notes

This assessment is **intentionally open-ended**. The goal is to hear how the developer thinks, not to grade them on perfect recall.

**Red flags** that suggest the developer needs more review:
- Confuses Layer A and Layer B
- Doesn't understand why proxy pattern matters
- Thinks stale response guard is "optional"
- Proposes adding more error handling instead of failing gracefully

**Green flags** that suggest readiness:
- Mentions "graceful degradation" or "offline-first" unprompted
- Recognizes trade-offs (complexity vs. resilience, speed vs. safety)
- Proposes practical testing strategies
- Asks clarifying questions about system behavior
