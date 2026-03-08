---
adr_id: ADR-0001
title: "Adopt the AI-Native Agentic Development Framework"
status: accepted
date: 2026-02-18
decision_makers: [facilitator, architecture-consultant]
discussion_id: null
supersedes: null
risk_level: high
confidence: 0.90
tags: [framework, architecture, process]
---

## Context

The project is starting with AI-assisted development using Claude Code. Without a structured framework, AI-generated code risks being merged without adequate understanding, review, or documentation — the "vibe coding" problem. Research (METR, July 2025) shows experienced developers are ~19% slower with unstructured AI tools despite believing they are faster.

We need a structured approach that:
- Ensures code quality through multi-perspective review
- Captures reasoning and decisions as durable artifacts
- Maintains developer understanding through education gates
- Improves continuously through measured feedback loops

## Decision

Adopt the AI-Native Agentic Development Framework v2.1 as the project's development methodology.

This framework uses:
- **Specialist agent panel** (9 core agents, including project-analyst) for multi-perspective code review
- **Coopetition model** where agents have shared goals but different professional priorities
- **Four-layer capture stack** (immutable files, SQLite index, curated memory, optional vector)
- **Education gates** (walkthrough, quiz, explain-back) before merge
- **Nested improvement loops** (micro/meso/macro) for continuous framework self-improvement
- **Spec-driven development** where every significant change starts with an executable specification

## Alternatives Considered

### Alternative 1: No structured framework (pure vibe coding)
- **Pros**: Maximum velocity, no process overhead
- **Cons**: No quality assurance, no captured reasoning, no learning, entropy accumulates
- **Reason rejected**: Research shows this approach is actually slower due to verification overhead and defect accumulation

### Alternative 2: Traditional code review process adapted for AI
- **Pros**: Well-understood, familiar to most developers
- **Cons**: Single-perspective review, no structured capture, no education component, no self-improvement loops
- **Reason rejected**: Does not leverage AI's unique capabilities (parallel review, codebase-wide context, fresh perspective agents)

### Alternative 3: Fully adversarial multi-agent debate
- **Pros**: Maximum rigor, thorough analysis
- **Cons**: Creates noise, developer disengagement, entrenchment over integration. Research (Kahneman 2003, Ellemers 2020) shows adversarial framing causes participants to entrench rather than integrate
- **Reason rejected**: Coopetition model produces better outcomes with less noise

## Consequences

### Positive
- Structured, traceable reasoning for all significant decisions
- Multi-perspective code review from complementary specialists
- Developer understanding verified before merge
- Framework improves itself through feedback loops
- Durable knowledge base grows over time

### Negative
- Initial setup overhead (~54 files in the template)
- Learning curve for the command workflows
- Additional time per review cycle (mitigated by adaptive depth)

### Neutral
- Developer role shifts from code writer to "Sovereign Conductor" / orchestrator
- Collaboration mode is adjustable per change (not one-size-fits-all)
