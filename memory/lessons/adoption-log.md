---
last_updated: "2026-02-28"
total_analyses: 8
patterns_evaluated: 75
patterns_adopted: 36
patterns_deferred: 16
patterns_rejected: 18
---

# Adoption Log (Learning Ledger)

This file tracks patterns discovered across external project analyses (`/analyze-project`). It serves as the template's learning memory — accumulating evidence across multiple reviews to identify which patterns are worth adopting.

## How This Works

1. Each `/analyze-project` run evaluates an external project and scores its patterns
2. Patterns scoring >= 20/25 are recommended for adoption
3. Patterns scoring 15-19 are deferred — tracked here for future consideration
4. Patterns scoring < 15 are rejected but noted briefly
5. **Rule of Three**: When a pattern is seen in 3+ independent projects, it gets +2 bonus to its score. Three sightings confirm a pattern is real, not coincidental.
6. **Adoption Audit Loop**: Adopted patterns follow a feedback lifecycle to track whether they actually worked:
   - **PENDING** — Adopted but not yet empirically evaluated. This is the initial state after implementation.
   - **CONFIRMED** — Evaluated and proved beneficial. Include evidence (e.g., "prevented 3 formatting issues in sprint 2", "quality gate caught secret in commit abc123").
   - **REVERTED** — Evaluated and proved harmful, unnecessary, or too costly to maintain. Include reason and date reverted.
   - Patterns are evaluated at the next `/retro` or `/meta-review` cycle after adoption. The question is: "Has this adoption produced measurable benefit, or is it inert/harmful?"

## How to Read Entries

Each entry records:
- **Pattern name** and description
- **Source**: Which project(s) it was seen in
- **Score**: 5-dimension score (prevalence, elegance, evidence, fit, maintenance) out of 25
- **Sightings**: How many independent projects exhibit this pattern
- **Status**: ADOPTED / DEFERRED / REJECTED (for adopted patterns, also tracks: PENDING / CONFIRMED / REVERTED)
- **Adoption Status**: (for ADOPTED patterns) PENDING → CONFIRMED or REVERTED with evidence
- **Location**: Where it was placed in our project (if adopted)

## Pattern Log

*Entries are added by `/analyze-project` as patterns are evaluated.*
*Most recent entries appear at the top.*

---

### Analysis: agentic_journal Framework Enhancements (2026-02-28)
**Source project**: `C:\Work\AI\agentic_journal` — Flutter/Dart journaling app, first real-world project built on this framework.
**Analysis report**: `docs/reviews/ANALYSIS-20260228-agentic-journal-framework-enhancements.md`
**Primary theme**: Regression prevention infrastructure
**All 16 patterns recommended for adoption** (confidence: 0.97; 13 from initial review + 3 from supplemental versioning review)

---

