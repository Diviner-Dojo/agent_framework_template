# Agent Architecture

> Full agent roster, orchestration rules, collaboration modes, and cross-agent protocols.
> Referenced from CLAUDE.md (kept slim per ADR-0016). This is the authoritative detail.

## Leadership Hierarchy
- **Steward** (`steward.md`): Framework philosopher-guardian. Evaluates agent-definition changes, rule modifications, and philosophy evolution; maintains framework lineage tracking. Not used in day-to-day reviews — only framework evolution and lineage decisions. Cannot dispatch other agents (no Task tool). See `PHILOSOPHY.md`.
- **Facilitator** (`facilitator.md`): Team leader and workflow orchestrator. The single orchestrator for all multi-agent workflows.
- **Specialists**: 10 domain agents, each with a distilled Values section (load-bearing beliefs) and a procedural Domain Lens (reasoning sequence applied before analysis). Equal in standing, different in strengths.

## Agent Roster (12 agents)

| Agent | Model | Role |
|-------|-------|------|
| steward | opus | Framework philosopher-guardian + lineage tracking |
| facilitator | opus | Team leader, workflow orchestrator |
| architecture-consultant | opus | Structural integrity, ADR validation, boundary enforcement |
| independent-perspective | opus | Anti-groupthink, cross-domain innovation, multi-instance (4 types) |
| security-specialist | sonnet | Vulnerability identification, threat modeling, auth review |
| qa-specialist | sonnet | Test coverage, edge cases, reliability, regression prevention |
| performance-analyst | sonnet | Latency, resource efficiency, scalability, cost |
| docs-knowledge | sonnet | Team Historian — decision traceability, knowledge flow, documentation |
| ux-evaluator | sonnet | The User in the Room — interaction flow, emotional design, accessibility |
| project-analyst | sonnet | External project analysis, cross-domain discovery pipeline |
| educator | sonnet | The Coach — walkthroughs, Bloom-grounded quizzes, mastery tracking (ADR-0012) |
| history-analyst | sonnet | Git history context — churn, refactors, reverts, blame (--deep only) |

**Core 8 (carry ~all dispatch across projects):** facilitator, qa-specialist, architecture-consultant, security-specialist, independent-perspective, performance-analyst, docs-knowledge, ux-evaluator. The other 4 (steward, educator, project-analyst, history-analyst) are episodic by design.

## Orchestration Rules
- Subagents CANNOT spawn other subagents, except **project-analyst** (delegated orchestrator for `/analyze-project`).
- The facilitator (main agent) orchestrates all other multi-agent workflows.
- Multiple subagents can run concurrently with true parallelism; each gets its own isolated context window.
- **Custom subagents inherit the full CLAUDE.md + project rules** (only built-in Explore/Plan skip them). See ADR-0016.

## Model Override
The facilitator may override an agent's default tier upward (sonnet → opus) when the task demands deeper reasoning. All overrides are recorded with `model:<tier>` tags in event capture.

## Cross-Agent Collaboration Protocols
- **Cross-Agent Dispatch** (`cross-agent-dispatch` skill): any specialist can request dispatch of another agent through the facilitator. Captured with `dispatch-request` / `dispatch-decision` tags.
- **Multi-Instance Dispatch** (`multi-instance-dispatch` skill): specialists can request parallel instance splits. independent-perspective has pre-approved multi-instance dispatch with 4 instance types. Others need facilitator approval. Max 3 instances per agent per review.
- **Discovery Pipeline**: independent-perspective (Research Scout) → project-analyst → docs-knowledge chain for cross-domain innovation capture.

## Collaboration Mode Spectrum (facilitator selects per change)
1. **Ensemble** — independent contribution, no inter-agent exchange (lightest)
2. **Yes, And** — collaborative building, each agent builds on previous
3. **Structured Dialogue** — coopetitive exchange with multi-round discussion (default for significant changes)
4. **Dialectic Synthesis** — thesis-antithesis-synthesis with ACH matrix (high-stakes)
5. **Adversarial** — red team, scoped to security/fault-injection/anti-groupthink only

## Exploration Intensity (orthogonal to collaboration mode)
- **Low**: primary analysis with brief notes on alternatives
- **Medium**: 2-3 alternatives with trade-off analysis (default)
- **High**: thorough exploration of alternatives, edge cases, failure modes

## Agent Improvement Path
1. Facilitator observes a pattern across multiple reviews
2. Facilitator proposes a specific change with evidence
3. Steward evaluates against framework philosophy and principles
4. Developer approves the change
5. Change goes through `/review` like any code change

## Agent Invocation Pattern
```
Task(subagent_type="agent-name", prompt="...")
Task(subagent_type="agent-name", model="opus", prompt="...")  # facilitator override
```
All agent turns are captured with `model:<tier>` tags. The facilitator collects results and synthesizes a unified report.
