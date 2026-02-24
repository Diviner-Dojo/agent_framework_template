---
adr_id: ADR-0017
title: "Local LLM Layer Architecture — ConversationLayer Strategy Pattern"
status: accepted
date: 2026-02-23
decision_makers: [developer]
discussion_id: null  # Phase 8A planning discussion
supersedes: ADR-0006
risk_level: medium
confidence: 0.85
tags: [architecture, agent, llm, offline, conversation, local-inference, strategy-pattern]
---

## Context

ADR-0006 defined a three-layer agent design (Layer A: rule-based, Layer B: Claude API, Layer C: memory recall). The agent logic lives inline in `AgentRepository` with if/else switching between Layer A and B paths. ADR-0006's own header anticipated: "Phase 5 re-evaluation: evaluate whether layer dispatch should be extracted into a strategy class."

Phase 8 introduces a third conversation engine: local LLM inference via llamadart (Qwen 2.5 0.5B). This creates three distinct conversation generation paths (rule-based, Claude API, local LLM), making inline switching unmaintainable. Additionally, each path has different:

- **Initialization requirements**: rule-based needs nothing, Claude needs network + config, local LLM needs model download + RAM
- **Failure modes**: rule-based can't fail, Claude fails on network, local LLM fails on OOM/model-not-loaded
- **Response characteristics**: rule-based is deterministic, Claude is high-quality, local LLM is medium-quality
- **Resource lifecycle**: local LLM needs explicit model load/unload for RAM management

## Decision

### 1. ConversationLayer Strategy Pattern

Extract `AgentRepository`'s inline conversation logic into a `ConversationLayer` abstract class with three implementations:

- **`RuleBasedLayer`** — extracted from `AgentRepository` private methods (Layer A)
- **`ClaudeApiLayer`** — extracted from `AgentRepository` LLM paths (Layer B remote)
- **`LocalLlmLayer`** — new in Phase 8B (Layer B local)

`AgentRepository` becomes a thin dispatcher that selects the active layer and delegates.

### 2. AgentLayer Enum Extension

Add `llmLocal` to the `AgentLayer` enum alongside `ruleBasedLocal` and `llmRemote`. All exhaustive `switch` statements updated in Phase 8A even though the layer implementation arrives in Phase 8B.

### 3. Session-Locked Layer Policy

Once a session starts on a given layer, it stays on that layer for the session's duration. If the locked layer fails mid-session, fall back to `RuleBasedLayer` (not switch to a different LLM layer). This prevents disorienting quality changes mid-conversation.

- Lock set in `startSession()` / `resumeSession()`
- Lock cleared in `endSession()` / `dismissSession()` / `discardSession()`

### 4. Fallback Chain

Layer selection priority (evaluated at session start):
1. If "Prefer Claude" enabled AND Claude available → `ClaudeApiLayer`
2. If local LLM loaded → `LocalLlmLayer`
3. If Claude available → `ClaudeApiLayer`
4. Always → `RuleBasedLayer`

Mid-session fallback on error: always to `RuleBasedLayer` (not lateral to another LLM).

### 5. shouldEndSession() Stays on AgentRepository

The end-session detection is synchronous, layer-independent, and uses the same rules regardless of layer. It does not move to `ConversationLayer`.

### 6. Journal-Only Mode

A layer-independent mode that bypasses all conversation layers: skip greeting, skip follow-ups, use Layer A summary only. Sessions just capture USER messages silently.

### 7. Personality / Custom Prompts (Phase 8B)

Custom system prompts are scoped to `LocalLlmLayer` only. Claude API uses Anthropic-defined system prompts via the Edge Function. Personality config stored in SharedPreferences (not drift) — single user-scoped config doesn't warrant a migration.

## Alternatives Considered

### Alternative 1: Keep Inline Switching
- **Pros**: No new files, no refactoring risk
- **Cons**: Three-way if/else becomes unmaintainable, violates single responsibility, testing requires mocking the entire repository
- **Reason rejected**: ADR-0006 itself flagged this as technical debt at Phase 5

### Alternative 2: Full ConversationAgent Interface with DI
- **Pros**: Maximum flexibility, each layer fully independent
- **Cons**: Over-engineered for current needs, would require replacing AgentRepository entirely, breaks all existing provider wiring
- **Reason rejected**: Strategy pattern on AgentRepository gives the same extensibility with less disruption

### Alternative 3: Store Personality in drift/SQLite
- **Pros**: Consistent with other structured data
- **Cons**: Requires schema migration for a single user-scoped config, SharedPreferences precedent already exists (VoiceModeNotifier)
- **Reason rejected**: SharedPreferences is the established pattern for user settings in this codebase

## Consequences

### Positive
- Each conversation engine is independently testable
- Adding new layers requires only a new `ConversationLayer` implementation
- Session-locked layer prevents mid-conversation quality jarring
- Journal-only mode is independently valuable (no LLM dependency)
- Clean separation of concerns makes Phase 8B implementation straightforward

### Negative
- One-time refactoring cost to extract existing code
- Three new files under `lib/layers/`
- Existing `AgentRepository` tests need updating for new structure

### Neutral
- `AgentLayer.llmLocal` enum value exists before its layer implementation
- "Prefer Claude" toggle is wired but has no observable effect until local LLM exists (Claude is already the default when available)

## Linked Discussion
See: Phase 8A planning discussion (pre-implementation)

## Supersedes
ADR-0006 (Three-Layer Agent Design) — this ADR extends the original layered design with the strategy pattern extraction and local LLM architecture. ADR-0006's Layer A/B/C concept is preserved; the implementation mechanism changes from inline switching to strategy dispatch.
