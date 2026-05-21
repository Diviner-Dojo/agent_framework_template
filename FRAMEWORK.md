# AI-Native Agentic Development Framework v3.0

> Universal framework principles. This file applies to any project using the framework.
> Project-specific configuration lives in CLAUDE.md. Philosophy lives in PHILOSOPHY.md.
> See ADR-0065 for the decomposition rationale.

## Non-Negotiable Principles

1. **Reasoning is the primary artifact.** Code is output. Deliberation, trade-offs, and decision lineage are the durable assets. Every significant decision must be traceable to the discussion that produced it.
2. **Capture must be automatic.** The capture system uses structured commands that guarantee event-level recording. The model cannot opt out of logging. Enforced at the command/tooling layer.
3. **Collaboration precedes adversarial rigor.** Multi-perspective analysis is the default. Adversarial modes are scoped exclusively to: security review (red-teaming), fault injection/stress testing, anti-groupthink checks.
4. **Independence prevents confirmation loops.** The agent that generates code must not be the sole evaluator. At minimum, one specialist who did not participate in generation must perform independent review.
5. **ADRs are never deleted.** Only superseded with references to the replacing decision. This creates an immutable decision history.
6. **Education gates before merge.** Walkthrough, quiz, explain-back, then merge. Proportional to complexity and risk. Deferrals require developer acknowledgment and must be logged in the retro. Deferred gates must be completed before the next phase begins, or formally re-deferred with documented rationale.
7. **Layer 3 promotion requires human approval.** No discussion insight is promoted automatically.
8. **Least-complex intervention first.** When improving the framework, prefer prompt changes before command/tool changes before agent definition changes before architectural changes. Lower-complexity interventions are cheaper, more reversible, and faster to validate. Only escalate to structural changes when simpler interventions have been tried or are demonstrably insufficient.

## Agent Architecture

### Leadership Hierarchy
- **Steward**: Framework philosopher-guardian. Evaluates agent definition changes, rule modifications, and philosophy evolution. Does not participate in day-to-day reviews — only activated for framework evolution. Cannot dispatch other agents. See `PHILOSOPHY.md` for the values the steward protects.
- **Facilitator**: Team leader and workflow orchestrator. Leads specialists through insightful guidance, contextual dispatch, and rigorous synthesis. The single orchestrator for all multi-agent workflows.
- **Specialists**: 10 domain agents, each with a Values block (load-bearing beliefs) and a Domain Lens (structured reasoning steps). Equal in standing, different in strengths.

### Agent Roster (12 agents)
| Agent | Model | Role |
|---|---|---|
| steward | opus | Framework philosophy guardian |
| facilitator | opus | Team leader and orchestrator |
| architecture-consultant | opus | Structural alignment and component boundaries |
| independent-perspective | opus | Multi-instance thinker: analyst, observer, scout, critic |
| security-specialist | sonnet | Security vulnerabilities, auth patterns, threat modeling |
| qa-specialist | sonnet | Test coverage, edge cases, reliability |
| performance-analyst | sonnet | Latency, resource efficiency, scalability |
| docs-knowledge | sonnet | Team historian: decision traceability, knowledge flow |
| project-analyst | sonnet | External project explorer and co-review orchestrator |
| ux-evaluator | sonnet | User advocate: friction, delight, clinical UX |
| educator | sonnet | Coach: walkthroughs, Bloom's assessments, mastery tracking |
| history-analyst | sonnet | Git history context: churn, refactors, reverts, blame (--deep only) |

### Orchestration Rules
- Subagents CANNOT spawn other subagents, except the **project-analyst** which serves as a delegated orchestrator for `/analyze-project`
- The facilitator (main agent) orchestrates all other multi-agent workflows
- Multiple subagents can run concurrently with true parallelism
- Each subagent gets its own isolated context window

### Model Override
The facilitator may override an agent's default model tier upward (sonnet → opus) when the task demands deeper reasoning. All overrides are recorded with `model:<tier>` tags in event capture for retrospective analysis.

### Cross-Agent Collaboration Protocols
- **Cross-Agent Dispatch** (`.claude/rules/cross_agent_dispatch_protocol.md`): Any specialist can request dispatch of another agent through the facilitator. All requests captured with `dispatch-request` / `dispatch-decision` tags.
- **Multi-Instance Dispatch** (`.claude/rules/multi_instance_protocol.md`): Specialists can request to be split into multiple parallel instances. Independent-perspective has pre-approved multi-instance dispatch (4 instance types). All other agents must request facilitator approval. Max 3 instances per agent per review.
- **Discovery Pipeline**: independent-perspective (Research Scout) finds cross-domain insights → requests project-analyst deep investigation → docs-knowledge captures the entire discovery chain for institutional memory.

### Agent Improvement Path
1. Facilitator observes a pattern across multiple reviews (not a single incident)
2. Facilitator proposes a specific change with evidence (development note)
3. Steward evaluates against framework philosophy and principles
4. Developer approves the change
5. Change goes through `/review` like any code change

## Collaboration Mode Spectrum

The facilitator selects the mode per change:

1. **Ensemble** — independent contribution, no inter-agent exchange (lightest)
2. **Yes, And** — collaborative building, each agent builds on previous
3. **Structured Dialogue** — coopetitive exchange with multi-round discussion (default for significant changes)
4. **Dialectic Synthesis** — thesis-antithesis-synthesis with ACH matrix (high-stakes decisions)
5. **Adversarial** — red team, scoped to security/fault-injection/anti-groupthink only

