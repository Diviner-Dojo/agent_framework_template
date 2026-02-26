---
adr_id: ADR-0025
title: "Journaling Mode Templates for Activity-Scoped Sessions"
status: accepted
date: 2026-02-26
decision_makers: [architect, facilitator]
discussion_id: null
supersedes: null
risk_level: medium
confidence: 0.85
tags: [journaling, modes, templates, conversation, ux]
---

## Context

The journaling app currently offers a single undifferentiated conversation mode. Users journal for different purposes — gratitude practice, dream recording, mood tracking — but the LLM has no awareness of the user's intent. This leads to generic prompts that don't guide the user through structured activities.

Research on journaling apps (Moodiary, Lumma) shows that mode-scoped templates with numbered conversation steps significantly improve user engagement and session quality.

## Decision

Implement activity-scoped journaling modes that shape the LLM's conversation flow with numbered steps. Each mode defines a system prompt fragment that composes with (not replaces) the base personality prompt.

### Mode Enum
Four modes at launch:
- **Free** (default): No additional prompt — current behavior
- **Gratitude**: 3-step guided gratitude practice
- **Dream Analysis**: 4-step dream exploration
- **Mood Check-In**: 3-step mood assessment

### Storage
- Mode stored per-session as `journaling_mode` column (TEXT, nullable, default null = free mode)
- Schema migration v8 adds the column
- Mode is immutable once session starts (no mid-session mode switching)

### Prompt Composition
- Mode-specific system prompt is appended to the personality prompt (composable)
- `ConversationLayer.getGreeting()` and `getFollowUp()` accept optional `journalingMode` parameter
- `ClaudeApiLayer` passes mode in context map to Edge Function
- `RuleBasedLayer` uses mode to select greeting template
- `LocalLlmLayer` composes mode prompt with personality prompt
- Edge Function validates mode against server-side allowlist

### Mode Selection
- Mode selection happens at session start
- UI for mode selection deferred to E12 (unified UI sprint)
- API supports mode from day one for programmatic testing

## Alternatives Considered

### Alternative 1: Separate prompt files per mode
- **Pros**: Easy to edit independently, clear separation
- **Cons**: File I/O at session start, deployment complexity, harder to test
- **Reason rejected**: Enum with inline prompts is simpler, testable, and sufficient for 4 modes. Can extract to files if mode count grows beyond ~10.

### Alternative 2: User-defined custom modes
- **Pros**: Maximum flexibility, user agency
- **Cons**: Complex UI for mode authoring, prompt injection risk from user-authored system prompts, hard to validate quality
- **Reason rejected**: Premature complexity. Start with curated modes; add custom modes if user demand materializes.

### Alternative 3: Mode as a separate table with foreign key
- **Pros**: Normalized schema, extensible metadata per mode
- **Cons**: Over-engineering for 4 static modes, extra join on every query
- **Reason rejected**: A TEXT column on journal_sessions is sufficient. Promote to a table only if modes gain per-instance metadata (e.g., user-custom step definitions).

## Consequences

### Positive
- Guided journaling sessions improve user engagement and session quality
- Composable prompt design means modes don't interfere with personality customization
- Server-side allowlist prevents injection of arbitrary mode values
- Nullable column means existing sessions are unaffected (backward compatible)

### Negative
- ConversationLayer interface change (optional parameter) touches all three implementations
- Edge Function change requires redeployment
- Mode prompt quality depends on prompt engineering (needs iteration)

### Neutral
- UI for mode selection deferred — programmatic-only until E12
- Mode is stored as string (not enum ordinal) for forward compatibility with new modes