### Pattern: `/ship` Command — End-to-End Ship Workflow
- **First seen**: agentic_journal (2026-02-28, supplemental review)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 23/25 (prevalence:4, elegance:5, evidence:5, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/commands/ship.md` (new file). 8-step workflow: analyze → version bump → quality gate → review gate → education gate → commit → branch+PR → merge+sync. Direct git + `gh` CLI automation with version classification table.

### Pattern: `bump_version.py` — Semantic Version Utility
- **First seen**: agentic_journal (2026-02-28, supplemental review)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 22/25 (prevalence:4, elegance:5, evidence:5, fit:4, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `scripts/bump_version.py` + `scripts/test_bump_version.py` (both new). Reads/writes version in `pyproject.toml`. Flags: `--read`, `--patch`, `--minor`, `--major`. 8 unit tests including comment-preservation and one-line-changed structural invariant.

### Pattern: Version Bump at Ship Time (Not Commit Time)
- **First seen**: agentic_journal (2026-02-28, supplemental review)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 21/25 (prevalence:4, elegance:4, evidence:4, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `CLAUDE.md` — Commit Protocol section note. Architectural principle: version bumps belong in `/ship` (ship-time), not in manual commit steps.

---

### Pattern: Regression Ledger
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 25/25 (prevalence:5, elegance:5, evidence:5, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `memory/bugs/regression-ledger.md` (new file and directory). Tracks: Bug | File(s) | Root Cause | Fix | Regression Test | Date.

### Pattern: Commit Protocol — Regression Test Verification Step
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 24/25 (prevalence:4, elegance:5, evidence:5, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/rules/commit_protocol.md` — Step 1.5 between quality gate and code review.

### Pattern: Commit Protocol — Framework-Only Changes Threshold
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 22/25 (prevalence:4, elegance:4, evidence:5, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/rules/commit_protocol.md` — Step 2 extension. >5 framework files = medium-risk, requires `/review`.

### Pattern: Testing Requirements — Regression Tests Section
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 25/25 (prevalence:5, elegance:5, evidence:5, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/rules/testing_requirements.md` — new "Regression Tests" section at end.

### Pattern: Review Gates — Advisory Lifecycle
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 21/25 (prevalence:4, elegance:4, evidence:4, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/rules/review_gates.md` — new "Advisory Lifecycle" section. Requires carry-forward of open advisories and CLAUDE.md documentation upon acceptance.

### Pattern: Build Review Protocol — Dependency/Service Wiring Trigger
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 22/25 (prevalence:4, elegance:4, evidence:5, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/rules/build_review_protocol.md` — new trigger row + regression ledger check in specialist prompt template.

### Pattern: Education Gate Deferral Accountability
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 23/25 (prevalence:4, elegance:5, evidence:5, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `CLAUDE.md` — Principle 6 extended with deferral accountability language.

### Pattern: Plan Mode Boundary for build_module
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 21/25 (prevalence:4, elegance:4, evidence:4, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `CLAUDE.md` — Build Review Protocol section, explicit plan-mode boundary rule.

### Pattern: Known Limitations Documentation in CLAUDE.md
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 22/25 (prevalence:4, elegance:4, evidence:5, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `CLAUDE.md` — Known limitation annotations inline with Quality Gate and Commit Protocol sections.

### Pattern: QA-Specialist — Regression Prevention Responsibility
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 24/25 (prevalence:4, elegance:5, evidence:5, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/agents/qa-specialist.md` — new Responsibility 6: Regression Prevention section.

### Pattern: Review Command Session Resumption
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 20/25 (prevalence:3, elegance:4, evidence:4, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/commands/review.md` — pre-step session resumption check via state.json.

### Pattern: Review Gates — Provably Incorrect Data Threshold
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 21/25 (prevalence:3, elegance:4, evidence:5, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/rules/review_gates.md` — Minimum Quality Thresholds: provably incorrect API responses are blocking.

### Pattern: build_module Pre-Flight Rule File Verification
- **First seen**: agentic_journal (2026-02-28)
- **Analysis**: ANALYSIS-20260228-agentic-journal-framework-enhancements
- **Score**: 21/25 (prevalence:3, elegance:4, evidence:4, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/commands/build_module.md` — pre-flight checks extended to verify 4 required rule files exist.

---

### Pattern: ADR Completeness Validator
- **First seen**: sa4s-serc/AgenticAKM (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043753-agenticakm
- **Score**: 20/25 (prevalence:4, elegance:4, evidence:4, fit:4, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `scripts/quality_gate.py` — `check_adrs()` function. Validates required YAML frontmatter fields (adr_id, title, status, date, decision_makers, discussion_id) and required markdown sections (Context, Decision, Alternatives Considered, Consequences).
- **Decision**: ADRs are the most durable artifact in the four-layer capture stack (Principle #5). No machine-checkable completeness validation existed. Inspired by AgenticAKM Pydantic-validated ADR schema. All 3 specialists endorsed.
- **Date**: 2026-02-19

### Pattern: Survey Quality Gate (Generate-Verify-Regenerate for Phase 1)
- **First seen**: sa4s-serc/AgenticAKM (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043753-agenticakm
- **Score**: 19/25 (prevalence:4, elegance:4, evidence:4, fit:3, maintenance:4)
- **Sightings**: 2 (related to Swarm Plan-Execute-Review Pipeline -- both are decomposed pipeline with verification feedback)
- **Status**: DEFERRED
- **Reason**: Empirically validated but Fit scored 3/5. Only applicable where no deterministic verifier exists.
- **Revisit if**: 3rd sighting triggers Rule of Three (+2 bonus to 21/25). Or survey phase failure.

### Pattern: Save-Last Artifact Persistence
- **First seen**: sa4s-serc/AgenticAKM (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043753-agenticakm
- **Score**: 16/25 (prevalence:3, elegance:4, evidence:3, fit:3, maintenance:3)
- **Sightings**: 1
- **Status**: DEFERRED
- **Reason**: Already implicitly followed. Documentation-only change with low urgency.
- **Revisit if**: Interrupted session leaves partial artifact in docs/.

### Pattern: CORRECT/INCORRECT Verdict Protocol
- **First seen**: sa4s-serc/AgenticAKM (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043753-agenticakm
- **Score**: 14/25 (prevalence:3, elegance:3, evidence:3, fit:2, maintenance:3)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Our agent outputs require richer structure than binary verdicts.

### Pattern: LLM-Gated Test Markers
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 24/25 (prevalence:5, elegance:5, evidence:4, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `tests/conftest.py` (pytest_addoption + pytest_collection_modifyitems) + `pyproject.toml` (marker registration). Adds `--run-llm` and `--run-slow` CLI flags to gate expensive/flaky tests.
- **Decision**: Quality gate runs deterministic tests by default. LLM-dependent and slow tests require explicit opt-in flags. Prevents API outages from blocking all commits. All 3 specialists converged (architecture, QA, independent).
- **Date**: 2026-02-19

### Pattern: Intervention Complexity Hierarchy
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 22/25 (prevalence:4, elegance:5, evidence:3, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `CLAUDE.md` — Non-Negotiable Principle #8: "Least-complex intervention first." Prefer prompt changes → command/tool changes → agent definition changes → architectural changes.
- **Decision**: Documented decision-making principle that prevents over-engineering. Forces cheapest, most reversible interventions to be tried first. Directly referenced in architecture-consultant anti-patterns.
- **Date**: 2026-02-19

### Pattern: Embedded Anti-Patterns in Agent Specializations
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 20/25 (prevalence:4, elegance:4, evidence:3, fit:5, maintenance:4)
- **Sightings**: 1 (complements "Use When Activation Triggers" from wshobson/agents)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/agents/*.md` — all 9 agent definitions now include "Anti-patterns to avoid" sections with 5 domain-specific prohibitions each.
- **Decision**: Prohibitions are more actionable than permissions. Each agent now carries explicit guidance on what NOT to recommend, preventing over-flagging and off-target suggestions. Complements the activation triggers adopted from wshobson/agents.
- **Date**: 2026-02-19

### Pattern: Adoption Audit Feedback Loop
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 20/25 (prevalence:4, elegance:4, evidence:3, fit:5, maintenance:4)
- **Sightings**: 1 (related to "Rule Status Lifecycle" from self-learning-agent, 18/25, DEFERRED)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `memory/lessons/adoption-log.md` — format updated with PENDING/CONFIRMED/REVERTED lifecycle. Evaluation happens at next `/retro` or `/meta-review`.
- **Decision**: Closes the empirical feedback loop for adopted patterns. Without this, the adoption log was write-only — recording decisions but never outcomes. Subsumes previously deferred "Rule Status Lifecycle (reverted state)" pattern.
- **Date**: 2026-02-19

### Pattern: Capture Pipeline Roundtrip Tests
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 19/25 (prevalence:4, elegance:4, evidence:3, fit:4, maintenance:4)
- **Sightings**: 1
- **Status**: DEFERRED
- **Reason**: 1 point below threshold. events.jsonl has no serialization fidelity tests, but no silent corruption bugs have been observed yet. Medium implementation effort (3-4 hours).
- **Revisit if**: Silent serialization bugs are observed in events.jsonl, or the capture pipeline scripts are modified

### Pattern: Tool Self-Documentation via generate_examples()
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 15/25 (prevalence:3, elegance:4, evidence:3, fit:2, maintenance:3)
- **Sightings**: 1
- **Status**: DEFERRED
- **Reason**: Mechanism doesn't apply — our agents are invoked by Claude Code, not by LLM tool-spec parsing. The principle of co-locating examples with definitions is valuable in the abstract.
- **Revisit if**: We build an agent that dynamically selects subagents via system prompts

### Pattern: Model Failover Map
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 15/25 (prevalence:4, elegance:4, evidence:3, fit:1, maintenance:3)
- **Sightings**: 1
- **Status**: DEFERRED
- **Reason**: We don't make direct LLM API calls. Elegant data-driven failover pattern but solves a problem we don't have.
- **Revisit if**: Direct LLM API call infrastructure is added to the framework

### Pattern: Dynamic Tool Injection (Sequential Reasoning)
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 12/25 (prevalence:3, elegance:4, evidence:2, fit:1, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Requires runtime control over the tool registry. We don't control Claude Code's tool set. Our slash commands already provide sequential workflow structure.

### Pattern: Async LLM Overseer
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 12/25 (prevalence:3, elegance:4, evidence:2, fit:1, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Requires asyncio agent runtime where agents are Python tasks. Our framework uses synchronous Claude Code sessions. Oversight value is distributed across our existing patterns (facilitator review, independent-perspective, quality gates).

### Pattern: InheritanceFlags for Context Propagation
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 12/25 (prevalence:3, elegance:4, evidence:2, fit:1, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Requires event bus architecture. Our context propagation is handled by Claude Code's conversation model.

### Pattern: Compositional Agent IDs
- **First seen**: MaximeRobeyns/self_improving_coding_agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-043657-self-improving-coding-agent
- **Score**: 10/25 (prevalence:2, elegance:3, evidence:2, fit:1, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Solves in-memory agent tree traversal. Our Layer 1 capture is file-based and flat. Would duplicate existing capture differently and worse.

### Pattern: Redact-Before-AI-Send
- **First seen**: daegwang/self-learning-agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-042113-self-learning-agent
- **Score**: 22/25 (prevalence:5, elegance:4, evidence:4, fit:5, maintenance:4)
- **Sightings**: 1 (related but distinct from "Secret Detection in PreToolUse Hook" — that's write-time; this is send-time)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `scripts/redact_secrets.py` (utility function, 11 regex patterns with key-name preservation). Also augmented `.claude/hooks/validate_tool_use.py` with Slack (xox*) and Bearer header patterns (6 → 8 patterns).
- **Decision**: `/analyze-project` reads external project files and sends content raw to specialist agents — no secret filtering. This closes the read-time/send-time gap. Distinct from PreToolUse write-time detection. Security-specialist primary recommendation (confidence 0.88).
- **Date**: 2026-02-19

### Pattern: Backup-Before-Modify with Atomic Revert
- **First seen**: daegwang/self-learning-agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-042113-self-learning-agent
- **Score**: 21/25 (prevalence:4, elegance:5, evidence:3, fit:5, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `scripts/backup_utils.py` — `backup_file()`, `restore_latest()`, `detect_conflicts()`, `prune_backups()`. Backups stored in `.claude/hooks/.backups/` (gitignored). Mandatory path containment validation via `pathlib.Path.resolve()`.
- **Decision**: Framework file writes (.claude/rules/, CLAUDE.md, memory/) had no rollback path beyond manual git checkout. This provides one-command undo with conflict detection. Architecture-consultant primary recommendation (confidence 0.82). Security-specialist conditionally endorsed with path traversal mitigation (implemented).
- **Date**: 2026-02-19

### Pattern: Storage Layout Documentation
- **First seen**: daegwang/self-learning-agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-042113-self-learning-agent
- **Score**: 19/25 (prevalence:4, elegance:4, evidence:3, fit:4, maintenance:4)
- **Sightings**: 1
- **Status**: DEFERRED
- **Reason**: Documentation gap, not a code pattern. One point below threshold. CLAUDE.md describes the four-layer architecture conceptually but omits concrete storage formats (events.jsonl schema, discussion lifecycle, SQLite tables).
- **Revisit if**: New contributors report confusion about the data model, or onboarding friction is observed

### Pattern: Token Budget Allocation with Failure-Priority Compression
- **First seen**: daegwang/self-learning-agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-042113-self-learning-agent
- **Score**: 19/25 (prevalence:4, elegance:4, evidence:3, fit:4, maintenance:4)
- **Sightings**: 1
- **Status**: DEFERRED
- **Reason**: Our prompts don't currently overflow. The failure-priority sort applies to streaming event logs, not our structured discussion artifacts.
- **Revisit if**: Specialist agent prompts hit truncation errors, or discussions grow beyond ~100 events

### Pattern: Rule Status Lifecycle (reverted state)
- **First seen**: daegwang/self-learning-agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-042113-self-learning-agent
- **Score**: 18/25 (prevalence:3, elegance:4, evidence:3, fit:4, maintenance:4)
- **Sightings**: 2 (also seen as "Adoption Audit Feedback Loop" from self_improving_coding_agent)
- **Status**: SUPERSEDED by "Adoption Audit Feedback Loop" (ADOPTED, 20/25)
- **Reason**: The broader feedback loop pattern (PENDING/CONFIRMED/REVERTED) subsumes this narrower "reverted state" concept.

### Pattern: Adapter Registry for Multi-Agent Observation
- **First seen**: daegwang/self-learning-agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-042113-self-learning-agent
- **Score**: 17/25 (prevalence:3, elegance:4, evidence:3, fit:3, maintenance:4)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Solves multi-agent-tool observation (Claude + Codex + Cursor). We have no multi-agent-tool observation problem — our capture pipeline is single-source.

### Pattern: Git History Bootstrapping
- **First seen**: daegwang/self-learning-agent (2026-02-19)
- **Analysis**: ANALYSIS-20260219-042113-self-learning-agent
- **Score**: 11/25 (prevalence:2, elegance:3, evidence:2, fit:2, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Reconstructs AI sessions from git history. Not applicable — our discussions/ layer provides direct session capture.

### Pattern: "Use When" Activation Triggers in Agent Descriptions
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 23/25 (prevalence:4, elegance:5, evidence:4, fit:5, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/agents/*.md` (all 9 agent description fields)
- **Decision**: Agent descriptions now include explicit activation criteria ("Activate for..."). Follows Anthropic's Agent Skills Specification. All 4 specialists converged on this as highest-value, lowest-cost improvement.
- **Date**: 2026-02-19

### Pattern: CRITICAL BEHAVIORAL RULES Framing for Commands
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 21/25 (prevalence:4, elegance:5, evidence:3, fit:4, maintenance:5)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/commands/review.md`, `.claude/commands/deliberate.md`, `.claude/commands/analyze-project.md`, `.claude/commands/build_module.md`
- **Decision**: Complex commands now declare explicit pass/fail behavioral rules at the top. Frames workflow adherence as correctness criteria, not preferences. Borrowed from formal verification. 3/4 specialists endorsed.
- **Date**: 2026-02-19

### Pattern: State-Persistent Multi-Phase Workflows
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 20/25 (prevalence:4, elegance:4, evidence:3, fit:5, maintenance:4)
- **Sightings**: 2 (related to "Session Handoff via State Files" from claude-agentic-framework)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/commands/review.md`, `.claude/commands/deliberate.md`, `.claude/commands/analyze-project.md` (state.json + session resumption checks)
- **Decision**: Multi-phase commands now write state.json to discussion directory, enabling session resumption on interruption. All 4 specialists agreed on applicability. Addresses real gap — interrupted sessions previously lost all progress.
- **Date**: 2026-02-19

### Pattern: Pre-Flight Checks for Commands
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 20/25 (prevalence:4, elegance:4, evidence:4, fit:4, maintenance:4)
- **Sightings**: 1
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: All 12 commands in `.claude/commands/*.md`
- **Decision**: Every command now verifies prerequisites (required scripts, directories, templates) before executing, with actionable error messages and recovery suggestions. Prevents cryptic mid-workflow failures. 2/4 specialists endorsed.
- **Date**: 2026-02-19

### Pattern: `inherit` Model Tier
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 18/25 (prevalence:3, elegance:4, evidence:4, fit:4, maintenance:3)
- **Sightings**: 4 (extension of Model-Tier Agent Assignment, already Rule of Three)
- **Status**: DEFERRED
- **Reason**: Architecture-consultant recommends; independent-perspective warns of silent quality degradation when users set cost-saving session models. Needs per-agent minimum tier guardrails documented before adoption.
- **Revisit if**: Per-agent minimum tier requirements are documented, or user demand for cost control increases

### Pattern: ACH Methodology for Independent Perspective Agent
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 18/25 (prevalence:3, elegance:4, evidence:3, fit:4, maintenance:4)
- **Sightings**: 1
- **Status**: DEFERRED
- **Reason**: ACH is established in intelligence analysis but novel in AI agent systems. Six failure-mode taxonomy and evidence strength calibration are more rigorous than our current pre-mortem, but unproven in this context.
- **Revisit if**: Independent-perspective pre-mortem proves insufficiently rigorous, or we add explicit debugging workflows

### Pattern: File Ownership Invariant for Parallel Agents
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 16/25 (prevalence:3, elegance:4, evidence:3, fit:2, maintenance:4)
- **Sightings**: 2 (related to "Hook-Based File Locking" from claude-agentic-framework)
- **Status**: DEFERRED
- **Reason**: Our subagents are read-only reviewers, not parallel writers. Pattern is inapplicable at current scale.
- **Revisit if**: We add parallel code-generation agents, or 3rd sighting triggers Rule of Three

### Pattern: Three-Tier Progressive Disclosure for Skills
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 14/25 (prevalence:3, elegance:4, evidence:3, fit:2, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Requires Claude Code plugin infrastructure we don't use. Sound concept but high adoption cost for our architecture.

### Pattern: Conductor Track Management
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 13/25 (prevalence:3, elegance:4, evidence:2, fit:1, maintenance:3)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Different problem domain (feature implementation lifecycle vs. reasoning capture). Our discussion → ADR → memory pipeline serves the same intent.

### Pattern: Plugin Marketplace Architecture
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 12/25 (prevalence:2, elegance:4, evidence:3, fit:1, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Wrong scale for our 9 core agents. Plugin isolation solves a breadth problem we don't have.

### Pattern: Agent-Teams Parallel Implementation
- **First seen**: wshobson/agents (2026-02-19)
- **Analysis**: ANALYSIS-20260219-040139-wshobson-agents
- **Score**: 10/25 (prevalence:2, elegance:3, evidence:2, fit:1, maintenance:2)
- **Sightings**: 1
- **Status**: REJECTED
- **Reason**: Requires experimental Claude Code flag (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1) and tmux. Not stable infrastructure to build on.

### Pattern: Secret Detection in PreToolUse Hook
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 23/25 (prevalence:5, elegance:4, evidence:5, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/hooks/validate_tool_use.py` (secret detection section)
- **Decision**: Scans Write/Edit content for 6 secret patterns (API keys, AWS keys, JWT, GitHub PATs, PEM keys, exported secrets). Our security_baseline.md says "No secrets in code" but had no automated enforcement. Combined with file locking in single PreToolUse validator.
- **Date**: 2026-02-19

### Pattern: Hook-Based File Locking for Multi-Agent Conflict Prevention
- **First seen**: claude-agentic-framework (2026-02-19)
- **Also seen**: wshobson/agents (2026-02-19) as "File Ownership Invariant for Parallel Agents"
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 2
- **Score**: 22/25 (prevalence:4, elegance:5, evidence:4, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/hooks/validate_tool_use.py` (file locking section) + `.claude/hooks/release_lock.py`
- **Decision**: Atomic lock via mkdir, 120s auto-expiry, session-based ownership. PostToolUse hook releases locks. Runtime state in `.claude/hooks/.locks/` (gitignored). Second sighting in wshobson/agents confirms pattern.
- **Date**: 2026-02-19

### Pattern: Pre-Commit Quality Gate Hook
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 2 (also seen as PostToolUse Auto-Format in CritInsight)
- **Score**: 22/25 (prevalence:5, elegance:4, evidence:4, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/hooks/pre-commit-gate.sh`
- **Decision**: Intercepts git commit, injects reminder to run `python scripts/quality_gate.py`. Uses 5-minute verification cache. Bridges gap between having quality_gate.py and actually running it.
- **Date**: 2026-02-19

### Pattern: Pre-Push Main Branch Blocker
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 22/25 (prevalence:5, elegance:4, evidence:4, fit:4, maintenance:5)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/hooks/pre-push-main-blocker.sh`
- **Decision**: Denies git push to main/master with remediation instructions. Detects both explicit and implicit push-to-main patterns.
- **Date**: 2026-02-19

### Pattern: Tiered Workers with Focus Modes
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 19/25 (prevalence:3, elegance:5, evidence:3, fit:3, maintenance:5)
- **Status**: DEFERRED
- **Reason**: We already have 9 specialized agents with model tiers. Focus modes conflict with single-responsibility agent design (Principle #4).
- **Revisit if**: Agent count becomes unwieldy or token costs justify consolidation

### Pattern: Skill Auto-Suggestion via UserPromptSubmit Hook
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 18/25 (prevalence:3, elegance:5, evidence:3, fit:4, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Interesting concept but adds TypeScript dependency; skill-rules.json must stay in sync with skills directory
- **Revisit if**: Our skill library grows past 10+ playbooks

### Pattern: Swarm Plan→Execute→Review Pipeline
- **First seen**: claude-agentic-framework (2026-02-19)
- **Also seen**: sa4s-serc/AgenticAKM (2026-02-19) as "Survey Quality Gate (Generate-Verify-Regenerate)"
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 2
- **Score**: 17/25 (prevalence:3, elegance:5, evidence:3, fit:3, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Architecturally sound but requires Beads external dependency. Our /plan and /build_module partially cover this. Study decomposition patterns without adopting Beads.
- **Revisit if**: We need structured multi-agent execution workflows

### Pattern: Session Handoff via State Files
- **First seen**: claude-agentic-framework (2026-02-19)
- **Also seen**: wshobson/agents (2026-02-19) as "State-Persistent Multi-Phase Workflows"
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 2
- **Score**: 17/25 (prevalence:3, elegance:4, evidence:3, fit:4, maintenance:3)
- **Status**: PARTIALLY SUPERSEDED — the intra-workflow state persistence aspect was adopted as "State-Persistent Multi-Phase Workflows" (20/25) from wshobson/agents. The inter-session handoff aspect remains DEFERRED.
- **Reason**: We already have session continuity hooks. Handoff.json adds inter-session comms but unclear if we need it yet.
- **Revisit if**: Multi-agent workflows require explicit session-to-session handoff

### Pattern: Comprehensive Permissions Allowlist
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 15/25 (prevalence:4, elegance:3, evidence:4, fit:2, maintenance:2)
- **Status**: REJECTED
- **Reason**: Mostly JS/Docker/Terraform-focused; must be customized per project. Python-relevant subset is small.

### Pattern: 65+ Categorized Skills Library
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 14/25 (prevalence:3, elegance:4, evidence:3, fit:2, maintenance:2)
- **Status**: REJECTED
- **Reason**: Most skills duplicate knowledge Claude already has. Our focused 6-playbook approach is more maintainable. Categorization scheme is worth noting.

### Pattern: Model-Tier Agent Assignment [RULE OF THREE ACHIEVED]
- **Third sighting**: claude-agentic-framework (2026-02-19) — explicit model: field in agent YAML frontmatter
- **Fourth sighting**: wshobson/agents (2026-02-19) — model: opus/sonnet/haiku/inherit per agent, with documented selection rationale
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 4 (ContractorVerification, CritInsight, claude-agentic-framework, wshobson/agents)
- **Score**: 22/25 + 2 (Rule of Three bonus) = 24/25
- **Status**: ADOPTED (confirmed by Rule of Three)
- **Note**: Pattern validated across 4 independent projects. wshobson/agents adds `inherit` tier — deferred as separate pattern pending guardrail documentation.

### Pattern: Session Continuity Hooks [RULE OF THREE ACHIEVED]
- **Third sighting**: claude-agentic-framework (2026-02-19) — session-start-loader.sh + stop-validator.sh
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 3 (ContractorVerification, CritInsight, claude-agentic-framework)
- **Score**: 21/25 + 2 (Rule of Three bonus) = 23/25
- **Status**: ADOPTED (confirmed by Rule of Three)
- **Note**: Pattern validated across 3 independent projects. Confirmed as essential for agent workflow continuity.

### Pattern: PostToolUse Auto-Format Hook
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 24/25 (prevalence:5, elegance:5, evidence:4, fit:5, maintenance:5)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/hooks/auto-format.sh` + `.claude/settings.json`
- **Decision**: Automates ruff formatting after every file edit. Zero cognitive overhead, set-and-forget. We already use ruff; this makes it automatic.
- **Date**: 2026-02-19

### Pattern: Model-Tier Agent Assignment
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 22/25 (prevalence:4, elegance:5, evidence:3, fit:5, maintenance:5)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/agents/*.md` (all 9 agent files)
- **Decision**: Assigns opus to facilitator/architecture-consultant, sonnet to analysis agents, haiku to educator. Cost optimization with one-line-per-file change. 3/5 specialists converged.
- **Date**: 2026-02-19

### Pattern: Session Continuity Hooks
- **First seen**: ContractorVerification (2026-02-19) as "Session Initialization Protocol"
- **Also seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight (adopted), ANALYSIS-20260219-010900-contractor-verification (deferred as "Session Initialization Protocol")
- **Sightings**: 2
- **Score**: 21/25 (prevalence:5, elegance:4, evidence:3, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `.claude/hooks/pre-compact.ps1` + `.claude/hooks/session-start.ps1` + `BUILD_STATUS.md` + `.claude/settings.json`
- **Decision**: 2nd sighting of session persistence pattern. CritInsight's hook-based implementation is more mature than ContractorVerification's manual approach. Solves real problem of context loss across sessions. 4/5 specialists converged.
- **Supersedes**: "Session Initialization Protocol" (DEFERRED) — now ADOPTED with automated hooks.
- **Date**: 2026-02-19

### Pattern: Spec-to-Code Mapping Table
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 19/25 (prevalence:4, elegance:4, evidence:3, fit:4, maintenance:4)
- **Status**: DEFERRED
- **Reason**: Useful navigation aid but project is small enough that it's not yet needed
- **Revisit if**: Project grows to 10+ source modules or NLSpec-style specifications are added

### Pattern: Protocol-Based DI with Factory
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 19/25 (prevalence:5, elegance:4, evidence:5, fit:2, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Our project at ~345 LOC source would be over-engineered with full protocol DI
- **Revisit if**: We add 3+ components that need decoupling

### Pattern: Pipeline Context Object
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 16/25 (prevalence:4, elegance:4, evidence:3, fit:2, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Our framework uses a simpler sequential approach; no multi-stage processing pipeline yet
- **Revisit if**: We build a multi-stage processing pipeline

### Pattern: Build Levels (L0/L1/L2)
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 14/25 (prevalence:3, elegance:4, evidence:2, fit:2, maintenance:3)
- **Status**: REJECTED
- **Reason**: Requires restructuring module hierarchy. Optimized for greenfield AI-built projects. Not justified at current project size.

### Pattern: 5-Layer Safety Validation
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 13/25 (prevalence:3, elegance:4, evidence:2, fit:1, maintenance:3)
- **Status**: REJECTED
- **Reason**: Domain-specific to SQL validation. No multi-stage validation pipeline in our project to apply it to.

### Pattern: Custom Exception Hierarchy with HTTP Status Mapping
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 23/25 (prevalence:5, elegance:4, evidence:5, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `src/exceptions.py` + `src/error_handlers.py`
- **Decision**: Fills a concrete gap. Routes used bare HTTPException with no error_code, no structured details, no centralized logging. Three specialists converged on this recommendation.
- **Date**: 2026-02-19

### Pattern: Quality Gate Script
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 22/25 (prevalence:5, elegance:4, evidence:4, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Adoption Status**: PENDING
- **Location**: `scripts/quality_gate.py`
- **Decision**: Framework documents quality standards in 3 rules files but had no automated enforcement. Quality gate converts documented-but-unenforced standards into executable validation.
- **Date**: 2026-02-19

### Pattern: Session Initialization Protocol
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 18/25 (prevalence:3, elegance:4, evidence:3, fit:5, maintenance:3)
- **Status**: SUPERSEDED by "Session Continuity Hooks" (ADOPTED, 21/25)
- **Decision**: Originally deferred due to maintenance concerns. CritInsight's hook-based implementation (2nd sighting) solved the maintenance problem with automated PreCompact/SessionStart hooks. Adopted as "Session Continuity Hooks" above.

### Pattern: Four-Phase Implementation Protocol with Self-Grading
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 17/25 (prevalence:3, elegance:4, evidence:3, fit:3, maintenance:4)
- **Status**: DEFERRED
- **Decision**: Overlaps with existing education gates. Self-grading conflicts with Principle #4. Could be reframed as pre-review self-check.
- **Revisit if**: Agents demonstrate premature completion patterns

### Pattern: Config-Driven Pydantic SelectorSpec
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 16/25 (prevalence:3, elegance:5, evidence:5, fit:1, maintenance:2)
- **Status**: REJECTED
- **Decision**: Elegant design but deeply domain-specific. No resource location problem in our framework.

### Pattern: Stuck Record Recovery at Startup
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 16/25 (prevalence:4, elegance:3, evidence:4, fit:2, maintenance:3)
- **Status**: REJECTED
- **Decision**: Standard for stateful processing systems but our Todo API has no long-running operations.

### Pattern: AI-Powered Config Auto-Repair
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 15/25 (prevalence:2, elegance:4, evidence:3, fit:3, maintenance:3)
- **Status**: REJECTED
- **Decision**: Architecturally interesting but no configs to degrade and no health monitoring to detect degradation.

### Pattern: Version Bump Discipline
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 13/25 (prevalence:4, elegance:2, evidence:3, fit:1, maintenance:3)
- **Status**: REJECTED
- **Decision**: Unnecessary ceremony for a framework template that is not a deployed service.