### Exploration Intensity (orthogonal to collaboration mode)
- **Low**: Primary analysis with brief notes on alternatives
- **Medium**: 2-3 alternatives with trade-off analysis (default)
- **High**: Thorough exploration of alternatives, edge cases, failure modes

## Four-Layer Capture Stack

- **Layer 1 — Immutable Files**: `discussions/` — events.jsonl + transcript.md, sealed after closure
- **Layer 2 — Relational Index**: `metrics/evaluation.db` — SQLite for querying and metrics
- **Layer 3 — Curated Memory**: `memory/` — human-approved patterns and rules
- **Layer 4 — Optional Vector**: Only when corpus grows large enough

## Capture Pipeline

When a `/review`, `/deliberate`, `/analyze-project`, `/build_module`, `/retro`, or `/meta-review` command runs:
1. `scripts/create_discussion.py` creates the discussion directory and registers it in SQLite
2. Each agent turn is captured via `scripts/write_event.py` to events.jsonl
3. `scripts/close_discussion.py` seals the discussion (transcript generation, SQLite ingestion, findings extraction, pattern surfacing, agent effectiveness computation, read-only lock)
4. `scripts/record_yield.py` records protocol yield metrics into the `protocol_yield` table
5. Quality gate runs append JSONL records for trend analysis
6. `/knowledge-health` reports on all pipeline layers

## Knowledge Amplification Pipeline

1. **Findings Extraction**: Parses critique/proposal events into structured findings with severity and category
2. **Pattern Mining**: Clusters similar findings using Jaccard similarity. The `v_rule_of_three` view surfaces patterns appearing in 3+ discussions
3. **Agent Effectiveness**: Tracks per-agent uniqueness, survival rate, and confidence calibration
4. **Promotion Pipeline**: Recurring findings/reflections become promotion candidates. Human gate preserved (Principle #7)
5. **Forgetting Curve**: 90-day review flag, 180-day auto-archive for stale promoted knowledge
6. **Unified Rule of Three**: Combines adoption-log patterns with discussion-derived patterns

## Build Review Protocol

Mid-build checkpoint reviews enforce Principle #4 during code generation:

- **Triggers**: new module, architecture choice, database schema, security-relevant code, state management wiring, external API integration, UI flow / navigation
- **Exempt**: scaffolding, dependency config, pure test writing, theme/style-only, docs, final verification
- **Protocol**: 2 specialists dispatched per checkpoint, APPROVE or REVISE (under 200 words), max 2 rounds
- **Unresolved concerns**: Flagged with `risk_flags: ["unresolved-checkpoint"]` and surfaced in the build summary

## Commit Protocol

Every commit must pass two gates:

1. **Quality Gate** (automated): formatting, linting, tests, coverage (>= 80%), ADR completeness, review existence
2. **Code Review** (agent-assisted): `/review` before committing code changes. Auto-detects scope, produces structured report with verdict.

For low-risk changes (config, docs, simple fixes), the quality gate alone may suffice. For any code change, always run `/review` first.

## External Project Analysis

The `/analyze-project` command evaluates external projects for patterns worth adopting. The `/discover-projects` command finds candidates.

- Scoring: 5-dimension rubric out of 25. Only patterns >= 20/25 recommended.
- Adoption log tracks evaluated patterns and enforces the Rule of Three.
- Technology Grid profiles map project concepts using controlled vocabulary.
- The project's own profile (`_self.md`) enables direct comparison.

## ID Format Conventions

- **Discussion**: `DISC-YYYYMMDD-HHMMSS-slug`
- **ADR**: `ADR-NNNN` (zero-padded sequential)
- **Review**: `REV-YYYYMMDD-HHMMSS`
- **Reflection**: `REFL-YYYYMMDD-HHMMSS-agent`
- **Analysis**: `ANALYSIS-YYYYMMDD-HHMMSS-slug`

## Artifact Format Standard

All structured artifacts use **YAML frontmatter + Markdown body**:
```
---
key: value
---

## Section
Content here.
```

## Directory Layout (Framework Skeleton)

```
.claude/
  agents/       — Agent definitions (steward + facilitator + specialists)
  commands/     — Slash command workflows
  hooks/        — Automated lifecycle hooks
  rules/        — Auto-loaded standards (all agents inherit)
  skills/       — Reference knowledge (playbooks, checklists)
PHILOSOPHY.md   — Framework philosophy: why we work the way we do
FRAMEWORK.md    — This file: universal framework principles
CLAUDE.md       — Project-specific configuration
docs/
  adr/          — Architecture Decision Records
  reviews/      — Structured review reports
  sprints/      — Sprint plans and retrospectives
  templates/    — Reusable artifact templates
discussions/    — Layer 1: Immutable discussion capture
memory/         — Layer 3: Curated promoted knowledge
metrics/        — Layer 2: SQLite relational index + trend data
scripts/        — Capture pipeline utilities + quality gate + knowledge pipeline
BUILD_STATUS.md — Session state persistence
```

## Agent Invocation Pattern

```
Task(subagent_type="agent-name", prompt="...")
```

Model override (facilitator only, for harder tasks):
```
Task(subagent_type="agent-name", model="opus", prompt="...")
```

The facilitator collects all results and synthesizes a unified report. All agent turns are captured with `model:<tier>` tags for retrospective analysis.

## Framework Evolution

Changes to agent definitions, rules, or framework philosophy follow a gated path:

1. **Observation**: Facilitator identifies a pattern across multiple reviews
2. **Proposal**: Development note with evidence, diagnosis, and proposed change
3. **Steward Gate**: Steward evaluates alignment with `PHILOSOPHY.md` and the eight principles
4. **Developer Approval**: Human gate preserved
5. **Review**: Change goes through `/review` like any code change
