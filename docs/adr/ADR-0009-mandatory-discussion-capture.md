---
adr_id: ADR-0009
title: "Mandatory Discussion Capture for All Agent-Dispatching Commands"
status: accepted
date: 2026-02-19
decision_makers: [developer, facilitator]
discussion_id: null  # This decision was made in direct conversation, not a captured discussion
supersedes: null
risk_level: medium
confidence: 0.92
tags: [capture, framework, principle-2, discussion, pipeline]
---

## Context

The framework's Principle #2 states: "Capture must be automatic. The capture system uses structured commands that guarantee event-level recording. The model cannot opt out of logging."

An audit of all 12 slash commands revealed that 3 commands dispatch subagents but do not integrate with the capture pipeline (`scripts/create_discussion.py`, `scripts/write_event.py`, `scripts/close_discussion.py`):

| Command | Agents Dispatched | Capture? |
|---------|------------------|----------|
| `/review` | 2-5 specialists | Yes |
| `/deliberate` | 2+ specialists | Yes |
| `/analyze-project` | project-analyst + specialists | Yes |
| **`/plan`** | architecture-consultant, qa-specialist, security-specialist | **No** |
| **`/walkthrough`** | educator | **No** |
| **`/quiz`** | educator | **No** |

The gap was discovered when the Phase 1 spec review dispatched three specialists whose substantial reasoning (architecture findings, QA findings, security findings) was consumed into the spec but never recorded in the immutable capture layer. The specialist outputs existed only in the ephemeral chat transcript.

## Decision

**Every command that dispatches one or more subagents via the Task tool MUST integrate the full capture pipeline:**

1. **Before dispatch**: Create a discussion via `scripts/create_discussion.py`
2. **After each agent returns**: Record the agent's output via `scripts/write_event.py`
3. **After synthesis**: Record the facilitator's synthesis via `scripts/write_event.py`
4. **On completion or abandonment**: Seal the discussion via `scripts/close_discussion.py`

Each affected command must include:
- **CRITICAL BEHAVIORAL RULES** section (matching `/review` and `/deliberate` pattern) stating capture is pass/fail
- **Pre-flight checks** verifying all three capture scripts exist
- **Discussion ID** propagated through all steps

Commands updated to comply:
- `/plan` — added Steps 3-6 for capture pipeline integration
- `/walkthrough` — added Steps 1, 3-4 for capture pipeline integration
- `/quiz` — added Steps 1, capture in Step 2, capture in Step 5, Step 6 for close

Commands that do NOT dispatch agents are unaffected: ~~`/build_module`~~, `/discover-projects`, ~~`/meta-review`~~, `/onboard`, `/promote`, ~~`/retro`~~.

> **Amendment (ADR-0010):** `/build_module` was reclassified as an agent-dispatching command when mid-build checkpoint reviews were added. It now fully integrates the capture pipeline. See ADR-0010.

> **Amendment (ADR-0011):** `/retro` and `/meta-review` now dispatch specialists to review their draft outputs (independent-perspective + docs-knowledge for retro; architecture-consultant + independent-perspective for meta-review). Both fully integrate the capture pipeline. See ADR-0011.

## Alternatives Considered

### Alternative 1: Capture only for "important" commands (review, deliberate)
- **Pros**: Less overhead for lightweight commands like walkthrough and quiz; fewer discussion directories created
- **Cons**: Violates Principle #2 ("the model cannot opt out of logging"); creates a gray area where significance is subjective; reasoning from spec reviews (high value) was lost under this model
- **Reason rejected**: The Phase 1 spec review demonstrated that "less important" commands can produce high-value reasoning. Selective capture is indistinguishable from optional capture, which Principle #2 explicitly prohibits.

### Alternative 2: Automatic capture via hook (intercept all Task tool calls)
- **Pros**: Zero command-level changes; capture happens at the infrastructure layer; impossible to forget
- **Cons**: Claude Code hooks cannot intercept Task tool outputs (only pre/post tool use); would require changes to the agent architecture itself; the content of agent responses is not available to hooks
- **Reason rejected**: Not technically feasible with the current hook system. The capture must be implemented at the command level where agent outputs are accessible.

### Alternative 3: Lightweight capture (log agent names and timestamps, not full content)
- **Pros**: Lower storage cost; faster to write; less noise in discussions/
- **Cons**: Loses the reasoning — the most valuable artifact. Agent findings without content are just timestamps. Violates Principle #1 ("reasoning is the primary artifact").
- **Reason rejected**: The whole point of capture is to preserve reasoning. Metadata-only capture defeats the purpose.

## Consequences

### Positive
- All specialist reasoning is now preserved in the immutable Layer 1 capture stack
- Discussion transcripts are queryable via SQLite (Layer 2) for retrospectives and meta-reviews
- Spec reviews, walkthroughs, and quizzes are linkable to the discussions that produced them
- `/retro` and `/meta-review` can now analyze planning and education activity, not just reviews

### Negative
- More discussion directories created (one per /plan, /walkthrough, /quiz invocation)
- Slightly more overhead per command execution (3 script calls: create, write, close)
- Storage grows faster — but discussion data is small text, so this is negligible

### Neutral
- The discussion ID format and directory structure are unchanged
- The capture pipeline scripts are unchanged — only the commands that call them are updated
- Commands that don't dispatch agents are not affected

## Linked Discussion
This decision was made in direct developer conversation on 2026-02-19 after the Phase 1 spec review revealed the capture gap. The developer's exact instruction: "I want to make sure that we ALWAYS create a discussion when there is a call to the agents."
