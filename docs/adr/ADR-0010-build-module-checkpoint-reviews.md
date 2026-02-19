---
adr_id: ADR-0010
title: "Mid-Build Checkpoint Reviews in /build_module"
status: accepted
date: 2026-02-19
decision_makers: [developer, facilitator, architecture-consultant, docs-knowledge, independent-perspective]
discussion_id: DISC-20260219-211818-build-checkpoint-review-protocol
supersedes: null  # Extends ADR-0009 scope — does not replace it
risk_level: medium
confidence: 0.88
tags: [build, checkpoint, principle-4, independence, capture, build-module]
---

## Context

ADR-0009 established that every command dispatching subagents must integrate the full capture pipeline. At the time, `/build_module` was classified as a command that does NOT dispatch agents (ADR-0009, line 50) and was therefore exempt.

During Phase 1 execution, `/build_module` ran 13 tasks straight through without any specialist involvement. Decisions about DAO patterns, state management, navigation, and provider wiring were never challenged or captured. This violated Principle #4 ("the agent that generates code must not be the sole evaluator") — not at commit time (where `/review` catches it), but during the build itself, when decisions are cheapest to revise.

The developer identified this gap and requested that specialist review be forced DURING development, with a maximum of 1-2 iteration rounds per review point to maintain velocity.

## Decision

**`/build_module` now dispatches specialist subagents at mid-build checkpoints and fully integrates the capture pipeline.** This reclassifies `/build_module` from ADR-0009's exempt list to a capture-integrated, agent-dispatching command.

The implementation follows Principle #8 (least-complex intervention first): 1 new rule file + 1 rewritten command + 1 CLAUDE.md update. No new scripts, no new agents, no architectural changes.

### Checkpoint mechanics

- **Trigger categories**: new module (2+ files under `lib/`), architecture choice, database schema, security-relevant code, state management wiring, external API integration
- **Exemptions**: scaffolding, dependency config, pure test writing, theme/style-only, docs, final verification
- **Dispatch**: Exactly 2 specialists per checkpoint, selected from a trigger-to-specialist mapping table in `.claude/rules/build_review_protocol.md`
- **Response format**: APPROVE or REVISE, under 200 words
- **Iteration cap**: Max 2 rounds per task. After Round 2, unresolved concerns are captured with `risk_flags: ["unresolved-checkpoint"]` and surfaced in the build summary. The build is never blocked.
- **Cost optimization**: Checkpoints use sonnet-tier dispatch regardless of agent default tier, justified by the 200-word cap and focused scope
- **Tie-breaking**: When trigger categories overlap, security-relevant always claims one specialist slot; the other goes to the highest-specificity remaining category

### Capture integration

- Discussion created at build start (`create_discussion.py`)
- Every checkpoint response captured via `write_event.py` with tags `checkpoint,task-N`
- Every exempt task captured as a bypass note with tags `checkpoint-bypass,task-N`
- Discussion sealed at build end (`close_discussion.py`), even on failure

### ADR-0009 amendment

ADR-0009 line 50 stated: "Commands that do NOT dispatch agents are unaffected: `/build_module`, `/discover-projects`, `/meta-review`, `/onboard`, `/promote`, `/retro`."

This ADR removes `/build_module` from that exempt list. The remaining commands on the list are still unaffected.

## Alternatives Considered

### Alternative 1: Post-build but pre-commit review only (status quo + `/review`)
- **Pros**: Zero build overhead; specialists see complete code in context; the final `/review` already enforces Principle #4 at commit time
- **Cons**: Decisions made early in the build (DAO pattern, state shape) propagate through all subsequent tasks unchallenged. By the time `/review` catches a structural issue, the rework cost is 5-10x higher than catching it at task time. Phase 1 demonstrated this: 13 tasks completed without a single specialist checkpoint.
- **Reason rejected**: Principle #4 requires independence during generation, not only at the end. The post-build review is necessary but not sufficient.

### Alternative 2: Structured self-review checklist (zero subagent cost)
- **Pros**: No additional cost; the facilitator runs a checklist after each task against ADR and pattern conformance; forces explicit articulation of concerns
- **Cons**: Violates the literal requirement of Principle #4 — the code generator is the sole evaluator. Confirmation bias is real: the same agent that chose a pattern will not challenge it via checklist. The Phase 1 gap was precisely this scenario.
- **Reason rejected**: A self-checklist may have value for exempt tasks as a lightweight supplement, but it cannot replace independent specialist review for triggering tasks.

### Alternative 3: Batch checkpoints at module boundaries (not per-task)
- **Pros**: Specialists see complete module context, eliminating the partial-code review problem; fewer total checkpoint invocations; less context pressure on the facilitator
- **Cons**: Defers error detection — a bad abstraction in Task 2 propagates through Tasks 3-5 before any specialist sees it. Requires the facilitator to define "module boundaries" that may not map cleanly to spec tasks. Revision cost compounds with each unchecked task.
- **Reason rejected**: Per-task checkpoints catch errors earlier. The 200-word cap and 2-round limit keep overhead manageable. If context pressure becomes an issue on large builds, task batching can be reconsidered as a future enhancement.

### Alternative 4: Rule file only, no command rewrite
- **Pros**: Minimal change surface; the facilitator would read the rule and follow it; trigger categories and protocol already live in the rule file
- **Cons**: Capture pipeline integration (create_discussion, write_event, close_discussion) requires exact Bash commands that belong in a procedural command, not a guideline rule. Pre-flight checks for script existence can only be enforced in the command. Without the command rewrite, capture compliance would be facilitator-dependent — exactly the gap ADR-0009 was designed to close.
- **Reason rejected**: The rule file defines policy; the command operationalizes it. Both are needed. The command rewrite also migrated from Python/ruff to Flutter/Dart, which was overdue.

## Consequences

### Positive
- Principle #4 is now enforced during builds, not just at commit time
- Early detection of structural issues reduces late-stage rework cost
- All checkpoint deliberation is captured in Layer 1 (immutable) and Layer 2 (queryable)
- Bypass notes for exempt tasks create a complete audit trail of what was and wasn't reviewed
- The 2-round hard limit ensures builds always complete — no infinite specialist loops

### Negative
- Build execution time increases by ~2 specialist invocations per triggering task (estimated 5 checkpoints on a typical 13-task build = 10 dispatches)
- Facilitator context window fills faster on long builds due to absorbed specialist responses
- Specialists reviewing partial code (mid-build) may flag issues that resolve themselves in later tasks

### Neutral
- The capture pipeline scripts are unchanged — only the commands that call them are updated
- The remaining exempt commands from ADR-0009 are still unaffected
- The final `/review` before commit is still required — checkpoints are supplementary, not a replacement

## Known Limitations

Identified during the multi-specialist review (DISC-20260219-211818-build-checkpoint-review-protocol):

1. **No session resumption**: Unlike `/review` and `/deliberate`, `/build_module` does not write a `state.json` for mid-build recovery after context compaction. A long build interrupted by compaction must be manually resumed.
2. **No capture error handling**: The command does not instruct the facilitator to check `write_event.py` exit codes. A silent capture failure would violate Principle #2 without detection.
3. **No build-to-review linkage**: The build discussion and the subsequent `/review` discussion are separate. Retrospective analysis cannot link checkpoint outcomes to final review verdicts without manual cross-referencing.

These are deferred for future enhancement per Principle #8 (solve the primary gap first, iterate on refinements).

## Linked Discussion
See: discussions/2026-02-19/DISC-20260219-211818-build-checkpoint-review-protocol/
