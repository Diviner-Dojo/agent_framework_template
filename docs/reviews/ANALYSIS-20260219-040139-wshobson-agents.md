---
analysis_id: "ANALYSIS-20260219-040139-wshobson-agents"
discussion_id: "DISC-20260219-035401-analyze-wshobson-agents"
target_project: "https://github.com/wshobson/agents"
target_language: "Markdown/YAML (prompt engineering project)"
target_stars: "28,870"
agents_consulted: [project-analyst, architecture-consultant, docs-knowledge, qa-specialist, independent-perspective]
patterns_evaluated: 11
patterns_recommended: 4
analysis_date: "2026-02-19"
---

## Project Profile

- **Name**: wshobson/agents
- **Source**: https://github.com/wshobson/agents
- **Tech Stack**: Markdown + YAML frontmatter (prompt engineering project). JSON for marketplace catalog. One Python utility script. No application code.
- **Size**: 378 files (excluding .git), 497 Markdown files in plugins/, 146 SKILL.md files, 73 plugin.json manifests. ~0 LOC application code.
- **Maturity**: Active. Marketplace v1.5.1, semantic versioning per plugin. GitHub issue templates, code of conduct, contributing guide. Community contributions from 3+ external authors. No CI/CD pipeline. No test suite (prompt-only project).
- **AI Integration**: Sophisticated — the entire project IS the AI integration artifact. 73 Claude Code plugins containing 112 agent definitions, 79 commands, and 146 skills.

### Tech Stack Details

- **Format**: YAML frontmatter (name, description, model, tools, color) + Markdown body for all agent/command/skill definitions
- **Catalog**: `.claude-plugin/marketplace.json` — single JSON array of 73 plugin descriptors
- **Model assignment**: Explicit `model:` field per agent (opus/sonnet/haiku/inherit)
- **Tools**: Agents declare `tools:` arrays in frontmatter
- **Special fields**: `color:` for agent-teams visual distinction; `argument-hint:` for command parameter docs
- **One Python utility**: `tools/yt-design-extractor.py` (YouTube frame extraction — not core)

### Key Files Examined

| File | Significance |
|------|-------------|
| `.claude-plugin/marketplace.json` | 73-plugin registry with versioning |
| `docs/architecture.md` | Progressive disclosure philosophy, three-tier model strategy |
| `plugins/comprehensive-review/commands/full-review.md` | State-persistent multi-phase review orchestration |
| `plugins/conductor/commands/implement.md` | TDD-enforcing context-driven workflow with phase gates |
| `plugins/conductor/commands/new-track.md` | Interactive spec gathering with user approval gates |
| `plugins/agent-teams/README.md` | File ownership boundary enforcement for parallel agents |
| `plugins/agent-teams/agents/team-lead.md` | Multi-agent team orchestration protocol |
| `plugins/agent-teams/skills/parallel-debugging/SKILL.md` | ACH methodology for debugging |
| `plugins/agent-orchestration/commands/improve-agent.md` | Aspirational documentation (references non-existent infra) |
| `docs/agent-skills.md` | Skills catalog with progressive disclosure spec |
| `README.md` | Three-tier model strategy rationale |
| `.github/ISSUE_TEMPLATE/new_subagent.yml` | Quality gate for new agent contributions |
| `plugins/documentation-generation/agents/mermaid-expert.md` | Exemplar: focused, minimal agent definition |

---

## Specialist Findings

### Project Analyst — Scout Report (confidence: 0.92)

Surveyed 378 files across 73 plugins. Identified 6 notable patterns and 5 anti-patterns. The project is a mature, multi-agent Claude Code plugin ecosystem — fundamentally a breadth-optimized collection (73 plugins across many domains) compared to our depth-optimized framework (9 agents, focused on reasoning capture). The applicable patterns are workflow-level mechanics that can bolt onto our existing structure, not architectural philosophy that would change our direction.

Key finding: the project implicitly acknowledges limits of specialization — its own `full-review.md` command uses `subagent_type: "general-purpose"` for 3 of 8 sub-tasks despite having 112 specialized agents available.

### Architecture Consultant (confidence: 0.81)

Three patterns evaluated against our architectural boundaries:

1. **HIGH**: State-persistent workflow orchestration (`.full-review/*.md` file pattern) directly addresses session interruption gap in our multi-phase commands. Our `/review`, `/deliberate`, `/analyze-project` lose all progress on interruption.
2. **MEDIUM**: The `inherit` model tier is absent from our framework. Useful cost optimization but needs guardrails (independent-perspective raised degradation risk).
3. **LOW**: File ownership invariant for parallel agents is inapplicable now — our subagents are read-only reviewers.

