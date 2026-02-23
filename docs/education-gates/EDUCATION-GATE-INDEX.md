---
title: "Education Gate Index"
description: "Navigation guide for Phase 3 education materials"
last_updated: "2026-02-22"
---

# Education Gate Index

This index helps you navigate the Phase 3 education gate materials. Start here if you're unsure where to begin.

---

## What Is an Education Gate?

An education gate is a three-step learning pathway designed to build understanding before a developer owns or extends code. The three steps are:

1. **Walkthrough**: Guided reading path through the code and architecture
2. **Quiz**: 12 questions testing understanding at multiple cognitive levels (Bloom's)
3. **Explain-Back**: Open-ended assessment of design reasoning and systems thinking

**Time commitment**: 45-60 minutes total

**Passing criteria**: 70% on quiz, 69% on explain-back, plus demonstrated ability to articulate design rationale

---

## Phase 3 Materials

### For Developers Learning Phase 3

| Material | Duration | Purpose | File |
|----------|----------|---------|------|
| **Start Here** | 5 min | Overview of what you'll learn | `EDUCATION-GATE-phase3.md` |
| **Walkthrough** | 10-15 min | Guided reading path through architecture | `/docs/walkthroughs/WALKTHROUGH-phase3-claude-integration.md` |
| **Quiz** | 15-20 min | 12 questions to test comprehension | `/docs/quizzes/QUIZ-phase3-claude-integration.md` |
| **Explain-Back** | 10-15 min | 8 prompts to articulate understanding | `/docs/assessments/EXPLAIN-BACK-phase3-claude-integration.md` |

### For Facilitators Guiding Phase 3

| Material | Duration | Purpose | File |
|----------|----------|---------|------|
| **Gate Overview** | 5 min | What the gate covers | `EDUCATION-GATE-phase3.md` |
| **Quiz Answer Key** | 10 min | Expected answers and scoring | End of `/docs/quizzes/QUIZ-phase3-claude-integration.md` |
| **Explain-Back Rubric** | 10 min | Scoring criteria and feedback | End of `/docs/assessments/EXPLAIN-BACK-phase3-claude-integration.md` |

---

## Quick Start for Developers

### If You Have 45 Minutes

1. Read `/docs/education-gates/EDUCATION-GATE-phase3.md` (5 min) — overview
2. Read `/docs/walkthroughs/WALKTHROUGH-phase3-claude-integration.md` (15 min) — understand the architecture
3. Take `/docs/quizzes/QUIZ-phase3-claude-integration.md` (20 min) — test yourself
4. Debrief: Can you trace one complete flow? Do you understand fallback? → You're on track

### If You Have 60 Minutes

Same as above, plus:
5. Start `/docs/assessments/EXPLAIN-BACK-phase3-claude-integration.md` (15 min) — work through first 2-3 prompts

### If You Have 2 Hours

Complete all four materials:
1. Gate overview (5 min)
2. Walkthrough (15 min)
3. Quiz (20 min)
4. Explain-Back (20 min)
5. Pair with a facilitator to discuss your answers (20 min)

---

## The Learning Path

```
START: I know nothing about Phase 3
  │
  ├─ Read EDUCATION-GATE-phase3.md
  │  └─ Q: Do I understand the three-layer architecture?
  │     ├─ NO → Re-read Part 1-2 of the walkthrough
  │     └─ YES → Continue
  │
  ├─ Read WALKTHROUGH-phase3-claude-integration.md
  │  └─ Q: Can I trace a user message from UI to Claude and back?
  │     ├─ NO → Code along with breakpoints in the IDE
  │     └─ YES → Continue
  │
  ├─ Take QUIZ-phase3-claude-integration.md
  │  └─ Q: Did I score ≥70%?
  │     ├─ NO (< 70%) → Review failed questions, re-read walkthrough
  │     └─ YES (≥ 70%) → Continue
  │
  ├─ Complete EXPLAIN-BACK-phase3-claude-integration.md
  │  └─ Q: Did I score ≥69% and demonstrate systems thinking?
  │     ├─ NO → Discuss with facilitator, identify gaps
  │     └─ YES → Continue
  │
  ├─ Pair with facilitator
  │  └─ Q: Can you defend the design to a skeptic?
  │     └─ YES → You're certified!
  │
END: Ready to own, maintain, and extend Phase 3 code
```

---

## Key Concepts You'll Learn

### Concept 1: Three-Layer Agent Design

- **Layer A**: Rule-based, offline, always available (keywords → follow-up pools)
- **Layer B**: Claude API, online, enhanced (natural language generation)
- **Layer C**: Intent classification (Phase 5) — routes queries vs. journal entries

**Key insight**: Try Layer B, fall back to Layer A on any failure. User never sees an error.

### Concept 2: Proxy Pattern

- API key lives on server (Supabase Edge Function)
- App only sees semi-public anon key
- Edge Function validates auth, calls Claude, returns safe responses
- If app is compromised, API key is not

**Key insight**: Trust boundary = one Edge Function that controls access.

### Concept 3: Graceful Degradation

- Works offline (Layer A)
- Works online (Layer B)
- Works with slow network (timeout, fallback)
- Works with misconfiguration (Layer A only)

**Key insight**: "Fail open" — keep going with reduced quality, don't crash.

### Concept 4: Stale Response Guard

- Check `if (state.activeSessionId == null)` after every async call
- Handles race condition: session ends while response is in flight
- Prevents orphaned messages and state corruption

**Key insight**: After async, verify session still active before processing response.

### Concept 5: Stateless Repository

- Repository receives all state as parameters (message history, follow-up count, etc.)
- Never stores state in fields
- Makes testing easy, data flow explicit

**Key insight**: Data flows down (UI → Notifier → Repository), never up.

---

## Files Referenced in Materials

### Core Application Code

| File | Purpose |
|------|---------|
| `/lib/config/environment.dart` | Compile-time config (Supabase URL, anon key) |
| `/lib/models/agent_response.dart` | Unified response type for both layers |
| `/lib/services/claude_api_service.dart` | HTTP client for Edge Function |
| `/lib/services/connectivity_service.dart` | Online/offline detection |
| `/lib/repositories/agent_repository.dart` | Business logic + Layer A/B switching |
| `/lib/providers/session_providers.dart` | State management (Riverpod notifier) |
| `/lib/ui/screens/journal_session_screen.dart` | UI that displays conversation |
| `/supabase/functions/claude-proxy/index.ts` | Edge Function proxy (server-side) |

### Architecture Decision Records

| ADR | Topic |
|-----|-------|
| `ADR-0005` | Claude API via Supabase Edge Function Proxy |
| `ADR-0006` | Three-Layer Agent Design |

---

## Assessment Criteria

### Quiz (12 Questions)

**Pass**: ≥ 70% (8.4 out of 12 points)

**Question breakdown**:
- 1 Remember (fact check)
- 4 Understand (concepts)
- 3 Apply (trace flows)
- 2 Analyze (design)
- 1 Evaluate (trade-offs)
- 1 Debug (failure scenario)

### Explain-Back (8 Prompts)

**Pass**: ≥ 69% (22 out of 32 points)

**Prompt breakdown**:
- 5 conceptual prompts (4 points each)
- 1 failure tracing prompt (5 points)
- 1 reflection prompt (5 points)
- 1 systems thinking prompt (5 points)

---

## Troubleshooting

### "I don't understand Layer A vs. Layer B"

→ Re-read Part 1 of the walkthrough. Then look at:
- `/lib/repositories/agent_repository.dart` lines 111-114: `_isLlmAvailable` check
- `/lib/repositories/agent_repository.dart` lines 133-158: `getGreeting()` with try/catch/fallback

### "I'm confused about the proxy pattern"

→ Read the proxy pattern section (Part 5) of the walkthrough. Then:
- Look at `/lib/services/claude_api_service.dart` line 108-114: how it gets the URL and key from Environment
- Look at `/supabase/functions/claude-proxy/index.ts` line 366-372: how it loads the secret from Deno.env

### "I don't know why stale response guard matters"

→ Think through this scenario:
- User sends message → follow-up in progress (waiting for Claude)
- User presses back → session ends → activeSessionId becomes null
- Response arrives → we check `if (state.activeSessionId == null)` → discard response
- Without this check: we save a message to a session that no longer exists

### "I'm struggling with the quiz"

→ Check which question types are hard:
- **Remember/Understand**: Re-read the walkthrough
- **Apply**: Code along in the IDE with breakpoints
- **Analyze**: Read ADR-0005 and ADR-0006
- **Debug**: Reason through the type checking in `AgentMetadata.fromJson()`

### "Explain-back feels overwhelming"

→ Start with just prompts 1-3 (conceptual). These build confidence:
- Prompt 1: Why three layers? (should be easy after walkthrough)
- Prompt 2: Why proxy pattern? (should be easy after walkthrough)
- Prompt 3: What happens on timeout? (trace a path)

Once you nail those, tackle 4-8 (deeper thinking).

---

## Next Steps After Phase 3

Once you pass the education gate and feel confident:

1. **Review PRs**: Look at Phase 3 PRs in the discussions history
2. **Safe first change**: Modify a Layer A follow-up question
3. **Write a test**: Add a test for fallback behavior
4. **Explore Phase 4**: Learn about authentication + sync
5. **Understand Phase 5**: Intent classification + memory recall (more complex)

---

## Questions?

- **Architecture questions**: See ADR-0005 and ADR-0006
- **Code walkthrough questions**: Ask a facilitator to pair on the code
- **Learning path questions**: Check this index or the `EDUCATION-GATE-phase3.md` file

---

## Record Your Progress

Use this checklist to track your progress:

- [ ] Understand three-layer architecture
- [ ] Know why proxy pattern matters
- [ ] Can trace a user message flow
- [ ] Understand stale response guard
- [ ] Pass quiz (≥70%)
- [ ] Complete explain-back (≥69%)
- [ ] Pair with facilitator on quiz/explain-back answers
- [ ] Ready to own Phase 3 code
