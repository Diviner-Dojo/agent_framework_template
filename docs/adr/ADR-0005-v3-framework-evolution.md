---
adr_id: ADR-0005
title: "Framework v3.0: Leadership Hierarchy, Specialist Philosophy, and Collaboration Protocols"
status: accepted
date: 2026-03-14
decision_makers: [facilitator, architecture-consultant, docs-knowledge, independent-perspective, qa-specialist]
discussion_id: DISC-20260314-002623-review-v3-framework-upgrade
supersedes: ADR-0002
risk_level: medium
confidence: 0.83
tags: [framework, architecture, agents, governance, v3]
---

## Linked Discussion

Review discussion `DISC-20260314-002623-review-v3-framework-upgrade` with report `docs/reviews/REV-20260314-003200.md`. Verdict: approve-with-changes (3 blocking, 12 advisory). All blocking findings resolved.

## Context

The v2.1 framework had 11 agents in a flat panel with a facilitator orchestrator. Agents had job descriptions but no professional philosophy — they produced competent but interchangeable analysis. There was no mechanism for agents to request collaboration with each other, no way for an agent to request parallel instances of itself, and no formal governance process for evolving agent definitions or framework rules.

Practical experience with the framework on the agentic journal project revealed:
1. **Agent identity gap**: Specialists produced generic analysis without a philosophical lens to guide judgment in edge cases
2. **Collaboration gap**: Specialists could not request input from other specialists during reviews
3. **Governance gap**: Agent definition changes happened ad-hoc without evaluation against framework philosophy
4. **Steward role expansion**: The Phase 1 Chronicler (ADR-0002) needed broader governance responsibilities

## Decision

Evolve the framework to v3.0 with three major changes:

### 1. Specialist Philosophy

Every agent receives a "Specialist Philosophy" section: core beliefs about their craft that guide behavior without creating persona bias. These replace thin instruction sets with professional judgment. Example: the security-specialist believes "security calibrated to the actual threat model is more valuable than theoretical perfection."

### 2. Leadership Hierarchy

Three tiers replace the flat panel:
- **Steward** (opus): Framework philosopher-guardian. Evaluates agent definition changes, rule modifications, and philosophy evolution. Retains lineage tracking from ADR-0002. Activated only for framework evolution, not day-to-day reviews.
- **Facilitator** (opus): Team leader. Gains pre-review intelligence (reads code before dispatching), contextual dispatch (tailored prompts per specialist), follow-up challenge (re-dispatches shallow analysis), and team development notes.
- **Specialists** (9 agents): Equal in standing, different in strengths. Each with a distinct specialist philosophy.

### 3. Collaboration Protocols

Two new rules enable organic inter-agent collaboration while preserving the single-orchestrator pattern:
- **Cross-Agent Dispatch** (`.claude/rules/cross_agent_dispatch_protocol.md`): Any specialist can request dispatch of another agent through the facilitator. Requests are captured with `dispatch-request` / `dispatch-decision` tags for retrospective analysis.
- **Multi-Instance Dispatch** (`.claude/rules/multi_instance_protocol.md`): Specialists can request parallel instance splits. Independent-perspective has pre-approved multi-instance dispatch with 4 instance types (Independent Analyst, Team Observer, Research Scout, Process Critic); facilitator selects at most 3 per review. All other agents need facilitator approval. Max 3 instances per agent per review.

### Model Tier Changes

| Agent | v2.1 Tier | v3.0 Tier | Rationale |
|-------|-----------|-----------|-----------|
| steward | sonnet | opus | Expanded governance scope requires deeper reasoning for philosophy evaluation and agent definition assessment |
| independent-perspective | sonnet | opus | Multi-instance operation with 4 distinct modes requires stronger reasoning to maintain quality across instance types; anti-groupthink analysis benefits from deeper inference |
| educator | haiku | sonnet | Bloom's taxonomy quiz generation at Analyze/Evaluate levels requires stronger reasoning than haiku provides; knowledge gap escalation demands accurate domain assessment |
| architecture-consultant | opus | opus | Unchanged |
| facilitator | opus | opus | Unchanged |

### Supporting Artifacts

- **PHILOSOPHY.md** (project root): The "why" companion to CLAUDE.md's "how". Establishes the framework's philosophical foundation — creative empowerment, exploration as default, promotion is earned.
- **Framework Evolution section** in CLAUDE.md: Documents the gated path for framework changes (Facilitator observes → proposes → Steward evaluates → developer approves → `/review`).

## Supersession of ADR-0002

ADR-0002 established the Steward as a "peer-level agent" at "sonnet tier" with "Chronicler sub-function only." Under v3.0:
- The Steward is no longer peer-level — it sits above the Facilitator in the governance hierarchy
- The Steward operates at opus tier (expanded governance scope)
- The Steward retains all Chronicler lineage tracking capabilities but adds philosopher-guardian governance responsibilities
- The "separate agent" decision from ADR-0002 is preserved and validated — the steward's governance role further justifies separation from the project-analyst

All other aspects of ADR-0002 remain valid (lineage manifest, drift scanning, append-only events, Phase 1 scope).

## Alternatives Considered

### Alternative 1: Specialist philosophy without leadership hierarchy

- **Pros**: Simpler, lower cost (no steward tier upgrade), addresses agent identity gap without governance overhead
- **Cons**: No formal path for framework evolution, no check on facilitator's team development proposals
- **Reason rejected**: The governance gap was real — ad-hoc agent changes risk introducing unintended behavioral shifts without philosophical evaluation

### Alternative 2: Governance checklist instead of Steward agent

- **Pros**: Lowest complexity per Principle #8, no agent overhead, developer applies checklist directly
- **Cons**: Checklist cannot evaluate philosophical alignment with the depth an opus-tier agent can, does not produce an immutable governance record in the capture pipeline
- **Reason rejected**: A checklist is a reasonable alternative for small projects. For this framework (which serves as a template for derived projects), the institutional memory and capture integration justify the agent approach.

### Alternative 3: Keep facilitator at sonnet, let specialists escalate to opus

- **Pros**: Concentrates compute where domain depth matters most
- **Cons**: The facilitator's pre-read, contextual dispatch, and synthesis are the highest-leverage points in the review — quality at these points amplifies specialist quality. The model override mechanism allows specialist escalation when needed.
- **Reason rejected**: Facilitator quality has the highest multiplier effect. Model override covers specialist escalation.

## Consequences

### Positive

- Every agent has a distinct professional identity that guides edge-case judgment
- Framework evolution follows a formal, captured governance process
- Specialists can request cross-agent collaboration organically
- The facilitator produces richer dispatch context, improving specialist output quality
- Retrospective data (dispatch patterns, split requests, model overrides) enables empirical framework improvement

### Negative

- Opus-tier cost increases: 2 agents → 4 agents at opus (steward, facilitator, architecture-consultant, independent-perspective)
- Sonnet-tier cost increase: educator upgraded from haiku
- Governance process adds friction to agent definition changes (mitigated by Steward activation pattern limiting involvement to framework evolution only)
- Two new protocol rules add documentation surface area

### Risks to Monitor

- **Governance paralysis**: If steward evaluations become a bottleneck, consider a lightweight track for minor agent tweaks (Facilitator + developer approval only)
- **Multi-instance cost spiral**: If pre-approved independent-perspective dispatch inflates per-review costs, restrict to facilitator-approved per-situation
- **Facilitator authority creep**: If pre-read framing anchors specialists, adjust to sharing pre-read as questions rather than conclusions
- **Discovery pipeline adoption**: If zero completed discovery chains after 3 review cycles, simplify the pipeline
