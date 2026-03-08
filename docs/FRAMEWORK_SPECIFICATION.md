---
title: "AI-Native Agentic Development Framework — Full Specification"
version: "2.1"
status: living-document
created: "2026-02-18"
last_updated: "2026-03-07"
origin: AI_Native_Agentic_Development_Framework_FULL.txt
total_files: ~130
total_lines: ~11,500
external_analyses: 7
patterns_evaluated: 59
patterns_adopted: 20
---

# AI-Native Agentic Development Framework v2.1

## Full Specification

> **Reasoning is the primary artifact. Code is output.**
>
> This framework operationalizes multi-agent collaborative rigor, structured decision lineage, automated discussion capture, relational evaluation integrity, and continuous self-improvement — all inside VS Code with Claude Code.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Foundational Principles](#2-foundational-principles)
3. [Four-Layer Capture Architecture](#3-four-layer-capture-architecture)
4. [Collaboration Model](#4-collaboration-model)
5. [Agent Architecture](#5-agent-architecture)
6. [Command Reference](#6-command-reference)
7. [Hook System — Safety & Automation](#7-hook-system--safety--automation)
8. [Security Architecture](#8-security-architecture)
9. [Quality & Testing Framework](#9-quality--testing-framework)
10. [Learning Architecture — Three Nested Loops](#10-learning-architecture--three-nested-loops)
11. [Education Gate](#11-education-gate)
12. [External Project Analysis & Onboarding](#12-external-project-analysis--onboarding)
13. [Reference Implementation — Todo API](#13-reference-implementation--todo-api)
14. [Configuration Reference](#14-configuration-reference)
15. [Implementation Status & Roadmap](#15-implementation-status--roadmap)
16. [Appendix A — External Project Provenance Table](#appendix-a--external-project-provenance-table)
17. [Appendix B — Artifact Templates & ID Conventions](#appendix-b--artifact-templates--id-conventions)
18. [Appendix C — Directory Layout](#appendix-c--directory-layout)

---

## 1. Executive Summary

This document is the authoritative specification for the AI-Native Agentic Development Framework v2.1 — a practical, implementable, AI-native development system designed for use inside VS Code with Claude Code.

### Origin

The framework originated from a research synthesis (`AI_Native_Agentic_Development_Framework_FULL.txt`) that integrated:

- Deep multi-agent collaboration theory
- Structured decision lineage (ADRs)
- SECI-based knowledge externalization
- Reflexive learning loops
- Practical Claude Code scaffolding
- Independent evaluation to prevent confirmation loops

### Evolution via External Project Analysis

After the initial implementation, **7 external projects** were systematically analyzed using the `/analyze-project` command, evaluating **59 distinct patterns** across a 5-dimension scoring rubric (prevalence, elegance, evidence, fit, maintenance — max 25 points). Of these:

- **20 patterns adopted** — integrated into the framework with full implementation
- **16 patterns deferred** — tracked for future consideration
- **18 patterns rejected** — documented with reasoning (preserving decision lineage per Principle #1)
- **5 patterns** achieved Rule of Three status (seen in 3+ independent projects)

The adoption history is tracked in [`memory/lessons/adoption-log.md`](../memory/lessons/adoption-log.md).

### Source Projects Analyzed

| # | Project | Repository | Analysis Date | Patterns Evaluated | Adopted |
|---|---------|-----------|--------------|-------------------|---------|
| 1 | ContractorVerification (SDD-Centric) | — | 2026-02-19 | 8 | 2 |
| 2 | CritInsight | Stott | 2026-02-19 | 8 | 3 |
| 3 | claude-agentic-framework | dralgorhythm | 2026-02-19 | 10 | 4 |
| 4 | wshobson/agents | wshobson | 2026-02-19 | 11 | 4 |
| 5 | self-learning-agent | daegwang | 2026-02-19 | 7 | 2 |
| 6 | self-improving-coding-agent | MaximeRobeyns | 2026-02-19 | 11 | 4 |
| 7 | AgenticAKM | sa4s-serc | 2026-02-19 | 4 | 1 |

Full provenance details are in [Appendix A](#appendix-a--external-project-provenance-table).

---

## 2. Foundational Principles

The framework is governed by 8 non-negotiable principles, codified in [`CLAUDE.md`](../CLAUDE.md). The original research defined principles 1–7; Principle 8 was adopted from external analysis.

### Principle 1: Reasoning is the Primary Artifact
> Code is output. Deliberation, trade-offs, and decision lineage are the durable assets. Every significant decision must be traceable to the discussion that produced it.

**Implementation**: The [Four-Layer Capture Architecture](#3-four-layer-capture-architecture) ensures all reasoning is captured in `discussions/` (Layer 1), indexed in SQLite (Layer 2), and optionally promoted to curated memory (Layer 3).

### Principle 2: Capture Must Be Automatic
> If logging depends on model compliance, it will fail. Structured commands must guarantee capture.

**Implementation**: All slash commands (see [Section 6](#6-command-reference)) invoke capture pipeline scripts automatically. The model cannot opt out of logging. Enforced at the command/tooling layer via [`scripts/create_discussion.py`](../scripts/create_discussion.py), [`scripts/write_event.py`](../scripts/write_event.py), and [`scripts/close_discussion.py`](../scripts/close_discussion.py).

### Principle 3: Collaboration Precedes Adversarial Rigor
> Multi-perspective analysis is the default. Adversarial modes are scoped exclusively to: security review (red-teaming), fault injection/stress testing, anti-groupthink checks.

**Implementation**: The [Collaboration Model](#4-collaboration-model) uses a 5-mode spectrum where adversarial mode is the last resort. The [`independent-perspective`](../.claude/agents/independent-perspective.md) agent provides anti-groupthink checks within the collaborative frame.

### Principle 4: Independence Prevents Confirmation Loops
> The agent that generates code must not be the sole evaluator. At minimum, one specialist who did not participate in generation must perform independent review.

**Implementation**: The [`/review`](../.claude/commands/review.md) command assembles a specialist panel where no single agent both proposes and evaluates. The [`facilitator`](../.claude/agents/facilitator.md) orchestrates but does not render specialist verdicts.

### Principle 5: ADRs Are Never Deleted
> Only superseded with references to the replacing decision. This creates an immutable decision history.

**Implementation**: ADRs in `docs/adr/` follow the `ADR-NNNN` format. The `decisions` table in SQLite tracks `supersedes` references. The [`quality_gate.py`](../scripts/quality_gate.py) `check_adrs()` function validates ADR completeness. *ADR completeness validation adopted from* ***AgenticAKM*** *(Score: 20/25,* [*ANALYSIS-20260219-043753*](reviews/ANALYSIS-20260219-043753-agenticakm.md)*).*

### Principle 6: Education Gates Before Merge
> Walkthrough, quiz, explain-back, then merge. Proportional to complexity and risk.

**Implementation**: The [`/quiz`](../.claude/commands/quiz.md) and [`/walkthrough`](../.claude/commands/walkthrough.md) commands invoke the [`educator`](../.claude/agents/educator.md) agent. Results are recorded to SQLite via [`scripts/record_education.py`](../scripts/record_education.py). See [Section 11](#11-education-gate) for details.

### Principle 7: Layer 3 Promotion Requires Human Approval
> No discussion insight is promoted automatically.

**Implementation**: The [`/promote`](../.claude/commands/promote.md) command requires 2+ independent confirmations plus explicit human approval. Promoted artifacts have a 90-day forgetting curve (must be reconfirmed or archived).

### Principle 8: Least-Complex Intervention First
> When improving the framework, prefer prompt changes before command/tool changes before agent definition changes before architectural changes. Lower-complexity interventions are cheaper, more reversible, and faster to validate.

**Implementation**: Codified in [`CLAUDE.md`](../CLAUDE.md) Principle #8 and referenced in [`architecture-consultant`](../.claude/agents/architecture-consultant.md) anti-patterns. *Adopted from* ***self-improving-coding-agent*** *(MaximeRobeyns, Score: 22/25,* [*ANALYSIS-20260219-043657*](reviews/ANALYSIS-20260219-043657-self-improving-coding-agent.md)*).*

---

## 3. Four-Layer Capture Architecture

The research report defined a 4-layer capture stack. This section maps each layer to its implementation.

### Layer 1 — Immutable Discussion Capture (Files)

Every canonical reasoning session creates an immutable discussion directory:

```
discussions/YYYY-MM-DD/DISC-YYYYMMDD-HHMMSS-slug/
  events.jsonl       # Machine-readable event stream (canonical record)
  transcript.md      # Human-readable rendering (generated from events.jsonl)
  artifacts/         # Any files produced during the discussion
  state.json         # Workflow resumption state (for interrupted sessions)
```

| Component | Implementing File | Status |
|-----------|------------------|--------|
| Discussion creation | [`scripts/create_discussion.py`](../scripts/create_discussion.py) — creates dated directory, initializes events.jsonl, registers in SQLite | **Implemented** |
| Event writing | [`scripts/write_event.py`](../scripts/write_event.py) — appends JSONL events with validation (7 intent types), auto-increments turn_id | **Implemented** |
| Transcript generation | [`scripts/generate_transcript.py`](../scripts/generate_transcript.py) — converts events.jsonl → transcript.md with YAML frontmatter | **Implemented** |
| Discussion closure | [`scripts/close_discussion.py`](../scripts/close_discussion.py) — orchestrates: transcript → ingest → mark closed → set read-only | **Implemented** |
| Workflow state persistence | `state.json` written by commands — enables session resumption on interruption | **Implemented** |

**State persistence** was *adopted from* ***wshobson/agents*** *(Score: 20/25,* [*ANALYSIS-20260219-040139*](reviews/ANALYSIS-20260219-040139-wshobson-agents.md)*).* Multi-phase commands write `state.json` to the discussion directory, enabling interrupted sessions to resume from the last completed phase.

#### Event Schema (JSONL)

Defined in [`docs/templates/event-schema.md`](templates/event-schema.md):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `discussion_id` | string | yes | Parent discussion ID (`DISC-YYYYMMDD-HHMMSS-slug`) |
| `turn_id` | integer | yes | Sequential within discussion, starting at 1 |
| `timestamp` | string (ISO 8601) | yes | When the turn occurred |
| `agent` | string | yes | Which specialist produced this turn |
| `reply_to` | integer or null | yes | Which turn_id this responds to |
| `intent` | enum | yes | `proposal` \| `critique` \| `question` \| `evidence` \| `synthesis` \| `decision` \| `reflection` |
| `content` | string | yes | Substantive content of the turn |
| `tags` | array[string] | yes | Topical tags for retrieval |
| `confidence` | float (0–1) | yes | Agent's self-assessed confidence |
| `risk_flags` | array[string] | no | Risk signals detected |

**Immutability Rule**: After closure, `events.jsonl` and `transcript.md` are sealed. Corrections require new discussions that reference the original.

### Layer 2 — Structured Relational Index (SQLite)

Stored at `metrics/evaluation.db`. Initialized by [`scripts/init_db.py`](../scripts/init_db.py).

#### Schema (5 tables, 10 indexes)

**`discussions`** — Master discussion registry

| Column | Type | Constraints |
|--------|------|------------|
| `discussion_id` | TEXT | PRIMARY KEY |
| `created_at` | DATETIME | NOT NULL |
| `closed_at` | DATETIME | |
| `risk_level` | TEXT | CHECK IN ('low', 'medium', 'high', 'critical') |
| `collaboration_mode` | TEXT | CHECK IN ('ensemble', 'yes-and', 'structured-dialogue', 'dialectic', 'adversarial') |
| `exploration_intensity` | TEXT | DEFAULT 'medium', CHECK IN ('low', 'medium', 'high') |
| `status` | TEXT | DEFAULT 'open', CHECK IN ('open', 'closed', 'reopened') |
| `linked_decision` | TEXT | |
| `linked_pr` | TEXT | |
| `agent_count` | INTEGER | DEFAULT 0 |

**`turns`** — Individual agent contributions

| Column | Type | Constraints |
|--------|------|------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `discussion_id` | TEXT | FK → discussions |
| `turn_id` | INTEGER | UNIQUE with discussion_id |
| `agent` | TEXT | NOT NULL |
| `reply_to` | INTEGER | |
| `intent` | TEXT | CHECK IN (7 intent values) |
| `timestamp` | DATETIME | NOT NULL |
| `confidence` | REAL | CHECK 0.0–1.0 |
| `content_hash` | TEXT | SHA-256 hash |

**`decisions`** — ADR linkage

| Column | Type | Constraints |
|--------|------|------------|
| `decision_id` | TEXT | PRIMARY KEY |
| `discussion_id` | TEXT | FK → discussions |
| `adr_path` | TEXT | NOT NULL |
| `supersedes` | TEXT | |
| `created_at` | DATETIME | NOT NULL |
| `status` | TEXT | CHECK IN ('accepted', 'superseded', 'deprecated') |

**`reflections`** — Agent self-assessments

| Column | Type | Constraints |
|--------|------|------------|
| `reflection_id` | TEXT | PRIMARY KEY |
| `discussion_id` | TEXT | FK → discussions |
| `agent` | TEXT | NOT NULL |
| `missed_signal` | TEXT | |
| `improvement_rule` | TEXT | |
| `confidence_delta` | REAL | |
| `promoted` | BOOLEAN | DEFAULT 0 |
| `created_at` | DATETIME | NOT NULL |

**`education_results`** — Education gate outcomes

| Column | Type | Constraints |
|--------|------|------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `session_id` | TEXT | NOT NULL |
| `discussion_id` | TEXT | FK → discussions |
| `bloom_level` | TEXT | CHECK IN ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create') |
| `question_type` | TEXT | CHECK IN ('recall', 'walkthrough', 'debug-scenario', 'change-impact', 'explain-back') |
| `score` | REAL | CHECK 0.0–1.0 |
| `passed` | BOOLEAN | NOT NULL |
| `timestamp` | DATETIME | NOT NULL |

**Indexes**: `idx_turns_discussion`, `idx_turns_agent`, `idx_turns_timestamp`, `idx_decisions_discussion`, `idx_reflections_discussion`, `idx_reflections_agent`, `idx_education_session`, `idx_education_discussion`, `idx_discussions_status`, `idx_discussions_created`.

#### Ingestion Pipeline

| Script | Function | Status |
|--------|----------|--------|
| [`scripts/ingest_events.py`](../scripts/ingest_events.py) | JSONL → SQLite `turns` table with SHA-256 hashing, INSERT OR IGNORE | **Implemented** |
| [`scripts/ingest_reflection.py`](../scripts/ingest_reflection.py) | Reflection YAML frontmatter → SQLite `reflections` table | **Implemented** (0% test coverage) |
| [`scripts/record_education.py`](../scripts/record_education.py) | Education results → SQLite `education_results` table | **Implemented** |

#### What SQLite Enables (from research report)

- Agent contribution scoring
- False positive rate tracking
- Time-to-consensus measurement
- Reopened decision analysis
- Decision churn metrics
- Drift detection across months

### Layer 3 — Curated Memory

```
memory/
  decisions/     # Promoted decision summaries
  patterns/      # Promoted code and process patterns
  reflections/   # Promoted agent reflections
  lessons/       # Adoption log (learning ledger)
  rules/         # Promoted rules (graduated to .claude/rules/)
  archive/       # Superseded or deprecated knowledge
```

**Promotion Pipeline**: Discussion → Reflection → Candidate Pattern → Human Approval → Rule/Pattern

| Component | Implementing File | Status |
|-----------|------------------|--------|
| Promotion workflow | [`/promote`](../.claude/commands/promote.md) command | **Implemented** |
| Requirements | 2+ independent confirmations + human approval | **Implemented** (in command spec) |
| Forgetting curve | 90-day expiry — artifacts must be reconfirmed or archived | **Implemented** (in command spec) |
| Adoption audit | [`memory/lessons/adoption-log.md`](../memory/lessons/adoption-log.md) — PENDING/CONFIRMED/REVERTED lifecycle | **Implemented** |
| Actual promotions | None yet — Layer 3 directories contain only `.gitkeep` files | **Planned** |

The **Adoption Audit Feedback Loop** was *adopted from* ***self-improving-coding-agent*** *(Score: 20/25,* [*ANALYSIS-20260219-043657*](reviews/ANALYSIS-20260219-043657-self-improving-coding-agent.md)*).* It closes the empirical feedback loop — without it, the adoption log was write-only.

### Layer 4 — Optional Vector Acceleration

**Status**: **Planned** — not yet implemented.

Per the research report, the vector layer is introduced only when:
- Discussion corpus grows large enough that keyword/FTS retrieval becomes insufficient
- Semantic recall is required

The vector index would key off stable `chunk_id` values derived from discussion events. **The vector layer never replaces the relational structure** — it accelerates retrieval only.

---

## 4. Collaboration Model

The framework uses a 5-mode collaboration spectrum with orthogonal exploration intensity. The [`facilitator`](../.claude/agents/facilitator.md) selects the appropriate mode based on risk assessment.

### Collaboration Mode Spectrum

| Mode | Description | When Used |
|------|-------------|-----------|
| **1. Ensemble** | Independent contribution, no inter-agent exchange | Low-risk changes (docs, config, simple fixes) |
| **2. Yes, And** | Collaborative building — each agent builds on previous | Additive features, brainstorming |
| **3. Structured Dialogue** | Coopetitive exchange with multi-round discussion | **Default for significant changes** |
| **4. Dialectic Synthesis** | Thesis-antithesis-synthesis with ACH matrix | High-stakes architectural decisions |
| **5. Adversarial** | Red team — scoped to security/fault-injection/anti-groupthink only | Security review, fault testing |

### Exploration Intensity (Orthogonal)

| Level | Description |
|-------|-------------|
| **Low** | Primary analysis with brief notes on alternatives |
| **Medium** | 2–3 alternatives with trade-off analysis (**default**) |
| **High** | Thorough exploration of alternatives, edge cases, failure modes |

### Risk-Based Activation

| Risk Level | Collaboration Mode | Exploration Intensity | Review Focus |
|------------|-------------------|----------------------|-------------|
| Low | Ensemble | Low | Docs, config, simple fixes |
| Medium | Structured Dialogue | Medium | New features, refactoring |
| High | Dialectic or Adversarial | High | Security, architecture, distributed systems |

### Anti-Compliance Measures

Complex commands embed **CRITICAL BEHAVIORAL RULES** at the top of their definitions, framing workflow adherence as correctness criteria rather than suggestions. This prevents LLM tendencies to shortcut multi-step processes. *Adopted from* ***wshobson/agents*** *(Score: 21/25,* [*ANALYSIS-20260219-040139*](reviews/ANALYSIS-20260219-040139-wshobson-agents.md)*).* Implemented in: [`/review`](../.claude/commands/review.md), [`/deliberate`](../.claude/commands/deliberate.md), [`/analyze-project`](../.claude/commands/analyze-project.md), [`/build_module`](../.claude/commands/build_module.md).

---

## 5. Agent Architecture

The framework deploys **11 specialist agents**, each with a defined role, model tier, activation triggers, and anti-patterns.

### Design Principles

- Subagents **cannot** spawn other subagents, except the **project-analyst** (delegated orchestrator for `/analyze-project`)
- The **facilitator** (main agent) orchestrates all other multi-agent workflows
- Multiple subagents can run concurrently with true parallelism
- Each subagent gets its own isolated context window
- Agents are invoked via the Task tool: `Task(subagent_type="agent-name", prompt="...")`

### Agent Roster

| Agent | Model Tier | File | Role |
|-------|-----------|------|------|
| **facilitator** | opus | [`.claude/agents/facilitator.md`](../.claude/agents/facilitator.md) | Orchestrates all multi-agent workflows; risk assessment, specialist assembly, synthesis, capture enforcement |
| **architecture-consultant** | opus | [`.claude/agents/architecture-consultant.md`](../.claude/agents/architecture-consultant.md) | Structural integrity, ADR validation, boundary enforcement, pattern consistency |
| **security-specialist** | sonnet | [`.claude/agents/security-specialist.md`](../.claude/agents/security-specialist.md) | OWASP Top-10, trust boundaries, auth/authz, red-team thinking |
| **qa-specialist** | sonnet | [`.claude/agents/qa-specialist.md`](../.claude/agents/qa-specialist.md) | Test adequacy, coverage analysis, edge cases, error handling |
| **performance-analyst** | sonnet | [`.claude/agents/performance-analyst.md`](../.claude/agents/performance-analyst.md) | Algorithmic complexity, hot paths, DB queries, scalability |
| **docs-knowledge** | sonnet | [`.claude/agents/docs-knowledge.md`](../.claude/agents/docs-knowledge.md) | Documentation completeness, ADR quality, CLAUDE.md currency, self-healing docs |
| **independent-perspective** | sonnet | [`.claude/agents/independent-perspective.md`](../.claude/agents/independent-perspective.md) | Anti-groupthink, hidden assumptions, pre-mortem, alternative exploration |
| **project-analyst** | sonnet | [`.claude/agents/project-analyst.md`](../.claude/agents/project-analyst.md) | External project scout + orchestrator for `/analyze-project` (two-phase: Survey → Orchestrate) |
| **educator** | haiku | [`.claude/agents/educator.md`](../.claude/agents/educator.md) | Walkthroughs, quizzes, Bloom's taxonomy assessment, mastery tier tracking |
| **steward** | sonnet | [`.claude/agents/steward.md`](../.claude/agents/steward.md) | Framework lineage tracking, drift detection, manifest validation, upstream-downstream relationship management |
| **ux-evaluator** | sonnet | [`.claude/agents/ux-evaluator.md`](../.claude/agents/ux-evaluator.md) | UX friction evaluation, interaction flow analysis, state feedback, platform conventions, accessibility |

### Model-Tier Assignment

Agents declare a `model:` tier in their YAML frontmatter for cost optimization:

| Tier | Purpose | Agents |
|------|---------|--------|
| **opus** | Complex generation and architectural reasoning | facilitator, architecture-consultant |
| **sonnet** | Analysis, review, and evaluation | security-specialist, qa-specialist, performance-analyst, independent-perspective, docs-knowledge, project-analyst, steward, ux-evaluator |
| **haiku** | Mechanical verification and lightweight tasks | educator |

*Model-tier assignment achieved* ***Rule of Three*** *status with 4 independent sightings: CritInsight, claude-agentic-framework, wshobson/agents, self-improving-coding-agent. Originally adopted from* ***CritInsight*** *(Score: 22/25 + 2 Rule of Three bonus = 24/25,* [*ANALYSIS-20260219-033023*](reviews/ANALYSIS-20260219-033023-critinsight.md)*).*

### "Use When" Activation Triggers

Each agent's description includes explicit activation criteria (`"Activate for: ..."`), following Anthropic's Agent Skills Specification. This guides the facilitator and Claude Code's agent selection in assembling the right panel for each task.

*Adopted from* ***wshobson/agents*** *(Score: 23/25,* [*ANALYSIS-20260219-040139*](reviews/ANALYSIS-20260219-040139-wshobson-agents.md)*).*

### Embedded Anti-Patterns

All 11 agent definitions include "Anti-patterns to avoid" sections with 5 domain-specific prohibitions each. Prohibitions are more actionable than permissions — each agent carries explicit guidance on what NOT to recommend, preventing over-flagging and off-target suggestions.

*Adopted from* ***self-improving-coding-agent*** *(Score: 20/25,* [*ANALYSIS-20260219-043657*](reviews/ANALYSIS-20260219-043657-self-improving-coding-agent.md)*).*

---

## 6. Command Reference

The framework provides **16 slash commands** in [`.claude/commands/`](../.claude/commands/). All commands include pre-flight checks that verify prerequisites before execution.

### Core Workflow Commands

#### `/review` — Multi-Agent Code Review
**File**: [`.claude/commands/review.md`](../.claude/commands/review.md) (270 lines)

10-step workflow:
1. Pre-flight checks (scripts, templates, DB)
2. Risk assessment and collaboration mode selection
3. Discussion creation via capture pipeline
4. Specialist assembly based on risk level
5. Independent analysis by each specialist
6. Cross-pollination round
7. Synthesis of findings
8. Verdict rendering (approve / approve-with-changes / request-changes / reject)
9. Report generation to `docs/reviews/`
10. Discussion closure

Features: CRITICAL BEHAVIORAL RULES framing, state.json persistence for session resumption.

#### `/deliberate` — Structured Multi-Agent Discussion
**File**: [`.claude/commands/deliberate.md`](../.claude/commands/deliberate.md) (164 lines)

Open-ended multi-agent discussion on any topic. Same state persistence pattern as `/review`.

#### `/build_module` — Module Construction
**File**: [`.claude/commands/build_module.md`](../.claude/commands/build_module.md) (92 lines)

Spec-driven module building with test-first approach and quality gates.

#### `/plan` — Feature Planning
**File**: [`.claude/commands/plan.md`](../.claude/commands/plan.md) (126 lines)

Creates executable specification documents with specialist review before implementation.

### Analysis & Learning Commands

#### `/analyze-project` — External Project Pattern Analysis
**File**: [`.claude/commands/analyze-project.md`](../.claude/commands/analyze-project.md) (327 lines)

Two-phase analysis of external projects:
- **Phase 1 (Survey)**: `project-analyst` scouts the target project
- **Phase 2 (Orchestrate)**: Domain specialists evaluate specific patterns

Uses a 5-dimension scoring rubric (prevalence, elegance, evidence, fit, maintenance) out of 25. Patterns scoring ≥ 20 are recommended for adoption. Integrates with [`memory/lessons/adoption-log.md`](../memory/lessons/adoption-log.md) and enforces the Rule of Three.

#### `/discover-projects` — GitHub Project Discovery
**File**: [`.claude/commands/discover-projects.md`](../.claude/commands/discover-projects.md) (57 lines)

Searches GitHub via `gh` CLI to find candidate projects for analysis.

#### `/retro` — Sprint Retrospective (Meso Loop)
**File**: [`.claude/commands/retro.md`](../.claude/commands/retro.md) (116 lines)

Queries SQLite for: reopened decisions, override frequency, frequent issue tags, time-to-resolution stats, adoption pattern evaluation.

#### `/meta-review` — Quarterly Framework Evaluation (Macro Loop)
**File**: [`.claude/commands/meta-review.md`](../.claude/commands/meta-review.md) (144 lines)

Agent effectiveness scoring, drift analysis, rule update candidates, decision churn index.

### Knowledge Management Commands

#### `/promote` — Artifact Promotion to Layer 3
**File**: [`.claude/commands/promote.md`](../.claude/commands/promote.md) (118 lines)

Promotes artifacts from Layers 1/2 to curated memory (Layer 3). Requires 2+ independent confirmations + human approval. 90-day forgetting curve.

#### `/onboard` — Project Takeover Protocol
**File**: [`.claude/commands/onboard.md`](../.claude/commands/onboard.md) (127 lines)

Steps: codebase mapping → reverse-engineered ADR creation → pattern extraction → baseline test generation → first structured discussion.

### Lineage & Release Commands

#### `/batch-evaluate` — Batch Adoption Evaluation
**File**: [`.claude/commands/batch-evaluate.md`](../.claude/commands/batch-evaluate.md)

Processes stale PENDING patterns from `memory/lessons/adoption-log.md`, reviews evidence, checks artifact existence, and presents batch verdicts for developer approval. Expected cadence: quarterly at meta-review, or when `/retro` flags stale-pending > 5.

#### `/knowledge-health` — Knowledge Pipeline Health Check
**File**: [`.claude/commands/knowledge-health.md`](../.claude/commands/knowledge-health.md)

Runs `scripts/knowledge_dashboard.py` to report on all pipeline layers (discussions, relational index, findings, patterns, curated memory). Includes forgetting curve status and promotion candidate checks. Appends results to `metrics/knowledge_pipeline_log.jsonl`.

#### `/lineage` — Framework Lineage Status
**File**: [`.claude/commands/lineage.md`](../.claude/commands/lineage.md)

Dispatches the Steward agent to report on framework lineage: drift analysis, manifest validation, and divergence tracking. Results are captured as a discussion via the standard capture pipeline.

#### `/ship` — Release Workflow
**File**: [`.claude/commands/ship.md`](../.claude/commands/ship.md)

Full release workflow: quality gate verification, testing checklist, version bump, changelog generation, and rollback strategy documentation. Requires all quality gate checks to pass before proceeding.

### Education Commands

#### `/quiz` — Bloom's Taxonomy Assessment
**File**: [`.claude/commands/quiz.md`](../.claude/commands/quiz.md) (48 lines)

Invokes the educator agent for comprehension assessment.

#### `/walkthrough` — Guided Code Walkthrough
**File**: [`.claude/commands/walkthrough.md`](../.claude/commands/walkthrough.md) (56 lines)

Invokes the educator agent for step-by-step code explanation.

### Cross-Cutting Command Features

All commands incorporate two patterns adopted from external projects:

**Pre-Flight Checks**: Every command verifies prerequisites (required scripts, directories, templates) before executing, with actionable error messages and recovery suggestions. *Adopted from* ***wshobson/agents*** *(Score: 20/25,* [*ANALYSIS-20260219-040139*](reviews/ANALYSIS-20260219-040139-wshobson-agents.md)*).*

**State-Persistent Workflows**: Multi-phase commands write `state.json` to the discussion directory, enabling session resumption on interruption. *Adopted from* ***wshobson/agents*** *(Score: 20/25,* [*ANALYSIS-20260219-040139*](reviews/ANALYSIS-20260219-040139-wshobson-agents.md)*).*

---

## 7. Hook System — Safety & Automation

The framework uses **7 logical hooks** (implemented in **10 files**) within Claude Code's hook system. Hooks provide automated safety enforcement and quality automation.

### PreToolUse Hooks (Before file writes, git operations)

#### 1. File Locking + Secret Detection + Protected Files
**Files**: [`.claude/hooks/pre-tool-use-validator.sh`](../.claude/hooks/pre-tool-use-validator.sh) → [`.claude/hooks/validate_tool_use.py`](../.claude/hooks/validate_tool_use.py) (233 lines)
**Trigger**: Write/Edit operations

Three protections in a single validator:

| Protection | Description |
|-----------|-------------|
| **File Locking** | Atomic lock via `mkdir`, 120s auto-expiry, session-based ownership. Prevents concurrent agent edits. |
| **Secret Detection** | Scans content for 12 secret patterns (API keys, AWS keys, JWT, GitHub PATs, private keys, exported secrets, Slack tokens, Bearer tokens, Anthropic keys, OpenAI keys, GCP API keys, GCP OAuth tokens). Test files are exempt. |
| **Protected Files** | Blocks edits to `.env`, `.git/`, `evaluation.db`, `.claude/settings.json`. |

- *File locking adopted from* ***claude-agentic-framework*** *(Score: 22/25,* [*ANALYSIS-20260219-035210*](reviews/ANALYSIS-20260219-035210-claude-agentic-framework.md)*).*
- *Secret detection adopted from* ***claude-agentic-framework*** *(Score: 23/25,* [*ANALYSIS-20260219-035210*](reviews/ANALYSIS-20260219-035210-claude-agentic-framework.md)*).*

#### 2. Pre-Commit Quality Gate
**File**: [`.claude/hooks/pre-commit-gate.sh`](../.claude/hooks/pre-commit-gate.sh)
**Trigger**: `git commit`

Intercepts commit commands and injects a reminder to run `python scripts/quality_gate.py`. Uses a 5-minute verification cache to avoid repetition.

*Adopted from* ***claude-agentic-framework*** *(Score: 22/25,* [*ANALYSIS-20260219-035210*](reviews/ANALYSIS-20260219-035210-claude-agentic-framework.md)*).*

#### 3. Push-to-Main Blocker
**File**: [`.claude/hooks/pre-push-main-blocker.sh`](../.claude/hooks/pre-push-main-blocker.sh)
**Trigger**: `git push`

Blocks direct pushes to `main`/`master` with remediation instructions for branch-based workflow.

*Adopted from* ***claude-agentic-framework*** *(Score: 22/25,* [*ANALYSIS-20260219-035210*](reviews/ANALYSIS-20260219-035210-claude-agentic-framework.md)*).*

### PostToolUse Hooks (After file writes)

#### 4. Auto-Format
**File**: [`.claude/hooks/auto-format.sh`](../.claude/hooks/auto-format.sh)
**Trigger**: Edit/Write of `.py` files

Runs `ruff format` + `ruff check --fix` on any Python file after every edit. Zero cognitive overhead — formatting is always automatic.

*Adopted from* ***CritInsight*** *(Score: 24/25,* [*ANALYSIS-20260219-033023*](reviews/ANALYSIS-20260219-033023-critinsight.md)*).*

#### 5. Lock Release
**Files**: [`.claude/hooks/post-tool-use-unlock.sh`](../.claude/hooks/post-tool-use-unlock.sh) → [`.claude/hooks/release_lock.py`](../.claude/hooks/release_lock.py)
**Trigger**: Edit/Write completion

Releases file locks acquired by the PreToolUse validator.

### Session Lifecycle Hooks

#### 6. PreCompact
**File**: [`.claude/hooks/pre-compact.ps1`](../.claude/hooks/pre-compact.ps1)
**Trigger**: Before context compaction (auto/manual)

Prompts the agent to update [`BUILD_STATUS.md`](../BUILD_STATUS.md) with current task state before context is compacted.

#### 7. SessionStart
**File**: [`.claude/hooks/session-start.ps1`](../.claude/hooks/session-start.ps1)
**Trigger**: Session resume or post-compaction

Prompts the agent to read `BUILD_STATUS.md` to restore working context.

*Session continuity hooks achieved* ***Rule of Three*** *status with 3 independent sightings: ContractorVerification (as "Session Initialization Protocol"), CritInsight, claude-agentic-framework. Score: 21/25 + 2 Rule of Three bonus = 23/25. Originally adopted from* ***CritInsight*** *(*[*ANALYSIS-20260219-033023*](reviews/ANALYSIS-20260219-033023-critinsight.md)*).*

### Hook Runtime State

Hooks use gitignored directories for runtime state:
- `.claude/hooks/.locks/` — Active file locks
- `.claude/hooks/.backups/` — File backups (from backup_utils.py)

---

## 8. Security Architecture

The framework implements a **dual-layer secret protection model** plus additional safety mechanisms.

### Layer 1: Write-Time Detection (PreToolUse Hook)

[`.claude/hooks/validate_tool_use.py`](../.claude/hooks/validate_tool_use.py) scans content at write time for **12 secret patterns**:

| # | Pattern | Regex Description |
|---|---------|------------------|
| 1 | Generic API Keys | `(?:api[_-]?key\|apikey).*['\"][A-Za-z0-9]{20,}` |
| 2 | AWS Access Keys | `AKIA[0-9A-Z]{16}` |
| 3 | JWT Tokens | `eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}` |
| 4 | GitHub PATs | `gh[ps]_[A-Za-z0-9]{36,}` |
| 5 | Private Keys | `-----BEGIN (?:RSA\|DSA\|EC\|OPENSSH)? ?PRIVATE KEY-----` |
| 6 | Exported Secrets | `export\s+[A-Z_]*(?:SECRET\|KEY\|TOKEN\|PASSWORD)` |
| 7 | Slack Tokens | `xox[bpors]-[A-Za-z0-9-]{10,}` |
| 8 | Bearer Tokens | `Bearer\s+[A-Za-z0-9._~+/=-]{20,}` |
| 9 | Anthropic API Keys | `sk-ant-[A-Za-z0-9-]{20,}` |
| 10 | OpenAI API Keys | `sk-[A-Za-z0-9]{20,}` |
| 11 | GCP API Keys | `AIza[A-Za-z0-9_-]{35}` |
| 12 | GCP OAuth Tokens | `ya29\.[A-Za-z0-9_-]{50,}` |

Test files (`test_`, `conftest.py`, `fixture`) are exempt from scanning.

*Adopted from* ***claude-agentic-framework*** *(Score: 23/25,* [*ANALYSIS-20260219-035210*](reviews/ANALYSIS-20260219-035210-claude-agentic-framework.md)*).*

### Layer 2: Read-Time Redaction

[`scripts/redact_secrets.py`](../scripts/redact_secrets.py) provides **15 regex patterns** for read-time secret redaction, preserving key names while masking values. Used when external content is read (e.g., during `/analyze-project`).

*Adopted from* ***self-learning-agent*** *(daegwang, Score: 22/25,* [*ANALYSIS-20260219-042113*](reviews/ANALYSIS-20260219-042113-self-learning-agent.md)*).*

### Protected Files

The validator blocks edits to:
- `.env` files
- `.git/` directory
- `evaluation.db`
- `.claude/settings.json`

### Backup-Before-Modify

[`scripts/backup_utils.py`](../scripts/backup_utils.py) (203 lines) provides:
- `backup_file()` — Creates timestamped backup
- `restore_latest()` — One-command undo
- `detect_conflicts()` — Checks for concurrent modifications
- `prune_backups()` — Cleans old backups

Backups stored in `.claude/hooks/.backups/` (gitignored). Mandatory path containment validation via `pathlib.Path.resolve()`.

*Adopted from* ***self-learning-agent*** *(Score: 21/25,* [*ANALYSIS-20260219-042113*](reviews/ANALYSIS-20260219-042113-self-learning-agent.md)*).*

**Status**: Fully coded and tested (12 tests) but **not yet invoked** by any hook or command. Integration is planned.

### Security Standards

Codified in [`.claude/rules/security_baseline.md`](../.claude/rules/security_baseline.md):
- Validate all user input at API boundaries using Pydantic models
- Use parameterized queries exclusively (no string interpolation in SQL)
- No secrets in source code or committed config files
- Configure CORS explicitly (no wildcard `*` in production)
- Pin dependency versions
- Review new dependencies for known vulnerabilities

Detailed checklists available in the [security-checklist skill](../.claude/skills/security-checklist/SKILL.md).

### Known Security Gaps (Planned)

| ID | Gap | Severity | Source |
|----|-----|----------|--------|
| R1 | Additional Anthropic/OpenAI/GCP key patterns needed | High | [REV-20260219-051846](reviews/REV-20260219-051846-framework-readiness.md) |
| R2 | Secret detection uses `ask` instead of `deny` permission | Medium | [REV-20260219-051846](reviews/REV-20260219-051846-framework-readiness.md) |

---

## 9. Quality & Testing Framework

### Quality Gate

[`scripts/quality_gate.py`](../scripts/quality_gate.py) (223 lines) runs **5 automated checks**:

| Check | Tool | Threshold | Skip Flag |
|-------|------|-----------|-----------|
| Formatting | `ruff format --check` | Clean | `--skip-format` |
| Linting | `ruff check` | No errors | `--skip-lint` |
| Tests | `pytest tests/` | All pass | `--skip-tests` |
| Coverage | `pytest --cov=src` | ≥ 80% | `--skip-coverage` |
| ADR Completeness | YAML + Markdown validation | All fields present | `--skip-adrs` |

**Usage**: `python scripts/quality_gate.py` (or `--fix` to auto-remediate formatting and lint issues)

The quality gate runs automatically via the git pre-commit hook ([`.claude/hooks/pre-commit-gate.sh`](../.claude/hooks/pre-commit-gate.sh)).

- *Quality gate script adopted from* ***ContractorVerification*** *(Score: 22/25,* [*ANALYSIS-20260219-010900*](reviews/ANALYSIS-20260219-010900-contractor-verification.md)*).*
- *ADR completeness validator adopted from* ***AgenticAKM*** *(Score: 20/25,* [*ANALYSIS-20260219-043753*](reviews/ANALYSIS-20260219-043753-agenticakm.md)*).*

### Structured Exception Hierarchy

[`src/exceptions.py`](../src/exceptions.py) defines a semantic exception tree:

```
AppError (base)
├── NotFoundError      → 404
├── ValidationError    → 422
└── ConflictError      → 409
```

[`src/error_handlers.py`](../src/error_handlers.py) provides centralized error handling that converts exceptions to consistent JSON responses with `(message, error_code, details, status_code)`.

Routes raise semantic exceptions (e.g., `NotFoundError("todo", id)`) — the centralized handler converts them to consistent JSON.

*Adopted from* ***ContractorVerification*** *(Score: 23/25,* [*ANALYSIS-20260219-010900*](reviews/ANALYSIS-20260219-010900-contractor-verification.md)*).*

### Test Infrastructure

**Configuration**: [`pyproject.toml`](../pyproject.toml) — Python ≥ 3.11, asyncio_mode=auto, coverage source=`src`, fail_under=80.

**Test Files**:

| File | Tests | Scope |
|------|-------|-------|
| [`tests/test_routes.py`](../tests/test_routes.py) | 15 | Async tests across 5 endpoint classes |
| [`tests/test_capture_pipeline.py`](../tests/test_capture_pipeline.py) | 24 | init_db, create_discussion, write_event, generate_transcript, ingest_events, record_education |
| [`tests/test_backup_utils.py`](../tests/test_backup_utils.py) | 12 | Path containment, backup, restore, detect_conflicts, prune |
| [`tests/test_redact_secrets.py`](../tests/test_redact_secrets.py) | ~20 | All 15 secret patterns, non-secrets, multiple matches |
| [`tests/test_simulated_review.py`](../tests/test_simulated_review.py) | 2 | End-to-end simulated `/review` workflow |

**Fixtures**: [`tests/conftest.py`](../tests/conftest.py) provides `test_db`, `client`, and `sample_todo` fixtures plus LLM/slow marker gating.

### LLM-Gated Test Markers

Tests can be gated with custom markers:

| Marker | Flag | Purpose |
|--------|------|---------|
| `@pytest.mark.uses_llm` | `--run-llm` | Tests that call real LLM APIs (skipped by default) |
| `@pytest.mark.slow` | `--run-slow` | Slow-running tests (skipped by default) |

The quality gate runs deterministic tests only. LLM-dependent and slow tests require explicit opt-in.

*Adopted from* ***self-improving-coding-agent*** *(Score: 24/25,* [*ANALYSIS-20260219-043657*](reviews/ANALYSIS-20260219-043657-self-improving-coding-agent.md)*).*

### Testing Standards

Codified in [`.claude/rules/testing_requirements.md`](../.claude/rules/testing_requirements.md):
- Unit tests for all business logic functions
- Integration tests for all API endpoints
- Target ≥ 80% coverage for new and modified code
- Every test must have meaningful assertions
- Test both success paths and error/edge cases
- Tests must be deterministic — no flaky tests
- Test files mirror source structure: `src/routes.py` → `tests/test_routes.py`
- Use descriptive test names: `test_create_todo_with_empty_title_returns_422`

Detailed strategies in the [testing-playbook skill](../.claude/skills/testing-playbook/SKILL.md).

### Coding Standards

Codified in [`.claude/rules/coding_standards.md`](../.claude/rules/coding_standards.md):
- Python 3.11+ required
- All public functions must have type annotations
- Google-style docstrings
- No bare `except:` — always catch specific exceptions
- No mutable default arguments
- Prefer `pathlib.Path` over `os.path`
- `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- Maximum function length: ~50 lines (guideline)
- Single responsibility per function

---

## 10. Learning Architecture — Three Nested Loops

The research report defined three nested improvement loops. The framework implements all three, though the micro loop trigger mechanism is still planned.

### Micro Loop — Per-Discussion Reflections

**Trigger**: After each discussion resolution
**Cycle**: Agent writes structured reflection → reflection inserted into SQLite → candidate improvement rule generated

| Component | Implementing File | Status |
|-----------|------------------|--------|
| Reflection template | [`docs/templates/reflection-template.md`](templates/reflection-template.md) | **Implemented** |
| Reflection ingestion | [`scripts/ingest_reflection.py`](../scripts/ingest_reflection.py) — parses YAML frontmatter → SQLite `reflections` table | **Implemented** (0% test coverage) |
| Trigger mechanism | No automated trigger exists — agents must be explicitly prompted to reflect | **Planned** |

### Meso Loop — Sprint Retrospectives

**Trigger**: End of sprint (developer-initiated)
**Command**: [`/retro`](../.claude/commands/retro.md)

Produces:
- Reopened decisions
- Override frequency
- Frequent issue tags
- Time-to-resolution stats
- Adoption pattern evaluation (PENDING → CONFIRMED/REVERTED)

**Status**: **Implemented** (command exists, not yet executed)

### Macro Loop — Quarterly Framework Evolution

**Trigger**: Quarterly (developer-initiated)
**Command**: [`/meta-review`](../.claude/commands/meta-review.md)

Produces:
- Agent effectiveness scoring
- Drift analysis
- Rule update candidates
- Decision churn index

**Status**: **Implemented** (command exists, not yet executed)

### Adoption Audit Feedback Loop

The adoption log at [`memory/lessons/adoption-log.md`](../memory/lessons/adoption-log.md) tracks a lifecycle for every adopted pattern:

```
PENDING → CONFIRMED (with evidence) or REVERTED (with reason)
```

Evaluation happens at the next `/retro` or `/meta-review` cycle. The question: *"Has this adoption produced measurable benefit, or is it inert/harmful?"*

*Adopted from* ***self-improving-coding-agent*** *(Score: 20/25,* [*ANALYSIS-20260219-043657*](reviews/ANALYSIS-20260219-043657-self-improving-coding-agent.md)*).*

### Learning Model

Learning operates at two levels (from research report):
- **Single-loop**: Threshold adjustments, parameter tuning within existing rules
- **Double-loop**: Criteria redefinition — changing what counts as "good" based on accumulated evidence

---

## 11. Education Gate

The education gate ensures developers understand AI-generated code before it's merged. Proportional to complexity and risk.

### Four-Step Gate Workflow

1. **Walkthrough** — Guided explanation of the code via [`/walkthrough`](../.claude/commands/walkthrough.md)
2. **Quiz** — Bloom's taxonomy assessment via [`/quiz`](../.claude/commands/quiz.md)
3. **Explain-back** — Developer explains the code in their own words
4. **Merge** — Only after steps 1–3 complete

### Assessment Dimensions (Bloom's Taxonomy)

| Level | Description | Question Type |
|-------|-------------|---------------|
| Remember | Recall facts | recall |
| Understand | Explain concepts | walkthrough |
| Apply | Use in new situations | — |
| Analyze | Break down components | debug-scenario |
| Evaluate | Make judgments | change-impact |
| Create | Produce new work | explain-back |

### Configuration

From [`.claude/rules/review_gates.md`](../.claude/rules/review_gates.md):
- Quiz pass threshold: **70%**
- Bloom's level mix: 60–70% Understand/Apply, 30–40% Analyze/Evaluate
- At least 1 debug scenario and 1 change-impact question per quiz
- Educational intensity adapts to demonstrated competence (scaffolding fades)

### Implementation

| Component | Implementing File | Status |
|-----------|------------------|--------|
| Quiz command | [`.claude/commands/quiz.md`](../.claude/commands/quiz.md) | **Implemented** |
| Walkthrough command | [`.claude/commands/walkthrough.md`](../.claude/commands/walkthrough.md) | **Implemented** |
| Educator agent | [`.claude/agents/educator.md`](../.claude/agents/educator.md) (haiku tier) | **Implemented** |
| Result recording | [`scripts/record_education.py`](../scripts/record_education.py) → SQLite `education_results` table | **Implemented** |
| Competence trend analysis | SQLite queries across `education_results` | **Implemented** (schema ready) |

---

## 12. External Project Analysis & Onboarding

### Outward-Facing Analysis

The framework can analyze external projects to discover adoptable patterns.

#### `/analyze-project` — Pattern Discovery

**Command**: [`.claude/commands/analyze-project.md`](../.claude/commands/analyze-project.md) (327 lines)
**Agent**: [`.claude/agents/project-analyst.md`](../.claude/agents/project-analyst.md) (255 lines)

**Two-Phase Process**:
1. **Phase 1 — Survey**: The `project-analyst` scouts the target project, identifying candidate patterns
2. **Phase 2 — Orchestrate**: Domain specialists (architecture, security, QA, independent) evaluate each pattern

**5-Dimension Scoring Rubric**:

| Dimension | Question | Scale |
|-----------|----------|-------|
| Prevalence | How widely used is this pattern? | 1–5 |
| Elegance | How clean is the implementation? | 1–5 |
| Evidence | Is there empirical evidence it works? | 1–5 |
| Fit | How well does it fit our framework? | 1–5 |
| Maintenance | How maintainable is the adoption? | 1–5 |

- Patterns scoring **≥ 20/25** → Recommended for adoption
- Patterns scoring **15–19** → Deferred (tracked for future consideration)
- Patterns scoring **< 15** → Rejected (documented with reasoning)

**Rule of Three**: When a pattern is seen in 3+ independent projects, it receives a +2 bonus to its score. Three sightings confirm a pattern is real, not coincidental.

**Template**: [`docs/templates/project-analysis-template.md`](templates/project-analysis-template.md)

#### `/discover-projects` — GitHub Search

**Command**: [`.claude/commands/discover-projects.md`](../.claude/commands/discover-projects.md) (57 lines)

Uses `gh` CLI to search GitHub for candidate projects matching specified criteria.

### Inward-Facing Onboarding

#### `/onboard` — Project Takeover Protocol

**Command**: [`.claude/commands/onboard.md`](../.claude/commands/onboard.md) (127 lines)

Five steps:
1. Codebase mapping
2. Reverse-engineered ADR creation
3. Pattern extraction
4. Baseline test generation
5. First structured discussion

### Analysis Track Record

As of 2026-02-19, 7 projects analyzed → 59 patterns evaluated → 20 adopted. Two patterns achieved Rule of Three:

| Pattern | Sightings | Projects | Final Score |
|---------|-----------|----------|-------------|
| Model-Tier Agent Assignment | 4 | CritInsight, claude-agentic, wshobson, self-improving | 24/25 |
| Session Continuity Hooks | 3 | ContractorVerification, CritInsight, claude-agentic | 23/25 |

---

## 13. Reference Implementation — Todo API

The framework includes a sample Todo API that demonstrates all framework patterns in practice. Reviews, tests, and discussions have all been exercised against this real code.

### Architecture

| File | Lines | Purpose |
|------|-------|---------|
| [`src/main.py`](../src/main.py) | 32 | FastAPI app with lifespan pattern, TodoDatabase creation, error handler registration |
| [`src/routes.py`](../src/routes.py) | 67 | 5 CRUD endpoints: list (with `?completed` filter), create, get, update, delete |
| [`src/models.py`](../src/models.py) | 29 | 3 Pydantic models: `TodoCreate`, `TodoUpdate` (input), `TodoResponse` (output) |
| [`src/database.py`](../src/database.py) | 97 | `TodoDatabase` class wrapping SQLite with WAL mode, full CRUD |
| [`src/exceptions.py`](../src/exceptions.py) | 64 | `AppError` base + `NotFoundError`, `ValidationError`, `ConflictError` |
| [`src/error_handlers.py`](../src/error_handlers.py) | 47 | Centralized handlers: `AppError` → structured JSON, generic `Exception` → 500 |

### Patterns Demonstrated

- **FastAPI lifespan context manager** for database lifecycle
- **Pydantic model separation** (input vs. output models)
- **SQLite with WAL mode** for concurrent reads
- **Structured exception hierarchy** with semantic error codes
- **Centralized error handling** (routes raise exceptions, handler converts to JSON)
- **Dependency injection** via FastAPI's `Depends()`
- **15 async tests** spanning all endpoints and error paths

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/todos` | List todos (optional `?completed=true/false` filter) |
| POST | `/todos` | Create a new todo |
| GET | `/todos/{todo_id}` | Get a specific todo |
| PATCH | `/todos/{todo_id}` | Update a todo |
| DELETE | `/todos/{todo_id}` | Delete a todo |

### Review History

The Todo API has been through structured multi-agent review:
- [REV-20260218-230957](reviews/REV-20260218-230957.md) — 5 agents, 7 turns. Verdict: approve-with-changes. Required: Replace global `_db` → `Depends()`, add `Path(gt=0)`, add whitespace validation.

---

## 14. Configuration Reference

### Project Configuration

**[`pyproject.toml`](../pyproject.toml)**:
- `requires-python = ">=3.11"`
- Ruff: `line-length = 99`, `target-version = "py311"`, rules: E, F, I, N, W, UP
- Pytest: `asyncio_mode = "auto"`
- Coverage: `source = ["src"]`, `fail_under = 80`

**[`requirements.txt`](../requirements.txt)** — 8 pinned dependencies:
- `fastapi`, `uvicorn[standard]`, `pydantic`
- `pytest`, `pytest-asyncio`, `httpx`, `pytest-cov`
- `ruff`

### Claude Code Configuration

**`.claude/settings.json`**:
- 9 allowed Bash commands: `python`, `pytest`, `ruff`, `sqlite3`, `git`, `pip`, `uvicorn`, `mkdir`, `ls`
- 5 hook configurations (PreToolUse ×3, PostToolUse ×2, PreCompact ×1, SessionStart ×1)

### Project Constitution

**[`CLAUDE.md`](../CLAUDE.md)** serves as the project constitution, loaded by all agents. Contains:
- 8 non-negotiable principles
- Architectural boundaries
- ID format conventions
- Directory layout
- Capture pipeline description
- Agent invocation pattern
- Commit protocol
- Error handling documentation
- Hook documentation

### Rule Files (Auto-Loaded)

All agents inherit 7 rule files from [`.claude/rules/`](../.claude/rules/):

| File | Scope |
|------|-------|
| [`build_review_protocol.md`](../.claude/rules/build_review_protocol.md) | Mid-build checkpoint reviews, Principle #4 enforcement |
| [`coding_standards.md`](../.claude/rules/coding_standards.md) | Python conventions, naming, structure |
| [`commit_protocol.md`](../.claude/rules/commit_protocol.md) | Quality gate → review → education gate → commit |
| [`documentation_policy.md`](../.claude/rules/documentation_policy.md) | What, where, and how to document |
| [`review_gates.md`](../.claude/rules/review_gates.md) | Quality thresholds, architectural gates, education gates |
| [`security_baseline.md`](../.claude/rules/security_baseline.md) | Input validation, DB security, secrets management, API security |
| [`testing_requirements.md`](../.claude/rules/testing_requirements.md) | Coverage, quality, isolation, organization, markers |

### Skill Reference Documents

5 reference playbooks in [`.claude/skills/`](../.claude/skills/):

| Skill | File | Scope |
|-------|------|-------|
| ADR Writing | [`.claude/skills/adr-writing/SKILL.md`](../.claude/skills/adr-writing/SKILL.md) | Quality criteria, lifecycle, common mistakes |
| Performance Playbook | [`.claude/skills/performance-playbook/SKILL.md`](../.claude/skills/performance-playbook/SKILL.md) | Complexity assessment, async patterns, N+1 detection |
| Python Project Patterns | [`.claude/skills/python-project-patterns/SKILL.md`](../.claude/skills/python-project-patterns/SKILL.md) | App factory, lifespan, DI, Pydantic separation |
| Security Checklist | [`.claude/skills/security-checklist/SKILL.md`](../.claude/skills/security-checklist/SKILL.md) | Structured checklist for security reviews |
| Testing Playbook | [`.claude/skills/testing-playbook/SKILL.md`](../.claude/skills/testing-playbook/SKILL.md) | pytest patterns, parametrize, edge cases |

### Session State

**[`BUILD_STATUS.md`](../BUILD_STATUS.md)** — ephemeral session state file. Read on session start, updated before compaction. Preserves in-flight context across sessions. Distinct from the four-layer capture stack.

---

## 15. Implementation Status & Roadmap

### Implemented & Operational

| Feature | Files | Evidence |
|---------|-------|---------|
| Layer 1 capture pipeline (create → write → generate → close) | `scripts/create_discussion.py`, `write_event.py`, `generate_transcript.py`, `close_discussion.py` | 10 discussions captured, 24+ tests |
| Layer 2 SQLite indexing | `scripts/init_db.py`, `ingest_events.py`, `record_education.py` | 5 tables, 10 indexes, tested |
| 11 agent definitions with model tiers | `.claude/agents/*.md` | All include activation triggers + anti-patterns |
| 16 slash commands | `.claude/commands/*.md` | Pre-flight checks, state persistence |
| 7 hooks (10 files) | `.claude/hooks/*` | File locking, secret detection, auto-format, session continuity |
| Quality gate (5 checks) | `scripts/quality_gate.py` + pre-commit hook | Runs on every commit |
| Sample Todo API with full CRUD + tests | `src/*.py` + `tests/test_routes.py` | 15 async tests, reviewed |
| Dual-layer secret detection (write-time + read-time) | `validate_tool_use.py` + `redact_secrets.py` | 12 + 15 patterns, tested |
| File locking system | `validate_tool_use.py` + `release_lock.py` | Atomic mkdir, 120s expiry |
| Session continuity | `pre-compact.ps1`, `session-start.ps1`, `BUILD_STATUS.md` | Hooks configured |
| Structured exception hierarchy | `src/exceptions.py`, `src/error_handlers.py` | AppError → JSON responses |
| LLM-gated test markers | `tests/conftest.py`, `pyproject.toml` | `--run-llm`, `--run-slow` |
| Adoption audit lifecycle | `memory/lessons/adoption-log.md` | 59 patterns tracked |
| 5 skill reference documents | `.claude/skills/*/SKILL.md` | Security, performance, testing, patterns, ADR |
| 7 auto-loaded rule files | `.claude/rules/*.md` | Coding, commit, docs, review, security, testing, build review |
| 5 artifact templates | `docs/templates/*.md` | ADR, event, analysis, reflection, review |
| Steward agent + lineage tracking | `.claude/agents/steward.md`, `scripts/lineage/`, `framework-lineage.yaml`, `.claude/custodian/` | ADR-0002 accepted, Phase 1 operational |
| UX evaluator agent | `.claude/agents/ux-evaluator.md` | Interaction flow, accessibility, platform conventions |
| Build review protocol | `.claude/rules/build_review_protocol.md` | Mid-build checkpoint reviews, Principle #4 |
| 4 new commands (batch-evaluate, knowledge-health, lineage, ship) | `.claude/commands/*.md` | Lineage, release, knowledge pipeline, adoption evaluation |
| Lineage test suite | `tests/test_lineage.py` | Manifest parsing, drift detection |
| Education documentation | `WALKTHROUGH.md`, `FRAMEWORK_QUIZ.md`, `EDUCATOR_NOTES.md`, `EDUCATION_GATE_*.md` | Full education gate materials |

### Implemented but Unused / Under-Tested

| Feature | Files | Gap |
|---------|-------|-----|
| Backup-before-modify utilities | `scripts/backup_utils.py` (203 lines, 12 tests) | Fully coded and tested but **never invoked** by any hook or command |
| Reflection ingestion | `scripts/ingest_reflection.py` (102 lines) | Script exists, **0% test coverage**, no documented invocation path |
| Quality gate script | `scripts/quality_gate.py` (223 lines) | Works via hook but has **0% direct test coverage** |
| Close discussion | `scripts/close_discussion.py` (66 lines) | ~33% test coverage |
| Layer 3 memory directories | `memory/decisions/`, `patterns/`, `reflections/`, `rules/` | Directories exist but contain only `.gitkeep` — **no promotions yet** |
| `/retro` and `/meta-review` commands | `.claude/commands/retro.md`, `meta-review.md` | Commands defined but **never executed** |

### Planned — Roadmap

#### From Readiness Review ([REV-20260219-051846](reviews/REV-20260219-051846-framework-readiness.md))

| ID | Finding | Severity | Description |
|----|---------|----------|-------------|
| R1 | Additional secret patterns | High | Add Anthropic, OpenAI, GCP key patterns to write-time detection |
| R2 | Escalate detection permission | Medium | Change secret detection from `ask` to `deny` |
| R3 | `ingest_reflection.py` tests | High | Add tests (0% coverage) |
| R4 | `quality_gate.py` tests | High | Add tests (0% coverage) |
| R5 | `close_discussion.py` coverage | Medium | Increase from ~33% to ≥ 80% |
| R6 | Additional ruff rules | Medium | Add B, ANN rules per coding_standards.md |
| R7 | Quality gate silent-pass fix | High | Fix silent-pass on empty test directories |
| R8 | Project-analyst subagent docs | Medium | Resolve spawning constraint vs CLAUDE.md documentation |
| R9 | CLAUDE.md drift fixes | Medium | Update secret count (6→12), memory directory layout |
| R10 | Document `ingest_reflection.py` path | Medium | Document invocation path or mark as planned |
| R11 | Dual-layer security ADR | Low | Document the dual-layer secret architecture decision |
| R12 | ADR-0001 cleanup | Low | Fix stale `discussion_id: null` |

#### From Gap Analysis

| Feature | Description | Priority |
|---------|-------------|----------|
| Micro-loop reflection trigger | Automated mechanism to prompt agents to reflect after discussions | Medium |
| Layer 4 vector acceleration | Optional semantic retrieval when corpus grows large | Low |
| Cross-platform session hooks | `.sh` equivalents for PowerShell-only hooks | Medium |
| Spec template for `/plan` | Referenced by command but doesn't exist in `docs/templates/` | Low |
| SQLite migration infrastructure | No schema migration mechanism for `evaluation.db` | Low |
| API pagination | List endpoint lacks pagination (flagged in review) | Low |
| Backup integration | Wire `backup_utils.py` into hooks/commands | Medium |
| Scripts coverage measurement | `pyproject.toml` coverage source is `src/` only — scripts excluded | Medium |

---

## Appendix A — External Project Provenance Table

Complete record of all 59 patterns evaluated across 7 external project analyses, grouped by source project. Status: **ADOPTED** / **DEFERRED** / **REJECTED**.

### 1. ContractorVerification (SDD-Centric) — [ANALYSIS-20260219-010900](reviews/ANALYSIS-20260219-010900-contractor-verification.md)

| Pattern | Score | Status | Implementing File(s) |
|---------|-------|--------|---------------------|
| Custom Exception Hierarchy with HTTP Status Mapping | 23/25 | **ADOPTED** (PENDING) | `src/exceptions.py`, `src/error_handlers.py` |
| Quality Gate Script | 22/25 | **ADOPTED** (PENDING) | `scripts/quality_gate.py`, pre-commit hook |
| Session Initialization Protocol | 18/25 | SUPERSEDED | Superseded by "Session Continuity Hooks" |
| Four-Phase Implementation Protocol with Self-Grading | 17/25 | DEFERRED | Overlaps education gates; self-grading conflicts with Principle #4 |
| Config-Driven Pydantic SelectorSpec | 16/25 | REJECTED | Domain-specific; no resource location problem |
| Stuck Record Recovery at Startup | 16/25 | REJECTED | No long-running operations |
| AI-Powered Config Auto-Repair | 15/25 | REJECTED | No configs to degrade |
| Version Bump Discipline | 13/25 | REJECTED | Unnecessary for a template, not a deployed service |

### 2. CritInsight (Stott) — [ANALYSIS-20260219-033023](reviews/ANALYSIS-20260219-033023-critinsight.md)

| Pattern | Score | Status | Implementing File(s) |
|---------|-------|--------|---------------------|
| PostToolUse Auto-Format Hook | 24/25 | **ADOPTED** (PENDING) | `.claude/hooks/auto-format.sh` |
| Model-Tier Agent Assignment | 22/25 | **ADOPTED** (PENDING) | All 11 agent YAML files |
| Session Continuity Hooks | 21/25 | **ADOPTED** (PENDING) | `pre-compact.ps1`, `session-start.ps1`, `BUILD_STATUS.md` |
| Spec-to-Code Mapping Table | 19/25 | DEFERRED | Project too small to benefit yet |
| Protocol-Based DI with Factory | 19/25 | DEFERRED | Over-engineered at ~345 LOC |
| Pipeline Context Object | 16/25 | DEFERRED | No multi-stage pipeline yet |
| Build Levels (L0/L1/L2) | 14/25 | REJECTED | Requires module restructuring |
| 5-Layer Safety Validation | 13/25 | REJECTED | Domain-specific to SQL validation |

### 3. claude-agentic-framework (dralgorhythm) — [ANALYSIS-20260219-035210](reviews/ANALYSIS-20260219-035210-claude-agentic-framework.md)

| Pattern | Score | Status | Implementing File(s) |
|---------|-------|--------|---------------------|
| Secret Detection in PreToolUse Hook | 23/25 | **ADOPTED** (PENDING) | `.claude/hooks/validate_tool_use.py` |
| Hook-Based File Locking | 22/25 | **ADOPTED** (PENDING) | `.claude/hooks/validate_tool_use.py`, `release_lock.py` |
| Pre-Commit Quality Gate Hook | 22/25 | **ADOPTED** (PENDING) | `.claude/hooks/pre-commit-gate.sh` |
| Pre-Push Main Branch Blocker | 22/25 | **ADOPTED** (PENDING) | `.claude/hooks/pre-push-main-blocker.sh` |
| Model-Tier Agent Assignment *(3rd sighting — Rule of Three)* | 22+2/25 | ADOPTED | (Already adopted from CritInsight) |
| Session Continuity Hooks *(3rd sighting — Rule of Three)* | 21+2/25 | ADOPTED | (Already adopted from CritInsight) |
| Tiered Workers with Focus Modes | 19/25 | DEFERRED | Conflicts with single-responsibility agent design |
| Skill Auto-Suggestion via Hook | 18/25 | DEFERRED | Adds TypeScript dependency |
| Swarm Plan→Execute→Review Pipeline | 17/25 | DEFERRED | Requires Beads dependency |
| Session Handoff via State Files | 17/25 | PARTIALLY SUPERSEDED | Intra-workflow aspect adopted as "State-Persistent Workflows" |
| Comprehensive Permissions Allowlist | 15/25 | REJECTED | Mostly JS/Docker/Terraform-focused |
| 65+ Categorized Skills Library | 14/25 | REJECTED | Most duplicate Claude's knowledge |

### 4. wshobson/agents — [ANALYSIS-20260219-040139](reviews/ANALYSIS-20260219-040139-wshobson-agents.md)

| Pattern | Score | Status | Implementing File(s) |
|---------|-------|--------|---------------------|
| "Use When" Activation Triggers | 23/25 | **ADOPTED** (PENDING) | All 11 agent description fields |
| CRITICAL BEHAVIORAL RULES Framing | 21/25 | **ADOPTED** (PENDING) | `review.md`, `deliberate.md`, `analyze-project.md`, `build_module.md` |
| State-Persistent Multi-Phase Workflows | 20/25 | **ADOPTED** (PENDING) | `review.md`, `deliberate.md`, `analyze-project.md` (state.json) |
| Pre-Flight Checks for Commands | 20/25 | **ADOPTED** (PENDING) | All 16 commands |
| Model-Tier Agent Assignment *(4th sighting)* | — | ADOPTED | (Already adopted) |
| `inherit` Model Tier | 18/25 | DEFERRED | Needs per-agent minimum tier guardrails |
| ACH Methodology for Independent Perspective | 18/25 | DEFERRED | Unproven in AI agent context |
| File Ownership Invariant | 16/25 | DEFERRED | Subagents are read-only; inapplicable |
| Three-Tier Progressive Disclosure for Skills | 14/25 | REJECTED | Requires Claude Code plugin infrastructure |
| Conductor Track Management | 13/25 | REJECTED | Different problem domain |
| Plugin Marketplace Architecture | 12/25 | REJECTED | Wrong scale for 11 agents |
| Agent-Teams Parallel Implementation | 10/25 | REJECTED | Requires experimental/unstable infrastructure |

### 5. self-learning-agent (daegwang) — [ANALYSIS-20260219-042113](reviews/ANALYSIS-20260219-042113-self-learning-agent.md)

| Pattern | Score | Status | Implementing File(s) |
|---------|-------|--------|---------------------|
| Redact-Before-AI-Send | 22/25 | **ADOPTED** (PENDING) | `scripts/redact_secrets.py` |
| Backup-Before-Modify with Atomic Revert | 21/25 | **ADOPTED** (PENDING) | `scripts/backup_utils.py` |
| Storage Layout Documentation | 19/25 | DEFERRED | Documentation gap, one point below threshold |
| Token Budget Allocation | 19/25 | DEFERRED | Prompts don't currently overflow |
| Rule Status Lifecycle | 18/25 | SUPERSEDED | Subsumed by "Adoption Audit Feedback Loop" |
| Adapter Registry for Multi-Agent Observation | 17/25 | REJECTED | No multi-agent-tool observation problem |
| Git History Bootstrapping | 11/25 | REJECTED | `discussions/` provides direct capture |

### 6. self-improving-coding-agent (MaximeRobeyns) — [ANALYSIS-20260219-043657](reviews/ANALYSIS-20260219-043657-self-improving-coding-agent.md)

| Pattern | Score | Status | Implementing File(s) |
|---------|-------|--------|---------------------|
| LLM-Gated Test Markers | 24/25 | **ADOPTED** (PENDING) | `tests/conftest.py`, `pyproject.toml` |
| Intervention Complexity Hierarchy | 22/25 | **ADOPTED** (PENDING) | `CLAUDE.md` — Principle #8 |
| Embedded Anti-Patterns in Agent Specializations | 20/25 | **ADOPTED** (PENDING) | All 9 `.claude/agents/*.md` files |
| Adoption Audit Feedback Loop | 20/25 | **ADOPTED** (PENDING) | `memory/lessons/adoption-log.md` |
| Capture Pipeline Roundtrip Tests | 19/25 | DEFERRED | One point below; no bugs observed yet |
| Tool Self-Documentation via generate_examples() | 15/25 | DEFERRED | Mechanism doesn't apply to our architecture |
| Model Failover Map | 15/25 | DEFERRED | No direct LLM API calls |
| Dynamic Tool Injection | 12/25 | REJECTED | No runtime tool registry control |
| Async LLM Overseer | 12/25 | REJECTED | Requires asyncio agent runtime |
| InheritanceFlags for Context Propagation | 12/25 | REJECTED | Requires event bus architecture |
| Compositional Agent IDs | 10/25 | REJECTED | Solves in-memory traversal; our capture is file-based |

### 7. AgenticAKM (sa4s-serc) — [ANALYSIS-20260219-043753](reviews/ANALYSIS-20260219-043753-agenticakm.md)

| Pattern | Score | Status | Implementing File(s) |
|---------|-------|--------|---------------------|
| ADR Completeness Validator | 20/25 | **ADOPTED** (PENDING) | `scripts/quality_gate.py` — `check_adrs()` |
| Survey Quality Gate (Generate-Verify-Regenerate) | 19/25 | DEFERRED | Fit scored 3/5; 2nd sighting of pipeline verification |
| Save-Last Artifact Persistence | 16/25 | DEFERRED | Already implicitly followed |
| CORRECT/INCORRECT Verdict Protocol | 14/25 | REJECTED | Binary verdicts too simplistic for our outputs |

### Summary Statistics

| Status | Count | Percentage |
|--------|-------|-----------|
| **ADOPTED** (PENDING) | 20 | 34% |
| DEFERRED | 16 | 27% |
| REJECTED | 18 | 31% |
| SUPERSEDED | 3 | 5% |
| Rule of Three achieved | 2 | — |

---

## Appendix B — Artifact Templates & ID Conventions

### ID Format Conventions

| Artifact | Format | Example |
|----------|--------|---------|
| Discussion | `DISC-YYYYMMDD-HHMMSS-slug` | `DISC-20260218-215011-test-pipeline` |
| ADR | `ADR-NNNN` (zero-padded sequential) | `ADR-0001` |
| Review | `REV-YYYYMMDD-HHMMSS` | `REV-20260218-230957` |
| Reflection | `REFL-YYYYMMDD-HHMMSS-agent` | `REFL-20260219-120000-security-specialist` |
| Analysis | `ANALYSIS-YYYYMMDD-HHMMSS-slug` | `ANALYSIS-20260219-010900-contractor-verification` |

### Artifact Format Standard

All structured artifacts use **YAML frontmatter + Markdown body**:

```markdown
---
key: value
---

## Section
Content here.
```

### Templates

| Template | File | Purpose |
|----------|------|---------|
| ADR | [`docs/templates/adr-template.md`](templates/adr-template.md) | YAML frontmatter (10 fields) + 4 sections (Context, Decision, Alternatives, Consequences) |
| Event Schema | [`docs/templates/event-schema.md`](templates/event-schema.md) | JSONL event field definitions, 7 intent values, immutability rule |
| Project Analysis | [`docs/templates/project-analysis-template.md`](templates/project-analysis-template.md) | Full `/analyze-project` output structure with scoring, anti-patterns, license section |
| Reflection | [`docs/templates/reflection-template.md`](templates/reflection-template.md) | Agent self-reflection with confidence calibration section |
| Review Report | [`docs/templates/review-report-template.md`](templates/review-report-template.md) | Review report YAML frontmatter + specialist findings sections |

---

## Appendix C — Directory Layout

```
agent_framework_template/
│
├── CLAUDE.md                          # Project constitution (loaded by all agents)
├── BUILD_STATUS.md                    # Ephemeral session state persistence
├── WALKTHROUGH.md                     # Guided framework walkthrough (45-60 min)
├── FRAMEWORK_QUIZ.md                  # Comprehension quiz for framework concepts
├── EDUCATOR_NOTES.md                  # Notes for the educator agent
├── EDUCATION_GATE_START.md            # Education gate entry point
├── EDUCATION_GATE_MANIFEST.md         # Education gate manifest
├── framework-lineage.yaml            # Lineage manifest (project-template relationship)
├── pyproject.toml                     # Python config: ruff, pytest, coverage
├── requirements.txt                   # 8 pinned dependencies
│
├── .claude/
│   ├── agents/                        # 11 specialist agent definitions
│   │   ├── facilitator.md             #   opus — orchestrator
│   │   ├── architecture-consultant.md #   opus — structural integrity
│   │   ├── security-specialist.md     #   sonnet — OWASP, red-team
│   │   ├── qa-specialist.md           #   sonnet — test adequacy
│   │   ├── performance-analyst.md     #   sonnet — complexity, scalability
│   │   ├── docs-knowledge.md          #   sonnet — documentation completeness
│   │   ├── independent-perspective.md #   sonnet — anti-groupthink
│   │   ├── project-analyst.md         #   sonnet — external project analysis
│   │   ├── educator.md               #   haiku — walkthroughs, quizzes
│   │   ├── steward.md                #   sonnet — framework lineage, drift detection
│   │   └── ux-evaluator.md           #   sonnet — UX friction, accessibility
│   │
│   ├── commands/                      # 16 slash commands
│   │   ├── analyze-project.md         #   External project analysis
│   │   ├── batch-evaluate.md          #   Batch adoption evaluation
│   │   ├── build_module.md            #   Spec-driven module building
│   │   ├── deliberate.md              #   Structured discussion
│   │   ├── discover-projects.md       #   GitHub search
│   │   ├── knowledge-health.md        #   Knowledge pipeline health check
│   │   ├── lineage.md                #   Framework lineage status
│   │   ├── meta-review.md             #   Quarterly framework evaluation
│   │   ├── onboard.md                 #   Project takeover protocol
│   │   ├── plan.md                    #   Feature planning
│   │   ├── promote.md                 #   Layer 3 memory promotion
│   │   ├── quiz.md                    #   Bloom's taxonomy quiz
│   │   ├── retro.md                   #   Sprint retrospective
│   │   ├── review.md                  #   Multi-agent code review
│   │   ├── ship.md                    #   Full release workflow
│   │   └── walkthrough.md             #   Guided code walkthrough
│   │
│   ├── hooks/                         # 10 files implementing 7 logical hooks
│   │   ├── pre-tool-use-validator.sh  #   Router for PreToolUse validation
│   │   ├── validate_tool_use.py       #   File locking + secret detection + protected files
│   │   ├── pre-commit-gate.sh         #   Quality gate reminder on commit
│   │   ├── pre-push-main-blocker.sh   #   Block push to main/master
│   │   ├── auto-format.sh             #   ruff format + check after edits
│   │   ├── post-tool-use-unlock.sh    #   Router for lock release
│   │   ├── release_lock.py            #   File lock release
│   │   ├── pre-compact.ps1            #   Save state before compaction
│   │   ├── session-start.ps1          #   Restore state on session start
│   │   ├── .locks/                    #   Runtime lock state (gitignored)
│   │   └── .backups/                  #   File backups (gitignored)
│   │
│   ├── custodian/                     # Steward lineage tracking
│   │   └── lineage-events.jsonl      #   Append-only lineage event log
│   │
│   ├── rules/                         # 7 auto-loaded rule files
│   │   ├── build_review_protocol.md  #   Mid-build checkpoint reviews
│   │   ├── coding_standards.md
│   │   ├── commit_protocol.md
│   │   ├── documentation_policy.md
│   │   ├── review_gates.md
│   │   ├── security_baseline.md
│   │   └── testing_requirements.md
│   │
│   └── skills/                        # 5 reference playbooks
│       ├── adr-writing/SKILL.md
│       ├── performance-playbook/SKILL.md
│       ├── python-project-patterns/SKILL.md
│       ├── security-checklist/SKILL.md
│       └── testing-playbook/SKILL.md
│
├── docs/
│   ├── FRAMEWORK_SPECIFICATION.md     # THIS DOCUMENT
│   ├── STEWARD_ARCHITECTURE.md       # Steward agent architecture and lineage design
│   ├── adr/                           # Architecture Decision Records
│   │   ├── ADR-0001-adopt-agentic-framework.md
│   │   └── ADR-0002-adopt-steward-agent.md
│   ├── reviews/                       # Review + analysis reports
│   │   ├── REV-*.md                   #   Code review reports
│   │   └── ANALYSIS-*.md             #   External project analyses
│   ├── sprints/                       # Sprint plans and retrospectives
│   ├── learning/                      # Education gate results
│   └── templates/                     # 5 artifact templates
│       ├── adr-template.md
│       ├── event-schema.md
│       ├── project-analysis-template.md
│       ├── reflection-template.md
│       └── review-report-template.md
│
├── discussions/                       # Layer 1: Immutable discussion capture
│   ├── 2026-02-18/
│   │   ├── DISC-20260218-215011-test-pipeline/
│   │   └── DISC-20260218-230957-review-routes/
│   └── 2026-02-19/
│       ├── DISC-20260219-004921-analyze-contractor-verification/
│       ├── DISC-20260219-032511-analyze-critinsight/
│       ├── DISC-20260219-034727-review-critinsight-adoption/
│       ├── DISC-20260219-035210-analyze-claude-agentic-framework/
│       ├── DISC-20260219-035401-analyze-wshobson-agents/
│       ├── DISC-20260219-041249-analyze-self-learning-agent/
│       ├── DISC-20260219-042737-analyze-agenticakm/
│       ├── DISC-20260219-042935-analyze-self-improving-coding-agent/
│       └── DISC-20260219-051846-framework-readiness-review/
│   ├── 2026-03-03/
│   │   └── DISC-20260303-183248-review-framework-enhancements-22-items/
│   └── 2026-03-07/
│       └── DISC-20260307-151526-review-steward-phase1/
│
├── memory/                            # Layer 3: Curated promoted knowledge
│   ├── archive/                       #   Superseded/deprecated
│   ├── bugs/
│   │   └── regression-ledger.md      #   Tracks fixed bugs and regression tests
│   ├── decisions/                     #   Promoted decision summaries
│   ├── lessons/
│   │   ├── adoption-log.md           #   Learning ledger (59 patterns tracked)
│   │   └── deploy-safety.md          #   Deployment safety lessons
│   ├── patterns/                      #   Promoted code/process patterns
│   ├── reflections/                   #   Promoted agent reflections
│   └── rules/                         #   Promoted rules (graduate to .claude/rules/)
│
├── metrics/                           # Layer 2: SQLite relational index + trend logs
│   ├── evaluation.db                  #   5 tables, 10 indexes
│   ├── quality_gate_log.jsonl        #   Quality gate run history
│   ├── knowledge_pipeline_log.jsonl  #   Knowledge pipeline health logs
│   ├── deploy_log.jsonl              #   Deployment trend log
│   └── emulator_test_log.jsonl       #   Test execution log
│
├── scripts/                           # Capture pipeline + quality utilities
│   ├── init_db.py                     #   SQLite schema creation
│   ├── create_discussion.py           #   Layer 1 discussion creation
│   ├── write_event.py                 #   JSONL event appender
│   ├── generate_transcript.py         #   events.jsonl → transcript.md
│   ├── ingest_events.py              #   JSONL → SQLite turns
│   ├── close_discussion.py            #   Orchestrates discussion closure
│   ├── ingest_reflection.py           #   Reflection → SQLite
│   ├── record_education.py            #   Education results → SQLite
│   ├── quality_gate.py                #   Quality enforcement checks
│   ├── redact_secrets.py              #   Read-time secret redaction (15 patterns)
│   ├── backup_utils.py               #   Backup/restore/conflict detection
│   ├── extract_findings.py           #   Parse events for structured findings
│   ├── mine_patterns.py              #   Cluster similar findings (Jaccard similarity)
│   ├── surface_candidates.py         #   Identify recurring patterns for promotion
│   ├── compute_agent_effectiveness.py #   Per-agent uniqueness/survival metrics
│   ├── record_yield.py               #   Protocol yield metrics
│   ├── knowledge_dashboard.py        #   Knowledge pipeline health check
│   ├── enforce_forgetting_curve.py   #   90-day forgetting curve enforcement
│   ├── pipeline_utils.py             #   Shared pipeline utilities
│   ├── check_stale_adoptions.py      #   Check stale adoption patterns
│   ├── unify_sightings.py            #   Unify pattern sightings across analyses
│   ├── backfill_findings.py          #   Backfill historical findings
│   ├── backfill_turn_content.py      #   Backfill turn content excerpts
│   └── lineage/                       #   Lineage tracking utilities
│       ├── __init__.py
│       ├── _utils.py                 #   Shared lineage helpers
│       ├── drift.py                  #   Drift detection between project and template
│       ├── init_lineage.py           #   Lineage initialization
│       └── manifest.py              #   Manifest parsing and validation
│
├── src/                               # Reference implementation (Todo API)
│   ├── __init__.py
│   ├── main.py                        #   FastAPI app with lifespan
│   ├── routes.py                      #   5 CRUD endpoints
│   ├── models.py                      #   Pydantic models
│   ├── database.py                    #   SQLite database wrapper
│   ├── exceptions.py                  #   Structured exception hierarchy
│   └── error_handlers.py             #   Centralized error handling
│
└── tests/                             # Test suite
    ├── conftest.py                    #   Fixtures + LLM/slow marker gating
    ├── test_routes.py                 #   15 async API tests
    ├── test_capture_pipeline.py       #   24 capture pipeline tests
    ├── test_backup_utils.py           #   12 backup utility tests
    ├── test_redact_secrets.py         #   ~20 secret redaction tests
    ├── test_lineage.py               #   Lineage manifest, drift detection tests
    └── test_simulated_review.py       #   2 end-to-end review simulation tests
```

---

## Document History

| Date | Change |
|------|--------|
| 2026-02-18 | Initial research synthesis (`AI_Native_Agentic_Development_Framework_FULL.txt`) |
| 2026-02-18 | Framework implementation begins — ADR-0001 accepted |
| 2026-02-18 | First discussions captured (test-pipeline, review-routes) |
| 2026-02-19 | 7 external projects analyzed, 59 patterns evaluated, 20 adopted |
| 2026-02-19 | Framework readiness review (REV-20260219-051846) — 12 required changes identified |
| 2026-02-19 | This specification document created |
| 2026-03-03 | Framework enhancements review — 22-item review (REV-20260303-183600) |
| 2026-03-07 | Steward agent adopted (ADR-0002), lineage tracking Phase 1 implemented |
| 2026-03-07 | UX evaluator agent added, build review protocol rule added |
| 2026-03-07 | Four new commands: `/batch-evaluate`, `/knowledge-health`, `/lineage`, `/ship` |
| 2026-03-07 | Specification refreshed to current project state (v2.1 counts updated) |