Plugin marketplace architecture classified as inapplicable at our scale. Conductor track management solves a different problem domain than our discussions/ADRs pipeline.

### QA Specialist (confidence: 0.72)

Two applicable patterns:

1. **HIGH**: ACH methodology from `parallel-debugging/SKILL.md` — six failure-mode categories, evidence strength grading (Direct/Correlational/Testimonial/Absence), confidence thresholds, result arbitration. Substantially more rigorous than our independent-perspective pre-mortem analysis.
2. **MEDIUM**: Pre-flight session resumption check pattern. Our commands don't handle interrupted sessions.

Notable observation: the `full-review.md` command's CRITICAL BEHAVIORAL RULES framing ("Violating any of them is a failure") is borrowed from formal verification. More effective than our guideline prose.

No automated validation exists in the target project — a significant QA gap for a prompt-only project.

### Documentation & Knowledge (confidence: 0.83)

Three applicable patterns:

1. **HIGH**: "Use when" activation trigger convention in skill/agent descriptions. Our descriptions say what agents do; theirs specify when to invoke them. Immediately applicable to our 9 agents.
2. **MEDIUM**: Aspirational documentation anti-pattern — `improve-agent.md` references `parallel-test-runner` and `context-manager` that don't exist. Our commands should be audited for similar gaps.
3. **MEDIUM**: Structured issue template for new agent proposals (`.github/ISSUE_TEMPLATE/new_subagent.yml`). Low priority unless framework is shared.

Proposed new rule: agent descriptions must include explicit activation criteria using "Activate for:" phrasing.

### Independent Perspective (confidence: 0.79)

Two applicable patterns with important counter-arguments:

1. Cost as first-class concern via model-tier discipline. However, the `inherit` tier risks silent quality degradation when users set cost-saving session models. Needs documentation guardrails.
2. CRITICAL BEHAVIORAL RULES framing as formal correctness criteria rather than preferences.

