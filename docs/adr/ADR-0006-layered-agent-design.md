---
adr_id: ADR-0006
title: "Three-Layer Agent Design"
status: accepted
date: 2026-02-18
decision_makers: [developer]
discussion_id: null  # Pre-framework decision — documented from product brief
supersedes: null
risk_level: medium
confidence: 0.85
tags: [architecture, agent, llm, offline, conversation]
---

## Context

The Agentic Journal app runs conversational journaling sessions. The conversation agent must:
- Work fully offline (Phase 1 MVP requirement)
- Enhance conversations with LLM intelligence when online (Phase 3)
- Support querying past entries as "external memory" with RAG (Phase 5)
- Degrade gracefully — never block journaling due to network/API failures

Building all three capabilities at once is too complex for incremental delivery. A layered approach allows each phase to ship a working product while building toward full capability.

## Decision

Implement a **three-layer agent design** where each layer builds on the previous:

### Layer A — Rule-Based Agent (Phase 1, offline MVP)
- Time-of-day greetings and gap detection
- Keyword-based follow-up questions (emotional, social, work-related triggers)
- Rule-based session summary (concatenation of first sentences)
- **Zero LLM dependencies** — fully offline, always available

### Layer B — LLM-Enhanced Agent (Phase 3, online)
- Claude API via Supabase Edge Function proxy (see ADR-0005)
- Natural language follow-ups replacing keyword-based logic
- AI-generated summaries, mood tags, people extraction, topic tags
- **Falls back to Layer A** when offline or on API failure

### Layer C — Memory Recall Agent (Phase 5, RAG)
- Intent classification: journaling vs. querying
- Local FTS search across journal messages
- Supabase pgvector semantic search (stretch goal)
- Claude synthesizes answers grounded in retrieved context
- Anti-hallucination enforcement in system prompt

**Key invariant**: Layer A is never removed. It is the permanent offline fallback. Layers B and C enhance but do not replace Layer A.

## Alternatives Considered

### Alternative 1: LLM-Only Agent (Skip Layer A)
- **Pros**: Better conversation quality from day one, simpler codebase (no rule-based logic to maintain)
- **Cons**: App is non-functional offline; Phase 1 requires cloud infrastructure before any journaling can happen; API failures break the core experience
- **Reason rejected**: Violates the offline-first requirement (ADR-0004); blocks MVP delivery on cloud setup

### Alternative 2: Single Adaptive Agent (All Layers Merged)
- **Pros**: One codebase path, no layer switching logic
- **Cons**: Massive initial scope; can't ship until all three capabilities work; testing complexity; harder to debug which layer caused an issue
- **Reason rejected**: Prevents incremental delivery; too risky for a learning developer

### Alternative 3: Plugin Architecture (Dynamic Agent Loading)
- **Pros**: Maximum flexibility, agents can be updated independently, supports third-party extensions
- **Cons**: Over-engineered for a single-developer project; plugin system is complex to build correctly; unnecessary abstraction
- **Reason rejected**: YAGNI — the three layers are well-defined and don't need runtime extensibility

## Consequences

### Positive
- Each phase ships a complete, working product
- Offline journaling always works, regardless of API status
- Clear separation of concerns: rule-based, LLM-enhanced, and RAG are distinct code paths
- Easy to test each layer independently
- Fallback chain is explicit and predictable

### Negative
- Rule-based agent (Layer A) must be maintained even after LLM agent ships
- Layer switching logic adds some complexity to `agent_repository.dart`
- Conversation quality in offline mode is noticeably lower than LLM mode (expected trade-off)

### Neutral
- The layer decision is transparent to the user — they see seamless conversation regardless of which layer is active
- Monitoring which layer served a session helps track online/offline usage patterns
- Layer C's intent classification creates a clear modal boundary (journaling vs. querying)

## Linked Discussion
Pre-framework decision — documented from product brief (`docs/product-brief.md`, Agent Design section).