**Hidden assumptions**: The project assumes Claude Code's plugin system is stable (it's experimental). The three-tier model strategy assumes Haiku is appropriate for "deterministic" tasks (Haiku's reliability on structured output is lower than Sonnet's). Agent-Teams requires experimental flag `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

**Key counter-argument**: Adopting breadth-optimized patterns (plugin isolation, minimal token usage) would optimize the wrong dimension for our depth-focused framework. Our value is reasoning quality, not token efficiency.

---

## Pattern Scorecard

| Pattern | Prevalence | Elegance | Evidence | Fit | Maintenance | Total | Sightings | Verdict |
|---------|-----------|----------|----------|-----|-------------|-------|-----------|---------|
| "Use When" Activation Triggers | 4 | 5 | 4 | 5 | 5 | **23/25** | 1 | ADOPT |
| CRITICAL BEHAVIORAL RULES Framing | 4 | 5 | 3 | 4 | 5 | **21/25** | 1 | ADOPT |
| State-Persistent Multi-Phase Workflows | 4 | 4 | 3 | 5 | 4 | **20/25** | 2* | ADOPT |
| Pre-Flight Checks for Commands | 4 | 4 | 4 | 4 | 4 | **20/25** | 1 | ADOPT |
| `inherit` Model Tier | 3 | 4 | 4 | 4 | 3 | **18/25** | 4** | DEFER |
| ACH Methodology for Debugging | 3 | 4 | 3 | 4 | 4 | **18/25** | 1 | DEFER |
| File Ownership Invariant | 3 | 4 | 3 | 2 | 4 | **16/25** | 2*** | DEFER |
| Progressive Disclosure for Skills | 3 | 4 | 3 | 2 | 2 | **14/25** | 1 | SKIP |
| Conductor Track Management | 3 | 4 | 2 | 1 | 3 | **13/25** | 1 | SKIP |
| Plugin Marketplace Architecture | 2 | 4 | 3 | 1 | 2 | **12/25** | 1 | SKIP |
| Agent-Teams Parallel Implementation | 2 | 3 | 2 | 1 | 2 | **10/25** | 1 | SKIP |

\* Related to "Session Handoff via State Files" (DEFERRED, 17/25) from claude-agentic-framework.
\** Model-Tier base pattern has Rule of Three (ADOPTED, 24/25); `inherit` is a new extension.
\*** Related to "Hook-Based File Locking" (RECOMMENDED, 22/25) from claude-agentic-framework.

---

## Recommended Adoptions

### "Use When" Activation Triggers (Score: 23/25)

- **What**: Every agent description includes explicit activation criteria using "Use when" or "Activate for" phrasing, specifying the conditions under which the agent should be invoked — not just what it does.
- **Where it goes**: All 9 agent files in `.claude/agents/*.md` — update `description:` fields. Optionally codify as a rule in `.claude/rules/`.
- **Why it scored high**: Perfect fit (5/5) and zero maintenance (5/5). Drops right into our existing agent frontmatter with no structural change.
- **Implementation notes**: Add activation criteria to each agent's description. Example: architecture-consultant changes from "Reviews code for structural alignment..." to "Reviews code for structural alignment, component boundaries, and architectural drift. Activate for architectural decisions, new modules, refactoring, or dependency changes."
- **Sightings**: 1 (first seen in wshobson/agents across all 146 SKILL.md files)

### CRITICAL BEHAVIORAL RULES Framing (Score: 21/25)

- **What**: Complex slash commands declare explicit pass/fail behavioral rules at the top of the command file, framed as correctness criteria rather than guidelines. E.g., "CRITICAL BEHAVIORAL RULES — You MUST follow these rules exactly. Violating any of them is a failure."
- **Where it goes**: Complex commands in `.claude/commands/` — particularly review.md, deliberate.md, analyze-project.md, build_module.md.
- **Why it scored high**: Zero maintenance cost (5/5), high elegance (5/5). It's a reframing, not a structural change. Borrowed from formal verification — treating workflow adherence as correctness.
- **Implementation notes**: Add a "CRITICAL BEHAVIORAL RULES" section at the top of complex commands listing the 3-5 non-negotiable behaviors as pass/fail assertions. E.g., "NEVER skip a specialist dispatch", "ALWAYS write events before synthesis", "HALT on failure — do not silently continue."
- **Sightings**: 1 (first seen in wshobson/agents, full-review.md)

### State-Persistent Multi-Phase Workflows (Score: 20/25)

- **What**: Long-running workflows write intermediate phase outputs to files (e.g., `.full-review/00-scope.md`, `01-quality.md`, `state.json`). Each subsequent phase reads prior phase output from disk rather than relying on context window memory. Includes session resumption check: on startup, if state.json exists with status "in_progress", ask user to resume or start fresh.
- **Where it goes**: Commands `/review`, `/deliberate`, `/analyze-project` — write phase outputs to the active discussion directory. Add state.json tracking workflow progress.
- **Why it scored high**: Perfect fit (5/5) — our multi-phase commands directly benefit. Addresses a real gap: interrupted sessions lose all progress.
- **Implementation notes**: For each multi-phase command: (1) write phase output to `discussions/<id>/phase-NN-<name>.md` after each phase completes, (2) maintain `discussions/<id>/state.json` with current phase and status, (3) on command startup check for existing in-progress state and offer resume.
- **Sightings**: 2 (related to "Session Handoff via State Files" from claude-agentic-framework, DEFERRED at 17/25)

### Pre-Flight Checks for Commands (Score: 20/25)

- **What**: Every command verifies its prerequisites exist before executing, with actionable error messages and recovery suggestions. E.g., Conductor commands check `conductor/product.md` exists → display error + suggest `/conductor:setup` if missing.
- **Where it goes**: All 12 commands in `.claude/commands/` — add a pre-flight check section.
- **Why it scored high**: Widely adopted pattern (evidence 4/5), good fit (4/5). Our commands currently assume their context exists; adding pre-flight checks prevents cryptic mid-workflow failures.
- **Implementation notes**: Each command should verify: (1) required scripts exist (`scripts/create_discussion.py`, etc.), (2) required directories exist (`discussions/`, `docs/reviews/`, etc.), (3) any command-specific prerequisites (e.g., `/retro` needs sprint data). On failure, display what's missing and how to fix it.
- **Sightings**: 1 (first seen in wshobson/agents, Conductor plugin)

---

## Anti-Patterns & Warnings

### Agent Definition Duplication Across Plugins

- **What**: `backend-architect.md` appears in at least 4 different plugins with identical or near-identical content. Bug fixes in one don't propagate.
- **Where seen**: `plugins/backend-development/agents/`, `plugins/api-scaffolding/agents/`, `plugins/database-cloud-optimization/agents/`
- **Why it's bad**: Maintenance burden scales with duplication count. Creates version drift between copies.
- **Our safeguard**: Our 9 agents each exist in exactly one location (`.claude/agents/`). Commands reference them by subagent_type, not by copying. Maintain this discipline.

### Aspirational Documentation as Executable Commands

- **What**: `improve-agent.md` references `parallel-test-runner`, `context-manager analyze-agent-performance`, and A/B testing infrastructure that doesn't exist anywhere in the repository.
- **Where seen**: `plugins/agent-orchestration/commands/improve-agent.md:11-26`
- **Why it's bad**: Users following the command will hit errors. Aspirational docs presented as runnable workflows erode trust.
- **Our safeguard**: Audit our 12 commands to verify every script call, tool reference, and infrastructure dependency actually exists. Add this check to our review process.

### No Automated Validation for Prompt Projects

- **What**: No CI pipeline validates frontmatter schema, description length, or command executability across 73 plugins.
- **Where seen**: Project-wide — no `.github/workflows/` for validation
- **Why it's bad**: Quality degrades silently at scale. The 6% version skew (docs say 67 plugins, marketplace has 73) is a symptom.
- **Our safeguard**: Our `scripts/quality_gate.py` already validates code quality. Consider extending it to validate agent/command frontmatter schema.

### Documentation Version Skew

- **What**: `docs/architecture.md` says "67 focused plugins" but `marketplace.json` has 73.
- **Where seen**: `docs/architecture.md:39` vs `marketplace.json`
- **Why it's bad**: Stale documentation misleads users and erodes trust.
- **Our safeguard**: Our CLAUDE.md has the same risk. Codify a trigger for updating CLAUDE.md when project conventions change (already documented in `.claude/rules/documentation_policy.md` but worth reinforcing).

---

## Deferred Patterns

### `inherit` Model Tier (Score: 18/25)

- **What**: A fourth model tier (`inherit`) that defers model selection to the user's session context, allowing cost-sensitive users to run non-critical agents on cheaper models.
- **Why deferred**: Maintenance burden scored 3/5 — needs guardrail documentation specifying which agents are safe for inheritance. Independent-perspective raised risk of silent quality degradation. Architecture-consultant and independent-perspective disagreed on adoption without guardrails.
- **Revisit if**: We document per-agent minimum tier requirements, or the base pattern (already Rule of Three with 4 sightings) makes the extension natural.

### ACH Methodology for Independent Perspective (Score: 18/25)

- **What**: Analysis of Competing Hypotheses (ACH) embedded in the independent-perspective agent: six failure-mode categories (Logic Error, Data Issue, State Problem, Integration Failure, Resource Issue, Environment), evidence strength taxonomy (Direct/Correlational/Testimonial/Absence), confidence calibration (>80%/50-80%/<50%), result arbitration (Confirmed/Plausible/Falsified/Inconclusive).
- **Why deferred**: Evidence scored 3/5 (ACH is established in intelligence analysis but novel in AI agent systems). Prevalence scored 3/5 (debugging/root-cause analysis is common but formalized ACH is rare).
- **Revisit if**: Our independent-perspective agent's pre-mortem analysis proves insufficiently rigorous, or we add explicit debugging workflows.

### File Ownership Invariant for Parallel Agents (Score: 16/25)

- **What**: When parallel agents modify the same codebase, enforce "one owner per file" — shared files handled sequentially by the lead agent, with interface contracts defined at boundaries before work begins.
- **Why deferred**: Fit scored 2/5 — our subagents are read-only reviewers, not parallel writers. This is sighting 2 (also seen as "Hook-Based File Locking" in claude-agentic-framework, 22/25, RECOMMENDED).
- **Revisit if**: We add parallel code-generation agents, or this pattern reaches Rule of Three (currently at 2 sightings).

---

## Specialist Consensus

- **Agents that agreed**: All 4 specialists (architecture-consultant, docs-knowledge, qa-specialist, independent-perspective) converged on state-persistent workflows and "Use when" activation triggers as the top patterns. 3/4 identified CRITICAL BEHAVIORAL RULES framing as valuable. 2/4 flagged pre-flight checks.
- **Notable disagreements**: The `inherit` model tier split the panel — architecture-consultant recommends (Medium), independent-perspective warns of silent quality degradation. Resolution: adopt only with documented guardrails per agent.
- **Strongest signal**: The "Use When" activation trigger pattern (23/25) is the single highest-impact, lowest-cost improvement. It immediately clarifies agent invocation criteria, follows Anthropic's published Agent Skills Specification, and requires only updating description fields in our existing 9 agent files.
- **Blind spot acknowledged**: The project uses `subagent_type: "general-purpose"` for 3/8 review sub-tasks despite having 112 specialized agents — an implicit admission that specialization has diminishing returns. Our framework should be aware of this tension rather than always defaulting to specialist dispatch.
